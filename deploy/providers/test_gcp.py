"""Tests for deploy/providers/gcp.py.

These tests use mocks for all subprocess.run / gcloud invocations so they
run without a real GCP project.

Run from repo root:
    pytest deploy/providers/test_gcp.py -v --no-cov
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROVIDERS_DIR = Path(__file__).parent
sys.path.insert(0, str(PROVIDERS_DIR))

import gcp as gcp_mod  # noqa: E402

# Reuse validate_config from sibling deploy/scripts/.
SCRIPTS_DIR = PROVIDERS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import validate_config as vc  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


@pytest.fixture
def minimal_config_dict() -> dict:
    return {
        "meta": {"config_version": 1, "project_name": "facil",
                 "environment": "production", "version": "v1.0.0"},
        "database": {"url_secret": "database-url"},
        "redis": {"url_secret": "REDIS_URL"},
        "auth": {
            "jwt_secret_name": "jwt-secret-key",
            "app_secret_name": "jwt-secret-key",
            "totp_encryption_secret": "totp-encryption-key",
        },
        "firebase": {"project_id": "facil-prod", "storage_bucket": "facil-prod-uploads"},
        "ai": {"gemini_api_key_secret": "gemini-api-key"},
        "server": {"frontend_url": "https://facil.gq",
                   "api_base_url": "https://api.facil.gq"},
        "cron": {"secret_name": "cron-secret"},
        "gcp": {"project_id": "taxasge-dev"},
    }


@pytest.fixture
def cfg(minimal_config_dict: dict) -> vc.DeployConfig:
    return vc.DeployConfig.model_validate(minimal_config_dict)


@pytest.fixture
def manifest() -> dict[str, str]:
    return {
        "DATABASE_URL": "database-url",
        "REDIS_URL": "REDIS_URL",
        "JWT_SECRET_KEY": "jwt-secret-key",
        "SECRET_KEY": "jwt-secret-key",
        "TOTP_ENCRYPTION_KEY": "totp-encryption-key",
        "GEMINI_API_KEY": "gemini-api-key",
        "CRON_SECRET": "cron-secret",
    }


# ---------------------------------------------------------------------------
# find_gcloud
# ---------------------------------------------------------------------------

class TestFindGcloud:
    def test_returns_path_when_on_path(self) -> None:
        with patch("gcp.shutil.which", return_value="/usr/bin/gcloud"):
            assert gcp_mod.find_gcloud() == "/usr/bin/gcloud"

    def test_returns_none_when_absent(self) -> None:
        with patch("gcp.shutil.which", return_value=None), \
             patch("gcp.Path.exists", return_value=False):
            assert gcp_mod.find_gcloud() is None


# ---------------------------------------------------------------------------
# build_set_secrets_arg
# ---------------------------------------------------------------------------

class TestBuildSetSecretsArg:
    def test_single_pair(self) -> None:
        result = gcp_mod.build_set_secrets_arg({"DATABASE_URL": "database-url"})
        assert result == "DATABASE_URL=database-url:latest"

    def test_multiple_sorted(self) -> None:
        result = gcp_mod.build_set_secrets_arg({
            "Z_LAST": "z-secret",
            "A_FIRST": "a-secret",
            "M_MID": "m-secret",
        })
        assert result == (
            "A_FIRST=a-secret:latest,M_MID=m-secret:latest,Z_LAST=z-secret:latest"
        )

    def test_empty(self) -> None:
        assert gcp_mod.build_set_secrets_arg({}) == ""


# ---------------------------------------------------------------------------
# plan_backend_deploy / plan_frontend_deploy
# ---------------------------------------------------------------------------

class TestPlanCommands:
    def test_backend_command_shape(
        self, cfg: vc.DeployConfig, manifest: dict[str, str]
    ) -> None:
        cmd = gcp_mod.plan_backend_deploy(cfg, manifest)
        assert cmd[0] == "run"
        assert cmd[1] == "deploy"
        assert cmd[2] == "facil-backend"
        assert "--project=taxasge-dev" in cmd
        assert "--region=us-central1" in cmd
        assert "--source=packages/backend" in cmd
        # --set-secrets contains all manifest entries
        set_secrets = next(a for a in cmd if a.startswith("--set-secrets="))
        assert "DATABASE_URL=database-url:latest" in set_secrets
        assert "JWT_SECRET_KEY=jwt-secret-key:latest" in set_secrets

    def test_frontend_command_shape(self, cfg: vc.DeployConfig) -> None:
        cmd = gcp_mod.plan_frontend_deploy(cfg)
        assert "facil-frontend" in cmd
        assert "--source=packages/web" in cmd
        # NEXT_PUBLIC_API_URL is set
        assert any("NEXT_PUBLIC_API_URL=https://api.facil.gq" in a for a in cmd)


# ---------------------------------------------------------------------------
# check_prereqs (mocked subprocess)
# ---------------------------------------------------------------------------

class TestCheckPrereqs:
    def test_all_good_returns_ok(self) -> None:
        def fake_run(args: list[str], capture: bool = True) -> MagicMock:
            joined = " ".join(args)
            if "--version" in joined:
                return make_completed(0, "Google Cloud SDK 460.0.0\n")
            if "auth application-default print-access-token" in joined:
                return make_completed(0, "ya29.fake\n")
            if "config get-value project" in joined:
                return make_completed(0, "taxasge-dev\n")
            if "projects describe" in joined:
                return make_completed(0, "taxasge-dev\n")
            if "services list" in joined:
                return make_completed(0,
                    "run.googleapis.com\n"
                    "cloudbuild.googleapis.com\n"
                    "secretmanager.googleapis.com\n"
                    "containerregistry.googleapis.com\n"
                )
            return make_completed(0, "")

        with patch("gcp.find_gcloud", return_value="/usr/bin/gcloud"), \
             patch("gcp.run_gcloud", side_effect=fake_run):
            result = gcp_mod.check_prereqs("taxasge-dev")

        assert result.gcloud_present
        assert result.adc_configured
        assert result.project_accessible
        assert result.apis_missing == []
        assert result.ok is True

    def test_no_gcloud_returns_failure(self) -> None:
        with patch("gcp.find_gcloud", return_value=None):
            result = gcp_mod.check_prereqs("taxasge-dev")
        assert result.gcloud_present is False
        assert result.ok is False

    def test_missing_apis_flagged(self) -> None:
        def fake_run(args: list[str], capture: bool = True) -> MagicMock:
            joined = " ".join(args)
            if "services list" in joined:
                # Only run.googleapis.com enabled.
                return make_completed(0, "run.googleapis.com\n")
            return make_completed(0, "ok\n")

        with patch("gcp.find_gcloud", return_value="/usr/bin/gcloud"), \
             patch("gcp.run_gcloud", side_effect=fake_run):
            result = gcp_mod.check_prereqs("taxasge-dev")

        assert "cloudbuild.googleapis.com" in result.apis_missing
        assert "secretmanager.googleapis.com" in result.apis_missing
        assert result.ok is False


# ---------------------------------------------------------------------------
# cross_check_secrets
# ---------------------------------------------------------------------------

class TestCrossCheckSecrets:
    def test_all_present(
        self, tmp_path: Path, manifest: dict[str, str]
    ) -> None:
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))

        gcp_secrets = set(manifest.values())
        with patch("gcp.list_gcp_secrets", return_value=gcp_secrets):
            result = gcp_mod.cross_check_secrets(manifest_file, "taxasge-dev")

        assert result.missing_in_gcp == []
        assert result.ok is True

    def test_missing_secrets_listed(
        self, tmp_path: Path, manifest: dict[str, str]
    ) -> None:
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))

        # GCP only has 2 of the 6 expected secrets.
        partial = {"database-url", "jwt-secret-key"}
        with patch("gcp.list_gcp_secrets", return_value=partial):
            result = gcp_mod.cross_check_secrets(manifest_file, "taxasge-dev")

        assert "REDIS_URL" in result.missing_in_gcp
        assert "totp-encryption-key" in result.missing_in_gcp
        assert "gemini-api-key" in result.missing_in_gcp
        assert "cron-secret" in result.missing_in_gcp
        assert result.ok is False

    def test_orphans_reported(
        self, tmp_path: Path, manifest: dict[str, str]
    ) -> None:
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))

        # GCP has all expected + 2 extra.
        gcp_secrets = set(manifest.values()) | {"some-mobile-secret", "github-pat"}
        with patch("gcp.list_gcp_secrets", return_value=gcp_secrets):
            result = gcp_mod.cross_check_secrets(manifest_file, "taxasge-dev")

        assert result.missing_in_gcp == []
        assert "some-mobile-secret" in result.orphans_in_gcp
        assert "github-pat" in result.orphans_in_gcp
        assert result.ok is True  # orphans are info, not blocker

    def test_missing_manifest_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            gcp_mod.cross_check_secrets(tmp_path / "nonexistent.json", "p")


# ---------------------------------------------------------------------------
# CLI integration (mocked subprocess)
# ---------------------------------------------------------------------------

class TestCliValidate:
    def test_validate_ok_path(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
        manifest: dict[str, str],
        capsys: pytest.CaptureFixture,
    ) -> None:
        import yaml as yaml_mod
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_mod.safe_dump(minimal_config_dict))
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))

        # Mock all gcloud calls to "all good".
        ok_result = gcp_mod.PrereqResult(
            gcloud_present=True,
            gcloud_version="Google Cloud SDK 460",
            adc_configured=True,
            active_project="taxasge-dev",
            project_accessible=True,
            apis_required=list(gcp_mod.REQUIRED_APIS),
            apis_enabled=list(gcp_mod.REQUIRED_APIS),
            apis_missing=[],
        )
        with patch("gcp.check_prereqs", return_value=ok_result), \
             patch("gcp.list_gcp_secrets", return_value=set(manifest.values())):
            rc = gcp_mod.main([
                "--config", str(cfg_file),
                "--manifest", str(manifest_file),
                "--validate",
            ])

        out = capsys.readouterr().out
        assert rc == 0
        assert "Validation passed" in out

    def test_validate_fails_on_missing_secret(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
        manifest: dict[str, str],
    ) -> None:
        import yaml as yaml_mod
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_mod.safe_dump(minimal_config_dict))
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest))

        ok_result = gcp_mod.PrereqResult(
            gcloud_present=True, adc_configured=True,
            project_accessible=True,
            apis_required=list(gcp_mod.REQUIRED_APIS),
            apis_enabled=list(gcp_mod.REQUIRED_APIS),
            apis_missing=[],
        )
        with patch("gcp.check_prereqs", return_value=ok_result), \
             patch("gcp.list_gcp_secrets", return_value={"database-url"}):  # only 1 of 6
            rc = gcp_mod.main([
                "--config", str(cfg_file),
                "--manifest", str(manifest_file),
                "--validate",
            ])
        assert rc == 1

    def test_validate_fails_when_gcp_project_id_empty(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
    ) -> None:
        import yaml as yaml_mod
        # Remove gcp.project_id
        minimal_config_dict["gcp"] = {"project_id": ""}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_mod.safe_dump(minimal_config_dict))
        rc = gcp_mod.main([
            "--config", str(cfg_file),
            "--validate",
        ])
        assert rc == 1
