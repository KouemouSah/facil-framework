"""
Payment Processors Module.

Provides a unified interface for handling different payment methods
using the Strategy pattern.

Processors:
- GatewayProcessor: Generic processor for any bank gateway API
- BangeProcessor: BANGE-specific processor (backward compat, uses BANGEService)
- ManualValidationProcessor: For manual validation (Cash, Check)
"""

from .base import PaymentProcessorBase, PaymentInitResult, PaymentStatusResult, PaymentContext
from .gateway_processor import GatewayProcessor
from .bange_processor import BangeProcessor, bange_processor
from .manual_processor import ManualValidationProcessor, manual_processor
from .registry import PaymentProcessorRegistry, payment_processor_registry

__all__ = [
    "PaymentProcessorBase",
    "PaymentInitResult",
    "PaymentStatusResult",
    "PaymentContext",
    "GatewayProcessor",
    "BangeProcessor",
    "bange_processor",
    "ManualValidationProcessor",
    "manual_processor",
    "PaymentProcessorRegistry",
    "payment_processor_registry",
]
