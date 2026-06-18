#!/usr/bin/env python3
"""Render the frontend's OIDC env from the bootstrap state (K2).

The Keycloak bootstrap step mints the realm + confidential client and records the
OIDC facts in deploy/.bootstrap-state.json. The frontend BFF (Next.js) needs them
server-side to run the auth-code flow (issuer, client id/secret, redirect uri) and
NEXT_PUBLIC_OIDC_ENABLED to surface the SSO button. This merges that block into
packages/web/.env.deploy.gen WITHOUT clobbering the config render_env.py wrote
(distinct managed marker, single block per file). No-op when Keycloak wasn't
provisioned (no keycloak step / not enabled).

Usage:
    python deploy/scripts/render_web_env.py
    python deploy/scripts/render_web_env.py --frontend-url http://localhost:3000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_backend_env as rbe  # noqa: E402  (reuse merge_into / _state_secrets)

DEPLOY_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DEPLOY_DIR.parent
DEFAULT_STATE = DEPLOY_DIR / ".bootstrap-state.json"
DEFAULT_OUT = REPO_ROOT / "packages" / "web" / ".env.deploy.gen"
WEB_MARKER = "# --- render_web_env: Keycloak OIDC (managed) ---"


def render(state_path: Path = DEFAULT_STATE, *,
           frontend_url: str = "http://localhost:3000") -> tuple[str, bool]:
    """Build the web OIDC block. Returns (content, has_oidc)."""
    kc = rbe._state_secrets(state_path).get("keycloak", {})
    issuer = kc.get("oidc_issuer", "")
    if not issuer:
        return "", False
    lines = [
        f"OIDC_ISSUER={issuer}\n",
        f"OIDC_CLIENT_ID={kc.get('oidc_client_id', '')}\n",
        f"OIDC_CLIENT_SECRET={kc.get('oidc_client_secret', '')}\n",
        f"OIDC_REDIRECT_URI={frontend_url.rstrip('/')}/api/auth/oidc/callback\n",
        "NEXT_PUBLIC_OIDC_ENABLED=1\n",
    ]
    return "".join(lines), True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--frontend-url", default="http://localhost:3000")
    a = p.parse_args(argv)
    try:
        content, has_oidc = render(a.state, frontend_url=a.frontend_url)
        if not has_oidc:
            print("[OK] no Keycloak in state — frontend OIDC env unchanged.")
            return 0
        existing = a.out.read_text(encoding="utf-8") if a.out.exists() else ""
        merged = rbe.merge_into(existing, content, marker=WEB_MARKER)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(merged, encoding="utf-8", newline="\n")
    except OSError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"[OK] wrote OIDC env -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
