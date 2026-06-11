"""Tests for deploy/scripts/validate_config.py.

Run from repo root:
    pytest deploy/scripts/test_validate_config.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Ensure the validator module is importable when pytest runs from repo root.
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_valid_config() -> dict:
    """The bare minimum required to pass validation."""
    return {
        "meta": {
            "config_version": 1,
            "project_name": "facil",
            "environment": "production",
            "version": "latest",
        },
        "database": {
            "url_secret": "facil-database-url",
        },
        "redis": {
            "url_secret": "facil-redis-url",
        },
        "auth": {
            "jwt_secret_name": "facil-jwt",
            "app_secret_name": "facil-app",
            "totp_encryption_secret": "facil-totp",
        },
        "firebase": {
            "project_id": "facil-prod",
            "storage_bucket": "facil-prod-uploads",
        },
        "ai": {
            "gemini_api_key_secret": "facil-gemini-api-key",
        },
        "server": {
            "frontend_url": "https://facil.gq",
            "api_base_url": "https://api.facil.gq",
        },
        "cron": {
            "secret_name": "facil-cron-secret",
        },
    }


@pytest.fixture
def example_yaml_path() -> Path:
    """Path to deploy/config.example.yaml in the repo."""
    return Path(__file__).resolve().parents[1] / "config.example.yaml"


# ---------------------------------------------------------------------------
# Schema validation — happy paths
# ---------------------------------------------------------------------------

class TestMinimalValid:
    def test_minimal_config_passes(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.meta.project_name == "facil"
        assert cfg.meta.environment == "production"

    def test_defaults_are_applied(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.auth.access_token_minutes == 30
        assert cfg.redis.cache_ttl_seconds == 3600
        assert cfg.features.scheduler_enabled is True
        assert cfg.features.executive_tools is False


class TestExampleYaml:
    """The shipped example must be valid (with empty REQUIRED fields filled)."""

    def test_example_yaml_loads(self, example_yaml_path: Path) -> None:
        assert example_yaml_path.exists(), \
            f"config.example.yaml missing at {example_yaml_path}"
        with example_yaml_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert raw is not None
        # The example has empty placeholders; we must NOT pass it as-is.
        # We only check it parses.

    def test_example_with_placeholders_filled_passes(
        self, example_yaml_path: Path
    ) -> None:
        with example_yaml_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        # Fill in the [REQUIRED] placeholders with dummy values.
        raw["firebase"]["project_id"] = "facil-prod"
        raw["firebase"]["storage_bucket"] = "facil-prod-uploads"
        raw["server"]["frontend_url"] = "https://facil.gq"
        raw["server"]["api_base_url"] = "https://api.facil.gq"
        # ai requires either gemini_api_key_secret OR google_cloud_project.
        raw["ai"]["google_cloud_project"] = "facil-prod"
        cfg = vc.DeployConfig.model_validate(raw)
        assert cfg.meta.project_name == "facil"


# ---------------------------------------------------------------------------
# Schema validation — failure paths
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_missing_meta_fails(self, minimal_valid_config: dict) -> None:
        del minimal_valid_config["meta"]
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_invalid_environment_fails(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["meta"]["environment"] = "preprod"
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_database_url_or_parts_required(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["database"] = {}  # Neither url_secret nor host/name/user.
        with pytest.raises(Exception, match="url_secret"):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_database_parts_alone_pass(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["database"] = {
            "host": "127.0.0.1",
            "name": "facil",
            "user": "facil_app",
            "password_secret": "facil-db-password",
        }
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.database.host == "127.0.0.1"

    def test_ai_requires_gemini_key_or_gcp_project(
        self, minimal_valid_config: dict
    ) -> None:
        minimal_valid_config["ai"] = {}
        with pytest.raises(Exception, match="gemini_api_key_secret"):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_url_must_be_http(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["server"]["frontend_url"] = "facil.gq"
        with pytest.raises(Exception, match="http"):
            vc.DeployConfig.model_validate(minimal_valid_config)


class TestRangeValidators:
    @pytest.mark.parametrize("port", [0, 65536, -1, 99999])
    def test_invalid_port_rejected(
        self, minimal_valid_config: dict, port: int
    ) -> None:
        minimal_valid_config["server"] = {
            **minimal_valid_config.get("server", {}),
            "port": port,
            "frontend_url": "https://facil.gq",
            "api_base_url": "https://api.facil.gq",
        }
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    @pytest.mark.parametrize("temperature", [-0.1, 2.5, 100.0])
    def test_invalid_ai_temperature_rejected(
        self, minimal_valid_config: dict, temperature: float
    ) -> None:
        minimal_valid_config["ai"]["generation"] = {"temperature": temperature}
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_negative_token_count_rejected(
        self, minimal_valid_config: dict
    ) -> None:
        minimal_valid_config["auth"]["access_token_minutes"] = -1
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestCollectSecretReferences:
    def test_returns_sorted_unique(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        secrets = vc.collect_secret_references(cfg)
        assert "facil-database-url" in secrets
        assert "facil-redis-url" in secrets
        assert "facil-jwt" in secrets
        assert "facil-app" in secrets
        assert "facil-totp" in secrets
        assert "facil-gemini-api-key" in secrets
        assert "facil-cron-secret" in secrets
        # Sorted, unique.
        assert secrets == sorted(set(secrets))

    def test_empty_secret_refs_excluded(
        self, minimal_valid_config: dict
    ) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        secrets = vc.collect_secret_references(cfg)
        # We didn't set firebase.service_account_secret → must NOT appear.
        assert "" not in secrets
        assert all(s for s in secrets)


class TestProviderRequiredFields:
    def test_gcp_requires_project_id(
        self, minimal_valid_config: dict
    ) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        missing = vc.provider_required_fields(cfg, "gcp")
        assert "gcp.project_id" in missing

    def test_gcp_with_project_id_passes(
        self, minimal_valid_config: dict
    ) -> None:
        minimal_valid_config["gcp"] = {"project_id": "facil-prod"}
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert vc.provider_required_fields(cfg, "gcp") == []

    def test_docker_local_has_no_extra_requirements(
        self, minimal_valid_config: dict
    ) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert vc.provider_required_fields(cfg, "docker-local") == []


# ---------------------------------------------------------------------------
# New seams: observability (P14) / edge (Caddy) / auth provider (P11)
# ---------------------------------------------------------------------------

class TestObservabilitySeam:
    def test_defaults_are_disabled_and_sovereign_ready(
        self, minimal_valid_config: dict
    ) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        o = cfg.observability
        # Default OFF => zero behaviour change for existing cloud configs.
        assert o.mode == "disabled"
        assert o.errors_backend == "none"
        assert o.session_replay == "none"
        # Dev-local tier defaults (P14 palier A).
        assert o.grafana_port == 3001          # 3000 reserved for frontend
        assert o.otlp_grpc_port == 4317
        assert o.otel_lgtm_image.startswith("grafana/otel-lgtm")

    def test_existing_saas_fields_preserved(
        self, minimal_valid_config: dict
    ) -> None:
        minimal_valid_config["observability"] = {
            "sentry_dsn_backend_secret": "facil-sentry-be",
            "mode": "local",
            "errors_backend": "glitchtip",
            "errors_dsn_secret": "facil-glitchtip-dsn",
        }
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.observability.sentry_dsn_backend_secret == "facil-sentry-be"
        assert cfg.observability.mode == "local"
        secrets = vc.collect_secret_references(cfg)
        # Both the legacy Sentry secret and the new errors DSN are collected.
        assert "facil-sentry-be" in secrets
        assert "facil-glitchtip-dsn" in secrets

    @pytest.mark.parametrize("bad_mode", ["on", "prod", "saas"])
    def test_invalid_mode_rejected(
        self, minimal_valid_config: dict, bad_mode: str
    ) -> None:
        minimal_valid_config["observability"] = {"mode": bad_mode}
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)


class TestEdgeSeam:
    def test_defaults(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.edge.proxy == "caddy"
        assert cfg.edge.tls_mode == "none"     # dev default = plain HTTP
        assert cfg.edge.http_port == 8090      # avoids backend 8080 / frontend 3000

    @pytest.mark.parametrize("tls_mode", ["internal", "acme", "custom"])
    def test_valid_tls_modes_accepted(
        self, minimal_valid_config: dict, tls_mode: str
    ) -> None:
        minimal_valid_config["edge"] = {"tls_mode": tls_mode}
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.edge.tls_mode == tls_mode

    def test_invalid_tls_mode_rejected(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["edge"] = {"tls_mode": "letsencrypt"}
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)


class TestAuthProviderSeam:
    def test_defaults_native_everywhere(self, minimal_valid_config: dict) -> None:
        """Zero regression: both surfaces stay native until P11 flips agents."""
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.auth.provider_citizen == "native"
        assert cfg.auth.provider_agent == "native"
        assert cfg.auth.keycloak.image.startswith("quay.io/keycloak/keycloak")

    def test_agent_can_move_to_keycloak(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["auth"]["provider_agent"] = "keycloak_oidc"
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.auth.provider_agent == "keycloak_oidc"

    def test_citizen_cannot_be_keycloak(self, minimal_valid_config: dict) -> None:
        """Citizens are native by design (no Keycloak-for-all). The Literal
        only allows 'native' for the citizen surface."""
        minimal_valid_config["auth"]["provider_citizen"] = "keycloak_oidc"
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_keycloak_admin_password_secret_collected(
        self, minimal_valid_config: dict
    ) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        # Default secret name mirrors the MinIO/OpenBao pattern.
        assert "KEYCLOAK_ADMIN_PASSWORD" in vc.collect_secret_references(cfg)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

class TestCli:
    def test_main_returns_0_on_valid_config(
        self,
        tmp_path: Path,
        minimal_valid_config: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_valid_config))
        rc = vc.main([str(cfg_file)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "[OK] Config valid" in captured.out

    def test_main_returns_3_on_missing_file(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        # SystemExit(3) propagates from load_yaml().
        with pytest.raises(SystemExit) as exc:
            vc.main(["/nonexistent/path/config.yaml"])
        assert exc.value.code == 3

    def test_main_returns_1_on_provider_missing_field(
        self,
        tmp_path: Path,
        minimal_valid_config: dict,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_valid_config))
        # gcp.project_id is empty → must fail with --provider=gcp.
        rc = vc.main([str(cfg_file), "--provider=gcp"])
        assert rc == 1

    def test_main_quiet_suppresses_success_output(
        self,
        tmp_path: Path,
        minimal_valid_config: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_valid_config))
        rc = vc.main([str(cfg_file), "--quiet"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out == ""


# ---------------------------------------------------------------------------
# MinIO security/governance fields (MINIO_SECURITY_ARCH S1)
# ---------------------------------------------------------------------------

class TestMinioSecurityFields:
    def test_defaults_applied(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        m = cfg.storage.minio
        assert m.compliance.enabled is True
        assert m.compliance.bucket == "facil-compliance"
        assert m.compliance.retention_mode == "governance"
        assert m.compliance.retention_days == 365
        assert m.lifecycle.expire_noncurrent_versions_days == 90
        assert m.quota_documents_gb == 0 and m.quota_compliance_gb == 0

    def test_backward_compatible_without_storage_block(
        self, minimal_valid_config: dict
    ) -> None:
        # No `storage:` key at all -> still valid, security defaults present.
        minimal_valid_config.pop("storage", None)
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.storage.minio.compliance.bucket == "facil-compliance"

    def test_retention_mode_literal_enforced(
        self, minimal_valid_config: dict
    ) -> None:
        minimal_valid_config["storage"] = {
            "provider": "minio",
            "minio": {"compliance": {"retention_mode": "permanent"}},
        }
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_overrides_round_trip(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["storage"] = {
            "provider": "minio",
            "minio": {
                "compliance": {"retention_mode": "compliance", "retention_days": 2555},
                "lifecycle": {"expire_noncurrent_versions_days": 30},
                "quota_documents_gb": 500,
            },
        }
        m = vc.DeployConfig.model_validate(minimal_valid_config).storage.minio
        assert m.compliance.retention_mode == "compliance"
        assert m.compliance.retention_days == 2555
        assert m.lifecycle.expire_noncurrent_versions_days == 30
        assert m.quota_documents_gb == 500

    def test_negative_quota_rejected(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["storage"] = {
            "provider": "minio", "minio": {"quota_documents_gb": -1}}
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)


# ---------------------------------------------------------------------------
# Provider parity (Azure/AWS) + deployment profile (DEPLOY_WIZARD_V2 W1)
# ---------------------------------------------------------------------------

class TestProviderParityAndProfile:
    def test_profile_default_empty(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.meta.profile == "empty"

    def test_profile_accepts_known(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["meta"]["profile"] = "gov-emergent-country"
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.meta.profile == "gov-emergent-country"

    def test_profile_rejects_unknown(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["meta"]["profile"] = "martian-colony"
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_azure_defaults(self, minimal_valid_config: dict) -> None:
        az = vc.DeployConfig.model_validate(minimal_valid_config).azure
        assert az.resource_group == "facil-rg"
        assert az.location == "westeurope"
        assert az.containerapp_env == "facil-env"

    def test_aws_serverless_default(self, minimal_valid_config: dict) -> None:
        aws = vc.DeployConfig.model_validate(minimal_valid_config).aws
        assert aws.runtime == "app_runner"        # Cloud Run analog
        assert aws.ecr_repository == "facil"

    def test_aws_runtime_literal_enforced(self, minimal_valid_config: dict) -> None:
        minimal_valid_config["aws"] = {"runtime": "lambda"}
        with pytest.raises(Exception):
            vc.DeployConfig.model_validate(minimal_valid_config)

    def test_backward_compatible_without_azure_or_profile(
        self, minimal_valid_config: dict
    ) -> None:
        # A pre-existing config (no azure section, no profile) still validates.
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        assert cfg.azure.resource_group == "facil-rg"
        assert cfg.meta.profile == "empty"

    def test_required_fields_azure(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        missing = vc.provider_required_fields(cfg, "azure")
        assert any("subscription_id" in m for m in missing)
        assert any("acr_registry" in m for m in missing)

    def test_required_fields_aws_account(self, minimal_valid_config: dict) -> None:
        cfg = vc.DeployConfig.model_validate(minimal_valid_config)
        missing = vc.provider_required_fields(cfg, "aws")
        assert any("account_id" in m for m in missing)
