#!/usr/bin/env python3
"""OpenBao provisioner — kv-v2 mount + boot secrets + policy + AppRole.

Uses the OpenBao HTTP API via ``requests`` (decision D6 — already available, no
heavy SDK). Applies for ``secrets.provider == "openbao"``. Scope (decision D5):
secrets consumption only — kv-v2 at ``facil/``, the boot secrets written under
``facil/boot`` (decision D4, with ``.env.secrets`` kept as fallback), a
read-only ``facil-backend`` policy, and an AppRole the backend authenticates
with. PKI / mTLS is explicitly out of scope (P7/P8).

In dev mode OpenBao is in-memory, so this provisioning is re-run on every
``up`` — which is exactly why it must be idempotent.
"""

from __future__ import annotations

from .context import BootstrapContext, vc
from .state import ProvisionStep

NAME = "openbao"


def is_applicable(cfg: vc.DeployConfig) -> bool:
    return cfg.secrets.provider == "openbao"


def provision(ctx: BootstrapContext) -> ProvisionStep:  # pragma: no cover - B3
    """Implemented in Phase B3. B1 ships the stub so dispatch is wired."""
    return ProvisionStep(name=NAME, detail="openbao provisioner pending (B3)")
