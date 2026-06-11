"""
Secret Manager Integration for TaxasGE Backend
Reads secrets from Google Cloud Secret Manager with local .env fallback
"""

import os
from functools import lru_cache
from typing import Optional, Any
from loguru import logger

# Try to import Secret Manager client (optional for local dev)
try:
    from google.cloud import secretmanager
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    secretmanager = None  # type: ignore
    SECRET_MANAGER_AVAILABLE = False
    logger.warning("google-cloud-secret-manager not installed, using .env fallback only")

# Initialize Secret Manager client (lazy)
_client: Optional[Any] = None


def get_secret_manager_client() -> Optional[Any]:
    """Get or create Secret Manager client (singleton)"""
    global _client
    if not SECRET_MANAGER_AVAILABLE:
        return None

    if _client is None:
        try:
            _client = secretmanager.SecretManagerServiceClient()
            logger.info("Secret Manager client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Secret Manager client: {e}")
            return None

    return _client


@lru_cache(maxsize=128)
def get_secret(secret_name: str, project_id: str = "taxasge-dev") -> Optional[str]:
    """
    Retrieve secret from Google Cloud Secret Manager with .env fallback

    Args:
        secret_name: Name of the secret (e.g., 'smtp-password')
        project_id: GCP project ID (default: taxasge-dev)

    Returns:
        Secret value as string, or None if not found

    Priority:
        1. Local .env (if ENV=local or development)
        2. Secret Manager (if available and ENV=production)
    """
    # Convert secret name to env var format (smtp-password -> SMTP_PASSWORD)
    env_var = secret_name.upper().replace("-", "_")

    # Check environment mode
    env_mode = os.getenv("ENV", "local")

    # For local/development: Always use .env
    if env_mode in ["local", "development"]:
        value = os.getenv(env_var)
        if value:
            logger.debug(f"Using local env var for secret: {secret_name} ({env_var})")
            return value
        else:
            logger.warning(f"Secret '{secret_name}' not found in .env (expected: {env_var})")
            return None

    # For production: Try Secret Manager first, fallback to .env
    if SECRET_MANAGER_AVAILABLE:
        try:
            client = get_secret_manager_client()
            if client:
                secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": secret_path})
                secret_value = response.payload.data.decode("UTF-8")
                logger.info(f"✅ Secret loaded from Secret Manager: {secret_name}")
                return secret_value
        except Exception as e:
            logger.error(f"Failed to load secret '{secret_name}' from Secret Manager: {e}")
            # Fallback to env var

    # Fallback to environment variable
    value = os.getenv(env_var)
    if value:
        logger.warning(f"Using env var fallback for secret: {secret_name} ({env_var})")
        return value

    logger.error(f"❌ Secret '{secret_name}' not found in Secret Manager or .env")
    return None


# Cached getters for frequently used secrets
@lru_cache(maxsize=1)
def get_smtp_password() -> Optional[str]:
    """Get SMTP_PASSWORD for email notifications"""
    return get_secret("smtp-password")


@lru_cache(maxsize=1)
def get_jwt_secret_key() -> Optional[str]:
    """Get JWT_SECRET_KEY for token signing"""
    return get_secret("jwt-secret-key")


@lru_cache(maxsize=1)
def get_database_url() -> Optional[str]:
    """Get PostgreSQL DATABASE_URL"""
    return get_secret("database-url")


@lru_cache(maxsize=1)
def get_supabase_url() -> Optional[str]:
    """Get Supabase URL"""
    return get_secret("supabase-url")


@lru_cache(maxsize=1)
def get_supabase_anon_key() -> Optional[str]:
    """Get Supabase Anon Key"""
    return get_secret("supabase-anon-key")


@lru_cache(maxsize=1)
def get_github_pat() -> Optional[str]:
    """Get GitHub Personal Access Token for API operations"""
    return get_secret("github-pat")


@lru_cache(maxsize=1)
def get_cron_secret() -> Optional[str]:
    """Get CRON_SECRET for cron endpoint authentication"""
    return get_secret("cron-secret")


# Ecobank Payment Integration secrets
@lru_cache(maxsize=1)
def get_ecobank_client_id() -> Optional[str]:
    """Get Ecobank API client ID"""
    return get_secret("ecobank-client-id")


@lru_cache(maxsize=1)
def get_ecobank_client_secret() -> Optional[str]:
    """Get Ecobank API client secret"""
    return get_secret("ecobank-client-secret")


@lru_cache(maxsize=1)
def get_ecobank_webhook_secret() -> Optional[str]:
    """Get Ecobank webhook HMAC secret"""
    return get_secret("ecobank-webhook-secret")


# Mastercard MPGS secrets (via Ecobank)
@lru_cache(maxsize=1)
def get_mpgs_merchant_id() -> Optional[str]:
    """Get MPGS merchant ID"""
    return get_secret("mpgs-merchant-id")


@lru_cache(maxsize=1)
def get_mpgs_api_password() -> Optional[str]:
    """Get MPGS API password"""
    return get_secret("mpgs-api-password")


@lru_cache(maxsize=1)
def get_mpgs_webhook_secret() -> Optional[str]:
    """Get MPGS webhook shared secret"""
    return get_secret("mpgs-webhook-secret")


# Validation helper
def validate_secrets_available() -> dict:
    """
    Check if all critical secrets are available

    Returns:
        dict with status of each secret
    """
    critical_secrets = {
        "jwt-secret-key": get_jwt_secret_key(),
        "database-url": get_database_url(),
        "smtp-password": get_smtp_password(),
        "cron-secret": get_cron_secret(),
    }

    status = {}
    all_ok = True

    for name, value in critical_secrets.items():
        is_available = value is not None and len(value) > 0
        status[name] = "✅ OK" if is_available else "❌ MISSING"
        if not is_available:
            all_ok = False

    status["all_critical_secrets_ok"] = all_ok

    return status
