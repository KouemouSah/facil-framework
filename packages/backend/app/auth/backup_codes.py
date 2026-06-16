"""One-time TOTP backup codes (D4.5/B2).

Generated when 2FA is enabled, shown to the user ONCE, stored only as SHA-256
hashes. Each code is single-use (consumed on a successful login). Format
`NNNN-NNNN` (8 digits) for easy manual entry.
"""

from __future__ import annotations

import hashlib
import secrets

COUNT = 10


def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate(n: int = COUNT) -> tuple[list[str], list[str]]:
    """Return (plaintext codes to show once, hashes to store)."""
    codes = [f"{secrets.randbelow(10000):04d}-{secrets.randbelow(10000):04d}"
             for _ in range(n)]
    return codes, [_hash(c) for c in codes]


def verify_and_consume(stored: list[str], code: str) -> tuple[bool, list[str]]:
    """If `code` matches a stored hash, return (True, remaining-hashes); else
    (False, unchanged)."""
    h = _hash(code)
    if h in (stored or []):
        return True, [c for c in stored if c != h]
    return False, stored or []
