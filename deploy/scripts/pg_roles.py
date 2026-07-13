#!/usr/bin/env python3
"""SQL du role applicatif moindre-privilege — partage docker-local <-> k3s.

`deploy/providers/bootstrap/postgres.py` cree deja ce role, mais via `docker exec`
(transport non portable sur k3s). Ce module n'expose que le **SQL**, que les deux
chemins executent avec leur propre transport (docker exec / Job Helm psql).

Le mot de passe n'est JAMAIS concatene dans le SQL : il est passe a psql via
`-v app_pw=...` et reference par `:'app_pw'` (quoting psql), sinon il finirait en
clair dans les logs Postgres (CWE-532).
"""
from __future__ import annotations


def app_role_name(project: str) -> str:
    """Nom du role applicatif — meme convention que bootstrap/postgres.py:93."""
    return f"{project}_app"


def create_role_sql(role: str, db: str) -> list[str]:
    """CREATE ROLE idempotent + grants moindre-privilege.

    Idempotent car rejoue a CHAQUE `helm upgrade` (hook pre-upgrade) : un
    `CREATE ROLE` nu echouerait avec "role already exists" des le 2e deploiement.
    ALTER ROLE reaffirme le mot de passe courant (rotation supportee).
    """
    return [
        f"""DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$""",
        f"ALTER ROLE {role} WITH LOGIN PASSWORD :'app_pw'",
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
