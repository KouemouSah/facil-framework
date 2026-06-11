"""Layered config resolver: defaults -> config.yaml -> DB -> env.

Precedence (highest wins, checked first): env > DB > file > default.
- INFRA config is usually set via env at deploy -> env wins (NOT runtime-editable).
- APP config has no env -> the DB layer wins (admin-editable at runtime).

The DB layer is cached in-process; `reload()` refreshes it (D1 invalidation;
EventBus/NOTIFY fan-out lands later).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def _env_key(key: str) -> str:
    return key.upper().replace(".", "_").replace("-", "_")


class ConfigResolver:
    def __init__(self, *, defaults: Mapping[str, Any] | None = None,
                 file_cfg: Mapping[str, Any] | None = None,
                 env: Mapping[str, str] | None = None) -> None:
        self._defaults = dict(defaults or {})
        self._file = dict(file_cfg or {})
        self._env = env if env is not None else os.environ
        self._db: dict[str, Any] = {}

    def set_db(self, db_map: Mapping[str, Any]) -> None:
        """Replace the cached DB layer (called on load / invalidation)."""
        self._db = dict(db_map)

    def resolve(self, key: str, default: Any = None) -> Any:
        envk = _env_key(key)
        if envk in self._env:
            return self._env[envk]
        if key in self._db:
            return self._db[key]
        if key in self._file:
            return self._file[key]
        if key in self._defaults:
            return self._defaults[key]
        return default

    def source(self, key: str) -> str:
        """Which layer would answer (for the doctor / debug)."""
        if _env_key(key) in self._env:
            return "env"
        if key in self._db:
            return "db"
        if key in self._file:
            return "file"
        if key in self._defaults:
            return "default"
        return "missing"
