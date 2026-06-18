#!/usr/bin/env python3
"""Phase B4 tests — Postgres extensions provisioner, mocked (no live psql).

Seam: ``postgres.exec_in``. The fake answers the ``SELECT extname`` probe and
records ``CREATE EXTENSION`` statements, so we assert that only missing
extensions are created (idempotency) without a database.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROVIDERS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

from bootstrap import postgres as pg  # noqa: E402
from bootstrap.context import BootstrapContext, vc  # noqa: E402
from bootstrap.docker_helpers import ContainerInfo, DockerError  # noqa: E402
from bootstrap.state import BootstrapState, ProvisionStep  # noqa: E402

_BASE_CONFIG = {
    "meta": {"config_version": 1, "project_name": "facil", "environment": "development"},
    "database": {"url_secret": "database-url"},
    "redis": {"url_secret": "REDIS_URL"},
    "auth": {"jwt_secret_name": "JWT", "app_secret_name": "SK",
             "totp_encryption_secret": "TOTP"},
    "firebase": {"project_id": "x", "storage_bucket": "x"},
    "ai": {"gemini_api_key_secret": "G"},
    "server": {"frontend_url": "http://localhost:3000",
               "api_base_url": "http://localhost:8080"},
    "cron": {"secret_name": "CRON"},
}


def make_cfg(**overrides) -> vc.DeployConfig:
    raw = copy.deepcopy(_BASE_CONFIG)
    for k, v in overrides.items():
        raw[k] = {**raw.get(k, {}), **v} if isinstance(v, dict) else v
    return vc.DeployConfig.model_validate(raw)


class FakePsql:
    def __init__(self, existing=(), fail_on_create=False, role_exists=False,
                 password_valid=True):
        self.existing = "\n".join(existing)
        self.fail_on_create = fail_on_create
        self.role_exists = role_exists
        self.password_valid = password_valid   # does the verify probe succeed?
        self.creates: list[str] = []
        self.role_sql: list[str] = []   # CREATE ROLE / ALTER ROLE statements
        self.verified = False           # was the password verification probe run?

    def __call__(self, container, cmd, *, timeout=60, check=True, env=None):
        sql = cmd[-1]
        if env and "PGPASSWORD" in env:        # password verification probe (S3)
            self.verified = True
            return SimpleNamespace(stdout="1" if self.password_valid else "",
                                   returncode=0 if self.password_valid else 2)
        if sql.startswith("SELECT extname"):
            return SimpleNamespace(stdout=self.existing, returncode=0)
        if sql.startswith("SELECT 1 FROM pg_roles"):
            return SimpleNamespace(stdout="1" if self.role_exists else "", returncode=0)
        if sql.startswith("CREATE EXTENSION"):
            if self.fail_on_create:
                raise DockerError("boom")
            self.creates.append(sql)
            return SimpleNamespace(stdout="", returncode=0)
        if sql.startswith(("CREATE ROLE", "ALTER ROLE")):
            self.role_sql.append(sql)
            return SimpleNamespace(stdout="", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)   # grants, etc.


@pytest.fixture
def ctx() -> BootstrapContext:
    return BootstrapContext(
        cfg=make_cfg(), network="net",
        containers={"postgres": ContainerInfo("facil-postgres-1", "net", "healthy", True)},
    )


def _patch(monkeypatch, fake):
    monkeypatch.setattr(pg, "exec_in", fake)


# ---------------------------------------------------------------------------

def test_is_applicable():
    assert pg.is_applicable(make_cfg()) is True
    assert pg.is_applicable(make_cfg(docker_local={"database_mode": "external"})) is False


def test_fresh_creates_all_three(monkeypatch, ctx):
    fake = FakePsql(existing=())
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert step.status == "ok"
    created = [s.split('"')[1] for s in fake.creates]
    assert created == ["vector", "pg_trgm", "uuid-ossp"]


def test_only_missing_created(monkeypatch, ctx):
    fake = FakePsql(existing=("plpgsql", "vector"))
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    created = [s.split('"')[1] for s in fake.creates]
    assert created == ["pg_trgm", "uuid-ossp"]          # vector skipped
    assert any("'vector' already present" in a for a in step.actions)


def test_uuid_ossp_is_quoted(monkeypatch, ctx):
    fake = FakePsql(existing=())
    _patch(monkeypatch, fake)
    pg.provision(ctx)
    assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' in fake.creates


def test_dry_run_mutates_nothing(monkeypatch):
    fake = FakePsql()
    _patch(monkeypatch, fake)
    dctx = BootstrapContext(cfg=make_cfg(), network="net", dry_run=True)
    step = pg.provision(dctx)
    assert fake.creates == []
    assert step.status == "skipped"
    assert len(step.actions) == 4          # 3 extensions + app role line
    assert any("_app" in a for a in step.actions)


def test_missing_container_fails(monkeypatch):
    fake = FakePsql()
    _patch(monkeypatch, fake)
    c = BootstrapContext(cfg=make_cfg(), network="net", containers={})
    step = pg.provision(c)
    assert step.status == "failed"
    assert "not resolved" in step.detail


def test_psql_error_becomes_failed_step(monkeypatch, ctx):
    fake = FakePsql(existing=(), fail_on_create=True)
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert step.status == "failed"
    assert "psql operation failed" in step.detail


# --- H2: least-privilege app role ---

def _ctx_with_state(tmp_path):
    (tmp_path / "deploy").mkdir()
    return BootstrapContext(
        cfg=make_cfg(), network="net", repo_root=tmp_path,
        containers={"postgres": ContainerInfo("facil-postgres-1", "net", "healthy", True)},
    )


def test_app_role_created_fresh(monkeypatch, tmp_path):
    ctx = _ctx_with_state(tmp_path)
    fake = FakePsql(existing=(), role_exists=False)
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert step.status == "ok"
    assert any(s.startswith("CREATE ROLE facil_app") for s in fake.role_sql)
    assert step.secrets["pg_app_role"] == "facil_app"
    assert len(step.secrets["pg_app_password"]) >= 20
    assert step.secrets["pg_app_db"] == "facil"


def test_app_role_is_nosuperuser(monkeypatch, tmp_path):
    ctx = _ctx_with_state(tmp_path)
    fake = FakePsql(role_exists=False)
    _patch(monkeypatch, fake)
    pg.provision(ctx)
    create = next(s for s in fake.role_sql if s.startswith("CREATE ROLE"))
    assert "NOSUPERUSER" in create and "NOCREATEDB" in create and "NOCREATEROLE" in create


def test_app_role_password_reused(monkeypatch, tmp_path):
    ctx = _ctx_with_state(tmp_path)
    BootstrapState(project="facil", storage_provider="minio",
                   secrets_provider="openbao", database_mode="local",
                   steps=[ProvisionStep(name="postgres", status="ok",
                                        secrets={"pg_app_password": "REUSEME01234567890"})]
                   ).save(ctx.state_file)
    fake = FakePsql(role_exists=True, password_valid=True)
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert fake.verified is True                      # S3: password was verified
    assert fake.role_sql == []                       # neither created nor altered
    assert step.secrets["pg_app_password"] == "REUSEME01234567890"
    assert any("reused (verified)" in a for a in step.actions)


def test_app_role_rotated_when_state_password_stale(monkeypatch, tmp_path):
    """S3: a state password that no longer authenticates IS rotated (not reused)."""
    ctx = _ctx_with_state(tmp_path)
    BootstrapState(project="facil", storage_provider="minio",
                   secrets_provider="openbao", database_mode="local",
                   steps=[ProvisionStep(name="postgres", status="ok",
                                        secrets={"pg_app_password": "STALEpw0123456789"})]
                   ).save(ctx.state_file)
    fake = FakePsql(role_exists=True, password_valid=False)   # verify fails
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert fake.verified is True
    assert any(s.startswith("ALTER ROLE facil_app") for s in fake.role_sql)
    assert any("no longer valid" in a for a in step.actions)
    assert step.secrets["pg_app_password"] != "STALEpw0123456789"   # fresh pw


def test_app_role_rotated_when_prior_unknown(monkeypatch, tmp_path):
    ctx = _ctx_with_state(tmp_path)        # role exists but no state file (no prior pw)
    fake = FakePsql(role_exists=True)
    _patch(monkeypatch, fake)
    step = pg.provision(ctx)
    assert fake.verified is False                    # nothing to verify (no prior)
    assert any(s.startswith("ALTER ROLE facil_app") for s in fake.role_sql)
    assert any("no prior password in state" in a for a in step.actions)


def test_app_role_grants_include_default_privileges(monkeypatch, tmp_path):
    ctx = _ctx_with_state(tmp_path)
    grants = pg._grants("facil_app", "facil")
    assert any("ALTER DEFAULT PRIVILEGES" in g for g in grants)   # future tables
    assert any(g.startswith("GRANT CONNECT") for g in grants)
    # no DDL/superuser grant
    assert all("SUPERUSER" not in g and "CREATE ON" not in g for g in grants)
