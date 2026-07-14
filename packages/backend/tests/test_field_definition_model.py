import pytest
from sqlalchemy import inspect

from app.core.schema.spec import FieldSpec
from app.models.field_definition import FieldDefinition
from app.modules.location.models import Site
from app.modules.organization.models import Organization, OrgUnit


def test_organization_id_is_not_nullable():
    # The formal statement of tenant isolation: no row may exist "above" an org.
    col = inspect(FieldDefinition).columns["organization_id"]
    assert col.nullable is False


def test_unique_on_org_target_key():
    # Verify both the constraint name AND its column set.
    for constraint in FieldDefinition.__table__.constraints:
        if constraint.__class__.__name__ == "UniqueConstraint" and constraint.name == "uq_field_definition_org_target_key":
            col_names = {col.name for col in constraint.columns}
            assert col_names == {"organization_id", "target", "key"}, \
                f"Expected columns {{organization_id, target, key}}, got {col_names}"
            return
    raise AssertionError("Constraint 'uq_field_definition_org_target_key' not found")


def test_every_extensible_entity_has_a_custom_fields_column():
    for model in (Organization, OrgUnit, Site):
        assert "custom_fields" in inspect(model).columns, f"{model.__name__} lacks custom_fields"


def test_as_spec_produces_a_valid_FieldSpec():
    fd = FieldDefinition(
        organization_id="org-1", target="site.custom_fields", key="convention_no",
        type="string", widget="plain",
        label_en="Convention no.", label_fr="N° de convention", label_es="N.º de convenio",
        required=False, rules={}, options=[], group="extra", order=1, col_span=1,
        indexed=False, index_state="none", archived=False, inherit_to_suborgs=False)
    spec = FieldSpec.model_validate(fd.as_spec())
    assert spec.key == "convention_no"
    assert spec.label["fr"] == "N° de convention"


def test_as_spec_is_valid_on_unflushed_object_with_only_required_fields():
    # SQLAlchemy column defaults fire at FLUSH, not __init__. A "validate before
    # persist" caller sees None in every implicit column — as_spec() must coalesce.
    fd = FieldDefinition(organization_id="org-1", target="site.custom_fields",
                         key="convention_no",
                         label_en="X", label_fr="X", label_es="X")
    spec = FieldSpec.model_validate(fd.as_spec())
    assert spec.type == "string"
    assert spec.widget == "plain"
    assert spec.indexed is False
    assert spec.index_state == "none"
    assert spec.required is False
    assert spec.col_span == 1
    assert spec.order == 0
    assert spec.group == ""


def test_fields_manage_permission_is_registered():
    from app.rbac.permissions import collect_permissions
    codes = {p["code"] for p in collect_permissions()}
    assert "fields.manage" in codes
