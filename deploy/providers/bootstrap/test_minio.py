#!/usr/bin/env python3
"""Phase B2 tests — MinIO provisioner, fully mocked (no live MinIO).

The single seam is ``minio.run_oneshot``; a fake records every ``mc`` call and
drives service-account existence, so we assert the exact idempotent behaviour
(create / reuse / rotate) without a container.
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

from bootstrap import minio as mn  # noqa: E402
from bootstrap.context import BootstrapContext, vc  # noqa: E402
from bootstrap.docker_helpers import DockerError  # noqa: E402
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


class FakeMC:
    """Stand-in for run_oneshot: records calls, controls svcacct existence."""

    def __init__(self, svcacct_exists=False, fail_on=None):
        self.calls: list[dict] = []
        self.svcacct_exists = svcacct_exists
        self.fail_on = fail_on  # substring of args that should raise DockerError

    def __call__(self, image, args, *, network, env, entrypoint=None,
                 check=True, timeout=120):
        self.calls.append({"args": args, "entrypoint": entrypoint,
                           "env": env, "check": check})
        if self.fail_on and any(self.fail_on in a for a in args):
            raise DockerError(f"boom on {self.fail_on}")
        if args[:4] == ["admin", "user", "svcacct", "info"]:
            return SimpleNamespace(returncode=0 if self.svcacct_exists else 1,
                                   stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def verbs(self) -> list:
        """First token of each recorded call (the mc subcommand or '-c')."""
        return [c["args"][0] for c in self.calls]


@pytest.fixture
def ctx(tmp_path: Path) -> BootstrapContext:
    (tmp_path / "deploy").mkdir()
    return BootstrapContext(cfg=make_cfg(), network="net", repo_root=tmp_path)


def _patch(monkeypatch, fake: FakeMC):
    monkeypatch.setattr(mn, "run_oneshot", fake)


# ---------------------------------------------------------------------------

def test_is_applicable():
    assert mn.is_applicable(make_cfg(storage={"provider": "minio"})) is True
    assert mn.is_applicable(make_cfg(storage={"provider": "s3"})) is False


def test_scoped_policy_single_bucket():
    pol = mn.scoped_policy("facil-documents")
    resources = [r for s in pol["Statement"] for r in s["Resource"]]
    assert resources == ["arn:aws:s3:::facil-documents/*",
                         "arn:aws:s3:::facil-documents"]
    # no wildcard bucket access
    assert all("*/*" not in r and r != "arn:aws:s3:::*" for r in resources)


def test_fresh_provision_creates_everything(monkeypatch, ctx):
    fake = FakeMC(svcacct_exists=False)
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert step.status == "ok"
    # bucket make, version enable, anonymous set, svcacct info, svcacct add(sh -c)
    assert fake.verbs() == ["mb", "version", "anonymous", "admin", "-c"]
    assert step.secrets["minio_access_key"] == "facil-backend"
    assert len(step.secrets["minio_secret_key"]) == 40   # token_hex(20)
    assert step.secrets["minio_bucket"] == "facil-documents"


def test_secret_passed_via_env_not_argv(monkeypatch, ctx):
    fake = FakeMC()
    _patch(monkeypatch, fake)
    mn.provision(ctx)
    # root password travels in MC_HOST_facil env, never as a bare mc arg.
    for call in fake.calls:
        assert "MC_HOST_facil" in call["env"]
        assert "facilminio" in call["env"]["MC_HOST_facil"]


def test_idempotent_reuse_when_secret_known(monkeypatch, ctx):
    # Pre-seed state as if a prior run created the SA.
    prior = BootstrapState(project="facil", storage_provider="minio",
                           secrets_provider="env_file", database_mode="local",
                           steps=[ProvisionStep(name="minio", status="ok",
                                                secrets={"minio_secret_key": "KNOWN" * 8})])
    prior.save(ctx.state_file)
    fake = FakeMC(svcacct_exists=True)
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert step.status == "ok"
    assert step.secrets["minio_secret_key"] == "KNOWN" * 8       # reused, stable
    assert "-c" not in fake.verbs()                              # no svcacct add
    assert any("reused" in a for a in step.actions)


def test_rotates_when_exists_but_secret_unknown(monkeypatch, ctx):
    fake = FakeMC(svcacct_exists=True)          # exists, but no prior state file
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert step.status == "ok"
    # rm (rotation) then re-add via sh -c
    assert "rm" in [c["args"][3] if c["args"][:3] == ["admin", "user", "svcacct"]
                    else "" for c in fake.calls]
    assert "-c" in fake.verbs()
    assert any("rotated" in a for a in step.actions)


def test_dry_run_mutates_nothing(monkeypatch, tmp_path):
    fake = FakeMC()
    _patch(monkeypatch, fake)
    dctx = BootstrapContext(cfg=make_cfg(), network="net",
                            repo_root=tmp_path, dry_run=True)
    step = mn.provision(dctx)
    assert fake.calls == []
    assert step.status == "skipped"
    assert any("scoped service account" in a for a in step.actions)


def test_docker_error_becomes_failed_step(monkeypatch, ctx):
    fake = FakeMC(fail_on="mb")
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert step.status == "failed"
    assert "mc operation failed" in step.detail
