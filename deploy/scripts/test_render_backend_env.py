"""Tests for deploy/scripts/render_backend_env.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import render_backend_env as rbe  # noqa: E402


def _write_state(tmp_path, steps):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"steps": steps}), encoding="utf-8")
    return p


def test_database_url_from_facil_app(tmp_path):
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {
            "pg_app_role": "facil_app", "pg_app_password": "s3cret", "pg_app_db": "facil"}},
    ])
    content, has = rbe.render(state, host="postgres")
    assert has is True
    assert "DATABASE_URL=postgresql+asyncpg://facil_app:s3cret@postgres:5432/facil" in content


def test_no_postgres_secret_warns(tmp_path):
    state = _write_state(tmp_path, [{"name": "minio", "secrets": {}}])
    content, has = rbe.render(state)
    assert has is False
    assert "DATABASE_URL" not in content


def test_minio_and_openbao_emitted(tmp_path):
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}},
        {"name": "minio", "secrets": {
            "minio_endpoint": "http://minio:9000", "minio_access_key": "facil-backend",
            "minio_secret_key": "k", "minio_bucket": "facil-documents"}},
        {"name": "openbao", "secrets": {
            "openbao_addr": "http://openbao:8200", "openbao_role_id": "rid",
            "openbao_secret_id": "sid"}},
    ])
    content, _ = rbe.render(state)
    assert "MINIO_ACCESS_KEY=facil-backend" in content
    assert "OPENBAO_ROLE_ID=rid" in content


def test_missing_state_file(tmp_path):
    content, has = rbe.render(tmp_path / "nope.json")
    assert has is False
    assert "DATABASE_URL" not in content


def test_main_writes_file(tmp_path):
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p", "pg_app_role": "facil_app"}}])
    out = tmp_path / "out.env"
    assert rbe.main(["--state", str(state), "--out", str(out)]) == 0
    assert "DATABASE_URL=" in out.read_text(encoding="utf-8")


def test_require_db_url_fails_when_absent(tmp_path):
    """#1 fix: fail loud (exit 1) instead of silently rendering no DATABASE_URL."""
    state = _write_state(tmp_path, [{"name": "minio", "secrets": {}}])
    out = tmp_path / "out.env"
    assert rbe.main(["--state", str(state), "--out", str(out), "--require-db-url"]) == 1


def test_require_db_url_ok_when_present(tmp_path):
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}}])
    out = tmp_path / "out.env"
    assert rbe.main(["--state", str(state), "--out", str(out), "--require-db-url"]) == 0


def test_output_has_no_crlf(tmp_path):
    """#4 fix: env file is LF-only (docker compose env_file stays clean on Windows)."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}}])
    out = tmp_path / "out.env"
    rbe.main(["--state", str(state), "--out", str(out)])
    assert b"\r\n" not in out.read_bytes()
