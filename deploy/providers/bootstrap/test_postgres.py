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
    def __init__(self, existing=(), fail_on_create=False):
        self.existing = "\n".join(existing)
        self.fail_on_create = fail_on_create
        self.creates: list[str] = []

    def __call__(self, container, cmd, *, timeout=60, check=True):
        sql = cmd[-1]
        if sql.startswith("SELECT extname"):
            return SimpleNamespace(stdout=self.existing, returncode=0)
        if sql.startswith("CREATE EXTENSION"):
            if self.fail_on_create:
                raise DockerError("boom")
            self.creates.append(sql)
            return SimpleNamespace(stdout="", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)


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
    assert len(step.actions) == 3


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
