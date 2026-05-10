"""
Webhook Routes - Bank Callback & Reconciliation API

Endpoints:
- POST /webhooks/bange     → BANGE webhook callback (legacy, backward compat)
- POST /webhooks/{bank_code} → Generic webhook for any configured gateway
- GET  /transactions/...   → Bank transaction management
- POST /transactions/reconcile → Manual reconciliation
- GET  /bank-configurations → Bank config management
- GET  /gateways           → List registered payment gateways
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Request, Header
from fastapi.security import HTTPBearer
from typing import Dict, Any, Optional, List
from loguru import logger
import json

from app.modules.webhooks.models import (
    BankConfigurationCreate,
    BankConfigurationUpdate,
    BankConfigurationResponse,
    BankTransactionCreate,
    BankTransactionResponse,
    BankTransactionListResponse,
    ReconcileRequest,
    BangeWebhookPayload,
    BankCode,
)
from app.modules.webhooks.repositories import WebhookRepository
from app.modules.webhooks.services import HMACService
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database

# Import appointment service for post-payment confirmation
from app.modules.service_requests.services.appointment_service import appointment_service

# Import registry for multi-gateway webhook dispatch
from app.modules.payments.services.processors.registry import payment_processor_registry

router = APIRouter(tags=["Webhooks"])
security = HTTPBearer()
repository = WebhookRepository()
hmac_service = HMACService()


# ========== WEBHOOK CALLBACK (PUBLIC - NO AUTH) ==========

@router.post("/bange", status_code=status.HTTP_200_OK)
async def bange_webhook_callback(
    request: Request,
    x_bange_signature: Optional[str] = Header(None, description="BANGE HMAC signature"),
    db=Depends(get_database),
):
    """
    BANGE webhook callback endpoint (PUBLIC - no authentication)

    Headers:
        X-Bange-Signature: HMAC-SHA256 signature

    Body: BangeWebhookPayload (JSON)

    Idempotency: bank_code + bank_reference UNIQUE constraint
    """
    # Get raw body for HMAC validation
    body_bytes = await request.body()

    # Get BANGE bank configuration
    bank_config = await repository.get_bank_config_by_code(db, BankCode.BANGE.value)
    if not bank_config:
        logger.error("BANGE bank configuration not found")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bank not configured")

    # Validate HMAC signature
    is_valid, error_msg = await hmac_service.validate_webhook(
        body_bytes,
        x_bange_signature,
        bank_config.get("webhook_secret")
    )

    if not is_valid:
        logger.warning(f"Invalid BANGE webhook signature: {error_msg}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    # Parse payload
    try:
        payload_dict = json.loads(body_bytes.decode('utf-8'))
        payload = BangeWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error(f"Failed to parse BANGE webhook payload: {type(e).__name__}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload")

    # Check idempotency (prevent duplicates)
    existing = await repository.get_by_bank_reference(db, BankCode.BANGE.value, payload.bank_reference)
    if existing:
        logger.info(f"BANGE webhook duplicate: {payload.bank_reference}, returning existing transaction")
        return {"message": "Transaction already processed", "transaction_id": existing["id"]}

    # Create bank transaction
    bank_transaction = BankTransactionCreate(
        bank_code=BankCode.BANGE,
        bank_reference=payload.bank_reference,
        bank_transaction_date=payload.transaction_date,
        amount=payload.amount,
        currency=payload.currency,
        account_number=payload.account_number,
        account_holder_name=payload.account_holder,
        raw_data=payload_dict,
    )

    result = await repository.create_bank_transaction(db, bank_transaction)
    transaction_id = result["id"]

    logger.info(f"BANGE webhook received: {payload.bank_reference}, transaction_id: {transaction_id}")

    # Try auto-reconciliation (match by merchant_reference)
    if payload.merchant_reference:
        try:
            # Reconcile via service_payments (unified payment module)
            service_reconciled = await reconcile_service_payment(
                db,
                payload.merchant_reference,
                payload.bank_reference
            )
            if service_reconciled:
                logger.info(f"Auto-reconciled transaction {transaction_id} with service_payment")
                return {"message": "Transaction processed and reconciled", "transaction_id": transaction_id}
        except Exception as e:
            logger.warning(f"Auto-reconciliation failed: {e}, will require manual reconciliation")

    return {"message": "Transaction processed, awaiting reconciliation", "transaction_id": transaction_id}


# ========== GENERIC MULTI-GATEWAY WEBHOOK ==========

@router.post("/{bank_code}", status_code=status.HTTP_200_OK)
async def generic_webhook_callback(
    bank_code: str,
    request: Request,
    db=Depends(get_database),
):
    """
    Generic webhook receiver for any configured bank gateway.

    Dispatches to the appropriate gateway based on bank_code path parameter.
    Each gateway handles its own signature validation and payload parsing.

    Supported bank codes: BANGE, ECOBANK, ECOBANK_MPGS, BGFI, SGBGE, CCEIBANK (if configured).

    Security:
    - bank_code validated against registered gateways (no SQL injection)
    - HMAC signature validated per bank's algorithm
    - Idempotency via bank_code + bank_reference UNIQUE constraint
    """
    bank_code_upper = bank_code.upper()

    # Skip if this is the BANGE route (handled by dedicated endpoint above)
    if bank_code_upper == "BANGE":
        # Forward to the dedicated BANGE handler (avoids duplicate processing)
        # The BANGE endpoint is already registered at /bange
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /webhooks/bange endpoint for BANGE callbacks",
        )

    # 1. Get gateway processor from registry
    gateway_proc = payment_processor_registry.get_gateway_by_bank_code(bank_code_upper)
    if not gateway_proc:
        logger.warning(f"Webhook received for unconfigured bank: {bank_code_upper}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No gateway configured for bank: {bank_code_upper}",
        )

    # 2. Get raw body for signature validation
    body_bytes = await request.body()

    # 3. Validate signature (bank-specific)
    gateway = gateway_proc.gateway
    sig_header = gateway.get_webhook_signature_header()
    signature = request.headers.get(sig_header, "")

    if not gateway.verify_webhook_signature(body_bytes, signature):
        logger.warning(
            f"Invalid {bank_code_upper} webhook signature "
            f"(header: {sig_header})"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # 4. Parse webhook data (bank-specific → standard format)
    try:
        payload_dict = json.loads(body_bytes.decode("utf-8"))
        webhook_data = gateway.parse_webhook_data(payload_dict)
    except Exception as e:
        logger.error(f"Failed to parse {bank_code_upper} webhook payload: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    # 5. Check idempotency — use webhook_data.bank_code (not URL path param)
    # This handles sub-processors like ECOBANK_MPGS whose webhook_data.bank_code = "ECOBANK"
    effective_bank_code = webhook_data.bank_code
    existing = await repository.get_by_bank_reference(
        db, effective_bank_code, webhook_data.bank_reference
    )
    if existing:
        logger.info(
            f"{bank_code_upper} webhook duplicate: "
            f"{webhook_data.bank_reference}"
        )
        return {
            "message": "Transaction already processed",
            "transaction_id": existing["id"],
        }

    # 6. Create bank transaction record
    bank_transaction = BankTransactionCreate(
        bank_code=BankCode(effective_bank_code) if effective_bank_code in [e.value for e in BankCode] else BankCode.ECOBANK,
        bank_reference=webhook_data.bank_reference,
        bank_transaction_date=webhook_data.transaction_date,
        amount=webhook_data.amount,
        currency=webhook_data.currency,
        account_number=webhook_data.account_number,
        account_holder_name=webhook_data.account_holder_name,
        raw_data=payload_dict,
    )

    result = await repository.create_bank_transaction(db, bank_transaction)
    transaction_id = result["id"]

    logger.info(
        f"{bank_code_upper} webhook received: "
        f"{webhook_data.bank_reference}, "
        f"transaction_id: {transaction_id}"
    )

    # 7. Auto-reconciliation (reuse existing logic)
    if webhook_data.merchant_reference:
        try:
            service_reconciled = await reconcile_service_payment(
                db,
                webhook_data.merchant_reference,
                webhook_data.bank_reference,
            )
            if service_reconciled:
                logger.info(
                    f"Auto-reconciled {bank_code_upper} transaction "
                    f"{transaction_id} with service_payment"
                )
                return {
                    "message": "Transaction processed and reconciled",
                    "transaction_id": transaction_id,
                }
        except Exception as e:
            logger.warning(
                f"Auto-reconciliation failed for {bank_code_upper}: {e}"
            )

    return {
        "message": "Transaction processed, awaiting reconciliation",
        "transaction_id": transaction_id,
    }


# ========== GATEWAYS INFO (ADMIN) ==========

@router.get("/gateways/info")
async def list_registered_gateways(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(permission_required("webhook.view")),
):
    """
    List all registered payment gateways with their status.
    Requires webhook.view permission.
    """
    gateways = payment_processor_registry.get_registered_gateways()
    gateway_list = []

    for bank_code, proc in gateways.items():
        gateway = proc.gateway if hasattr(proc, "gateway") else None
        if gateway:
            try:
                healthy = await gateway.health_check()
            except Exception:
                healthy = False

            gateway_list.append({
                "bank_code": gateway.bank_code,
                "bank_name": gateway.bank_name,
                "supported_methods": gateway.get_supported_methods(),
                "webhook_signature_header": gateway.get_webhook_signature_header(),
                "healthy": healthy,
            })

    return {"gateways": gateway_list}


# ========== BANK TRANSACTIONS (AUTHENTICATED) ==========

# ========== HELPER: Confirm appointment after payment ==========

async def confirm_appointment_for_payment(db, payment_id: str):
    """
    After successful payment reconciliation, confirm any held appointment.
    
    Flow:
    1. Find service_request with this payment_id
    2. If found, confirm the appointment hold
    """
    try:
        # Find service_request linked to this payment
        query = "SELECT id FROM service_requests WHERE payment_id = $1"
        result = await db.fetchrow(query, payment_id)
        
        if result:
            service_request_id = result["id"]
            confirm_result = await appointment_service.confirm_hold(db, service_request_id)
            if confirm_result.success:
                logger.info(f"Appointment confirmed for service_request {service_request_id} after payment {payment_id}")
            else:
                logger.warning(f"Failed to confirm appointment for service_request {service_request_id}: {confirm_result.error}")
        else:
            logger.debug(f"No service_request linked to payment {payment_id}")
    except Exception as e:
        logger.error(f"Error confirming appointment for payment {payment_id}: {e}")




async def reconcile_service_payment(db, merchant_reference: str, gateway_transaction_id: str) -> bool:
    """
    Reconcile a service_payment based on merchant_reference (our payment_reference).
    Called by bank webhook to mark payments as completed.

    Flow:
    1. Find pending payment by reference
    2. Update status to completed
    3. Generate receipt PDF and store in Firebase
    4. Publish PAYMENT_COMPLETED event for notifications
    5. Confirm appointment if applicable
    """
    from app.modules.payments.services.receipt_service import receipt_service
    from app.core.events import EventBus, EventType
    from datetime import datetime, timezone

    try:
        # 1. Get payment with all necessary data
        query = """
            SELECT sp.id, sp.service_request_id, sp.status, sp.user_id,
                   sp.payment_method, sp.total_amount, sp.currency,
                   sp.calculation_details
            FROM service_payments sp
            WHERE sp.payment_reference = $1
            AND sp.status IN ('pending', 'processing')
        """
        payment = await db.fetchrow(query, merchant_reference)

        if not payment:
            # Fallback: check if this is a batch payment
            batch = await db.fetchrow(
                """
                SELECT id FROM batch_requests
                WHERE (gateway_transaction_id = $1 OR gateway_transaction_id = $2)
                AND status = 'PAYMENT_PENDING'
                """,
                gateway_transaction_id,
                merchant_reference,
            )
            if batch:
                from app.modules.batch_requests.services.batch_persist_service import (
                    BatchPersistService,
                )
                await BatchPersistService.fan_out_batch_completion(
                    db=db,
                    batch_id=batch["id"],
                    paid_at=datetime.now(timezone.utc),
                )
                logger.info(
                    f"Batch payment reconciled: batch={batch['id']}, "
                    f"gateway_txn={gateway_transaction_id}"
                )
                return True
            logger.debug(f"No pending service_payment found with reference {merchant_reference}")
            return False

        payment_id = str(payment["id"])
        service_request_id = payment["service_request_id"]
        user_id = payment["user_id"]

        # 2. Get user data for receipt and notifications
        user_query = """
            SELECT id, email, phone_number as phone, first_name, last_name, dni, preferred_language
            FROM users WHERE id = $1
        """
        user_data = await db.fetchrow(user_query, user_id)

        # 3. Get service request data for receipt (workflow_code, entity_code, solicitud_type)
        service_data = None
        if service_request_id:
            service_query = """
                SELECT sr.id, sr.reference, sr.workflow_code, sr.solicitud_type, sr.entity_code
                FROM service_requests sr
                WHERE sr.id = $1
            """
            service_data = await db.fetchrow(service_query, service_request_id)

        # 4. Update payment status
        paid_at = datetime.now(timezone.utc)
        update_query = """
            UPDATE service_payments
            SET status = 'completed',
                workflow_status = 'completed',
                paid_at = $2,
                gateway_transaction_id = $3,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        updated = await db.fetchrow(update_query, payment_id, paid_at, gateway_transaction_id)

        # 5. Generate and store receipt PDF
        receipt_number = None
        receipt_url = None
        try:
            payment_data = dict(updated)
            receipt_result = await receipt_service.generate_and_store_receipt(
                db=db,
                payment_id=payment_id,
                user_id=str(user_id),
                payment_data=payment_data,
                user_data=dict(user_data) if user_data else {},
                service_data=dict(service_data) if service_data else None,
                language="es",
            )
            receipt_number = receipt_result["receipt_number"]
            receipt_url = receipt_result["receipt_url"]
            logger.info(f"BANGE payment receipt generated: {receipt_number}")
        except Exception as e:
            logger.error(f"Failed to generate receipt for BANGE payment {payment_id}: {e}")
            # Generate fallback receipt number
            year = datetime.now(timezone.utc).year
            count_query = "SELECT COUNT(*) + 1 as n FROM service_payments WHERE receipt_number IS NOT NULL AND EXTRACT(YEAR FROM paid_at) = $1"
            result = await db.fetchrow(count_query, year)
            receipt_number = f"REC-{year}-{result['n']:06d}" if result else f"REC-{year}-000001"
            await db.execute("UPDATE service_payments SET receipt_number = $1 WHERE id = $2::uuid", receipt_number, payment_id)

        # 6. Update service_request payment status + INSERT assignment outbox
        # Both must succeed atomically (outbox = guaranteed entity agent assignment)
        if service_request_id:
            await db.execute(
                "UPDATE service_requests SET payment_status = 'completed', paid_at = NOW(), updated_at = NOW() WHERE id = $1",
                service_request_id
            )
            logger.info(f"Updated service_request {service_request_id} payment_status to completed")
            await confirm_appointment_for_payment(db, payment_id)

            # INSERT into assignment outbox (guaranteed entity agent assignment)
            try:
                from app.modules.service_requests.services.assignment_outbox_service import (
                    assignment_outbox_service,
                )
                sr_data = await db.fetchrow(
                    "SELECT workflow_code, entity_code, entity_location_id "
                    "FROM service_requests WHERE id = $1",
                    service_request_id,
                )
                if sr_data and sr_data["entity_code"]:
                    await assignment_outbox_service.enqueue(
                        db=db,
                        service_request_id=service_request_id,
                        workflow_code=sr_data["workflow_code"],
                        entity_code=sr_data["entity_code"],
                        entity_location_id=sr_data["entity_location_id"],
                        payment_id=payment_id,
                        payment_method=payment["payment_method"],
                    )
                    logger.info(
                        f"Outbox item created for BANGE webhook payment {payment_id} "
                        f"(entity={sr_data['entity_code']})"
                    )
                else:
                    logger.warning(
                        f"Cannot enqueue outbox for BANGE webhook: "
                        f"SR {service_request_id} missing entity_code"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to enqueue outbox for BANGE webhook payment {payment_id}: {e}",
                    exc_info=True,
                )

        # 6b. OMS hook: if this payment has fee_type, route linked obligations
        try:
            from app.modules.fiscal_services.services.license_service import (
                LicenseService,
            )
            await LicenseService.on_payment_completed(db, payment_id)
        except Exception as e:
            logger.error(
                f"OMS hook failed for BANGE webhook payment {payment_id}: {e}",
                exc_info=True,
            )

        # 7. Publish PAYMENT_COMPLETED event (fallback + notifications)
        try:
            paid_at = datetime.now(timezone.utc)
            await EventBus.publish(EventType.PAYMENT_COMPLETED, {
                "payment_id": payment_id,
                "user_id": str(user_id),
                "service_request_id": str(service_request_id) if service_request_id else None,
                "amount": float(payment["total_amount"]),
                "currency": payment["currency"],
                "payment_method": payment["payment_method"],
                "receipt_number": receipt_number,
                "receipt_url": receipt_url,
                "gateway_transaction_id": gateway_transaction_id,
                "user_email": user_data["email"] if user_data else None,
                "user_phone": user_data["phone"] if user_data else None,
                "preferred_language": user_data.get("preferred_language", "es") if user_data else "es",
                "date": paid_at.strftime("%d/%m/%Y"),
            })
            logger.info(f"PAYMENT_COMPLETED event published for BANGE payment {payment_id}")
        except Exception as e:
            logger.error(f"Failed to publish PAYMENT_COMPLETED event for BANGE payment: {e}")

        logger.info(f"Service payment {payment_id} reconciled with gateway transaction {gateway_transaction_id}")
        return True

    except Exception as e:
        logger.error(f"Error reconciling service_payment with reference {merchant_reference}: {e}")
        return False

@router.get("/transactions/unreconciled", response_model=BankTransactionListResponse)
async def list_unreconciled_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1, max_length=200, description="Search by reference, holder name, or account number"),
    status: Optional[str] = Query(None, description="Filter: unreconciled (default), reconciled, failed, all"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.view"))
):
    """List bank transactions with optional status filter. Defaults to unreconciled."""

    # Default to unreconciled for backward compatibility; 'all' = no filter
    effective_status = status if status else 'unreconciled'
    if effective_status == 'all':
        effective_status = None

    offset = (page - 1) * page_size
    transactions, total = await repository.list_transactions(
        db, page_size, offset, search=search, status=effective_status
    )

    return BankTransactionListResponse(
        transactions=[BankTransactionResponse(**t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/transactions/search-payments")
async def search_payments_for_reconciliation(
    q: str = Query(..., min_length=2, max_length=100, description="Search by reference, payer name, or amount"),
    currency: Optional[str] = Query(None, description="Filter by currency code"),
    limit: int = Query(10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.view")),
):
    """Search completed service_payments for manual reconciliation ComboBox"""
    search_pattern = f"%{q}%"

    query = """
        SELECT sp.id, sp.payment_reference, sp.total_amount, sp.currency,
               sp.payment_method::text,
               COALESCE(sp.validated_at, sp.created_at) as payment_date,
               u.full_name as payer_name, u.email as payer_email
        FROM service_payments sp
        JOIN users u ON u.id = sp.user_id
        WHERE sp.workflow_status = 'completed'
          AND sp.bank_transaction_id IS NULL
          AND (
              sp.payment_reference ILIKE $1
              OR u.full_name ILIKE $1
              OR CAST(sp.total_amount AS TEXT) LIKE $1
          )
    """
    params: list = [search_pattern]
    param_idx = 2

    if currency:
        query += f" AND sp.currency = ${param_idx}"
        params.append(currency)
        param_idx += 1

    query += f" ORDER BY sp.validated_at DESC NULLS LAST LIMIT ${param_idx}"
    params.append(limit)

    results = await db.fetch(query, *params)
    return {
        "payments": [
            {
                "id": str(r["id"]),
                "paymentReference": r["payment_reference"],
                "totalAmount": float(r["total_amount"]) if r["total_amount"] else 0,
                "currency": r["currency"],
                "paymentMethod": r["payment_method"],
                "paymentDate": str(r["payment_date"]) if r["payment_date"] else None,
                "payerName": r["payer_name"],
                "payerEmail": r["payer_email"],
            }
            for r in results
        ]
    }


@router.get("/transactions/{transaction_id}", response_model=BankTransactionResponse)
async def get_bank_transaction(
    transaction_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.view"))
):
    """Get bank transaction by ID - Requires webhook.view permission"""

    transaction = await repository.get_transaction_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    return BankTransactionResponse(**transaction)


@router.post("/transactions/reconcile", response_model=BankTransactionResponse)
async def manual_reconcile(
    reconcile: ReconcileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.update"))
):
    """
    Manual reconciliation - Requires webhook.update permission

    Liens bidirectionnels:
    - bank_transactions.service_payment_id → service_payments.id
    - service_payments.bank_transaction_id → bank_transactions.id
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    try:
        result = await repository.reconcile(
            db,
            reconcile.bank_transaction_id,
            reconcile.service_payment_id,
            user_id
        )
        logger.info(f"Admin {user_id} reconciled transaction {reconcile.bank_transaction_id}")

        # Confirm appointment hold if this payment is for a service_request
        await confirm_appointment_for_payment(db, reconcile.service_payment_id)

        return BankTransactionResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ========== BANK CONFIGURATIONS (ADMIN) ==========

@router.get("/bank-configurations", response_model=List[BankConfigurationResponse])
async def list_bank_configurations(
    active_only: bool = Query(True, description="Show only active banks"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.view")),
):
    """List bank configurations (requires webhook.view permission)"""
    configs = await repository.list_bank_configs(db, active_only)
    return [BankConfigurationResponse(**c) for c in configs]


@router.post("/bank-configurations", response_model=BankConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_configuration(
    config: BankConfigurationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.create"))
):
    """Create bank configuration - Requires webhook.create permission"""

    result = await repository.create_bank_config(db, config)
    admin_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    logger.info(f"Super admin {admin_id} created bank config {config.bank_code}")
    return BankConfigurationResponse(**result)


@router.put("/bank-configurations/{config_id}", response_model=BankConfigurationResponse)
async def update_bank_configuration(
    config_id: int,
    update_data: BankConfigurationUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
    _: None = Depends(permission_required("webhook.update"))
):
    """Update bank configuration - Requires webhook.update permission"""

    updated = await repository.update_bank_config(db, config_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank configuration not found")

    admin_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    logger.info(f"Super admin {admin_id} updated bank config {config_id}")
    return BankConfigurationResponse(**updated)
