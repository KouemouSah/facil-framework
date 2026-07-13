"""The product schema that unblocks SP2 (document header/footer per entity)."""

from app.core.schema.registry import default_schema_registry
from app.core.schema.spec import FieldSpec


def test_document_identity_is_registered_and_flat():
    r = default_schema_registry()
    specs = r.get("organization.document_identity")
    assert specs, "document_identity must be registered"
    keys = {s["key"] for s in specs}
    assert keys == {
        "legal_name", "short_code", "logo_url", "seal_url", "header_note",
        "footer_note", "legal_mentions", "tax_id", "registration_number",
        "contact_line",
    }
    for s in specs:
        FieldSpec.model_validate(s)
        assert s["type"] != "json", "document_identity must be FLAT — no nested blob"


def test_every_label_is_localised_in_three_locales():
    for s in default_schema_registry().get("organization.document_identity"):
        assert s["label"]["en"] and s["label"]["fr"] and s["label"]["es"]
