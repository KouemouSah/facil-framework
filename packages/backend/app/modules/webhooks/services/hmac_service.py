"""
HMAC Service - Webhook Signature Validation

Validate BANGE webhook signatures using HMAC-SHA256
"""

import hmac
import hashlib
from typing import Dict, Any
from loguru import logger


class HMACService:
    """Service for HMAC signature validation"""

    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature

        Args:
            payload: Request body as string
            secret: Webhook secret from bank_configurations

        Returns:
            HMAC hex digest
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def validate_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Validate HMAC signature

        Args:
            payload: Request body as string
            signature: Signature from webhook header
            secret: Webhook secret from bank_configurations

        Returns:
            True if signature is valid
        """
        expected_signature = HMACService.generate_signature(payload, secret)

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)

    @staticmethod
    async def validate_webhook(
        payload_bytes: bytes,
        signature_header: str,
        webhook_secret: str
    ) -> tuple[bool, str]:
        """
        Validate webhook request

        Returns:
            (is_valid, error_message)
        """
        if not signature_header:
            return False, "Missing signature header"

        if not webhook_secret:
            return False, "Webhook secret not configured"

        # Decode payload
        try:
            payload_str = payload_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decode payload: {e}")
            return False, f"Invalid payload encoding: {e}"

        # Validate signature
        is_valid = HMACService.validate_signature(
            payload_str,
            signature_header,
            webhook_secret
        )

        if not is_valid:
            logger.warning(f"Invalid webhook signature")
            return False, "Invalid signature"

        return True, ""
