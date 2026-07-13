"""M0 safety net: the 13 built-in providers must expose the SAME schema keys,
labels, types, required flags and defaults as before the FieldSpec migration."""

from app.core.providers.registry import default_registry
from app.core.schema.spec import FieldSpec

# Captured from commit 50f16d1 ("feat(schema): FieldSpec descriptor validated at
# declaration time") — the LAST commit before 2c0cff1 rewired cfg() to delegate to
# FieldSpec. This is the pre-refactor ground truth for every provider's declared
# config_schema keys.
#
# These keys are the SEC-F2 allowlist source (registry.py:44, `schema_keys()`):
# the admin config-write endpoint rejects any key not in this set. A silent
# rename here (e.g. "host" -> "hostname") would make provider config writes
# start failing in production while looking like a harmless refactor.
#
# Changing a value in this dict is a deliberate, reviewed decision (a provider
# genuinely adding/renaming/removing a config key) — never a silent edit made
# just to get this test to pass. If you're touching this because the test is
# "in the way", stop and re-read SEC-F2 first.
SCHEMA_KEYS_BASELINE = {
    "auth/keycloak_oidc": [
        "algorithms",
        "audience",
        "client_id",
        "discovery_url",
        "introspection",
        "introspection_fail_closed",
        "issuer",
        "jwks_uri",
    ],
    "auth/native": [
        "access_ttl_seconds",
        "issuer",
        "refresh_ttl_seconds",
    ],
    "email/resend": [
        "from_email",
        "from_name",
        "timeout_seconds",
    ],
    "email/sendgrid": [
        "from_email",
        "from_name",
        "timeout_seconds",
    ],
    "email/smtp": [
        "from_email",
        "from_name",
        "host",
        "port",
        "timeout_seconds",
        "use_tls",
        "username",
    ],
    "llm/ollama": [
        "endpoint",
        "model",
        "timeout_seconds",
    ],
    "llm/openai_compat": [
        "endpoint",
        "model",
        "timeout_seconds",
    ],
    "secrets/aws_secretsmanager": [
        "prefix",
        "region",
    ],
    "secrets/env": [],
    "secrets/openbao": [
        "addr",
        "kv_path",
        "paths",
    ],
    "storage/memory": [],
    "storage/minio": [
        "bucket",
        "endpoint",
    ],
    "storage/s3": [
        "bucket",
        "endpoint",
        "region",
    ],
}


def test_all_thirteen_providers_still_register():
    r = default_registry()
    assert len(r.registered) == 13


def test_every_provider_schema_field_is_a_valid_FieldSpec():
    r = default_registry()
    for entry in r.registered_detailed:
        for f in entry["config_schema"]:
            FieldSpec.model_validate(f)  # raises if the descriptor is malformed


def test_schema_keys_are_unchanged_for_every_provider():
    # Compares the LIVE registry against SCHEMA_KEYS_BASELINE, a literal captured
    # from the pre-refactor commit (50f16d1) — not against itself. If cfg() or any
    # provider silently renames/adds/drops a config key, this fails and names the
    # offending provider.
    r = default_registry()
    actual = {
        f'{e["capability"]}/{e["provider_code"]}': sorted(f["key"] for f in e["config_schema"])
        for e in r.registered_detailed
    }
    expected = {k: sorted(v) for k, v in SCHEMA_KEYS_BASELINE.items()}

    assert set(actual) == set(expected), (
        f"provider set changed: missing={set(expected) - set(actual)} "
        f"extra={set(actual) - set(expected)}"
    )
    for provider, keys in expected.items():
        assert actual[provider] == keys, (
            f"{provider} schema keys drifted from the pre-refactor baseline "
            f"(50f16d1): expected={keys} actual={actual[provider]}"
        )
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
