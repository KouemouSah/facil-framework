#!/usr/bin/env python3
"""Minimal dotenv reader for the bootstrap provisioners.

The MinIO provisioner needs the root password the stack was started with, and
the OpenBao provisioner needs the boot secrets to seed kv — both live in
``.env.secrets`` (the same file ``docker compose`` loads via ``env_file``).

This is intentionally a tiny, dependency-free parser (not python-dotenv): it
handles ``KEY=VALUE``, ``#`` comments, blank lines, surrounding quotes and a
leading ``export``. It does NOT do variable interpolation — the bootstrap reads
literal values, matching how Compose treats ``env_file`` entries.
"""

from __future__ import annotations

from pathlib import Path


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file into a plain {KEY: VALUE} dict.

    Returns an empty dict if the file is absent (graceful: callers fall back to
    documented defaults, mirroring Compose's ``${VAR:-default}``).
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def env_value(path: Path, key: str, default: str) -> str:
    """Single-key convenience: value from the dotenv file, else ``default``.

    An empty value in the file counts as "unset" -> default, matching the
    "empty integration secret = graceful degradation" convention.
    """
    val = load_env_file(path).get(key, "")
    return val or default
