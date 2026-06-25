#!/usr/bin/env python3
"""Phase B2 tests — MinIO provisioner, fully mocked (no live MinIO).

The single seam is ``minio.run_oneshot``; a fake records every ``mc`` call and
drives service-account existence, so we assert the exact idempotent behaviour
(create / reuse / rotate) without a container.
"""

from __future__ import annotations

import copy
import json
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

    def __init__(self, svcacct_exists=False, fail_on=None,
                 existing_noncurrent_days=(), existing_quota_bytes=0):
        self.calls: list[dict] = []
        self.svcacct_exists = svcacct_exists
        self.fail_on = fail_on  # substring of args that should raise DockerError
        self.existing_noncurrent_days = list(existing_noncurrent_days)
        self.existing_quota_bytes = existing_quota_bytes

    def __call__(self, image, args, *, network, env, entrypoint=None,
                 check=True, timeout=120):
        self.calls.append({"args": args, "entrypoint": entrypoint,
                           "env": env, "check": check})
        if self.fail_on and any(self.fail_on in a for a in args):
            raise DockerError(f"boom on {self.fail_on}")
        if args[:4] == ["admin", "user", "svcacct", "info"]:
            return SimpleNamespace(returncode=0 if self.svcacct_exists else 1,
                                   stdout="", stderr="")
        if args[:3] == ["ilm", "rule", "ls"]:
            rules = [{"NoncurrentVersionExpiration": {"NoncurrentDays": d}}
                     for d in self.existing_noncurrent_days]
            return SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({"config": {"Rules": rules}}))
        if args[:2] == ["quota", "info"]:
            return SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({"quota": self.existing_quota_bytes}))
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


def test_scoped_policy_compliance_has_no_delete():
    pol = mn.scoped_policy("facil-documents", "facil-compliance")
    # Object-level statements keyed by bucket.
    doc_actions = next(s["Action"] for s in pol["Statement"]
                       if s["Resource"] == ["arn:aws:s3:::facil-documents/*"])
    comp_actions = next(s["Action"] for s in pol["Statement"]
                        if s["Resource"] == ["arn:aws:s3:::facil-compliance/*"])
    assert "s3:DeleteObject" in doc_actions            # documents: full rw
    assert "s3:DeleteObject" not in comp_actions        # compliance: write-once
    assert "s3:PutObject" in comp_actions               # but can write
    assert "s3:PutObjectRetention" in comp_actions      # and set retention
    # still no access to any other bucket
    all_res = [r for s in pol["Statement"] for r in s["Resource"]]
    assert all("facil-documents" in r or "facil-compliance" in r for r in all_res)


def test_fresh_provision_creates_everything(monkeypatch, ctx):
    fake = FakeMC(svcacct_exists=False)
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert step.status == "ok"
    # documents: mb, version, anonymous ; compliance: mb(--with-lock), anonymous,
    # retention ; lifecycle: ilm ls + ilm add ; SA: svcacct info (admin),
    # svcacct add (sh -c). Quotas skipped (gb=0 default).
    assert fake.verbs() == ["mb", "version", "anonymous",
                            "mb", "anonymous", "retention",
                            "ilm", "ilm", "admin", "-c"]
    assert step.secrets["minio_access_key"] == "facil-backend"
    assert len(step.secrets["minio_secret_key"]) == 40   # token_hex(20)
    assert step.secrets["minio_bucket"] == "facil-documents"
    assert step.secrets["minio_compliance_bucket"] == "facil-compliance"


def test_compliance_bucket_created_with_lock_and_retention(monkeypatch, ctx):
    fake = FakeMC(svcacct_exists=False)
    _patch(monkeypatch, fake)
    mn.provision(ctx)
    mb_calls = [c["args"] for c in fake.calls if c["args"][0] == "mb"]
    assert any("--with-lock" in a for a in mb_calls)          # WORM at creation
    assert any("facil-compliance" in a for a in mb_calls[-1])
    retention = [c["args"] for c in fake.calls if c["args"][0] == "retention"][0]
    assert retention[:3] == ["retention", "set", "--default"]
    assert "GOVERNANCE" in retention and "365d" in retention


def test_compliance_respects_config_overrides(monkeypatch, tmp_path):
    (tmp_path / "deploy").mkdir()
    cfg = make_cfg(storage={"provider": "minio", "minio": {
        "compliance": {"retention_mode": "compliance", "retention_days": 2555}}})
    c = BootstrapContext(cfg=cfg, network="net", repo_root=tmp_path)
    fake = FakeMC(svcacct_exists=False)
    _patch(monkeypatch, fake)
    mn.provision(c)
    retention = [x["args"] for x in fake.calls if x["args"][0] == "retention"][0]
    assert "COMPLIANCE" in retention and "2555d" in retention


def test_compliance_disabled_skips_worm(monkeypatch, tmp_path):
    (tmp_path / "deploy").mkdir()
    cfg = make_cfg(storage={"provider": "minio",
                            "minio": {"compliance": {"enabled": False}}})
    c = BootstrapContext(cfg=cfg, network="net", repo_root=tmp_path)
    fake = FakeMC(svcacct_exists=False)
    _patch(monkeypatch, fake)
    step = mn.provision(c)
    assert [x["args"] for x in fake.calls if x["args"][0] == "retention"] == []
    assert "minio_compliance_bucket" not in step.secrets
    assert any("disabled" in a for a in step.actions)


def test_secret_passed_via_env_not_argv(monkeypatch, ctx):
    fake = FakeMC()
    _patch(monkeypatch, fake)
    mn.provision(ctx)
    # root password travels in MC_HOST_facil env, never as a bare mc arg.
    for call in fake.calls:
        assert "MC_HOST_facil" in call["env"]
        assert "facilminio" in call["env"]["MC_HOST_facil"]


def test_warns_when_root_password_falls_back_to_default(monkeypatch, ctx, caplog):
    # F5: the weak built-in default must not be used silently — warn loudly when
    # MINIO_ROOT_PASSWORD is absent (ensure_secrets not run).
    import logging
    _patch(monkeypatch, FakeMC())
    with caplog.at_level(logging.WARNING):
        mn.provision(ctx)  # ctx has no MINIO_ROOT_PASSWORD secret
    assert any("MINIO_ROOT_PASSWORD" in r.message for r in caplog.records)


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
    # On reuse the secret is NOT recreated, but the policy is ensured via edit.
    sh_scripts = [c["args"][1] for c in fake.calls if c["args"][0] == "-c"]
    assert all("svcacct add" not in s for s in sh_scripts)       # never re-added
    assert any("svcacct edit" in s for s in sh_scripts)          # policy ensured
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


# --- S3: lifecycle + quotas ---

def _cfg_ctx(tmp_path, **minio_over):
    (tmp_path / "deploy").mkdir()
    cfg = make_cfg(storage={"provider": "minio", "minio": minio_over})
    return BootstrapContext(cfg=cfg, network="net", repo_root=tmp_path)


def test_lifecycle_added_when_absent(monkeypatch, ctx):
    fake = FakeMC(existing_noncurrent_days=())
    _patch(monkeypatch, fake)
    mn.provision(ctx)
    adds = [c["args"] for c in fake.calls if c["args"][:3] == ["ilm", "rule", "add"]]
    assert adds and "--noncurrent-expire-days" in adds[0] and "90" in adds[0]
    # lifecycle applies to documents, never the WORM bucket
    assert all("facil-compliance" not in a for a in adds[0])


def test_lifecycle_idempotent_when_present(monkeypatch, ctx):
    fake = FakeMC(existing_noncurrent_days=(90,))   # rule already there
    _patch(monkeypatch, fake)
    step = mn.provision(ctx)
    assert [c for c in fake.calls if c["args"][:3] == ["ilm", "rule", "add"]] == []
    assert any("already set" in a for a in step.actions)


def test_lifecycle_skipped_when_zero(monkeypatch, tmp_path):
    c = _cfg_ctx(tmp_path, lifecycle={"expire_noncurrent_versions_days": 0})
    fake = FakeMC()
    _patch(monkeypatch, fake)
    mn.provision(c)
    assert [x for x in fake.calls if x["args"][0] == "ilm"] == []


def test_quota_set_when_configured(monkeypatch, tmp_path):
    c = _cfg_ctx(tmp_path, quota_documents_gb=10)
    fake = FakeMC(existing_quota_bytes=0)
    _patch(monkeypatch, fake)
    step = mn.provision(c)
    sets = [x["args"] for x in fake.calls if x["args"][:2] == ["quota", "set"]]
    assert sets and "10gi" in sets[0] and "facil/facil-documents" in sets[0]


def test_quota_idempotent_when_matches(monkeypatch, tmp_path):
    c = _cfg_ctx(tmp_path, quota_documents_gb=10)
    fake = FakeMC(existing_quota_bytes=10 * 1024 ** 3)
    _patch(monkeypatch, fake)
    step = mn.provision(c)
    assert [x for x in fake.calls if x["args"][:2] == ["quota", "set"]] == []
    assert any("already set" in a for a in step.actions)


def test_quota_skipped_when_zero(monkeypatch, ctx):
    fake = FakeMC()
    _patch(monkeypatch, fake)
    mn.provision(ctx)            # defaults: quotas 0
    assert [x for x in fake.calls if x["args"][0] == "quota"] == []
