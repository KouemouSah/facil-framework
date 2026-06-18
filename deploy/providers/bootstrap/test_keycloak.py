#!/usr/bin/env python3
"""K1 tests — Keycloak bootstrap provisioner, mocked (no live Keycloak).

Seam: ``provision_keycloak.provision`` (the idempotent realm/client automation).
We assert applicability + that the provisioner captures the OIDC connection facts
(split-horizon issuer/jwks + confidential client_secret) into the step secrets.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

PROVIDERS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import provision_keycloak as pk  # noqa: E402
from bootstrap import keycloak as kc  # noqa: E402
from bootstrap.context import BootstrapContext, vc  # noqa: E402

_BASE_CONFIG = {
    "meta": {"config_version": 1, "project_name": "facil", "environment": "development"},
    "database": {"url_secret": "database-url"},
    "redis": {"url_secret": "REDIS_URL"},
    "auth": {"jwt_secret_name": "JWT", "app_secret_name": "SK",
             "totp_encryption_secret": "TOTP",
             "keycloak": {"enabled": True}},   # K opt-in for these tests
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


@pytest.fixture
def ctx(tmp_path) -> BootstrapContext:
    (tmp_path / "deploy").mkdir()
    (tmp_path / ".env.secrets").write_text("KEYCLOAK_ADMIN_PASSWORD=s3cret\n",
                                            encoding="utf-8")
    return BootstrapContext(cfg=make_cfg(), network="net", repo_root=tmp_path)


def test_is_applicable():
    # default agent_methods = ["keycloak_oidc"]
    assert kc.is_applicable(make_cfg()) is True
    assert kc.is_applicable(make_cfg(
        auth={"jwt_secret_name": "J", "app_secret_name": "S",
              "totp_encryption_secret": "T",
              "citizen_methods": ["native"], "agent_methods": ["native"]})) is False


def test_provision_captures_oidc_facts(monkeypatch, ctx):
    captured = {}

    def fake_provision(server, realm, admin_user, admin_pw, client_id, groups, *,
                       public_client=False):
        captured.update(server=server, realm=realm, admin_pw=admin_pw,
                        client_id=client_id, groups=groups, public=public_client)
        return {"realm": realm, "client": client_id, "created_realm": True,
                "created_client": True, "groups": groups, "mappers": ["groups", "org"],
                "client_secret": "SEKRET-123"}

    monkeypatch.setattr(pk, "provision", fake_provision)
    step = kc.provision(ctx)

    assert step.status == "ok"
    assert captured["admin_pw"] == "s3cret"           # read from .env.secrets
    assert captured["public"] is False                # confidential client
    s = step.secrets
    assert s["oidc_issuer"] == "http://localhost:8088/realms/facil"   # browser-facing
    assert s["oidc_jwks_uri"].startswith("http://keycloak:8080/realms/facil/")  # in-net
    assert s["oidc_client_id"] == "facil-backend"
    assert s["oidc_audience"] == "facil-backend"
    assert s["oidc_client_secret"] == "SEKRET-123"


def test_provision_warns_without_secret(monkeypatch, ctx):
    monkeypatch.setattr(pk, "provision",
                        lambda *a, **k: {"realm": "facil", "client": "facil-backend"})
    step = kc.provision(ctx)
    assert step.status == "ok"
    assert step.secrets["oidc_client_secret"] == ""
    assert any("no client_secret" in a for a in step.actions)


def test_provision_failure_is_failed_step(monkeypatch, ctx):
    def boom(*a, **k):
        raise RuntimeError("admin login 401")
    monkeypatch.setattr(pk, "provision", boom)
    step = kc.provision(ctx)
    assert step.status == "failed"
    assert "Keycloak provisioning failed" in step.detail


def test_dry_run_mutates_nothing(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(pk, "provision", lambda *a, **k: called.append(a))
    dctx = BootstrapContext(cfg=make_cfg(), network="net", repo_root=tmp_path,
                            dry_run=True)
    step = kc.provision(dctx)
    assert called == []
    assert step.status == "skipped"
