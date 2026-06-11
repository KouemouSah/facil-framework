"""Tests for deploy/init.py wizard.

Run from repo root:
    pytest deploy/test_init.py -v --no-cov
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

DEPLOY_DIR = Path(__file__).parent
sys.path.insert(0, str(DEPLOY_DIR))

import init as wiz  # noqa: E402

# Reuse validate_config to assert wizard output is schema-valid.
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import validate_config as vc  # noqa: E402


# ---------------------------------------------------------------------------
# Random secret generators
# ---------------------------------------------------------------------------

class TestSecretGenerators:
    def test_gen_hex_returns_hex_string_of_correct_length(self) -> None:
        out = wiz.gen_hex(32)
        assert len(out) == 64  # 32 bytes -> 64 hex chars
        assert all(c in "0123456789abcdef" for c in out)

    def test_gen_hex_random_each_call(self) -> None:
        assert wiz.gen_hex(16) != wiz.gen_hex(16)

    def test_gen_urlsafe_returns_url_safe_string(self) -> None:
        out = wiz.gen_urlsafe(32)
        assert len(out) >= 32
        # urlsafe alphabet: ASCII letters, digits, -, _
        assert all(c.isalnum() or c in "-_" for c in out)

    def test_gen_fernet_key_is_44_chars_base64(self) -> None:
        key = wiz.gen_fernet_key()
        # Fernet keys are 44-char URL-safe base64 (32 raw bytes + 12 chars overhead).
        assert len(key) == 44
        # Last char should be '=' or alphanumeric.
        assert key.endswith("=") or key[-1].isalnum()


# ---------------------------------------------------------------------------
# Prompter
# ---------------------------------------------------------------------------

class TestPrompterNonInteractive:
    def test_ask_uses_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOO_BAR", "from-env")
        p = wiz.Prompter(non_interactive=True)
        assert p.ask("Foo?", default="default", env="FOO_BAR") == "from-env"

    def test_ask_uses_default_in_non_interactive_when_no_env(self) -> None:
        p = wiz.Prompter(non_interactive=True)
        assert p.ask("X?", default="dflt") == "dflt"

    def test_ask_raises_in_non_interactive_when_no_default_no_env(self) -> None:
        p = wiz.Prompter(non_interactive=True)
        with pytest.raises(SystemExit):
            p.ask("X?")

    def test_ask_secret_raises_in_non_interactive_without_env(self) -> None:
        p = wiz.Prompter(non_interactive=True)
        with pytest.raises(SystemExit):
            p.ask_secret("Token?")

    def test_ask_secret_uses_env_var_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_SECRET", "abc123")
        p = wiz.Prompter(non_interactive=True)
        assert p.ask_secret("Token?", env="MY_SECRET") == "abc123"

    @pytest.mark.parametrize("env_value,expected", [
        ("1", True), ("true", True), ("yes", True), ("y", True),
        ("0", False), ("false", False), ("no", False),
    ])
    def test_ask_bool_parses_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
        expected: bool,
    ) -> None:
        monkeypatch.setenv("FLAG", env_value)
        p = wiz.Prompter(non_interactive=True)
        assert p.ask_bool("Flag?", default=False, env="FLAG") == expected

    def test_ask_choice_validates_env_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHOICE", "invalid")
        p = wiz.Prompter(non_interactive=True)
        with pytest.raises(SystemExit, match="not in choices"):
            p.ask_choice("Pick?", ["a", "b", "c"], default="a", env="CHOICE")


class TestPrompterInteractive:
    def test_ask_returns_user_input(self) -> None:
        p = wiz.Prompter(non_interactive=False)
        with patch("builtins.input", return_value="hello"):
            assert p.ask("Q?") == "hello"

    def test_ask_returns_default_on_empty_input(self) -> None:
        p = wiz.Prompter(non_interactive=False)
        with patch("builtins.input", return_value=""):
            assert p.ask("Q?", default="def") == "def"

    def test_ask_bool_yes_no(self) -> None:
        p = wiz.Prompter(non_interactive=False)
        with patch("builtins.input", return_value="y"):
            assert p.ask_bool("Q?")
        with patch("builtins.input", return_value="n"):
            assert not p.ask_bool("Q?", default=True)

    def test_ask_choice_retries_on_invalid(self) -> None:
        p = wiz.Prompter(non_interactive=False)
        responses = iter(["xxx", "a"])
        with patch("builtins.input", side_effect=lambda _: next(responses)):
            assert p.ask_choice("Q?", ["a", "b"], default="b") == "a"


# ---------------------------------------------------------------------------
# YAML / .env rendering
# ---------------------------------------------------------------------------

class TestRendering:
    def test_render_secrets_env_simple_values(self) -> None:
        out = wiz.render_secrets_env({"FOO": "bar", "BAZ": "qux"})
        assert "FOO=bar" in out
        assert "BAZ=qux" in out
        assert "DO NOT COMMIT" in out

    def test_render_secrets_env_quotes_values_with_spaces(self) -> None:
        out = wiz.render_secrets_env({"K": "value with space"})
        assert 'K="value with space"' in out

    def test_render_secrets_env_escapes_double_quote(self) -> None:
        out = wiz.render_secrets_env({"K": 'has " quote'})
        assert 'has \\"' in out

    def test_render_config_yaml_contains_header(self) -> None:
        cfg = {"meta": {"config_version": 1, "project_name": "test"}}
        out = wiz.render_config_yaml(cfg)
        assert "Generated by deploy/init.py" in out


# ---------------------------------------------------------------------------
# End-to-end: run the wizard non-interactively, validate output.
# ---------------------------------------------------------------------------

class TestEndToEndNonInteractive:
    def test_default_run_produces_valid_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Wipe any WIZ_* env vars that might pollute the test.
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)

        # Provide a Gemini key via env so the AI section doesn't fail.
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake-test-key")

        config_out = tmp_path / "config.yaml"
        secrets_out = tmp_path / ".env.secrets"
        rc = wiz.main([
            "--non-interactive",
            f"--config-out={config_out}",
            f"--secrets-out={secrets_out}",
        ])
        assert rc == 0

        # Both files written.
        assert config_out.exists()
        assert secrets_out.exists()

        # Generated config must validate against the Pydantic schema.
        import yaml
        raw = yaml.safe_load(config_out.read_text(encoding="utf-8"))
        cfg = vc.DeployConfig.model_validate(raw)
        assert cfg.meta.project_name == "facil"  # default
        assert cfg.meta.environment == "development"  # default

        # .env.secrets contains the auto-generated keys.
        secrets_content = secrets_out.read_text(encoding="utf-8")
        assert "JWT_SECRET_KEY=" in secrets_content
        assert "SECRET_KEY=" in secrets_content
        assert "TOTP_ENCRYPTION_KEY=" in secrets_content
        assert "CRON_SECRET=" in secrets_content
        # Generated values should not be the placeholder.
        for line in secrets_content.splitlines():
            if line.startswith("JWT_SECRET_KEY="):
                value = line.split("=", 1)[1]
                assert len(value) >= 32  # real random hex

    def test_force_overwrites_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake")

        cfg_path = tmp_path / "cfg.yaml"
        cfg_path.write_text("# old content")
        sec_path = tmp_path / ".env.secrets"
        sec_path.write_text("OLD=stuff")

        rc = wiz.main([
            "--non-interactive", "--force",
            f"--config-out={cfg_path}",
            f"--secrets-out={sec_path}",
        ])
        assert rc == 0
        assert "old content" not in cfg_path.read_text(encoding="utf-8")
        assert "OLD=stuff" not in sec_path.read_text(encoding="utf-8")

    def test_refuses_overwrite_without_force(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake")

        cfg_path = tmp_path / "cfg.yaml"
        cfg_path.write_text("# old content")
        sec_path = tmp_path / ".env.secrets"
        # secrets file does not exist -> the refusal happens on cfg first.

        rc = wiz.main([
            "--non-interactive",
            f"--config-out={cfg_path}",
            f"--secrets-out={sec_path}",
        ])
        assert rc == 3
        assert "old content" in cfg_path.read_text(encoding="utf-8")  # untouched

    def test_env_overrides_take_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_PROJECT_NAME", "myproject")
        monkeypatch.setenv("WIZ_ENVIRONMENT", "production")
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake")

        cfg_path = tmp_path / "cfg.yaml"
        sec_path = tmp_path / ".env.secrets"
        rc = wiz.main([
            "--non-interactive",
            f"--config-out={cfg_path}",
            f"--secrets-out={sec_path}",
        ])
        assert rc == 0
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert cfg["meta"]["project_name"] == "myproject"
        assert cfg["meta"]["environment"] == "production"


# ---------------------------------------------------------------------------
# Docker DB mode collection (Supabase / external)
# ---------------------------------------------------------------------------

class TestCollectDockerDbMode:
    def test_returns_local_for_non_docker_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        secrets: dict = {}
        p = wiz.Prompter(non_interactive=True)
        # gcp / aws → always 'local' (irrelevant field for those providers)
        assert wiz.collect_docker_db_mode(p, secrets, "gcp") == "local"
        assert wiz.collect_docker_db_mode(p, secrets, "aws") == "local"

    def test_external_mode_stores_database_url_in_secrets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_DOCKER_DB_MODE", "external")
        monkeypatch.setenv(
            "WIZ_EXTERNAL_DATABASE_URL",
            "postgresql://u:p@db.supabase.co:5432/postgres",
        )
        secrets: dict = {}
        p = wiz.Prompter(non_interactive=True)
        result = wiz.collect_docker_db_mode(p, secrets, "docker-local")
        assert result == "external"
        assert secrets.get("DATABASE_URL") == "postgresql://u:p@db.supabase.co:5432/postgres"

    def test_external_mode_without_url_in_non_interactive_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In non-interactive mode, ask_secret() requires the env var to be
        set with a non-empty value. Otherwise it raises SystemExit so CI
        fails loudly instead of silently producing a half-configured stack."""
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_DOCKER_DB_MODE", "external")
        # WIZ_EXTERNAL_DATABASE_URL deliberately NOT set.
        secrets: dict = {}
        p = wiz.Prompter(non_interactive=True)
        with pytest.raises(SystemExit):
            wiz.collect_docker_db_mode(p, secrets, "docker-local")

    def test_local_mode_default_for_docker_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        secrets: dict = {}
        p = wiz.Prompter(non_interactive=True)
        # No WIZ_DOCKER_DB_MODE set + non_interactive → default 'local'
        result = wiz.collect_docker_db_mode(p, secrets, "docker-local")
        assert result == "local"
        assert "DATABASE_URL" not in secrets


class TestEndToEndDatabaseMode:
    def test_default_run_is_local_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake")
        cfg_path = tmp_path / "cfg.yaml"
        sec_path = tmp_path / ".env.secrets"
        rc = wiz.main([
            "--non-interactive", "--force",
            f"--config-out={cfg_path}",
            f"--secrets-out={sec_path}",
        ])
        assert rc == 0
        import yaml
        cfg_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert cfg_data["docker_local"]["database_mode"] == "local"

    def test_external_mode_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ.keys()):
            if key.startswith("WIZ_"):
                monkeypatch.delenv(key)
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "fake")
        monkeypatch.setenv("WIZ_PROVIDER", "docker-local")
        monkeypatch.setenv("WIZ_DOCKER_DB_MODE", "external")
        monkeypatch.setenv(
            "WIZ_EXTERNAL_DATABASE_URL",
            "postgresql://u:p@db.example.com:5432/mydb",
        )
        cfg_path = tmp_path / "cfg.yaml"
        sec_path = tmp_path / ".env.secrets"
        rc = wiz.main([
            "--non-interactive", "--force",
            f"--config-out={cfg_path}",
            f"--secrets-out={sec_path}",
        ])
        assert rc == 0
        import yaml
        cfg_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert cfg_data["docker_local"]["database_mode"] == "external"
        secrets_content = sec_path.read_text(encoding="utf-8")
        assert "DATABASE_URL=postgresql://u:p@db.example.com" in secrets_content


# ---------------------------------------------------------------------------
# Provider-aware wizard v2 (DEPLOY_WIZARD_V2 W2)
# ---------------------------------------------------------------------------

class TestProviderAwareWizard:
    def _run(self, monkeypatch, **env):
        monkeypatch.setenv("WIZ_GEMINI_API_KEY", "k")
        for key, val in env.items():
            monkeypatch.setenv(key, val)
        p = wiz.Prompter(non_interactive=True)
        cfg, secrets_out = wiz.run_wizard(p)
        wiz.vc.DeployConfig.model_validate(cfg)   # must always validate
        return cfg, secrets_out

    def test_docker_local_sovereign_defaults(self, monkeypatch):
        cfg, sec = self._run(monkeypatch, WIZ_PROVIDER="docker-local")
        assert cfg["storage"]["provider"] == "minio"
        assert cfg["secrets"]["provider"] == "openbao"
        assert "POSTGRES_PASSWORD" in sec and "REDIS_PASSWORD" in sec
        assert "MINIO_ROOT_PASSWORD" in sec

    def test_aws_native_defaults(self, monkeypatch):
        cfg, sec = self._run(monkeypatch, WIZ_PROVIDER="aws")
        assert cfg["storage"]["provider"] == "s3"
        assert cfg["secrets"]["provider"] == "aws_secrets_manager"
        assert cfg["aws"]["runtime"] == "app_runner"
        assert "POSTGRES_PASSWORD" not in sec     # cloud-managed, not generated

    def test_azure_native_defaults(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="azure")
        assert cfg["storage"]["provider"] == "azure_blob"
        assert cfg["secrets"]["provider"] == "azure_key_vault"
        assert cfg["azure"]["resource_group"] == "facil-rg"

    def test_gcp_native_defaults(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="gcp",
                           WIZ_GCP_PROJECT_ID="facil-prod")
        assert cfg["storage"]["provider"] == "gcs"
        assert cfg["secrets"]["provider"] == "gcp_secret_manager"
        assert cfg["gcp"]["project_id"] == "facil-prod"

    def test_profile_propagated(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="docker-local",
                           WIZ_PROFILE="banking")
        assert cfg["meta"]["profile"] == "banking"

    def test_storage_provider_override(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="docker-local",
                           WIZ_STORAGE_PROVIDER="s3")
        assert cfg["storage"]["provider"] == "s3"

    def test_observability_local_endpoint(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="docker-local",
                           WIZ_OBS_MODE="local")
        assert cfg["observability"]["mode"] == "local"
        assert "4317" in cfg["observability"]["otlp_endpoint"]

    def test_profile_applies_modules_and_branding(self, monkeypatch):
        cfg, _ = self._run(monkeypatch, WIZ_PROVIDER="docker-local",
                           WIZ_PROFILE="banking")
        assert "kyc" in cfg["modules"]["enabled"]
        assert cfg["branding"]["app_name"] == "Facil Bank"
