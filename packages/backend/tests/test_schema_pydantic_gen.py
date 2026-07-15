"""Server-side validation generated from the descriptor. The server decides."""

import pytest

from app.core.schema.pydantic_gen import SchemaViolation, validate_blob
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}

SPECS = [
    field("legal_name", L, required=True, rules={"max_length": 200}),
    field("vat_rate", L, type="decimal", rules={"min": 0, "max": 100}),
    field("taxable", L, type="boolean"),
    field("vat_no", L, rules={"required_if": {"field": "taxable", "op": "eq",
                                              "value": True},
                              "visible_if": {"field": "taxable", "op": "eq",
                                             "value": True}}),
    field("amount", L, type="money"),
    field("opened_on", L, type="date"),
    field("status", L, type="select",
          options=[{"value": "draft", "label": L}, {"value": "live", "label": L}]),
]


def test_unknown_key_is_rejected_not_ignored():
    # Silent drop = the exact failure mode the repo's anti-silent-failure rule
    # forbids. The client must learn its key was refused.
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "sneaky": "x"})
    assert e.value.errors[0]["loc"] == ["sneaky"]
    assert "not declared" in e.value.errors[0]["msg"]


def test_required_field_missing_is_rejected():
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {})
    assert e.value.errors[0]["loc"] == ["legal_name"]
    assert "required" in e.value.errors[0]["msg"]


def test_decimal_bounds_enforced():
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "vat_rate": 150})
    assert e.value.errors[0]["loc"] == ["vat_rate"]
    assert "≤ 100" in e.value.errors[0]["msg"]


def test_select_value_must_be_one_of_the_options():
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "status": "archived"})
    assert e.value.errors[0]["loc"] == ["status"]
    assert "must be one of" in e.value.errors[0]["msg"]


def test_money_must_be_amount_plus_currency_with_a_string_amount():
    # A float amount would silently round money. Refused.
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme",
                              "amount": {"amount": 12.30, "currency": "XAF"}})
    ok = validate_blob(SPECS, {"legal_name": "Acme",
                               "amount": {"amount": "12.30", "currency": "XAF"}})
    assert ok["amount"] == {"amount": "12.30", "currency": "XAF"}


def test_date_must_be_iso():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "opened_on": "13/07/2026"})
    ok = validate_blob(SPECS, {"legal_name": "Acme", "opened_on": "2026-07-13"})
    assert ok["opened_on"] == "2026-07-13"


def test_required_if_true_and_field_absent_is_rejected():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "taxable": True})


def test_hidden_field_may_be_omitted_even_though_required_if_fires_when_visible():
    # taxable=False → vat_no is neither visible nor required. Omitting it is OK.
    ok = validate_blob(SPECS, {"legal_name": "Acme", "taxable": False})
    assert "vat_no" not in ok


def test_sending_a_hidden_field_is_rejected():
    # THE bypass this guard exists for: a client that hides a field client-side
    # but posts it anyway must be refused by the server.
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "taxable": False,
                              "vat_no": "GQ123"})
    assert "not visible" in e.value.errors[0]["msg"]


# --- Fix 1: "" / None on a declared, visible, optional field is the CLEAR
# sentinel, not a silent drop. ---------------------------------------------

def test_empty_string_clears_a_declared_optional_field():
    # "" / None is the CLEAR sentinel (RecordForm.buildPayload sends null to
    # empty a field). The key is deliberately absent from `clean` so that
    # merge_blob removes it from the stored blob. Not a silent drop.
    out = validate_blob(SPECS, {"legal_name": "Acme", "vat_rate": ""})
    assert "vat_rate" not in out
    assert out["legal_name"] == "Acme"


def test_none_clears_a_declared_optional_field():
    out = validate_blob(SPECS, {"legal_name": "Acme", "vat_rate": None})
    assert "vat_rate" not in out


def test_empty_value_on_a_REQUIRED_visible_field_is_still_rejected():
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": ""})
    assert e.value.errors[0]["loc"] == ["legal_name"]


def test_falsy_but_legitimate_values_survive():
    # `0` and `False` must NOT be mistaken for the clear sentinel.
    specs = [*SPECS, field("rank", L, type="number"), field("active", L, type="boolean")]
    out = validate_blob(specs, {"legal_name": "Acme", "rank": 0, "active": False})
    assert out["rank"] == 0
    assert out["active"] is False


# --- Fix 2: `number` is an integer type; non-integral input is rejected,
# not silently stringified. `decimal` keeps returning a decimal string. ----

def test_number_rejects_a_non_integral_value():
    specs = [*SPECS, field("rank", L, type="number")]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"legal_name": "Acme", "rank": 3.7})
    assert e.value.errors[0]["loc"] == ["rank"]
    assert "whole number" in e.value.errors[0]["msg"]


def test_number_returns_an_int_and_decimal_returns_a_decimal_string():
    specs = [*SPECS, field("rank", L, type="number")]
    out = validate_blob(specs, {"legal_name": "Acme", "rank": 7, "vat_rate": "19.60"})
    assert out["rank"] == 7 and isinstance(out["rank"], int)
    assert out["vat_rate"] == "19.60" and isinstance(out["vat_rate"], str)


# --- Fix 3: one 422, not two round trips — errors accumulate in one pass. -

def test_all_errors_are_reported_in_one_pass():
    # ERP standard: 422 maps onto fields in ONE round trip, not two.
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"sneaky": "x"})          # unknown key AND legal_name missing
    locs = {tuple(err["loc"]) for err in e.value.errors}
    assert ("sneaky",) in locs
    assert ("legal_name",) in locs


# --- Task 1: number/decimal `step`, decimal `precision`, money `min`/`max`. -

def test_number_step_multiple_enforced():
    specs = [field("qty", L, type="number", rules={"step": 5})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"qty": 7})
    assert e.value.errors[0]["loc"] == ["qty"]
    assert "multiple of 5" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"qty": 10}) == {"qty": 10}


def test_decimal_precision_enforced():
    specs = [field("rate", L, type="decimal", rules={"precision": 2})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"rate": "1.234"})
    assert "at most 2 decimal places" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"rate": "1.23"}) == {"rate": "1.23"}


def test_money_amount_bounds_enforced():
    specs = [field("price", L, type="money", rules={"min": 10, "max": 100})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"price": {"amount": "5.00", "currency": "usd"}})
    assert e.value.errors[0]["loc"] == ["price"]
    assert "≥ 10" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"price": {"amount": "50.00", "currency": "usd"}}) \
        == {"price": {"amount": "50.00", "currency": "USD"}}
