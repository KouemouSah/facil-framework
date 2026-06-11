#!/usr/bin/env python3
"""MinIO provisioner — bucket + versioning + private policy + scoped service account.

Driven entirely through a one-shot ``minio/mc`` container on the stack network
(decision D6): ``mc`` is the canonical MinIO admin tool and, unlike the S3 API,
can create a *scoped* service account (decision D3 — the backend never receives
root credentials). Applies for ``storage.provider == "minio"``.

The cloud S3 path (``provider == "s3"``) is intentionally NOT handled here yet —
it needs boto3 + IAM and lands when cloud provisioning is actually built.
"""

from __future__ import annotations

from .context import BootstrapContext, vc
from .state import ProvisionStep

NAME = "minio"


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.storage.provider == "minio"


def provision(ctx: BootstrapContext) -> ProvisionStep:  # pragma: no cover - B2
    """Implemented in Phase B2. B1 ships the stub so dispatch is wired."""
    return ProvisionStep(name=NAME, detail="minio provisioner pending (B2)")
