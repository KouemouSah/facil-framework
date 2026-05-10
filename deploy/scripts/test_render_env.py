"""Tests for deploy/scripts/render_env.py.

Run from repo root:
    pytest deploy/scripts/test_render_env.py -v --no-cov
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import render_env as re_mod  # noqa: E402
import validate_config as vc  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config() -> dict:
    """Minimal valid config — same shape as test_validate_config.py fixture."""
    return {
        "meta": {
            "config_version": 1,
            "project_name": "facil",
            "environment": "production",
            "version": "v1.0.0",
        },
        "database": {"url_secret": "facil-database-url"},
        "redis": {"url_secret": "facil-redis-url"},
        "auth": {
            "jwt_secret_name": "facil-jwt",
            "app_secret_name": "facil-app",
            "totp_encryption_secret": "facil-totp",
        },
        "firebase": {
            "project_id": "facil-prod",
            "storage_bucket": "facil-prod-uploads",
        },
        "ai": {"gemini_api_key_secret": "facil-gemini-api-key"},
        "server": {
            "frontend_url": "https://facil.gq",
            "api_base_url": "https://api.facil.gq",
        },
        "cron": {"secret_name": "facil-cron-secret"},
    }


@pytest.fixture
def cfg(minimal_config: dict) -> vc.DeployConfig:
    return vc.DeployConfig.model_validate(minimal_config)


# ---------------------------------------------------------------------------
# lookup_dotted
# ---------------------------------------------------------------------------

class TestLookupDotted:
    def test_simple_path(self, cfg: vc.DeployConfig) -> None:
        assert re_mod.lookup_dotted(cfg, "meta.environment") == "production"
        assert re_mod.lookup_dotted(cfg, "server.port") == 8080

    def test_nested_path(self, cfg: vc.DeployConfig) -> None:
        assert re_mod.lookup_dotted(cfg, "ai.generation.temperature") == 0.5
        assert re_mod.lookup_dotted(cfg, "database.pool.min_connections") == 10

    def test_missing_path_returns_none(self, cfg: vc.DeployConfig) -> None:
        assert re_mod.lookup_dotted(cfg, "meta.nonexistent") is None
        assert re_mod.lookup_dotted(cfg, "totally.fake.path") is None

    def test_secret_path(self, cfg: vc.DeployConfig) -> None:
        assert re_mod.lookup_dotted(cfg, "auth.jwt_secret_name") == "facil-jwt"


# ---------------------------------------------------------------------------
# coerce_for_env
# ---------------------------------------------------------------------------

class TestCoerceForEnv:
    @pytest.mark.parametrize("value,expected", [
        (True, "true"),
        (False, "false"),
        (None, ""),
        (42, "42"),
        (3.14, "3.14"),
        ("hello", "hello"),
        ("", ""),
    ])
    def test_coercion(self, value: object, expected: str) -> None:
        assert re_mod.coerce_for_env(value) == expected


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    def test_simple_substitution(self, cfg: vc.DeployConfig) -> None:
        text = "ENV={{meta.environment}}\nPORT={{server.port}}"
        rendered, missing = re_mod.render_template(text, cfg)
        assert rendered == "ENV=production\nPORT=8080"
        assert missing == []

    def test_boolean_coerced_lowercase(self, cfg: vc.DeployConfig) -> None:
        text = "FLAG={{features.scheduler_enabled}}"
        rendered, _ = re_mod.render_template(text, cfg)
        assert rendered == "FLAG=true"

    def test_missing_path_listed(self, cfg: vc.DeployConfig) -> None:
        text = "X={{nonexistent.path}}"
        _, missing = re_mod.render_template(text, cfg)
        assert "nonexistent.path" in missing

    def test_extras_substitution(self, cfg: vc.DeployConfig) -> None:
        text = "PRE\n{{__env_overrides__}}\nPOST"
        rendered, _ = re_mod.render_template(
            text, cfg, extra={"__env_overrides__": "QUEUE_DEFAULT_SLA_HOURS=72"}
        )
        assert "QUEUE_DEFAULT_SLA_HOURS=72" in rendered
        assert "{{__env_overrides__}}" not in rendered

    def test_whitespace_inside_braces_tolerated(self, cfg: vc.DeployConfig) -> None:
        text = "X={{ meta.environment }}"
        rendered, _ = re_mod.render_template(text, cfg)
        assert rendered == "X=production"


# ---------------------------------------------------------------------------
# build_env_overrides_block
# ---------------------------------------------------------------------------

class TestEnvOverridesBlock:
    def test_empty_returns_comment(self, cfg: vc.DeployConfig) -> None:
        out = re_mod.build_env_overrides_block(cfg)
        assert "no env_overrides" in out

    def test_renders_sorted(self, minimal_config: dict) -> None:
        minimal_config["env_overrides"] = {
            "QUEUE_DEFAULT_SLA_HOURS": 72,
            "AAA_FIRST": "value",
            "ZZZ_LAST": True,
        }
        cfg = vc.DeployConfig.model_validate(minimal_config)
        out = re_mod.build_env_overrides_block(cfg)
        lines = out.splitlines()
        assert lines == [
            "AAA_FIRST=value",
            "QUEUE_DEFAULT_SLA_HOURS=72",
            "ZZZ_LAST=true",
        ]


# ---------------------------------------------------------------------------
# build_secrets_manifest
# ---------------------------------------------------------------------------

class TestSecretsManifest:
    def test_minimal_manifest(self, cfg: vc.DeployConfig) -> None:
        manifest = re_mod.build_secrets_manifest(cfg)
        # Required secrets from minimal_config
        assert manifest["DATABASE_URL"] == "facil-database-url"
        assert manifest["REDIS_URL"] == "facil-redis-url"
        assert manifest["JWT_SECRET_KEY"] == "facil-jwt"
        assert manifest["SECRET_KEY"] == "facil-app"
        assert manifest["TOTP_ENCRYPTION_KEY"] == "facil-totp"
        assert manifest["GEMINI_API_KEY"] == "facil-gemini-api-key"
        assert manifest["CRON_SECRET"] == "facil-cron-secret"

    def test_empty_secrets_excluded(self, cfg: vc.DeployConfig) -> None:
        manifest = re_mod.build_secrets_manifest(cfg)
        # firebase.service_account_secret was empty in the fixture
        assert "FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV" not in manifest
        # payments.bange.api_key_secret was empty
        assert "BANGE_API_KEY" not in manifest

    def test_payment_secrets_when_set(self, minimal_config: dict) -> None:
        minimal_config["payments"] = {
            "bange": {
                "enabled": True,
                "api_key_secret": "facil-bange-api-key",
                "webhook_secret_secret": "facil-bange-webhook-secret",
            }
        }
        cfg = vc.DeployConfig.model_validate(minimal_config)
        manifest = re_mod.build_secrets_manifest(cfg)
        assert manifest["BANGE_API_KEY"] == "facil-bange-api-key"
        assert manifest["BANGE_WEBHOOK_SECRET"] == "facil-bange-webhook-secret"


# ---------------------------------------------------------------------------
# End-to-end: render real templates
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_backend_template_renders_without_missing(
        self, cfg: vc.DeployConfig
    ) -> None:
        template_path = re_mod.TEMPLATES_DIR / "env.backend.template"
        assert template_path.exists()
        text, missing = re_mod.render_backend(cfg, template_path)
        assert missing == [], f"Unresolved placeholders: {missing}"
        # Spot checks
        assert "ENVIRONMENT=production" in text
        assert "PORT=8080" in text
        assert "GEMINI_CHAT_MODEL=gemini-2.5-flash" in text
        # Secret refs MUST NOT appear as values in the rendered file.
        assert "DATABASE_URL=facil-database-url" not in text
        assert "JWT_SECRET_KEY=" not in text  # not in template at all
        # env_overrides block is present (with default "no overrides" comment).
        assert "no env_overrides" in text

    def test_web_template_renders_without_missing(
        self, cfg: vc.DeployConfig
    ) -> None:
        template_path = re_mod.TEMPLATES_DIR / "env.web.template"
        assert template_path.exists()
        text, missing = re_mod.render_web(cfg, template_path)
        assert missing == [], f"Unresolved placeholders: {missing}"
        assert "NEXT_PUBLIC_API_URL=https://api.facil.gq" in text
        assert "NEXT_PUBLIC_SITE_URL=https://facil.gq" in text
        assert "NEXT_PUBLIC_BUILD_VERSION=v1.0.0" in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli:
    def test_dry_run_backend(
        self,
        tmp_path: Path,
        minimal_config: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config))
        rc = re_mod.main([
            "--config", str(cfg_file),
            "--target=backend",
            "--dry-run",
        ])
        out = capsys.readouterr().out
        assert rc == 0
        assert "rendered backend" in out
        assert "ENVIRONMENT=production" in out
        assert "secrets manifest" in out
        assert '"DATABASE_URL": "facil-database-url"' in out

    def test_dry_run_both(
        self,
        tmp_path: Path,
        minimal_config: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config))
        rc = re_mod.main([
            "--config", str(cfg_file),
            "--target=both",
            "--dry-run",
        ])
        out = capsys.readouterr().out
        assert rc == 0
        assert "rendered backend" in out
        assert "rendered web" in out

    def test_writes_file(
        self,
        tmp_path: Path,
        minimal_config: dict,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config))
        out_file = tmp_path / "rendered.env"
        manifest_file = tmp_path / "manifest.json"
        rc = re_mod.main([
            "--config", str(cfg_file),
            "--target=backend",
            "--output", str(out_file),
            "--manifest", str(manifest_file),
        ])
        assert rc == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "ENVIRONMENT=production" in content
        assert manifest_file.exists()
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["DATABASE_URL"] == "facil-database-url"
