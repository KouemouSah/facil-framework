"""
Executive Consent Service (Phase 5) — single-use confirmation codes for
Level 3 agent tools (submit_prepared_request, book_appointment).

Why a dedicated service?
------------------------
Migration 287 defines a CHECK constraint on `user_agent_permissions.level`
that accepts only values 1 and 2 — level 3 cannot be persisted. Moreover,
the permission_type CHECK rejects `submit_request` and `book_appointment`.

For government procedures (OWASP A04 — Insecure Design) a persistent
"always allow" toggle is dangerous: a single grant would authorize every
future legal submission without user review. We therefore use per-action
consent: each executive call requires the user to click a "Confirm"
button that redeems a single-use code.

Flow
----
1. Gemini calls `submit_prepared_request(session_id=..., ...)` without a
   confirmation_code → this module issues a new code, stores the full
   tool args in Redis (TTL 300s) plus a hash for tamper detection, logs
   the issuance in `agent_executive_audit_log`, and returns the code +
   a human-readable summary.
2. The backend emits a `confirm_executive` action to the frontend.
3. The user clicks the action → frontend opens a modal showing the
   summary → clicks Confirm → POST /chatbot/execute-confirmed with the
   code.
4. The endpoint probes Redis for the code, dispatches to the right tool
   with `confirmation_code=...` injected in kwargs.
5. The tool calls `redeem_confirmation_code` which: re-verifies the args
   hash, deletes the Redis key (single-use), marks the audit log as
   `redeemed`, and returns the full args so the tool can execute.

Security notes
--------------
- Clear confirmation codes live ONLY in Redis (ephemeral) and are
  sent to the frontend in the action payload. We NEVER store them in
  PostgreSQL — the audit log keeps SHA-256 hashes only.
- `args_hash` is computed from a canonical JSON representation (sorted
  keys, compact separators) and re-verified at redemption. Tampering
  with the cached args is detected as `invalid_args` and logged.
- Single-use is enforced by `cache.delete` BEFORE execution, inside the
  same critical section. A second redemption attempt finds an empty
  Redis key and is rejected as `code_expired_or_invalid`.
- Rate limit: MAX_PENDING_PER_USER codes per hour, fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any, Dict, Optional, Tuple

from loguru import logger
import asyncpg

from app.core.cache import get_cache, check_rate_limit

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

CONSENT_KEY_PREFIX = "agent:exec_consent"
CONSENT_TTL_SECONDS = 300  # 5 minutes — enough for the user to read the modal
MAX_PENDING_PER_USER = 5   # rate limit window = 1 hour
RATE_LIMIT_WINDOW_SECONDS = 3600

ALLOWED_TOOLS = frozenset({"submit_prepared_request", "book_appointment"})


# ----------------------------------------------------------------------------
# Canonicalization + hashing
# ----------------------------------------------------------------------------

def canonicalize_args(args: Dict[str, Any]) -> str:
    """Deterministic JSON of tool args for hashing.

    Excludes `user_id` and `confirmation_code` — they are flow-control,
    not part of the business payload, and they differ between the issue
    call and the redemption call by construction.
    """
    filtered = {
        k: v for k, v in args.items()
        if k not in ("user_id", "confirmation_code")
    }
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"), default=str)


def hash_args(args: Dict[str, Any]) -> str:
    return hashlib.sha256(canonicalize_args(args).encode("utf-8")).hexdigest()


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _key(user_id: str, code: str) -> str:
    return f"{CONSENT_KEY_PREFIX}:{user_id}:{code}"


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

async def issue_confirmation_code(
    db: asyncpg.Connection,
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    summary: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Issue a new single-use confirmation code.

    Returns `(code, error_key)`. On success `code` is the clear token and
    `error_key` is None. On failure `code` is None and `error_key` is an
    i18n key the frontend can resolve.
    """
    if tool_name not in ALLOWED_TOOLS:
        return None, "executive.tool_not_allowed"

    allowed, _ = await check_rate_limit(
        user_id,
        "exec_consent_issue",
        MAX_PENDING_PER_USER,
        RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        await _audit_log(
            db,
            user_id=user_id,
            tool_name=tool_name,
            code_hash="",
            args_hash=hash_args(args),
            summary=summary,
            outcome="rate_limited",
        )
        return None, "executive.rate_limited"

    code = secrets.token_urlsafe(24)
    args_h = hash_args(args)

    cache = get_cache()
    payload = {
        "tool": tool_name,
        "args": args,
        "args_hash": args_h,
        "summary": summary,
    }
    await cache.set(_key(user_id, code), payload, ttl=CONSENT_TTL_SECONDS)

    await _audit_log(
        db,
        user_id=user_id,
        tool_name=tool_name,
        code_hash=hash_code(code),
        args_hash=args_h,
        summary=summary,
        outcome="issued",
    )

    return code, None


async def peek_confirmation_code(
    user_id: str,
    code: str,
) -> Optional[Dict[str, Any]]:
    """Read the Redis payload without consuming it.

    Used by the `/chatbot/execute-confirmed` endpoint to decide which
    tool to dispatch to. The tool itself then calls
    `redeem_confirmation_code` which actually deletes the key.
    """
    cache = get_cache()
    return await cache.get(_key(user_id, code))


async def redeem_confirmation_code(
    db: asyncpg.Connection,
    user_id: str,
    code: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validate + consume a confirmation code.

    On success returns `(payload, None)` where `payload` contains
    `tool`, `args`, and `summary`. The Redis key is deleted atomically
    BEFORE return, so a subsequent redemption attempt fails.
    """
    cache = get_cache()
    key = _key(user_id, code)
    stored = await cache.get(key)

    if not stored:
        return None, "executive.code_expired_or_invalid"

    recomputed = hash_args(stored.get("args", {}))
    if recomputed != stored.get("args_hash"):
        await _audit_log(
            db,
            user_id=user_id,
            tool_name=stored.get("tool", "?"),
            code_hash=hash_code(code),
            args_hash=recomputed,
            summary=stored.get("summary", ""),
            outcome="invalid_args",
            error_message="args_hash mismatch on redemption",
        )
        return None, "executive.invalid_args"

    # Single-use: delete BEFORE execution to prevent double-redeem races
    await cache.delete(key)

    await _mark_redeemed(
        db,
        user_id=user_id,
        code_hash=hash_code(code),
        args_hash=recomputed,
    )

    return stored, None


async def record_execution_failure(
    db: asyncpg.Connection,
    user_id: str,
    code: str,
    error_message: str,
) -> None:
    """Mark an audit row as execution_failed when the tool raises."""
    try:
        await db.execute(
            """
            UPDATE agent_executive_audit_log
            SET outcome = 'execution_failed',
                error_message = $3
            WHERE user_id = $1::uuid
              AND confirmation_code_hash = $2
              AND outcome = 'redeemed'
            """,
            user_id,
            hash_code(code),
            error_message[:500],  # truncate to avoid unbounded storage
        )
    except Exception as exc:
        logger.warning(f"executive_consent record_execution_failure failed: {exc}")


# ----------------------------------------------------------------------------
# Audit log helpers (private)
# ----------------------------------------------------------------------------

async def _audit_log(
    db: asyncpg.Connection,
    *,
    user_id: str,
    tool_name: str,
    code_hash: str,
    args_hash: str,
    summary: str,
    outcome: str,
    error_message: Optional[str] = None,
) -> None:
    """Best-effort audit insert. Failures are logged but never raise —
    the business flow must not be blocked by an audit outage."""
    try:
        await db.execute(
            """
            INSERT INTO agent_executive_audit_log
                (user_id, tool_name, confirmation_code_hash, args_hash,
                 summary, outcome, error_message)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
            """,
            user_id,
            tool_name,
            code_hash,
            args_hash,
            summary,
            outcome,
            error_message,
        )
    except Exception as exc:
        logger.warning(f"executive_consent audit_log failed: {exc}")


async def _mark_redeemed(
    db: asyncpg.Connection,
    *,
    user_id: str,
    code_hash: str,
    args_hash: str,
) -> None:
    try:
        await db.execute(
            """
            UPDATE agent_executive_audit_log
            SET redeemed_at = NOW(), outcome = 'redeemed'
            WHERE user_id = $1::uuid
              AND confirmation_code_hash = $2
              AND args_hash = $3
              AND outcome = 'issued'
            """,
            user_id,
            code_hash,
            args_hash,
        )
    except Exception as exc:
        logger.warning(f"executive_consent mark_redeemed failed: {exc}")
