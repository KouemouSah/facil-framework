#!/usr/bin/env python
"""
Looker Studio (Data Studio) — Linking API URL generator for Facil

Reference: https://developers.google.com/looker-studio/integrate/linking-api

Three URL families produced:
1. `datasource-create` — pre-fills the PostgreSQL connector form so the
   operator only types the password and clicks Connect.
2. `report-clone` — clones an existing template report and rebinds it to
   our datasource. Used after the first dashboard is built in UI to make
   subsequent dashboards a 1-click operation.
3. `report-embed` — produces the iframe embed URL used in the Next.js
   `/admin/dashboards/*` routes (Phase 5).

Usage:
    # 1. Pre-fill the PostgreSQL connector form
    python looker_studio_url_generator.py datasource

    # 2. Clone a template report (after building one in UI)
    python looker_studio_url_generator.py report-clone \
        --template-id 1abc... --datasource-alias treasury

    # 3. Get the embed URL for /admin/dashboards/recaudacion
    python looker_studio_url_generator.py embed --report-id <REPORT_ID>

Notes on connector IDs:
    Looker Studio's built-in PostgreSQL connector uses the public ID
    `2-c-postgres` (verified 2026-05). If Google changes this in the
    future, the script falls back to the override env var
    LOOKER_PG_CONNECTOR_ID. The fastest way to verify the current ID is
    to open https://lookerstudio.google.com/datasources/create , click
    'PostgreSQL', then read the URL — the `connectorId=...` query
    parameter is the canonical value at the time of inspection.

Why password isn't in the URL: Looker Studio's Linking API explicitly
forbids credentials in URL parameters. The user types the password once
on the connector page; Looker Studio stores it server-side and re-uses
it on every report refresh.
"""
import argparse
import os
import sys
import subprocess
from urllib.parse import urlencode

LOOKER_BASE = "https://lookerstudio.google.com"
PG_CONNECTOR_ID = os.environ.get("LOOKER_PG_CONNECTOR_ID", "2-c-postgres")

# Standard Facil connection — built from GCP Secret Manager once at runtime.
# We never bake credentials into the generator code.
GCLOUD = r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" \
         if os.name == "nt" else "gcloud"
PROJECT = "taxasge-dev"


def fetch_db_url() -> str:
    """Return looker-readonly-db-url from GCP Secret Manager.

    Falls back to env var LOOKER_READONLY_DB_URL if set (CI / contexts
    where gcloud subprocess hangs — observed on Cygwin bash + gcloud.cmd
    where the subprocess pipe doesn't close cleanly). Setting the env
    var lets the operator pre-fetch the URL once via shell:

        export LOOKER_READONLY_DB_URL="$(gcloud secrets versions access \
            latest --secret=looker-readonly-db-url --project=taxasge-dev)"
    """
    env_override = os.environ.get("LOOKER_READONLY_DB_URL")
    if env_override:
        return env_override.strip()
    out = subprocess.check_output(
        [GCLOUD, "secrets", "versions", "access", "latest",
         "--secret=looker-readonly-db-url", "--project", PROJECT],
        text=True,
        stdin=subprocess.DEVNULL,    # prevent gcloud waiting on terminal stdin
        timeout=30,                   # fail fast instead of hanging the script
    ).strip()
    return out


def parse_db_url(url: str) -> dict:
    """Extract host, port, db, user from postgresql://user:pwd@host:port/db?...

    Password is intentionally discarded — never in URL params per Linking API spec.
    """
    from urllib.parse import urlparse
    p = urlparse(url)
    return {
        "host": p.hostname,
        "port": str(p.port),
        "database": p.path.lstrip("/").split("?")[0],
        "username": p.username,
    }


def build_datasource_url(conn: dict, ssl: bool = True) -> str:
    """Build URL that opens the create-datasource form pre-filled."""
    params = {
        "connectorId": PG_CONNECTOR_ID,
        # ds.<connectorParam> per the Linking API spec for connectors
        "ds.host": conn["host"],
        "ds.port": conn["port"],
        "ds.database": conn["database"],
        "ds.username": conn["username"],
        "ds.enableSsl": "true" if ssl else "false",
        # ds.refreshFields=true forces Looker to re-introspect the schema
        # immediately after auth, so the field list is up-to-date with
        # whatever objects we GRANTed last (helps when we add new MVs).
        "ds.refreshFields": "true",
    }
    return f"{LOOKER_BASE}/datasources/create?{urlencode(params)}"


def build_report_clone_url(template_report_id: str,
                           datasource_alias: str = "ds0",
                           datasource_id: str = None) -> str:
    """Build URL that clones an existing report and (optionally) rebinds
    its datasource to a new one we already created.
    """
    params = {
        "c.reportId": template_report_id,
        "c.mode": "edit",
    }
    if datasource_id:
        # ds.<alias>.datasourceId tells Looker to swap the source bound
        # to the alias `datasource_alias` for the existing datasource id
        # we just authenticated.
        params[f"ds.{datasource_alias}.datasourceId"] = datasource_id
    return f"{LOOKER_BASE}/reporting/create?{urlencode(params)}"


def build_embed_url(report_id: str, page_id: str = None) -> str:
    """Build the iframe-embeddable URL for /admin/dashboards/*."""
    path = f"/embed/reporting/{report_id}"
    if page_id:
        path += f"/page/{page_id}"
    return f"{LOOKER_BASE}{path}"


def cmd_datasource(args):
    print("Fetching looker-readonly-db-url from GCP Secret Manager...")
    db_url = fetch_db_url()
    conn = parse_db_url(db_url)
    print(f"  host:     {conn['host']}")
    print(f"  port:     {conn['port']}")
    print(f"  database: {conn['database']}")
    print(f"  username: {conn['username']}")
    print()
    url = build_datasource_url(conn, ssl=True)
    print("Open this URL in the browser logged in to Looker Studio:")
    print(f"\n{url}\n")
    print("Then paste the password from:")
    print(f"  gcloud secrets versions access latest \\")
    print(f"    --secret=looker-readonly-pwd --project={PROJECT}")
    print()
    print("Click 'AUTHENTICATE' -> wait for the table list -> pick your first table -> 'CONNECT'.")


def cmd_report_clone(args):
    if not args.template_id:
        print("ERROR: --template-id required (find via UI: open report → URL is .../reporting/<ID>/edit)")
        sys.exit(2)
    url = build_report_clone_url(
        template_report_id=args.template_id,
        datasource_alias=args.datasource_alias,
        datasource_id=args.datasource_id,
    )
    print(url)


def cmd_embed(args):
    if not args.report_id:
        print("ERROR: --report-id required")
        sys.exit(2)
    url = build_embed_url(report_id=args.report_id, page_id=args.page_id)
    print(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ds = sub.add_parser("datasource",
                          help="Pre-fill datasource creation URL")
    p_ds.set_defaults(func=cmd_datasource)

    p_rc = sub.add_parser("report-clone",
                          help="Clone an existing template report")
    p_rc.add_argument("--template-id", required=True)
    p_rc.add_argument("--datasource-alias", default="ds0",
                      help="Alias of the datasource bound in the template (default ds0)")
    p_rc.add_argument("--datasource-id",
                      help="ID of an existing datasource to bind to the alias")
    p_rc.set_defaults(func=cmd_report_clone)

    p_em = sub.add_parser("embed",
                          help="Build iframe embed URL for /admin/dashboards/*")
    p_em.add_argument("--report-id", required=True)
    p_em.add_argument("--page-id",
                      help="Optional page within the report")
    p_em.set_defaults(func=cmd_embed)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
