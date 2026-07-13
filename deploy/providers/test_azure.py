#!/usr/bin/env python3
"""Tests for deploy/providers/azure.py (CLI mocked, no real Azure)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROVIDERS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import azure  # noqa: E402
import validate_config as vc  # noqa: E402

_BASE = {
    "meta": {"config_version": 1, "project_name": "facil", "environment": "production"},
    "database": {"url_secret": "database-url"},
    "redis": {"url_secret": "REDIS_URL"},
    "auth": {"jwt_secret_name": "J", "app_secret_name": "S", "totp_encryption_secret": "T"},
    "firebase": {"project_id": "x", "storage_bucket": "x"},
    "ai": {"gemini_api_key_secret": "G"},
    "server": {"frontend_url": "https://f.x", "api_base_url": "https://a.x"},
    "cron": {"secret_name": "C"},
}


def make_cfg(**az_over):
    return vc.DeployConfig.model_validate({**_BASE, "azure": az_over})


def test_validate_no_cli(monkeypatch):
    monkeypatch.setattr(azure, "find_az", lambda: None)
    assert "not found" in azure.check_prereqs(make_cfg())[0]


def test_validate_not_logged_in(monkeypatch):
    monkeypatch.setattr(azure, "find_az", lambda: "/usr/bin/az")
    monkeypatch.setattr(azure, "run_az",
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    assert any("login" in p for p in azure.check_prereqs(make_cfg()))


def test_validate_subscription_mismatch(monkeypatch):
    monkeypatch.setattr(azure, "find_az", lambda: "/usr/bin/az")
    monkeypatch.setattr(azure, "run_az",
                        lambda *a, **k: SimpleNamespace(
                            returncode=0, stdout=json.dumps({"id": "sub-AAA"})))
    problems = azure.check_prereqs(make_cfg(subscription_id="sub-BBB",
                                            acr_registry="facilacr"))
    assert any("!=" in p for p in problems)


def test_validate_ok(monkeypatch):
    monkeypatch.setattr(azure, "find_az", lambda: "/usr/bin/az")
    monkeypatch.setattr(azure, "run_az",
                        lambda *a, **k: SimpleNamespace(
                            returncode=0, stdout=json.dumps({"id": "sub-BBB"})))
    assert azure.check_prereqs(make_cfg(subscription_id="sub-BBB",
                                        acr_registry="facilacr")) == []


def test_plan_container_apps():
    plan = azure.build_plan(
        make_cfg(subscription_id="s", acr_registry="facilacr",
                 keyvault_name="facilkv"),
        {"database-url": "x"})
    text = "\n".join(plan)
    assert "acr create" in text
    assert "containerapp env" in text
    assert "containerapp create" in text
    assert "keyvault secret show" in text


def test_acr_image():
    # meta.version default changed "latest" -> "develop" (B4, see
    # validate_config.py::MetaConfig) -- acr_image() just interpolates
    # cfg.meta.version verbatim, so this follows the new default.
    uri = azure.acr_image(make_cfg(acr_registry="facilacr"), "frontend")
    assert uri == "facilacr.azurecr.io/facil-frontend:develop"
