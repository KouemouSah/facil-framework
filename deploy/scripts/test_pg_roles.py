from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

import pg_roles  # noqa: E402


def test_app_role_name_is_derived_from_project():
    assert pg_roles.app_role_name("facil") == "facil_app"


def test_create_role_sql_is_least_privilege_and_idempotent():
    sql = pg_roles.create_role_sql("facil_app", "facil")
    joined = " ".join(sql)
    # Le role applicatif ne doit JAMAIS pouvoir creer des roles/bases ni etre superuser.
    assert "NOSUPERUSER" in joined and "NOCREATEDB" in joined and "NOCREATEROLE" in joined
    # Idempotent : un re-run (helm upgrade) ne doit pas echouer sur "role already exists".
    assert any("DO $$" in s or "IF NOT EXISTS" in s for s in sql)
    # Les tables creees PLUS TARD par alembic (superuser) doivent etre auto-grantees.
    assert "ALTER DEFAULT PRIVILEGES" in joined
    # Aucun DROP/GRANT ALL : moindre privilege strict.
    assert "GRANT ALL" not in joined and "DROP" not in joined


def test_create_role_sql_never_embeds_a_password():
    # Le mot de passe est passe par psql -v (variable), jamais concatene dans le SQL
    # (sinon il finirait dans les logs Postgres — CWE-532).
    sql = " ".join(pg_roles.create_role_sql("facil_app", "facil"))
    assert "PASSWORD '" not in sql
    assert ":'app_pw'" in sql  # placeholder psql
