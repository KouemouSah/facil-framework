"""Branding config-store defaults (P4) — completeness, resolution, runtime override."""

from __future__ import annotations

import pytest

from app.config_store.resolver import ConfigResolver
from app.main import _DEFAULTS
from tests.conftest import AUTH

_EXPECTED = {
    "branding.app_name", "branding.tagline", "branding.logo_url",
    "branding.logo_dark_url", "branding.favicon_url",
    "branding.login_background_url", "branding.primary_color",
    "branding.secondary_color", "branding.theme_mode", "branding.default_locale",
    "branding.supported_locales", "branding.support_email", "branding.support_url",
}


def test_branding_defaults_complete():
    assert _EXPECTED <= set(_DEFAULTS)
    assert _DEFAULTS["branding.theme_mode"] == "light"
    assert _DEFAULTS["branding.supported_locales"] == ["en", "fr", "es"]


def test_resolver_serves_branding_defaults():
    r = ConfigResolver(defaults=_DEFAULTS, env={})
    assert r.resolve("branding.primary_color") == "#2563eb"
    assert r.resolve("branding.default_locale") == "en"
    assert r.resolve("branding.secondary_color") == "#7c3aed"


@pytest.mark.asyncio
async def test_branding_override_runtime(client):
    ac, _ = client
    from app.main import app
    await ac.put("/api/v1/admin/settings/branding.app_name", headers=AUTH,
                 json={"value": "MyGov", "value_type": "string"})
    # PUT refreshes the resolver DB layer -> the override wins over the default.
    assert app.state.resolver.resolve("branding.app_name") == "MyGov"
