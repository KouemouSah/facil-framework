"""Tests for deploy/scripts/render_web_env.py (K2 — frontend OIDC env)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import render_web_env as rwe  # noqa: E402

_KC = {
    "oidc_issuer": "http://localhost:8088/realms/facil",
    "oidc_client_id": "facil-backend",
    "oidc_client_secret": "SEKRET-123",
}


def _state(tmp_path, steps):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"steps": steps}), encoding="utf-8")
    return p


def test_web_oidc_rendered(tmp_path):
    state = _state(tmp_path, [{"name": "keycloak", "secrets": _KC}])
    content, has = rwe.render(state, frontend_url="http://localhost:3000")
    assert has is True
    assert "OIDC_ISSUER=http://localhost:8088/realms/facil" in content
    assert "OIDC_CLIENT_SECRET=SEKRET-123" in content      # BFF needs the secret
    assert "OIDC_REDIRECT_URI=http://localhost:3000/api/auth/oidc/callback" in content
    assert "NEXT_PUBLIC_OIDC_ENABLED=1" in content


def test_noop_without_keycloak(tmp_path):
    state = _state(tmp_path, [{"name": "postgres", "secrets": {"pg_app_password": "p"}}])
    content, has = rwe.render(state)
    assert has is False and content == ""
    out = tmp_path / "web.env"
    out.write_text("NEXT_PUBLIC_API_URL=keep\n", encoding="utf-8")
    assert rwe.main(["--state", str(state), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "NEXT_PUBLIC_API_URL=keep\n"  # untouched


def test_merge_preserves_web_config(tmp_path):
    state = _state(tmp_path, [{"name": "keycloak", "secrets": _KC}])
    out = tmp_path / "web.env"
    out.write_text("NEXT_PUBLIC_API_URL=http://localhost:8080\n", encoding="utf-8")
    assert rwe.main(["--state", str(state), "--out", str(out)]) == 0
    txt = out.read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_API_URL=http://localhost:8080" in txt   # config preserved
    assert "OIDC_ISSUER=" in txt and "NEXT_PUBLIC_OIDC_ENABLED=1" in txt
    assert b"\r\n" not in out.read_bytes()                      # LF-only


def test_idempotent(tmp_path):
    state = _state(tmp_path, [{"name": "keycloak", "secrets": _KC}])
    out = tmp_path / "web.env"
    out.write_text("NEXT_PUBLIC_API_URL=x\n", encoding="utf-8")
    rwe.main(["--state", str(state), "--out", str(out)])
    rwe.main(["--state", str(state), "--out", str(out)])
    txt = out.read_text(encoding="utf-8")
    assert txt.count("OIDC_ISSUER=") == 1 and txt.count(rwe.WEB_MARKER) == 1
