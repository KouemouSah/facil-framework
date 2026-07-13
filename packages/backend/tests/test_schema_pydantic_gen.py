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
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {})


def test_decimal_bounds_enforced():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "vat_rate": 150})


def test_select_value_must_be_one_of_the_options():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "status": "archived"})


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
