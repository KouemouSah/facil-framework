"""
Centralized cron endpoint authentication.

All cron endpoints MUST use this dependency to verify the X-Cron-Secret header.
Fail-closed: if CRON_SECRET is not configured, requests are BLOCKED (503).
"""

from typing import Optional
from fastapi import Header, HTTPException
from loguru import logger


def verify_cron_auth(x_cron_secret: Optional[str] = Header(None)) -> bool:
    """
    Verify cron job authentication via shared secret.

    Secret is loaded from:
    - Production: Google Cloud Secret Manager ('cron-secret')
    - Local dev: .env CRON_SECRET

    FAIL-CLOSED: If CRON_SECRET is not configured, all requests are rejected.
    """
    from app.core.secrets import get_cron_secret
    from app.config import get_settings

    settings = get_settings()

    # Priority: Secret Manager > config.py > .env
    expected_secret = get_cron_secret() or getattr(settings, 'CRON_SECRET', None)

    if not expected_secret:
        logger.error(
            "CRON_SECRET not configured — cron endpoints BLOCKED (fail-closed). "
            "Set CRON_SECRET in .env or Secret Manager."
        )
        raise HTTPException(
            status_code=503,
            detail="Cron authentication not configured. Set CRON_SECRET."
        )

    if not x_cron_secret:
        logger.warning("Cron request rejected: missing X-Cron-Secret header")
        raise HTTPException(status_code=403, detail="Missing cron authentication")

    if x_cron_secret != expected_secret:
        logger.warning("Cron request rejected: invalid X-Cron-Secret")
        raise HTTPException(status_code=403, detail="Invalid cron authentication")

    return True
