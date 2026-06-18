#!/usr/bin/env python3
"""Post-install hardening of the break-glass ADMIN_TOKEN (ADR-0009).

The break-glass token is a RANDOM bootstrap secret (never a default password) that
authorizes the first-run installer to create the first super-admin. Once that admin
exists it is a STANDING RBAC bypass and should be rotated or disabled.

This tool, run after install:
  - verifies the system is "installed" (a `*`-role admin exists) — REFUSES otherwise,
    so it never strands the bootstrap;
  - ROTATES ADMIN_TOKEN to a fresh random value (default — keeps an emergency path,
    invalidates the bootstrap-era token that may have transited logs), or DISABLES it
    (`--disable` → empty, locking the admin-token API entirely).

ADMIN_TOKEN lives only in .env.secrets (the backend's env_file) — not mirrored to the
vault — so updating that file + recreating the backend applies it.

Usage:
    python tools/break_glass.py            # rotate
    python tools/break_glass.py --disable   # disable (clear)
    FACIL_API=http://host:8080 python tools/break_glass.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SECRETS_FILE = REPO / ".env.secrets"
API = os.environ.get("FACIL_API", "http://localhost:8080")


def _installed() -> bool | None:
    """True/False from /system/install-status, or None if unreachable."""
    try:
        with urllib.request.urlopen(f"{API}/api/v1/system/install-status", timeout=10) as r:
            return bool(json.loads(r.read()).get("installed"))
    except (urllib.error.URLError, ValueError, OSError):
        return None


def _set_admin_token(value: str) -> bool:
    """Replace the ADMIN_TOKEN line in .env.secrets. Returns True if changed."""
    if not SECRETS_FILE.exists():
        print("ERROR: .env.secrets not found.", file=sys.stderr)
        return False
    text = SECRETS_FILE.read_text(encoding="utf-8")
    new_line = f"ADMIN_TOKEN={value}"
    if re.search(r"(?m)^ADMIN_TOKEN=.*$", text):
        text = re.sub(r"(?m)^ADMIN_TOKEN=.*$", new_line, text)
    else:
        text = text.rstrip("\n") + "\n" + new_line + "\n"
    SECRETS_FILE.write_text(text, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--disable", action="store_true",
                   help="Clear ADMIN_TOKEN (lock the admin-token API) instead of rotating.")
    p.add_argument("--force", action="store_true",
                   help="Skip the install-status check (use only if the API is down).")
    a = p.parse_args(argv)

    if not a.force:
        installed = _installed()
        if installed is None:
            print("ERROR: cannot reach /system/install-status — is the backend up? "
                  "Use --force only if you are certain a real admin exists.",
                  file=sys.stderr)
            return 1
        if not installed:
            print("REFUSING: no super-admin exists yet (system not installed). "
                  "Disabling the break-glass now would strand the bootstrap. "
                  "Create the first admin via /install first.", file=sys.stderr)
            return 1

    value = "" if a.disable else secrets.token_urlsafe(24)
    if not _set_admin_token(value):
        return 1
    action = "DISABLED (admin-token API locked)" if a.disable else "ROTATED"
    print(f"[OK] break-glass ADMIN_TOKEN {action} in {SECRETS_FILE.name}.")
    if not a.disable:
        print(f"     New token: {value}  (store it securely — shown once)")
    print("     Recreate the backend to apply: "
          "docker compose -f docker-compose.local.yml up -d --no-deps --force-recreate backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
