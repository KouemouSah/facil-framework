#!/usr/bin/env python3
"""Deployment profiles — coherent default packs applied by the wizard.

A profile pre-fills the config sections that are domain-shaped (which modules to
enable, branding, a couple of feature toggles) so the operator starts from a
sane baseline for their use case. The operator can still override any value.

Scope note (DEPLOY_WIZARD_V2 W3): this is the SELECTION + DEFAULTS layer. The
``modules.enabled`` lists are the documented framework module set (the contract
the Module Loader / Phase A.5 will read) — the module *code* and detailed seeds
land with the modules phase. No invented fields: every key here exists in the
deploy schema.
"""

from __future__ import annotations

from typing import Any

# profile -> default deltas (only schema-representable keys).
PROFILES: dict[str, dict[str, Any]] = {
    "empty": {
        "modules": ["rbac"],
        "branding": {"app_name": "Facil"},
        "features": {},
    },
    "private-services-company": {
        "modules": ["rbac", "treasury", "chatbot", "document_designer"],
        "branding": {"app_name": "Facil Services"},
        "features": {"executive_tools": True},
    },
    "gov-emergent-country": {
        "modules": ["rbac", "treasury", "chatbot", "verified_identifiers",
                    "document_designer", "signature"],
        "branding": {"app_name": "Gov Services"},
        "features": {"penalties": True},
    },
    "saas-multitenant": {
        "modules": ["rbac", "billing", "multitenancy", "chatbot"],
        "branding": {"app_name": "Facil SaaS"},
        "features": {"llm_routing": True},
    },
    "banking": {
        "modules": ["rbac", "treasury", "kyc", "signature", "document_designer"],
        "branding": {"app_name": "Facil Bank"},
        "features": {"executive_tools": True, "penalties": True},
    },
}


def apply_profile_defaults(cfg: dict[str, Any], profile: str) -> dict[str, Any]:
    """Fill ``cfg`` (a wizard config dict) with the profile's defaults, in place.

    - ``modules.enabled`` and ``branding`` are set from the profile (the wizard
      does not ask about them).
    - ``features`` flags from the profile are merged ON TOP of whatever defaults
      are already present (profile wins for the keys it sets).

    Unknown profile -> falls back to ``empty`` (never raises; validation upstream
    already constrained the value).
    """
    spec = PROFILES.get(profile, PROFILES["empty"])
    cfg["modules"] = {"enabled": list(spec["modules"])}
    cfg["branding"] = dict(spec["branding"])
    if spec.get("features"):
        features = dict(cfg.get("features", {}))
        features.update(spec["features"])
        cfg["features"] = features
    return cfg
