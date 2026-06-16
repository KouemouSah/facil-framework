"""Password hashing (bcrypt) + strength policy.

bcrypt only considers the first 72 bytes — we truncate explicitly so a long
password never raises and the hash/verify pair stays consistent.
"""

from __future__ import annotations

import bcrypt

_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def check_strength(password: str) -> tuple[bool, str]:
    """Returns (ok, reason). Min 8 chars + upper + lower + digit."""
    if password is None or len(password) < 8:
        return False, "password must be at least 8 characters"
    if not any(c.islower() for c in password):
        return False, "password must contain a lowercase letter"
    if not any(c.isupper() for c in password):
        return False, "password must contain an uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "password must contain a digit"
    return True, ""
