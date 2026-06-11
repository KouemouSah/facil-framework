#!/usr/bin/env python3
"""Interactive deployment wizard.

Generates `deploy/config.yaml` + `.env.secrets` (at repo root) by asking
the operator a guided sequence of questions. Auto-generates the random
auth secrets so the operator only has to provide values that genuinely
require human input (Gemini API key, Firebase JSON, etc.).

This is the CLI equivalent of a setup wizard — same UX as `npm init`,
`expo init`, `gh repo create`. Pure stdlib (input + getpass), no
extra dependencies on top of what validate_config.py already requires.

Usage
-----
    # Interactive (default)
    python deploy/init.py

    # Non-interactive: read all answers from environment variables.
    # Useful in CI. See FIELD_ENV_MAP at the bottom of this module for the
    # variable names.
    python deploy/init.py --non-interactive

    # Custom output paths.
    python deploy/init.py --config-out=deploy/config.yaml \\
                         --secrets-out=.env.secrets

    # Overwrite existing files without prompting.
    python deploy/init.py --force

Exit codes
----------
0  Files written successfully (validated against the Pydantic schema).
1  Generated config fails validation.
2  User aborted.
3  Refused to overwrite existing file (use --force).
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Callable

# Reuse validate_config to ensure what we generate is actually valid.
DEPLOY_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

REPO_ROOT = DEPLOY_DIR.parent
DEFAULT_CONFIG_OUT = DEPLOY_DIR / "config.yaml"
DEFAULT_SECRETS_OUT = REPO_ROOT / ".env.secrets"


# ---------------------------------------------------------------------------
# Prompt primitives
# ---------------------------------------------------------------------------

class Prompter:
    """Question/answer interface. Switches between interactive (input/getpass)
    and non-interactive (env vars + defaults) modes."""

    def __init__(self, non_interactive: bool) -> None:
        self.non_interactive = non_interactive

    def ask(
        self, question: str, *, default: str | None = None, env: str | None = None,
    ) -> str:
        """Ask a question. Returns the answer.

        - Non-interactive: reads $env or returns default. Errors if both missing.
        - Interactive: prompts the user. Empty input -> default if provided.
        """
        if env and os.environ.get(env):
            return os.environ[env]

        if self.non_interactive:
            if default is None:
                raise SystemExit(
                    f"Non-interactive mode: required value '{question}' has no "
                    f"default and no env var ({env}) set."
                )
            return default

        suffix = f" [{default}]" if default else ""
        answer = input(f"? {question}{suffix}: ").strip()
        return answer or (default or "")

    def ask_secret(
        self, question: str, *, env: str | None = None,
    ) -> str:
        """Like ask() but masks input for sensitive values.

        Falls back to ask() in non-interactive mode (env vars are not secrets
        from the wizard's POV — the operator already exposed them).
        """
        if env and os.environ.get(env):
            return os.environ[env]

        if self.non_interactive:
            raise SystemExit(
                f"Non-interactive mode: secret '{question}' must be provided "
                f"via env var ({env})."
            )
        return getpass.getpass(f"? {question} (input hidden): ").strip()

    def ask_bool(
        self,
        question: str,
        *,
        default: bool = False,
        env: str | None = None,
    ) -> bool:
        if env and os.environ.get(env):
            return os.environ[env].lower() in ("1", "true", "yes", "y")
        if self.non_interactive:
            return default
        suffix = "[Y/n]" if default else "[y/N]"
        answer = input(f"? {question} {suffix}: ").strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes", "1", "true")

    def ask_choice(
        self,
        question: str,
        choices: list[str],
        *,
        default: str,
        env: str | None = None,
    ) -> str:
        if env and os.environ.get(env):
            v = os.environ[env]
            if v not in choices:
                raise SystemExit(f"{env}={v} not in choices {choices}")
            return v
        if self.non_interactive:
            return default
        labels = "/".join(c if c != default else c.upper() for c in choices)
        while True:
            answer = input(f"? {question} [{labels}]: ").strip().lower()
            if not answer:
                return default
            if answer in choices:
                return answer
            print(f"  Invalid choice. Pick one of: {', '.join(choices)}")

    def section(self, title: str) -> None:
        if self.non_interactive:
            return
        print()
        print(f"=== {title} ===")


# ---------------------------------------------------------------------------
# Random secret generators
# ---------------------------------------------------------------------------

def gen_hex(n_bytes: int = 32) -> str:
    """Cryptographically random hex string (n_bytes -> 2n hex chars)."""
    return secrets.token_hex(n_bytes)


def gen_urlsafe(n_bytes: int = 32) -> str:
    return secrets.token_urlsafe(n_bytes)


def gen_fernet_key() -> str:
    """Generate a Fernet key (32-byte base64). Falls back to raw urlsafe if
    `cryptography` isn't importable — Fernet itself accepts any 32-byte
    base64-encoded key."""
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode("ascii")
    except ImportError:
        # Fernet expects 32 raw bytes, base64-encoded.
        import base64
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


# ---------------------------------------------------------------------------
# Wizard sections
# ---------------------------------------------------------------------------

def collect_meta(p: Prompter) -> dict[str, Any]:
    p.section("1/9 — Project metadata")
    return {
        "config_version": 1,
        "project_name": p.ask(
            "Project name (lowercase, no spaces)",
            default="facil",
            env="WIZ_PROJECT_NAME",
        ),
        "environment": p.ask_choice(
            "Environment",
            ["production", "staging", "development"],
            default="development",
            env="WIZ_ENVIRONMENT",
        ),
        "version": p.ask(
            "Image version tag",
            default="latest",
            env="WIZ_VERSION",
        ),
        "profile": collect_profile(p),
    }


def collect_database(p: Prompter, secrets_out: dict) -> dict[str, Any]:
    p.section("2/9 — Database (Postgres)")
    use_url = p.ask_bool(
        "Use a single DATABASE_URL secret (vs discrete fields)?",
        default=True,
        env="WIZ_DB_USE_URL",
    )
    cfg: dict[str, Any] = {
        "url_secret": "",
        "host": "",
        "port": 5432,
        "name": "",
        "user": "",
        "password_secret": "",
        "ssl_mode": "require",
        "pool": {
            "min_connections": 10,
            "max_connections": 20,
            "pool_timeout_seconds": 30,
        },
    }
    if use_url:
        cfg["url_secret"] = p.ask(
            "Secret name holding the full DATABASE_URL",
            default="database-url",
            env="WIZ_DB_URL_SECRET",
        )
    else:
        cfg["host"] = p.ask("Host", default="localhost", env="WIZ_DB_HOST")
        cfg["name"] = p.ask("Database name", default="facil", env="WIZ_DB_NAME")
        cfg["user"] = p.ask("User", default="facil", env="WIZ_DB_USER")
        cfg["password_secret"] = p.ask(
            "Secret name holding DB password",
            default="database-password",
            env="WIZ_DB_PASSWORD_SECRET",
        )
        cfg["ssl_mode"] = p.ask_choice(
            "SSL mode",
            ["disable", "require", "verify-ca", "verify-full"],
            default="require",
            env="WIZ_DB_SSL",
        )
    return cfg


def collect_redis(p: Prompter) -> dict[str, Any]:
    p.section("3/9 — Redis (cache + rate limit)")
    return {
        "url_secret": p.ask(
            "Secret name holding REDIS_URL",
            default="REDIS_URL",
            env="WIZ_REDIS_URL_SECRET",
        ),
        "cache_ttl_seconds": 3600,
    }


def collect_auth(p: Prompter, secrets_out: dict) -> dict[str, Any]:
    p.section("4/9 — Auth secrets (JWT, session, TOTP)")

    autogen = p.ask_bool(
        "Auto-generate random JWT/SECRET/TOTP keys for you?",
        default=True,
        env="WIZ_AUTH_AUTOGEN",
    )

    if autogen:
        secrets_out["JWT_SECRET_KEY"] = gen_hex(32)
        secrets_out["SECRET_KEY"] = gen_hex(32)
        secrets_out["TOTP_ENCRYPTION_KEY"] = gen_fernet_key()
        secrets_out["RECEIPT_VERIFICATION_SECRET"] = gen_hex(32)
        if not p.non_interactive:
            print("  ✓ Generated 4 cryptographic keys (will be written to .env.secrets)")
    else:
        secrets_out["JWT_SECRET_KEY"] = p.ask_secret(
            "JWT_SECRET_KEY (32+ bytes)", env="WIZ_JWT_SECRET",
        )
        secrets_out["SECRET_KEY"] = p.ask_secret(
            "SECRET_KEY (32+ bytes)", env="WIZ_SECRET_KEY",
        )
        secrets_out["TOTP_ENCRYPTION_KEY"] = p.ask_secret(
            "TOTP_ENCRYPTION_KEY (Fernet base64)", env="WIZ_TOTP_KEY",
        )
        secrets_out["RECEIPT_VERIFICATION_SECRET"] = p.ask_secret(
            "RECEIPT_VERIFICATION_SECRET (32+ bytes)",
            env="WIZ_RECEIPT_SECRET",
        )

    return {
        "jwt_secret_name": "JWT_SECRET_KEY",
        "app_secret_name": "SECRET_KEY",
        "totp_encryption_secret": "TOTP_ENCRYPTION_KEY",
        "receipt_verification_secret": "RECEIPT_VERIFICATION_SECRET",
        "access_token_minutes": 30,
        "refresh_token_days": 30,
    }


def collect_firebase(p: Prompter, secrets_out: dict) -> dict[str, Any]:
    p.section("5/9 — Firebase (push notifications + storage)")
    project_id = p.ask(
        "Firebase project_id (e.g. 'facil-prod')",
        default="facil-dev",
        env="WIZ_FIREBASE_PROJECT",
    )
    bucket = p.ask(
        "Firebase storage bucket",
        default=f"{project_id}.appspot.com",
        env="WIZ_FIREBASE_BUCKET",
    )
    has_admin_key = p.ask_bool(
        "Do you have a Firebase Admin SDK service account JSON to provide?",
        default=False,
        env="WIZ_FIREBASE_HAS_KEY",
    )
    if has_admin_key:
        admin_json = p.ask_secret(
            "Paste the full JSON on one line",
            env="WIZ_FIREBASE_ADMIN_JSON",
        )
        secrets_out["FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV"] = admin_json
    return {
        "project_id": project_id,
        "storage_bucket": bucket,
        "android_app_id": "",
        "service_account_dev_secret": "FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV"
            if has_admin_key else "",
        "service_account_pro_secret": "",
    }


def collect_ai(p: Prompter, secrets_out: dict) -> dict[str, Any]:
    p.section("6/9 — AI (Gemini / Vertex)")
    use_api_key = p.ask_choice(
        "Authentication mode",
        ["api_key", "vertex"],
        default="api_key",
        env="WIZ_AI_MODE",
    ) == "api_key"

    cfg: dict[str, Any] = {
        "gemini_api_key_secret": "",
        "google_cloud_project": "",
        "google_cloud_location": "us-central1",
        "models": {
            "chat": "gemini-2.5-flash",
            "pro": "gemini-2.5-flash",
            "embedding": "text-embedding-005",
        },
        "generation": {
            "max_output_tokens": 2048,
            "temperature": 0.5,
            "top_p": 0.9,
            "top_k": 40,
        },
    }
    if use_api_key:
        api_key = p.ask_secret(
            "Gemini API key (from https://aistudio.google.com/app/apikey)",
            env="WIZ_GEMINI_API_KEY",
        )
        if api_key:
            secrets_out["GEMINI_API_KEY"] = api_key
            cfg["gemini_api_key_secret"] = "GEMINI_API_KEY"
    else:
        cfg["google_cloud_project"] = p.ask(
            "GCP project ID (Vertex AI runs here)",
            default="facil-dev",
            env="WIZ_GCP_PROJECT",
        )
    return cfg


def collect_server(p: Prompter, env_label: str) -> dict[str, Any]:
    p.section("7/9 — Server URLs")
    if env_label == "development":
        default_frontend = "http://localhost:3000"
        default_api = "http://localhost:8080"
    else:
        default_frontend = "https://facil.gq"
        default_api = "https://api.facil.gq"
    return {
        "api_host": "0.0.0.0",
        "port": 8080,
        "frontend_url": p.ask(
            "Frontend URL", default=default_frontend, env="WIZ_FRONTEND_URL",
        ),
        "api_base_url": p.ask(
            "API base URL", default=default_api, env="WIZ_API_URL",
        ),
        "mobile_deep_link_schemes": "facil",
        "log_level": "INFO" if env_label == "production" else "DEBUG",
    }


def collect_cron(p: Prompter, secrets_out: dict) -> dict[str, Any]:
    p.section("8/9 — Cron (scheduled jobs)")
    secrets_out["CRON_SECRET"] = gen_urlsafe(32)
    if not p.non_interactive:
        print("  ✓ Generated CRON_SECRET (will be written to .env.secrets)")
    return {"secret_name": "CRON_SECRET"}


def collect_provider(p: Prompter, env_label: str) -> str:
    p.section("9/9 — Target deployment provider")
    return p.ask_choice(
        "Provider",
        ["docker-local", "vps", "gcp", "aws", "azure"],
        default="docker-local" if env_label == "development" else "gcp",
        env="WIZ_PROVIDER",
    )


def collect_docker_db_mode(
    p: Prompter, secrets_out: dict, provider: str,
) -> str:
    """Ask whether the docker-local stack should run its own postgres
    container, or connect to an external Postgres (Supabase, RDS, etc.).

    Only relevant if provider == 'docker-local'. For gcp/aws, the field
    is stored but unused.
    """
    if provider != "docker-local":
        return "local"

    p.section("9b/9 — Docker local: database location")
    if not p.non_interactive:
        print("  - 'local'    : compose generates a postgres container "
              "(zero external dependencies, good first install).")
        print("  - 'external' : connect to Supabase / RDS / Cloud SQL via the "
              "DATABASE_URL you provide in .env.secrets.")
    mode = p.ask_choice(
        "Database location",
        ["local", "external"],
        default="local",
        env="WIZ_DOCKER_DB_MODE",
    )

    if mode == "external":
        # Prompt for the DATABASE_URL value (will be stored in .env.secrets).
        url = p.ask_secret(
            "Full DATABASE_URL (postgresql://user:pwd@host:port/dbname)",
            env="WIZ_EXTERNAL_DATABASE_URL",
        )
        if url:
            secrets_out["DATABASE_URL"] = url
            if not p.non_interactive:
                print("  ✓ DATABASE_URL stored in .env.secrets")
        else:
            if not p.non_interactive:
                print("  ! No URL provided. You MUST add DATABASE_URL to "
                      ".env.secrets manually before --apply.")
    return mode


def collect_gcp(p: Prompter) -> dict[str, Any]:
    project = p.ask(
        "GCP project_id",
        default="facil-dev",
        env="WIZ_GCP_PROJECT_ID",
    )
    region = p.ask(
        "GCP region",
        default="us-central1",
        env="WIZ_GCP_REGION",
    )
    return {
        "project_id": project,
        "region": region,
        "backend_service_name": "facil-backend",
        "frontend_service_name": "facil-frontend",
        "cloud_sql_instance": "",
        "custom_domain_backend": "",
        "custom_domain_frontend": "",
    }


# ---------------------------------------------------------------------------
# Provider-aware defaults (storage / secrets backend follow the target)
# ---------------------------------------------------------------------------

# provider -> (default storage provider, default secrets provider). On-prem /
# docker-local / vps stay sovereign (MinIO + OpenBao); each cloud uses its native
# object store + secret manager.
_STORAGE_DEFAULT = {
    "docker-local": "minio", "vps": "minio",
    "gcp": "gcs", "aws": "s3", "azure": "azure_blob",
}
_SECRETS_DEFAULT = {
    "docker-local": "openbao", "vps": "openbao",
    "gcp": "gcp_secret_manager", "aws": "aws_secrets_manager",
    "azure": "azure_key_vault",
}


def collect_profile(p: Prompter) -> str:
    return p.ask_choice(
        "Deployment profile (sets coherent module/branding defaults)",
        ["empty", "private-services-company", "gov-emergent-country",
         "saas-multitenant", "banking"],
        default="empty",
        env="WIZ_PROFILE",
    )


def collect_storage(p: Prompter, provider: str) -> dict[str, Any]:
    p.section("Storage (object store)")
    sp = p.ask_choice(
        "Storage provider",
        ["minio", "s3", "gcs", "azure_blob", "local_fs", "disabled"],
        default=_STORAGE_DEFAULT.get(provider, "minio"),
        env="WIZ_STORAGE_PROVIDER",
    )
    cfg: dict[str, Any] = {"provider": sp}
    if sp == "minio":
        bucket = p.ask("Default documents bucket", default="facil-documents",
                       env="WIZ_MINIO_BUCKET")
        worm = p.ask_bool("Enable a WORM compliance bucket (Object-Lock)?",
                          default=True, env="WIZ_MINIO_WORM")
        cfg["minio"] = {
            "default_bucket": bucket,
            "compliance": {
                "enabled": worm,
                "bucket": "facil-compliance",
                "retention_mode": p.ask_choice(
                    "Compliance retention mode",
                    ["governance", "compliance"], default="governance",
                    env="WIZ_MINIO_RETENTION_MODE") if worm else "governance",
                "retention_days": 365,
            },
        }
    return cfg


def collect_secrets_backend(p: Prompter, provider: str) -> dict[str, Any]:
    p.section("Secrets backend")
    prov = p.ask_choice(
        "Secrets provider",
        ["env_file", "openbao", "sops_age", "gcp_secret_manager",
         "aws_secrets_manager", "azure_key_vault"],
        default=_SECRETS_DEFAULT.get(provider, "env_file"),
        env="WIZ_SECRETS_PROVIDER",
    )
    return {"provider": prov}


def collect_observability(p: Prompter, env_label: str) -> dict[str, Any]:
    p.section("Observability (telemetry)")
    mode = p.ask_choice(
        "Telemetry mode",
        ["disabled", "local", "cloud"],
        default="local" if env_label != "production" else "disabled",
        env="WIZ_OBS_MODE",
    )
    cfg: dict[str, Any] = {"mode": mode}
    if mode == "local":
        cfg["otlp_endpoint"] = p.ask(
            "OTLP endpoint (self-hosted otel-lgtm)",
            default="http://otel-lgtm:4317", env="WIZ_OBS_OTLP")
    elif mode == "cloud":
        cfg["otlp_endpoint"] = p.ask(
            "OTLP endpoint (cloud collector)", default="", env="WIZ_OBS_OTLP")
        cfg["errors_backend"] = p.ask_choice(
            "Error tracking", ["none", "sentry_saas", "glitchtip"],
            default="none", env="WIZ_OBS_ERRORS")
    return cfg


def collect_edge(p: Prompter, env_label: str) -> dict[str, Any]:
    p.section("Edge (reverse proxy)")
    enable = p.ask_bool(
        "Front the stack with a Caddy reverse-proxy (single origin, TLS)?",
        default=env_label == "production", env="WIZ_EDGE_ENABLE")
    if not enable:
        return {"proxy": "none", "tls_mode": "none"}
    return {
        "proxy": "caddy",
        "tls_mode": p.ask_choice(
            "TLS mode", ["none", "internal", "acme"],
            default="acme" if env_label == "production" else "internal",
            env="WIZ_EDGE_TLS"),
        "domain_frontend": p.ask("Frontend domain (for TLS)", default="",
                                 env="WIZ_EDGE_DOMAIN_FRONTEND"),
        "domain_backend": p.ask("Backend domain (for TLS)", default="",
                                env="WIZ_EDGE_DOMAIN_BACKEND"),
    }


def collect_aws(p: Prompter) -> dict[str, Any]:
    p.section("AWS target")
    return {
        "region": p.ask("AWS region", default="us-east-1", env="WIZ_AWS_REGION"),
        "account_id": p.ask("AWS account ID (12 digits)", default="",
                            env="WIZ_AWS_ACCOUNT"),
        "runtime": p.ask_choice("Compute runtime", ["app_runner", "ecs_fargate"],
                                default="app_runner", env="WIZ_AWS_RUNTIME"),
        "ecr_repository": p.ask("ECR repository", default="facil",
                                env="WIZ_AWS_ECR"),
        "backend_service_name": "facil-backend",
        "frontend_service_name": "facil-frontend",
        "backend_cluster": "facil-backend",
        "rds_instance": p.ask("RDS instance id (blank = external DATABASE_URL)",
                              default="", env="WIZ_AWS_RDS"),
        "secrets_manager_prefix": "facil/",
        "custom_domain_backend": "", "custom_domain_frontend": "",
    }


def collect_azure(p: Prompter) -> dict[str, Any]:
    p.section("Azure target")
    return {
        "subscription_id": p.ask("Azure subscription ID", default="",
                                 env="WIZ_AZURE_SUB"),
        "resource_group": p.ask("Resource group", default="facil-rg",
                                env="WIZ_AZURE_RG"),
        "location": p.ask("Location", default="westeurope",
                          env="WIZ_AZURE_LOCATION"),
        "acr_registry": p.ask("Container registry (ACR) name", default="",
                              env="WIZ_AZURE_ACR"),
        "containerapp_env": "facil-env",
        "backend_app_name": "facil-backend",
        "frontend_app_name": "facil-frontend",
        "postgres_flexible_server": p.ask(
            "Postgres Flexible Server name (blank = external)", default="",
            env="WIZ_AZURE_PG"),
        "keyvault_name": p.ask("Key Vault name", default="",
                               env="WIZ_AZURE_KV"),
        "custom_domain_backend": "", "custom_domain_frontend": "",
    }


# ---------------------------------------------------------------------------
# YAML rendering
# ---------------------------------------------------------------------------

def render_config_yaml(cfg: dict[str, Any]) -> str:
    """Render the config dict back to YAML. We use a deterministic order
    that matches config.example.yaml so diffs stay clean."""
    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML required (pip install pyyaml)")

    header = (
        "# Generated by deploy/init.py — feel free to edit by hand.\n"
        "# Re-run the wizard with --force to regenerate from scratch.\n"
        "\n"
    )
    return header + yaml.safe_dump(
        cfg, sort_keys=False, default_flow_style=False, allow_unicode=True,
    )


def render_secrets_env(secrets_out: dict[str, str]) -> str:
    """Render the .env.secrets file content."""
    lines = [
        "# Generated by deploy/init.py — DO NOT COMMIT.",
        "# This file is gitignored. Treat its contents as production secrets.",
        "",
    ]
    for key, value in secrets_out.items():
        # No escaping needed for the values we generate; user-pasted JSON
        # may need quoting. Wrap in single quotes if it contains spaces.
        if " " in value or '"' in value or "'" in value:
            # Use double quotes, escape internal double quotes.
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_wizard(p: Prompter) -> tuple[dict[str, Any], dict[str, str]]:
    secrets_out: dict[str, str] = {}

    cfg: dict[str, Any] = {}
    cfg["meta"] = collect_meta(p)
    env_label = cfg["meta"]["environment"]
    provider = collect_provider(p, env_label)   # drives storage/secrets defaults

    cfg["database"] = collect_database(p, secrets_out)
    cfg["redis"] = collect_redis(p)
    cfg["auth"] = collect_auth(p, secrets_out)
    cfg["firebase"] = collect_firebase(p, secrets_out)
    cfg["ai"] = collect_ai(p, secrets_out)
    cfg["server"] = collect_server(p, env_label)
    cfg["cron"] = collect_cron(p, secrets_out)

    # Infra backends (provider-aware), telemetry, edge — asked explicitly.
    cfg["storage"] = collect_storage(p, provider)
    cfg["secrets"] = collect_secrets_backend(p, provider)
    cfg["observability"] = collect_observability(p, env_label)
    cfg["edge"] = collect_edge(p, env_label)

    # Provider-specific target config — only the selected provider's block is
    # written; the others fall back to schema defaults.
    if provider == "gcp":
        cfg["gcp"] = collect_gcp(p)
    elif provider == "aws":
        cfg["aws"] = collect_aws(p)
    elif provider == "azure":
        cfg["azure"] = collect_azure(p)

    cfg["docker_local"] = {
        "database_mode": collect_docker_db_mode(p, secrets_out, provider),
        "backend_port": 8080, "frontend_port": 3000,
        "postgres_image": "postgres:16-alpine",
        "postgres_volume": f"{cfg['meta']['project_name']}_pgdata",
        "redis_image": "redis:7-alpine",
    }

    # Strong runtime data-plane passwords (compose interpolation) — only when we
    # run our own containers (local stack). Cloud-managed data uses the provider.
    if provider in ("docker-local", "vps") and \
            cfg["docker_local"]["database_mode"] == "local":
        for k in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "MINIO_ROOT_PASSWORD"):
            secrets_out.setdefault(k, gen_urlsafe(24))

    # Defaults for sections the wizard doesn't deep-dive (editable in config.yaml).
    cfg["payments"] = {
        "bange": {"enabled": False, "api_url": "", "merchant_id": "",
                  "api_key_secret": "", "webhook_secret_secret": ""},
        "ecobank": {"enabled": False, "api_url": "", "client_id": "",
                    "client_secret_secret": "", "webhook_secret_secret": "",
                    "primary_methods": ""},
        "mpgs": {"enabled": False, "api_url": "", "merchant_id": "",
                 "api_password_secret": "", "webhook_secret_secret": "",
                 "api_version": "85", "primary_methods": "card"},
    }
    cfg["smtp"] = {
        "host": "", "port": 587, "username": "", "password_secret": "",
        "use_tls": True, "from_email": "", "from_name": "Facil",
    }
    cfg["legal"] = {
        "privacy_version": "1.0.0", "privacy_last_updated": "2026-05-10",
        "terms_version": "1.0.0", "terms_last_updated": "2026-05-10",
        "cookies_version": "1.0.0", "cookies_last_updated": "2026-05-10",
    }
    cfg["features"] = {
        "scheduler_enabled": True, "rate_limit_enabled": True,
        "metrics_enabled": True, "structured_logging": True,
        "executive_tools": False, "llm_routing": False, "penalties": False,
    }
    cfg["env_overrides"] = {}

    return cfg, secrets_out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str, *, force: bool, label: str) -> int:
    if path.exists() and not force:
        print(
            f"ERROR: {label} already exists at {path}. "
            f"Use --force to overwrite.",
            file=sys.stderr,
        )
        return 3
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[OK] Wrote {label}: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config-out", type=Path, default=DEFAULT_CONFIG_OUT)
    parser.add_argument("--secrets-out", type=Path, default=DEFAULT_SECRETS_OUT)
    parser.add_argument("--non-interactive", action="store_true",
                        help="Read all answers from WIZ_* env vars + defaults.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing config.yaml / .env.secrets.")
    args = parser.parse_args(argv)

    if not args.non_interactive:
        print("Welcome to the Facil deployment wizard.")
        print("This will generate deploy/config.yaml and .env.secrets.")
        print("Press Ctrl+C at any time to abort.\n")

    p = Prompter(non_interactive=args.non_interactive)
    try:
        cfg, secrets_out = run_wizard(p)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 2

    # Validate the generated config against the Pydantic schema before writing.
    try:
        vc.DeployConfig.model_validate(cfg)
    except Exception as e:
        print(f"\nERROR: generated config does not validate:\n{e}", file=sys.stderr)
        return 1

    rc = write_file(
        args.config_out, render_config_yaml(cfg),
        force=args.force, label="deploy/config.yaml",
    )
    if rc != 0:
        return rc

    rc = write_file(
        args.secrets_out, render_secrets_env(secrets_out),
        force=args.force, label=".env.secrets",
    )
    if rc != 0:
        return rc

    if not args.non_interactive:
        print()
        print("=" * 60)
        print("Setup complete. Next steps:")
        print("=" * 60)
        print("  1. Review deploy/config.yaml (check the values are sane).")
        print("  2. Optionally edit .env.secrets to add Firebase/Sentry/etc.")
        print()
        print("  Then deploy:")
        print("    python deploy/deploy.py --provider=docker-local --action=apply")
        print("  or")
        print("    python deploy/deploy.py --provider=gcp --action=apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
