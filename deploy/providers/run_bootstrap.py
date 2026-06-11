#!/usr/bin/env python3
"""Standalone launcher for the data-plane bootstrap.

Flat-script convention (mirrors ``docker_local.py``) so it runs directly with
the repo venv, while the implementation lives in the ``bootstrap`` package:

    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --plan
    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply
    python deploy/providers/run_bootstrap.py --config=deploy/config.yaml --apply --only=minio

This exists because the package uses relative imports (``from . import minio``),
which require package context — a flat launcher provides it without forcing
``deploy`` to become an importable package.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROVIDERS_DIR))
sys.path.insert(0, str(PROVIDERS_DIR.parent / "scripts"))

import bootstrap  # noqa: E402

if __name__ == "__main__":
    sys.exit(bootstrap.main())
