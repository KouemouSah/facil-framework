"""Phase 1bis — module manifest + boot-time resource reconciliation.

A module declares its resource needs (config defaults, secret keys, buckets); the
reconciler provisions what CAN be provisioned at runtime and validates the rest:
  - config_defaults -> seeded into the config-store (idempotent, never overrides);
  - required_secret_keys -> validated (fail-loud report; a runtime cannot FORGE a secret);
  - required_buckets -> ensured via the active storage provider (best-effort, non-fatal).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config_store import repository as settings_repo  # noqa: E402
from app.core.module_registry import ModuleManifest, load_manifest  # noqa: E402
from app.core.module_resources import reconcile_module_resources  # noqa: E402
from app.core.providers.registry import default_registry  # noqa: E402


# --- Manifest dataclass + discovery ----------------------------------------

def test_manifest_defaults_are_empty():
    m = ModuleManifest()
    assert m.config_defaults == {}
    assert m.required_secret_keys == []
    assert m.required_buckets == []
    assert m.depends_on == []


def test_load_manifest_present():
    m = load_manifest("alpha", package="tests.sample_modules")
    assert m is not None
    assert m.config_defaults == {"alpha.greeting": "hi"}
    assert m.required_buckets == ["alpha-bucket"]


def test_load_manifest_absent_returns_none():
    assert load_manifest("beta", package="tests.sample_modules") is None


def test_load_manifest_absent_MODULE_returns_none():
    # Un module LISTÉ dans MODULES_ENABLED mais NON PORTÉ (totalement absent) ne doit
    # PAS lever — sinon la boucle de reconciliation au boot plante des le premier
    # module absent (regression : la config par defaut liste `rbac`, absent de
    # app.modules, ce qui tuait l'etape module-resources a chaque boot).
    assert load_manifest("ghost_absent_module", package="tests.sample_modules") is None


# --- Reconciler: config defaults --------------------------------------------

@pytest.mark.asyncio
async def test_seeds_config_default_when_absent(session):
    report = await reconcile_module_resources(
        ModuleManifest(config_defaults={"billing.prefix": "INV"}),
        "billing", session=session, registry=default_registry())
    assert "billing.prefix" in report["config_seeded"]
    row = await settings_repo.get_setting(session, "billing.prefix")
    assert row.value == "INV"


@pytest.mark.asyncio
async def test_preserves_existing_setting(session):
    await settings_repo.upsert_setting(session, "billing.prefix", "OLD", updated_by="admin")
    report = await reconcile_module_resources(
        ModuleManifest(config_defaults={"billing.prefix": "INV"}),
        "billing", session=session, registry=default_registry())
    assert report["config_seeded"] == []
    row = await settings_repo.get_setting(session, "billing.prefix")
    assert row.value == "OLD"  # admin/runtime value untouched


# --- Reconciler: secret keys (validate, never forge) ------------------------

@pytest.mark.asyncio
async def test_missing_secret_is_reported_not_raised(session, monkeypatch):
    monkeypatch.delenv("BILLING_KEY", raising=False)
    report = await reconcile_module_resources(
        ModuleManifest(required_secret_keys=["BILLING_KEY"]),
        "billing", session=session, registry=default_registry())
    assert "BILLING_KEY" in report["secrets_missing"]


@pytest.mark.asyncio
async def test_present_secret_is_not_reported_missing(session, monkeypatch):
    monkeypatch.setenv("BILLING_KEY", "s3cr3t")
    report = await reconcile_module_resources(
        ModuleManifest(required_secret_keys=["BILLING_KEY"]),
        "billing", session=session, registry=default_registry())
    assert report["secrets_missing"] == []


# --- Reconciler: buckets via active storage ---------------------------------

class _FakeStorage:
    def __init__(self):
        self.ensured: list[str] = []

    async def ensure_bucket(self, bucket: str) -> None:
        self.ensured.append(bucket)


@pytest.mark.asyncio
async def test_ensures_buckets_via_storage(session):
    storage = _FakeStorage()
    report = await reconcile_module_resources(
        ModuleManifest(required_buckets=["invoices"]),
        "billing", session=session, registry=default_registry(), storage=storage)
    assert storage.ensured == ["invoices"]
    assert report["buckets_ensured"] == ["invoices"]


@pytest.mark.asyncio
async def test_bucket_failure_is_captured_not_raised(session):
    class _Boom:
        async def ensure_bucket(self, bucket: str) -> None:
            raise RuntimeError("AccessDenied")

    report = await reconcile_module_resources(
        ModuleManifest(required_buckets=["x"]),
        "billing", session=session, registry=default_registry(), storage=_Boom())
    assert report["buckets_ensured"] == []
    assert report["bucket_errors"]  # captured for /health, boot survives
