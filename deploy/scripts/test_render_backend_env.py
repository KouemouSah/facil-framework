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


def test_merge_preserves_existing_config(tmp_path):
    """render_env.py's config keys must survive — render_backend_env only ADDS
    the bootstrap secrets (the two renderers share .env.deploy.gen)."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p", "pg_app_role": "facil_app"}}])
    out = tmp_path / "out.env"
    out.write_text("BANGE_MERCHANT_ID=42\nENVIRONMENT=development\n", encoding="utf-8")
    assert rbe.main(["--state", str(state), "--out", str(out)]) == 0
    txt = out.read_text(encoding="utf-8")
    assert "BANGE_MERCHANT_ID=42" in txt      # config preserved
    assert "ENVIRONMENT=development" in txt    # config preserved
    assert "DATABASE_URL=" in txt              # secret added


def test_merge_is_idempotent(tmp_path):
    """Re-running must not duplicate the managed block or the config keys."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p", "pg_app_role": "facil_app"}}])
    out = tmp_path / "out.env"
    out.write_text("BANGE_MERCHANT_ID=42\n", encoding="utf-8")
    rbe.main(["--state", str(state), "--out", str(out)])
    rbe.main(["--state", str(state), "--out", str(out)])
    txt = out.read_text(encoding="utf-8")
    assert txt.count("DATABASE_URL=") == 1
    assert txt.count("BANGE_MERCHANT_ID=42") == 1
    assert txt.count(rbe.MANAGED_MARKER) == 1


def test_merge_overrides_stale_secret(tmp_path):
    """A stale managed key loose in the body is replaced, not duplicated."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "new", "pg_app_role": "facil_app"}}])
    out = tmp_path / "out.env"
    out.write_text("FOO=keep\nDATABASE_URL=postgresql+asyncpg://old:old@h:5432/d\n",
                   encoding="utf-8")
    rbe.main(["--state", str(state), "--out", str(out)])
    txt = out.read_text(encoding="utf-8")
    assert txt.count("DATABASE_URL=") == 1
    assert "new" in txt and "old:old" not in txt
    assert "FOO=keep" in txt


def test_oidc_block_from_keycloak_step(tmp_path):
    """K2: a keycloak step in state emits AUTH_METHODS + AUTH_OIDC_* (no secret)."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}},
        {"name": "keycloak", "secrets": {
            "oidc_issuer": "http://localhost:8088/realms/facil",
            "oidc_jwks_uri": "http://keycloak:8080/realms/facil/protocol/openid-connect/certs",
            "oidc_audience": "facil-backend", "oidc_client_id": "facil-backend",
            "oidc_client_secret": "SEKRET"}}])
    content, _ = rbe.render(state)
    assert "AUTH_METHODS=native,keycloak_oidc" in content
    assert "AUTH_OIDC_ISSUER=http://localhost:8088/realms/facil" in content
    assert "AUTH_OIDC_JWKS_URI=http://keycloak:8080/realms/facil/" in content
    assert "AUTH_OIDC_CLIENT_ID=facil-backend" in content
    assert "SEKRET" not in content              # client_secret never in backend env
    assert "AUTH_OIDC_CLIENT_SECRET" not in content


def test_no_oidc_without_keycloak_step(tmp_path):
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}}])
    content, _ = rbe.render(state)
    assert "AUTH_METHODS" not in content and "AUTH_OIDC" not in content


def test_output_has_no_crlf(tmp_path):
    """#4 fix: env file is LF-only (docker compose env_file stays clean on Windows)."""
    state = _write_state(tmp_path, [
        {"name": "postgres", "secrets": {"pg_app_password": "p"}}])
    out = tmp_path / "out.env"
    rbe.main(["--state", str(state), "--out", str(out)])
    assert b"\r\n" not in out.read_bytes()
