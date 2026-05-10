"""
Payment Processor Registry.

Central registry that maps payment methods to their appropriate processors.
Supports multiple bank gateways with priority routing.

Architecture:
    _processors: PaymentMethod → PaymentProcessorBase (for payment initiation)
    _gateways:   bank_code → GatewayProcessor (for webhook dispatch)
"""

from typing import Optional, Dict, List
from decimal import Decimal
import asyncpg
from loguru import logger

from app.modules.payments.models.payment import PaymentMethod, PaymentStatus

from .base import (
    PaymentProcessorBase,
    PaymentContext,
    PaymentInitResult,
    PaymentStatusResult,
)
from .bange_processor import BangeProcessor, bange_processor
from .manual_processor import ManualValidationProcessor, manual_processor


class PaymentProcessorRegistry:
    """
    Registry for payment processors.

    Routes payment operations to the appropriate processor
    based on payment method.

    Multi-gateway support:
    - Multiple gateways can be registered
    - Each payment method maps to exactly one processor (primary)
    - Gateways are also indexed by bank_code for webhook dispatch

    Usage:
        registry = PaymentProcessorRegistry()
        result = await registry.initiate_payment(db, context)

        # Webhook dispatch
        processor = registry.get_gateway_by_bank_code("ECOBANK")
    """

    def __init__(self):
        # PaymentMethod → processor (for payment initiation)
        self._processors: Dict[PaymentMethod, PaymentProcessorBase] = {}
        # bank_code → GatewayProcessor (for webhook dispatch)
        self._gateways: Dict[str, PaymentProcessorBase] = {}
        self._register_default_processors()

    def _register_default_processors(self) -> None:
        """Register default payment processors."""
        # BANGE processor for electronic payments (backward compat)
        for method in bange_processor.get_supported_methods():
            self._processors[method] = bange_processor

        # Register BANGE in gateway index for webhook dispatch
        self._gateways["BANGE"] = bange_processor

        # Manual processor for cash/check
        for method in manual_processor.get_supported_methods():
            self._processors[method] = manual_processor

        # Try to register additional gateways from config
        self._register_configured_gateways()

        logger.info(
            f"PaymentProcessorRegistry initialized with {len(self._processors)} methods: "
            f"{[m.value for m in self._processors.keys()]}"
        )
        if len(self._gateways) > 1:
            logger.info(
                f"  Gateways registered: {list(self._gateways.keys())}"
            )

    def _register_configured_gateways(self) -> None:
        """
        Register additional gateways based on configuration.

        Checks for configured credentials and registers gateways
        that have valid credentials. Uses GatewayProcessor wrapper.
        """
        try:
            from app.config import get_settings
            settings = get_settings()

            # Ecobank: register if credentials are configured
            ecobank_client_id = getattr(settings, "ECOBANK_CLIENT_ID", None)
            if ecobank_client_id:
                try:
                    from app.modules.payments.services.gateways.ecobank_gateway import (
                        EcobankGateway,
                    )
                    from .gateway_processor import GatewayProcessor

                    ecobank_gateway = EcobankGateway()
                    ecobank_processor = GatewayProcessor(ecobank_gateway)

                    # Register in gateway index for webhook dispatch
                    self._gateways["ECOBANK"] = ecobank_processor

                    # Check which methods Ecobank should be primary for
                    ecobank_primary_methods = getattr(
                        settings, "ECOBANK_PRIMARY_METHODS", None
                    )
                    if ecobank_primary_methods:
                        # Admin explicitly configured primary methods
                        for method_str in ecobank_primary_methods.split(","):
                            method_str = method_str.strip()
                            try:
                                method = PaymentMethod(method_str)
                                self._processors[method] = ecobank_processor
                                logger.info(
                                    f"Ecobank is PRIMARY for {method.value}"
                                )
                            except ValueError:
                                logger.warning(
                                    f"Invalid payment method: {method_str}"
                                )
                    else:
                        # Register only for methods not already claimed
                        for method_str in ecobank_gateway.get_supported_methods():
                            method = PaymentMethod(method_str)
                            if method not in self._processors:
                                self._processors[method] = ecobank_processor

                    logger.info(
                        "Ecobank gateway registered successfully"
                    )
                except ImportError:
                    logger.debug(
                        "EcobankGateway not yet implemented, skipping"
                    )
                except Exception as e:
                    logger.warning(f"Failed to register Ecobank gateway: {e}")

            # MPGS (Mastercard): register if merchant ID is configured
            mpgs_merchant_id = getattr(settings, "MPGS_MERCHANT_ID", None)
            if mpgs_merchant_id:
                try:
                    from app.modules.payments.services.gateways.mastercard_gateway import (
                        MastercardGateway,
                    )
                    from .gateway_processor import GatewayProcessor as GwProc

                    mpgs_gateway = MastercardGateway()
                    mpgs_processor = GwProc(mpgs_gateway)

                    # Register with internal code for webhook dispatch
                    self._gateways["ECOBANK_MPGS"] = mpgs_processor

                    # Route configured methods to MPGS (default: card)
                    mpgs_primary = getattr(
                        settings, "MPGS_PRIMARY_METHODS", "card"
                    )
                    if mpgs_primary:
                        for method_str in mpgs_primary.split(","):
                            method_str = method_str.strip()
                            try:
                                method = PaymentMethod(method_str)
                                self._processors[method] = mpgs_processor
                                logger.info(
                                    f"MPGS is PRIMARY for {method.value}"
                                )
                            except ValueError:
                                logger.warning(
                                    f"Invalid MPGS method: {method_str}"
                                )

                    logger.info(
                        "MPGS (Mastercard) gateway registered successfully"
                    )
                except ImportError:
                    logger.debug(
                        "MastercardGateway not available, skipping"
                    )
                except Exception as e:
                    logger.warning(f"Failed to register MPGS gateway: {e}")

        except Exception as e:
            logger.warning(f"Error registering additional gateways: {e}")

    def register(
        self, method: PaymentMethod, processor: PaymentProcessorBase
    ) -> None:
        """
        Register a custom processor for a payment method.

        Args:
            method: Payment method
            processor: Processor instance to handle this method
        """
        self._processors[method] = processor
        logger.info(
            f"Registered processor {processor.__class__.__name__} "
            f"for {method.value}"
        )

    def register_gateway(
        self,
        gateway_processor: PaymentProcessorBase,
        bank_code: str,
        primary_for: Optional[List[PaymentMethod]] = None,
    ) -> None:
        """
        Register a gateway processor, optionally as primary for methods.

        Args:
            gateway_processor: GatewayProcessor instance
            bank_code: Bank code for webhook dispatch (e.g., "ECOBANK")
            primary_for: If set, override primary processor for these methods
        """
        self._gateways[bank_code.upper()] = gateway_processor

        if primary_for:
            for method in primary_for:
                self._processors[method] = gateway_processor
                logger.info(
                    f"Gateway {bank_code} is PRIMARY for {method.value}"
                )

        logger.info(f"Registered gateway: {bank_code}")

    def get_processor(
        self, method: PaymentMethod
    ) -> Optional[PaymentProcessorBase]:
        """
        Get the processor for a specific payment method.

        Args:
            method: Payment method

        Returns:
            Processor instance or None if not found
        """
        return self._processors.get(method)

    def get_gateway_by_bank_code(
        self, bank_code: str
    ) -> Optional[PaymentProcessorBase]:
        """
        Get a gateway processor by bank code.
        Used for webhook dispatch: /webhooks/{bank_code}

        Args:
            bank_code: Bank code (e.g., "BANGE", "ECOBANK")

        Returns:
            GatewayProcessor instance or None
        """
        return self._gateways.get(bank_code.upper())

    def get_registered_gateways(self) -> Dict[str, PaymentProcessorBase]:
        """Get all registered gateway processors."""
        return dict(self._gateways)

    def get_available_methods(self) -> List[PaymentMethod]:
        """
        Get all available payment methods.

        Returns:
            List of available PaymentMethod values
        """
        return list(self._processors.keys())

    def get_methods_info(self) -> List[Dict]:
        """
        Get detailed information about available payment methods.

        Returns list with method code, label, processor type, and bank info.
        Useful for frontend to display payment options.
        """
        methods_info = []
        for method, processor in self._processors.items():
            info = {
                "code": method.value,
                "label_es": self._get_method_label_es(method),
                "label_en": self._get_method_label_en(method),
                "label_fr": self._get_method_label_fr(method),
                "processor_type": processor.processor_type.value,
                "requires_phone": method == PaymentMethod.MOBILE_MONEY,
                "requires_redirect": (
                    processor.processor_type.value != "manual"
                ),
                "requires_agent_validation": (
                    processor.processor_type.value == "manual"
                ),
            }

            # Add bank info for gateway processors
            if hasattr(processor, "gateway"):
                info["bank_code"] = processor.gateway.bank_code
                info["bank_name"] = processor.gateway.bank_name
            else:
                info["bank_code"] = None
                info["bank_name"] = None

            methods_info.append(info)
        return methods_info

    def _get_fallback_processor(
        self,
        method: PaymentMethod,
        failed_processor: PaymentProcessorBase,
    ) -> Optional[PaymentProcessorBase]:
        """
        Find alternative gateway for the same method if primary fails.

        Iterates registered gateways and returns the first one that
        supports the given method and is not the failed processor.
        """
        for bank_code, gw_proc in self._gateways.items():
            if gw_proc is failed_processor:
                continue
            # Check if this gateway supports the method
            supported = gw_proc.get_supported_methods()
            if method in supported or method.value in supported:
                logger.info(
                    f"Fallback gateway found: {bank_code} for {method.value}"
                )
                return gw_proc
        return None

    async def initiate_payment(
        self,
        db: asyncpg.Connection,
        context: PaymentContext
    ) -> PaymentInitResult:
        """
        Initiate a payment using the appropriate processor.
        If the primary processor fails, attempts fallback to another gateway.

        Args:
            db: Database connection
            context: Payment context with all required information

        Returns:
            PaymentInitResult from the appropriate processor
        """
        processor = self.get_processor(context.payment_method)
        if not processor:
            logger.error(
                f"No processor registered for method: "
                f"{context.payment_method}"
            )
            return PaymentInitResult(
                success=False,
                payment_id="",
                status=PaymentStatus.FAILED,
                error=(
                    f"Payment method not supported: "
                    f"{context.payment_method.value}"
                ),
                message_es=(
                    f"Método de pago no soportado: "
                    f"{context.payment_method.value}"
                ),
            )

        logger.info(
            f"Initiating {context.payment_method.value} payment via "
            f"{processor.__class__.__name__} "
            f"for service_request {context.service_request_id}"
        )

        result = await processor.initiate(db, context)

        # Fallback: if primary gateway fails, try alternative
        if not result.success and hasattr(processor, 'gateway'):
            fallback = self._get_fallback_processor(
                context.payment_method, processor
            )
            if fallback:
                logger.warning(
                    f"Primary gateway {processor.__class__.__name__} failed "
                    f"({result.error}), trying fallback "
                    f"{fallback.__class__.__name__}"
                )
                result = await fallback.initiate(db, context)
                if result.success:
                    logger.info(
                        f"Fallback gateway succeeded for "
                        f"{context.payment_method.value}"
                    )

        return result

    async def check_status(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        payment_method: Optional[PaymentMethod] = None
    ) -> PaymentStatusResult:
        """
        Check payment status.

        If payment_method is provided, uses that processor.
        Otherwise, queries DB to find the payment and its method.
        """
        if not payment_method:
            payment = await self._get_payment_method(db, payment_id)
            if not payment:
                return PaymentStatusResult(
                    payment_id=payment_id,
                    status=PaymentStatus.FAILED,
                    error="Payment not found",
                )
            payment_method = PaymentMethod(payment["payment_method"])

        processor = self.get_processor(payment_method)
        if not processor:
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                error=f"No processor for method: {payment_method.value}",
            )

        return await processor.check_status(db, payment_id)

    async def cancel_payment(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel a pending payment."""
        payment = await self._get_payment_method(db, payment_id)
        if not payment:
            return False

        processor = self.get_processor(
            PaymentMethod(payment["payment_method"])
        )
        if not processor:
            return False

        return await processor.cancel(db, payment_id, reason)

    # === Agent Validation Methods (for manual payments) ===

    async def validate_manual_payment(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        agent_profile_id: str,
        comment: Optional[str] = None
    ) -> PaymentStatusResult:
        """
        Validate a manual payment (cash/check).
        Called by Treasury agent when they confirm receipt.
        """
        payment = await self._get_payment_method(db, payment_id)
        if not payment:
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                error="Payment not found",
            )

        method = PaymentMethod(payment["payment_method"])
        if method not in [PaymentMethod.CASH, PaymentMethod.CHECK]:
            return PaymentStatusResult(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
                error="Payment method does not require manual validation",
            )

        return await manual_processor.validate_payment(
            db, payment_id, agent_profile_id, comment
        )

    async def reject_manual_payment(
        self,
        db: asyncpg.Connection,
        payment_id: str,
        agent_profile_id: str,
        reason: str
    ) -> PaymentStatusResult:
        """
        Reject a manual payment (cash/check).
        Called by Treasury agent when they reject a payment.
        """
        return await manual_processor.reject_payment(
            db, payment_id, agent_profile_id, reason
        )

    # === Private Helper Methods ===

    async def _get_payment_method(
        self,
        db: asyncpg.Connection,
        payment_id: str
    ) -> Optional[dict]:
        """Get payment record with method from database."""
        query = """
            SELECT id, payment_method, status
            FROM service_payments
            WHERE id = $1::uuid
        """
        return await db.fetchrow(query, payment_id)

    def _get_method_label_es(self, method: PaymentMethod) -> str:
        labels = {
            PaymentMethod.MOBILE_MONEY: "Dinero Móvil",
            PaymentMethod.CARD: "Tarjeta Bancaria",
            PaymentMethod.BANK_TRANSFER: "Transferencia Bancaria",
            PaymentMethod.CASH: "Efectivo",
            PaymentMethod.CHECK: "Cheque",
        }
        return labels.get(method, method.value)

    def _get_method_label_en(self, method: PaymentMethod) -> str:
        labels = {
            PaymentMethod.MOBILE_MONEY: "Mobile Money",
            PaymentMethod.CARD: "Bank Card",
            PaymentMethod.BANK_TRANSFER: "Bank Transfer",
            PaymentMethod.CASH: "Cash",
            PaymentMethod.CHECK: "Check",
        }
        return labels.get(method, method.value)

    def _get_method_label_fr(self, method: PaymentMethod) -> str:
        labels = {
            PaymentMethod.MOBILE_MONEY: "Mobile Money",
            PaymentMethod.CARD: "Carte Bancaire",
            PaymentMethod.BANK_TRANSFER: "Virement Bancaire",
            PaymentMethod.CASH: "Espèces",
            PaymentMethod.CHECK: "Chèque",
        }
        return labels.get(method, method.value)


# Singleton instance
payment_processor_registry = PaymentProcessorRegistry()
