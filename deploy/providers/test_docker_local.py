"""Tests for deploy/providers/docker_local.py.

Run from repo root:
    pytest deploy/providers/test_docker_local.py -v --no-cov
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

PROVIDERS_DIR = Path(__file__).parent
sys.path.insert(0, str(PROVIDERS_DIR))
SCRIPTS_DIR = PROVIDERS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import docker_local as dl  # noqa: E402
import validate_config as vc  # noqa: E402


@pytest.fixture
def minimal_config_dict() -> dict:
    return {
        "meta": {"config_version": 1, "project_name": "facil",
                 "environment": "development", "version": "v1.0.0"},
        "database": {"url_secret": "database-url"},
        "redis": {"url_secret": "REDIS_URL"},
        "auth": {
            "jwt_secret_name": "jwt-secret-key",
            "app_secret_name": "jwt-secret-key",
            "totp_encryption_secret": "totp-encryption-key",
        },
        "firebase": {"project_id": "facil-prod", "storage_bucket": "facil-prod-uploads"},
        "ai": {"gemini_api_key_secret": "gemini-api-key"},
        "server": {"frontend_url": "http://localhost:3000",
                   "api_base_url": "http://localhost:8080"},
        "cron": {"secret_name": "cron-secret"},
    }


@pytest.fixture
def cfg(minimal_config_dict: dict) -> vc.DeployConfig:
    return vc.DeployConfig.model_validate(minimal_config_dict)


# ---------------------------------------------------------------------------
# Compose generation
# ---------------------------------------------------------------------------

class TestGenerateCompose:
    def test_contains_postgres_redis_backend_frontend(
        self, cfg: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg)
        assert "services:" in out
        assert "postgres:" in out
        assert "redis:" in out
        assert "backend:" in out
        assert "frontend:" in out

    def test_uses_config_ports(self, cfg: vc.DeployConfig) -> None:
        out = dl.generate_compose(cfg)
        # Defaults from DockerLocalConfig: backend_port=8080, frontend_port=3000
        assert "8080:8080" in out
        assert "3000:3000" in out

    def test_uses_config_postgres_image(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["docker_local"] = {
            "postgres_image": "postgres:15-alpine",
            "redis_image": "redis:7-alpine",
        }
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        out = dl.generate_compose(cfg)
        assert "image: postgres:15-alpine" in out

    def test_pg_user_db_uses_project_name(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["meta"]["project_name"] = "myproject"
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        out = dl.generate_compose(cfg)
        assert "POSTGRES_DB: myproject" in out
        assert "POSTGRES_USER: myproject" in out

    def test_yaml_parses(self, cfg: vc.DeployConfig) -> None:
        """Generated compose file must be valid YAML."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        assert parsed is not None
        assert "services" in parsed
        # Base services: postgres + redis + minio (storage default=minio, ADR-0005)
        # + db-init (one-shot) + backend + frontend. OpenBao is absent by default
        # (secrets default=env_file). Gating covered in TestStorageAndSecretsServices.
        assert set(parsed["services"].keys()) == {
            "postgres", "redis", "minio", "db-init", "backend", "frontend"
        }

    def test_no_deprecated_version_field(self, cfg: vc.DeployConfig) -> None:
        """Compose v2 ignores `version:` and warns when present."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        assert "version" not in parsed

    def test_db_init_runs_init_database_script(self, cfg: vc.DeployConfig) -> None:
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        db_init = parsed["services"]["db-init"]
        # Must run init_database.py (not just any python command).
        assert "init_database.py" in " ".join(db_init["command"])
        # Must NOT auto-restart (it's a one-shot bootstrap).
        assert db_init["restart"] == "no"
        # Must wait for postgres healthcheck.
        assert db_init["depends_on"]["postgres"]["condition"] == "service_healthy"

    def test_backend_waits_for_db_init_completion(self, cfg: vc.DeployConfig) -> None:
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        backend_deps = parsed["services"]["backend"]["depends_on"]
        # The critical guarantee: backend never starts before db-init exits 0.
        assert backend_deps["db-init"]["condition"] == "service_completed_successfully"

    def test_internal_api_url_for_ssr(self, cfg: vc.DeployConfig) -> None:
        """Frontend container must have INTERNAL_API_URL pointing at the
        backend service hostname (not localhost) so SSR works."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        env = parsed["services"]["frontend"]["environment"]
        assert env["INTERNAL_API_URL"].startswith("http://backend:")

    def test_restart_policy_on_long_running_services(
        self, cfg: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        for svc in ("postgres", "redis", "backend", "frontend"):
            assert parsed["services"][svc].get("restart") == "unless-stopped", \
                f"{svc} missing restart: unless-stopped"


# ---------------------------------------------------------------------------
# database_mode: local vs external (Supabase / RDS / etc.)
# ---------------------------------------------------------------------------

class TestDatabaseModeExternal:
    @pytest.fixture
    def cfg_external(self, minimal_config_dict: dict) -> vc.DeployConfig:
        # deepcopy to avoid mutating the shared minimal_config_dict fixture
        # — otherwise other tests requesting `cfg` in the same test function
        # would see the docker_local override.
        import copy
        config = copy.deepcopy(minimal_config_dict)
        config["docker_local"] = {
            "database_mode": "external",
            "backend_port": 8080,
            "frontend_port": 3000,
        }
        return vc.DeployConfig.model_validate(config)

    def test_external_mode_skips_postgres_service(
        self, cfg_external: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg_external)
        parsed = yaml.safe_load(out)
        assert "postgres" not in parsed["services"], \
            "external mode must NOT generate a postgres service"
        assert "SKIPPED — database_mode=external" in out

    def test_external_mode_no_postgres_volume(
        self, cfg_external: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg_external)
        parsed = yaml.safe_load(out)
        # `volumes:` key may be absent or empty/None, but must NOT contain pgdata.
        volumes = parsed.get("volumes") or {}
        assert "facil_pgdata" not in volumes
        assert "pgdata" not in str(volumes).lower()

    def test_external_mode_db_init_no_postgres_dependency(
        self, cfg_external: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg_external)
        parsed = yaml.safe_load(out)
        db_init = parsed["services"]["db-init"]
        # In external mode db-init has no depends_on (or doesn't list postgres).
        deps = db_init.get("depends_on") or {}
        assert "postgres" not in deps

    def test_external_mode_backend_no_postgres_dependency(
        self, cfg_external: vc.DeployConfig
    ) -> None:
        out = dl.generate_compose(cfg_external)
        parsed = yaml.safe_load(out)
        backend_deps = parsed["services"]["backend"]["depends_on"]
        assert "postgres" not in backend_deps
        # But db-init dependency must still be enforced.
        assert "db-init" in backend_deps
        assert backend_deps["db-init"]["condition"] == "service_completed_successfully"

    def test_external_mode_does_not_inline_database_url(
        self, cfg_external: vc.DeployConfig
    ) -> None:
        """In external mode, DATABASE_URL must come from .env.secrets, NOT
        be inlined in the compose `environment:` block (otherwise the inline
        value would override .env.secrets and break the operator's intent)."""
        out = dl.generate_compose(cfg_external)
        parsed = yaml.safe_load(out)
        backend_env = parsed["services"]["backend"]["environment"]
        # The key may be absent, OR present but the in-file content must be
        # a comment line (not a real key-value).
        assert "DATABASE_URL" not in backend_env or backend_env.get("DATABASE_URL") is None
        # Same for db-init.
        db_init_env = parsed["services"]["db-init"]["environment"]
        assert "DATABASE_URL" not in db_init_env or db_init_env.get("DATABASE_URL") is None

    def test_local_mode_inlines_database_url(
        self, cfg: vc.DeployConfig
    ) -> None:
        """In local mode, DATABASE_URL must be inlined pointing at the in-stack
        postgres service hostname."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        backend_env = parsed["services"]["backend"]["environment"]
        assert "DATABASE_URL" in backend_env
        assert "@postgres:5432" in backend_env["DATABASE_URL"]

    def test_local_mode_keeps_postgres_service(
        self, cfg: vc.DeployConfig
    ) -> None:
        """Default (local) mode must still generate the postgres service."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        assert "postgres" in parsed["services"]

    def test_database_mode_in_header_comment(
        self, cfg_external: vc.DeployConfig, cfg: vc.DeployConfig
    ) -> None:
        """The header comment must state the chosen mode for clarity."""
        assert "database_mode: external" in dl.generate_compose(cfg_external)
        assert "database_mode: local" in dl.generate_compose(cfg)


# ---------------------------------------------------------------------------
# Storage (MinIO) & Secrets (OpenBao) service gating — ADR-0005 / ADR-0006 / P7
# ---------------------------------------------------------------------------

class TestStorageAndSecretsServices:
    def test_minio_emitted_by_default(self, cfg: vc.DeployConfig) -> None:
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        assert "minio" in parsed["services"]
        assert parsed["services"]["minio"]["image"].startswith("minio/minio")
        assert "facil_minio_data" in (parsed.get("volumes") or {})

    def test_openbao_absent_by_default(self, cfg: vc.DeployConfig) -> None:
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        assert "openbao" not in parsed["services"]

    def test_storage_local_fs_skips_minio(self, minimal_config_dict: dict) -> None:
        minimal_config_dict["storage"] = {"provider": "local_fs"}
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        assert "minio" not in parsed["services"]
        assert "facil_minio_data" not in (parsed.get("volumes") or {})

    def test_secrets_openbao_emits_dev_mode_no_volume(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["secrets"] = {"provider": "openbao"}
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        assert "openbao" in parsed["services"]
        bao = parsed["services"]["openbao"]
        assert bao["image"].startswith("openbao/openbao")
        # dev mode -> `-dev` flag, in-memory (no persistent named volume).
        assert "-dev" in " ".join(bao["command"])
        assert "facil_openbao_data" not in (parsed.get("volumes") or {})

    def test_secrets_openbao_prod_mode_adds_volume(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["secrets"] = {
            "provider": "openbao", "openbao": {"dev_mode": False}
        }
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        assert "facil_openbao_data" in (parsed.get("volumes") or {})


# ---------------------------------------------------------------------------
# Prereq detection
# ---------------------------------------------------------------------------

class TestFindDocker:
    def test_returns_path_when_on_path(self) -> None:
        with patch("docker_local.shutil.which", return_value="/usr/bin/docker"):
            assert dl.find_docker() == "/usr/bin/docker"

    def test_returns_none_when_absent(self) -> None:
        with patch("docker_local.shutil.which", return_value=None):
            assert dl.find_docker() is None


class TestDockerComposeAvailable:
    def test_returns_true_on_success(self) -> None:
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.subprocess.run",
                   return_value=MagicMock(returncode=0, stdout="Docker Compose v2.x")):
            assert dl.docker_compose_available()

    def test_returns_false_when_no_docker(self) -> None:
        with patch("docker_local.find_docker", return_value=None):
            assert not dl.docker_compose_available()

    def test_returns_false_on_error(self) -> None:
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.subprocess.run",
                   return_value=MagicMock(returncode=1)):
            assert not dl.docker_compose_available()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCli:
    def test_validate_passes_when_docker_present(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True):
            rc = dl.main([
                "--config", str(cfg_file),
                "--validate",
            ])

        out = capsys.readouterr().out
        assert rc == 0
        assert "Prereqs validated" in out

    def test_plan_prints_compose_content(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
        capsys: pytest.CaptureFixture,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True):
            rc = dl.main([
                "--config", str(cfg_file),
                "--plan",
            ])

        out = capsys.readouterr().out
        assert rc == 0
        assert "services:" in out
        assert "postgres:" in out

    def test_validate_fails_without_docker(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))

        with patch("docker_local.find_docker", return_value=None), \
             patch("docker_local.docker_compose_available", return_value=False):
            rc = dl.main([
                "--config", str(cfg_file),
                "--validate",
            ])
        assert rc == 1

    def test_apply_fails_without_secrets_file(
        self,
        tmp_path: Path,
        minimal_config_dict: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))
        monkeypatch.setattr(dl, "SECRETS_FILE", tmp_path / ".env.secrets-missing")

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True):
            rc = dl.main([
                "--config", str(cfg_file),
                "--apply",
            ])
        assert rc == 1


# ---------------------------------------------------------------------------
# stack_running detection
# ---------------------------------------------------------------------------

class TestStackRunning:
    def test_returns_false_when_no_compose_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(dl, "COMPOSE_FILE", tmp_path / "absent.yml")
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"):
            assert not dl.stack_running()

    def test_returns_true_when_ps_lists_containers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        compose = tmp_path / "compose.yml"
        compose.write_text("services: {}")
        monkeypatch.setattr(dl, "COMPOSE_FILE", compose)
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.subprocess.run",
                   return_value=MagicMock(returncode=0,
                                          stdout="abc123\ndef456\n",
                                          stderr="")):
            assert dl.stack_running()

    def test_returns_false_when_ps_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        compose = tmp_path / "compose.yml"
        compose.write_text("services: {}")
        monkeypatch.setattr(dl, "COMPOSE_FILE", compose)
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.subprocess.run",
                   return_value=MagicMock(returncode=0, stdout="", stderr="")):
            assert not dl.stack_running()


# ---------------------------------------------------------------------------
# --down / --logs / --restart commands
# ---------------------------------------------------------------------------

class TestDownLogsRestart:
    def test_down_fails_without_compose_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(dl, "COMPOSE_FILE", tmp_path / "absent.yml")
        rc = dl.main(["--down"])
        assert rc == 1

    def test_down_runs_compose_down(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        compose = tmp_path / "compose.yml"
        compose.write_text("services: {}")
        monkeypatch.setattr(dl, "COMPOSE_FILE", compose)
        called = []

        def fake_run_compose(args, **kwargs):
            called.append(args)
            return 0

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.run_compose", side_effect=fake_run_compose):
            rc = dl.main(["--down"])

        assert rc == 0
        assert called and "down" in called[0]
        assert "-v" not in called[0]

    def test_down_with_volumes_passes_v_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        compose = tmp_path / "compose.yml"
        compose.write_text("services: {}")
        monkeypatch.setattr(dl, "COMPOSE_FILE", compose)
        called = []

        def fake_run_compose(args, **kwargs):
            called.append(args)
            return 0

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.run_compose", side_effect=fake_run_compose):
            rc = dl.main(["--down", "--volumes"])

        assert rc == 0
        assert "-v" in called[0]

    def test_logs_fails_without_compose_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(dl, "COMPOSE_FILE", tmp_path / "absent.yml")
        rc = dl.main(["--logs"])
        assert rc == 1

    def test_restart_runs_compose_restart(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        compose = tmp_path / "compose.yml"
        compose.write_text("services: {}")
        monkeypatch.setattr(dl, "COMPOSE_FILE", compose)
        called = []

        def fake_run_compose(args, **kwargs):
            called.append(args)
            return 0

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.run_compose", side_effect=fake_run_compose):
            rc = dl.main(["--restart"])

        assert rc == 0
        assert "restart" in called[0]


# ---------------------------------------------------------------------------
# BuildKit env vars
# ---------------------------------------------------------------------------

class TestBuildKit:
    def test_run_compose_sets_buildkit_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured_env = {}

        def fake_subprocess_run(args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return MagicMock(returncode=0)

        monkeypatch.setattr(dl.subprocess, "run", fake_subprocess_run)
        dl.run_compose(["docker", "compose", "version"])

        assert captured_env.get("DOCKER_BUILDKIT") == "1"
        assert captured_env.get("COMPOSE_DOCKER_CLI_BUILD") == "1"
