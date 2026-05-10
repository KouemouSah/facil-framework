"""Tests for deploy/scripts/extract_seeds.py.

Pure unit tests for the SQL literal formatter and the SQL renderer. The
async asyncpg paths are not exercised here — they live in the integration
suite that runs against a live DATABASE_URL.

Run from repo root:
    pytest deploy/scripts/test_extract_seeds.py -v --no-cov
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import extract_seeds as es  # noqa: E402


# ---------------------------------------------------------------------------
# to_sql_literal
# ---------------------------------------------------------------------------

class TestToSqlLiteral:
    @pytest.mark.parametrize("value,expected", [
        (None, "NULL"),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        (-7, "-7"),
        (3.14, "3.14"),
        (0, "0"),
    ])
    def test_primitives(self, value: object, expected: str) -> None:
        assert es.to_sql_literal(value) == expected

    def test_decimal(self) -> None:
        assert es.to_sql_literal(Decimal("1234.56")) == "1234.56"

    def test_string_simple(self) -> None:
        assert es.to_sql_literal("hello") == "'hello'"

    def test_string_with_single_quote_doubled(self) -> None:
        # 'It's' must become 'It''s'
        assert es.to_sql_literal("It's") == "'It''s'"

    def test_string_unicode(self) -> None:
        # Spanish accents must survive verbatim.
        assert es.to_sql_literal("España") == "'España'"

    def test_uuid(self) -> None:
        u = UUID("12345678-1234-5678-1234-567812345678")
        assert es.to_sql_literal(u) == "'12345678-1234-5678-1234-567812345678'::uuid"

    def test_datetime_with_tz(self) -> None:
        dt = datetime(2026, 5, 9, 12, 30, 0, tzinfo=timezone.utc)
        result = es.to_sql_literal(dt)
        assert result.startswith("'2026-05-09T12:30:00")
        assert result.endswith("::timestamptz")

    def test_date(self) -> None:
        assert es.to_sql_literal(date(2026, 5, 9)) == "'2026-05-09'::date"

    def test_time(self) -> None:
        assert es.to_sql_literal(time(14, 30, 0)) == "'14:30:00'::time"

    def test_dict_jsonb(self) -> None:
        out = es.to_sql_literal({"key": "value", "num": 1})
        assert out.endswith("::jsonb")
        assert '"key": "value"' in out
        assert '"num": 1' in out

    def test_list_jsonb(self) -> None:
        out = es.to_sql_literal([1, 2, 3])
        assert out == "'[1, 2, 3]'::jsonb"

    def test_dict_with_quote_in_value(self) -> None:
        out = es.to_sql_literal({"name": "It's me"})
        # JSON escapes the inner quote, then PG escape doubles it.
        assert "::jsonb" in out
        assert "It''s me" in out

    def test_bytes_hex(self) -> None:
        out = es.to_sql_literal(b"\x01\x02")
        assert out == "'\\x0102'::bytea"

    def test_set_renders_as_sorted_array_literal(self) -> None:
        out = es.to_sql_literal({"b", "a", "c"})
        # Sorted alphabetically for determinism.
        assert out == "'{\"a\",\"b\",\"c\"}'"


# ---------------------------------------------------------------------------
# render_seed_sql
# ---------------------------------------------------------------------------

class FakeRecord(dict):
    """Mimics asyncpg.Record (dict-style access)."""


class TestRenderSeedSql:
    def test_with_pk_emits_on_conflict_do_update(self) -> None:
        info = es.TableInfo(
            name="roles",
            columns=["id", "name", "code"],
            pk_columns=["id"],
        )
        rows = [
            FakeRecord(id="r1", name="Citizen", code="citizen"),
        ]
        sql = es.render_seed_sql(info, rows)
        assert 'INSERT INTO public."roles"' in sql
        assert 'ON CONFLICT ("id") DO UPDATE SET' in sql
        assert '"name" = EXCLUDED."name"' in sql
        assert '"code" = EXCLUDED."code"' in sql
        # PK column itself must NOT appear in the SET clause.
        assert '"id" = EXCLUDED."id"' not in sql
        # File starts with header + BEGIN, ends with COMMIT.
        assert "BEGIN;" in sql
        assert sql.rstrip().endswith("COMMIT;")

    def test_pk_only_table_uses_do_nothing(self) -> None:
        info = es.TableInfo(
            name="role_links",
            columns=["role_a", "role_b"],
            pk_columns=["role_a", "role_b"],
        )
        rows = [FakeRecord(role_a="x", role_b="y")]
        sql = es.render_seed_sql(info, rows)
        assert 'ON CONFLICT ("role_a", "role_b") DO NOTHING' in sql

    def test_no_pk_uses_do_nothing(self) -> None:
        info = es.TableInfo(
            name="audit_logs",
            columns=["actor", "action"],
            pk_columns=[],
        )
        rows = [FakeRecord(actor="alice", action="login")]
        sql = es.render_seed_sql(info, rows)
        assert "ON CONFLICT DO NOTHING" in sql
        assert "DO UPDATE" not in sql

    def test_empty_rows(self) -> None:
        info = es.TableInfo(name="cities", columns=["id", "name"], pk_columns=["id"])
        sql = es.render_seed_sql(info, [])
        assert "(empty — no rows to insert)" in sql
        assert "Rows:  0" in sql

    def test_no_columns_skips(self) -> None:
        info = es.TableInfo(name="ghost", columns=[], pk_columns=[])
        sql = es.render_seed_sql(info, [])
        assert "no columns introspected, skipping" in sql

    def test_quotes_in_value_escape(self) -> None:
        info = es.TableInfo(name="t", columns=["x"], pk_columns=["x"])
        rows = [FakeRecord(x="O'Brien")]
        sql = es.render_seed_sql(info, rows)
        assert "'O''Brien'" in sql

    def test_uuid_value_cast(self) -> None:
        u = UUID("12345678-1234-5678-1234-567812345678")
        info = es.TableInfo(name="t", columns=["id"], pk_columns=["id"])
        rows = [FakeRecord(id=u)]
        sql = es.render_seed_sql(info, rows)
        assert "::uuid" in sql

    def test_jsonb_value(self) -> None:
        info = es.TableInfo(name="t", columns=["id", "config"], pk_columns=["id"])
        rows = [FakeRecord(id=1, config={"k": "v"})]
        sql = es.render_seed_sql(info, rows)
        assert "::jsonb" in sql


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestParseTablesArg:
    def test_explicit_list(self) -> None:
        assert es.parse_tables_arg("a,b,c", tier=0) == ["a", "b", "c"]

    def test_strips_whitespace(self) -> None:
        assert es.parse_tables_arg("a, b , c", tier=0) == ["a", "b", "c"]

    def test_filters_empty_segments(self) -> None:
        assert es.parse_tables_arg("a,,b,", tier=0) == ["a", "b"]

    def test_tier_0_default(self) -> None:
        result = es.parse_tables_arg(None, tier=0)
        # User-defined TIER_0: roles + permissions + role_permissions +
        # communication templates (6 tables).
        assert "roles" in result
        assert "permissions" in result
        assert "role_permissions" in result
        assert "email_templates" in result
        assert "sms_templates" in result
        assert "push_templates" in result
        assert "notification_templates" in result
        assert "ussd_configurations" in result
        assert "communication_provider_settings" in result
        assert len(result) == len(es.TIER_0_TABLES)

    def test_tier_1_includes_tier_0(self) -> None:
        result = es.parse_tables_arg(None, tier=1)
        for table in es.TIER_0_TABLES:
            assert table in result
        # And much more.
        assert "fiscal_services" in result
        assert "translations" in result
        assert "categories" in result
        assert "ministries" in result
        assert len(result) > len(es.TIER_0_TABLES)
