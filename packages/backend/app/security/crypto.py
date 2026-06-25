"""Symmetric encryption for secrets at rest — AES-256-GCM (D4.5/B2).

Used to encrypt the TOTP shared secret in the DB (and reusable for any small
secret at rest). Authenticated encryption (GCM) gives confidentiality + integrity.

Key: derived (SHA-256 -> 32 bytes) from `TOTP_ENCRYPTION_KEY`. In dev it may fall
back to the canonical `JWT_SECRET_KEY`; in PRODUCTION a distinct `TOTP_ENCRYPTION_KEY`
is REQUIRED (key separation, SEC-008) — the fallback raises. Deriving lets the
operator supply any-length secret; ⚠️ rotating that secret makes existing ciphertexts
undecryptable (re-enrol 2FA).
⚠️ UPGRADE NOTE: a prod deploy that previously encrypted TOTP secrets via the JWT
fallback (no dedicated key) must set `TOTP_ENCRYPTION_KEY` AND re-enrol TOTP users —
their old ciphertexts are not decryptable under the new key.
Token format: urlsafe-base64(nonce[12] || ciphertext||tag).
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.env_posture import is_dev

_NONCE = 12


class DecryptionError(Exception):
    pass


def _key() -> bytes:
    distinct = os.environ.get("TOTP_ENCRYPTION_KEY")
    if distinct:
        return hashlib.sha256(distinct.encode("utf-8")).digest()  # 32 bytes
    # Fallback to the JWT signing secret — convenient in dev, but reusing one
    # secret across signing AND at-rest encryption breaks cryptographic domain
    # separation (a JWT-secret leak/rotation then also compromises 2FA at rest).
    # Refuse it in production (SEC-008).
    fallback = os.environ.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET") or ""
    if not fallback:
        raise RuntimeError(
            "no encryption key: set TOTP_ENCRYPTION_KEY (or JWT_SECRET_KEY)")
    if not is_dev(os.environ):
        raise RuntimeError(
            "TOTP_ENCRYPTION_KEY is required in production — refusing to reuse the "
            "JWT signing secret for at-rest encryption (cryptographic key separation).")
    return hashlib.sha256(fallback.encode("utf-8")).digest()  # 32 bytes


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
