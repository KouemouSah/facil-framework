#!/usr/bin/env python3
"""Tests for deploy/scripts/ensure_secrets.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import ensure_secrets as es  # noqa: E402


def test_generates_all_when_file_absent(tmp_path):
    f = tmp_path / ".env.secrets"
    gen = es.ensure_secrets(f)
    assert set(gen) == set(es.RUNTIME_SECRETS)
    parsed = es._parse(f)
    for k in es.RUNTIME_SECRETS:
        assert len(parsed[k]) >= 20            # strong


def test_idempotent_keeps_existing(tmp_path):
    f = tmp_path / ".env.secrets"
    f.write_text("POSTGRES_PASSWORD=keepme\nREDIS_PASSWORD=alsokeep\n"
                 "MINIO_ROOT_PASSWORD=third\nADMIN_TOKEN=tok\n", encoding="utf-8")
    gen = es.ensure_secrets(f)
    assert gen == []                            # nothing generated
    parsed = es._parse(f)
    assert parsed["POSTGRES_PASSWORD"] == "keepme"   # untouched
    assert parsed["REDIS_PASSWORD"] == "alsokeep"


def test_only_missing_generated(tmp_path):
    f = tmp_path / ".env.secrets"
    f.write_text("POSTGRES_PASSWORD=existing\n", encoding="utf-8")
    gen = es.ensure_secrets(f)
    assert set(gen) == {"REDIS_PASSWORD", "MINIO_ROOT_PASSWORD", "ADMIN_TOKEN"}
    parsed = es._parse(f)
    assert parsed["POSTGRES_PASSWORD"] == "existing"   # preserved
    assert parsed["REDIS_PASSWORD"] and parsed["MINIO_ROOT_PASSWORD"]


def test_empty_value_treated_as_missing(tmp_path):
    f = tmp_path / ".env.secrets"
    f.write_text("REDIS_PASSWORD=\n", encoding="utf-8")
    gen = es.ensure_secrets(f)
    assert "REDIS_PASSWORD" in gen


def test_load_runtime_env_returns_present(tmp_path):
    f = tmp_path / ".env.secrets"
    f.write_text("POSTGRES_PASSWORD=p\nUNRELATED=x\n", encoding="utf-8")
    env = es.load_runtime_env(f)
    assert env == {"POSTGRES_PASSWORD": "p"}     # only runtime keys, only present


def test_generated_values_are_url_safe(tmp_path):
    f = tmp_path / ".env.secrets"
    es.ensure_secrets(f)
    for v in es._parse(f).values():
        assert all(c.isalnum() or c in "-_" for c in v)   # safe in URLs/compose
