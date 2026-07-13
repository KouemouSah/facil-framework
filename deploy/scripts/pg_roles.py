#!/usr/bin/env python3
"""SQL du role applicatif moindre-privilege — partage docker-local <-> k3s.

`deploy/providers/bootstrap/postgres.py` cree deja ce role, mais via `docker exec`
(transport non portable sur k3s). Ce module expose le **SQL** (`create_role_sql` /
`render_sql`) que le chemin k3s execute via le Job Helm `psql`, et les **grants**
(`grants_sql`) que `bootstrap/postgres.py::_grants` delegue ici — seule la partie
reellement dupliquee entre les deux transports (docker exec vs Job Helm) est
factorisee ; la logique de rotation idempotente reste propre a chaque chemin.

Le mot de passe n'est JAMAIS concatene dans le SQL : il est lu par psql via la
meta-commande `\\getenv app_pw FACIL_APP_PASSWORD` (PostgreSQL 14+ ; l'image du
chart est `pgvector/pgvector:pg16`) et reference par `:'app_pw'` (quoting psql).
`\\getenv` lit la variable **d'environnement** du process psql — elle ne transite
JAMAIS par son `argv[]`. Ceci ferme DEUX canaux de fuite distincts :
  - CWE-532 : le mot de passe n'apparait jamais en clair dans les logs Postgres
    (il n'est jamais concatene dans une instruction SQL).
  - CWE-214 : le mot de passe n'apparait jamais dans l'argv de psql (donc pas
    dans `/proc/<pid>/cmdline`, lisible par tout process co-localise / EDR /
    scraper d'audit) — contrairement a `-v app_pw="$VAR"` qui interpole la
    variable AVANT d'exec `psql`.
"""
from __future__ import annotations


def app_role_name(project: str) -> str:
    """Nom du role applicatif — meme convention que bootstrap/postgres.py:93."""
    return f"{project}_app"


def grants_sql(role: str, db: str) -> list[str]:
    """Grants moindre-privilege — source unique partagee par les deux transports
    (docker exec via `bootstrap/postgres.py::_grants`, Job Helm psql via
    `create_role_sql`). Modifier les privileges ici seulement : les deux chemins
    divergeraient silencieusement sinon.
    """
    return [
        f"GRANT CONNECT ON DATABASE {db} TO {role}",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
        # Les tables creees ENSUITE par alembic (superuser) sont auto-grantees au
        # role applicatif — sinon chaque migration exigerait un re-grant manuel.
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role}",
    ]


def create_role_sql(role: str, db: str) -> list[str]:
    """CREATE ROLE idempotent + grants moindre-privilege.

    Idempotent car rejoue a CHAQUE `helm upgrade` (hook pre-upgrade) : un
    `CREATE ROLE` nu echouerait avec "role already exists" des le 2e deploiement.
    ALTER ROLE reaffirme le mot de passe courant (rotation supportee).

    Le 1er element est une meta-commande psql (`\\getenv`, pas une instruction
    SQL) : elle doit rester la PREMIERE ligne du script rendu, et ne doit JAMAIS
    recevoir de `;` terminal (voir `render_sql`).
    """
    return [
        "\\getenv app_pw FACIL_APP_PASSWORD",
        f"""DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$""",
        f"ALTER ROLE {role} WITH LOGIN PASSWORD :'app_pw'",
        *grants_sql(role, db),
    ]


def render_sql(role: str, db: str) -> str:
    """Assemble le script psql complet execute par le Job Helm.

    Les instructions SQL sont terminees par `;`, mais les meta-commandes psql
    (lignes commencant par `\\`, ex. `\\getenv`) sont terminees par un simple
    saut de ligne — psql les lit jusqu'a la fin de ligne, PAS jusqu'au premier
    `;`. Un `;` accole rendrait `FACIL_APP_PASSWORD;` comme nom de variable
    d'environnement (qui n'existe pas) et `app_pw` ne serait jamais defini,
    laissant `:'app_pw'` litteral dans le SQL suivant.
    """
    lines = [
        stmt if stmt.startswith("\\") else f"{stmt};"
        for stmt in create_role_sql(role, db)
    ]
    return "\n".join(lines) + "\n"
