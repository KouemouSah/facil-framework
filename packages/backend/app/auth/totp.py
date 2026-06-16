"""TOTP (2FA) utilities — RFC 6238 via pyotp.

The provisioning-URI issuer is configurable (branding-driven, not hard-coded to
"TaxasGE" like the legacy) so each deployment brands its authenticator entry.
"""

from __future__ import annotations

import pyotp


def generate_secret() -> str:
    return pyotp.random_base32()


def verify_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=valid_window)
    except Exception:  # noqa: BLE001 — malformed secret/code -> not verified
        return False


def provisioning_uri(secret: str, account_name: str, *, issuer: str = "Facil") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)
