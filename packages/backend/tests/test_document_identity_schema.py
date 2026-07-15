"""The product schema that unblocks SP2 (document header/footer per entity)."""

from app.core.schema.registry import default_schema_registry
from app.core.schema.spec import FieldSpec


def test_document_identity_is_registered_and_flat():
    r = default_schema_registry()
    specs = r.get("organization.document_identity")
    assert specs, "document_identity must be registered"
    keys = {s["key"] for s in specs}
    assert keys == {
        "short_code", "seal_url", "header_note", "footer_note",
        "legal_mentions", "contact_line",
    }
    for s in specs:
        FieldSpec.model_validate(s)
        assert s["type"] != "json", "document_identity must be FLAT — no nested blob"


def test_every_label_is_localised_in_three_locales():
    for s in default_schema_registry().get("organization.document_identity"):
        assert s["label"]["en"] and s["label"]["fr"] and s["label"]["es"]


def test_legal_identity_keys_are_deliberately_absent_sp1_d1():
    # `legal_name`, `tax_id`, `registration_number` and `logo_url` live as REAL
    # COLUMNS on `Organization` (app/modules/organization/models.py). SP1 D1
    # found these four re-declared here too — an admin typed the legal name
    # once on the Details tab and again on this schema, and the two values
    # WILL diverge (fix it in Details, the document keeps printing the old
    # one). `Organization` is now the single source of truth for legal
    # identity; this schema only carries what is document-specific. Do not
    # re-add them — read the resolved identity via
    # `core.schema.issuer.resolve_issuer_identity` instead.
    keys = {s["key"] for s in default_schema_registry().get("organization.document_identity")}
    assert keys.isdisjoint({"legal_name", "tax_id", "registration_number", "logo_url"})


def test_org_unit_and_site_overrides_are_registered_and_optional():
    # SP1 D1 value inheritance: a child OrgUnit/Site MAY override a NARROW
    # subset going down the hierarchy — an organisation never overrides its
    # own name (meaningless), so `tax_id`/`registration_number` (legal/fiscal
    # identifiers) and `seal_url`/`header_note`/`legal_mentions`
    # (organisation-wide legal text) are NOT overridable here.
    for target in ("org_unit.document_identity", "site.document_identity"):
        specs = default_schema_registry().get(target)
        assert specs, f"{target} must be registered"
        keys = {s["key"] for s in specs}
        assert keys == {"legal_name", "short_code", "logo_url", "contact_line", "footer_note"}
        for s in specs:
            FieldSpec.model_validate(s)
            assert s["required"] is False, (
                f"{target}.{s['key']} must not be required — it is an OPTIONAL "
                f"override, an empty value must fall back to the parent")
