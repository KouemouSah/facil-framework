"""account_number (NIU) generation + validation — security-critical, no DB.

The NIU is a generic identifier (not a secret): login by NIU STILL requires the
password. Design rules (validated 2026-06-16):
- DEFAULT = numeric, NON-sequential (random body) + ISO 7064 Mod 97,10 check
  digits (very robust: catches all single-digit errors and adjacent
  transpositions). Random body => anti-enumeration; DB UNIQUE + bounded retry
  guarantee uniqueness at the data layer.
- check digit validated on every input (login/lookup) BEFORE any DB hit, so a
  mistyped NIU is rejected early.
- strategy locked at deploy (config-store identity.number_strategy); changing it
  only affects NEW accounts — never renumbers existing ones.
- the body carries NO PII (purely random digits).

Pure functions here; the DB-aware unique generation lives in the service.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

CHECKSUMS = ("iso7064_mod97_10", "luhn", "none")


@dataclass(frozen=True)
class NumberStrategy:
    prefix: str = ""           # optional fixed prefix (e.g. org namespace), digits only
    body_length: int = 10      # random numeric body length
    checksum: str = "iso7064_mod97_10"

    @classmethod
    def from_config(cls, cfg: dict | None) -> "NumberStrategy":
        cfg = cfg or {}
        s = cls(prefix=str(cfg.get("prefix", "")),
                body_length=int(cfg.get("body_length", 10)),
                checksum=str(cfg.get("checksum", "iso7064_mod97_10")))
        if s.checksum not in CHECKSUMS:
            raise ValueError(f"checksum must be one of {CHECKSUMS}")
        if not s.prefix.isdigit() and s.prefix != "":
            raise ValueError("prefix must be digits only (numeric NIU)")
        if s.body_length < 4:
            raise ValueError("body_length must be >= 4 (anti-enumeration)")
        return s


# --- ISO 7064 Mod 97,10 (2 check digits) ---------------------------------

def iso7064_mod97_10(payload: str) -> str:
    """2 check digits C such that int(payload + C) % 97 == 1."""
    check = 98 - (int(payload) * 100) % 97
    return f"{check:02d}"


def _valid_mod97_10(number: str) -> bool:
    return number.isdigit() and len(number) >= 3 and int(number) % 97 == 1


# --- Luhn (mod 10, 1 check digit) ----------------------------------------

def _luhn_sum(digits: str) -> int:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total


def luhn(payload: str) -> str:
    return str((10 - _luhn_sum(payload + "0") % 10) % 10)


def _valid_luhn(number: str) -> bool:
    return number.isdigit() and _luhn_sum(number) % 10 == 0


def _checksum(payload: str, kind: str) -> str:
    if kind == "iso7064_mod97_10":
        return iso7064_mod97_10(payload)
    if kind == "luhn":
        return luhn(payload)
    return ""  # none


def mint(strategy: NumberStrategy) -> str:
    """Generate ONE candidate account_number (no uniqueness check — the service
    enforces uniqueness with the DB UNIQUE constraint + retry)."""
    body = "".join(str(secrets.randbelow(10)) for _ in range(strategy.body_length))
    payload = strategy.prefix + body
    return payload + _checksum(payload, strategy.checksum)


def validate(number: str, strategy: NumberStrategy) -> bool:
    """Format + check-digit validation (no DB). Reject typos before any lookup."""
    if not number or not number.isdigit():
        return False
    if strategy.prefix and not number.startswith(strategy.prefix):
        return False
    if strategy.checksum == "iso7064_mod97_10":
        expected = len(strategy.prefix) + strategy.body_length + 2
        return len(number) == expected and _valid_mod97_10(number)
    if strategy.checksum == "luhn":
        expected = len(strategy.prefix) + strategy.body_length + 1
        return len(number) == expected and _valid_luhn(number)
    return len(number) == len(strategy.prefix) + strategy.body_length


def normalize(raw: str) -> str:
    """Canonicalize user input before lookup (strip spaces/separators)."""
    return "".join(c for c in (raw or "") if c.isdigit())
