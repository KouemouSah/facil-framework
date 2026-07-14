#!/usr/bin/env python3
"""docker-local provider — Phase A.5.5 of DEPLOY_SYSTEM_PLAN.

Generates a docker-compose.local.yml at the repo root and brings up:

  - Postgres                   (with persistent named volume)
  - Redis
  - db-init (one-shot)         runs init_database.py to create schema +
                               apply baseline + seeds. Backend depends on
                               its successful completion.
  - Backend (FastAPI/uvicorn)  starts only after db-init finishes
  - Frontend (Next.js)         starts after backend is healthy

Secrets are NOT bound through Cloud Secret Manager here. Instead, copy
deploy/.env.secrets.example to .env.secrets at the repo root and fill in
the required values. The compose file maps that file as env_file for
backend + db-init.

Usage
-----
    # Validate prereqs (docker installed, compose available).
    python deploy/providers/docker_local.py --config=deploy/config.yaml --validate

    # Show the generated docker-compose.local.yml content.
    python deploy/providers/docker_local.py --config=deploy/config.yaml --plan

    # Write docker-compose.local.yml + start the stack.
    python deploy/providers/docker_local.py --config=deploy/config.yaml --apply

    # Stop and remove containers (volumes preserved unless --volumes).
    python deploy/providers/docker_local.py --config=deploy/config.yaml --down
    python deploy/providers/docker_local.py --config=deploy/config.yaml --down --volumes

    # Tail logs of all services.
    python deploy/providers/docker_local.py --config=deploy/config.yaml --logs

    # Restart all services without rebuilding.
    python deploy/providers/docker_local.py --config=deploy/config.yaml --restart

Exit codes
----------
0  Success.
1  Validation error (docker missing, secrets file missing in --apply mode).
2  Subprocess error (docker compose up failed).
3  YAML / file error.
4  User aborted at a confirmation prompt.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = PROVIDERS_DIR.parent
SCRIPTS_DIR = DEPLOY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_config as vc  # noqa: E402
import ensure_secrets as es  # noqa: E402

REPO_ROOT = DEPLOY_DIR.parent
DEFAULT_CONFIG = DEPLOY_DIR / "config.yaml"
COMPOSE_FILE = REPO_ROOT / "docker-compose.local.yml"
CADDYFILE = REPO_ROOT / "Caddyfile"  # generated; mounted by the `edge` profile
STATE_FILE = DEPLOY_DIR / ".bootstrap-state.json"  # bootstrap provisioning state
SECRETS_FILE = REPO_ROOT / ".env.secrets"  # local-only, gitignored
SECRETS_EXAMPLE = DEPLOY_DIR / ".env.secrets.example"
BACKUPS_DIR = REPO_ROOT / "backups"  # local-only, gitignored (D1 — pre-update dump)


# ---------------------------------------------------------------------------
# Prereq checks
# ---------------------------------------------------------------------------

def find_docker() -> str | None:
    return shutil.which("docker")


def docker_compose_available() -> bool:
    """True if `docker compose` (v2 plugin) works."""
    docker = find_docker()
    if not docker:
        return False
    proc = subprocess.run(
        [docker, "compose", "version"],
        capture_output=True, text=True, check=False,
    )
    return proc.returncode == 0


def stack_running() -> bool:
    """True if the local stack already has running containers.

    Used to detect conflicts before --apply (which would otherwise hit
    'port already allocated' errors).
    """
    docker = find_docker()
    if not docker or not COMPOSE_FILE.exists():
        return False
    proc = subprocess.run(
        [docker, "compose", "-f", str(COMPOSE_FILE), "ps", "-q"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


# ---------------------------------------------------------------------------
# D1 — Postgres backup before an update (tier lite / compose, best-effort).
#
# The spec explicitly treats the compose tier as 2nd-class (best-effort, no
# rolling update). But an on-prem customer WITHOUT ops staff is exactly who
# ends up running this tier — and losing their data on an update is just as
# bad as it would be on k3s. `--apply` IS this tier's update path (there is
# no separate `--update` command: re-running `--apply` is how an operator
# ships a new image/migration, the same "idempotent re-invoke" shape as
# `helm upgrade --install`). This mirrors the k3s pre-upgrade backup Job
# (infra/helm/facil/templates/backup-job.yaml): same fail-closed contract
# (an empty dump is WORSE than no dump — false confidence), gated the same
# way ("nothing to protect on a first install").
# ---------------------------------------------------------------------------

def backup_postgres(cfg: vc.DeployConfig, *, dest_dir: Path = BACKUPS_DIR,
                    compose_file: Path = COMPOSE_FILE) -> tuple[bool, str]:
    """Dumps Postgres via `docker compose exec` BEFORE the app tier (db-init's
    Alembic migration) starts. Returns (ok, message); `ok=False` means the
    caller MUST abort the update — never proceed with a failed/empty backup.

    No PGPASSWORD anywhere (not env, not argv): `pg_dump` here connects via
    the container's local UNIX socket (no `-h` given), which the official
    Postgres image always accepts as `trust` regardless of POSTGRES_PASSWORD
    — the EXACT same assumption this file's own Postgres healthcheck already
    relies on (`pg_isready -U {project}`, also no `-h`). So there is no
    secret to leak into argv here (CWE-214 is moot, not just mitigated).
    """
    docker = find_docker()
    if not docker:
        return False, "docker introuvable dans le PATH — sauvegarde impossible."

    project = cfg.meta.project_name
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / ts
    dest.mkdir(parents=True, exist_ok=True)
    dump_path = dest / "postgres.dump"

    proc = subprocess.run(
        [docker, "compose", "-f", str(compose_file), "exec", "-T", "postgres",
         "pg_dump", "-U", project, "-Fc", project],
        capture_output=True, check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        return False, f"pg_dump a echoue (code {proc.returncode}): {stderr or '(aucune sortie)'}"

    dump_path.write_bytes(proc.stdout or b"")
    # FAIL-CLOSED (mirrors backup-job.yaml): an empty dump is WORSE than no
    # dump at all (false confidence). A freshly-created database still
    # produces a SMALL dump (custom-format header + empty schema) but never
    # an empty one.
    if dump_path.stat().st_size == 0:
        dump_path.unlink(missing_ok=True)
        return False, "le dump Postgres est vide — update avorte AVANT db-init."

    return True, f"sauvegarde Postgres -> {dump_path}"


# ---------------------------------------------------------------------------
# Compose file generator
# ---------------------------------------------------------------------------

def generate_compose(cfg: vc.DeployConfig) -> str:
    """Build a docker-compose.yml string from the deploy config.

    Two database topologies depending on cfg.docker_local.database_mode:

      - "local"    (default): generates a postgres container with persistent
                              volume + healthcheck. Backend + db-init point
                              at it via the in-network hostname `postgres`.
      - "external" : NO postgres container generated. Operator's
                              .env.secrets must contain DATABASE_URL pointing
                              at the external Postgres (Supabase, RDS, Cloud
                              SQL via proxy, Neon, Railway, etc.). Backend +
                              db-init use that URL directly. Useful when:
                                · You already pay for managed Postgres
                                · You want zero-install local stack (no pg
                                  data in your Docker volumes)
                                · You demo with seeded production-like data
                                  in Supabase

    No `version:` field — Compose v2 ignores it (and warns when present).
    """
    backend_port = cfg.docker_local.backend_port
    # Module Loader contract (Phase A.5): the enabled list -> MODULES_ENABLED env
    # read by the backend at boot. Not-yet-ported modules are skipped (warned).
    modules_csv = ",".join(cfg.modules.enabled)
    frontend_port = cfg.docker_local.frontend_port
    pg_image = cfg.docker_local.postgres_image
    pg_volume = cfg.docker_local.postgres_volume
    redis_image = cfg.docker_local.redis_image
    project = cfg.meta.project_name
    env_label = cfg.meta.environment
    use_external_db = cfg.docker_local.database_mode == "external"

    # Password is interpolated by compose at up time from .env.secrets
    # (passed as env_extra). The generated YAML keeps the ${...} placeholder.
    redis_url = "redis://:${REDIS_PASSWORD}@redis:6379/0"
    public_api_url = f"http://localhost:{backend_port}"
    internal_api_url = f"http://backend:{backend_port}"

    # ---- Block: postgres service (only in local mode) ----
    if use_external_db:
        postgres_block = (
            "  # ---------------------------------------------------------------------\n"
            "  # Postgres: SKIPPED — database_mode=external. Backend + db-init use\n"
            "  # the DATABASE_URL provided in .env.secrets (Supabase, RDS, etc.).\n"
            "  # ---------------------------------------------------------------------"
        )
        volumes_block = "# (no named volumes — external DB is managed elsewhere)"
        # In external mode, DATABASE_URL comes from .env.secrets (no inline value).
        # We do NOT set DATABASE_URL in the `environment:` block so .env.secrets'
        # value wins.
        db_url_line = "      # DATABASE_URL: provided by .env.secrets (external mode)"
        backend_db_url_line = db_url_line
        db_init_depends = "    # No postgres dependency in external mode."
        backend_depends_postgres = "      # No postgres dependency in external mode."
    else:
        db_url = (
            f"postgresql://{project}:${{POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required — run via docker_local --apply or export it}}"
            f"@postgres:5432/{project}"
        )
        postgres_block = f"""  # ---------------------------------------------------------------------
  # Postgres — persistent volume, healthcheck-gated for dependents.
  # ---------------------------------------------------------------------
  postgres:
    image: {pg_image}
    environment:
      POSTGRES_DB: {project}
      POSTGRES_USER: {project}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required — run via docker_local --apply or export it}}
    volumes:
      - {pg_volume}:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "{project}"]
      interval: 5s
      timeout: 3s
      retries: 10"""
        volumes_block = f"  {pg_volume}:"
        db_url_line = f"      DATABASE_URL: {db_url}"
        # The backend connects as the least-privilege facil_app role; that URL is
        # rendered post-bootstrap into packages/backend/.env.deploy.gen.
        backend_db_url_line = (
            "      # DATABASE_URL: from packages/backend/.env.deploy.gen "
            "(facil_app, least-privilege)")
        db_init_depends = (
            "    depends_on:\n"
            "      postgres:\n"
            "        condition: service_healthy"
        )
        backend_depends_postgres = (
            "      postgres:\n"
            "        condition: service_healthy"
        )

    # ---- Block: MinIO object storage (ADR-0005) — emitted when storage.provider=minio ----
    emit_minio = cfg.storage.provider == "minio"
    if emit_minio:
        m = cfg.storage.minio
        minio_block = f"""  # ---------------------------------------------------------------------
  # MinIO — S3-compatible object storage (ADR-0005, souverain default).
  # Console http://localhost:{m.console_port}  ·  API http://localhost:{m.api_port}
  # ---------------------------------------------------------------------
  minio:
    image: {m.image}
    command: server /data --console-address ":{m.console_port}"
    environment:
      MINIO_ROOT_USER: {m.root_user}
      MINIO_ROOT_PASSWORD: ${{MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required — run via docker_local --apply or export it}}
    volumes:
      - {m.volume}:/data
    ports:
      - "{m.api_port}:9000"
      - "{m.console_port}:{m.console_port}"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 3s
      retries: 10

"""
    else:
        minio_block = ""

    # ---- OpenBao secrets+PKI (ADR-0003/0006, P7): emitted when secrets.provider=openbao
    # DEV MODE only for now: in-memory, auto-unsealed, NON-PRODUCTION. Container
    # always listens on 8200; host port is configurable. Prod unseal = P7.
    emit_openbao = cfg.secrets.provider == "openbao"
    if emit_openbao:
        o = cfg.secrets.openbao
        openbao_block = f"""  # ---------------------------------------------------------------------
  # OpenBao — secrets + PKI engine (ADR-0003/0006, P7). DEV MODE:
  # in-memory, auto-unsealed, NON-PRODUCTION. Prod unseal (SOPS+age) = P7.
  # ---------------------------------------------------------------------
  openbao:
    image: {o.image}
    command: ["server", "-dev", "-dev-listen-address=0.0.0.0:8200"]
    environment:
      BAO_ADDR: http://127.0.0.1:8200
      BAO_DEV_ROOT_TOKEN_ID: ${{OPENBAO_DEV_ROOT_TOKEN:?OPENBAO_DEV_ROOT_TOKEN is required — run via docker_local --apply (ensure_secrets) or export it}}
    cap_add:
      - IPC_LOCK
    ports:
      - "{o.port}:8200"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "bao", "status"]
      interval: 5s
      timeout: 3s
      retries: 10

"""
    else:
        openbao_block = ""

    # ---- Named volumes (recomputed): pg (local) + minio + openbao (prod only; dev=in-memory) ----
    vol_names: list[str] = []
    if not use_external_db:
        vol_names.append(pg_volume)
    if emit_minio:
        vol_names.append(cfg.storage.minio.volume)
    if emit_openbao and not cfg.secrets.openbao.dev_mode:
        vol_names.append(cfg.secrets.openbao.volume)
    # Scaffolded profile-gated services (always declared so the skeleton is
    # complete; created by Docker only when their profile is actually run).
    # Keycloak runs dev mode (in-memory H2) so it needs no named volume.
    vol_names.extend(["facil_caddy_data", "facil_caddy_config", "facil_otel_lgtm",
                      "facil_ollama"])
    volumes_block = (
        "\n".join(f"  {v}:" for v in vol_names)
        if vol_names else "# (no named volumes)"
    )

    # ---- Scaffolded, profile-gated services (OFF by default) ----
    # Emitted ALWAYS so the skeleton exists & is documented, but they only
    # start when their Compose profile is explicitly selected. Activation is a
    # profile switch, not a regeneration:
    #   docker compose --profile edge up           Caddy reverse-proxy (P3/P8/P12)
    #   docker compose --profile auth up            Keycloak — agents auth (P11)
    #   docker compose --profile observability up    Grafana otel-lgtm (P14 palier A)
    #   docker compose --profile ai up              Ollama — sovereign LLM (D2/P1)
    #   docker compose --profile mail up            smtp4dev — dev SMTP sink (D2/P2)
    e = cfg.edge
    kc = cfg.auth.keycloak
    obs = cfg.observability
    caddy_https_publish = (
        f'\n      - "{e.https_port}:443"' if e.tls_mode != "none" else ""
    )
    scaffold_block = f"""
  # ---------------------------------------------------------------------
  # Caddy — reverse-proxy (SCAFFOLD, profile `edge`, OFF by default).
  # Single origin http://localhost:{e.http_port} → frontend + /api→backend (no CORS).
  # Prod TLS/PKI (ACME / OpenBao internal CA) + per-surface routing = P8/P12.
  #   docker compose --profile edge up
  # ---------------------------------------------------------------------
  caddy:
    image: {e.image}
    profiles: ["edge"]
    ports:
      - "{e.http_port}:80"{caddy_https_publish}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - facil_caddy_data:/data
      - facil_caddy_config:/config
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started

  # ---------------------------------------------------------------------
  # Keycloak — agents auth (SCAFFOLD, profile `auth`, OFF by default).
  # DEV MODE: `start-dev` (in-memory H2, NON-PROD). Realm + AD/LDAP
  # federation + client config + prod Postgres = P11 (late-binding).
  #   docker compose --profile auth up   →   http://localhost:{kc.http_port}
  # ---------------------------------------------------------------------
  keycloak:
    image: {kc.image}
    profiles: ["auth"]
    command: ["start-dev"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: {kc.admin_user}
      KC_BOOTSTRAP_ADMIN_PASSWORD: ${{KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD is required — run via docker_local --apply (ensure_secrets) or export it}}
    ports:
      - "{kc.http_port}:8080"
    restart: unless-stopped

  # ---------------------------------------------------------------------
  # otel-lgtm — Grafana + Prometheus + Tempo + Loki, all-in-one
  # (SCAFFOLD, profile `observability`, OFF by default — P14 palier A).
  # Sovereign self-hosted telemetry: backend emits OTLP here when
  # observability.mode=local (nothing leaves the network).
  #   docker compose --profile observability up   →   Grafana http://localhost:{obs.grafana_port}
  # ---------------------------------------------------------------------
  otel-lgtm:
    image: {obs.otel_lgtm_image}
    profiles: ["observability"]
    ports:
      - "{obs.grafana_port}:3000"
      - "{obs.otlp_grpc_port}:4317"
      - "{obs.otlp_http_port}:4318"
    volumes:
      - facil_otel_lgtm:/data
    restart: unless-stopped

  # ---------------------------------------------------------------------
  # Ollama — sovereign local LLM inference (SCAFFOLD, profile `ai`, OFF by
  # default — D2/P1, ADR-0002). Weights live in the `facil_ollama` volume,
  # NEVER baked into an image. The backend reaches it at http://ollama:11434
  # (OLLAMA_ENDPOINT, wired below). Prod-at-scale (100+ agents) = vLLM+GPU
  # behind the same openai_compat provider. Pull a model after `up`:
  #   docker compose --profile ai up -d ollama
  #   docker compose exec ollama ollama pull gemma4:e4b
  # (bootstrap-time auto-pull = follow-up, like the MinIO/OpenBao provisioning).
  # ---------------------------------------------------------------------
  ollama:
    image: ollama/ollama:latest
    profiles: ["ai"]
    ports:
      - "11434:11434"
    volumes:
      - facil_ollama:/root/.ollama
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ---------------------------------------------------------------------
  # smtp4dev — dev SMTP sink + web inbox (SCAFFOLD, profile `mail`, OFF by
  # default — D2/P2). Captures all outbound mail locally so SMTPEmailProvider
  # is live-testable without a real relay. NON-PROD (no auth, in-memory).
  # Backend reaches it at smtp4dev:25 (SMTP_HOST/SMTP_PORT, wired below);
  # browse the captured mail at http://localhost:5000.
  #   docker compose --profile mail up -d smtp4dev
  # ---------------------------------------------------------------------
  smtp4dev:
    image: rnwood/smtp4dev:v3
    profiles: ["mail"]
    ports:
      - "5000:80"
      - "2525:25"
    restart: unless-stopped
"""

    return f"""# Generated by deploy/providers/docker_local.py — DO NOT EDIT MANUALLY.
# Regenerate by editing deploy/config.yaml then running the provider with --apply.
# database_mode: {cfg.docker_local.database_mode}

services:
{postgres_block}

  # ---------------------------------------------------------------------
  # Redis — for cache, rate limit, idempotency.
  # ---------------------------------------------------------------------
  redis:
    image: {redis_image}
    command: ["redis-server", "--requirepass", "${{REDIS_PASSWORD:?REDIS_PASSWORD is required — run via docker_local --apply or export it}}"]
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${{REDIS_PASSWORD:?REDIS_PASSWORD is required — run via docker_local --apply or export it}}", "--no-auth-warning", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

{minio_block}{openbao_block}  # ---------------------------------------------------------------------
  # db-init — one-shot bootstrap. Reuses the backend image (same build
  # context) and runs init_database.py in hybrid mode:
  #   - empty DB + baseline.sql present -> applies baseline + seeds (~30s)
  #   - existing DB                       -> applies pending migrations + seeds
  # Backend container does NOT start until this exits with code 0.
  # ---------------------------------------------------------------------
  db-init:
    build:
      context: ./packages/backend
    env_file:
      - ./.env.secrets
    environment:
{db_url_line}
      ENVIRONMENT: {env_label}
      APPLIED_BY: docker-local-init
    command: ["alembic", "upgrade", "head"]
{db_init_depends}
    restart: "no"

  # ---------------------------------------------------------------------
  # Backend — FastAPI / uvicorn. Schema is guaranteed to be ready
  # (db-init completed) before this container starts.
  # ---------------------------------------------------------------------
  backend:
    build:
      context: ./packages/backend
    env_file:
      - ./.env.secrets
      - ./packages/backend/.env.deploy.gen
    environment:
{backend_db_url_line}
      REDIS_URL: {redis_url}
      ENVIRONMENT: {env_label}
      PORT: "{backend_port}"
      OLLAMA_ENDPOINT: http://ollama:11434
      SMTP_HOST: smtp4dev
      SMTP_PORT: "25"
      MODULES_ENABLED: "{modules_csv}"
    ports:
      - "{backend_port}:{backend_port}"
    restart: unless-stopped
    healthcheck:
      test:
        - CMD-SHELL
        - python -c "import urllib.request; urllib.request.urlopen('http://localhost:{backend_port}/health', timeout=3)"
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    depends_on:
{backend_depends_postgres}
      redis:
        condition: service_healthy
      db-init:
        condition: service_completed_successfully

  # ---------------------------------------------------------------------
  # Frontend — Next.js. DEFAULT service of the stack (the facil_framework group
  # mirrors production). Built LOCALLY from source, exactly like the backend —
  # zero registry / login needed for local dev. The prod/VPS path instead PULLS
  # the CI-built image (release-images.yml -> GHCR); to mirror that locally (e.g.
  # if the local Next build is too heavy) use tools/refresh-local.sh. Frontend
  # hot-reload dev = `npm run dev` on the host (a separate tool).
  # ---------------------------------------------------------------------
  frontend:
    build:
      context: ./packages/web
      args:
        NEXT_PUBLIC_API_URL: {public_api_url}
        NEXT_PUBLIC_BUILD_VERSION: {cfg.meta.version}
        NEXT_PUBLIC_ENVIRONMENT: {env_label}
        # Build-time SSO flag (client bundle). The apply sets it to 1 when Keycloak
        # is enabled; otherwise the compose default keeps the button hidden.
        NEXT_PUBLIC_OIDC_ENABLED: ${{NEXT_PUBLIC_OIDC_ENABLED:-0}}
    env_file:
      - ./packages/web/.env.deploy.gen
    environment:
      INTERNAL_API_URL: {internal_api_url}
    ports:
      - "{frontend_port}:3000"
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
{scaffold_block}
volumes:
{volumes_block}
"""


def generate_caddyfile(cfg: vc.DeployConfig) -> str:
    """Minimal dev Caddyfile for the `edge` profile (SCAFFOLD; P8/P12 harden it).

    Single origin: everything is reverse-proxied to the frontend, except
    `/api/*` which goes to the backend — this removes CORS in local dev.

    `tls_mode`:
      - none     : plain HTTP on :80 (auto_https off) — default dev.
      - internal : Caddy's local CA (`tls internal`) — P8 replaces this CA with
                   the OpenBao PKI issuer; the routing block is unchanged.
      - acme/custom : production paths, configured in P8 (domains required).
    """
    e = cfg.edge
    backend_port = cfg.docker_local.backend_port
    routes = (
        "\thandle /api/* {\n"
        f"\t\treverse_proxy backend:{backend_port}\n"
        "\t}\n"
        "\thandle {\n"
        "\t\treverse_proxy frontend:3000\n"
        "\t}\n"
    )
    if e.tls_mode == "none":
        return f"{{\n\tauto_https off\n}}\n\n:80 {{\n{routes}}}\n"
    host = e.domain_frontend or "localhost"
    tls_line = "\ttls internal\n" if e.tls_mode == "internal" else ""
    return f"{host} {{\n{tls_line}{routes}}}\n"


# ---------------------------------------------------------------------------
# Compose subcommand wrappers
# ---------------------------------------------------------------------------

def compose_cmd(*args: str) -> list[str]:
    """Build `docker compose -f <file> <args...>` invocation."""
    docker = find_docker()
    if not docker:
        raise RuntimeError("docker not found on PATH")
    return [docker, "compose", "-f", str(COMPOSE_FILE), *args]


def run_compose(args: list[str], *, env_extra: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    # Enable BuildKit + Compose CLI build for faster, cached builds.
    env.setdefault("DOCKER_BUILDKIT", "1")
    env.setdefault("COMPOSE_DOCKER_CLI_BUILD", "1")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(args, cwd=REPO_ROOT, env=env, check=False)
    return proc.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true",
                      help="Check prereqs (docker, compose v2). No mutation.")
    mode.add_argument("--plan", action="store_true",
                      help="Print the generated docker-compose file. No mutation.")
    mode.add_argument("--apply", action="store_true",
                      help="Write compose file + bring the stack up.")
    mode.add_argument("--down", action="store_true",
                      help="Stop and remove containers. Preserves volumes.")
    mode.add_argument("--logs", action="store_true",
                      help="Tail logs of all services (Ctrl+C to stop).")
    mode.add_argument("--restart", action="store_true",
                      help="Restart services without rebuilding images.")
    parser.add_argument("--volumes", action="store_true",
                        help="With --down: also remove the postgres volume "
                             "(WIPES the local DB).")
    parser.add_argument("--yes", action="store_true",
                        help="Skip interactive confirmations.")
    parser.add_argument("--no-bootstrap", action="store_true",
                        help="With --apply: skip the data-plane provisioning "
                             "(MinIO bucket/SA, OpenBao kv/policy/AppRole, "
                             "Postgres extensions) that normally runs once the "
                             "stack is healthy.")
    args = parser.parse_args(argv)

    # Config is required for plan/apply (template generation depends on it).
    # For --down/--logs/--restart we only need the compose file already on disk.
    if args.validate or args.plan or args.apply:
        if not args.config.exists():
            print(f"ERROR: config not found: {args.config}", file=sys.stderr)
            return 3
        raw = vc.load_yaml(args.config)
        try:
            cfg = vc.DeployConfig.model_validate(raw)
        except Exception as e:
            print(f"ERROR: config validation failed:\n{e}", file=sys.stderr)
            return 1
    else:
        cfg = None  # Not needed for compose-only commands.

    # ---- Mode dispatch ----

    if args.validate:
        return _do_validate()

    if args.plan:
        return _do_plan(cfg)

    if args.apply:
        return _do_apply(cfg, yes=args.yes, no_bootstrap=args.no_bootstrap)

    if args.down:
        return _do_down(remove_volumes=args.volumes)

    if args.logs:
        return _do_logs()

    if args.restart:
        return _do_restart()

    return 0  # unreachable


def _do_validate() -> int:
    print(f"=== Prerequisites ===")
    docker = find_docker()
    if not docker:
        print("[FAIL] docker not found on PATH")
        return 1
    print(f"[OK] docker: {docker}")
    if not docker_compose_available():
        print("[FAIL] docker compose v2 plugin not available "
              "(legacy docker-compose v1 is NOT supported)")
        return 1
    print("[OK] docker compose v2 available")
    if not SECRETS_EXAMPLE.exists():
        print(f"[WARN] deploy/.env.secrets.example missing — "
              f"deployers won't have a template to copy from")
    if SECRETS_FILE.exists():
        print(f"[OK] .env.secrets present at repo root "
              f"(content not validated here)")
    else:
        print(f"[INFO] .env.secrets not yet created at repo root — "
              f"will be required for --apply")
    print("\n[OK] Prereqs validated. Use --plan to see the compose file.")
    return 0


def _do_plan(cfg: vc.DeployConfig) -> int:
    print(f"=== Generated {COMPOSE_FILE.name} ===")
    print(generate_compose(cfg))
    print(f"\n=== Generated {CADDYFILE.name} (mounted by `docker compose --profile edge up`) ===")
    print(generate_caddyfile(cfg))
    return 0


def _run_bootstrap(cfg: vc.DeployConfig):
    """Run the data-plane bootstrap after the stack is up (non-fatal).

    Lazy-imported so compose-only commands never pay its import cost, and so a
    bootstrap import error can never block bringing the stack up. A provisioner
    failure is surfaced loudly but does NOT tear the stack down — the operator
    re-runs ``run_bootstrap.py --apply`` once the cause is fixed.

    Returns the BootstrapState (or None if the bootstrap could not run) so the
    caller can gate the app tier on a required provisioner (see _do_apply).
    """
    print("\n=== Data-plane bootstrap (provisioning) ===")
    sys.path.insert(0, str(PROVIDERS_DIR))
    try:
        import bootstrap  # noqa: E402  (lazy)
        state = bootstrap.run_bootstrap(cfg)
    except Exception as e:  # never fatal to the up
        print(f"[WARN] bootstrap could not run: {e}\n"
              f"       Re-run: python deploy/providers/run_bootstrap.py --apply",
              file=sys.stderr)
        return None
    summary = state.redacted_summary()
    print(summary)
    if not state.succeeded:
        print("[WARN] some provisioners failed (see above). Re-run: "
              "python deploy/providers/run_bootstrap.py --apply", file=sys.stderr)
        # #2 guard: a host OOM (Docker CLI 'cannot allocate memory') is the usual
        # cause under a heavy stack — give an actionable hint, it's not a code bug.
        if "cannot allocate memory" in summary or "allocate memory" in summary:
            print("[HINT] looks like the host ran OUT OF MEMORY during bootstrap. "
                  "Free RAM (stop optional services, e.g. "
                  "`docker stop facil_framework-keycloak-1 facil_framework-otel-lgtm-1`, "
                  "and any `--profile ai/mail` containers), then re-run the bootstrap.",
                  file=sys.stderr)
    return state


def _openbao_required_but_failed(cfg: vc.DeployConfig, state) -> bool:
    """True when secrets.provider=openbao but its provisioner did not succeed.

    In openbao mode the backend authenticates via the AppRole the provisioner
    mints; a failed/missing step means it would silently fall back to plaintext
    env secrets. The caller turns this into a hard abort of the app tier — never
    a silent degrade.
    """
    if cfg.secrets.provider != "openbao":
        return False
    step = state.step("openbao") if state is not None else None
    return step is None or step.status != "ok"


def _do_apply(cfg: vc.DeployConfig, *, yes: bool, no_bootstrap: bool = False) -> int:
    if not SECRETS_FILE.exists():
        print(
            f"ERROR: missing secrets file: {SECRETS_FILE}\n"
            f"       Copy deploy/.env.secrets.example to .env.secrets at "
            f"the repo root and fill in the values.",
            file=sys.stderr,
        )
        return 1

    # Ensure strong runtime passwords exist (Postgres/Redis/MinIO). Without this
    # compose falls back to weak dev defaults. Generated once, then stable.
    generated = es.ensure_secrets(SECRETS_FILE)
    if generated:
        print(f"[OK] generated strong runtime secrets: {', '.join(generated)}")

    # D1: captured once, reused below to gate the pre-update backup — a stack
    # that was ALREADY running before this --apply is an UPDATE (there's data
    # to protect); one that wasn't is a first install (nothing to back up
    # yet, same "pre-upgrade only" decision as backup-job.yaml on k3s).
    was_running = stack_running()
    if was_running:
        msg = ("[WARN] Stack already running. --apply on top can hit "
               "'port already allocated' errors.")
        if yes:
            print(msg + " Proceeding (--yes).")
        else:
            print(msg)
            answer = input("Run --down first then --apply? [Y/n] ").strip().lower()
            if answer in ("", "y", "yes"):
                rc = _do_down(remove_volumes=False)
                if rc != 0:
                    print(f"ERROR: --down failed (exit {rc})", file=sys.stderr)
                    return rc

    # Render env files first (idempotent — required for env_file: in compose).
    rc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "render_env.py"),
         f"--config={DEFAULT_CONFIG}", "--target=both"],
        cwd=REPO_ROOT, check=False,
    ).returncode
    if rc != 0:
        print(f"ERROR: render_env.py failed (exit {rc})", file=sys.stderr)
        return 1

    COMPOSE_FILE.write_text(generate_compose(cfg), encoding="utf-8")
    print(f"[OK] Wrote {COMPOSE_FILE.name}")

    # Caddyfile is written even when the `edge` profile is not used now, so that
    # `docker compose --profile edge up` later finds a real file (a missing bind
    # source would make Docker create a directory named "Caddyfile").
    CADDYFILE.write_text(generate_caddyfile(cfg), encoding="utf-8")
    print(f"[OK] Wrote {CADDYFILE.name} (used by the `edge` profile)")

    # Strong runtime secrets passed as compose interpolation env so
    # ${POSTGRES_PASSWORD}/… resolve to the real values (not the weak defaults).
    runtime_env = es.load_runtime_env(SECRETS_FILE)

    # ---- Staged bring-up (the app tier needs creds the bootstrap mints) ----
    # 1) data-plane only  2) bootstrap (mints facil_app/SA/AppRole -> state)
    # 3) render the backend env from that state  4) app tier (db-init + backend).
    data_plane = ["redis"]
    if cfg.docker_local.database_mode == "local":
        data_plane.append("postgres")
    if cfg.storage.provider == "minio":
        data_plane.append("minio")
    if cfg.secrets.provider == "openbao":
        data_plane.append("openbao")

    print("\n=== Starting data-plane ===")
    rc = run_compose(compose_cmd("up", "-d", "--build", *data_plane),
                     env_extra=runtime_env)
    if rc != 0:
        print(f"ERROR: data-plane up failed (exit {rc})", file=sys.stderr)
        return 2

    # K: bring up the profile-gated Keycloak BEFORE the bootstrap so its realm/
    # client provisioner (which the bootstrap runs) finds a healthy service. Only
    # when opt-in + a surface uses keycloak_oidc — otherwise the default apply is
    # untouched.
    _kc_methods = set(cfg.auth.citizen_methods) | set(cfg.auth.agent_methods)
    if cfg.auth.keycloak.enabled and "keycloak_oidc" in _kc_methods:
        print("\n=== Starting Keycloak (auth profile) ===")
        rc = run_compose(compose_cmd("--profile", "auth", "up", "-d", "keycloak"),
                         env_extra=runtime_env)
        if rc != 0:
            print(f"[WARN] keycloak up failed (exit {rc}) — OIDC provisioning will "
                  f"be skipped this run.", file=sys.stderr)

    if not no_bootstrap:
        bstate = _run_bootstrap(cfg)
        # Fail loud (don't start a backend that silently fell back to env secrets):
        # in secrets=openbao mode the backend needs the AppRole the provisioner
        # mints. Abort the app tier; the data-plane stays up for a re-run.
        if _openbao_required_but_failed(cfg, bstate):
            print("ERROR: secrets.provider=openbao but the OpenBao provisioner did "
                  "not succeed — the backend would fall back to plaintext env "
                  "secrets. App tier ABORTED (data-plane stays up). Fix the cause "
                  "and re-run: python deploy/providers/run_bootstrap.py --apply",
                  file=sys.stderr)
            return 1
    else:
        print("\n[INFO] --no-bootstrap: skipped data-plane provisioning.")
        # Even when skipping provisioning, openbao mode REQUIRES a prior successful
        # bootstrap (the AppRole the backend authenticates with). Verify the state
        # file rather than silently starting the backend on plaintext env secrets.
        if cfg.secrets.provider == "openbao":
            sys.path.insert(0, str(PROVIDERS_DIR))
            from bootstrap.state import BootstrapState  # noqa: E402 (lazy)
            prior = BootstrapState.load(STATE_FILE) if STATE_FILE.exists() else None
            if _openbao_required_but_failed(cfg, prior):
                print("ERROR: --no-bootstrap with secrets.provider=openbao, but no "
                      "successful OpenBao step in .bootstrap-state.json. The backend "
                      "would have no AppRole. App tier ABORTED. Run the bootstrap "
                      "first: python deploy/providers/run_bootstrap.py --apply",
                      file=sys.stderr)
                return 1

    # Render packages/backend/.env.deploy.gen (DATABASE_URL = facil_app) from the
    # bootstrap state, then bring up the app tier — only if it's present.
    backend_ctx = REPO_ROOT / "packages" / "backend"
    if backend_ctx.exists():
        # D1: back up Postgres BEFORE db-init (Alembic migration) starts —
        # fail-closed, an update on this tier must never risk data loss any
        # more than the k3s tier does. Only when there's actually a
        # facil-managed Postgres container to protect (database_mode=local)
        # AND this is an update, not the first install (was_running, above).
        if was_running and cfg.docker_local.database_mode == "local":
            print("\n=== Backing up Postgres before update (tier lite, best-effort) ===")
            ok, msg = backup_postgres(cfg)
            if not ok:
                print(f"ERROR: {msg}\n"
                      f"Update ABORTED (fail-closed) — the data-plane stays up, no "
                      f"migration has run. Fix the cause and re-run --apply.",
                      file=sys.stderr)
                return 1
            print(f"[OK] {msg}")

        print("\n=== Rendering backend env + starting app tier ===")
        # Fail loud (don't start a degraded backend) if the bootstrap's postgres
        # step didn't yield a DATABASE_URL in local mode (the #1 silent-failure fix).
        render_cmd = [sys.executable, str(SCRIPTS_DIR / "render_backend_env.py")]
        if cfg.docker_local.database_mode == "local":
            render_cmd.append("--require-db-url")
        if subprocess.run(render_cmd, cwd=REPO_ROOT, check=False).returncode != 0:
            print("ERROR: no DATABASE_URL for the backend — the bootstrap postgres "
                  "step must succeed first. App tier ABORTED (data-plane stays up). "
                  "If the bootstrap OOM'd, free RAM (stop optional services) then "
                  "re-run: python deploy/providers/run_bootstrap.py --apply",
                  file=sys.stderr)
            return 1
        # K2: render the frontend OIDC env from the keycloak state step (no-op if
        # Keycloak wasn't provisioned). MUST precede the frontend build/up so the
        # BFF picks up issuer/client/secret + NEXT_PUBLIC_OIDC_ENABLED.
        if cfg.auth.keycloak.enabled:
            subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "render_web_env.py"),
                 f"--frontend-url=http://localhost:{cfg.docker_local.frontend_port}"],
                cwd=REPO_ROOT, check=False)
        # App tier built locally (db-init + backend + frontend) — no registry.
        # When Keycloak is on, turn the build-time SSO flag on so the (client) login
        # page shows the SSO button.
        build_env = dict(runtime_env)
        if cfg.auth.keycloak.enabled and "keycloak_oidc" in _kc_methods:
            build_env["NEXT_PUBLIC_OIDC_ENABLED"] = "1"
        rc = run_compose(compose_cmd("up", "-d", "--build", "db-init", "backend", "frontend"),
                         env_extra=build_env)
        if rc != 0:
            print(f"[WARN] app tier up failed (exit {rc}) — data-plane is up; "
                  f"fix and re-run. If the frontend (Next) build OOM'd, pull the "
                  f"prebuilt image instead: tools/refresh-local.sh.", file=sys.stderr)
    else:
        print("\n[INFO] packages/backend absent — app tier skipped (data-plane only).")

    print("\n[OK] Stack up. Inspect:")
    print(f"  docker compose -f {COMPOSE_FILE.name} ps")
    print(f"  docker compose -f {COMPOSE_FILE.name} logs -f")
    print(f"  Backend:  http://localhost:{cfg.docker_local.backend_port}")
    print(f"  Frontend: http://localhost:{cfg.docker_local.frontend_port}")
    print("\n[INFO] Optional profile-gated services (OFF by default, opt-in per profile):")
    print(f"  docker compose -f {COMPOSE_FILE.name} --profile edge up -d           "
          f"# Caddy single-origin -> http://localhost:{cfg.edge.http_port}")
    print(f"  docker compose -f {COMPOSE_FILE.name} --profile auth up -d            "
          f"# Keycloak -> http://localhost:{cfg.auth.keycloak.http_port}")
    print(f"  docker compose -f {COMPOSE_FILE.name} --profile observability up -d   "
          f"# Grafana -> http://localhost:{cfg.observability.grafana_port}")
    return 0


def _do_down(*, remove_volumes: bool) -> int:
    if not COMPOSE_FILE.exists():
        print(f"ERROR: {COMPOSE_FILE.name} not found. Run --apply first.",
              file=sys.stderr)
        return 1
    args = ["down"]
    if remove_volumes:
        args.append("-v")
        print("[WARN] --volumes flag: postgres data will be DELETED.")
    rc = run_compose(compose_cmd(*args))
    if rc != 0:
        print(f"ERROR: docker compose down failed (exit {rc})", file=sys.stderr)
        return 2
    print("[OK] Stack stopped.")
    return 0


def _do_logs() -> int:
    if not COMPOSE_FILE.exists():
        print(f"ERROR: {COMPOSE_FILE.name} not found.", file=sys.stderr)
        return 1
    return run_compose(compose_cmd("logs", "-f"))


def _do_restart() -> int:
    if not COMPOSE_FILE.exists():
        print(f"ERROR: {COMPOSE_FILE.name} not found.", file=sys.stderr)
        return 1
    rc = run_compose(compose_cmd("restart"))
    if rc != 0:
        return 2
    print("[OK] Services restarted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
