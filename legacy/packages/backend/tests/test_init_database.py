"""Unit tests for scripts/deploy/init_database.py — Phase A of the
MIGRATIONS_BASELINE_REFACTOR_PLAN.

These are *pure-function* tests that do NOT require a live Postgres
connection. The integration tests (advisory lock, schema_migrations table,
end-to-end apply) live separately in tests/integration/ and run against a
real DB in CI when DATABASE_URL is configured.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so we can import the module (it's not a package).
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.deploy import init_database as init_db  # noqa: E402


# ---------------------------------------------------------------------------
# MigrationFile.from_path
# ---------------------------------------------------------------------------

class TestMigrationFile:
    def test_from_path_computes_correct_checksum(self, tmp_path: Path) -> None:
        f = tmp_path / "001_test.sql"
        content = b"SELECT 1;"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()

        mig = init_db.MigrationFile.from_path(f)

        assert mig.checksum == expected
        assert mig.version == "001_test"
        assert mig.filename == "001_test.sql"
        assert mig.filetype == "migration"

    def test_from_path_filetype_override(self, tmp_path: Path) -> None:
        f = tmp_path / "001_seed.sql"
        f.write_text("INSERT INTO foo VALUES (1);")
        mig = init_db.MigrationFile.from_path(f, filetype="seed")
        assert mig.filetype == "seed"

    def test_checksum_changes_on_edit(self, tmp_path: Path) -> None:
        f = tmp_path / "001_test.sql"
        f.write_text("SELECT 1;")
        c1 = init_db.MigrationFile.from_path(f).checksum
        f.write_text("SELECT 2;")
        c2 = init_db.MigrationFile.from_path(f).checksum
        assert c1 != c2


# ---------------------------------------------------------------------------
# discover_files
# ---------------------------------------------------------------------------

class TestDiscoverFiles:
    def test_returns_sorted_by_filename(self, tmp_path: Path) -> None:
        (tmp_path / "002_b.sql").write_text("SELECT 2;")
        (tmp_path / "001_a.sql").write_text("SELECT 1;")
        (tmp_path / "010_c.sql").write_text("SELECT 10;")

        files = init_db.discover_files(tmp_path, filetype="migration")

        assert [f.filename for f in files] == [
            "001_a.sql", "002_b.sql", "010_c.sql"
        ]

    def test_empty_directory(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert init_db.discover_files(empty, filetype="migration") == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        ghost = tmp_path / "nonexistent"
        assert init_db.discover_files(ghost, filetype="migration") == []

    def test_only_sql_files(self, tmp_path: Path) -> None:
        (tmp_path / "001.sql").write_text("SELECT 1;")
        (tmp_path / "README.md").write_text("# notes")
        (tmp_path / "002.txt").write_text("not a migration")

        files = init_db.discover_files(tmp_path, filetype="migration")

        assert [f.filename for f in files] == ["001.sql"]


# ---------------------------------------------------------------------------
# split_statements
# ---------------------------------------------------------------------------

class TestSplitStatements:
    def test_splits_on_semicolons(self) -> None:
        sql = "SELECT 1; SELECT 2; SELECT 3"
        assert init_db.split_statements(sql) == [
            "SELECT 1", "SELECT 2", "SELECT 3"
        ]

    def test_strips_empty_statements(self) -> None:
        sql = "SELECT 1;;SELECT 2;"
        assert init_db.split_statements(sql) == ["SELECT 1", "SELECT 2"]

    def test_skips_comment_only_statements(self) -> None:
        sql = "-- A header comment;\nSELECT 1;-- trailing comment"
        result = init_db.split_statements(sql)
        # Only the SELECT survives; both '--' lines are filtered.
        assert "SELECT 1" in result
        assert all(not s.startswith("--") for s in result)


# ---------------------------------------------------------------------------
# is_already_exists_error
# ---------------------------------------------------------------------------

class TestIsAlreadyExistsError:
    @pytest.mark.parametrize("msg", [
        "relation \"users\" already exists",
        "duplicate key value violates unique constraint",
        "constraint already exists",
        "DUPLICATE OBJECT",
    ])
    def test_matches_idempotent_errors(self, msg: str) -> None:
        assert init_db.is_already_exists_error(Exception(msg))

    @pytest.mark.parametrize("msg", [
        "syntax error at or near \"SELCT\"",
        "permission denied for table users",
        "could not connect to server",
        "deadlock detected",
    ])
    def test_does_not_match_real_errors(self, msg: str) -> None:
        assert not init_db.is_already_exists_error(Exception(msg))


# ---------------------------------------------------------------------------
# Constants safety
# ---------------------------------------------------------------------------

class TestConstants:
    def test_advisory_lock_id_is_signed_bigint(self) -> None:
        """Postgres pg_advisory_lock takes a signed bigint."""
        max_signed_bigint = 2**63 - 1
        assert 0 <= init_db.ADVISORY_LOCK_ID <= max_signed_bigint

    def test_advisory_lock_id_is_stable(self) -> None:
        """Must NOT depend on Python's randomized hash()."""
        # Re-importing should yield the same constant (no module-level hash()).
        from importlib import reload
        reload(init_db)
        # If this assertion fails, someone introduced randomness.
        assert init_db.ADVISORY_LOCK_ID == 0x7461_7861_7367_6569

    def test_lock_timeout_is_reasonable(self) -> None:
        # 60s is the chosen value; if changed, update the docstring too.
        assert 10 <= init_db.ADVISORY_LOCK_TIMEOUT_SEC <= 300

    def test_repo_paths_resolve_under_backend(self) -> None:
        """REPO_ROOT must point at packages/backend/, not deeper or higher."""
        assert init_db.REPO_ROOT.name == "backend"
        assert init_db.REPO_ROOT.parent.name == "packages"
        assert init_db.MIGRATIONS_DIR == init_db.REPO_ROOT / "database" / "migrations"

    def test_baseline_dir_path(self) -> None:
        """BASELINE_DIR points at database/baseline/ — used for fresh-DB fast path."""
        assert init_db.BASELINE_DIR == init_db.REPO_ROOT / "database" / "baseline"

    def test_seeds_dir_path(self) -> None:
        assert init_db.SEEDS_DIR == init_db.REPO_ROOT / "database" / "seeds"


# ---------------------------------------------------------------------------
# is_database_empty — query shape (no live DB)
# ---------------------------------------------------------------------------

class TestIsDatabaseEmptySignature:
    """Cannot exercise is_database_empty without a live DB; assert the
    function exists, is async, and is reachable through the module surface
    so the baseline-first branch in main() can call it."""

    def test_function_exists(self) -> None:
        assert hasattr(init_db, "is_database_empty")

    def test_function_is_async(self) -> None:
        import asyncio
        coro = init_db.is_database_empty
        # Calling on a sentinel should produce a coroutine.
        # We can't await it (no conn), but we can detect the wrapping.
        assert asyncio.iscoroutinefunction(coro)
