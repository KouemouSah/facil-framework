#!/usr/bin/env python3
"""MinIO provisioner — bucket + versioning + private policy + scoped service account.

Driven entirely through a one-shot ``minio/mc`` container on the stack network
(decision D6): ``mc`` is the canonical MinIO admin tool and, unlike the plain S3
API, can mint a *scoped* service account (decision D3 — the backend never
receives root credentials). Applies for ``storage.provider == "minio"``.

Every operation is idempotent so the provisioner is safe to re-run on every
``up``:
  - ``mc mb --ignore-existing``     bucket creation is a no-op if it exists
  - ``mc version enable``           enabling twice is a no-op
  - ``mc anonymous set none``       re-asserting private is a no-op
  - service account                 reused if present (secret recovered from the
                                    bootstrap state file); rotated only if the
                                    account exists but its secret is unknown

The scoped service-account secret is generated once and persisted in
``.bootstrap-state.json`` so re-runs are stable and the value survives for
``render_env`` to wire into the backend (Phase D).

The cloud S3 path (``provider == "s3"``) is intentionally NOT handled here yet —
it needs boto3 + IAM and lands when cloud provisioning is actually built.
"""

from __future__ import annotations

import json
import logging
import secrets as _secrets

from .context import BootstrapContext, vc
from .docker_helpers import DockerError, run_oneshot
from .env_secrets import env_value
from .state import BootstrapState, ProvisionStep

logger = logging.getLogger(__name__)

NAME = "minio"
MC_IMAGE = "minio/mc:latest"
ALIAS = "facil"               # mc alias name (via MC_HOST_<alias> env)
# Weak last-resort default used ONLY when MINIO_ROOT_PASSWORD is absent (ensure_secrets
# not run). The compose now requires the secret (${MINIO_ROOT_PASSWORD:?}), so this is
# a footgun for an out-of-band run — provision() warns loudly when it falls back (F5).
DEFAULT_ROOT_PASSWORD = "facilminio"


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.storage.provider == "minio"


# ---------------------------------------------------------------------------
# Least-privilege policy (decision D3)
# ---------------------------------------------------------------------------

def scoped_policy(documents_bucket: str, compliance_bucket: str | None = None) -> dict:
    """Least-privilege S3 policy for the backend service account (D3).

    documents: full object rw + listing.
    compliance (WORM): read + write + set-retention, but **NO DeleteObject** —
    defense in depth on top of Object-Lock so the backend cannot even attempt a
    delete. Nothing else, no access to any other bucket.
    """
    statements = [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                "s3:ListMultipartUploadParts", "s3:AbortMultipartUpload",
            ],
            "Resource": [f"arn:aws:s3:::{documents_bucket}/*"],
        },
        {
            "Effect": "Allow",
            "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
            "Resource": [f"arn:aws:s3:::{documents_bucket}"],
        },
    ]
    if compliance_bucket:
        statements += [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject", "s3:PutObject", "s3:PutObjectRetention",
                    "s3:GetObjectRetention", "s3:ListMultipartUploadParts",
                    "s3:AbortMultipartUpload",
                ],
                "Resource": [f"arn:aws:s3:::{compliance_bucket}/*"],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket", "s3:GetBucketLocation",
                    "s3:GetBucketObjectLockConfiguration",
                ],
                "Resource": [f"arn:aws:s3:::{compliance_bucket}"],
            },
        ]
    return {"Version": "2012-10-17", "Statement": statements}


# ---------------------------------------------------------------------------
# mc invocation
# ---------------------------------------------------------------------------

def _mc(ctx, args, *, root_user, root_pwd, entrypoint=None, check=True):
    """Run a single ``mc`` invocation in a throwaway container on the stack net.

    Credentials are passed via ``MC_HOST_<alias>`` so there is no separate
    ``mc alias set`` step and the secret never lands in an argv visible to
    ``docker inspect`` of a *persistent* container (this one is ``--rm``).
    """
    env = {f"MC_HOST_{ALIAS}": f"http://{root_user}:{root_pwd}@minio:9000"}
    return run_oneshot(MC_IMAGE, args, network=ctx.network, env=env,
                       entrypoint=entrypoint, check=check)


def _svcacct_policy_script(policy: str, mc_cmd: str) -> str:
    """sh -c body: write the inline policy file in-container, then run mc_cmd."""
    return (
        "set -e\n"
        f"cat > /tmp/sa-policy.json <<'JSON'\n{policy}\nJSON\n"
        f"{mc_cmd}\n"
    )


def _ensure_service_account(ctx, sa_access, documents_bucket, compliance_bucket,
                            root_user, root_pwd, step: ProvisionStep) -> str:
    """Create / reuse / rotate the scoped service account. Returns its secret.

    The inline policy is (re)applied on every run — on reuse via ``svcacct edit``
    — so a policy change (e.g. adding the compliance bucket) is picked up without
    rotating the secret.
    """
    policy = json.dumps(scoped_policy(documents_bucket, compliance_bucket))
    info = _mc(ctx, ["admin", "user", "svcacct", "info", ALIAS, sa_access],
               root_user=root_user, root_pwd=root_pwd, check=False)
    exists = info.returncode == 0

    prior_secret = ""
    prior = BootstrapState.load(ctx.state_file)
    if prior and (ps := prior.step(NAME)):
        prior_secret = ps.secrets.get("minio_secret_key", "")

    if exists and prior_secret:
        # Reuse the secret but ensure the policy is current (idempotent edit).
        _mc(ctx, ["-c", _svcacct_policy_script(
            policy, f"mc admin user svcacct edit {ALIAS} '{sa_access}' "
                    f"--policy /tmp/sa-policy.json")],
            root_user=root_user, root_pwd=root_pwd, entrypoint="sh")
        step.actions.append(
            f"service account '{sa_access}' present — secret reused, policy ensured")
        return prior_secret
    if exists and not prior_secret:
        _mc(ctx, ["admin", "user", "svcacct", "rm", ALIAS, sa_access],
            root_user=root_user, root_pwd=root_pwd, check=False)
        step.actions.append(
            f"service account '{sa_access}' existed without a known secret — rotated")

    new_secret = _secrets.token_hex(20)
    _mc(ctx, ["-c", _svcacct_policy_script(
        policy, f"mc admin user svcacct add --access-key '{sa_access}' "
                f"--secret-key '{new_secret}' --policy /tmp/sa-policy.json "
                f"{ALIAS} {root_user}")],
        root_user=root_user, root_pwd=root_pwd, entrypoint="sh")
    step.actions.append(
        f"service account '{sa_access}' created (rw '{documents_bucket}'"
        + (f", write-only '{compliance_bucket}'" if compliance_bucket else "") + ")")
    return new_secret


def _ensure_compliance_bucket(ctx, m, root_user, root_pwd, step) -> str | None:
    """Create the WORM (Object-Lock) compliance bucket + default retention.

    Object-Lock can ONLY be enabled at bucket creation, so this is a dedicated
    bucket separate from default_bucket. Object-Lock auto-enables versioning.
    Idempotent: ``--ignore-existing`` on the bucket; ``retention set --default``
    re-applied is a no-op. Returns the bucket name (or None if disabled).

    GOVERNANCE: privileged users can bypass (dev-cleanable). COMPLIANCE:
    immutable even to root until expiry (production legal hold).
    """
    c = m.compliance
    if not c.enabled:
        step.actions.append("compliance bucket disabled (config)")
        return None
    ctarget = f"{ALIAS}/{c.bucket}"
    _mc(ctx, ["mb", "--with-lock", "--ignore-existing", ctarget],
        root_user=root_user, root_pwd=root_pwd)
    step.actions.append(f"WORM bucket '{c.bucket}' ensured (object-lock + versioning)")
    _mc(ctx, ["anonymous", "set", "none", ctarget],
        root_user=root_user, root_pwd=root_pwd)
    _mc(ctx, ["retention", "set", "--default", c.retention_mode.upper(),
              f"{c.retention_days}d", ctarget],
        root_user=root_user, root_pwd=root_pwd)
    step.actions.append(
        f"default retention {c.retention_mode.upper()} {c.retention_days}d "
        f"on '{c.bucket}'")
    return c.bucket


def _existing_noncurrent_days(ctx, bucket, root_user, root_pwd) -> set[int]:
    """NoncurrentDays values of existing lifecycle rules (for idempotency).

    ``mc ilm rule add`` is NOT idempotent (it mints a new rule each call), so we
    must check before adding to avoid duplicate rules.
    """
    res = _mc(ctx, ["ilm", "rule", "ls", "--json", f"{ALIAS}/{bucket}"],
              root_user=root_user, root_pwd=root_pwd, check=False)
    days: set[int] = set()
    try:
        rules = (json.loads(res.stdout).get("config") or {}).get("Rules") or []
        for r in rules:
            nv = (r or {}).get("NoncurrentVersionExpiration") or {}
            if "NoncurrentDays" in nv:
                days.add(int(nv["NoncurrentDays"]))
    except (ValueError, TypeError, json.JSONDecodeError):
        pass  # no config / unparseable -> treat as no rules
    return days


def _ensure_lifecycle(ctx, bucket, days, root_user, root_pwd, step) -> None:
    """Expire non-current object versions after N days (versioned buckets only).

    NOT applied to the WORM bucket: expiring versions there conflicts with the
    Object-Lock retention by design.
    """
    if days <= 0:
        return
    if days in _existing_noncurrent_days(ctx, bucket, root_user, root_pwd):
        step.actions.append(
            f"lifecycle: non-current expire {days}d on '{bucket}' already set")
        return
    _mc(ctx, ["ilm", "rule", "add", "--noncurrent-expire-days", str(days),
              f"{ALIAS}/{bucket}"], root_user=root_user, root_pwd=root_pwd)
    step.actions.append(
        f"lifecycle: non-current versions expire after {days}d on '{bucket}'")


def _current_quota_bytes(ctx, bucket, root_user, root_pwd) -> int:
    res = _mc(ctx, ["quota", "info", "--json", f"{ALIAS}/{bucket}"],
              root_user=root_user, root_pwd=root_pwd, check=False)
    try:
        return int(json.loads(res.stdout).get("quota", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return 0


def _ensure_quota(ctx, bucket, gb, root_user, root_pwd, step) -> None:
    """Set a hard per-bucket quota. ``gb == 0`` => unmanaged (no quota enforced)."""
    if gb <= 0:
        return
    desired = gb * 1024 ** 3
    if _current_quota_bytes(ctx, bucket, root_user, root_pwd) == desired:
        step.actions.append(f"quota {gb}GiB on '{bucket}' already set")
        return
    _mc(ctx, ["quota", "set", f"{ALIAS}/{bucket}", "--size", f"{gb}gi"],
        root_user=root_user, root_pwd=root_pwd)
    step.actions.append(f"quota set to {gb}GiB on '{bucket}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    m = cfg.storage.minio
    bucket = m.default_bucket
    root_user = m.root_user
    root_pwd = env_value(ctx.secrets_file, m.root_password_secret, None)
    if not root_pwd:
        logger.warning(
            "MINIO_ROOT_PASSWORD (%s) not found in the secrets file — falling back to "
            "the weak built-in default. Run via docker_local --apply (ensure_secrets) "
            "so a strong secret is generated.", m.root_password_secret)
        root_pwd = DEFAULT_ROOT_PASSWORD
    sa_access = f"{cfg.meta.project_name}-backend"
    target = f"{ALIAS}/{bucket}"
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [
            f"mc mb --ignore-existing {target}",
            f"mc version enable {target}  (long-term retention / PAdES)",
            f"mc anonymous set none {target}  (private)",
        ]
        if m.compliance.enabled:
            step.actions.append(
                f"mc mb --with-lock {ALIAS}/{m.compliance.bucket}  "
                f"+ retention {m.compliance.retention_mode.upper()} "
                f"{m.compliance.retention_days}d (WORM)")
        if m.lifecycle.expire_noncurrent_versions_days > 0:
            step.actions.append(
                f"lifecycle: non-current expire "
                f"{m.lifecycle.expire_noncurrent_versions_days}d on '{bucket}'")
        for b, gb in (("documents", m.quota_documents_gb),
                      ("compliance", m.quota_compliance_gb)):
            if gb > 0:
                step.actions.append(f"quota {gb}GiB on {b} bucket")
        step.actions.append(f"scoped service account '{sa_access}' (rw on '{bucket}' only)")
        return step.skip("dry-run: would provision MinIO")

    try:
        _mc(ctx, ["mb", "--ignore-existing", target],
            root_user=root_user, root_pwd=root_pwd)
        step.actions.append(f"bucket '{bucket}' ensured")

        _mc(ctx, ["version", "enable", target],
            root_user=root_user, root_pwd=root_pwd)
        step.actions.append("versioning enabled (long-term retention)")

        _mc(ctx, ["anonymous", "set", "none", target],
            root_user=root_user, root_pwd=root_pwd)
        step.actions.append("anonymous access = none (private)")

        compliance_bucket = _ensure_compliance_bucket(
            ctx, m, root_user, root_pwd, step)

        _ensure_lifecycle(ctx, bucket, m.lifecycle.expire_noncurrent_versions_days,
                          root_user, root_pwd, step)
        _ensure_quota(ctx, bucket, m.quota_documents_gb, root_user, root_pwd, step)
        if compliance_bucket:
            _ensure_quota(ctx, compliance_bucket, m.quota_compliance_gb,
                          root_user, root_pwd, step)

        sa_secret = _ensure_service_account(
            ctx, sa_access, bucket, compliance_bucket, root_user, root_pwd, step)
    except DockerError as exc:
        return step.fail(f"mc operation failed: {exc}")

    step.secrets = {
        "minio_endpoint": "http://minio:9000",
        "minio_bucket": bucket,
        "minio_access_key": sa_access,
        "minio_secret_key": sa_secret,
    }
    if compliance_bucket:
        step.secrets["minio_compliance_bucket"] = compliance_bucket
    return step.ok(
        f"bucket '{bucket}' (versioned, private)"
        + (f" + WORM '{compliance_bucket}'" if compliance_bucket else "")
        + f" + scoped service account '{sa_access}'")
