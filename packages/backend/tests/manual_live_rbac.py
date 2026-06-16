"""Manual LIVE RBAC check against the running docker_local backend (D4.3).

Not a pytest — run by hand against http://localhost:8080 after rebuilding the
app tier. Proves scope enforcement end-to-end on real Postgres with real JWTs:
bootstrap admin (token) seeds, creates two orgs, registers a member scoped to
org A; the member reads A (200) but not B (403). Usage:

    "C:/facil_framework/.venv/Scripts/python.exe" packages/backend/tests/manual_live_rbac.py
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("FACIL_BASE", "http://localhost:8080")
ADMIN = {"X-Admin-Token": os.environ.get("ADMIN_TOKEN", "")}
ORG = "/api/v1/modules/organization"


def _ok(cond: bool, label: str) -> None:
    print(("  OK  " if cond else " FAIL ") + label)
    if not cond:
        _ok.failed = True  # type: ignore[attr-defined]


def main() -> int:
    _ok.failed = False  # type: ignore[attr-defined]
    with httpx.Client(base_url=BASE, timeout=15) as c:
        h = c.get("/health").json()
        print("health:", h)

        r = c.post("/api/v1/rbac/admin/reseed?profile=empty", headers=ADMIN)
        _ok(r.status_code == 200, f"reseed -> {r.status_code} {r.text[:120]}")

        roles = c.get("/api/v1/rbac/roles", headers=ADMIN).json()
        member = next(x["id"] for x in roles if x["code"] == "member")

        import uuid
        suffix = uuid.uuid4().hex[:8]
        org_a = c.post(f"{ORG}/", headers=ADMIN,
                       json={"code": f"a{suffix}", "legal_name": "A"}).json()["id"]
        org_b = c.post(f"{ORG}/", headers=ADMIN,
                       json={"code": f"b{suffix}", "legal_name": "B"}).json()["id"]

        email = f"alice{suffix}@x.com"
        pw = "Sup3rStr0ng!pw"
        acc = c.post("/api/v1/auth/register",
                     json={"password": pw, "email": email}).json()
        c.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=ADMIN,
               json={"role_id": member, "organization_id": org_a})

        login = c.post("/api/v1/auth/login",
                       json={"identifier": email, "password": pw})
        _ok(login.status_code == 200, f"login -> {login.status_code}")
        bearer = {"Authorization": f"Bearer {login.json()['access']}"}

        ra = c.get(f"{ORG}/{org_a}", headers=bearer)
        _ok(ra.status_code == 200, f"member reads OWN org A -> {ra.status_code}")
        rb = c.get(f"{ORG}/{org_b}", headers=bearer)
        _ok(rb.status_code == 403, f"member denied OTHER org B -> {rb.status_code}")
        rw = c.put(f"{ORG}/{org_a}", headers=bearer, json={"legal_name": "A2"})
        _ok(rw.status_code == 403, f"member (read-only) cannot write A -> {rw.status_code}")
        rl = c.get(f"{ORG}/", headers=bearer)
        ids = {o["id"] for o in rl.json()} if rl.status_code == 200 else set()
        _ok(rl.status_code == 200 and org_a in ids and org_b not in ids,
            f"global list scope-filtered (A yes / B no) -> {rl.status_code} {sorted(ids)}")

    failed = getattr(_ok, "failed", False)
    print("\nRESULT:", "FAILED" if failed else "ALL PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
