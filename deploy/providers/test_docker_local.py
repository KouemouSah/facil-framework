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
        # Scaffolded profile-gated services (caddy/keycloak/otel-lgtm) are ALWAYS
        # present in the file but OFF by default (see TestScaffoldedProfileServices).
        assert set(parsed["services"].keys()) == {
            "postgres", "redis", "minio", "db-init", "backend", "frontend",
            "caddy", "keycloak", "otel-lgtm", "ollama", "smtp4dev",
        }

    def test_no_deprecated_version_field(self, cfg: vc.DeployConfig) -> None:
        """Compose v2 ignores `version:` and warns when present."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        assert "version" not in parsed

    def test_db_init_runs_alembic_migrations(self, cfg: vc.DeployConfig) -> None:
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        db_init = parsed["services"]["db-init"]
        # Migrations run via Alembic (as the superuser; DATABASE_URL inline).
        assert " ".join(db_init["command"]) == "alembic upgrade head"
        assert "DATABASE_URL" in db_init["environment"]
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
        """In local mode, db-init (migrations) gets DATABASE_URL inlined at the
        in-stack postgres (as the superuser). The BACKEND instead receives its
        facil_app DATABASE_URL from packages/backend/.env.deploy.gen (so it is
        NOT inlined in the backend environment)."""
        out = dl.generate_compose(cfg)
        parsed = yaml.safe_load(out)
        db_init_env = parsed["services"]["db-init"]["environment"]
        assert "DATABASE_URL" in db_init_env
        assert "@postgres:5432" in db_init_env["DATABASE_URL"]
        # Backend connects as least-privilege facil_app via the rendered env_file.
        backend_env = parsed["services"]["backend"].get("environment", {}) or {}
        assert "DATABASE_URL" not in backend_env

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
# Scaffolded profile-gated services (Caddy / Keycloak / otel-lgtm) — P14 + P11
# ---------------------------------------------------------------------------

class TestScaffoldedProfileServices:
    def test_three_services_present(self, cfg: vc.DeployConfig) -> None:
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        for name in ("caddy", "keycloak", "otel-lgtm"):
            assert name in svcs, f"{name} must be scaffolded in the compose file"

    def test_all_three_are_profile_gated_off_by_default(
        self, cfg: vc.DeployConfig
    ) -> None:
        """The whole point: present in the file but they DON'T start unless
        their profile is selected. A service without `profiles:` starts on a
        plain `docker compose up` — these must NOT."""
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        assert svcs["caddy"]["profiles"] == ["edge"]
        assert svcs["keycloak"]["profiles"] == ["auth"]
        assert svcs["otel-lgtm"]["profiles"] == ["observability"]
        assert svcs["ollama"]["profiles"] == ["ai"]
        assert svcs["smtp4dev"]["profiles"] == ["mail"]

    def test_base_services_have_no_profile(self, cfg: vc.DeployConfig) -> None:
        """Core services must remain un-gated (start on plain `up`)."""
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        # frontend is now a default service too (the facil_framework group mirrors
        # production); it is built locally from source like the backend.
        for name in ("postgres", "redis", "backend", "db-init", "frontend"):
            assert "profiles" not in svcs[name], \
                f"{name} must NOT be profile-gated (it's a core service)"
        assert svcs["frontend"]["build"]["context"] == "./packages/web", \
            "frontend should build locally (like the backend), not pull a registry image"

    def test_ollama_scaffold_and_backend_wiring(self, cfg: vc.DeployConfig) -> None:
        """Ollama is profile-gated `ai`, persists weights in facil_ollama, and
        the backend is wired to reach it (degrades cleanly when profile is OFF)."""
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        ollama = svcs["ollama"]
        assert ollama["profiles"] == ["ai"]
        assert any("facil_ollama:" in v for v in ollama["volumes"])
        assert svcs["backend"]["environment"]["OLLAMA_ENDPOINT"] == "http://ollama:11434"

    def test_smtp4dev_scaffold_and_backend_wiring(self, cfg: vc.DeployConfig) -> None:
        """smtp4dev is profile-gated `mail`; backend is wired to reach it."""
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        assert svcs["smtp4dev"]["profiles"] == ["mail"]
        env = svcs["backend"]["environment"]
        assert env["SMTP_HOST"] == "smtp4dev" and env["SMTP_PORT"] == "25"

    def test_no_weak_password_defaults(self, cfg: vc.DeployConfig) -> None:
        """#3 fix: core data-plane secrets are REQUIRED (compose ${VAR:?...}),
        never a silent weak default — so a raw `docker compose up` without the
        secrets fails loud instead of provisioning with localdev/facilminio."""
        out = dl.generate_compose(cfg)
        assert ":-localdev" not in out and ":-facilminio" not in out
        assert "${POSTGRES_PASSWORD:?" in out and "${MINIO_ROOT_PASSWORD:?" in out

    def test_modules_enabled_wired_to_backend(self, cfg: vc.DeployConfig) -> None:
        """The W6 modules.enabled list reaches the backend as MODULES_ENABLED
        (the Module Loader contract, Phase A.5)."""
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        expected = ",".join(cfg.modules.enabled)
        assert svcs["backend"]["environment"]["MODULES_ENABLED"] == expected

    def test_caddy_mounts_generated_caddyfile(self, cfg: vc.DeployConfig) -> None:
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        mounts = svcs["caddy"]["volumes"]
        assert any("/etc/caddy/Caddyfile" in m for m in mounts)

    def test_keycloak_dev_mode_no_named_volume(self, cfg: vc.DeployConfig) -> None:
        """Dev Keycloak uses in-memory H2 → no persistent volume (prod DB = P11)."""
        parsed = yaml.safe_load(dl.generate_compose(cfg))
        kc = parsed["services"]["keycloak"]
        assert "start-dev" in " ".join(kc["command"])
        assert "volumes" not in kc

    def test_scaffold_volumes_declared(self, cfg: vc.DeployConfig) -> None:
        volumes = yaml.safe_load(dl.generate_compose(cfg)).get("volumes") or {}
        for v in ("facil_caddy_data", "facil_caddy_config", "facil_otel_lgtm",
                  "facil_ollama"):
            assert v in volumes, f"{v} must be declared for the scaffolded service"

    def test_otel_lgtm_exposes_otlp_and_grafana_ports(
        self, cfg: vc.DeployConfig
    ) -> None:
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        published = " ".join(svcs["otel-lgtm"]["ports"])
        # Defaults: grafana 3001, OTLP grpc 4317, OTLP http 4318.
        assert "3001:3000" in published          # Grafana (3000 taken by frontend)
        assert "4317:4317" in published          # OTLP gRPC
        assert "4318:4318" in published          # OTLP HTTP

    def test_grafana_port_does_not_clash_with_frontend(
        self, cfg: vc.DeployConfig
    ) -> None:
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        front = " ".join(svcs["frontend"]["ports"])
        grafana = " ".join(svcs["otel-lgtm"]["ports"])
        assert "3000:3000" in front
        assert "3000:3000" not in grafana


class TestGenerateCaddyfile:
    def test_tls_none_is_plain_http(self, cfg: vc.DeployConfig) -> None:
        out = dl.generate_caddyfile(cfg)  # default tls_mode=none
        assert "auto_https off" in out
        assert ":80 {" in out

    def test_routes_api_to_backend_rest_to_frontend(
        self, cfg: vc.DeployConfig
    ) -> None:
        out = dl.generate_caddyfile(cfg)
        assert "handle /api/* {" in out
        assert "reverse_proxy backend:8080" in out
        assert "reverse_proxy frontend:3000" in out

    def test_tls_internal_emits_tls_internal_directive(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["edge"] = {"tls_mode": "internal",
                                       "domain_frontend": "facil.local"}
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        out = dl.generate_caddyfile(cfg)
        assert "tls internal" in out
        assert "facil.local {" in out

    def test_tls_internal_publishes_https_port(
        self, minimal_config_dict: dict
    ) -> None:
        minimal_config_dict["edge"] = {"tls_mode": "internal"}
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        published = " ".join(svcs["caddy"]["ports"])
        assert "8443:443" in published

    def test_tls_none_does_not_publish_https_port(
        self, cfg: vc.DeployConfig
    ) -> None:
        svcs = yaml.safe_load(dl.generate_compose(cfg))["services"]
        published = " ".join(svcs["caddy"]["ports"])
        assert ":443" not in published


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


# ---------------------------------------------------------------------------
# Data-plane bootstrap integration (auto-run post-up, opt-out, non-fatal)
# ---------------------------------------------------------------------------

class TestBootstrapIntegration:
    def _apply_mocks(self, tmp_path, minimal_config_dict, monkeypatch):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))
        secrets = tmp_path / ".env.secrets"
        secrets.write_text("X=1")
        monkeypatch.setattr(dl, "SECRETS_FILE", secrets)
        monkeypatch.setattr(dl, "COMPOSE_FILE", tmp_path / "docker-compose.local.yml")
        monkeypatch.setattr(dl, "CADDYFILE", tmp_path / "Caddyfile")
        return cfg_file

    def test_apply_runs_bootstrap_by_default(
        self, tmp_path, minimal_config_dict, monkeypatch
    ):
        cfg_file = self._apply_mocks(tmp_path, minimal_config_dict, monkeypatch)
        called = []
        monkeypatch.setattr(dl, "_run_bootstrap", lambda cfg: called.append(cfg))
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=False), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", return_value=0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 0
        assert len(called) == 1            # bootstrap ran once

    def test_apply_no_bootstrap_flag_skips(
        self, tmp_path, minimal_config_dict, monkeypatch
    ):
        cfg_file = self._apply_mocks(tmp_path, minimal_config_dict, monkeypatch)
        called = []
        monkeypatch.setattr(dl, "_run_bootstrap", lambda cfg: called.append(cfg))
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=False), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", return_value=0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes",
                          "--no-bootstrap"])
        assert rc == 0
        assert called == []                # bootstrap skipped

    def test_run_bootstrap_is_non_fatal_on_failure(
        self, minimal_config_dict, monkeypatch
    ):
        import types
        fake = types.ModuleType("bootstrap")

        def boom(cfg):
            raise RuntimeError("kaboom")

        fake.run_bootstrap = boom
        monkeypatch.setitem(sys.modules, "bootstrap", fake)
        cfg = vc.DeployConfig.model_validate(minimal_config_dict)
        # Must NOT raise — a provisioning failure never tears the stack down.
        dl._run_bootstrap(cfg)


# ---------------------------------------------------------------------------
# Redis auth + runtime secrets (DATAPLANE_AUTH_HARDENING H1)
# ---------------------------------------------------------------------------

class TestRedisAuthGeneration:
    def _cfg(self, minimal_config_dict):
        return vc.DeployConfig.model_validate(minimal_config_dict)

    def test_redis_requires_password(self, minimal_config_dict):
        # SEC-004: required (:?) so a direct `compose up` without the secret fails
        # loud instead of starting Redis with an empty password (no auth).
        out = dl.generate_compose(self._cfg(minimal_config_dict))
        assert '"--requirepass", "${REDIS_PASSWORD:?' in out
        assert '"${REDIS_PASSWORD}"' not in out  # no bare (defaultless) form left

    def test_redis_healthcheck_authenticated(self, minimal_config_dict):
        out = dl.generate_compose(self._cfg(minimal_config_dict))
        assert '"-a", "${REDIS_PASSWORD:?' in out

    def test_backend_redis_url_carries_password(self, minimal_config_dict):
        out = dl.generate_compose(self._cfg(minimal_config_dict))
        assert "REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0" in out

    def test_placeholder_not_interpolated_in_file(self, minimal_config_dict):
        # The generated YAML keeps ${REDIS_PASSWORD} literal (compose resolves it
        # at up via env_extra) — no real secret is ever written to the file.
        out = dl.generate_compose(self._cfg(minimal_config_dict))
        assert "${REDIS_PASSWORD}" in out


# ---------------------------------------------------------------------------
# (a2) App-tier gate: openbao required but failed => hard abort, not silent
# ---------------------------------------------------------------------------

sys.path.insert(0, str(PROVIDERS_DIR))
from bootstrap.state import BootstrapState, ProvisionStep  # noqa: E402


def _state(status: str | None) -> BootstrapState:
    steps = [] if status is None else [ProvisionStep(name="openbao", status=status)]
    return BootstrapState(project="facil", storage_provider="minio",
                          secrets_provider="openbao", database_mode="local",
                          steps=steps)


# ---------------------------------------------------------------------------
# D1 : sauvegarde Postgres avant update, tier lite (compose) — best-effort
# mais pas 2e classe sur la perte de donnees. `--apply` EST le chemin
# d'update du tier lite (idempotent, re-invoque pour deployer un nouveau
# code/une nouvelle migration -- il n'existe pas de commande `--update`
# separee ; c'est le meme constat que `helm upgrade --install`). La
# sauvegarde se greffe donc DANS `_do_apply`, fail-closed, mirroring
# infra/helm/facil/templates/backup-job.yaml (meme discipline : dump vide =
# echec, PGPASSWORD jamais dans l'argv).
# ---------------------------------------------------------------------------

class TestBackupPostgres:
    def test_writes_dump_file_on_success(self, cfg, tmp_path, monkeypatch):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            captured["kwargs"] = kw
            return MagicMock(returncode=0, stdout=b"PGDMP-fake-dump-bytes", stderr=b"")

        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(dl.subprocess, "run", fake_run)

        ok, msg = dl.backup_postgres(cfg, dest_dir=tmp_path,
                                     compose_file=tmp_path / "docker-compose.local.yml")

        assert ok is True
        dumps = list(tmp_path.glob("*/postgres.dump"))
        assert len(dumps) == 1
        assert dumps[0].read_bytes() == b"PGDMP-fake-dump-bytes"
        assert dumps[0].name in msg or str(dumps[0]) in msg
        # pg_dump invoked via `docker compose exec` — no `-h` (local trust
        # socket, same assumption the compose healthcheck already relies on:
        # `pg_isready -U {project}` with no host either).
        cmd = captured["cmd"]
        assert cmd[:2] == ["/usr/bin/docker", "compose"]
        assert "exec" in cmd
        assert "pg_dump" in cmd
        assert "-U" in cmd and cfg.meta.project_name in cmd

    def test_fails_closed_when_pg_dump_errors_and_leaves_no_file(
        self, cfg, tmp_path, monkeypatch,
    ):
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(
            dl.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=1, stdout=b"", stderr=b"connection refused"))

        ok, msg = dl.backup_postgres(cfg, dest_dir=tmp_path,
                                     compose_file=tmp_path / "docker-compose.local.yml")

        assert ok is False
        assert "connection refused" in msg
        assert list(tmp_path.glob("*/postgres.dump")) == []

    def test_fails_closed_on_empty_dump_mutation_guard(self, cfg, tmp_path, monkeypatch):
        # Mutation-guard (fail-closed, un dump vide est PIRE que pas de dump) :
        # pg_dump "reussit" (rc=0) mais ne produit RIEN -- doit quand meme
        # etre traite comme un echec, sans laisser de fichier vide trainer.
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(
            dl.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=0, stdout=b"", stderr=b""))

        ok, msg = dl.backup_postgres(cfg, dest_dir=tmp_path,
                                     compose_file=tmp_path / "docker-compose.local.yml")

        assert ok is False
        assert "vide" in msg.lower()
        assert list(tmp_path.rglob("postgres.dump")) == [], (
            "un dump vide ne doit jamais rester sur disque (fausse confiance)")

    def test_fails_closed_when_docker_missing(self, cfg, tmp_path, monkeypatch):
        monkeypatch.setattr(dl, "find_docker", lambda: None)
        called = []
        monkeypatch.setattr(dl.subprocess, "run", lambda cmd, **kw: called.append(cmd))

        ok, msg = dl.backup_postgres(cfg, dest_dir=tmp_path,
                                     compose_file=tmp_path / "docker-compose.local.yml")

        assert ok is False
        assert called == [], "sans docker, aucune tentative de subprocess"

    def test_never_puts_a_password_in_the_pg_dump_argv(self, cfg, tmp_path, monkeypatch):
        # CWE-214 : meme garde que k3s.py (SEC-006) -- aucune valeur de secret
        # ne doit jamais apparaitre dans l'argv d'un subprocess, docker exec
        # inclus. Ce chemin n'a d'ailleurs BESOIN d'aucun mot de passe (auth
        # locale par socket unix, deja le postulat de la healthcheck compose
        # existante `pg_isready -U {project}` sans -h) -- on verifie que le
        # marqueur n'apparait nulle part si jamais il fuitait par accident.
        MARKER = "s3ntinel-pw-marker"
        monkeypatch.setenv("POSTGRES_PASSWORD", MARKER)
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            captured["kwargs"] = kw
            return MagicMock(returncode=0, stdout=b"PGDMP-x", stderr=b"")

        monkeypatch.setattr(dl.subprocess, "run", fake_run)
        dl.backup_postgres(cfg, dest_dir=tmp_path,
                           compose_file=tmp_path / "docker-compose.local.yml")

        for arg in captured["cmd"]:
            assert MARKER not in arg


class TestPostgresDataState:
    """B4 : le signal reel de gating -- schema deja initialise, pas liveness
    du conteneur (stack_running()).

    TERNAIRE, jamais booleen : "has_data" / "empty" / "unknown". Ecraser
    "unknown" sur "empty" (ce que faisait la version booleenne) est un
    fail-OPEN -- "je n'ai pas pu savoir" devenait "rien a proteger", donc
    "migre sans sauvegarde".
    """

    def test_has_data_when_a_public_table_exists(self, cfg, monkeypatch):
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(
            dl.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=0, stdout="1\n", stderr=""))
        assert dl.postgres_data_state(cfg) == "has_data"

    def test_empty_on_a_genuinely_empty_database(self, cfg, monkeypatch):
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(
            dl.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=0, stdout="", stderr=""))
        assert dl.postgres_data_state(cfg) == "empty"

    def test_unknown_when_psql_never_answers(self, cfg, monkeypatch):
        # LE test qui compte. Postgres rejoue son WAL apres un arret sale, ou
        # `up -d` (sans --wait) a rendu la main avant que le socket accepte :
        # psql echoue. La base est peut-etre PLEINE. Repondre "empty" ici
        # revient a sauter la sauvegarde puis lancer la migration Alembic
        # dessus. Le seul verdict honnete est "unknown" -- et l'appelant
        # avorte (cf. test_probe_failure_aborts_the_apply_before_db_init).
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(dl.time, "sleep", lambda s: None)
        monkeypatch.setattr(
            dl.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=1, stdout="", stderr="starting up"))
        assert dl.postgres_data_state(cfg, attempts=3, delay=0) == "unknown"

    def test_retries_a_starting_postgres_instead_of_declaring_it_empty(
        self, cfg, monkeypatch,
    ):
        # Une base qui demarre n'est pas une base vide : la sonde attend, comme
        # `until pg_isready` le fait cote k3s (backup-job.yaml). Sans cette
        # attente, le flux nominal `docker compose down` + `--apply` sur une
        # base peuplee tomberait en "unknown" et avorterait a chaque fois.
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        slept = []
        monkeypatch.setattr(dl.time, "sleep", lambda s: slept.append(s))
        answers = [
            MagicMock(returncode=1, stdout="", stderr="the database system is starting up"),
            MagicMock(returncode=1, stdout="", stderr="the database system is starting up"),
            MagicMock(returncode=0, stdout="1\n", stderr=""),
        ]
        monkeypatch.setattr(dl.subprocess, "run", lambda cmd, **kw: answers.pop(0))
        assert dl.postgres_data_state(cfg, attempts=5, delay=2) == "has_data"
        assert slept == [2, 2], "la sonde doit patienter entre deux tentatives"

    def test_unknown_when_docker_missing(self, cfg, monkeypatch):
        monkeypatch.setattr(dl, "find_docker", lambda: None)
        called = []
        monkeypatch.setattr(dl.subprocess, "run", lambda cmd, **kw: called.append(cmd))
        assert dl.postgres_data_state(cfg) == "unknown"
        assert called == []

    def test_never_puts_a_password_in_the_psql_argv(self, cfg, monkeypatch):
        MARKER = "s3ntinel-pw-marker"
        monkeypatch.setenv("POSTGRES_PASSWORD", MARKER)
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dl.subprocess, "run", fake_run)
        dl.postgres_data_state(cfg, attempts=1)
        for arg in captured["cmd"]:
            assert MARKER not in arg

    def test_queries_via_local_socket_no_host_flag_same_as_backup_postgres(
        self, cfg, monkeypatch,
    ):
        # Meme postulat que backup_postgres() (auth locale par socket unix) :
        # jamais de `-h` dans l'invocation psql.
        monkeypatch.setattr(dl, "find_docker", lambda: "/usr/bin/docker")
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dl.subprocess, "run", fake_run)
        dl.postgres_data_state(cfg, attempts=1)
        assert "-h" not in captured["cmd"]
        assert "psql" in captured["cmd"]
        assert "-U" in captured["cmd"] and cfg.meta.project_name in captured["cmd"]


class TestBackupWiredIntoApply:
    def _mocks(self, tmp_path, minimal_config_dict, monkeypatch):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.safe_dump(minimal_config_dict))
        secrets = tmp_path / ".env.secrets"
        secrets.write_text("X=1")
        monkeypatch.setattr(dl, "SECRETS_FILE", secrets)
        monkeypatch.setattr(dl, "COMPOSE_FILE", tmp_path / "docker-compose.local.yml")
        monkeypatch.setattr(dl, "CADDYFILE", tmp_path / "Caddyfile")
        monkeypatch.setattr(dl, "_run_bootstrap", lambda cfg: None)
        return cfg_file

    def test_update_backs_up_before_the_app_tier_comes_up(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # "Update" == Postgres ALREADY has an initialized schema (B4 :
        # `postgres_data_state()`, PAS `stack_running()` -- une stack
        # ARRETEE puis `--apply` (down + apply, flux normal) a quand meme des
        # donnees a proteger). database_mode reste "local" par defaut.
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "has_data")
        # A1 : preuve d'ORDRE reelle, pas un index d'enumerate (toujours >= 0).
        # Un sentinel PARTAGE entre le faux backup_postgres et le faux
        # run_compose enregistre le RANG relatif des deux evenements.
        order = []
        monkeypatch.setattr(
            dl, "backup_postgres",
            lambda cfg, **kw: (order.append("backup") or (True, "ok: /tmp/x")))

        def fake_run_compose(args, **kw):
            if "db-init" in args:
                order.append("app_tier")
            return 0

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=True), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", side_effect=fake_run_compose):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 0
        assert order == ["backup", "app_tier"], (
            "backup_postgres doit tourner AVANT le bring-up de l'app tier "
            "(db-init lance les migrations Alembic juste apres) -- ordre "
            f"observe : {order}")

    def test_fresh_install_never_calls_backup(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # Rien a sauvegarder a la 1ere installation (meme decision que
        # backup-job.yaml, hook pre-upgrade SEULEMENT) : une base neuve n'a
        # encore AUCUNE table -- postgres_data_state() renvoie False.
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        calls = []
        monkeypatch.setattr(dl, "backup_postgres", lambda cfg, **kw: (calls.append(cfg) or (True, "ok")))
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "empty")
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=False), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", return_value=0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 0
        assert calls == []

    def test_probe_failure_aborts_the_apply_before_db_init(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # SEC-001 / C1 (revue E2) -- LE test de la gate. Quand la sonde ne peut
        # PAS repondre ("unknown"), on ne sait pas si la base est pleine. La
        # version booleenne repondait False => sauvegarde sautee => `db-init`
        # (alembic upgrade head) migrait quand meme une base peut-etre peuplee,
        # sans dump, sans message. C'est fail-OPEN, et c'est la negation exacte
        # du contrat de ce lot.
        #
        # Preuve par MUTATION, pas par code de retour : on assert que `db-init`
        # n'apparait dans AUCUNE invocation compose. Rendre la migration
        # inatteignable est l'invariant ; rc=1 n'en est que le symptome.
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        calls = []
        monkeypatch.setattr(dl, "backup_postgres", lambda cfg, **kw: (calls.append(cfg) or (True, "ok")))
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "unknown")
        composed = []

        def fake_run_compose(args, **kw):
            composed.append(list(args))
            return 0

        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=True), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", side_effect=fake_run_compose):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])

        assert rc == 1, "une sonde muette doit AVORTER l'update (fail-closed)"
        assert calls == [], "rien a sauvegarder n'est pas etabli -- ne pas pretendre l'avoir fait"
        assert not any("db-init" in args for args in composed), (
            "la migration Alembic ne doit JAMAIS etre atteinte quand on ignore "
            f"si la base contient des donnees -- invocations compose : {composed}")

    def test_stopped_stack_with_existing_data_still_backs_up(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # B4 (le bug reel) : `docker compose down` (ou un reboot) PUIS
        # `--apply` est le flux d'update le plus naturel -- `stack_running()`
        # vaut False ici, alors qu'il y a bel et bien des donnees existantes
        # (postgres_data_state()=True). L'ancien gate (`was_running`)
        # aurait saute la sauvegarde ; celui-ci ne doit PAS le faire.
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        calls = []
        monkeypatch.setattr(dl, "backup_postgres", lambda cfg, **kw: (calls.append(cfg) or (True, "ok")))
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "has_data")
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=False), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", return_value=0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 0
        assert len(calls) == 1, (
            "une stack ARRETEE avec des donnees existantes doit quand meme "
            "declencher la sauvegarde -- stack_running()=False n'est pas "
            "synonyme de 'rien a proteger'")

    def test_external_database_mode_never_calls_backup(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # database_mode=external : aucun conteneur Postgres facil-manage a
        # sauvegarder par ce chemin (la base vit ailleurs) -- pas de fausse
        # confiance en pretendant sauvegarder quelque chose qu'on ne peut
        # pas atteindre ainsi. postgres_data_state() force a True pour
        # prouver que c'est bien le garde database_mode qui bloque ici, pas
        # une coincidence de valeur par defaut.
        minimal_config_dict["docker_local"] = {"database_mode": "external"}
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        calls = []
        monkeypatch.setattr(dl, "backup_postgres", lambda cfg, **kw: (calls.append(cfg) or (True, "ok")))
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "has_data")
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=True), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose", return_value=0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 0
        assert calls == []

    def test_failed_backup_aborts_the_apply_before_app_tier_comes_up(
        self, tmp_path, minimal_config_dict, monkeypatch,
    ):
        # Fail-closed : une sauvegarde ratee doit EMPECHER l'update (pas
        # juste avertir) -- db-init (migrations Alembic) ne doit jamais
        # demarrer si la sauvegarde a echoue.
        cfg_file = self._mocks(tmp_path, minimal_config_dict, monkeypatch)
        monkeypatch.setattr(dl, "backup_postgres",
                            lambda cfg, **kw: (False, "pg_dump a echoue: boom"))
        monkeypatch.setattr(dl, "postgres_data_state", lambda cfg, **kw: "has_data")
        run_compose_calls = []
        with patch("docker_local.find_docker", return_value="/usr/bin/docker"), \
             patch("docker_local.docker_compose_available", return_value=True), \
             patch("docker_local.stack_running", return_value=True), \
             patch("docker_local.subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("docker_local.run_compose",
                   side_effect=lambda args, **kw: run_compose_calls.append(args) or 0):
            rc = dl.main(["--config", str(cfg_file), "--apply", "--yes"])
        assert rc == 1
        assert not any("db-init" in args for args in run_compose_calls), (
            "l'app tier (db-init/backend/frontend) ne doit jamais demarrer "
            "quand la sauvegarde pre-update a echoue")


class TestOpenbaoRequiredGate:
    def _openbao_cfg(self, minimal_config_dict):
        minimal_config_dict["secrets"] = {"provider": "openbao"}
        return vc.DeployConfig.model_validate(minimal_config_dict)

    def test_env_file_mode_never_gates(self, cfg):
        # default provider != openbao -> failed/absent state is irrelevant
        assert dl._openbao_required_but_failed(cfg, _state("failed")) is False
        assert dl._openbao_required_but_failed(cfg, None) is False

    def test_openbao_ok_passes(self, minimal_config_dict):
        cfg = self._openbao_cfg(minimal_config_dict)
        assert dl._openbao_required_but_failed(cfg, _state("ok")) is False

    def test_openbao_failed_aborts(self, minimal_config_dict):
        cfg = self._openbao_cfg(minimal_config_dict)
        assert dl._openbao_required_but_failed(cfg, _state("failed")) is True

    def test_openbao_missing_step_aborts(self, minimal_config_dict):
        cfg = self._openbao_cfg(minimal_config_dict)
        assert dl._openbao_required_but_failed(cfg, _state(None)) is True

    def test_openbao_no_state_aborts(self, minimal_config_dict):
        cfg = self._openbao_cfg(minimal_config_dict)
        assert dl._openbao_required_but_failed(cfg, None) is True
