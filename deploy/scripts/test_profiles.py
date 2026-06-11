#!/usr/bin/env python3
"""Tests for deploy/scripts/profiles.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import profiles as pr  # noqa: E402
import validate_config as vc  # noqa: E402

_BASE = {
    "meta": {"config_version": 1, "project_name": "facil",
             "environment": "production"},
    "database": {"url_secret": "database-url"},
    "redis": {"url_secret": "REDIS_URL"},
    "auth": {"jwt_secret_name": "J", "app_secret_name": "S",
             "totp_encryption_secret": "T"},
    "firebase": {"project_id": "x", "storage_bucket": "x"},
    "ai": {"gemini_api_key_secret": "G"},
    "server": {"frontend_url": "https://f.example", "api_base_url": "https://a.example"},
    "cron": {"secret_name": "C"},
    "features": {"scheduler_enabled": True, "rate_limit_enabled": True,
                 "metrics_enabled": True, "structured_logging": True,
                 "executive_tools": False, "llm_routing": False, "penalties": False},
}


def test_every_profile_applies_and_validates():
    for name in pr.PROFILES:
        cfg = {**_BASE, "meta": {**_BASE["meta"], "profile": name}}
        pr.apply_profile_defaults(cfg, name)
        # must validate against the real schema
        validated = vc.DeployConfig.model_validate(cfg)
        assert validated.modules.enabled, f"{name} has no modules"
        assert validated.branding.app_name


def test_gov_profile_sets_penalties():
    cfg = dict(_BASE)
    pr.apply_profile_defaults(cfg, "gov-emergent-country")
    assert cfg["features"]["penalties"] is True
    assert "verified_identifiers" in cfg["modules"]["enabled"]


def test_banking_profile_modules_and_branding():
    cfg = dict(_BASE)
    pr.apply_profile_defaults(cfg, "banking")
    assert "kyc" in cfg["modules"]["enabled"]
    assert cfg["branding"]["app_name"] == "Facil Bank"


def test_features_merge_keeps_existing_keys():
    cfg = {"features": {"scheduler_enabled": True, "penalties": False}}
    pr.apply_profile_defaults(cfg, "gov-emergent-country")
    assert cfg["features"]["scheduler_enabled"] is True   # preserved
    assert cfg["features"]["penalties"] is True            # profile override


def test_unknown_profile_falls_back_to_empty():
    cfg = dict(_BASE)
    pr.apply_profile_defaults(cfg, "does-not-exist")
    assert cfg["modules"]["enabled"] == ["rbac"]            # empty baseline
