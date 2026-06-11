"""
Batch Persist Service — Atomic persist of N service requests + payment.

Phase 4 of batch_requests: takes a validated batch session from Redis
and atomically creates N service_requests + N*M document records +
N service_payments in a single database transaction.

Key differences from individual WizardSessionService.initiate_payment():
- N items (loop) instead of 1
- Documents already on Firebase (early upload) — just create DB refs
- NO processor call — handles BANGE/Manual directly (avoids N+1 payment bug)
- Payments created per-SR with correct schema (base_amount, total_amount, workflow_status)
- Per-beneficiary tariff calculation (supports variable-rate workflows)
- Fan-out helper for batch payment completion (webhook/agent validation)
- No appointments (planned post-submission by agent)
- Partial submission: only READY items, EXCLUDED items skipped
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

import asyncpg
from loguru import logger

from app.modules.service_requests.repositories.service_request_repository import (
    service_request_repository,
)
from app.modules.service_requests.repositories.document_repository import (
    document_repository,
)
from app.modules.service_requests.models.enums import (
    ServiceRequestStatus,
    SolicitudType,
)
from app.modules.service_requests.services.workflow_engine import workflow_engine, resolve_workflow_code
from app.modules.service_requests.workflows.workflow_interface import WorkflowContext

from ..repositories.batch_repository import batch_repository
from .batch_session_service import (
    batch_session_service,
    BatchSessionError,
)


class BatchPersistError(Exception):
    """Raised when batch persist/payment fails."""
    def __init__(self, message: str, code: str = "BATCH_PERSIST_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class BatchPersistService:
    """
    Atomically persists a batch session into the database and initiates payment.

    Flow:
    1. prepare_payment() — calculate tariff per beneficiary, determine ready items
    2. submit_batch() — atomic DB transaction: create batch_request + N items
       + N service_requests + N*M documents + N service_payments + payment initiation

    Payment architecture (no processor):
    - N service_payments created directly (1 per service_request, proper schema)
    - BANGE: call BANGEService.create_payment() for total amount, link all N payments
    - Manual: all N created with workflow_status='pending_agent_review'
    - Fan-out: when payment completes, fan_out_batch_completion() updates all N
    """

    # =========================================================================
    # PREPARE PAYMENT
    # =========================================================================

    async def prepare_payment(
        self,
        session_id: str,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Calculate tariff per beneficiary and determine which items are ready.

        Per-beneficiary tariff supports variable-rate workflows (Contrato, TramitesVisado)
        where tariff depends on form_data. For fixed-rate workflows (Pasaporte, Residencia),
        all beneficiaries get the same amount — this is correct and consistent.

        Returns:
            {
                "per_item_tariffs": {ben_id: tariff_dict, ...},
                "ready_count": int,
                "excluded_count": int,
                "total_amount": float,
                "currency": str,
                "ready_beneficiaries": [...],
                "excluded_beneficiaries": [...]
            }
        """
        import time as _time
        _t_prep = _time.monotonic()

        session = await batch_session_service.get_session(session_id, user_id)

        workflow_code = resolve_workflow_code(session)
        solicitud_type = session.get("solicitud_type", "expedicion")
        beneficiaries = session.get("beneficiaries", [])
        item_documents = session.get("item_documents", {})
        form_data_grid = session.get("form_data_grid", {})

        if not beneficiaries:
            raise BatchSessionError(
                "No hay beneficiarios en la sesión.",
                "NO_BENEFICIARIES"
            )

        workflow = workflow_engine.get_workflow_by_string(workflow_code)
        if not workflow:
            raise BatchSessionError(
                f"Workflow '{workflow_code}' no encontrado.",
                "WORKFLOW_NOT_FOUND"
            )

        # Determine ready vs excluded items
        ready = []
        excluded = []

        for ben in beneficiaries:
            ben_id = ben["id"]
            has_docs = ben_id in item_documents and len(item_documents[ben_id]) > 0
            has_form = ben_id in form_data_grid and form_data_grid[ben_id]
            status = ben.get("status", "PENDING")

            if status == "EXCLUDED":
                excluded.append({
                    "id": ben_id,
                    "name": ben.get("name"),
                    "reason": "Excluido por el usuario",
                })
            elif not has_docs:
                excluded.append({
                    "id": ben_id,
                    "name": ben.get("name"),
                    "reason": "Sin documentos asignados",
                })
            elif not has_form:
                excluded.append({
                    "id": ben_id,
                    "name": ben.get("name"),
                    "reason": "Sin datos de formulario",
                })
            else:
                ready.append({
                    "id": ben_id,
                    "name": ben.get("name"),
                    "identifier": ben.get("identifier"),
                })

        if not ready:
            raise BatchSessionError(
                "Ningún beneficiario está listo para envío. "
                "Verifique que todos tengan documentos y datos completos.",
                "NO_READY_ITEMS"
            )

        # Calculate tariff per beneficiary (supports variable-rate workflows)
        # Per-beneficiary try/except: one failure doesn't crash the whole batch
        per_item_tariffs: Dict[str, Dict[str, Any]] = {}
        currency = "XAF"
        tariff_failures: List[Dict[str, Any]] = []

        for ben_info in ready[:]:  # iterate copy — we may remove items
            ben_id = ben_info["id"]
            ben_form_data = form_data_grid.get(ben_id, {})

            try:
                tariff_context = WorkflowContext(
                    service_request_id=UUID("00000000-0000-0000-0000-000000000000"),
                    user_id=user_id,
                    workflow_code=workflow.workflow_code,
                    solicitud_type=SolicitudType(solicitud_type),
                    form_data=ben_form_data,
                )

                ben_tariff = workflow.get_tariff_breakdown(
                    solicitud_type=SolicitudType(solicitud_type),
                    context=tariff_context,
                )
                per_item_tariffs[ben_id] = ben_tariff
                currency = ben_tariff.get("currency", "XAF")
            except Exception as e:
                logger.warning(
                    f"[BatchPersist] Tariff calculation failed for "
                    f"beneficiary {ben_id} ({ben_info.get('name')}): {e}"
                )
                tariff_failures.append({
                    "id": ben_id,
                    "name": ben_info.get("name"),
                    "reason": f"Error al calcular tarifa: {str(e)[:100]}",
                })

        # Move tariff failures from ready to excluded
        if tariff_failures:
            failure_ids = {f["id"] for f in tariff_failures}
            ready = [b for b in ready if b["id"] not in failure_ids]
            excluded.extend(tariff_failures)

        if not ready:
            raise BatchSessionError(
                "Ningún beneficiario tiene tarifa calculada correctamente.",
                "ALL_TARIFFS_FAILED"
            )

        total_amount = sum(t.get("total_amount", 0) for t in per_item_tariffs.values())

        # Save tariff + readiness in session
        await batch_session_service.update_session_fields(
            session_id, user_id, {
                "per_item_tariffs": per_item_tariffs,
                "ready_beneficiaries": [b["id"] for b in ready],
                "excluded_beneficiaries": [b["id"] for b in excluded],
                "total_amount": total_amount,
                "currency": currency,
                "status": "PAYMENT_PENDING",
            }
        )

        result = {
            "per_item_tariffs": per_item_tariffs,
            "ready_count": len(ready),
            "excluded_count": len(excluded),
            "total_amount": total_amount,
            "currency": currency,
            "ready_beneficiaries": ready,
            "excluded_beneficiaries": excluded,
            "workflow_code": workflow_code,
            "service_name": workflow.service_name_es,
        }

        _prep_elapsed = _time.monotonic() - _t_prep
        logger.info(
            f"[BatchPersist] prepare_payment: session={session_id}, "
            f"ready={len(ready)}, excluded={len(excluded)}, "
            f"total={total_amount} {currency}, elapsed={_prep_elapsed:.2f}s"
        )
        return result

    # =========================================================================
    # SUBMIT BATCH (ATOMIC)
    # =========================================================================

    async def submit_batch(
        self,
        session_id: str,
        user_id: UUID,
        db: asyncpg.Connection,
        payment_method: str,
        phone_number: Optional[str] = None,
        user_email: Optional[str] = None,
        user_phone: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atomically persist the batch: create batch_request + N service_requests +
        N*M documents + N service_payments + payment initiation.

        If anything fails, the entire DB transaction is rolled back.

        Payment handling (NO processor — avoids N+1 payment bug):
        - N service_payments created directly with correct schema
        - BANGE: BANGEService.create_payment() called once for total, all N linked
        - Manual: all N created with pending_agent_review status
        - Webhook/validation fan-out: call fan_out_batch_completion() separately
        """
        # B-020: Track processing time metrics
        import time as _time
        _t_start = _time.monotonic()

        logger.info(
            f"[BatchPersist] submit_batch: session={session_id}, method={payment_method}"
        )

        # 1. Read and validate session
        session = await batch_session_service.get_session(session_id, user_id)

        if session.get("status") != "PAYMENT_PENDING":
            raise BatchPersistError(
                "Ejecute prepare-payment primero.",
                "NOT_READY"
            )

        per_item_tariffs = session.get("per_item_tariffs")
        if not per_item_tariffs:
            raise BatchPersistError(
                "Tarifas no calculadas. Ejecute prepare-payment.",
                "NO_TARIFF"
            )

        ready_ids = set(session.get("ready_beneficiaries", []))
        if not ready_ids:
            raise BatchPersistError(
                "No hay beneficiarios listos para envío.",
                "NO_READY_ITEMS"
            )

        # Validate payment method
        from app.modules.payments.models.payment import PaymentMethod as PM
        try:
            payment_method_enum = PM(payment_method)
        except ValueError:
            raise BatchPersistError(
                f"Método de pago no válido: {payment_method}",
                "INVALID_PAYMENT_METHOD"
            )

        is_manual = payment_method_enum in (PM.CASH, PM.CHECK)

        if payment_method_enum == PM.MOBILE_MONEY and not phone_number:
            raise BatchPersistError(
                "Número de teléfono requerido para Mobile Money.",
                "PHONE_REQUIRED"
            )

        total_amount = session.get("total_amount", 0)
        currency = session.get("currency", "XAF")

        # Anti double-submit: atomic Redis lock (SET NX EX)
        lock_key = f"batch_submit_lock:{session_id}"
        try:
            redis_client = await batch_session_service.cache._backend._get_client()
            lock_acquired = await redis_client.set(
                lock_key, "1", nx=True, ex=120  # 2-minute lock
            )
            if not lock_acquired:
                raise BatchPersistError(
                    "Este lote ya se está enviando. Por favor espere.",
                    "ALREADY_SUBMITTING"
                )
        except BatchPersistError:
            raise
        except Exception as e:
            logger.warning(f"[BatchPersist] Redis lock failed, proceeding with soft lock: {e}")
            # Fallback: soft lock via session status
            pass

        await batch_session_service.update_session_fields(
            session_id, user_id, {"status": "SUBMITTING"}
        )

        workflow_code = resolve_workflow_code(session)
        solicitud_type = session.get("solicitud_type", "expedicion")
        company_id_str = session.get("company_id")
        company_id = UUID(company_id_str) if company_id_str else None
        beneficiaries = session.get("beneficiaries", [])
        item_documents = session.get("item_documents", {})
        form_data_grid = session.get("form_data_grid", {})
        shared_documents = session.get("shared_documents", [])

        # Derive entity_code from entities.workflow_codes (BD source of truth).
        # Batch requests use the main office of the first entity that handles
        # this workflow. TODO: add site selection to batch wizard for multi-entity.
        from app.modules.service_requests.services.workflow_engine import resolve_workflow_sites
        sites = await resolve_workflow_sites(db, workflow_code)
        # Prefer main office, else first site
        main_site = next((s for s in sites if s.get("is_main_office")), sites[0])
        entity_code = main_site["entity_code"]
        entity_location_id = main_site["id"]

        try:
            async with db.transaction():
                # ---------------------------------------------------------------
                # Step A: Create batch_request record in DB
                # ---------------------------------------------------------------
                batch_record = await batch_repository.create_batch(
                    db=db,
                    submitted_by=user_id,
                    workflow_code=workflow_code,
                    solicitud_type=solicitud_type,
                    company_id=company_id,
                    notes=session.get("notes"),
                )
                batch_id = batch_record["id"]
                batch_reference = batch_record["reference"]

                logger.info(
                    f"[BatchPersist] Step A: batch created {batch_reference} ({batch_id})"
                )

                # ---------------------------------------------------------------
                # Step B: Loop over ready beneficiaries
                # ---------------------------------------------------------------
                created_requests = []
                payment_ids = []

                for item_idx, ben in enumerate(
                    (b for b in beneficiaries if b["id"] in ready_ids)
                ):
                    ben_id = ben["id"]
                    ben_form_data = form_data_grid.get(ben_id, {})
                    ben_tariff = per_item_tariffs.get(ben_id, {})
                    ben_total = ben_tariff.get("total_amount", 0)
                    ben_base = ben_tariff.get("base_amount", 0)
                    ben_supplements = ben_tariff.get("supplements_total", 0)
                    ben_penalties = ben_tariff.get("penalties_amount", 0)

                    # B1: Create service_request
                    request_data = await service_request_repository.create(
                        db=db,
                        user_id=user_id,
                        workflow_code=workflow_code,
                        solicitud_type=solicitud_type,
                        form_data=ben_form_data,
                        batch_id=batch_id,
                        company_id=company_id,
                        entity_code=entity_code,
                        entity_location_id=entity_location_id,
                    )
                    sr_id = request_data["id"]
                    sr_reference = request_data["reference"]

                    # B2: Update status to PAYMENT_PENDING
                    await service_request_repository.update_status(
                        db=db,
                        request_id=sr_id,
                        new_status=ServiceRequestStatus.PAYMENT_PENDING.value,
                        performed_by=user_id,
                        comment=f"Batch submission: {batch_reference}",
                    )

                    # B3: Store tariff amounts on service_request
                    await service_request_repository.update_amounts(
                        db=db,
                        request_id=sr_id,
                        base_amount=float(ben_base),
                        supplements_amount=float(ben_supplements),
                        penalties_amount=float(ben_penalties),
                        total_amount=float(ben_total),
                    )

                    # B4: Create document records for individual docs (already on Firebase)
                    ben_docs = item_documents.get(ben_id, [])
                    for doc in ben_docs:
                        doc_record = await document_repository.add_document(
                            db=db,
                            service_request_id=sr_id,
                            document_code=doc["document_code"],
                            document_name=doc.get("document_code", "document"),
                            file_path=doc["file_path"],
                            file_name=doc.get("file_name", "document"),
                            file_size=0,
                            mime_type=doc.get("mime_type", "application/pdf"),
                            uploaded_by=user_id,
                            source="batch_upload",
                        )

                        extraction_data = doc.get("extraction_data", {})
                        if extraction_data:
                            await document_repository.update_extraction(
                                db=db,
                                document_id=doc_record["id"],
                                extraction_data=extraction_data,
                                extraction_confidence=doc.get("confidence", 0) or 0,
                                extraction_status="completed",
                            )

                    # B5: Create document records for shared docs (each SR gets a ref)
                    for sdoc in shared_documents:
                        await document_repository.add_document(
                            db=db,
                            service_request_id=sr_id,
                            document_code=sdoc["document_code"],
                            document_name=sdoc.get("document_code", "shared_document"),
                            file_path=sdoc["file_path"],
                            file_name=sdoc.get("file_name", "document"),
                            file_size=sdoc.get("file_size", 0),
                            mime_type=sdoc.get("mime_type", "application/pdf"),
                            uploaded_by=user_id,
                            source="batch_shared",
                        )

                    # B6: Create service_payment with CORRECT schema
                    # (no processor — avoids N+1 bug, uses proper columns)
                    payment_id = str(uuid4())
                    payment_ref = self._generate_payment_reference(
                        batch_reference, item_idx, is_manual
                    )

                    await db.execute(
                        """
                        INSERT INTO service_payments (
                            id, payment_reference, user_id, service_request_id,
                            payment_type, payment_method, base_amount, total_amount,
                            currency, calculation_details,
                            status, workflow_status, requires_agent_validation,
                            batch_id, created_at, updated_at
                        ) VALUES (
                            $1::uuid, $2, $3::uuid, $4::uuid,
                            'full', $5, $6, $7,
                            $8, $9::jsonb,
                            $10, $11, $12,
                            $13, NOW(), NOW()
                        )
                        """,
                        payment_id,
                        payment_ref,
                        user_id,
                        sr_id,
                        payment_method,
                        Decimal(str(ben_base)),
                        Decimal(str(ben_total)),
                        currency,
                        json.dumps(ben_tariff),
                        "processing" if not is_manual else "pending",
                        "submitted" if not is_manual else "pending_agent_review",
                        is_manual,
                        batch_id,
                    )
                    payment_ids.append(payment_id)

                    # B7: Create batch_request_item directly (no sub-transaction overhead)
                    await db.fetchrow(
                        """
                        INSERT INTO batch_request_items (
                            batch_id, beneficiary_name, beneficiary_identifier,
                            beneficiary_identifier_type, beneficiary_email,
                            beneficiary_phone, conditions, item_order,
                            service_request_id, status, form_data,
                            assigned_documents, item_amount
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8,
                                $9, 'SUBMITTED', $10::jsonb, $11::jsonb, $12)
                        RETURNING id
                        """,
                        batch_id,
                        ben.get("name", ""),
                        ben.get("identifier"),
                        ben.get("identifier_type"),
                        ben.get("email"),
                        ben.get("phone"),
                        json.dumps(ben.get("conditions") or {}),
                        item_idx,
                        sr_id,
                        json.dumps(ben_form_data),
                        json.dumps(ben_docs),
                        Decimal(str(ben_total)),
                    )

                    created_requests.append({
                        "service_request_id": str(sr_id),
                        "reference": sr_reference,
                        "beneficiary_name": ben.get("name"),
                        "beneficiary_id": ben_id,
                        "amount": ben_total,
                    })

                logger.info(
                    f"[BatchPersist] Step B: {len(created_requests)} service_requests + "
                    f"service_payments created"
                )

                # ---------------------------------------------------------------
                # Step C: Update batch totals (1 update for all items)
                # ---------------------------------------------------------------
                await batch_repository.update_batch(
                    db=db,
                    batch_id=batch_id,
                    per_item_amount=Decimal(str(
                        total_amount / len(created_requests)
                        if created_requests else 0
                    )),
                    total_amount=Decimal(str(total_amount)),
                    total_items=len(created_requests),
                    items_ready=len(created_requests),
                    items_submitted=len(created_requests),
                    submitted_at=datetime.now(timezone.utc),
                )

                # ---------------------------------------------------------------
                # Step D: Payment initiation (NO processor — direct handling)
                # ---------------------------------------------------------------
                if total_amount <= 0:
                    # Free workflow — skip payment, mark as SUBMITTED directly
                    payment_result = self._build_free_result(batch_reference)
                    new_batch_status = "SUBMITTED"
                    # Update all SRs to SUBMITTED (not PAYMENT_PENDING)
                    await db.execute(
                        """
                        UPDATE service_requests
                        SET status = 'SUBMITTED', payment_status = 'not_required',
                            updated_at = NOW()
                        WHERE batch_id = $1
                        """,
                        batch_id,
                    )
                elif is_manual:
                    # Cash/Check: payments already created with pending_agent_review
                    payment_result = self._build_manual_result(
                        batch_reference, total_amount, currency,
                        payment_method_enum, len(created_requests),
                    )
                    new_batch_status = "PAYMENT_PENDING"
                    # NOTE: manual event published AFTER commit (see post-commit below)
                else:
                    # BANGE: call API for total amount, link all payments
                    payment_result = await self._initiate_bange_batch(
                        db=db,
                        batch_id=batch_id,
                        batch_reference=batch_reference,
                        total_amount=Decimal(str(total_amount)),
                        currency=currency,
                        user_email=user_email,
                        user_phone=phone_number or user_phone,
                        workflow_code=workflow_code,
                        workflow=workflow,
                        items_count=len(created_requests),
                    )
                    if not payment_result.get("success"):
                        raise BatchPersistError(
                            payment_result.get("error", "Error al iniciar el pago."),
                            "PAYMENT_FAILED",
                            {"payment_error": payment_result.get("error")}
                        )
                    new_batch_status = "PAYMENT_PENDING"

                # ---------------------------------------------------------------
                # Step E: Update batch status
                # ---------------------------------------------------------------
                await batch_repository.update_batch_status(
                    db=db,
                    batch_id=batch_id,
                    status=new_batch_status,
                )

            # ---------------------------------------------------------------
            # Post-commit: clean up session + events (non-critical)
            # ---------------------------------------------------------------
            try:
                await batch_session_service.delete_session(session_id, user_id)
            except Exception:
                pass  # TTL handles cleanup

            # Publish manual event AFTER commit (B-010 fix: was inside transaction)
            if is_manual and total_amount > 0:
                self._publish_manual_event(
                    batch_id, batch_reference, user_id,
                    total_amount, currency, payment_method_enum,
                    user_email, phone_number or user_phone,
                    len(created_requests),
                )

            _elapsed = _time.monotonic() - _t_start
            logger.info(
                f"[BatchPersist] submit_batch complete: batch={batch_reference}, "
                f"requests={len(created_requests)}, total={total_amount} {currency}, "
                f"elapsed={_elapsed:.2f}s"
            )

            # Publish BATCH_SUBMITTED event (consolidated — 1 not N)
            self._publish_batch_submitted_event(
                batch_id=batch_id,
                batch_reference=batch_reference,
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                workflow_code=workflow_code,
                total_items=len(created_requests),
                total_amount=total_amount,
                currency=currency,
                payment_method=payment_method,
                beneficiary_names=[
                    b.get("name", "")
                    for b in beneficiaries
                    if b.get("id") in ready_ids
                ][:10],
            )

            return {
                "batch_id": str(batch_id),
                "batch_reference": batch_reference,
                "service_requests_created": len(created_requests),
                "service_requests": created_requests,
                "payment_id": payment_result.get("payment_id"),
                "payment_reference": payment_result.get("external_reference"),
                "redirect_url": payment_result.get("redirect_url"),
                "requires_action": payment_result.get("requires_action", False),
                "action_type": payment_result.get("action_type"),
                "message_es": payment_result.get("message_es"),
                "total_amount": total_amount,
                "currency": currency,
                "items_count": len(created_requests),
            }

        except BatchPersistError:
            await batch_session_service.update_session_fields(
                session_id, user_id, {"status": "PAYMENT_PENDING"}
            )
            await self._release_submit_lock(session_id)
            raise

        except Exception as e:
            logger.error(f"[BatchPersist] submit_batch failed: {e}", exc_info=True)
            await batch_session_service.update_session_fields(
                session_id, user_id, {"status": "PAYMENT_PENDING"}
            )
            await self._release_submit_lock(session_id)
            raise BatchPersistError(
                f"Error al procesar el lote: {str(e)}",
                "BATCH_PERSIST_FAILED",
                {"original_error": str(e)}
            )

    # =========================================================================
    # LOCK HELPERS
    # =========================================================================

    async def _release_submit_lock(self, session_id: str) -> None:
        """Release the Redis atomic submit lock (best-effort)."""
        try:
            redis_client = await batch_session_service.cache._backend._get_client()
            await redis_client.delete(f"batch_submit_lock:{session_id}")
        except Exception as e:
            logger.warning(f"[BatchPersist] Failed to release submit lock: {e}")

    # =========================================================================
    # PAYMENT HELPERS (replace processor calls)
    # =========================================================================

    async def _initiate_bange_batch(
        self,
        db: asyncpg.Connection,
        batch_id: UUID,
        batch_reference: str,
        total_amount: Decimal,
        currency: str,
        user_email: Optional[str],
        user_phone: Optional[str],
        workflow_code: str,
        workflow: Any,
        items_count: int,
    ) -> Dict[str, Any]:
        """
        Call BANGE API once for total batch amount, then link all N payments.

        Unlike the processor pattern (which creates its own service_payment),
        we've already created N correct payments in B6. This just triggers
        the BANGE payment and links them via gateway_transaction_id.
        """
        from app.modules.payments.services.bange_service import BANGEService
        from app.modules.payments.models.payment import BANGEPaymentRequest
        from app.config import get_settings

        settings = get_settings()
        bange_service = BANGEService()

        # Generate batch payment reference
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        short_id = str(uuid4())[:8].upper()
        bange_ref = f"BATCH-{timestamp}-{short_id}"

        callback_url = f"{settings.API_BASE_URL}/api/v1/webhooks/bange"
        return_url = (
            f"{settings.FRONTEND_URL}/dashboard/batch-requests/{batch_id}"
        )

        service_name = workflow.service_name_es if workflow else workflow_code
        bange_request = BANGEPaymentRequest(
            amount=total_amount,
            currency=currency,
            description=(
                f"Lote {batch_reference} - {items_count} solicitudes - {service_name}"
            ),
            reference=bange_ref,
            customer_email=user_email,
            customer_phone=user_phone,
            callback_url=callback_url,
            return_url=return_url,
            metadata={
                "batch_id": str(batch_id),
                "batch_reference": batch_reference,
                "items_count": items_count,
                "workflow_code": workflow_code,
            },
        )

        # B-019: Retry with exponential backoff on BANGE failure
        import asyncio as _asyncio
        bange_response = None
        last_error = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bange_response = await bange_service.create_payment(bange_request)
                if bange_response:
                    break
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[BatchPersist] BANGE attempt {attempt + 1}/{max_retries} failed: {e}"
                )
            if attempt < max_retries - 1:
                await _asyncio.sleep(2 ** attempt)  # 1s, 2s backoff

        if not bange_response:
            logger.error(
                f"[BatchPersist] BANGE API failed after {max_retries} attempts: {last_error}"
            )
            return {
                "success": False,
                "error": "Error al conectar con el sistema de pago. Intente nuevamente.",
            }

        # Store gateway_transaction_id on batch_requests (NOT on individual
        # service_payments — gateway_transaction_id has UNIQUE constraint on
        # service_payments, can't share across N rows).
        # Webhook handler should look up batch_requests.gateway_transaction_id
        # for batch payments, then call fan_out_batch_completion().
        await batch_repository.update_batch(
            db=db,
            batch_id=batch_id,
            gateway_transaction_id=bange_response.payment_id,
        )

        # Set expires_at on individual payments (no UNIQUE constraint issue)
        if bange_response.expires_at:
            await db.execute(
                """
                UPDATE service_payments
                SET expires_at = $1, updated_at = NOW()
                WHERE batch_id = $2
                """,
                bange_response.expires_at,
                batch_id,
            )

        logger.info(
            f"[BatchPersist] BANGE payment initiated: "
            f"batch={batch_reference}, bange_id={bange_response.payment_id}, "
            f"redirect={bange_response.payment_url}"
        )

        return {
            "success": True,
            "payment_id": bange_response.payment_id,
            "external_reference": bange_response.payment_id,
            "redirect_url": bange_response.payment_url,
            "requires_action": True,
            "action_type": "redirect",
            "message_es": "Redirigiendo al sistema de pago...",
        }

    @staticmethod
    def _build_manual_result(
        batch_reference: str,
        total_amount: float,
        currency: str,
        payment_method: Any,
        items_count: int,
    ) -> Dict[str, Any]:
        """Build result dict for manual (cash/check) payment."""
        from app.modules.payments.models.payment import PaymentMethod as PM

        if payment_method == PM.CASH:
            message = (
                f"Pago en efectivo registrado para lote {batch_reference} "
                f"({items_count} solicitudes). "
                f"Presente este comprobante en la oficina del Tesoro "
                f"junto con el monto de {total_amount:,.0f} {currency}."
            )
            action_type = "agent_validation_cash"
        else:
            message = (
                f"Pago con cheque registrado para lote {batch_reference} "
                f"({items_count} solicitudes). "
                f"Presente el cheque por {total_amount:,.0f} {currency} "
                f"en la oficina del Tesoro."
            )
            action_type = "agent_validation_check"

        return {
            "success": True,
            "payment_id": None,
            "external_reference": batch_reference,
            "redirect_url": None,
            "requires_action": True,
            "action_type": action_type,
            "message_es": message,
        }

    @staticmethod
    def _build_free_result(batch_reference: str) -> Dict[str, Any]:
        """Build result dict for free (0-amount) batch."""
        return {
            "success": True,
            "payment_id": None,
            "external_reference": batch_reference,
            "redirect_url": None,
            "requires_action": False,
            "action_type": "none",
            "message_es": f"Lote {batch_reference} enviado correctamente. No se requiere pago.",
        }

    @staticmethod
    def _publish_manual_event(
        batch_id: UUID,
        batch_reference: str,
        user_id: UUID,
        total_amount: float,
        currency: str,
        payment_method: Any,
        user_email: Optional[str],
        user_phone: Optional[str],
        items_count: int,
    ) -> None:
        """Publish a single PAYMENT_MANUAL_PENDING event for the batch."""
        from app.core.events import EventBus, EventType

        try:
            EventBus.publish_nowait(EventType.PAYMENT_MANUAL_PENDING, {
                "batch_id": str(batch_id),
                "batch_reference": batch_reference,
                "user_id": str(user_id),
                "amount": float(total_amount),
                "currency": currency,
                "payment_method": payment_method.value,
                "user_email": user_email,
                "user_phone": user_phone,
                "preferred_language": "es",
                "items_count": items_count,
                "is_batch": True,
            })
            logger.info(
                f"[BatchPersist] PAYMENT_MANUAL_PENDING event for batch {batch_reference}"
            )
        except Exception as e:
            logger.error(f"[BatchPersist] Failed to publish manual event: {e}")

    @staticmethod
    def _publish_batch_submitted_event(
        batch_id: UUID,
        batch_reference: str,
        user_id: UUID,
        user_email: Optional[str],
        user_name: Optional[str],
        workflow_code: str,
        total_items: int,
        total_amount: float,
        currency: str,
        payment_method: str,
        beneficiary_names: List[str],
    ) -> None:
        """Publish a single BATCH_SUBMITTED event (1 email, not N)."""
        from app.core.events import EventBus, EventType

        try:
            EventBus.publish_nowait(EventType.BATCH_SUBMITTED, {
                "batch_id": str(batch_id),
                "batch_reference": batch_reference,
                "user_id": str(user_id),
                "user_email": user_email,
                "user_name": user_name or "",
                "workflow_code": workflow_code,
                "total_items": total_items,
                "amount": float(total_amount),
                "currency": currency,
                "payment_method": payment_method,
                "beneficiary_names": beneficiary_names,
                "preferred_language": "es",
            })
            logger.info(
                f"[BatchPersist] BATCH_SUBMITTED event for {batch_reference} "
                f"({total_items} items, {total_amount} {currency})"
            )
        except Exception as e:
            logger.error(f"[BatchPersist] Failed to publish BATCH_SUBMITTED: {e}")

    @staticmethod
    def _generate_payment_reference(
        batch_reference: str,
        item_index: int,
        is_manual: bool,
    ) -> str:
        """Generate unique payment reference for a batch item."""
        prefix = "CSH" if is_manual else "SR"
        short_id = str(uuid4())[:6].upper()
        return f"{prefix}-{batch_reference}-{item_index:03d}-{short_id}"

    # =========================================================================
    # FAN-OUT: Batch payment completion
    # =========================================================================

    @staticmethod
    async def fan_out_batch_completion(
        db: asyncpg.Connection,
        batch_id: UUID,
        paid_at: datetime,
        agent_profile_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Update ALL service_payments and service_requests in a batch to PAID.

        Called from:
        - BANGE webhook handler (when webhook detects batch_id in metadata
          or finds batch_requests.gateway_transaction_id match)
        - Manual validate_payment (when agent validates a batch payment)

        This is the batch equivalent of _mark_payment_completed() in processors.

        Args:
            db: Database connection (should be inside a transaction)
            batch_id: Batch request UUID
            paid_at: Payment timestamp
            agent_profile_id: Agent who validated (Manual payments only)

        Returns:
            {"payments_updated": int, "requests_updated": int}
        """
        import time as _time
        _t_fanout = _time.monotonic()

        # Resolve user_id from agent_profile_id (validated_by_agent_id stores user_id)
        agent_user_id = agent_profile_id
        if agent_profile_id:
            resolved = await db.fetchval(
                "SELECT user_id FROM agent_profiles WHERE id = $1::uuid",
                agent_profile_id
            )
            if resolved:
                agent_user_id = str(resolved)

        # Update all service_payments in the batch
        if agent_user_id:
            payments_result = await db.execute(
                """
                UPDATE service_payments
                SET status = 'completed',
                    workflow_status = 'completed',
                    paid_at = $2,
                    validated_by_agent_id = $3::uuid,
                    validated_at = $2,
                    updated_at = NOW()
                WHERE batch_id = $1 AND status != 'completed'
                """,
                batch_id,
                paid_at,
                agent_user_id,
            )
        else:
            payments_result = await db.execute(
                """
                UPDATE service_payments
                SET status = 'completed',
                    workflow_status = 'completed',
                    paid_at = $2,
                    updated_at = NOW()
                WHERE batch_id = $1 AND status != 'completed'
                """,
                batch_id,
                paid_at,
            )
        payments_updated = int(payments_result.split()[-1]) if payments_result else 0

        # Update all service_requests in the batch to SUBMITTED
        # (not PAID — agents' pending queue filters on SUBMITTED/UNDER_REVIEW)
        requests_result = await db.execute(
            """
            UPDATE service_requests
            SET status = 'SUBMITTED',
                payment_status = 'completed',
                paid_at = $2,
                updated_at = NOW()
            WHERE batch_id = $1 AND status = 'PAYMENT_PENDING'
            """,
            batch_id,
            paid_at,
        )
        requests_updated = int(requests_result.split()[-1]) if requests_result else 0

        # Add batch service_requests to assignment outbox for guaranteed processing
        # (outbox cron handles: add_to_queue + auto_assign + status transition)
        batch_srs = await db.fetch(
            """
            SELECT sr.id, sr.workflow_code, sr.entity_code, sr.entity_location_id
            FROM service_requests sr
            WHERE sr.batch_id = $1 AND sr.status = 'SUBMITTED'
            """,
            batch_id,
        )

        from app.modules.service_requests.services.assignment_outbox_service import (
            assignment_outbox_service,
        )

        queue_inserted = 0
        enqueue_failures = 0
        for sr in batch_srs:
            entity_code = sr["entity_code"]
            if not entity_code:
                logger.warning(
                    f"Batch fan-out: SR {sr['id']} missing entity_code, "
                    f"skipping (health check will catch)"
                )
                enqueue_failures += 1
                continue
            try:
                outbox_id = await assignment_outbox_service.enqueue(
                    db=db,
                    service_request_id=sr["id"],
                    workflow_code=sr["workflow_code"],
                    entity_code=entity_code,
                    entity_location_id=sr.get("entity_location_id"),
                    batch_id=batch_id,
                )
                if outbox_id:
                    queue_inserted += 1
            except Exception as e:
                enqueue_failures += 1
                logger.error(
                    f"Batch fan-out: failed to enqueue SR {sr['id']} "
                    f"(entity={entity_code}): {e}"
                )

        if enqueue_failures > 0:
            logger.error(
                f"Batch fan-out: {enqueue_failures}/{len(batch_srs)} SRs failed to enqueue "
                f"for batch {batch_id}. Health check cron will catch orphans."
            )

        # Update batch status
        await db.execute(
            """
            UPDATE batch_requests
            SET status = 'PAID', updated_at = NOW()
            WHERE id = $1 AND status != 'PAID'
            """,
            batch_id,
        )

        _fanout_elapsed = _time.monotonic() - _t_fanout
        logger.info(
            f"[BatchPersist] fan_out_batch_completion: batch={batch_id}, "
            f"payments={payments_updated}, requests={requests_updated}, "
            f"queue_items={queue_inserted}, elapsed={_fanout_elapsed:.2f}s"
        )
        return {
            "payments_updated": payments_updated,
            "requests_updated": requests_updated,
        }


# Singleton
batch_persist_service = BatchPersistService()
