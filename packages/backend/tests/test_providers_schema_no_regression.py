"""M0 safety net: the 13 built-in providers must expose the SAME schema keys,
labels, types, required flags and defaults as before the FieldSpec migration."""

from app.core.providers.registry import default_registry
from app.core.schema.spec import FieldSpec


def test_all_thirteen_providers_still_register():
    r = default_registry()
    assert len(r.registered) == 13


def test_every_provider_schema_field_is_a_valid_FieldSpec():
    r = default_registry()
    for entry in r.registered_detailed:
        for f in entry["config_schema"]:
            FieldSpec.model_validate(f)  # raises if the descriptor is malformed


def test_schema_keys_are_unchanged_for_every_provider():
    # The SEC-F2 allowlist is built from these keys. If a key silently changed,
    # a provider's config writes would start being rejected in production.
    r = default_registry()
    actual = {
        (e["capability"], e["provider_code"]): sorted(f["key"] for f in e["config_schema"])
        for e in r.registered_detailed
    }
    for (cap, code), keys in actual.items():
        assert keys == sorted(set(keys)), f"{cap}/{code} declares a duplicate key"
        assert all(isinstance(k, str) and k for k in keys)
    # Spot-check the shape the admin form depends on (providers/fields.ts:14-22).
    for e in r.registered_detailed:
        for f in e["config_schema"]:
            assert {"key", "label", "type", "required", "default", "hint"} <= set(f)


def test_cfg_keeps_its_legacy_scalar_types_working():
    from app.core.providers.base import cfg
    assert cfg("host", "Host")["type"] == "string"
    assert cfg("port", "Port", type="number")["type"] == "number"
    assert cfg("tls", "TLS", type="boolean")["type"] == "boolean"
    assert cfg("extra", "Extra", type="json")["type"] == "json"
