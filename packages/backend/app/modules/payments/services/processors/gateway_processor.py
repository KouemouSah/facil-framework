"""
Gateway Payment Processor — Generic processor for any bank gateway.

Handles orchestration logic (DB records, events, outbox) generically.
Delegates API communication to a GatewayServiceBase implementation.

Architecture:
    GatewayProcessor(BANGEGateway)    → BANGE payments
    GatewayProcessor(EcobankGateway)  → Ecobank payments
    GatewayProcessor(FutureGateway)   → Future bank payments

The GatewayProcessor is NOT bank-specific. It only knows about:
- Creating service_payment records (DB)
- Building GatewayPaymentRequest (generic)
- Calling gateway.create_payment() (polymorphic)
- Publishing events (EventBus)
- Creating outbox items (assignment)
"""

from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import json
import asyncpg
from loguru import logger

from app.modules.payments.models.payment import (
    PaymentMethod,
    PaymentStatus,
)
from app.config import get_settings

from app.core.events import EventBus, EventType

from app.modules.payments.services.gateways.base import (
    GatewayServiceBase,
    GatewayPaymentRequest,
)

from .base import (
    PaymentProcessorBase,
    ProcessorType,
    PaymentContext,
    PaymentInitResult,
    PaymentStatusResult,
)


class GatewayProcessor(PaymentProcessorBase):
    """
    Generic payment processor for any bank gateway API.

    Accepts a GatewayServiceBase instance and uses it for all
    API communication. The orchestration logic (DB, events, outbox)
    is identical regardless of which bank.

    Usage:
        bange_gateway = BANGEGateway()
        processor = GatewayProcessor(bange_gateway)
        result = await processor.initiate(db, context)
    """

    processor_type = ProcessorType.GATEWAY_API

    def __init__(self, gateway: GatewayServiceBase):
        self.gateway = gateway
        self.settings = get_settings()

    def get_supported_methods(self) -> list[PaymentMethod]:
        """Return payment methods supported by the underlying gateway."""
        return [PaymentMethod(m) for m in self.gateway.get_supported_methods()]

    async def initiate(
        self,
        db: asyncpg.Connection,
        context: PaymentContext
    ) -> PaymentInitResult:
        """
        Initiate a payment via the bank gateway API.

        1. Generate unique payment reference
        2. Create service_payment record in DB
        3. Build gateway-agnostic payment request
        4. Call gateway.create_payment() (polymorphic)
        5. Update record with external transaction ID
        6. Return redirect URL or confirmation

        Args:
            db: Database connection
            context: Payment context

        Returns:
            PaymentInitResult with redirect URL for bank payment page
        """
        try:
            # 1. Generate payment reference
            payment_reference = self._generate_reference(context)
            payment_id = str(uuid4())

            # 2. Create service_payment record
            await self._create_service_payment(
                db=db,
                payment_id=payment_id,
                context=context,
                payment_reference=payment_reference,
            )

            # 3. Build callback URL using gateway's webhook routing code
            # (may differ from bank_code: e.g., MPGS uses "ECOBANK_MPGS" for
            # routing but "ECOBANK" for bank_transactions)
            routing_code = self.gateway.get_webhook_routing_code().lower()
            callback_url = f"{self.settings.API_BASE_URL}/api/v1/webhooks/{routing_code}"
            return_url = (
                f"{self.settings.FRONTEND_URL}/dashboard/service-requests/"
                f"{context.service_request_id}/payment/result"
            )

            # 4. Build gateway-agnostic payment request
            gw_request = GatewayPaymentRequest(
                amount=context.amount,
                currency=context.currency,
                reference=payment_reference,
                description=(
                    f"Pago {context.service_name or context.workflow_code} "
                    f"- {context.reference_number}"
                ),
                callback_url=callback_url,
                return_url=return_url,
                customer_email=context.user_email,
                customer_phone=context.user_phone,
                metadata={
                    "service_request_id": context.service_request_id,
                    "payment_id": payment_id,
                    "workflow_code": context.workflow_code,
                    "user_id": context.user_id,
                },
            )

            # 5. Call gateway API (polymorphic)
            gw_response = await self.gateway.create_payment(gw_request)

            if not gw_response.success:
                # Gateway API call failed
                await self._update_payment_status(
                    db=db,
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error=gw_response.error or f"{self.gateway.bank_code} API call failed",
                )

                # Publish PAYMENT_FAILED event
                try:
                    EventBus.publish_nowait(EventType.PAYMENT_FAILED, {
                        "payment_id": payment_id,
                        "user_id": context.user_id,
                        "service_request_id": context.service_request_id,
                        "amount": float(context.amount),
                        "currency": context.currency,
                        "payment_method": context.payment_method.value,
                        "user_email": context.user_email,
                        "user_phone": context.user_phone,
                        "preferred_language": "es",
                        "reason": (
                            f"Error al conectar con el sistema de pago "
                            f"{self.gateway.bank_name}"
                        ),
                        "bank_code": self.gateway.bank_code,
                    })
                except Exception as e:
                    logger.error(f"Failed to publish PAYMENT_FAILED event: {e}")

                return PaymentInitResult(
                    success=False,
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error=gw_response.error,
                    message_es=(
                        "Error al conectar con el sistema de pago. "
                        "Intente nuevamente."
                    ),
                )

            # 6. Update record with external transaction ID
            await self._update_gateway_reference(
                db=db,
                payment_id=payment_id,
                external_id=gw_response.external_id,
                expires_at=gw_response.expires_at,
            )

            logger.info(
                f"{self.gateway.bank_code} payment initiated: "
                f"{payment_id} -> {gw_response.external_id}"
            )

            return PaymentInitResult(
                success=True,
                payment_id=payment_id,
                external_reference=gw_response.external_id,
                redirect_url=gw_response.redirect_url,
                status=PaymentStatus.PROCESSING,
                requires_action=True,
                action_type="redirect",
                message_es="Redirigiendo al sistema de pago...",
                expires_at=gw_response.expires_at,
                metadata={
                    "gateway_payment_id": gw_response.external_id,
                    "payment_reference": payment_reference,
                    "bank_code": self.gateway.bank_code,
                },
            )

        except Exception as e:
            logger.error(f"Error initiating {self.gateway.bank_code} payment: {e}")
            return PaymentInitResult(
                success=False,
                payment_id=str(uuid4()),
                status=PaymentStatus.FAILED,
                error=str(e),
                message_es="Error interno. Contacte soporte técnico.",
            )

    async def check_status(
        self,
        db: asyncpg.Connection,
        payment_id: str
    ) -> PaymentStatusResult:
        """
        Check payment status.

        First checks local DB, then verifies with gateway API if still processing.
        """
        try:
            # 1. Get local payment record
            payment = await self._get_payment(db, payment_id)
            if not payment:
                return PaymentStatusResult(
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error="Payment not found",
                )

            local_status = PaymentStatus(payment["status"])

            # 2. If terminal status, return local
            if local_status in [
                PaymentStatus.COMPLETED,
                PaymentStatus.FAILED,
                PaymentStatus.CANCELLED,
            ]:
                return PaymentStatusResult(
                    payment_id=payment_id,
                    status=local_status,
                    paid=local_status == PaymentStatus.COMPLETED,
                    paid_at=payment.get("paid_at"),
                    amount=payment.get("total_amount"),
                    currency=payment.get("currency", "XAF"),
                    receipt_number=payment.get("receipt_number"),
                    receipt_url=payment.get("receipt_url"),
                )

            # 3. If still processing, verify with gateway API
            gateway_transaction_id = payment.get("gateway_transaction_id")
            if gateway_transaction_id:
                gw_status = await self.gateway.verify_payment(gateway_transaction_id)

                if gw_status.paid:
                    paid_at = gw_status.paid_at or datetime.now(timezone.utc)
                    sr_id = payment.get("service_request_id")

                    # ATOMIC: mark_completed + outbox INSERT
                    async with db.transaction():
                        await self._mark_payment_completed(
                            db=db,
                            payment_id=payment_id,
                            paid_at=paid_at,
                        )

                        # Insert into assignment outbox
                        if sr_id:
                            from app.modules.service_requests.services.assignment_outbox_service import (
                                assignment_outbox_service,
                            )
                            sr_data = await db.fetchrow(
                                "SELECT workflow_code, entity_code, entity_location_id "
                                "FROM service_requests WHERE id = $1",
                                sr_id,
                            )
                            if sr_data and sr_data["entity_code"]:
                                await assignment_outbox_service.enqueue(
                                    db=db,
                                    service_request_id=sr_id,
                                    workflow_code=sr_data["workflow_code"],
                                    entity_code=sr_data["entity_code"],
                                    entity_location_id=sr_data["entity_location_id"],
                                    payment_id=payment_id,
                                    payment_method=payment.get(
                                        "payment_method", "mobile_money"
                                    ),
                                )
                                logger.info(
                                    f"Outbox item created for "
                                    f"{self.gateway.bank_code} payment {payment_id}"
                                )

                    # Publish PAYMENT_COMPLETED event (outside transaction)
                    user_data = None
                    try:
                        user_data = await db.fetchrow(
                            "SELECT email, phone_number as phone, preferred_language "
                            "FROM users WHERE id = $1",
                            payment.get("user_id"),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch user for notification: {e}")

                    try:
                        await EventBus.publish(EventType.PAYMENT_COMPLETED, {
                            "payment_id": payment_id,
                            "user_id": str(payment.get("user_id")),
                            "service_request_id": str(sr_id) if sr_id else None,
                            "amount": float(payment.get("total_amount", 0)),
                            "currency": payment.get("currency", "XAF"),
                            "payment_method": payment.get(
                                "payment_method", "mobile_money"
                            ),
                            "receipt_number": payment.get("receipt_number"),
                            "gateway_transaction_id": gateway_transaction_id,
                            "bank_code": self.gateway.bank_code,
                            "user_email": (
                                user_data["email"] if user_data else None
                            ),
                            "user_phone": (
                                user_data["phone"] if user_data else None
                            ),
                            "preferred_language": (
                                user_data["preferred_language"]
                                if user_data else "es"
                            ),
                            "date": paid_at.strftime("%d/%m/%Y"),
                        })
                    except Exception as e:
                        logger.error(
                            f"Failed to publish PAYMENT_COMPLETED: {e}"
                        )

                    return PaymentStatusResult(
                        payment_id=payment_id,
                        status=PaymentStatus.COMPLETED,
                        paid=True,
                        paid_at=paid_at,
                        amount=payment.get("total_amount"),
                        currency=payment.get("currency", "XAF"),
                    )

            # 4. Still processing
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.PROCESSING,
                paid=False,
                amount=payment.get("total_amount"),
                currency=payment.get("currency", "XAF"),
            )

        except Exception as e:
            logger.error(
                f"Error checking {self.gateway.bank_code} payment status: {e}"
            )
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.PENDING,
                error=str(e),
            )

    async def cancel(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel a pending gateway payment."""
        try:
            payment = await self._get_payment(db, payment_id)
            if not payment:
                return False

            if payment["status"] not in ["pending", "processing"]:
                return False

            # Cancel with gateway if we have an external ID
            external_id = payment.get("gateway_transaction_id")
            if external_id:
                await self.gateway.cancel_payment(external_id, reason or "")

            await self._update_payment_status(
                db=db,
                payment_id=payment_id,
                status=PaymentStatus.CANCELLED,
                error=reason,
            )
            return True

        except Exception as e:
            logger.error(
                f"Error cancelling {self.gateway.bank_code} payment: {e}"
            )
            return False

    # === Private Helper Methods ===

    def _generate_reference(self, context: PaymentContext) -> str:
        """Generate unique payment reference."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        short_id = str(uuid4())[:8].upper()
        return f"SR-{timestamp}-{short_id}"

    async def _create_service_payment(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        context: PaymentContext,
        payment_reference: str,
    ) -> None:
        """Create service_payment record in database."""
        calculation_details = None
        if context.tariff_breakdown:
            calculation_details = json.dumps(context.tariff_breakdown)

        total_amount = context.get_total_amount()
        base_amount = context.amount

        if context.tariff_breakdown:
            base_amount = Decimal(
                str(context.tariff_breakdown.get("base_amount", context.amount))
            )

        query = """
            INSERT INTO service_payments (
                id, payment_reference, user_id, service_request_id,
                payment_type, payment_method, base_amount, total_amount, currency,
                calculation_details,
                status, workflow_status, requires_agent_validation,
                created_at, updated_at
            ) VALUES (
                $1::uuid, $2, $3::uuid, $4::uuid,
                'full', $5, $6, $7, $8,
                $9::jsonb,
                'processing', 'submitted', false,
                NOW(), NOW()
            )
        """
        await db.execute(
            query,
            payment_id,
            payment_reference,
            context.user_id,
            context.service_request_id,
            context.payment_method.value,
            base_amount,
            total_amount,
            context.currency,
            calculation_details,
        )

    async def _update_gateway_reference(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        external_id: str,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """Update payment with gateway external transaction ID."""
        query = """
            UPDATE service_payments
            SET gateway_transaction_id = $2,
                expires_at = $3,
                updated_at = NOW()
            WHERE id = $1
        """
        await db.execute(query, payment_id, external_id, expires_at)

    async def _update_payment_status(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        status: PaymentStatus,
        error: Optional[str] = None,
    ) -> None:
        """Update payment status."""
        query = """
            UPDATE service_payments
            SET status = $2,
                updated_at = NOW()
            WHERE id = $1
        """
        await db.execute(query, payment_id, status.value)

    async def _mark_payment_completed(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        paid_at: datetime,
    ) -> None:
        """
        Mark payment as completed.
        Updates both service_payments AND service_requests.
        """
        query = """
            UPDATE service_payments
            SET status = 'completed',
                workflow_status = 'completed',
                paid_at = $2,
                updated_at = NOW()
            WHERE id = $1
            RETURNING service_request_id
        """
        result = await db.fetchrow(query, payment_id, paid_at)

        if result and result["service_request_id"]:
            await db.execute(
                """
                UPDATE service_requests
                SET payment_status = 'completed',
                    status = 'PAID',
                    paid_at = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                result["service_request_id"],
                paid_at,
            )
            logger.info(
                f"{self.gateway.bank_code} payment {payment_id} completed - "
                f"service_request {result['service_request_id']} status=PAID"
            )

            # OMS hook: if this payment has fee_type, route linked obligations
            try:
                from app.modules.fiscal_services.services.license_service import (
                    LicenseService,
                )
                await LicenseService.on_payment_completed(db, payment_id)
            except Exception as e:
                logger.error(
                    f"OMS hook failed for payment {payment_id}: {e}",
                    exc_info=True,
                )

    async def _get_payment(
        self,
        db: asyncpg.Connection,
        payment_id: str,
    ) -> Optional[dict]:
        """Get payment record from database."""
        query = """
            SELECT * FROM service_payments WHERE id = $1::uuid
        """
        return await db.fetchrow(query, payment_id)
