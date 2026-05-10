"""
Payment Gateway Integrations.

Abstract base + concrete implementations for bank API integrations.
Each gateway handles API communication with a specific bank.

Available gateways:
    BANGEGateway      → https://api.bange.gq
    EcobankGateway    → https://developer.ecobank.com (Collection API)
    MastercardGateway → https://ecobank.gateway.mastercard.com (MPGS cards)
"""

from .base import (
    GatewayServiceBase,
    GatewayPaymentRequest,
    GatewayPaymentResponse,
    GatewayStatusResponse,
    GatewayWebhookData,
)
from .bange_gateway import BANGEGateway
from .ecobank_gateway import EcobankGateway
from .mastercard_gateway import MastercardGateway

__all__ = [
    "GatewayServiceBase",
    "GatewayPaymentRequest",
    "GatewayPaymentResponse",
    "GatewayStatusResponse",
    "GatewayWebhookData",
    "BANGEGateway",
    "EcobankGateway",
    "MastercardGateway",
]
