"""Branding projection — the single source of truth for the `branding.*` theme:
the default values AND which fields the admin editor may write. Shared by the
public system endpoint, the RBAC-gated admin editor (D5.4), and the resolver's
code defaults in `main` (so there is one place to change, no drift).

Values live in the config-store (`branding.*`); colours are hex (e.g. `#2563eb`)
and the web layer converts them to HSL CSS variables at render time.
"""

from __future__ import annotations

THEME_MODES: tuple[str, ...] = ("light", "dark", "auto")

# Default branding (the lowest resolver layer). Field name -> default value.
BRANDING_DEFAULTS: dict[str, object] = {
    "app_name": "Facil",
    "tagline": "",
    "logo_url": "",
    "logo_dark_url": "",
    "favicon_url": "",
    "login_background_url": "",
    "primary_color": "#2563eb",
    "secondary_color": "#7c3aed",
    "theme_mode": "light",
    "default_locale": "en",
    "support_email": "",
    "support_url": "",
    "supported_locales": ["en", "fr", "es"],
}

# Simple string fields the admin editor may write (key = `branding.<field>`).
BRANDING_STRING_FIELDS: tuple[str, ...] = (
    "app_name", "tagline", "logo_url", "logo_dark_url", "favicon_url",
    "login_background_url", "primary_color", "secondary_color", "theme_mode",
    "default_locale", "support_email", "support_url",
)


def resolver_defaults() -> dict[str, object]:
    """The branding defaults keyed as resolver entries (`branding.<field>`)."""
    return {f"branding.{k}": v for k, v in BRANDING_DEFAULTS.items()}


def branding_snapshot(resolver) -> dict:
    """The full public branding payload, resolved through the layered config
    (defaults -> file -> DB -> env), falling back to the baked default per field
    so the snapshot is correct even if the resolver was built without them."""
    return {
        k: resolver.resolve(f"branding.{k}", default)
        for k, default in BRANDING_DEFAULTS.items()
    }
