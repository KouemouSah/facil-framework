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
import secrets as _secrets

from .context import BootstrapContext, vc
from .docker_helpers import DockerError, run_oneshot
from .env_secrets import env_value
from .state import BootstrapState, ProvisionStep

NAME = "minio"
MC_IMAGE = "minio/mc:latest"
ALIAS = "facil"               # mc alias name (via MC_HOST_<alias> env)
DEFAULT_ROOT_PASSWORD = "facilminio"   # matches compose ${MINIO_ROOT_PASSWORD:-facilminio}


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.storage.provider == "minio"


# ---------------------------------------------------------------------------
# Least-privilege policy (decision D3)
# ---------------------------------------------------------------------------

def scoped_policy(bucket: str) -> dict:
    """S3 policy granting object rw + bucket listing on ONE bucket, nothing else."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                    "s3:ListMultipartUploadParts", "s3:AbortMultipartUpload",
                ],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                "Resource": [f"arn:aws:s3:::{bucket}"],
            },
        ],
    }


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


def _ensure_service_account(ctx, sa_access, bucket, root_user, root_pwd,
                            step: ProvisionStep) -> str:
    """Create / reuse / rotate the scoped service account. Returns its secret."""
    info = _mc(ctx, ["admin", "user", "svcacct", "info", ALIAS, sa_access],
               root_user=root_user, root_pwd=root_pwd, check=False)
    exists = info.returncode == 0

    prior_secret = ""
    prior = BootstrapState.load(ctx.state_file)
    if prior and (ps := prior.step(NAME)):
        prior_secret = ps.secrets.get("minio_secret_key", "")

    if exists and prior_secret:
        step.actions.append(f"service account '{sa_access}' present — secret reused")
        return prior_secret
    if exists and not prior_secret:
        _mc(ctx, ["admin", "user", "svcacct", "rm", ALIAS, sa_access],
            root_user=root_user, root_pwd=root_pwd, check=False)
        step.actions.append(
            f"service account '{sa_access}' existed without a known secret — rotated")

    new_secret = _secrets.token_hex(20)
    policy = json.dumps(scoped_policy(bucket))
    # Write the inline policy inside the container then attach it to the svcacct.
    script = (
        "set -e\n"
        f"cat > /tmp/sa-policy.json <<'JSON'\n{policy}\nJSON\n"
        f"mc admin user svcacct add --access-key '{sa_access}' "
        f"--secret-key '{new_secret}' --policy /tmp/sa-policy.json "
        f"{ALIAS} {root_user}\n"
    )
    _mc(ctx, ["-c", script], root_user=root_user, root_pwd=root_pwd, entrypoint="sh")
    step.actions.append(f"service account '{sa_access}' created (scoped rw on '{bucket}')")
    return new_secret


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def provision(ctx: BootstrapContext) -> ProvisionStep:
    cfg = ctx.cfg
    m = cfg.storage.minio
    bucket = m.default_bucket
    root_user = m.root_user
    root_pwd = env_value(ctx.secrets_file, m.root_password_secret, DEFAULT_ROOT_PASSWORD)
    sa_access = f"{cfg.meta.project_name}-backend"
    target = f"{ALIAS}/{bucket}"
    step = ProvisionStep(name=NAME)

    if ctx.dry_run:
        step.actions = [
            f"mc mb --ignore-existing {target}",
            f"mc version enable {target}  (long-term retention / PAdES)",
            f"mc anonymous set none {target}  (private)",
            f"scoped service account '{sa_access}' (rw on '{bucket}' only)",
        ]
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

        sa_secret = _ensure_service_account(
            ctx, sa_access, bucket, root_user, root_pwd, step)
    except DockerError as exc:
        return step.fail(f"mc operation failed: {exc}")

    step.secrets = {
        "minio_endpoint": "http://minio:9000",
        "minio_bucket": bucket,
        "minio_access_key": sa_access,
        "minio_secret_key": sa_secret,
    }
    return step.ok(
        f"bucket '{bucket}' (versioned, private) + scoped service account '{sa_access}'")
