"""
Crypto Service for Verified Identifiers

Provides AES-256-GCM encryption and HMAC-SHA256 blind indexing
for secure storage and search of verified identifiers.

Keys are stored in Google Cloud Secret Manager.
"""

import os
import re
import hmac
import hashlib
import base64
from typing import Optional
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from loguru import logger

from app.core.secrets import get_secret


class CryptoServiceError(Exception):
    """Base exception for crypto service errors."""
    pass


class KeyNotFoundError(CryptoServiceError):
    """Raised when encryption keys are not available."""
    pass


class DecryptionError(CryptoServiceError):
    """Raised when decryption fails."""
    pass


class CryptoService:
    """
    Cryptographic service for verified identifiers.

    Uses:
    - AES-256-GCM for encryption (authenticated encryption)
    - HMAC-SHA256 for blind index (searchable without decryption)

    Keys are loaded from Secret Manager on initialization.
    """

    # Key names in Secret Manager
    AES_KEY_NAME = "verified-identifiers-aes-key"
    HMAC_KEY_NAME = "verified-identifiers-hmac-key"

    # AES-256-GCM parameters
    AES_KEY_SIZE = 32  # 256 bits
    NONCE_SIZE = 12    # 96 bits (recommended for GCM)
    TAG_SIZE = 16      # 128 bits

    def __init__(self, aes_key: Optional[bytes] = None, hmac_key: Optional[bytes] = None):
        """
        Initialize CryptoService.

        Args:
            aes_key: Optional AES key (for testing). If not provided, loads from Secret Manager.
            hmac_key: Optional HMAC key (for testing). If not provided, loads from Secret Manager.
        """
        self._aes_key = aes_key
        self._hmac_key = hmac_key
        self._keys_loaded = False

    def _ensure_keys_loaded(self) -> None:
        """Load keys from Secret Manager if not already loaded."""
        if self._keys_loaded:
            return

        if self._aes_key is None:
            logger.info(f"Loading AES key from secret: {self.AES_KEY_NAME}")
            aes_key_str = get_secret(self.AES_KEY_NAME)
            if not aes_key_str:
                logger.error(f"AES key not found. Secret name: {self.AES_KEY_NAME}")
                logger.error("Check: 1) Secret exists in Secret Manager 2) Correct name (with dashes) 3) Service account has secretAccessor role")
                raise KeyNotFoundError(
                    f"AES key not found in Secret Manager: {self.AES_KEY_NAME}. "
                    f"Ensure the secret exists with this exact name and the service account has access."
                )
            # Key is stored as base64
            try:
                self._aes_key = base64.b64decode(aes_key_str)
            except Exception:
                # Maybe it's hex-encoded
                self._aes_key = bytes.fromhex(aes_key_str)

            if len(self._aes_key) != self.AES_KEY_SIZE:
                raise KeyNotFoundError(
                    f"AES key must be {self.AES_KEY_SIZE} bytes, got {len(self._aes_key)}"
                )

        if self._hmac_key is None:
            hmac_key_str = get_secret(self.HMAC_KEY_NAME)
            if not hmac_key_str:
                raise KeyNotFoundError(
                    f"HMAC key not found in Secret Manager: {self.HMAC_KEY_NAME}"
                )
            # Key is stored as base64
            try:
                self._hmac_key = base64.b64decode(hmac_key_str)
            except Exception:
                # Maybe it's hex-encoded
                self._hmac_key = bytes.fromhex(hmac_key_str)

        self._keys_loaded = True
        logger.info("Crypto keys loaded successfully")

    def compute_blind_index(self, value: str, identifier_type: str) -> bytes:
        """
        Compute HMAC-SHA256 blind index for searchable encryption.

        The blind index allows searching for identifiers without decrypting them.
        Uses normalized value + identifier type to prevent cross-type collisions.

        Args:
            value: The identifier value (e.g., "123456789")
            identifier_type: The type (e.g., "dni", "pasaporte")

        Returns:
            32-byte HMAC-SHA256 digest
        """
        self._ensure_keys_loaded()

        # Normalize the value
        normalized = self._normalize_value(value, identifier_type)

        # Compute HMAC with type prefix to prevent cross-type attacks
        message = f"{identifier_type}:{normalized}".encode("utf-8")
        digest = hmac.new(
            self._hmac_key,
            message,
            hashlib.sha256
        ).digest()

        return digest

    def encrypt_value(self, value: str) -> bytes:
        """
        Encrypt a value using AES-256-GCM.

        Format: nonce (12 bytes) + tag (16 bytes) + ciphertext

        Args:
            value: The plaintext value to encrypt

        Returns:
            Encrypted bytes (nonce + tag + ciphertext)
        """
        self._ensure_keys_loaded()

        # Generate random nonce
        nonce = os.urandom(self.NONCE_SIZE)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self._aes_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt
        ciphertext = encryptor.update(value.encode("utf-8")) + encryptor.finalize()

        # Return: nonce + tag + ciphertext
        return nonce + encryptor.tag + ciphertext

    def decrypt_value(self, encrypted: bytes) -> str:
        """
        Decrypt a value using AES-256-GCM.

        Args:
            encrypted: Encrypted bytes (nonce + tag + ciphertext)

        Returns:
            Decrypted plaintext

        Raises:
            DecryptionError: If decryption fails (wrong key, tampered data, etc.)
        """
        self._ensure_keys_loaded()

        if len(encrypted) < self.NONCE_SIZE + self.TAG_SIZE:
            raise DecryptionError("Encrypted data too short")

        # Extract components
        nonce = encrypted[:self.NONCE_SIZE]
        tag = encrypted[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = encrypted[self.NONCE_SIZE + self.TAG_SIZE:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self._aes_key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode("utf-8")
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def _normalize_value(self, value: str, identifier_type: str) -> str:
        """
        Normalize identifier value for consistent hashing.

        Different identifier types have different normalization rules:
        - DNI: Remove non-digits, ensure 9 digits
        - Pasaporte: Uppercase, remove spaces/dashes
        - NIF: Uppercase, alphanumeric only
        - Default: Uppercase, strip whitespace

        Args:
            value: Raw identifier value
            identifier_type: Type of identifier

        Returns:
            Normalized value
        """
        value = value.strip().upper()

        if identifier_type == "dni":
            # DNI: Only digits, padded to 9
            value = re.sub(r"[^0-9]", "", value)
            value = value.zfill(9)[-9:]  # Keep last 9 digits

        elif identifier_type == "pasaporte":
            # Pasaporte: Alphanumeric only (2 letters + 6-7 digits)
            value = re.sub(r"[^A-Z0-9]", "", value)

        elif identifier_type == "nif":
            # NIF: Alphanumeric
            value = re.sub(r"[^A-Z0-9]", "", value)

        elif identifier_type == "permiso_residencia":
            # Residence permit: Keep alphanumeric and dashes
            value = re.sub(r"[^A-Z0-9\-]", "", value)

        elif identifier_type in ("cuve", "matricula_vehiculo"):
            # Vehicle identifiers: Alphanumeric and dashes
            value = re.sub(r"[^A-Z0-9\-]", "", value)

        elif identifier_type == "certificado_conducir":
            # Driver's license: Alphanumeric
            value = re.sub(r"[^A-Z0-9]", "", value)

        elif identifier_type == "registro_civil":
            # Civil registry: Alphanumeric and dashes
            value = re.sub(r"[^A-Z0-9\-]", "", value)

        elif identifier_type == "contrato_ornc":
            # Contract: Alphanumeric and dashes
            value = re.sub(r"[^A-Z0-9\-]", "", value)

        else:
            # Default: Alphanumeric only
            value = re.sub(r"[^A-Z0-9]", "", value)

        return value

    def validate_format(self, value: str, identifier_type: str, regex_pattern: Optional[str] = None) -> bool:
        """
        Validate identifier format.

        Args:
            value: The identifier value
            identifier_type: The type of identifier
            regex_pattern: Optional custom regex pattern

        Returns:
            True if format is valid
        """
        normalized = self._normalize_value(value, identifier_type)

        if regex_pattern:
            return bool(re.match(regex_pattern, normalized))

        # Default patterns
        default_patterns = {
            "dni": r"^[0-9]{9}$",
            "pasaporte": r"^[A-Z]{2}[0-9]{6,7}$",
            "nif": r"^[A-Z]{0,2}[0-9]{6,10}[A-Z]?$",
        }

        pattern = default_patterns.get(identifier_type)
        if pattern:
            return bool(re.match(pattern, normalized))

        # No validation for unknown types
        return True


@lru_cache(maxsize=1)
def get_crypto_service() -> CryptoService:
    """
    Get singleton CryptoService instance.

    Uses LRU cache to ensure single instance.
    """
    return CryptoService()
