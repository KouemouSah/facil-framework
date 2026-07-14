"""`organization.settings` replaces the raw-JSON admin editing with a generated
form (Task 9). Only the settings the product genuinely consumes are declared —
see `product_schemas.ORGANIZATION_SETTINGS` for why the set is deliberately
small."""

from app.core.schema.registry import default_schema_registry
from app.core.schema.spec import FieldSpec


def test_organization_settings_declares_only_fields_the_product_consumes():
    specs = default_schema_registry().get("organization.settings")
    assert {s["key"] for s in specs} == {
        "default_document_locale", "fiscal_year_start_month", "document_number_prefix",
    }
    for s in specs:
        FieldSpec.model_validate(s)


def test_fiscal_year_start_month_is_bounded():
    spec = next(s for s in default_schema_registry().get("organization.settings")
                if s["key"] == "fiscal_year_start_month")
    assert spec["type"] == "number"
    assert spec["rules"]["min"] == 1 and spec["rules"]["max"] == 12


def test_every_label_is_localised_in_three_locales():
    for s in default_schema_registry().get("organization.settings"):
        assert s["label"]["en"] and s["label"]["fr"] and s["label"]["es"]
