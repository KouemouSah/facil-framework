#!/usr/bin/env python3
"""Bootstrap state — the bridge between provisioning and the app tier.

Each provisioner returns a :class:`ProvisionStep`. The orchestrator collects
them into a :class:`BootstrapState` and persists it to
``deploy/.bootstrap-state.json`` (gitignored). That file records WHAT was
provisioned and any credentials generated along the way (MinIO service-account
keys, OpenBao AppRole role_id/secret_id). When the application tier lands
(Phase D), ``render_env.py`` consumes this file to wire the backend, so nothing
generated here is ever lost.

The state is deliberately a plain dataclass tree serialised to JSON — no DB, no
external dependency — so it is trivially diffable and inspectable by an operator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

StepStatus = Literal["ok", "skipped", "pending", "failed"]


@dataclass
class ProvisionStep:
    """Outcome of a single provisioner run.

    Attributes
    ----------
    name:
        Provisioner identifier (``"minio"``, ``"openbao"``, ``"postgres"``).
    status:
        ``ok`` (provisioned / already correct), ``skipped`` (not applicable for
        the active deployment mode), ``pending`` (stub not yet implemented),
        ``failed`` (an error occurred — ``detail`` carries the reason).
    detail:
        Human-readable summary of what happened (idempotent runs say so).
    actions:
        Ordered list of concrete idempotent actions taken (or that would be
        taken, in dry-run). Lets an operator audit exactly what changed.
    secrets:
        Credentials produced by this step, keyed by a stable name
        (e.g. ``minio_access_key``). Consumed later by render_env. NEVER logged
        verbatim — :meth:`BootstrapState.redacted_summary` masks them.
    """

    name: str
    status: StepStatus = "pending"
    detail: str = ""
    actions: list[str] = field(default_factory=list)
    secrets: dict[str, str] = field(default_factory=dict)

    def ok(self, detail: str) -> "ProvisionStep":
        self.status = "ok"
        self.detail = detail
        return self

    def skip(self, detail: str) -> "ProvisionStep":
        self.status = "skipped"
        self.detail = detail
        return self

    def fail(self, detail: str) -> "ProvisionStep":
        self.status = "failed"
        self.detail = detail
        return self


@dataclass
class BootstrapState:
    """Aggregate of all provisioner steps for one bootstrap run."""

    project: str
    storage_provider: str
    secrets_provider: str
    database_mode: str
    steps: list[ProvisionStep] = field(default_factory=list)

    # ----- aggregate helpers -------------------------------------------------

    @property
    def succeeded(self) -> bool:
        """True if no step failed (skipped/pending do not count as failures)."""
        return all(s.status != "failed" for s in self.steps)

    def step(self, name: str) -> ProvisionStep | None:
        for s in self.steps:
            if s.name == name:
                return s
        return None

    def all_secrets(self) -> dict[str, str]:
        """Flattened {name: value} of every credential produced this run."""
        out: dict[str, str] = {}
        for s in self.steps:
            out.update(s.secrets)
        return out

    # ----- persistence -------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        """Write the state file with 0600-ish intent (best effort on Windows).

        Secrets are stored in clear in this gitignored file — same trust level
        as ``.env.secrets``. The caller is responsible for keeping the repo
        root out of any shared/synced location.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:  # POSIX-only; harmless no-op on Windows.
            path.chmod(0o600)
        except (OSError, NotImplementedError):
            pass

    @classmethod
    def load(cls, path: Path) -> "BootstrapState | None":
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        steps = [ProvisionStep(**s) for s in raw.pop("steps", [])]
        return cls(steps=steps, **raw)

    # ----- reporting ---------------------------------------------------------

    def redacted_summary(self) -> str:
        """Operator-facing summary with secret VALUES masked (keys shown)."""
        lines = [
            f"project={self.project} storage={self.storage_provider} "
            f"secrets={self.secrets_provider} db_mode={self.database_mode}",
        ]
        for s in self.steps:
            marker = {"ok": "[OK]", "skipped": "[--]",
                      "pending": "[..]", "failed": "[!!]"}[s.status]
            lines.append(f"  {marker} {s.name}: {s.detail}")
            for action in s.actions:
                lines.append(f"        - {action}")
            if s.secrets:
                masked = ", ".join(f"{k}=***" for k in s.secrets)
                lines.append(f"        secrets: {masked}")
        return "\n".join(lines)
