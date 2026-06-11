#!/usr/bin/env python3
"""Validator for deploy/config.yaml — Phase A.5.1 of DEPLOY_SYSTEM_PLAN.

Loads a deploy config YAML, validates it against a Pydantic schema, and
emits a summary including:
  - Required fields that are still empty
  - List of secret names referenced (so the operator can verify they all
    exist in Secret Manager / equivalent)
  - Provider sections that will be consumed for the chosen --provider

Usage
-----
    python validate_config.py path/to/config.yaml
    python validate_config.py config.yaml --provider=gcp
    python validate_config.py config.yaml --quiet   # exit code only

Exit codes
----------
0  Config valid for the target provider.
1  Validation error (required field missing, schema mismatch, etc.).
2  YAML parse error.
3  File not found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
except ImportError:  # pragma: no cover
    print("ERROR: Pydantic v2 is required. Install with: pip install 'pydantic>=2'",
          file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Schema models — mirror config.example.yaml structure.
# ---------------------------------------------------------------------------

class MetaConfig(BaseModel):
    config_version: int = Field(ge=1, le=1)
    project_name: str = Field(min_length=1)
    environment: Literal["production", "staging", "development"]
    version: str = "latest"


class DatabasePool(BaseModel):
    min_connections: int = Field(default=10, ge=1, le=200)
    max_connections: int = Field(default=20, ge=1, le=500)
    pool_timeout_seconds: int = Field(default=30, ge=1, le=600)


class DatabaseConfig(BaseModel):
    url_secret: str = ""
    host: str = ""
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = ""
    user: str = ""
    password_secret: str = ""
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] = "require"
    pool: DatabasePool = Field(default_factory=DatabasePool)
    # Optional Supabase bridge fields (kept for legacy code paths that read
    # SUPABASE_URL / SUPABASE_ANON_KEY in addition to / instead of DATABASE_URL).
    supabase_url_secret: str = ""
    supabase_anon_key_secret: str = ""

    @model_validator(mode="after")
    def must_have_url_or_parts(self) -> "DatabaseConfig":
        if not self.url_secret and not (self.host and self.name and self.user):
            raise ValueError(
                "database: provide either 'url_secret' OR all of "
                "(host, name, user, password_secret)"
            )
        return self


class RedisConfig(BaseModel):
    url_secret: str = Field(min_length=1)
    cache_ttl_seconds: int = Field(default=3600, ge=1)


class AuthKeycloakConfig(BaseModel):
    # Keycloak is SCAFFOLDED in the dev stack behind the `auth` Compose profile
    # (OFF by default). Realm creation, AD/LDAP federation, client config and
    # production Postgres wiring are LATE-BINDING and done in P11 — these fields
    # are only a placeholder so the service skeleton (image, port, admin
    # bootstrap) exists and future activation is a profile switch, not a build.
    image: str = "quay.io/keycloak/keycloak:26.0"
    http_port: int = Field(default=8088, ge=1, le=65535)
    admin_user: str = "admin"
    admin_password_secret: str = "KEYCLOAK_ADMIN_PASSWORD"
    realm: str = "facil-agents"   # placeholder name — realm actually created in P11


class AuthConfig(BaseModel):
    jwt_secret_name: str = Field(min_length=1)
    app_secret_name: str = Field(min_length=1)
    totp_encryption_secret: str = Field(min_length=1)
    receipt_verification_secret: str = ""
    access_token_minutes: int = Field(default=30, ge=1)
    refresh_token_days: int = Field(default=30, ge=1)
    # Auth provider PER SURFACE (seam for P11). Defaults keep the current
    # behaviour (native everywhere) => zero regression. Citizens stay native by
    # design (no Keycloak-for-all: SPOF + scale cost + no citizen AD). Agents
    # move to keycloak_oidc in P11.
    provider_citizen: Literal["native"] = "native"
    provider_agent: Literal["native", "keycloak_oidc", "saml"] = "native"
    keycloak: AuthKeycloakConfig = Field(default_factory=AuthKeycloakConfig)


class FirebaseConfig(BaseModel):
    project_id: str = Field(min_length=1)
    storage_bucket: str = Field(min_length=1)
    android_app_id: str = ""
    # Different secrets for dev vs prod environments. Empty = not used.
    service_account_dev_secret: str = ""
    service_account_pro_secret: str = ""


class AIGenerationConfig(BaseModel):
    max_output_tokens: int = Field(default=2048, ge=1, le=32000)
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1, le=200)


class AIModelsConfig(BaseModel):
    chat: str = Field(default="gemini-2.5-flash")
    pro: str = Field(default="gemini-2.5-flash")
    embedding: str = Field(default="text-embedding-005")


class AIConfig(BaseModel):
    gemini_api_key_secret: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    models: AIModelsConfig = Field(default_factory=AIModelsConfig)
    generation: AIGenerationConfig = Field(default_factory=AIGenerationConfig)

    @model_validator(mode="after")
    def must_have_credentials_path(self) -> "AIConfig":
        if not self.gemini_api_key_secret and not self.google_cloud_project:
            raise ValueError(
                "ai: provide either 'gemini_api_key_secret' (API Studio path) "
                "OR 'google_cloud_project' (Vertex ADC path)"
            )
        return self


class PaymentBangeConfig(BaseModel):
    enabled: bool = False
    api_url: str = ""
    merchant_id: str = ""
    api_key_secret: str = ""
    webhook_secret_secret: str = ""


class PaymentEcobankConfig(BaseModel):
    enabled: bool = False
    api_url: str = ""
    client_id: str = ""
    client_secret_secret: str = ""
    webhook_secret_secret: str = ""
    primary_methods: str = ""


class PaymentMpgsConfig(BaseModel):
    enabled: bool = False
    api_url: str = ""
    merchant_id: str = ""
    api_password_secret: str = ""
    webhook_secret_secret: str = ""
    api_version: str = "85"
    primary_methods: str = "card"


class PaymentsConfig(BaseModel):
    bange: PaymentBangeConfig = Field(default_factory=PaymentBangeConfig)
    ecobank: PaymentEcobankConfig = Field(default_factory=PaymentEcobankConfig)
    mpgs: PaymentMpgsConfig = Field(default_factory=PaymentMpgsConfig)


class SmtpConfig(BaseModel):
    host: str = ""
    port: int = Field(default=587, ge=1, le=65535)
    username: str = ""
    password_secret: str = ""
    use_tls: bool = True
    from_email: str = ""
    from_name: str = "Facil"


class ObservabilityConfig(BaseModel):
    # --- Existing SaaS-cloud fields (CONSERVED; empty default = disabled) ---
    # Backend Sentry DSN (different from web Sentry DSN — separate projects).
    sentry_dsn_backend_secret: str = ""
    sentry_dsn_web_secret: str = ""        # Public, but kept in Secret Manager for parity.
    sentry_auth_token_secret: str = ""     # Build-time only (sourcemap upload).
    logrocket_app_id_secret: str = ""      # Public, kept in Secret Manager for parity.
    grafana_otlp_endpoint: str = ""
    grafana_token_secret: str = ""
    maxmind_license_key_secret: str = ""   # GeoIP DB auto-download at boot.
    slack_webhook_url: str = ""
    # --- NEW (P14): OTLP-first pluggable seam — sovereign-capable -----------
    # `mode` switches the whole telemetry target local<->cloud BY CONFIG, the
    # same pluggable philosophy as ADR-002 for inference. The current SaaS
    # fields above stay for the cloud profile; `mode=local` points at the
    # self-hosted stack instead (nothing leaves the network).
    mode: Literal["disabled", "local", "cloud"] = "disabled"
    otlp_endpoint: str = ""                                     # Alloy (local) OR Grafana Cloud
    otlp_protocol: Literal["grpc", "http"] = "grpc"
    errors_backend: Literal["none", "sentry_saas", "glitchtip"] = "none"
    errors_dsn_secret: str = ""            # GlitchTip OR Sentry DSN — same `sentry-sdk`, only the DSN changes.
    session_replay: Literal["none", "logrocket", "openreplay"] = "none"  # OpenReplay = sovereign (heavy, opt-in)
    # Dev-local tier (P14 palier A): single all-in-one grafana/otel-lgtm
    # container, gated by the `observability` Compose profile (OFF by default).
    otel_lgtm_image: str = "grafana/otel-lgtm:latest"
    grafana_port: int = Field(default=3001, ge=1, le=65535)    # 3000 is taken by the frontend
    otlp_grpc_port: int = Field(default=4317, ge=1, le=65535)
    otlp_http_port: int = Field(default=4318, ge=1, le=65535)


class ServerConfig(BaseModel):
    api_host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    frontend_url: str = Field(min_length=1)
    api_base_url: str = Field(min_length=1)
    mobile_deep_link_schemes: str = "facil"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("frontend_url", "api_base_url")
    @classmethod
    def must_look_like_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: {v}")
        return v


class LegalConfig(BaseModel):
    privacy_version: str = "1.0.0"
    privacy_last_updated: str = "2026-05-02"
    terms_version: str = "1.0.0"
    terms_last_updated: str = "2026-05-02"
    cookies_version: str = "1.0.0"
    cookies_last_updated: str = "2026-05-02"


class CronConfig(BaseModel):
    secret_name: str = Field(min_length=1)


class FeaturesConfig(BaseModel):
    scheduler_enabled: bool = True
    rate_limit_enabled: bool = True
    metrics_enabled: bool = True
    structured_logging: bool = True
    executive_tools: bool = False
    llm_routing: bool = False
    penalties: bool = False


class GcpConfig(BaseModel):
    project_id: str = ""
    region: str = "us-central1"
    backend_service_name: str = "facil-backend"
    frontend_service_name: str = "facil-frontend"
    cloud_sql_instance: str = ""
    custom_domain_backend: str = ""
    custom_domain_frontend: str = ""


class AwsConfig(BaseModel):
    region: str = "us-east-1"
    backend_cluster: str = "facil-backend"
    rds_instance: str = ""


class MinioComplianceConfig(BaseModel):
    # WORM (Object-Lock) bucket for legally-retained artefacts: signed PDFs
    # (PAdES/eIDAS), receipts, audit trails. Object-Lock can only be enabled at
    # bucket creation, so this is a SEPARATE bucket from default_bucket.
    enabled: bool = True
    bucket: str = "facil-compliance"
    # GOVERNANCE: privileged users (s3:BypassGovernanceRetention) can still
    # delete/shorten — safe default, dev-cleanable. COMPLIANCE: immutable even
    # to root until expiry — opt-in for production legal requirements.
    retention_mode: Literal["governance", "compliance"] = "governance"
    retention_days: int = Field(default=365, ge=1, le=36500)


class MinioLifecycleConfig(BaseModel):
    # Non-current versions accumulate forever once versioning is ON (they MUST
    # be pruned or storage grows unbounded). 0 = rule disabled.
    # NB: incomplete multipart uploads are already auto-cleaned by the MinIO
    # server (api.stale_uploads_expiry, default 24h) — not a per-bucket rule, so
    # no config knob here (it would only let you make cleanup *worse*).
    expire_noncurrent_versions_days: int = Field(default=90, ge=0, le=3650)


class MinioConfig(BaseModel):
    # On-prem souverain object storage (ADR-0005). P4 pins by digest
    # (verified latest = sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e).
    image: str = "minio/minio:latest"
    api_port: int = Field(default=9000, ge=1, le=65535)
    console_port: int = Field(default=9001, ge=1, le=65535)
    volume: str = "facil_minio_data"
    root_user: str = "facil"
    root_password_secret: str = "MINIO_ROOT_PASSWORD"
    default_bucket: str = "facil-documents"
    # --- Security / governance hardening (MINIO_SECURITY_ARCH, S1) ---
    # All defaulted -> existing configs stay valid (zero-regression).
    compliance: MinioComplianceConfig = Field(default_factory=MinioComplianceConfig)
    lifecycle: MinioLifecycleConfig = Field(default_factory=MinioLifecycleConfig)
    # Per-bucket quota in GiB; 0 = unlimited.
    quota_documents_gb: int = Field(default=0, ge=0, le=1_048_576)
    quota_compliance_gb: int = Field(default=0, ge=0, le=1_048_576)


class StorageConfig(BaseModel):
    # Pluggable file-storage backend (ADR-0005). On-prem souverain default = MinIO (S3-compatible).
    provider: Literal["minio", "s3", "gcs", "azure_blob", "local_fs", "disabled"] = "minio"
    minio: MinioConfig = Field(default_factory=MinioConfig)


class OpenbaoConfig(BaseModel):
    # Secrets + PKI engine (ADR-0003/0006, P7). P4 pins by digest
    # (verified latest = sha256:436eaf9778cad75507ff70ea26ace30dcbe15606e619ac3823495663d7f7c115).
    image: str = "openbao/openbao:latest"
    port: int = Field(default=8200, ge=1, le=65535)
    volume: str = "facil_openbao_data"
    # dev_mode=True -> `bao server -dev` (in-memory, auto-unsealed, NON-PROD).
    # Production unseal (SOPS+age bootstrap) is implemented in P7.
    dev_mode: bool = True
    dev_root_token_secret: str = "OPENBAO_DEV_ROOT_TOKEN"


class SecretsConfig(BaseModel):
    # Pluggable secrets backend (ADR-0003, P7). Default dev = env_file.
    provider: Literal[
        "env_file", "docker_secrets", "sops_age", "openbao",
        "gcp_secret_manager", "aws_secrets_manager", "azure_key_vault",
    ] = "env_file"
    openbao: OpenbaoConfig = Field(default_factory=OpenbaoConfig)


class EdgeConfig(BaseModel):
    # Reverse-proxy (Caddy) SCAFFOLDED in the dev stack behind the `edge`
    # Compose profile (OFF by default). Real dev benefit: single origin
    # (frontend + /api on one host => no CORS) and early TLS testing. Production
    # TLS/PKI (ACME or OpenBao internal CA) and per-surface routing land in
    # P8/P12 — only `tls_mode`/domains there change, the seam stays the same.
    proxy: Literal["caddy", "traefik", "none"] = "caddy"
    image: str = "caddy:2-alpine"
    tls_mode: Literal["none", "internal", "acme", "custom"] = "none"
    http_port: int = Field(default=8090, ge=1, le=65535)
    https_port: int = Field(default=8443, ge=1, le=65535)
    domain_backend: str = ""
    domain_frontend: str = ""


class DockerLocalConfig(BaseModel):
    # Where the Postgres database lives.
    #   - "local"    : compose generates a postgres container (default,
    #                  zero external dependencies, good for first-time
    #                  install / demo / offline dev).
    #   - "external" : compose does NOT generate postgres; backend +
    #                  db-init connect to DATABASE_URL from .env.secrets
    #                  (works for Supabase, AWS RDS, Cloud SQL via SQL
    #                  proxy, Neon, Railway, any external Postgres).
    database_mode: Literal["local", "external"] = "local"
    backend_port: int = Field(default=8080, ge=1, le=65535)
    frontend_port: int = Field(default=3000, ge=1, le=65535)
    postgres_image: str = "postgres:16-alpine"
    postgres_volume: str = "facil_pgdata"
    redis_image: str = "redis:7-alpine"


class DeployConfig(BaseModel):
    """Top-level deploy/config.yaml schema."""
    meta: MetaConfig
    database: DatabaseConfig
    redis: RedisConfig
    auth: AuthConfig
    firebase: FirebaseConfig
    ai: AIConfig
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    smtp: SmtpConfig = Field(default_factory=SmtpConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    server: ServerConfig
    legal: LegalConfig = Field(default_factory=LegalConfig)
    cron: CronConfig
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    gcp: GcpConfig = Field(default_factory=GcpConfig)
    aws: AwsConfig = Field(default_factory=AwsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)
    edge: EdgeConfig = Field(default_factory=EdgeConfig)
    docker_local: DockerLocalConfig = Field(default_factory=DockerLocalConfig)
    env_overrides: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("env_overrides", mode="before")
    @classmethod
    def coerce_none_env_overrides_to_empty(cls, v):
        # YAML 'env_overrides:' with nothing under it parses as None.
        return v or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_secret_references(cfg: DeployConfig) -> list[str]:
    """Return the deduplicated list of secret-name references found in cfg.

    Looks at every field whose name ends in '_secret' or '_secret_name' or
    '_secret_secret' (yes, the convention is awkward — kept consistent with
    legacy env var naming).
    """
    secrets: set[str] = set()

    # Field names that hold a secret reference. Use suffix matching for the
    # convention `<thing>_secret`, plus exact-match for the few fields named
    # just `secret_name` (e.g. cron.secret_name).
    SECRET_SUFFIXES = ("_secret", "_secret_name", "_secret_secret")
    SECRET_EXACT_NAMES = {"secret_name"}

    def visit(obj: object) -> None:
        if isinstance(obj, BaseModel):
            for name, value in obj.model_dump().items():
                if name in SECRET_EXACT_NAMES or name.endswith(SECRET_SUFFIXES):
                    if isinstance(value, str) and value:
                        secrets.add(value)
                else:
                    visit(getattr(obj, name, None))
        # dicts/lists etc. don't carry secret refs in our schema.

    visit(cfg)
    return sorted(secrets)


def provider_required_fields(cfg: DeployConfig, provider: str) -> list[str]:
    """Return human-readable descriptions of provider-specific empty required fields."""
    missing = []
    if provider == "gcp":
        if not cfg.gcp.project_id:
            missing.append("gcp.project_id")
    elif provider == "aws":
        if not cfg.aws.rds_instance:
            missing.append("aws.rds_instance (or DATABASE_URL externally configured)")
    elif provider == "docker-local":
        # Self-contained, nothing extra required at this stage.
        pass
    return missing


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: config file not found: {path}", file=sys.stderr)
        sys.exit(3)
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse failed: {e}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("config", type=Path, help="Path to config.yaml")
    parser.add_argument(
        "--provider",
        choices=["gcp", "aws", "docker-local"],
        default=None,
        help="Validate provider-specific required fields too.",
    )
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress success output (errors still printed).")
    args = parser.parse_args(argv)

    raw = load_yaml(args.config)

    try:
        cfg = DeployConfig.model_validate(raw)
    except Exception as e:
        print(f"ERROR: schema validation failed:\n{e}", file=sys.stderr)
        return 1

    if args.provider:
        missing = provider_required_fields(cfg, args.provider)
        if missing:
            print(
                f"ERROR: provider '{args.provider}' requires these fields "
                f"to be set: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

    if not args.quiet:
        secrets = collect_secret_references(cfg)
        print(f"[OK] Config valid for project '{cfg.meta.project_name}' "
              f"(env={cfg.meta.environment}, version={cfg.meta.version})")
        if args.provider:
            print(f"  Provider: {args.provider}")
        print(f"  Secrets referenced ({len(secrets)}):")
        for s in secrets:
            print(f"    - {s}")
        print(f"  Payments enabled: bange={cfg.payments.bange.enabled}, "
              f"ecobank={cfg.payments.ecobank.enabled}, "
              f"mpgs={cfg.payments.mpgs.enabled}")
        print(f"  Features enabled: "
              f"{[k for k, v in cfg.features.model_dump().items() if v]}")
        print(f"  env_overrides ({len(cfg.env_overrides)}): "
              f"{list(cfg.env_overrides.keys())[:5]}"
              f"{'...' if len(cfg.env_overrides) > 5 else ''}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
