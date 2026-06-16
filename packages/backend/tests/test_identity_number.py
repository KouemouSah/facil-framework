"""account_number (NIU) generation + check-digit validation (D4.1, security)."""

from __future__ import annotations

import pytest

from app.identity import number as num
from app.identity.number import NumberStrategy


def test_default_strategy_is_numeric_mod97():
    s = NumberStrategy()
    assert s.checksum == "iso7064_mod97_10" and s.body_length == 10 and s.prefix == ""


def test_mint_is_valid_and_numeric():
    s = NumberStrategy()
    for _ in range(50):
        n = num.mint(s)
        assert n.isdigit()
        assert len(n) == s.body_length + 2  # body + 2 check digits
        assert num.validate(n, s) is True
        assert int(n) % 97 == 1  # ISO 7064 Mod 97,10 invariant


def test_mint_with_prefix():
    s = NumberStrategy(prefix="240", body_length=8)
    n = num.mint(s)
    assert n.startswith("240") and len(n) == 3 + 8 + 2 and num.validate(n, s)


def test_single_digit_typo_is_rejected():
    """Mod 97,10 catches ALL single-digit errors (the whole point)."""
    s = NumberStrategy()
    n = num.mint(s)
    for i in range(len(n)):
        for d in "0123456789":
            if d != n[i]:
                typo = n[:i] + d + n[i + 1:]
                assert num.validate(typo, s) is False, f"missed typo at {i}: {typo}"


def test_adjacent_transposition_rejected():
    s = NumberStrategy()
    # build a number where two adjacent digits differ, swap them, expect invalid
    for _ in range(50):
        n = num.mint(s)
        for i in range(len(n) - 1):
            if n[i] != n[i + 1]:
                swapped = n[:i] + n[i + 1] + n[i] + n[i + 2:]
                assert num.validate(swapped, s) is False
                break


def test_luhn_strategy():
    s = NumberStrategy(checksum="luhn", body_length=9)
    n = num.mint(s)
    assert len(n) == 9 + 1 and num.validate(n, s)
    assert num._luhn_sum(n) % 10 == 0
    # flip last check digit -> invalid
    bad = n[:-1] + str((int(n[-1]) + 1) % 10)
    assert num.validate(bad, s) is False


def test_validate_rejects_garbage():
    s = NumberStrategy()
    assert num.validate("", s) is False
    assert num.validate("12ab34", s) is False
    assert num.validate("123", s) is False           # wrong length
    n = num.mint(NumberStrategy(prefix="99", body_length=10))
    assert num.validate(n, s) is False               # prefix/length mismatch


def test_normalize_strips_separators():
    assert num.normalize(" 12 34-56 ") == "123456"
    assert num.normalize(None) == ""


def test_from_config_validation():
    assert NumberStrategy.from_config({"checksum": "luhn", "body_length": 6}).checksum == "luhn"
    with pytest.raises(ValueError):
        NumberStrategy.from_config({"checksum": "sha256"})   # unknown
    with pytest.raises(ValueError):
        NumberStrategy.from_config({"body_length": 2})        # too short
    with pytest.raises(ValueError):
        NumberStrategy.from_config({"prefix": "AB"})          # non-numeric prefix


# --- category prefixes (national / foreigner / entity) -------------------

_CATS = {"category_prefixes": {"national": "1", "foreigner": "2", "entity": "9"}}


def test_category_prefix_distinguishes_and_validates():
    s = NumberStrategy.from_config({**_CATS, "body_length": 8})
    nat = num.mint(s, category="national")
    fgn = num.mint(s, category="foreigner")
    assert nat.startswith("1") and fgn.startswith("2")
    assert num.validate(nat, s) and num.validate(fgn, s)
    assert len(nat) == 1 + 8 + 2 == len(fgn)  # uniform length


def test_category_required_when_configured():
    s = NumberStrategy.from_config(_CATS)
    with pytest.raises(ValueError):
        num.mint(s, category=None)            # category mandatory
    with pytest.raises(ValueError):
        num.mint(s, category="alien")         # unknown category


def test_validate_rejects_unknown_category_prefix():
    s = NumberStrategy.from_config({**_CATS, "body_length": 8})
    n = num.mint(s, category="national")
    foreign_prefix = "7" + n[1:]              # prefix not in the configured set
    assert num.validate(foreign_prefix, s) is False


def test_category_prefixes_must_share_length():
    with pytest.raises(ValueError):
        NumberStrategy.from_config({"category_prefixes": {"a": "1", "b": "22"}})
