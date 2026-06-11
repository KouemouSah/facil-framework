#!/usr/bin/env python3
"""Phase B3 tests — OpenBao provisioner, fully mocked (no live OpenBao).

The single seam is ``openbao._request``; a fake router answers each API call so
we assert the idempotent behaviour (mount / write-if-changed / reuse secret-id)
without a server.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

PROVIDERS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

from bootstrap import openbao as ob  # noqa: E402
from bootstrap.context import BootstrapContext, vc  # noqa: E402
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
    "secrets": {"provider": "openbao"},
}


def make_cfg(**overrides) -> vc.DeployConfig:
    raw = copy.deepcopy(_BASE_CONFIG)
    for k, v in overrides.items():
        raw[k] = {**raw.get(k, {}), **v} if isinstance(v, dict) else v
    return vc.DeployConfig.model_validate(raw)


class FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeBao:
    """Routes OpenBao API calls by the path after '/v1'."""

    def __init__(self, kv_mounted=False, approle_enabled=False, boot_current=None,
                 raise_on=None):
        self.kv_mounted = kv_mounted
        self.approle_enabled = approle_enabled
        self.boot_current = boot_current  # dict or None (404)
        self.raise_on = raise_on          # path substring -> raise
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, token, *, json=None, allow=()):
        path = url.split("/v1", 1)[1]
        self.calls.append((method, path))
        if self.raise_on and self.raise_on in path:
            raise ob.OpenBaoError(f"boom {path}")
        if path == "/sys/mounts":
            data = {"facil/": {}} if self.kv_mounted else {"secret/": {}}
            return FakeResp(200, {"data": data})
        if path == "/sys/auth":
            data = {"approle/": {}} if self.approle_enabled else {"token/": {}}
            return FakeResp(200, {"data": data})
        if path == "/facil/data/boot" and method == "GET":
            if self.boot_current is None:
                return FakeResp(404, {})
            return FakeResp(200, {"data": {"data": self.boot_current}})
        if path.endswith("/role-id"):
            return FakeResp(200, {"data": {"role_id": "RID-123"}})
        if path.endswith("/secret-id"):
            return FakeResp(200, {"data": {"secret_id": "SID-456"}})
        return FakeResp(204, {})

    def methods_to(self, substr) -> list[str]:
        return [m for m, p in self.calls if substr in p]


@pytest.fixture
def ctx(tmp_path: Path) -> BootstrapContext:
    (tmp_path / "deploy").mkdir()
    (tmp_path / ".env.secrets").write_text(
        "JWT_SECRET_KEY=jwt\nSECRET_KEY=sk\nTOTP_ENCRYPTION_KEY=totp\n"
        "CRON_SECRET=cron\nRECEIPT_VERIFICATION_SECRET=rcpt\n"
        "GEMINI_API_KEY=\n",  # empty integration secret — must be ignored
        encoding="utf-8",
    )
    return BootstrapContext(cfg=make_cfg(), network="net", repo_root=tmp_path)


def _patch(monkeypatch, fake):
    monkeypatch.setattr(ob, "_request", fake)


# ---------------------------------------------------------------------------

def test_is_applicable():
    assert ob.is_applicable(make_cfg(secrets={"provider": "openbao"})) is True
    assert ob.is_applicable(make_cfg(secrets={"provider": "env_file"})) is False


def test_fresh_provision(monkeypatch, ctx):
    fake = FakeBao(kv_mounted=False, approle_enabled=False, boot_current=None)
    _patch(monkeypatch, fake)
    step = ob.provision(ctx)
    assert step.status == "ok"
    # mounts kv, writes boot, policy, approle, role, role-id, secret-id
    assert ("POST", "/sys/mounts/facil") in fake.calls
    assert ("POST", "/facil/data/boot") in fake.calls
    assert ("PUT", "/sys/policies/acl/facil-backend") in fake.calls
    assert ("POST", "/sys/auth/approle") in fake.calls
    assert step.secrets["openbao_role_id"] == "RID-123"
    assert step.secrets["openbao_secret_id"] == "SID-456"
    assert step.secrets["openbao_kv_path"] == "facil"


def test_only_five_boot_secrets_written(monkeypatch, ctx):
    captured = {}

    def fake(method, url, token, *, json=None, allow=()):
        if url.endswith("/facil/data/boot") and method == "POST":
            captured["data"] = json["data"]
        return FakeBao(boot_current=None)(method, url, token, json=json, allow=allow)

    _patch(monkeypatch, fake)
    ob.provision(ctx)
    # empty GEMINI_API_KEY must be excluded; only the 5 boot keys present.
    assert set(captured["data"]) == set(ob.BOOT_SECRET_KEYS)


def test_kv_already_mounted_skips_mount(monkeypatch, ctx):
    fake = FakeBao(kv_mounted=True)
    _patch(monkeypatch, fake)
    step = ob.provision(ctx)
    assert ("POST", "/sys/mounts/facil") not in fake.calls
    assert any("already mounted" in a for a in step.actions)


def test_boot_secrets_idempotent_when_unchanged(monkeypatch, ctx):
    desired = {"JWT_SECRET_KEY": "jwt", "SECRET_KEY": "sk",
               "TOTP_ENCRYPTION_KEY": "totp", "CRON_SECRET": "cron",
               "RECEIPT_VERIFICATION_SECRET": "rcpt"}
    fake = FakeBao(kv_mounted=True, boot_current=desired)
    _patch(monkeypatch, fake)
    step = ob.provision(ctx)
    assert ("POST", "/facil/data/boot") not in fake.calls   # no rewrite
    assert any("up to date" in a for a in step.actions)


def test_secret_id_reused_from_state(monkeypatch, ctx):
    prior = BootstrapState(project="facil", storage_provider="minio",
                           secrets_provider="openbao", database_mode="local",
                           steps=[ProvisionStep(name="openbao", status="ok",
                                                secrets={"openbao_secret_id": "OLD-SID"})])
    prior.save(ctx.state_file)
    fake = FakeBao(kv_mounted=True, approle_enabled=True, boot_current=None)
    _patch(monkeypatch, fake)
    step = ob.provision(ctx)
    assert step.secrets["openbao_secret_id"] == "OLD-SID"
    assert not fake.methods_to("/secret-id")     # never generated a new one
    assert any("reused" in a for a in step.actions)


def test_dry_run_mutates_nothing(monkeypatch, tmp_path):
    calls = []
    _patch(monkeypatch, lambda *a, **k: calls.append(a) or FakeResp())
    dctx = BootstrapContext(cfg=make_cfg(), network="net",
                            repo_root=tmp_path, dry_run=True)
    step = ob.provision(dctx)
    assert calls == []
    assert step.status == "skipped"


def test_api_error_becomes_failed_step(monkeypatch, ctx):
    fake = FakeBao(raise_on="/sys/mounts")
    _patch(monkeypatch, fake)
    step = ob.provision(ctx)
    assert step.status == "failed"
    assert "OpenBao API error" in step.detail


# --- H3: runtime secrets mirror ---

def test_runtime_secrets_mirrored(monkeypatch, tmp_path):
    (tmp_path / "deploy").mkdir()
    (tmp_path / ".env.secrets").write_text(
        "JWT_SECRET_KEY=j\nSECRET_KEY=s\nTOTP_ENCRYPTION_KEY=t\n"
        "CRON_SECRET=c\nRECEIPT_VERIFICATION_SECRET=r\n"
        "POSTGRES_PASSWORD=pgpw\nREDIS_PASSWORD=rdpw\nMINIO_ROOT_PASSWORD=miopw\n",
        encoding="utf-8",
    )
    ctx = BootstrapContext(cfg=make_cfg(), network="net", repo_root=tmp_path)
    captured = {}

    def fake(method, url, token, *, json=None, allow=()):
        if url.endswith("/facil/data/runtime") and method == "POST":
            captured["data"] = json["data"]
        return FakeBao(kv_mounted=True, boot_current=None)(
            method, url, token, json=json, allow=allow)

    monkeypatch.setattr(ob, "_request", fake)
    step = ob.provision(ctx)
    assert step.status == "ok"
    assert set(captured["data"]) == set(ob.RUNTIME_SECRET_KEYS)
    assert captured["data"]["REDIS_PASSWORD"] == "rdpw"


def test_runtime_mirror_skipped_when_absent(monkeypatch, ctx):
    # ctx fixture .env.secrets has no runtime passwords -> nothing mirrored.
    fake = FakeBao(kv_mounted=True, boot_current=None)
    monkeypatch.setattr(ob, "_request", fake)
    step = ob.provision(ctx)
    assert ("POST", "/facil/data/runtime") not in fake.calls
    assert any("no runtime secrets" in a for a in step.actions)
