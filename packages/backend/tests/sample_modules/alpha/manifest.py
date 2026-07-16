"""Test fixture — a module manifest declaring resources (Phase 1bis)."""

from __future__ import annotations

from app.core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    config_defaults={"alpha.greeting": "hi"},
    required_secret_keys=["ALPHA_API_KEY"],
    required_buckets=["alpha-bucket"],
)
