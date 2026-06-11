#!/usr/bin/env python3
"""Tests for deploy/doctor.py (static coherence checks)."""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY_DIR))
sys.path.insert(0, str(DEPLOY_DIR / "scripts"))

import doctor  # noqa: E402
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


def cfg(**over):
    raw = {**_BASE, **over}
    return vc.DeployConfig.model_validate(raw)


def _levels(issues):
    return {i.level for i in issues}


def _has(issues, level, substr):
    return any(i.level == level and substr in i.message for i in issues)


def test_coherent_docker_local():
    issues = doctor.check_coherence(cfg(), "docker-local")
    assert "fail" not in _levels(issues)
    assert _has(issues, "ok", "coherent")


def test_openbao_on_serverless_warns():
    c = cfg(secrets={"provider": "openbao"})
    assert _has(doctor.check_coherence(c, "aws"), "warn", "OpenBao")


def test_minio_on_serverless_warns():
    c = cfg(storage={"provider": "minio"})
    assert _has(doctor.check_coherence(c, "gcp"), "warn", "minio")


def test_managed_db_with_local_mode_warns():
    # Schema requires a connection, so use url_secret; the incoherence the doctor
    # catches is: managed DB selected but the local postgres still spins up.
    c = cfg(database={"provider": "supabase", "url_secret": "database-url"},
            docker_local={"database_mode": "local"})
    assert _has(doctor.check_coherence(c, "gcp"), "warn", "database_mode=local")


def test_multi_llm_info():
    c = cfg(ai={"providers": {"a": {"kind": "ollama", "model": "x"}},
                "routing": {"public_chat": "a"}})
    assert _has(doctor.check_coherence(c, "docker-local"), "info", "LLM routing")


def test_email_without_from_warns():
    c = cfg(email={"provider": "sendgrid", "api_key_secret": "K"})
    assert _has(doctor.check_coherence(c, "docker-local"), "warn", "from_email")


def test_stripe_disabled_warns():
    c = cfg(payments={"provider": "stripe", "stripe": {"enabled": False}})
    assert _has(doctor.check_coherence(c, "docker-local"), "warn", "stripe.enabled")


def test_citizen_keycloak_scale_warning():
    c = cfg(auth={"jwt_secret_name": "J", "app_secret_name": "S",
                  "totp_encryption_secret": "T",
                  "citizen_methods": ["keycloak_oidc"]})
    assert _has(doctor.check_coherence(c, "docker-local"), "warn", "keycloak")


def test_prod_edge_no_tls_warns():
    c = cfg(edge={"proxy": "caddy", "tls_mode": "none"})
    assert _has(doctor.check_coherence(c, "docker-local"), "warn", "tls_mode=none")


def test_static_checks_never_fail():
    # The doctor is advisory: static coherence yields warn/info/ok, never fail
    # (hard failures are caught earlier by the schema). FAIL is reserved for
    # --live (a down service).
    issues = doctor.check_coherence(cfg(secrets={"provider": "openbao"}), "aws")
    assert "fail" not in _levels(issues)


def test_main_exit_zero_on_clean(tmp_path):
    import yaml
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(_BASE), encoding="utf-8")
    assert doctor.main(["--config", str(p), "--provider", "docker-local"]) == 0
