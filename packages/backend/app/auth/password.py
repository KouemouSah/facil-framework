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


# Common base words to reject (NIST 800-63B: screen against common/expected
# passwords). Compared against the password's alphabetic core (digits/symbols
# stripped) so trivial decorations ("Password1234", "P@ssw0rd!") are caught too.
_COMMON_BASES = {
    "password", "passwort", "motdepasse", "contrasena", "qwerty", "azerty",
    "qwertyuiop", "admin", "administrator", "welcome", "letmein", "iloveyou",
    "monkey", "dragon", "football", "baseball", "abcdef", "abcdefg", "secret",
    "master", "superman", "trustno", "sunshine", "princess", "facil", "changeme",
}


def check_strength(password: str) -> tuple[bool, str]:
    """Returns (ok, reason). Min 12 chars + upper + lower + digit + not a common
    password (NIST 800-63B screening)."""
    if password is None or len(password) < 12:
        return False, "password must be at least 12 characters"
    if not any(c.islower() for c in password):
        return False, "password must contain a lowercase letter"
    if not any(c.isupper() for c in password):
        return False, "password must contain an uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "password must contain a digit"
    core = "".join(c for c in password.lower() if c.isalpha())
    if core in _COMMON_BASES:
        return False, "password is too common — choose a less predictable one"
    return True, ""
