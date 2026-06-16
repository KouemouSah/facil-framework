"""account_number (NIU) generation + validation — security-critical, no DB.

The NIU is a generic identifier (not a secret): login by NIU STILL requires the
password. Design (validated 2026-06-16):
- DEFAULT = numeric, NON-sequential (random body) + ISO 7064 Mod 97,10 check
  digits (catches all single-digit errors and adjacent transpositions). Random
  body => anti-enumeration; DB UNIQUE + bounded retry guarantee uniqueness.
- CATEGORY prefix (national / foreigner / entity …): a configurable fixed-length
  prefix encoded at the FRONT of the NIU so categories are visually
  distinguishable. Fixed AT ISSUANCE (the NIU is immutable); the authoritative,
  mutable status lives in Account.subject_type. All prefixes share one length.
- check digit validated on every input BEFORE any DB hit (reject typos early).
- strategy locked at deploy (config-store identity.number_strategy); changing it
  only affects NEW accounts. The body carries NO PII (purely random digits).

Pure functions here; DB-aware unique generation lives in the service.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

CHECKSUMS = ("iso7064_mod97_10", "luhn", "none")


@dataclass(frozen=True)
class NumberStrategy:
    prefix: str = ""                      # default prefix (no category)
    body_length: int = 10                 # random numeric body length
    checksum: str = "iso7064_mod97_10"
    category_prefixes: dict = field(default_factory=dict)  # {subject_type: prefix}

    @classmethod
    def from_config(cls, cfg: dict | None) -> "NumberStrategy":
        cfg = cfg or {}
        cats = {str(k): str(v) for k, v in (cfg.get("category_prefixes") or {}).items()}
        s = cls(prefix=str(cfg.get("prefix", "")),
                body_length=int(cfg.get("body_length", 10)),
                checksum=str(cfg.get("checksum", "iso7064_mod97_10")),
                category_prefixes=cats)
        if s.checksum not in CHECKSUMS:
            raise ValueError(f"checksum must be one of {CHECKSUMS}")
        for p in [s.prefix, *cats.values()]:
            if p and not p.isdigit():
                raise ValueError("prefixes must be digits only (numeric NIU)")
        # When categories are used they replace the base prefix entirely and must
        # all share one length (uniform NIU length / parseable).
        if cats:
            if len({len(v) for v in cats.values()}) != 1:
                raise ValueError("all category prefixes must have the same length")
        if s.body_length < 4:
            raise ValueError("body_length must be >= 4 (anti-enumeration)")
        return s

    def prefix_len(self) -> int:
        if self.category_prefixes:
            return len(next(iter(self.category_prefixes.values())))
        return len(self.prefix)

    def allowed_prefixes(self) -> set[str]:
        if self.category_prefixes:
            return set(self.category_prefixes.values())
        return {self.prefix}

    def prefix_for(self, category: str | None) -> str:
        if self.category_prefixes:
            if category is None:
                raise ValueError("a category is required (category_prefixes configured)")
            if category not in self.category_prefixes:
                raise ValueError(f"no NIU prefix configured for category '{category}'")
            return self.category_prefixes[category]
        return self.prefix  # no categories -> single base prefix


# --- ISO 7064 Mod 97,10 (2 check digits) ---------------------------------

def iso7064_mod97_10(payload: str) -> str:
    """2 check digits C such that int(payload + C) % 97 == 1."""
    return f"{98 - (int(payload) * 100) % 97:02d}"


def _valid_mod97_10(number: str) -> bool:
    return number.isdigit() and len(number) >= 3 and int(number) % 97 == 1


# --- Luhn (mod 10, 1 check digit) ----------------------------------------

def _luhn_sum(digits: str) -> int:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
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
    return ""


def _check_len(kind: str) -> int:
    return {"iso7064_mod97_10": 2, "luhn": 1, "none": 0}[kind]


def mint(strategy: NumberStrategy, *, category: str | None = None) -> str:
    """Generate ONE candidate NIU for a category (no uniqueness check — the
    service enforces uniqueness via the DB UNIQUE constraint + retry)."""
    prefix = strategy.prefix_for(category)
    body = "".join(str(secrets.randbelow(10)) for _ in range(strategy.body_length))
    payload = prefix + body
    return payload + _checksum(payload, strategy.checksum)


def validate(number: str, strategy: NumberStrategy) -> bool:
    """Format + prefix + check-digit validation (no DB). Reject typos early."""
    if not number or not number.isdigit():
        return False
    plen = strategy.prefix_len()
    if number[:plen] not in strategy.allowed_prefixes():
        return False
    expected = plen + strategy.body_length + _check_len(strategy.checksum)
    if len(number) != expected:
        return False
    if strategy.checksum == "iso7064_mod97_10":
        return _valid_mod97_10(number)
    if strategy.checksum == "luhn":
        return _valid_luhn(number)
    return True


def normalize(raw: str) -> str:
    """Canonicalize user input before lookup (strip spaces/separators)."""
    return "".join(c for c in (raw or "") if c.isdigit())
