"""
Async helper for document hash lookups from gemini_document_processor.

Wraps pool acquisition + repository call to keep the processor clean.
"""
from typing import List, Dict, Any
from uuid import UUID

from loguru import logger


async def find_documents_by_hash(
    file_hash: str,
    request_id: str
) -> List[Dict[str, Any]]:
    """Find documents with matching hash, excluding the current request.

    Uses get_db_pool() directly to avoid passing connections through
    the synchronous RiskAnalyzer layer.
    """
    from app.database.connection import get_db_pool
    from app.modules.service_requests.repositories.document_repository import (
        document_repository,
    )

    req_uuid = None
    try:
        req_uuid = UUID(request_id)
    except (ValueError, AttributeError):
        pass

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await document_repository.find_by_hash(
            conn, file_hash, exclude_request_id=req_uuid
        )
