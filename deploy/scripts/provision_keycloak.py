#!/usr/bin/env python3
"""Provision the Keycloak realm the backend↔Keycloak contract needs (idempotent).

Automates exactly what the backend requires to consume Keycloak tokens (D4.6/D4.7):
a realm, an OIDC client, a SHARED client scope carrying the `groups` (full path)
and `org` protocol mappers, and the group taxonomy. Users / LDAP federation /
upstream IdPs (Google, SAML) are operator/business config — NOT created here.

This is the automation behind the "professional" contract: instead of hand-clicking
the admin console, run this (or wire it into the deploy / P11). Idempotent — safe
to re-run; existing objects are updated, not duplicated.

Usage
-----
    python deploy/scripts/provision_keycloak.py \
        --server http://localhost:8088 --realm facil \
        --admin-user admin --admin-password admin \
        --client facil-backend --groups agents,supervisors

Exit codes: 0 ok · 1 error.
"""

from __future__ import annotations

import argparse
import sys

import httpx

# The two claim mappers the backend's federation reads (app/auth/federation.py):
# `groups` (full path, e.g. /agents) -> role mapping; `org` (user attribute) -> scope.
_MAPPERS = [
    {"name": "groups", "protocol": "openid-connect",
     "protocolMapper": "oidc-group-membership-mapper",
     "config": {"claim.name": "groups", "full.path": "true",
                "access.token.claim": "true", "id.token.claim": "false"}},
    {"name": "org", "protocol": "openid-connect",
     "protocolMapper": "oidc-usermodel-attribute-mapper",
     "config": {"user.attribute": "org", "claim.name": "org",
                "jsonType.label": "String", "access.token.claim": "true"}},
]


def _admin_token(c: httpx.Client, server: str, user: str, pw: str) -> str:
    r = c.post(f"{server}/realms/master/protocol/openid-connect/token",
               data={"client_id": "admin-cli", "username": user, "password": pw,
                     "grant_type": "password"})
    r.raise_for_status()
    return r.json()["access_token"]


def provision(server: str, realm: str, admin_user: str, admin_password: str,
              client_id: str, groups: list[str], *,
              public_client: bool = False) -> dict:
    out: dict = {"realm": realm, "client": client_id, "groups": [], "mappers": []}
    with httpx.Client(timeout=20) as c:
        H = {"Authorization": f"Bearer {_admin_token(c, server, admin_user, admin_password)}"}
        api = f"{server}/admin/realms"

        # 1. realm (idempotent)
        if c.get(f"{api}/{realm}", headers=H).status_code == 404:
            c.post(api, headers=H, json={"realm": realm, "enabled": True}).raise_for_status()
            out["created_realm"] = True

        # 2. allow the unmanaged `org` user attribute (Keycloak 24+ user profile)
        prof = c.get(f"{api}/{realm}/users/profile", headers=H).json()
        if prof.get("unmanagedAttributePolicy") != "ENABLED":
            prof["unmanagedAttributePolicy"] = "ENABLED"
            c.put(f"{api}/{realm}/users/profile", headers=H, json=prof)

        # 3. a SHARED client scope carrying the contract mappers (professional:
        #    one scope reused by every client, not per-client duplication)
        scope_name = "facil-contract"
        scopes = c.get(f"{api}/{realm}/client-scopes", headers=H).json()
        scope = next((s for s in scopes if s["name"] == scope_name), None)
        if scope is None:
            c.post(f"{api}/{realm}/client-scopes", headers=H, json={
                "name": scope_name, "protocol": "openid-connect",
                "attributes": {"include.in.token.scope": "true"}})
            scope = next(s for s in c.get(f"{api}/{realm}/client-scopes", headers=H).json()
                         if s["name"] == scope_name)
        existing_m = {m["name"] for m in c.get(
            f"{api}/{realm}/client-scopes/{scope['id']}/protocol-mappers/models",
            headers=H).json()}
        for m in _MAPPERS:
            if m["name"] not in existing_m:
                c.post(f"{api}/{realm}/client-scopes/{scope['id']}/protocol-mappers/models",
                       headers=H, json=m)
                out["mappers"].append(m["name"])

        # 4. client (idempotent) + attach the shared scope as a default scope
        clients = c.get(f"{api}/{realm}/clients?clientId={client_id}", headers=H).json()
        if not clients:
            c.post(f"{api}/{realm}/clients", headers=H, json={
                "clientId": client_id, "enabled": True,
                "publicClient": public_client,
                "directAccessGrantsEnabled": public_client,
                "standardFlowEnabled": True, "redirectUris": ["*"]})
            clients = c.get(f"{api}/{realm}/clients?clientId={client_id}", headers=H).json()
            out["created_client"] = True
        cid = clients[0]["id"]
        c.put(f"{api}/{realm}/clients/{cid}/default-client-scopes/{scope['id']}", headers=H)

        # 4b. confidential client secret — the BFF authenticates with it on the
        #     server-side code->token exchange. Public clients have none.
        if not public_client:
            sec = c.get(f"{api}/{realm}/clients/{cid}/client-secret", headers=H)
            if sec.status_code == 200:
                out["client_secret"] = sec.json().get("value", "")

        # 5. group taxonomy (idempotent)
        existing_g = {g["name"] for g in c.get(f"{api}/{realm}/groups", headers=H).json()}
        for g in groups:
            if g and g not in existing_g:
                c.post(f"{api}/{realm}/groups", headers=H, json={"name": g})
                out["groups"].append(g)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--server", default="http://localhost:8088")
    p.add_argument("--realm", default="facil")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-password", default="admin")
    p.add_argument("--client", default="facil-backend")
    p.add_argument("--public-client", action="store_true",
                   help="Public + direct-grant (DEV/TEST only; prod = confidential).")
    p.add_argument("--groups", default="agents",
                   help="Comma-separated group names to ensure exist.")
    a = p.parse_args(argv)
    try:
        res = provision(a.server, a.realm, a.admin_user, a.admin_password, a.client,
                        [g.strip() for g in a.groups.split(",") if g.strip()],
                        public_client=a.public_client)
    except (httpx.HTTPError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"[OK] provisioned realm '{res['realm']}': {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
