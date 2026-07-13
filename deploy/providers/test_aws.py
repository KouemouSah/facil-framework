#!/usr/bin/env python3
"""Tests for deploy/providers/aws.py (CLI mocked, no real AWS)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROVIDERS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import aws  # noqa: E402
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


def make_cfg(**aws_over):
    raw = {**_BASE, "aws": aws_over}
    return vc.DeployConfig.model_validate(raw)


def test_validate_no_cli(monkeypatch):
    monkeypatch.setattr(aws, "find_aws", lambda: None)
    assert "not found" in aws.check_prereqs(make_cfg())[0]


def test_validate_account_mismatch(monkeypatch):
    monkeypatch.setattr(aws, "find_aws", lambda: "/usr/bin/aws")
    monkeypatch.setattr(aws, "run_aws",
                        lambda *a, **k: SimpleNamespace(
                            returncode=0, stdout=json.dumps({"Account": "999999999999"})))
    problems = aws.check_prereqs(make_cfg(account_id="123456789012"))
    assert any("!=" in p for p in problems)


def test_validate_ok(monkeypatch):
    monkeypatch.setattr(aws, "find_aws", lambda: "/usr/bin/aws")
    monkeypatch.setattr(aws, "run_aws",
                        lambda *a, **k: SimpleNamespace(
                            returncode=0, stdout=json.dumps({"Account": "123456789012"})))
    assert aws.check_prereqs(make_cfg(account_id="123456789012")) == []


def test_plan_app_runner():
    plan = aws.build_plan(make_cfg(account_id="123456789012", runtime="app_runner"),
                          {"database-url": "facil-database-url"})
    text = "\n".join(plan)
    assert "ecr describe-repositories" in text
    assert "apprunner create-service" in text
    assert "secretsmanager describe-secret" in text


def test_plan_ecs_fargate():
    plan = aws.build_plan(make_cfg(account_id="1", runtime="ecs_fargate"), {})
    assert any("ecs update-service" in c for c in plan)


def test_ecr_image_uri():
    # meta.version default changed "latest" -> "develop" (B4, see
    # validate_config.py::MetaConfig) -- ecr_image_uri() just interpolates
    # cfg.meta.version verbatim, so this follows the new default.
    uri = aws.ecr_image_uri(make_cfg(account_id="123456789012", region="eu-west-1"),
                            "backend")
    assert uri == "123456789012.dkr.ecr.eu-west-1.amazonaws.com/facil-backend:develop"
