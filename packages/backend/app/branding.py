"""Branding projection — the single source of truth for which `branding.*`
settings make up the public theme, shared by the public system endpoint and the
RBAC-gated admin editor (D5.4).

Values live in the config-store (`branding.*`), with code defaults baked in the
resolver (`main._DEFAULTS`). Colours are hex (e.g. `#2563eb`); the web layer
converts them to HSL CSS variables at render time.
"""

from __future__ import annotations

# Simple string fields the admin editor may write (key = `branding.<field>`).
BRANDING_STRING_FIELDS: tuple[str, ...] = (
    "app_name", "tagline", "logo_url", "logo_dark_url", "favicon_url",
    "login_background_url", "primary_color", "secondary_color", "theme_mode",
    "default_locale", "support_email", "support_url",
)

THEME_MODES: tuple[str, ...] = ("light", "dark", "auto")


def branding_snapshot(resolver) -> dict:
    """The full public branding payload (string fields + supported_locales),
    resolved through the layered config (defaults -> file -> DB -> env)."""
    snap = {f: resolver.resolve(f"branding.{f}", "") for f in BRANDING_STRING_FIELDS}
    snap["supported_locales"] = resolver.resolve(
        "branding.supported_locales", ["en", "fr", "es"])
    return snap
