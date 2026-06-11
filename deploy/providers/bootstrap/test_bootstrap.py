#!/usr/bin/env python3
"""Phase B1 tests — state mechanics, mode-aware dispatch, health gate, run.

Pure-Python and fully mocked: no live docker stack, no network. Run with the
canonical venv:

    C:\\facil_framework\\.venv\\Scripts\\python.exe -m pytest \\
        deploy/providers/bootstrap/test_bootstrap.py -q
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

# Match the repo convention (see test_docker_local.py): put the providers dir
# on sys.path and import the package flat as `bootstrap`, plus scripts/ for
# validate_config.
PROVIDERS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

from bootstrap import (  # noqa: E402
    DEFAULT_NETWORK,
    run_bootstrap,
    select_provisioners,
    _merge_prior_steps,
    _resolve_network,
)
from bootstrap import docker_helpers as dh  # noqa: E402
from bootstrap.context import vc  # noqa: E402
from bootstrap.docker_helpers import ContainerInfo, DockerError  # noqa: E402
from bootstrap.state import BootstrapState, ProvisionStep  # noqa: E402


# ---------------------------------------------------------------------------
# Config fixture — minimal config valid against the Pydantic schema.
# ---------------------------------------------------------------------------

_BASE_CONFIG = {
    "meta": {"config_version": 1, "project_name": "facil",
             "environment": "development"},
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
    for key, val in overrides.items():
        raw.setdefault(key, {})
        raw[key].update(val) if isinstance(val, dict) else raw.__setitem__(key, val)
    return vc.DeployConfig.model_validate(raw)


# ---------------------------------------------------------------------------
# state.py
# ---------------------------------------------------------------------------

def _sample_state() -> BootstrapState:
    return BootstrapState(
        project="facil", storage_provider="minio",
        secrets_provider="openbao", database_mode="local",
        steps=[
            ProvisionStep(name="minio", status="ok", detail="bucket ready",
                          actions=["create bucket facil-documents"],
                          secrets={"minio_access_key": "AKIA", "minio_secret_key": "s3cr3t"}),
            ProvisionStep(name="postgres", status="skipped", detail="external db"),
        ],
    )


def test_state_roundtrip(tmp_path: Path):
    st = _sample_state()
    f = tmp_path / "state.json"
    st.save(f)
    loaded = BootstrapState.load(f)
    assert loaded is not None
    assert loaded.to_dict() == st.to_dict()


def test_state_save_is_idempotent(tmp_path: Path):
    st = _sample_state()
    f = tmp_path / "state.json"
    st.save(f)
    first = f.read_text(encoding="utf-8")
    st.save(f)
    assert f.read_text(encoding="utf-8") == first  # byte-stable rewrite


def test_load_missing_returns_none(tmp_path: Path):
    assert BootstrapState.load(tmp_path / "nope.json") is None


def test_all_secrets_flattens():
    st = _sample_state()
    assert st.all_secrets() == {"minio_access_key": "AKIA", "minio_secret_key": "s3cr3t"}


def test_redacted_summary_masks_values():
    summary = _sample_state().redacted_summary()
    assert "s3cr3t" not in summary
    assert "AKIA" not in summary
    assert "minio_access_key=***" in summary
    assert "[OK] minio" in summary and "[--] postgres" in summary


def test_succeeded_true_without_failures():
    assert _sample_state().succeeded is True


def test_succeeded_false_with_a_failure():
    st = _sample_state()
    st.steps.append(ProvisionStep(name="openbao").fail("boom"))
    assert st.succeeded is False


# ---------------------------------------------------------------------------
# dispatch (select_provisioners)
# ---------------------------------------------------------------------------

def _names(mods) -> list[str]:
    """Provisioner module NAMEs (modules carry NAME)."""
    return [m.NAME for m in mods]


def _step_names(steps) -> list[str]:
    """ProvisionStep names (steps carry name)."""
    return [s.name for s in steps]


def test_select_default_runs_all_three():
    # defaults: storage=minio, secrets=env_file?, db_mode=local.
    cfg = make_cfg(storage={"provider": "minio"},
                   secrets={"provider": "openbao"})
    assert _names(select_provisioners(cfg)) == ["openbao", "minio", "postgres"]


def test_select_skips_minio_when_storage_not_minio():
    cfg = make_cfg(storage={"provider": "disabled"},
                   secrets={"provider": "openbao"})
    assert "minio" not in _names(select_provisioners(cfg))


def test_select_skips_openbao_when_secrets_env_file():
    cfg = make_cfg(secrets={"provider": "env_file"})
    assert "openbao" not in _names(select_provisioners(cfg))


def test_select_skips_postgres_when_external_db():
    cfg = make_cfg(docker_local={"database_mode": "external"})
    assert "postgres" not in _names(select_provisioners(cfg))


def test_only_filter_restricts():
    cfg = make_cfg(secrets={"provider": "openbao"})
    assert _names(select_provisioners(cfg, only={"minio"})) == ["minio"]


# ---------------------------------------------------------------------------
# health gate
# ---------------------------------------------------------------------------

def test_wait_for_healthy_resolves(monkeypatch):
    infos = {
        "minio": ContainerInfo("facil-minio-1", "facil_framework_default", "healthy", True),
        "openbao": ContainerInfo("facil-openbao-1", "facil_framework_default", "healthy", True),
    }
    monkeypatch.setattr(dh, "find_container", lambda svc, project=None: infos[svc])
    resolved = dh.wait_for_healthy(["minio", "openbao"], sleep=lambda _: None)
    assert set(resolved) == {"minio", "openbao"}


def test_wait_for_healthy_times_out(monkeypatch):
    # postgres never becomes healthy → timeout naming it.
    monkeypatch.setattr(
        dh, "find_container",
        lambda svc, project=None: ContainerInfo("c", "net", "starting", True),
    )
    with pytest.raises(DockerError, match="postgres"):
        dh.wait_for_healthy(["postgres"], timeout=0, sleep=lambda _: None)


def test_no_healthcheck_container_is_ready(monkeypatch):
    monkeypatch.setattr(
        dh, "find_container",
        lambda svc, project=None: ContainerInfo("c", "net", None, True),
    )
    resolved = dh.wait_for_healthy(["redis"], sleep=lambda _: None)
    assert "redis" in resolved


# ---------------------------------------------------------------------------
# network resolution
# ---------------------------------------------------------------------------

def test_resolve_network_prefers_container_net():
    cs = {"minio": ContainerInfo("m", "stack_net", "healthy", True)}
    assert _resolve_network(cs) == "stack_net"


def test_resolve_network_falls_back():
    assert _resolve_network({}) == DEFAULT_NETWORK


# ---------------------------------------------------------------------------
# orchestration (run_bootstrap) — injected wait, no live stack
# ---------------------------------------------------------------------------

def test_run_bootstrap_dry_run_skips_wait(tmp_path: Path):
    called = {"wait": False}

    def fake_wait(*a, **k):
        called["wait"] = True
        return {}

    cfg = make_cfg(secrets={"provider": "openbao"})
    state = run_bootstrap(cfg, dry_run=True, repo_root=tmp_path,
                          log=lambda *_: None, _wait=fake_wait)
    assert called["wait"] is False                 # dry-run never waits
    assert _step_names(state.steps) == ["openbao", "minio", "postgres"]
    # dry-run is no-mutation: no state file written.
    assert not (tmp_path / "deploy" / ".bootstrap-state.json").exists()


def test_run_bootstrap_writes_state(tmp_path: Path):
    (tmp_path / "deploy").mkdir()
    cfg = make_cfg(secrets={"provider": "openbao"})
    infos = {s: ContainerInfo(f"c-{s}", "net", "healthy", True)
             for s in ("openbao", "minio", "postgres")}
    state = run_bootstrap(
        cfg, repo_root=tmp_path, log=lambda *_: None,
        _wait=lambda services, **k: {s: infos[s] for s in services},
    )
    f = tmp_path / "deploy" / ".bootstrap-state.json"
    assert f.exists()
    reloaded = BootstrapState.load(f)
    assert _step_names(reloaded.steps) == ["openbao", "minio", "postgres"]


def test_merge_preserves_absent_provisioners(tmp_path: Path):
    f = tmp_path / "state.json"
    prior = BootstrapState(
        project="facil", storage_provider="minio", secrets_provider="openbao",
        database_mode="local",
        steps=[ProvisionStep(name="openbao", status="ok",
                             secrets={"openbao_secret_id": "SID"}),
               ProvisionStep(name="minio", status="ok",
                             secrets={"minio_secret_key": "MK"})],
    )
    prior.save(f)
    # Simulate a `--only=postgres` run that only produced a postgres step.
    new = BootstrapState(project="facil", storage_provider="minio",
                         secrets_provider="openbao", database_mode="local",
                         steps=[ProvisionStep(name="postgres", status="ok")])
    _merge_prior_steps(new, f)
    assert _step_names(new.steps) == ["openbao", "minio", "postgres"]  # sorted
    assert new.step("openbao").secrets["openbao_secret_id"] == "SID"   # preserved
    assert new.step("minio").secrets["minio_secret_key"] == "MK"       # preserved


def test_merge_current_run_wins(tmp_path: Path):
    f = tmp_path / "state.json"
    BootstrapState(project="facil", storage_provider="minio",
                   secrets_provider="openbao", database_mode="local",
                   steps=[ProvisionStep(name="minio",
                                        secrets={"minio_secret_key": "OLD"})]).save(f)
    new = BootstrapState(project="facil", storage_provider="minio",
                         secrets_provider="openbao", database_mode="local",
                         steps=[ProvisionStep(name="minio",
                                              secrets={"minio_secret_key": "NEW"})])
    _merge_prior_steps(new, f)
    minio_steps = [s for s in new.steps if s.name == "minio"]
    assert len(minio_steps) == 1                              # no duplicate
    assert minio_steps[0].secrets["minio_secret_key"] == "NEW"  # current wins


def test_run_bootstrap_no_applicable(tmp_path: Path):
    cfg = make_cfg(storage={"provider": "disabled"},
                   secrets={"provider": "env_file"},
                   docker_local={"database_mode": "external"})
    state = run_bootstrap(cfg, dry_run=True, repo_root=tmp_path, log=lambda *_: None)
    assert state.steps == []
