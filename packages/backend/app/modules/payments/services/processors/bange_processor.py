"""
BANGE Payment Processor.

Handles payments via BANGE API:
- Mobile Money (MTN, Orange)
- Card payments
- Bank transfers

Uses the existing BANGEService for API communication.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import json
import asyncpg
from loguru import logger

from app.modules.payments.models.payment import (
    PaymentMethod,
    PaymentStatus,
    BANGEPaymentRequest,
)
from app.modules.payments.services.bange_service import BANGEService
from app.modules.payments.services.gateways.bange_gateway import BANGEGateway
from app.config import get_settings
from app.core.events import EventBus, EventType
from app.core.circuit_breaker import bange_circuit

from .base import (
    PaymentProcessorBase,
    ProcessorType,
    PaymentContext,
    PaymentInitResult,
    PaymentStatusResult,
)


class BangeProcessor(PaymentProcessorBase):
    """
    Payment processor for BANGE API payments.

    Handles Mobile Money, Card, and Bank Transfer payments
    via the BANGE payment gateway.
    """

    processor_type = ProcessorType.BANGE_API

    def __init__(self):
        self.bange_service = BANGEService()
        self.gateway = BANGEGateway()  # For registry bank_code/bank_name access
        self.settings = get_settings()

    def get_supported_methods(self) -> list[PaymentMethod]:
        """Return payment methods handled by BANGE API."""
        return [
            PaymentMethod.MOBILE_MONEY,
            PaymentMethod.CARD,
            PaymentMethod.BANK_TRANSFER,
        ]

    async def initiate(
        self,
        db: asyncpg.Connection,
        context: PaymentContext
    ) -> PaymentInitResult:
        """
        Initiate a payment via BANGE API.

        1. Generate unique payment reference
        2. Create service_payment record in DB
        3. Call BANGE API to create payment
        4. Update record with BANGE transaction ID
        5. Return redirect URL for user

        Args:
            db: Database connection
            context: Payment context

        Returns:
            PaymentInitResult with redirect URL for BANGE payment page
        """
        # ── CIRCUIT BREAKER: fast-fail if BANGE is down ──
        if not bange_circuit.allow_request():
            logger.warning("BANGE circuit breaker OPEN — payment rejected without API call")
            return PaymentInitResult(
                success=False,
                payment_id=str(uuid4()),
                status=PaymentStatus.FAILED,
                error="El sistema de pago no esta disponible temporalmente. Intente en unos minutos.",
                message_es="El sistema de pago no esta disponible temporalmente. Intente en unos minutos.",
            )

        try:
            # 1. Generate payment reference
            payment_reference = self._generate_reference(context)
            payment_id = str(uuid4())

            # 2. Create service_payment record with status 'pending' (short transaction)
            await self._create_service_payment(
                db=db,
                payment_id=payment_id,
                context=context,
                payment_reference=payment_reference
            )

            # 3. Build callback URLs (Note: Settings fields are UPPERCASE)
            callback_url = f"{self.settings.API_BASE_URL}/api/v1/webhooks/bange"
            # Prefer client-supplied return_url (mobile deep link) when provided and validated.
            # Falls back to the web dashboard URL for browser clients.
            return_url = (
                context.return_url
                or f"{self.settings.FRONTEND_URL}/dashboard/service-requests/{context.service_request_id}/payment/result"
            )

            # 4. Create BANGE payment request
            bange_request = BANGEPaymentRequest(
                amount=context.amount,
                currency=context.currency,
                description=f"Pago {context.service_name or context.workflow_code} - {context.reference_number}",
                reference=payment_reference,
                customer_email=context.user_email,
                customer_phone=context.user_phone,
                callback_url=callback_url,
                return_url=return_url,
                metadata={
                    "service_request_id": context.service_request_id,
                    "payment_id": payment_id,
                    "workflow_code": context.workflow_code,
                    "user_id": context.user_id,
                }
            )

            # 5. Call BANGE API (OUTSIDE transaction — don't hold DB connection during HTTP)
            bange_response = await self.bange_service.create_payment(bange_request)

            if not bange_response:
                # BANGE API failed — mark the existing record as FAILED
                bange_circuit.record_failure()
                await self._update_payment_status(
                    db=db,
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error="BANGE API call failed"
                )
                logger.warning(f"BANGE API failed for payment {payment_id}")

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
                        "reason": "Error al conectar con el sistema de pago BANGE",
                    })
                except Exception as e:
                    logger.error(f"Failed to publish PAYMENT_FAILED event: {e}")

                return PaymentInitResult(
                    success=False,
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error="Error al conectar con el sistema de pago. Intente nuevamente.",
                    message_es="Error al conectar con el sistema de pago. Intente nuevamente."
                )

            # 6. Update record with BANGE transaction ID (short transaction)
            await self._update_gateway_reference(
                db=db,
                payment_id=payment_id,
                gateway_transaction_id=bange_response.payment_id,
                expires_at=bange_response.expires_at
            )

            bange_circuit.record_success()
            logger.info(
                f"BANGE payment initiated: {payment_id} -> {bange_response.payment_id}"
            )

            return PaymentInitResult(
                success=True,
                payment_id=payment_id,
                external_reference=bange_response.payment_id,
                redirect_url=bange_response.payment_url,
                status=PaymentStatus.PROCESSING,
                requires_action=True,
                action_type="redirect",
                message_es="Redirigiendo al sistema de pago...",
                expires_at=bange_response.expires_at,
                metadata={
                    "bange_payment_id": bange_response.payment_id,
                    "payment_reference": payment_reference,
                }
            )

        except Exception as e:
            logger.error(f"Error initiating BANGE payment: {e}")
            return PaymentInitResult(
                success=False,
                payment_id=str(uuid4()),
                status=PaymentStatus.FAILED,
                error=str(e),
                message_es="Error interno. Contacte soporte técnico."
            )

    async def check_status(
        self,
        db: asyncpg.Connection,
        payment_id: str
    ) -> PaymentStatusResult:
        """
        Check payment status.

        First checks local DB, then verifies with BANGE API if still processing.

        Args:
            db: Database connection
            payment_id: Internal payment ID

        Returns:
            PaymentStatusResult with current status
        """
        try:
            # 1. Get local payment record
            payment = await self._get_payment(db, payment_id)
            if not payment:
                return PaymentStatusResult(
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error="Payment not found"
                )

            local_status = PaymentStatus(payment["status"])

            # 2. If already completed or failed, return local status
            if local_status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.CANCELLED]:
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

            # 3. If still processing, verify with BANGE
            gateway_transaction_id = payment.get("gateway_transaction_id")
            if gateway_transaction_id:
                bange_status = await self.bange_service.verify_payment(gateway_transaction_id)

                if bange_status and bange_status.get("status") == "completed":
                    paid_at = datetime.now(timezone.utc)
                    sr_id = payment.get("service_request_id")

                    # ATOMIC: mark_completed + outbox INSERT in same transaction
                    # If outbox fails → payment stays 'processing' → next poll retries
                    async with db.transaction():
                        await self._mark_payment_completed(
                            db=db,
                            payment_id=payment_id,
                            paid_at=paid_at
                        )

                        # Insert into assignment outbox (guaranteed delivery)
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
                                    payment_method=payment.get("payment_method", "mobile_money"),
                                )
                                logger.info(f"Outbox item created for BANGE payment {payment_id}")

                    # Get user data for notifications (outside transaction)
                    user_data = None
                    try:
                        user_data = await db.fetchrow(
                            "SELECT email, phone_number as phone, preferred_language FROM users WHERE id = $1",
                            payment.get("user_id")
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch user data for notification: {e}")

                    # Publish PAYMENT_COMPLETED event (fallback + notifications)
                    try:
                        await EventBus.publish(EventType.PAYMENT_COMPLETED, {
                            "payment_id": payment_id,
                            "user_id": str(payment.get("user_id")),
                            "service_request_id": str(sr_id) if sr_id else None,
                            "amount": float(payment.get("total_amount", 0)),
                            "currency": payment.get("currency", "XAF"),
                            "payment_method": payment.get("payment_method", "mobile_money"),
                            "receipt_number": payment.get("receipt_number"),
                            "gateway_transaction_id": gateway_transaction_id,
                            "user_email": user_data["email"] if user_data else None,
                            "user_phone": user_data["phone"] if user_data else None,
                            "preferred_language": user_data["preferred_language"] if user_data else "es",
                            "date": paid_at.strftime("%d/%m/%Y"),
                        })
                        logger.info(f"PAYMENT_COMPLETED event published for BANGE payment {payment_id}")
                    except Exception as e:
                        logger.error(f"Failed to publish PAYMENT_COMPLETED for BANGE payment: {e}")

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
            logger.error(f"Error checking BANGE payment status: {e}")
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.PENDING,
                error=str(e)
            )

    async def cancel(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel a pending BANGE payment.

        Args:
            db: Database connection
            payment_id: Internal payment ID
            reason: Cancellation reason

        Returns:
            True if cancelled successfully
        """
        try:
            payment = await self._get_payment(db, payment_id)
            if not payment:
                return False

            # Can only cancel pending/processing payments
            if payment["status"] not in ["pending", "processing"]:
                return False

            # Cancel with BANGE if we have a transaction ID
            bange_id = payment.get("gateway_transaction_id")
            if bange_id:
                # BANGE cancellation would go here
                pass

            # Update local status
            await self._update_payment_status(
                db=db,
                payment_id=payment_id,
                status=PaymentStatus.CANCELLED,
                error=reason
            )

            return True
        except Exception as e:
            logger.error(f"Error cancelling BANGE payment: {e}")
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
        payment_reference: str
    ) -> None:
        """Create service_payment record in database."""
        # Serialize tariff_breakdown for calculation_details
        calculation_details = None
        if context.tariff_breakdown:
            calculation_details = json.dumps(context.tariff_breakdown)

        # Use total from tariff_breakdown if available
        total_amount = context.get_total_amount()
        base_amount = context.amount  # Original amount before supplements

        if context.tariff_breakdown:
            base_amount = Decimal(str(context.tariff_breakdown.get('base_amount', context.amount)))

        # fiscal_service_code column removed in migration 041
        # All payments now link via service_request_id

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
        gateway_transaction_id: str,
        expires_at: Optional[datetime] = None
    ) -> None:
        """Update payment with gateway transaction ID."""
        query = """
            UPDATE service_payments
            SET gateway_transaction_id = $2,
                expires_at = $3,
                updated_at = NOW()
            WHERE id = $1
        """
        await db.execute(query, payment_id, gateway_transaction_id, expires_at)

    async def _update_payment_status(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        status: PaymentStatus,
        error: Optional[str] = None
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
        paid_at: datetime
    ) -> None:
        """
        Mark payment as completed.

        Updates both service_payments AND service_requests tables
        to keep status in sync for frontend polling.
        """
        # 1. Update service_payments
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

        # 2. Update service_requests for frontend polling consistency
        # Critical: checkPaymentStatus endpoint reads from service_requests
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
                paid_at
            )
            logger.info(
                f"BANGE payment {payment_id} completed - "
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
        payment_id: str
    ) -> Optional[dict]:
        """Get payment record from database."""
        query = """
            SELECT * FROM service_payments WHERE id = $1::uuid
        """
        return await db.fetchrow(query, payment_id)


# Singleton instance
bange_processor = BangeProcessor()
