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
    # Le mot de passe est lu par psql via \getenv (variable d'environnement du
    # process), jamais concatene dans le SQL (sinon il finirait dans les logs
    # Postgres — CWE-532) et jamais passe en argv psql (CWE-214).
    stmts = pg_roles.create_role_sql("facil_app", "facil")
    sql = " ".join(stmts)
    assert "PASSWORD '" not in sql
    assert ":'app_pw'" in sql  # placeholder psql
    # \getenv doit etre la PREMIERE instruction (avant tout usage de :'app_pw').
    assert stmts[0] == "\\getenv app_pw FACIL_APP_PASSWORD"
    assert stmts.index(stmts[0]) < next(
        i for i, s in enumerate(stmts) if ":'app_pw'" in s)


def test_grants_sql_is_the_tail_of_create_role_sql():
    # grants_sql() est la source unique deleguee par bootstrap/postgres.py::_grants
    # (chemin docker-local) — create_role_sql() (chemin k3s) doit rendre EXACTEMENT
    # la meme liste en fin de script, sinon les deux transports divergent.
    role, db = "facil_app", "facil"
    grants = pg_roles.grants_sql(role, db)
    stmts = pg_roles.create_role_sql(role, db)
    assert stmts[-len(grants):] == grants


def test_render_sql_terminates_getenv_by_newline_not_semicolon():
    # \getenv est une meta-commande psql : elle doit finir par un saut de ligne,
    # PAS par ';' (sinon ';' rejoint le dernier argument -> psql cherche la
    # variable d'env "FACIL_APP_PASSWORD;", qui n'existe pas, et app_pw reste
    # indefini). Reproduit et corrige un piege trouve en revue (finding R2/F1).
    rendered = pg_roles.render_sql("facil_app", "facil")
    assert "\\getenv app_pw FACIL_APP_PASSWORD\n" in rendered
    assert "FACIL_APP_PASSWORD;" not in rendered
    # Aucune trace de l'ancien canal de fuite argv (-v app_pw=...).
    assert "-v app_pw" not in rendered
    assert ":'app_pw'" in rendered  # le reste du SQL reste bien rendu
