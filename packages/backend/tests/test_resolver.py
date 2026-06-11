"""ConfigResolver precedence: env > DB > file > default."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config_store.resolver import ConfigResolver  # noqa: E402


def _r(env=None):
    r = ConfigResolver(
        defaults={"a": "default-a", "shared": "from-default"},
        file_cfg={"b": "file-b", "shared": "from-file"},
        env=env or {},
    )
    r.set_db({"c": "db-c", "shared": "from-db"})
    return r


def test_default_layer():
    assert _r().resolve("a") == "default-a"


def test_file_over_default():
    assert _r().resolve("b") == "file-b"


def test_db_over_file_and_default():
    # 'shared' exists in default+file+db -> db wins (admin-editable at runtime).
    assert _r().resolve("shared") == "from-db"


def test_env_wins_over_all():
    # env key = upper, dots/dashes -> underscores.
    r = _r(env={"SHARED": "from-env"})
    assert r.resolve("shared") == "from-env"
    assert r.source("shared") == "env"


def test_missing_returns_explicit_default():
    assert _r().resolve("nope", default="fallback") == "fallback"
    assert _r().source("nope") == "missing"


def test_dotted_key_env_mapping():
    r = ConfigResolver(env={"EMAIL_PROVIDER": "sendgrid"})
    assert r.resolve("email.provider") == "sendgrid"


def test_source_reports_layer():
    r = _r()
    assert r.source("a") == "default"
    assert r.source("b") == "file"
    assert r.source("c") == "db"
