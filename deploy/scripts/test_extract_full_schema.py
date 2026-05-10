"""Tests for deploy/scripts/extract_full_schema.py.

Pure unit tests for the SQL rendering logic. Async asyncpg paths are
exercised against a live DATABASE_URL only by the integration suite.

Run from repo root:
    pytest deploy/scripts/test_extract_full_schema.py -v --no-cov
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import extract_full_schema as efs  # noqa: E402


# ---------------------------------------------------------------------------
# render_sql
# ---------------------------------------------------------------------------

class TestRenderSqlEmpty:
    def test_empty_extraction_emits_header_only(self) -> None:
        out = efs.render_sql(efs.SchemaExtraction())
        assert "Facil baseline schema" in out
        assert "DO NOT EDIT MANUALLY" in out
        assert "Re-run the extractor" in out


class TestRenderSqlExtensions:
    def test_extensions_use_create_extension_if_not_exists(self) -> None:
        ex = efs.SchemaExtraction(extensions=[
            ("uuid-ossp", "public"),
            ("pgvector", "public"),
        ])
        out = efs.render_sql(ex)
        assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' in out
        assert 'CREATE EXTENSION IF NOT EXISTS "pgvector";' in out


class TestRenderSqlEnums:
    def test_enum_wrapped_in_do_block_for_idempotency(self) -> None:
        ex = efs.SchemaExtraction(enums=[
            ("user_role_enum", ["citizen", "business", "admin"]),
        ])
        out = efs.render_sql(ex)
        assert "DO $$ BEGIN" in out
        assert (
            'CREATE TYPE "public"."user_role_enum" AS ENUM '
            "('citizen', 'business', 'admin');"
        ) in out
        assert "EXCEPTION WHEN duplicate_object" in out


class TestRenderSqlTables:
    def test_table_create_sql_passthrough(self) -> None:
        ex = efs.SchemaExtraction(tables=[
            ("users", 'CREATE TABLE IF NOT EXISTS "public"."users" (\n    "id" uuid NOT NULL\n);'),
        ])
        out = efs.render_sql(ex)
        assert 'CREATE TABLE IF NOT EXISTS "public"."users"' in out


class TestRenderSqlConstraints:
    def test_constraints_in_correct_order(self) -> None:
        ex = efs.SchemaExtraction(
            primary_keys=[("users", "users_pkey", 'ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");')],
            unique_constraints=[("users", "users_email_key", 'ALTER TABLE "public"."users" ADD CONSTRAINT "users_email_key" UNIQUE ("email");')],
            check_constraints=[("users", "ck_age_positive", 'ALTER TABLE "public"."users" ADD CONSTRAINT "ck_age_positive" CHECK (age > 0);')],
            foreign_keys=[("orders", "fk_orders_user", 'ALTER TABLE "public"."orders" ADD CONSTRAINT "fk_orders_user" FOREIGN KEY ("user_id") REFERENCES users(id);')],
        )
        out = efs.render_sql(ex)
        # All four kinds present
        assert "users_pkey" in out
        assert "users_email_key" in out
        assert "ck_age_positive" in out
        assert "fk_orders_user" in out
        # PK before UNIQUE before CHECK before FK (textual order in output).
        pk_pos = out.index("users_pkey")
        unique_pos = out.index("users_email_key")
        check_pos = out.index("ck_age_positive")
        fk_pos = out.index("fk_orders_user")
        assert pk_pos < unique_pos < check_pos < fk_pos


class TestRenderSqlIndexes:
    def test_index_definition_passthrough(self) -> None:
        ex = efs.SchemaExtraction(indexes=[
            ("idx_users_email",
             "CREATE INDEX idx_users_email ON public.users USING btree (email);"),
        ])
        out = efs.render_sql(ex)
        assert "idx_users_email" in out


class TestRenderSqlFunctionsTriggersViews:
    def test_function_block_present(self) -> None:
        body = (
            "CREATE OR REPLACE FUNCTION public.touch_updated_at()\n"
            "RETURNS trigger LANGUAGE plpgsql AS $$\n"
            "BEGIN NEW.updated_at = now(); RETURN NEW; END;$$;"
        )
        ex = efs.SchemaExtraction(functions=[("touch_updated_at", body)])
        out = efs.render_sql(ex)
        assert "touch_updated_at" in out
        assert "LANGUAGE plpgsql" in out

    def test_trigger_block_present(self) -> None:
        body = (
            "CREATE TRIGGER trg_users_touch BEFORE UPDATE ON public.users "
            "FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();"
        )
        ex = efs.SchemaExtraction(triggers=[("trg_users_touch", body)])
        out = efs.render_sql(ex)
        assert "trg_users_touch" in out

    def test_view_wrapped_in_create_or_replace(self) -> None:
        body = 'CREATE OR REPLACE VIEW "public"."active_users" AS\nSELECT * FROM users WHERE active'
        ex = efs.SchemaExtraction(views=[("active_users", body)])
        out = efs.render_sql(ex)
        assert "CREATE OR REPLACE VIEW" in out
        assert "active_users" in out

    def test_materialized_view_idempotent(self) -> None:
        body = (
            'CREATE MATERIALIZED VIEW IF NOT EXISTS "public"."v_stats" AS\n'
            "SELECT count(*) FROM users\nWITH NO DATA;"
        )
        ex = efs.SchemaExtraction(materialized_views=[("v_stats", body)])
        out = efs.render_sql(ex)
        assert "CREATE MATERIALIZED VIEW IF NOT EXISTS" in out
        assert "WITH NO DATA" in out


# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------

class TestConstants:
    def test_target_schema_is_public(self) -> None:
        assert efs.TARGET_SCHEMA == "public"

    def test_relevant_extensions_includes_pgvector(self) -> None:
        assert "pgvector" in efs.RELEVANT_EXTENSIONS
        assert "uuid-ossp" in efs.RELEVANT_EXTENSIONS

    def test_default_output_under_baseline_dir(self) -> None:
        assert efs.DEFAULT_OUTPUT.parent.name == "baseline"
        assert efs.DEFAULT_OUTPUT.parent.parent.name == "database"
