"""
Auto-classify background service (Phase 6).

When a user uploads a document to their vault WITHOUT specifying a
`document_type_hint` AND they have the `auto_classify` agent permission
active, the upload endpoint spawns a fire-and-forget background task
that calls the existing `BatchDocumentClassifier` (Gemini Flash vision)
to identify the document type and update the DB row.

Safety rails:
- **Opt-in**: requires explicit `user_agent_permissions` grant → no
  runaway Gemini costs at 1M users scale.
- **OWASP A01**: UPDATE is scoped by (id, user_id) to prevent
  cross-tenant writes if the background context is ever abused.
- **Idempotent**: if the document_type was changed between upload
  completion and task execution (user manually tagged it), skip the
  overwrite.
- **Timeouts + error swallowing**: the task must never crash the upload
  endpoint — all exceptions logged and dropped.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

import asyncpg
from loguru import logger

from app.modules.user_documents.utils.category_inference import infer_category


AUTO_CLASSIFY_TIMEOUT_SECONDS = 30
AUTO_CLASSIFY_RATE_LIMIT_PER_HOUR = 20


async def has_auto_classify_permission(db: asyncpg.Connection, user_id: UUID) -> bool:
    """Check if `user_id` has the `auto_classify` permission granted and active."""
    return bool(
        await db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM user_agent_permissions
                WHERE user_id = $1::uuid
                  AND permission_type = 'auto_classify'
                  AND is_active = TRUE
            )
            """,
            user_id,
        )
    )


async def should_spawn_classify(db: asyncpg.Connection, user_id: UUID) -> bool:
    """Decide whether to spawn an auto-classify task for this upload.

    Combines the persistent permission check with a per-user hourly
    rate limit so a single user cannot trigger runaway Gemini costs
    even while opted-in (at 1M users scale, a compromised account
    uploading in a loop would otherwise drain our quota).
    """
    if not await has_auto_classify_permission(db, user_id):
        return False

    # Rate limit: 20 classifications / user / hour. Upload endpoint
    # already caps uploads at 10/min/user, so this adds a second layer.
    from app.core.cache import check_rate_limit
    is_allowed, _remaining = await check_rate_limit(
        str(user_id),
        "auto_classify_upload",
        AUTO_CLASSIFY_RATE_LIMIT_PER_HOUR,
        3600,
    )
    if not is_allowed:
        logger.info(
            f"[AutoClassify] Rate limit exceeded for user={user_id} — "
            f"skipping classification"
        )
    return bool(is_allowed)


async def auto_classify_background(
    doc_id: UUID,
    user_id: UUID,
    content: bytes,
    mime_type: str,
    file_name: str,
    db_pool: asyncpg.Pool,
) -> None:
    """Run Gemini classification on an uploaded document and persist the result.

    Invoked via `asyncio.create_task` after a vault upload completes.
    Acquires its own DB connection from the pool because the request-
    scoped connection is gone by the time the task runs.

    Guarantees:
    - Never raises (all exceptions logged + swallowed).
    - Bounded by `AUTO_CLASSIFY_TIMEOUT_SECONDS` via `asyncio.wait_for`.
    - Idempotent: skips if the `document_type` column was changed
      between upload completion and task execution.
    """
    try:
        await asyncio.wait_for(
            _auto_classify_impl(doc_id, user_id, content, mime_type, file_name, db_pool),
            timeout=AUTO_CLASSIFY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"[AutoClassify] Timeout classifying doc={doc_id} after "
            f"{AUTO_CLASSIFY_TIMEOUT_SECONDS}s — skipping"
        )
    except Exception as exc:
        logger.warning(
            f"[AutoClassify] Background task failed for doc={doc_id}: {exc}"
        )


async def _auto_classify_impl(
    doc_id: UUID,
    user_id: UUID,
    content: bytes,
    mime_type: str,
    file_name: str,
    db_pool: asyncpg.Pool,
) -> None:
    from app.modules.batch_requests.services.document_classifier import (
        batch_document_classifier,
    )

    if not getattr(batch_document_classifier, "enabled", False):
        logger.info(
            f"[AutoClassify] Classifier disabled (Vertex AI down) — "
            f"skipping doc={doc_id}"
        )
        return

    # "VAULT" triggers the fallback to schema_loader.get_schema_keys() inside
    # _get_known_document_types, returning ALL known document types — no
    # workflow constraint (a vault doc isn't tied to a specific procedure).
    results = await batch_document_classifier.classify_documents(
        documents=[{
            "content": content,
            "mime_type": mime_type,
            "file_path": file_name,  # placeholder — not persisted
            "file_name": file_name,
        }],
        workflow_code="VAULT",
    )
    if not results:
        logger.warning(f"[AutoClassify] Empty result for doc={doc_id}")
        return

    result = results[0]
    if result.error or not result.document_type:
        logger.info(
            f"[AutoClassify] Classification failed/empty for doc={doc_id}: "
            f"error={result.error}"
        )
        return

    category = infer_category(result.document_type)

    async with db_pool.acquire() as conn:
        # Idempotency guard: only overwrite if the row is still marked
        # 'unknown'. If the user manually tagged the document between
        # upload and task execution, we preserve their choice.
        updated = await conn.fetchval(
            """
            UPDATE user_documents
            SET document_type = $3,
                document_category = COALESCE($4, document_category),
                classification_method = 'gemini',
                classification_confidence = $5,
                updated_at = NOW()
            WHERE id = $1
              AND user_id = $2
              AND document_type = 'unknown'
            RETURNING id
            """,
            doc_id,
            user_id,
            result.document_type,
            category,
            result.confidence,
        )
        if not updated:
            logger.info(
                f"[AutoClassify] doc={doc_id} already tagged — skip overwrite"
            )
            return

        # Best-effort audit log — never blocks the happy path.
        try:
            await conn.execute(
                """
                INSERT INTO user_document_access_log
                    (document_id, accessed_by, access_type, access_context)
                VALUES ($1, $2, 'reclassify', 'auto_classify_agent')
                """,
                doc_id,
                user_id,
            )
        except Exception as audit_exc:
            logger.debug(
                f"[AutoClassify] Audit log failed (non-critical): {audit_exc}"
            )

    logger.info(
        f"[AutoClassify] doc={doc_id} classified as '{result.document_type}' "
        f"(confidence={result.confidence:.2f})"
    )


# _infer_category extracted to utils/category_inference.infer_category
# — shared with user_documents_routes.py so the two callers can't drift.
