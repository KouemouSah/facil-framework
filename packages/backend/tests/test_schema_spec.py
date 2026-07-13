"""FieldSpec validates the descriptor itself — fail fast, at import time."""

import pytest

from app.core.schema.spec import FieldSpec, field


def test_field_returns_a_plain_dict_with_the_default_widget_filled_in():
    f = field("legal_name", {"en": "Legal name", "fr": "Raison sociale",
                             "es": "Razón social"})
    assert f["key"] == "legal_name"
    assert f["type"] == "string"
    assert f["widget"] == "plain"          # DEFAULT_WIDGET["string"]
    assert f["label"]["fr"] == "Raison sociale"


def test_legacy_type_alias_is_expanded_to_type_plus_widget():
    f = field("primary_color", {"en": "Colour", "fr": "Couleur", "es": "Color"},
              type="color")
    assert f["type"] == "string" and f["widget"] == "color"


def test_unknown_type_is_refused():
    with pytest.raises(ValueError, match="unknown field type"):
        field("x", {"en": "X", "fr": "X", "es": "X"}, type="quantum")


def test_widget_must_belong_to_the_type():
    with pytest.raises(ValueError, match="widget 'rating' is not valid for type 'string'"):
        field("x", {"en": "X", "fr": "X", "es": "X"}, type="string", widget="rating")


def test_key_must_be_snake_case_and_bounded():
    with pytest.raises(ValueError, match="key"):
        field("Bad-Key", {"en": "X", "fr": "X", "es": "X"})
    with pytest.raises(ValueError, match="key"):
        field("a" * 61, {"en": "X", "fr": "X", "es": "X"})


def test_label_requires_all_three_locales():
    # Repo rule: every user-visible string is an en/fr/es key. A field whose
    # label is monolingual would ship an untranslatable form.
    with pytest.raises(ValueError, match="label must provide en, fr and es"):
        field("x", {"en": "X"})


def test_indexed_is_refused_on_a_non_indexable_type():
    with pytest.raises(ValueError, match="type 'json' cannot be indexed"):
        field("payload", {"en": "P", "fr": "P", "es": "P"}, type="json", indexed=True)


def test_select_requires_options():
    with pytest.raises(ValueError, match="select requires options"):
        field("status", {"en": "S", "fr": "S", "es": "S"}, type="select")


def test_relation_requires_a_resource():
    with pytest.raises(ValueError, match="relation requires relation_resource"):
        field("country", {"en": "C", "fr": "C", "es": "C"}, type="relation")


def test_visible_if_must_reference_a_known_operator():
    with pytest.raises(ValueError, match="visible_if.op"):
        field("vat", {"en": "V", "fr": "V", "es": "V"},
              rules={"visible_if": {"field": "taxable", "op": "matches", "value": True}})


def test_spec_roundtrips_through_the_model():
    f = field("amount", {"en": "Amount", "fr": "Montant", "es": "Importe"},
              type="money", indexed=True, group="billing", order=3)
    spec = FieldSpec.model_validate(f)
    assert spec.type == "money" and spec.indexed is True and spec.order == 3
