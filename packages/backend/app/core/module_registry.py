"""Module Loader (Phase A.5, clé de voûte) — conditional router inclusion.

The framework ships every business module as code; a deployment activates a
subset via `modules.enabled` (W6), rendered to the `MODULES_ENABLED` env at boot.
This loader reads that list and includes only the enabled modules' routers.

Convention: a module is a package `app.modules.<name>` exposing
`app.modules.<name>.api:router` (a FastAPI `APIRouter`). The base package is a
parameter so tests can point the loader at fixture packages.

Two failure modes, deliberately different (incremental porting reality):
- module **not present** (a profile lists it but it isn't ported yet) -> WARN +
  skip, so the backend still boots;
- module **present but broken** (no `api`, or no `APIRouter` named `router`) ->
  `ModuleLoadError` at boot, because that is a real bug, not a missing feature.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import pkgutil
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, FastAPI

logger = logging.getLogger(__name__)

DEFAULT_PACKAGE = "app.modules"


class ModuleLoadError(RuntimeError):
    """An enabled, *present* module is broken (no api / no router)."""


@dataclass
class ModuleManifest:
    """Declarative resource needs of a module (Phase 1bis). All optional — a module
    without a manifest keeps the current behaviour. The module *declares*; the
    system provider (or the deploy layer) *provisions*. `config_defaults` are seeded
    into the config-store, `required_secret_keys` are validated (never forged at
    runtime), `required_buckets` are ensured via the active storage provider."""
    config_defaults: dict[str, Any] = field(default_factory=dict)
    required_secret_keys: list[str] = field(default_factory=list)
    required_buckets: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


def load_manifest(name: str, package: str = DEFAULT_PACKAGE) -> ModuleManifest | None:
    """Return a module's `manifest:MANIFEST` if it declares one, else None. A module
    that is ABSENT (listed in MODULES_ENABLED but not ported yet) or PRESENT WITHOUT a
    `manifest` submodule both yield None — nothing to reconcile, exactly like
    `load_modules` skips absent modules. Only a manifest that is PRESENT BUT BROKEN
    (not a ModuleManifest) raises — a real bug, not a missing feature."""
    if not _is_present(name, package):
        return None  # module not ported/absent — no resources to reconcile
    manifest_mod = f"{package}.{name}.manifest"
    try:
        mod = importlib.import_module(manifest_mod)
    except ModuleNotFoundError as e:
        if e.name == manifest_mod:
            return None  # no manifest declared — fine
        raise  # a real import error inside the module's manifest
    obj = getattr(mod, "MANIFEST", None)
    if not isinstance(obj, ModuleManifest):
        raise ModuleLoadError(
            f"module '{name}': '{manifest_mod}' exposes no ModuleManifest named 'MANIFEST'")
    return obj


def enabled_from_env(env: dict | None = None) -> list[str]:
    """Parse MODULES_ENABLED (comma-separated) from the environment."""
    raw = (env or os.environ).get("MODULES_ENABLED", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


def discover(package: str = DEFAULT_PACKAGE) -> list[str]:
    """Available module names = sub-packages of `package` (best-effort)."""
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError:
        return []
    paths = getattr(pkg, "__path__", [])
    return sorted(m.name for m in pkgutil.iter_modules(paths) if m.ispkg)


def import_module_models(package: str = DEFAULT_PACKAGE) -> list[str]:
    """Import every module's `models` submodule so its tables register on the
    shared Base — REGARDLESS of MODULES_ENABLED. Module *tables* always exist in
    the DB (Alembic / create_all); only the *router* is conditional (R1). Called
    by alembic/env.py and the test setup. Returns the modules whose models loaded.
    """
    imported: list[str] = []
    for name in discover(package):
        models_mod = f"{package}.{name}.models"
        try:
            importlib.import_module(models_mod)
            imported.append(name)
        except ModuleNotFoundError as e:
            if e.name == models_mod:
                continue  # module simply has no models (e.g. system) — fine
            raise  # a real import error inside the module's models
    return imported


def _is_present(name: str, package: str) -> bool:
    try:
        return importlib.util.find_spec(f"{package}.{name}") is not None
    except ModuleNotFoundError:
        return False


def _module_router(name: str, package: str) -> APIRouter:
    api_mod = f"{package}.{name}.api"
    try:
        mod = importlib.import_module(api_mod)
    except ModuleNotFoundError as e:
        raise ModuleLoadError(
            f"module '{name}' is present but '{api_mod}' is not importable: {e}") from e
    router = getattr(mod, "router", None)
    if not isinstance(router, APIRouter):
        raise ModuleLoadError(
            f"module '{name}': '{api_mod}' exposes no APIRouter named 'router'")
    return router


def load_modules(app: FastAPI, *, enabled: list[str],
                 package: str = DEFAULT_PACKAGE) -> list[str]:
    """Include each enabled+present module's router, in the given order. Missing
    modules are skipped (warned); present-but-broken modules raise. Returns the
    list of module names actually loaded."""
    loaded: list[str] = []
    for name in enabled:
        if not _is_present(name, package):
            logger.warning("MODULES_ENABLED lists '%s' but '%s.%s' is not present "
                           "(not ported yet) — skipping.", name, package, name)
            continue
        app.include_router(_module_router(name, package))
        loaded.append(name)
    return loaded
