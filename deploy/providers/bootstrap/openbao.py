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
    re-runs do not pile up secret-ids) — but only after it is **validated against
    the live vault**: a dev in-memory vault recreate drops the secret_id, so a
    blind reuse would 400 the backend's AppRole login and silently fall back to
    env secrets. When the stored secret_id is no longer known, a fresh one is
    minted.

In dev mode OpenBao is in-memory, so this whole provisioning is re-applied on
every ``up`` — which is exactly why each step is idempotent.
"""

from __future__ import annotations

import json as _json
import time

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

# Runtime data-plane passwords (compose interpolation) — mirrored into OpenBao
# so the backend reads them centrally via the AppRole. .env.secrets stays the
# authoritative source for compose; OpenBao is the read store.
RUNTIME_SECRET_KEYS = ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD")

KV_PATH = "facil"          # kv-v2 mount path
BOOT_PATH = "boot"         # secret name under the mount
RUNTIME_PATH = "runtime"   # runtime data-plane passwords under the mount
INFRA_PATH = "infra"       # backend-consumed infra creds (DATABASE_URL, MinIO SA)
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


# OpenBao's /sys/health returns non-200 for standby/sealed/uninitialised, but any
# HTTP response means the API accepts connections — which is all we wait for.
_HEALTH_OK = (200, 429, 472, 473, 501, 503)


def _wait_api_ready(base, token, step, *, attempts=30, delay=1.0, sleep=None):
    """Poll /sys/health until the API accepts connections.

    The Docker healthcheck can report ``healthy`` a beat before the published
    port actually serves requests, so the very first call used to die with
    ``RemoteDisconnected`` and the whole step failed. Here we retry on connection
    errors (the transient) but treat ANY HTTP status — even an error one — as
    "the server is up", since that is what we need before provisioning.
    """
    sleep = sleep or time.sleep
    last_exc = None
    for i in range(attempts):
        try:
            _request("GET", f"{base}/sys/health", token, allow=_HEALTH_OK)
        except OpenBaoError:
            pass  # server answered with a status code → it is up
        except requests.RequestException as exc:  # not accepting connections yet
            last_exc = exc
            sleep(delay)
            continue
        if i:
            step.actions.append(f"API ready after {i + 1} probe(s)")
        return
    raise OpenBaoError(
        f"API not ready after {attempts} probe(s) "
        f"({attempts * delay:.0f}s): {last_exc}")


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


def _put_if_changed(base, token, path, desired, step, label):
    """Write-if-changed a kv-v2 secret. Returns the key count written/kept."""
    cur = _request("GET", f"{base}/{KV_PATH}/data/{path}", token, allow=(404,))
    current = cur.json().get("data", {}).get("data", {}) if cur.status_code == 200 else {}
    if current == desired:
        step.actions.append(f"{label} up to date ({len(desired)} keys)")
        return len(desired)
    _request("POST", f"{base}/{KV_PATH}/data/{path}", token, json={"data": desired})
    step.actions.append(f"{label} written to '{KV_PATH}/{path}' ({len(desired)} keys)")
    return len(desired)


def _ensure_infra_secrets(base, token, ctx, step):
    """Mirror the backend-consumed infra creds (facil_app DATABASE_URL + MinIO SA)
    into ``facil/infra`` (write-if-changed). Sourced from the postgres/minio steps
    of THIS run (ctx.completed), so the backend can resolve them from the vault
    instead of the env (S2). Covered by the read-only ``facil-backend`` policy."""
    pg = (ctx.completed or {}).get("postgres", {})
    mi = (ctx.completed or {}).get("minio", {})
    desired: dict[str, str] = {}
    if pg.get("pg_app_password"):
        role = pg.get("pg_app_role", "facil_app")
        db = pg.get("pg_app_db", "facil")
        desired["DATABASE_URL"] = (
            f"postgresql+asyncpg://{role}:{pg['pg_app_password']}@postgres:5432/{db}")
    if mi.get("minio_access_key"):
        desired["MINIO_ACCESS_KEY"] = mi["minio_access_key"]
        desired["MINIO_SECRET_KEY"] = mi.get("minio_secret_key", "")
    if not desired:
        # Expected to run AFTER postgres/minio (PROVISIONERS order) — empty here
        # means those steps did not populate ctx.completed (skipped/external mode,
        # or a single-provisioner re-run without prior state). Flag it clearly so
        # an unexpectedly-missing mirror is not read as a benign no-op.
        step.actions.append(
            "infra mirror SKIPPED — no postgres/minio creds in ctx (external mode "
            "or partial run); facil/infra not written")
        return 0
    return _put_if_changed(base, token, INFRA_PATH, desired, step, "infra secrets")


def _ensure_runtime_secrets(base, token, secrets_env, step):
    """Mirror the data-plane runtime passwords into ``facil/runtime`` (write-if-
    changed). Covered by the existing read-only ``facil-backend`` policy."""
    desired = {k: secrets_env[k] for k in RUNTIME_SECRET_KEYS
               if secrets_env.get(k)}
    if not desired:
        step.actions.append("no runtime secrets in .env.secrets to mirror")
        return 0
    cur = _request("GET", f"{base}/{KV_PATH}/data/{RUNTIME_PATH}", token,
                   allow=(404,))
    current = cur.json().get("data", {}).get("data", {}) if cur.status_code == 200 else {}
    if current == desired:
        step.actions.append(f"runtime secrets up to date ({len(desired)} keys)")
        return len(desired)
    _request("POST", f"{base}/{KV_PATH}/data/{RUNTIME_PATH}", token,
             json={"data": desired})
    step.actions.append(f"runtime secrets mirrored to '{KV_PATH}/{RUNTIME_PATH}' "
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


def _secret_id_valid(base, token, sid):
    """True if ``sid`` is still a live secret_id for the role.

    After a dev (in-memory) vault recreate the stored secret_id is gone, so
    reusing it blindly makes the backend's AppRole login fail (HTTP 400) and
    silently fall back to env secrets. OpenBao answers 200+data for a known
    secret_id and 204 (No Content) for an unknown one; any non-200 ⇒ invalid.
    """
    resp = _request(
        "POST", f"{base}/auth/approle/role/{ROLE_NAME}/secret-id/lookup",
        token, json={"secret_id": sid}, allow=(204, 404))
    if resp.status_code != 200:
        return False
    try:
        return bool(resp.json().get("data"))
    except (ValueError, _json.JSONDecodeError):
        return False


def _ensure_secret_id(base, token, ctx, step):
    prior = BootstrapState.load(ctx.state_file)
    if prior and (ps := prior.step(NAME)):
        if (sid := ps.secrets.get("openbao_secret_id", "")):
            if _secret_id_valid(base, token, sid):
                step.actions.append("approle secret_id reused from state")
                return sid
            step.actions.append(
                "stored secret_id unknown to vault (dev recreate?) — regenerating")
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
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [
            f"enable kv-v2 at '{KV_PATH}/'",
            f"write {len(BOOT_SECRET_KEYS)} boot secrets to '{KV_PATH}/{BOOT_PATH}'",
            f"mirror runtime passwords to '{KV_PATH}/{RUNTIME_PATH}'",
            f"upsert read-only policy '{POLICY_NAME}'",
            f"enable approle + role '{ROLE_NAME}' (role_id + secret_id)",
        ]
        return step.skip("dry-run: would provision OpenBao")

    if requests is None:
        return step.fail("requests not installed — cannot reach OpenBao API")

    token = env_value(ctx.secrets_file, o.dev_root_token_secret, "")
    if not token:
        return step.fail(
            f"{o.dev_root_token_secret} not set in .env.secrets — refusing to use the "
            f"guessable `root` default (SEC-001). Run ensure_secrets (or the apply) first.")

    secrets_env = load_env_file(ctx.secrets_file)
    try:
        _wait_api_ready(base, token, step)
        _ensure_kv_mount(base, token, step)
        n = _ensure_boot_secrets(base, token, secrets_env, step)
        _ensure_runtime_secrets(base, token, secrets_env, step)
        _ensure_infra_secrets(base, token, ctx, step)
        _ensure_policy(base, token, step)
        _ensure_approle(base, token, step)
        role_id = _role_id(base, token)
        secret_id = _ensure_secret_id(base, token, ctx, step)
    except (OpenBaoError, requests.RequestException) as exc:
        return step.fail(f"OpenBao API error: {exc}")
    except (KeyError, ValueError, _json.JSONDecodeError) as exc:
        return step.fail(f"unexpected OpenBao response: {exc}")

    step.secrets = {
        # In-network address for the backend: the container ALWAYS listens on 8200;
        # o.port is only the HOST-published port (operator-configurable). Using
        # o.port here would break if the operator remaps the host port.
        "openbao_addr": "http://openbao:8200",
        "openbao_kv_path": KV_PATH,
        "openbao_role_id": role_id,
        "openbao_secret_id": secret_id,
    }
    return step.ok(
        f"kv-v2 '{KV_PATH}/' + {n} boot secrets + policy '{POLICY_NAME}' "
        f"+ approle '{ROLE_NAME}'")
