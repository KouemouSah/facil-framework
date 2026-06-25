#!/usr/bin/env python3
"""Dev/demo only — create or ensure loginable ADMIN accounts on a running stack.

This is deliberately NOT a seed. Shipping default-credential users is a security
anti-pattern (CWE-798); the platform only seeds the permission catalog + roles,
never accounts. This tool instead performs the *correct* operator bootstrap,
scripted and idempotent:

  1. register real accounts with STRONG, freshly-generated passwords,
  2. grant them the global ``admin`` role via the break-glass ``ADMIN_TOKEN``.

Credentials are printed once and written to a gitignored file. Refuses to run
against a production ENVIRONMENT. Existing accounts are reused (password NOT
reset — we never silently change a credential).

Usage:
    python tools/dev_create_admins.py
    ADMIN_EMAILS="alice@facil.local,bob@facil.local" python tools/dev_create_admins.py
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API = os.environ.get("FACIL_API", "http://localhost:8080")
SECRETS_FILE = REPO / ".env.secrets"
CREDS_FILE = REPO / ".admins.dev.json"
DEFAULT_EMAILS = "admin1@facil.local,admin2@facil.local"


def _env_from_secrets(key: str) -> str:
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")


def _req(method: str, path: str, *, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Admin-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or "null")
        except Exception:  # noqa: BLE001
            return e.code, None


def _strong_password() -> str:
    # Satisfies the policy (>=12, upper+lower+digit, uncommon); "Aa1" guarantees the
    # classes and token_urlsafe(12) makes it ~19 chars and unpredictable.
    return "Aa1" + secrets.token_urlsafe(12)


def main() -> int:
    if _env_from_secrets("ENVIRONMENT").lower() in {"production", "prod"} or \
            os.environ.get("ENVIRONMENT", "").lower() in {"production", "prod"}:
        print("REFUSING: this is a dev/demo tool — never run it against production.",
              file=sys.stderr)
        return 1

    # The ENVIRONMENT check guards the LOCAL secrets, but FACIL_API could point at a
    # remote prod backend. Refuse a non-local target unless explicitly acknowledged.
    host = urllib.parse.urlparse(API).hostname or ""
    if host not in {"localhost", "127.0.0.1", "::1", "backend"} \
            and not os.environ.get("FACIL_ALLOW_REMOTE"):
        print(f"REFUSING: FACIL_API={API} is not local. This tool creates admin "
              f"accounts and must not target a remote/production backend. Set "
              f"FACIL_ALLOW_REMOTE=1 only if you are certain.", file=sys.stderr)
        return 1

    token = _env_from_secrets("ADMIN_TOKEN")
    if not token:
        print("ERROR: no ADMIN_TOKEN in .env.secrets (the break-glass bootstrap "
              "token). Generate the stack secrets first.", file=sys.stderr)
        return 1

    st, roles = _req("GET", "/api/v1/rbac/roles", token=token)
    if st != 200 or not isinstance(roles, dict):
        print(f"ERROR: GET /rbac/roles -> {st}: {roles}", file=sys.stderr)
        return 1
    admin = next((r for r in roles.get("items", []) if r.get("code") == "admin"), None)
    if not admin:
        print("ERROR: 'admin' role not seeded — is the RBAC seed applied?",
              file=sys.stderr)
        return 1
    role_id = admin["id"]

    emails = [e.strip() for e in os.environ.get("ADMIN_EMAILS", DEFAULT_EMAILS).split(",")
              if e.strip()]
    # Preserve passwords already recorded for existing accounts, so re-running the
    # tool never DESTROYS the credentials it printed earlier (we can't recover them
    # from the bcrypt hash in the DB).
    prior_pw = {}
    if CREDS_FILE.exists():
        try:
            for a in json.loads(CREDS_FILE.read_text(encoding="utf-8")):
                if a.get("password") and not a["password"].startswith("("):
                    prior_pw[a["email"]] = a["password"]
        except (ValueError, OSError):
            pass
    out = []
    for email in emails:
        pw = _strong_password()
        st, acc = _req("POST", "/api/v1/auth/register",
                       body={"email": email, "password": pw,
                             "display_name": email.split("@")[0]})
        if st == 201 and isinstance(acc, dict):
            acc_id, created = acc["id"], True
        elif st == 409:
            q = urllib.parse.quote(email)
            s2, lst = _req("GET", f"/api/v1/admin/accounts?q={q}", token=token)
            items = (lst or {}).get("items", []) if isinstance(lst, dict) else []
            match = next((a for a in items if a.get("email") == email), None)
            if not match:
                print(f"WARN: {email} exists but lookup failed ({s2}); skipping.",
                      file=sys.stderr)
                continue
            # Reuse the previously-recorded password if we have it; otherwise the
            # account exists with a password we can't recover (we never reset it).
            acc_id, created = match["id"], False
            pw = prior_pw.get(email, "(unknown — existing account, not in creds file)")
        else:
            print(f"ERROR: register {email} -> {st}: {acc}", file=sys.stderr)
            continue

        st, asg = _req("POST", f"/api/v1/rbac/accounts/{acc_id}/roles",
                       token=token, body={"role_id": role_id})
        granted = "ok" if st in (200, 201, 409) else f"FAILED({st}: {asg})"
        out.append({"email": email, "password": pw, "account_id": acc_id,
                    "created": created, "admin_role": granted})

    CREDS_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\n=== Dev admin accounts — login at http://localhost:3000/login ===")
    for a in out:
        tag = "created" if a["created"] else "existing"
        print(f"  {a['email']:28} | {a['password']:24} | admin={a['admin_role']} ({tag})")
    print(f"\nWritten to {CREDS_FILE.name} (gitignored). Passwords shown once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
