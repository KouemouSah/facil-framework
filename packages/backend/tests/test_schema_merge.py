"""Merge, never replace. Historic keys nobody ever validated must survive."""

import pytest

from app.core.schema.merge import merge_blob
from app.core.schema.pydantic_gen import SchemaViolation
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}
SPECS = [field("legal_name", L), field("footer_note", L, type="text")]


def test_declared_keys_are_written():
    out = merge_blob({}, {"legal_name": "Acme"}, SPECS)
    assert out == {"legal_name": "Acme"}


def test_undeclared_pre_existing_key_is_preserved_untouched():
    # `seal_ref` predates the schema. Dropping it would destroy production data.
    existing = {"legal_name": "Old", "seal_ref": "SEAL-77"}
    out = merge_blob(existing, {"legal_name": "Acme"}, SPECS)
    assert out == {"legal_name": "Acme", "seal_ref": "SEAL-77"}


def test_undeclared_key_in_the_REQUEST_is_rejected():
    # Strict on input, tolerant on what's already stored.
    with pytest.raises(SchemaViolation):
        merge_blob({}, {"legal_name": "Acme", "injected": "x"}, SPECS)


def test_clearing_a_declared_key_removes_it_but_keeps_the_undeclared_ones():
    existing = {"legal_name": "Old", "footer_note": "n", "seal_ref": "SEAL-77"}
    out = merge_blob(existing, {"legal_name": "Acme", "footer_note": ""}, SPECS)
    assert out == {"legal_name": "Acme", "seal_ref": "SEAL-77"}
