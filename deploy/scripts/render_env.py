#!/usr/bin/env python3
"""Render backend / frontend .env files from deploy/config.yaml.

Phase A.5.2 of DEPLOY_SYSTEM_PLAN.

Inputs:
  - deploy/config.yaml (or --config <path>)
  - deploy/templates/env.{backend,web}.template

Outputs:
  - <target>/.env.deploy.gen   (rendered file, non-secret values only)
  - deploy/.secrets-manifest.json (mapping ENV_VAR_NAME -> secret_name)

The provider scripts (gcp.sh, docker-local.sh) consume the rendered .env
and the secrets manifest to bind secrets at runtime.

Usage
-----
    python deploy/scripts/render_env.py --target=backend
    python deploy/scripts/render_env.py --target=web --config=deploy/config.yaml
    python deploy/scripts/render_env.py --target=backend --output=/tmp/test.env
    python deploy/scripts/render_env.py --target=both --dry-run

Exit codes
----------
0  Render OK.
1  Validation/render error (missing field, unknown placeholder, etc.).
2  YAML parse error.
3  File not found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Reuse the schema + helpers from validate_config.py (sibling module).
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

DEPLOY_DIR = SCRIPTS_DIR.parent
TEMPLATES_DIR = DEPLOY_DIR / "templates"
DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"
DEFAULT_MANIFEST = DEPLOY_DIR / ".secrets-manifest.json"

# Placeholder regex: {{ path.to.value }}
# Supports dotted paths up to 5 levels deep, optional spaces inside braces.
PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")

# ---------------------------------------------------------------------------
# Mapping: dotted config path -> ENV_VAR name (for secrets manifest)
# ---------------------------------------------------------------------------
# Each entry maps a config field that holds a *secret name* to the backend
# env var that must receive the *secret value* at runtime. The provider
# script (gcp.sh / docker-local.sh) reads this manifest to wire the
# bindings.
SECRET_REF_TO_ENV_VAR: dict[str, str] = {
    # --- Database / cache ---
    "database.url_secret":                    "DATABASE_URL",
    "database.password_secret":               "DATABASE_PASSWORD",
    "database.supabase_url_secret":           "SUPABASE_URL",
    "database.supabase_anon_key_secret":      "SUPABASE_ANON_KEY",
    "redis.url_secret":                       "REDIS_URL",
    # --- Auth / signing ---
    "auth.jwt_secret_name":                   "JWT_SECRET_KEY",
    "auth.app_secret_name":                   "SECRET_KEY",
    "auth.totp_encryption_secret":            "TOTP_ENCRYPTION_KEY",
    "auth.receipt_verification_secret":       "RECEIPT_VERIFICATION_SECRET",
    # --- AI ---
    "ai.gemini_api_key_secret":               "GEMINI_API_KEY",
    # --- Firebase (env-dependent: dev or pro) ---
    "firebase.service_account_dev_secret":    "FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV",
    "firebase.service_account_pro_secret":    "FIREBASE_SERVICE_ACCOUNT_TAXASGE_PRO",
    # --- Payments ---
    "payments.bange.api_key_secret":          "BANGE_API_KEY",
    "payments.bange.webhook_secret_secret":   "BANGE_WEBHOOK_SECRET",
    "payments.ecobank.client_secret_secret":  "ECOBANK_CLIENT_SECRET",
    "payments.ecobank.webhook_secret_secret": "ECOBANK_WEBHOOK_SECRET",
    "payments.mpgs.api_password_secret":      "MPGS_API_PASSWORD",
    "payments.mpgs.webhook_secret_secret":    "MPGS_WEBHOOK_SECRET",
    # --- Email ---
    "smtp.password_secret":                   "SMTP_PASSWORD",
    # --- Cron / scheduling ---
    "cron.secret_name":                       "CRON_SECRET",
    # --- Observability ---
    "observability.sentry_dsn_backend_secret":  "SENTRY_DSN",
    "observability.sentry_auth_token_secret":   "SENTRY_AUTH_TOKEN",  # build-time, harmless at runtime
    "observability.grafana_token_secret":       "GRAFANA_SA_TOKEN",
    "observability.maxmind_license_key_secret": "MAXMIND_LICENSE_KEY",
}

# Frontend build-time secret bindings (NEXT_PUBLIC_* values that come from
# Secret Manager at build time, baked into the client bundle).
FRONTEND_SECRET_REF_TO_ENV_VAR: dict[str, str] = {
    "observability.sentry_dsn_web_secret":     "NEXT_PUBLIC_SENTRY_DSN",
    "observability.logrocket_app_id_secret":   "NEXT_PUBLIC_LOGROCKET_APP_ID",
    "observability.sentry_auth_token_secret":  "SENTRY_AUTH_TOKEN",  # build-only
}

# Frontend build-time secret (only one).


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def lookup_dotted(cfg: vc.DeployConfig, dotted: str) -> Any:
    """Walk the cfg model along a dotted path. Returns None if any segment misses."""
    obj: Any = cfg
    for part in dotted.split("."):
        if obj is None:
            return None
        if hasattr(obj, part):
            obj = getattr(obj, part)
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def coerce_for_env(value: Any) -> str:
    """Render a Python value as it should appear in a .env file."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_template(
    template_text: str,
    cfg: vc.DeployConfig,
    *,
    extra: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """Replace {{path.to.value}} placeholders in template_text.

    Returns (rendered_text, missing_placeholders_list).
    `missing_placeholders_list` contains any placeholder whose path could
    not be resolved — empty list = success.
    """
    missing: list[str] = []
    extras = extra or {}

    def replace(match: re.Match[str]) -> str:
        path = match.group(1)
        if path.startswith("__") and path in extras:
            return extras[path]
        value = lookup_dotted(cfg, path)
        if value is None and path not in extras:
            missing.append(path)
            return match.group(0)  # leave placeholder visible
        return coerce_for_env(value)

    rendered = PLACEHOLDER_RE.sub(replace, template_text)
    return rendered, missing


def build_env_overrides_block(cfg: vc.DeployConfig) -> str:
    """Render env_overrides dict into KEY=value lines."""
    if not cfg.env_overrides:
        return "# (no env_overrides defined in config.yaml)"
    lines = []
    for key, value in sorted(cfg.env_overrides.items()):
        lines.append(f"{key}={coerce_for_env(value)}")
    return "\n".join(lines)


def build_secrets_manifest(
    cfg: vc.DeployConfig,
    mapping: dict[str, str] = None,
) -> dict[str, str]:
    """Return {ENV_VAR_NAME: secret_name} for every config secret ref that
    has both a non-empty value and a known mapping."""
    mapping = mapping or SECRET_REF_TO_ENV_VAR
    manifest: dict[str, str] = {}
    for cfg_path, env_var in mapping.items():
        secret_name = lookup_dotted(cfg, cfg_path)
        if isinstance(secret_name, str) and secret_name:
            manifest[env_var] = secret_name
    return manifest


# ---------------------------------------------------------------------------
# Per-target glue
# ---------------------------------------------------------------------------

def render_backend(cfg: vc.DeployConfig, template_path: Path) -> tuple[str, list[str]]:
    template_text = template_path.read_text(encoding="utf-8")
    overrides_block = build_env_overrides_block(cfg)
    return render_template(
        template_text,
        cfg,
        extra={"__env_overrides__": overrides_block},
    )


def render_web(cfg: vc.DeployConfig, template_path: Path) -> tuple[str, list[str]]:
    template_text = template_path.read_text(encoding="utf-8")
    return render_template(template_text, cfg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config.yaml (default: {DEFAULT_CONFIG.relative_to(DEPLOY_DIR.parent)})",
    )
    parser.add_argument(
        "--target",
        choices=["backend", "web", "both"],
        required=True,
        help="Which target's .env to render.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output path (default: <target>/.env.deploy.gen).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Output path for the secrets manifest JSON (default: {DEFAULT_MANIFEST.relative_to(DEPLOY_DIR.parent)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print to stdout instead of writing files.",
    )
    args = parser.parse_args(argv)

    raw = vc.load_yaml(args.config)
    try:
        cfg = vc.DeployConfig.model_validate(raw)
    except Exception as e:
        print(f"ERROR: config validation failed:\n{e}", file=sys.stderr)
        return 1

    targets = ["backend", "web"] if args.target == "both" else [args.target]
    rc = 0

    for tgt in targets:
        template_path = TEMPLATES_DIR / f"env.{tgt}.template"
        if not template_path.exists():
            print(f"ERROR: template missing: {template_path}", file=sys.stderr)
            return 3

        if tgt == "backend":
            text, missing = render_backend(cfg, template_path)
        else:
            text, missing = render_web(cfg, template_path)

        if missing:
            print(
                f"ERROR: {tgt}: {len(missing)} unresolved placeholder(s): {missing}",
                file=sys.stderr,
            )
            rc = 1
            continue

        if args.dry_run:
            print(f"# ===== rendered {tgt} =====")
            print(text)
            continue

        if args.output and args.target != "both":
            out_path = args.output
        else:
            # Default: write next to the package source.
            base = DEPLOY_DIR.parent / "packages" / ("backend" if tgt == "backend" else "web")
            out_path = base / ".env.deploy.gen"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"[OK] {tgt}: wrote {out_path}")

    # Always emit the secrets manifest (or print on dry-run).
    manifest = build_secrets_manifest(cfg)
    if args.dry_run:
        print("# ===== secrets manifest =====")
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"[OK] secrets manifest: wrote {args.manifest} ({len(manifest)} entries)")

    return rc


if __name__ == "__main__":
    sys.exit(main())
