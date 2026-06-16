"""Symmetric encryption for secrets at rest — AES-256-GCM (D4.5/B2).

Used to encrypt the TOTP shared secret in the DB (and reusable for any small
secret at rest). Authenticated encryption (GCM) gives confidentiality + integrity.

Key: derived (SHA-256 -> 32 bytes) from `TOTP_ENCRYPTION_KEY`, falling back to the
canonical `JWT_SECRET_KEY`. Deriving lets the operator supply any-length secret;
⚠️ rotating that secret makes existing ciphertexts undecryptable (re-enrol 2FA).
Token format: urlsafe-base64(nonce[12] || ciphertext||tag).
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE = 12


class DecryptionError(Exception):
    pass


def _key() -> bytes:
    raw = (os.environ.get("TOTP_ENCRYPTION_KEY")
           or os.environ.get("JWT_SECRET_KEY")
           or os.environ.get("JWT_SECRET") or "")
    if not raw:
        raise RuntimeError(
            "no encryption key: set TOTP_ENCRYPTION_KEY (or JWT_SECRET_KEY)")
    return hashlib.sha256(raw.encode("utf-8")).digest()  # 32 bytes


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(_NONCE)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(token: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        return AESGCM(_key()).decrypt(raw[:_NONCE], raw[_NONCE:], None).decode("utf-8")
    except (InvalidTag, ValueError) as e:
        raise DecryptionError("could not decrypt") from e
