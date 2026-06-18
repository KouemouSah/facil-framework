#!/usr/bin/env python3
"""Shared execution context passed to every provisioner.

Keeping the context in its own module avoids an import cycle: provisioners
import :class:`BootstrapContext` from here, and the orchestrator
(``bootstrap/__init__.py``) imports the provisioners.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# validate_config lives in deploy/scripts; make it importable.
_PROVIDERS_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _PROVIDERS_DIR.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

from .docker_helpers import ContainerInfo  # noqa: E402


@dataclass
class BootstrapContext:
    """Everything a provisioner needs, resolved once by the orchestrator.

    Attributes
    ----------
    cfg:
        The validated deploy config (single source of truth for ports, names,
        providers, deployment mode).
    network:
        Docker network the running stack uses — one-shot tool containers attach
        to it so ``minio:9000`` / ``openbao:8200`` resolve by service DNS.
    containers:
        Resolved {service: ContainerInfo} for the services this run touches,
        already confirmed healthy by the orchestrator's wait gate.
    repo_root:
        Used to locate ``.env.secrets`` (secret source) and write
        ``.bootstrap-state.json``.
    dry_run:
        When True, provisioners record the actions they WOULD take in
        ``ProvisionStep.actions`` but mutate nothing.
    log:
        Injected sink (defaults to print) so the CLI and tests can capture
        output.
    """

    cfg: vc.DeployConfig
    network: str
    containers: dict[str, ContainerInfo] = field(default_factory=dict)
    repo_root: Path = field(default_factory=lambda: _PROVIDERS_DIR.parent.parent)
    dry_run: bool = False
    log: Callable[[str], None] = print
    # Secrets minted by sibling provisioners earlier in THIS run (name -> secrets),
    # seeded from the prior state file so a single-provisioner re-run still sees
    # them. Lets OpenBao (run last) mirror the postgres/minio creds into the vault.
    completed: dict[str, dict] = field(default_factory=dict)

    @property
    def secrets_file(self) -> Path:
        return self.repo_root / ".env.secrets"

    @property
    def state_file(self) -> Path:
        return self.repo_root / "deploy" / ".bootstrap-state.json"
