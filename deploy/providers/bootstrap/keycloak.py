#!/usr/bin/env python3
"""Keycloak provisioner — realm + OIDC client for the federated auth contract (K).

Applies when any surface enables ``keycloak_oidc`` (``auth.{citizen,agent}_methods``).
Drives the existing, idempotent ``deploy/scripts/provision_keycloak.py`` against the
running Keycloak (host-published port) to create the realm, the ``facil-contract``
client scope (groups + org mappers the backend federation reads), the confidential
OIDC client and the group taxonomy — then captures the connection facts the backend
verifier and the frontend BFF need.

Split-horizon OIDC (dev): the ``iss`` claim must match what the BROWSER reaches, so
``oidc_issuer`` is host-facing (``http://localhost:<port>/realms/<realm>``), while the
backend fetches JWKS server-side over the Docker network
(``http://keycloak:8080/...``). The two are separate config keys by design.

Scope (D5/K): the realm + client contract only. Users / LDAP / upstream IdPs are
operator/business config, never seeded here.
"""

from __future__ import annotations

import time

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from .context import BootstrapContext, vc
from .env_secrets import env_value
from .state import ProvisionStep

NAME = "keycloak"

# In-network service address (compose service `keycloak`, container port 8080) the
# backend uses for server-side JWKS fetch — independent of the host-published port.
_INTERNAL = "http://keycloak:8080"


def _wait_ready(base: str, step, *, attempts: int = 40, delay: float = 3.0,
                sleep=time.sleep) -> bool:
    """Poll the (unauthenticated) master discovery doc until Keycloak serves it.

    Keycloak has no compose healthcheck and ``start-dev`` takes 20-40s to accept
    requests, so wait_for_healthy reports it 'ready' (running) far too early. We
    retry HOST-side on connection errors (no dependency on in-container tooling),
    mirroring the OpenBao readiness gate."""
    if httpx is None:
        return True  # can't probe; provision() will surface the real failure
    url = f"{base}/realms/master/.well-known/openid-configuration"
    for i in range(attempts):
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                if i:
                    step.actions.append(f"API ready after {i + 1} probe(s)")
                return True
        except httpx.RequestError:
            pass
        sleep(delay)
    return False


def is_applicable(cfg: vc.DeployConfig) -> bool:
    # Opt-in (default OFF) AND a surface actually uses keycloak_oidc. Default OFF
    # keeps the standard apply from waiting on the profile-gated keycloak service.
    if not cfg.auth.keycloak.enabled:
        return False
    methods = set(cfg.auth.citizen_methods) | set(cfg.auth.agent_methods)
    return "keycloak_oidc" in methods


def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    kc = cfg.auth.keycloak
    realm, client_id = kc.realm, kc.client_id
    host_base = f"http://localhost:{kc.http_port}"
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [
            f"provision realm '{realm}' + client '{client_id}' on {host_base}",
            f"ensure groups {kc.groups} + facil-contract scope (groups/org mappers)",
            "capture issuer/jwks/client_secret into state",
        ]
        return step.skip("dry-run: would provision Keycloak realm + client")

    # provision_keycloak lives in deploy/scripts (on sys.path via context.py).
    try:
        import provision_keycloak as pk  # noqa: E402
    except ImportError as exc:  # pragma: no cover
        return step.fail(f"provision_keycloak not importable: {exc}")

    if not _wait_ready(host_base, step):
        return step.fail("Keycloak API not ready (timed out waiting for the master "
                         "discovery doc) — is the `auth` profile up?")

    # The OIDC redirect URI must match the BFF callback exactly (no wildcard —
    # SECURITY, enforced in provision_keycloak). Host-facing frontend port.
    callback = f"http://localhost:{cfg.docker_local.frontend_port}/api/auth/oidc/callback"
    admin_pw = env_value(ctx.secrets_file, kc.admin_password_secret, "admin")
    try:
        res = pk.provision(host_base, realm, kc.admin_user, admin_pw,
                           client_id, list(kc.groups), public_client=False,
                           redirect_uris=[callback])
    except Exception as exc:  # httpx errors, bad admin creds, KeyError on response
        return step.fail(f"Keycloak provisioning failed: {type(exc).__name__}: {exc}")

    for k in ("created_realm", "created_client"):
        if res.get(k):
            step.actions.append(k.replace("_", " "))
    if res.get("groups"):
        step.actions.append(f"groups ensured: {', '.join(res['groups'])}")
    if res.get("mappers"):
        step.actions.append(f"mappers added: {', '.join(res['mappers'])}")

    secret = res.get("client_secret", "")
    if not secret:
        step.actions.append("WARN: no client_secret returned (public client?) — "
                            "the BFF code->token exchange needs a confidential client")

    step.secrets = {
        # Browser-facing issuer — MUST equal the token `iss` (what the browser hits).
        "oidc_issuer": f"{host_base}/realms/{realm}",
        # Server-side JWKS (backend, in-network) — decoupled from the public issuer.
        "oidc_jwks_uri": f"{_INTERNAL}/realms/{realm}/protocol/openid-connect/certs",
        "oidc_audience": client_id,
        "oidc_client_id": client_id,
        "oidc_client_secret": secret,
        "oidc_realm": realm,
    }
    return step.ok(f"realm '{realm}' + OIDC client '{client_id}' provisioned")
