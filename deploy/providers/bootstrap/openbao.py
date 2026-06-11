#!/usr/bin/env python3
"""OpenBao provisioner — kv-v2 mount + boot secrets + policy + AppRole.

Talks to OpenBao over its HTTP API via ``requests`` (decision D6 — already
available, no heavy SDK) on the host-published port. Applies for
``secrets.provider == "openbao"``. Scope (decision D5): secrets *consumption*
only — no PKI/mTLS (that is P7/P8).

What it provisions, all idempotently:
  - a ``kv-v2`` secrets engine at ``facil/`` (the app secrets namespace),
  - the boot secrets copied from ``.env.secrets`` into ``facil/boot`` (decision
    D4 — ``.env.secrets`` is kept as the runtime fallback), written only when
    they differ from what is already stored,
  - a read-only ``facil-backend`` ACL policy,
  - an AppRole the backend authenticates with; its ``role_id`` is stable and its
    ``secret_id`` is generated once and reused from the bootstrap state (so
    re-runs do not pile up secret-ids).

In dev mode OpenBao is in-memory, so this whole provisioning is re-applied on
every ``up`` — which is exactly why each step is idempotent.
"""

from __future__ import annotations

import json as _json

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # provision() degrades to a clear failed step.

from .context import BootstrapContext, vc
from .env_secrets import env_value, load_env_file
from .state import BootstrapState, ProvisionStep

NAME = "openbao"

# The 5 boot secrets generated at install (P1). Integration secrets (Gemini,
# Firebase, ...) are intentionally NOT mirrored here — they stay in .env.secrets
# and degrade gracefully when empty.
BOOT_SECRET_KEYS = (
    "JWT_SECRET_KEY", "SECRET_KEY", "TOTP_ENCRYPTION_KEY",
    "CRON_SECRET", "RECEIPT_VERIFICATION_SECRET",
)

KV_PATH = "facil"          # kv-v2 mount path
BOOT_PATH = "boot"         # secret name under the mount
POLICY_NAME = "facil-backend"
ROLE_NAME = "facil-backend"

POLICY_HCL = (
    'path "facil/data/*"     { capabilities = ["read"] }\n'
    'path "facil/metadata/*" { capabilities = ["read", "list"] }\n'
)


class OpenBaoError(RuntimeError):
    pass


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.secrets.provider == "openbao"


# ---------------------------------------------------------------------------
# HTTP seam (single mockable function)
# ---------------------------------------------------------------------------

def _request(method, url, token, *, json=None, allow=()):
    """One OpenBao API call. Raises OpenBaoError on unexpected status.

    ``allow`` lists extra status codes the caller tolerates (e.g. 404 when
    probing whether a secret exists yet).
    """
    resp = requests.request(
        method, url, headers={"X-Vault-Token": token}, json=json, timeout=10)
    if resp.status_code >= 400 and resp.status_code not in allow:
        raise OpenBaoError(f"{method} {url} -> {resp.status_code}: {resp.text[:200]}")
    return resp


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def _ensure_kv_mount(base, token, step):
    body = _request("GET", f"{base}/sys/mounts", token).json()
    mounts = body.get("data", body)
    if f"{KV_PATH}/" in mounts:
        step.actions.append(f"kv-v2 '{KV_PATH}/' already mounted")
        return
    _request("POST", f"{base}/sys/mounts/{KV_PATH}", token,
             json={"type": "kv", "options": {"version": "2"}})
    step.actions.append(f"kv-v2 mounted at '{KV_PATH}/'")


def _ensure_boot_secrets(base, token, secrets_env, step):
    desired = {k: secrets_env[k] for k in BOOT_SECRET_KEYS
               if secrets_env.get(k)}
    if not desired:
        step.actions.append("no boot secrets found in .env.secrets to mirror")
        return 0
    cur = _request("GET", f"{base}/{KV_PATH}/data/{BOOT_PATH}", token,
                   allow=(404,))
    current = cur.json().get("data", {}).get("data", {}) if cur.status_code == 200 else {}
    if current == desired:
        step.actions.append(f"boot secrets up to date ({len(desired)} keys)")
        return len(desired)
    _request("POST", f"{base}/{KV_PATH}/data/{BOOT_PATH}", token,
             json={"data": desired})
    step.actions.append(f"boot secrets written to '{KV_PATH}/{BOOT_PATH}' "
                        f"({len(desired)} keys)")
    return len(desired)


def _ensure_policy(base, token, step):
    # PUT is an upsert — idempotent by construction.
    _request("PUT", f"{base}/sys/policies/acl/{POLICY_NAME}", token,
             json={"policy": POLICY_HCL})
    step.actions.append(f"policy '{POLICY_NAME}' (read-only on {KV_PATH}/*) ensured")


def _ensure_approle(base, token, step):
    auths = _request("GET", f"{base}/sys/auth", token).json()
    auths = auths.get("data", auths)
    if "approle/" not in auths:
        _request("POST", f"{base}/sys/auth/approle", token,
                 json={"type": "approle"})
        step.actions.append("approle auth method enabled")
    else:
        step.actions.append("approle auth method already enabled")
    _request("POST", f"{base}/auth/approle/role/{ROLE_NAME}", token,
             json={"token_policies": POLICY_NAME, "token_ttl": "1h",
                   "token_max_ttl": "4h"})
    step.actions.append(f"approle role '{ROLE_NAME}' ensured")


def _role_id(base, token):
    return _request("GET", f"{base}/auth/approle/role/{ROLE_NAME}/role-id",
                    token).json()["data"]["role_id"]


def _ensure_secret_id(base, token, ctx, step):
    prior = BootstrapState.load(ctx.state_file)
    if prior and (ps := prior.step(NAME)):
        if (sid := ps.secrets.get("openbao_secret_id", "")):
            step.actions.append("approle secret_id reused from state")
            return sid
    sid = _request("POST", f"{base}/auth/approle/role/{ROLE_NAME}/secret-id",
                   token).json()["data"]["secret_id"]
    step.actions.append("approle secret_id generated")
    return sid


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    o = cfg.secrets.openbao
    base = f"http://localhost:{o.port}/v1"
    token = env_value(ctx.secrets_file, o.dev_root_token_secret, "root")
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [
            f"enable kv-v2 at '{KV_PATH}/'",
            f"write {len(BOOT_SECRET_KEYS)} boot secrets to '{KV_PATH}/{BOOT_PATH}'",
            f"upsert read-only policy '{POLICY_NAME}'",
            f"enable approle + role '{ROLE_NAME}' (role_id + secret_id)",
        ]
        return step.skip("dry-run: would provision OpenBao")

    if requests is None:
        return step.fail("requests not installed — cannot reach OpenBao API")

    secrets_env = load_env_file(ctx.secrets_file)
    try:
        _ensure_kv_mount(base, token, step)
        n = _ensure_boot_secrets(base, token, secrets_env, step)
        _ensure_policy(base, token, step)
        _ensure_approle(base, token, step)
        role_id = _role_id(base, token)
        secret_id = _ensure_secret_id(base, token, ctx, step)
    except (OpenBaoError, requests.RequestException) as exc:
        return step.fail(f"OpenBao API error: {exc}")
    except (KeyError, ValueError, _json.JSONDecodeError) as exc:
        return step.fail(f"unexpected OpenBao response: {exc}")

    step.secrets = {
        "openbao_addr": f"http://openbao:{o.port}",   # in-network address for backend
        "openbao_kv_path": KV_PATH,
        "openbao_role_id": role_id,
        "openbao_secret_id": secret_id,
    }
    return step.ok(
        f"kv-v2 '{KV_PATH}/' + {n} boot secrets + policy '{POLICY_NAME}' "
        f"+ approle '{ROLE_NAME}'")
