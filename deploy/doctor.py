#!/usr/bin/env python3
"""Deployment doctor — config coherence + (optional) live health.

Catches incoherent provider combinations the schema can't (e.g. self-hosted
OpenBao/MinIO on a serverless cloud) and surfaces scale/security guidance,
BEFORE you deploy. With ``--live`` it also checks the local data-plane
containers are up + healthy.

    python deploy/doctor.py --config=deploy/config.yaml            # static checks
    python deploy/doctor.py --config=deploy/config.yaml --provider=aws
    python deploy/doctor.py --config=deploy/config.yaml --live     # + container health

Exit codes
----------
0  No FAIL-level issue (WARN/INFO allowed). · 1  At least one FAIL. · 3  File error.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402

SERVERLESS = ("gcp", "aws", "azure")
_CLOUD_STORE = {"gcp": "gcs", "aws": "s3", "azure": "azure_blob"}


@dataclass
class Issue:
    level: str   # "ok" | "info" | "warn" | "fail"
    message: str


def check_coherence(cfg: vc.DeployConfig, provider: str) -> list[Issue]:
    """Static cross-field coherence checks (no network). Pure + testable."""
    out: list[Issue] = []
    serverless = provider in SERVERLESS

    # Self-hosted infra on a serverless cloud has nowhere to run.
    if serverless and cfg.secrets.provider == "openbao":
        out.append(Issue("warn", f"secrets=openbao (self-hosted) on '{provider}' — "
                          "OpenBao has no host on serverless; prefer the cloud secret manager"))
    if serverless and cfg.storage.provider == "minio":
        out.append(Issue("warn", f"storage=minio (self-hosted) on '{provider}' — "
                          f"prefer {_CLOUD_STORE.get(provider, 'the cloud object store')}"))

    # Managed DB but the local stack also spins its own postgres (contradiction).
    if cfg.database.provider != "local" and cfg.docker_local.database_mode == "local":
        out.append(Issue("warn", f"database.provider={cfg.database.provider} but "
                          "docker_local.database_mode=local — a local postgres will "
                          "be started AND unused; set database_mode=external"))

    # LLM present (schema already enforces one path; defensive).
    if (not cfg.ai.providers and not cfg.ai.gemini_api_key_secret
            and not cfg.ai.google_cloud_project):
        out.append(Issue("warn", "no LLM configured (ai.providers / gemini / vertex all empty)"))
    elif cfg.ai.providers:
        out.append(Issue("info", f"LLM routing: {len(cfg.ai.providers)} provider(s), "
                          f"roles {sorted(cfg.ai.routing)}"))

    # Email / payment sanity.
    if cfg.email.provider != "disabled" and not cfg.email.from_email:
        out.append(Issue("warn", f"email.provider={cfg.email.provider} but from_email is empty"))
    if cfg.payments.provider == "stripe" and not cfg.payments.stripe.enabled:
        out.append(Issue("warn", "payments.provider=stripe but stripe.enabled is false"))

    # Auth scale guidance (not a restriction — a heads-up).
    if "keycloak_oidc" in cfg.auth.citizen_methods:
        out.append(Issue("warn", "citizen auth uses keycloak — a self-hosted Keycloak for "
                          "millions of citizens has SPOF/scale cost; a managed IdP often scales better"))

    # Edge in production without TLS.
    if cfg.meta.environment == "production" and cfg.edge.proxy != "none" \
            and cfg.edge.tls_mode == "none":
        out.append(Issue("warn", "production edge proxy with tls_mode=none — enable internal/acme"))

    if not any(i.level == "fail" for i in out):
        out.insert(0, Issue("ok", f"config coherent for provider '{provider}'"))
    return out


def check_live(cfg: vc.DeployConfig) -> list[Issue]:
    """Best-effort: are the local data-plane containers up + healthy?"""
    out: list[Issue] = []
    try:
        sys.path.insert(0, str(DEPLOY_DIR / "providers"))
        from bootstrap import docker_helpers as dh  # noqa: E402
    except Exception as e:  # bootstrap not importable
        return [Issue("warn", f"live checks skipped (docker helpers unavailable: {e})")]

    services = ["postgres", "redis"]
    if cfg.storage.provider == "minio":
        services.append("minio")
    if cfg.secrets.provider == "openbao":
        services.append("openbao")
    for svc in services:
        try:
            info = dh.find_container(svc)
        except Exception as e:
            out.append(Issue("warn", f"{svc}: docker query failed ({e})"))
            continue
        if info is None or not info.running:
            out.append(Issue("fail", f"{svc}: not running"))
        elif info.health in (None, "healthy"):
            out.append(Issue("ok", f"{svc}: running"
                             + (f" ({info.health})" if info.health else "")))
        else:
            out.append(Issue("warn", f"{svc}: {info.health}"))
    return out


_MARK = {"ok": "[OK]  ", "info": "[INFO]", "warn": "[WARN]", "fail": "[FAIL]"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEPLOY_DIR / "config.yaml")
    parser.add_argument("--provider", default="docker-local")
    parser.add_argument("--live", action="store_true",
                        help="Also check local data-plane container health.")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 3
    try:
        cfg = vc.DeployConfig.model_validate(vc.load_yaml(args.config))
    except Exception as e:
        print(f"ERROR: config invalid:\n{e}", file=sys.stderr)
        return 1

    issues = check_coherence(cfg, args.provider)
    if args.live:
        issues += check_live(cfg)

    print("=== deploy doctor ===")
    for i in issues:
        print(f"  {_MARK[i.level]} {i.message}")
    fails = sum(1 for i in issues if i.level == "fail")
    warns = sum(1 for i in issues if i.level == "warn")
    print(f"\n{fails} fail - {warns} warn")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
