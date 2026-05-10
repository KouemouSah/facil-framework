"""
Vertex AI Embedding Service — compute text embeddings for semantic similarity.

Uses textembedding-gecko-multilingual@001 (768-dim, multilingual).
Designed for fire-and-forget embedding of agent queries after logging.

Cache: embeddings cached in Redis (1h TTL) to avoid redundant API calls.
Graceful degradation: if Vertex AI unavailable, returns None (TF-IDF fallback).
"""

import hashlib
import json
from typing import List, Optional

from loguru import logger

from app.config import get_settings

# Embedding model: 768-dim multilingual (supports ES, FR, EN)
MODEL_ID = "text-multilingual-embedding-002"
EMBEDDING_DIM = 768
CACHE_TTL = 3600  # 1 hour

_VERTEX_AVAILABLE = False
try:
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput  # type: ignore
    import vertexai
    _VERTEX_AVAILABLE = True
except ImportError:
    pass


def _cache_key(text: str) -> str:
    """Deterministic cache key for an embedding."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"emb:{h}"


async def get_embedding(text: str) -> Optional[List[float]]:
    """
    Get 768-dim embedding for a text string.

    Pipeline:
      1. Check Redis cache
      2. If miss, call Vertex AI embedding API
      3. Cache result (1h TTL)
      4. Return list of floats or None on failure

    Designed to be called fire-and-forget (never blocks user response).
    """
    if not _VERTEX_AVAILABLE:
        return None

    # 1. Check cache
    cache_k = _cache_key(text)
    try:
        from app.core.cache import get_cache
        cache = get_cache()
        cached = await cache.get(cache_k)
        if cached and isinstance(cached, str):
            return json.loads(cached)
    except Exception:
        pass

    # 2. Call Vertex AI
    try:
        settings = get_settings()
        project = (
            getattr(settings, "VERTEX_AI_PROJECT_ID", None)
            or getattr(settings, "GCP_PROJECT_ID", None)
            or getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
        )
        location = (
            getattr(settings, "VERTEX_AI_LOCATION", None)
            or getattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
        )

        if project:
            vertexai.init(project=project, location=location)

        model = TextEmbeddingModel.from_pretrained(MODEL_ID)

        # Use task_type for better quality
        inputs = [TextEmbeddingInput(text=text[:2048], task_type="RETRIEVAL_QUERY")]
        embeddings = model.get_embeddings(inputs)

        if not embeddings or not embeddings[0].values:
            return None

        vector = embeddings[0].values

        # 3. Cache
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            await cache.set(cache_k, json.dumps(vector), ttl=CACHE_TTL)
        except Exception:
            pass

        return vector

    except Exception as exc:
        logger.debug(f"EmbeddingService: Vertex AI call failed (non-fatal): {exc}")
        return None


async def get_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Batch embedding for multiple texts (more efficient than individual calls).
    Returns list of embeddings (None for any that fail).
    """
    if not _VERTEX_AVAILABLE or not texts:
        return [None] * len(texts)

    try:
        settings = get_settings()
        project = (
            getattr(settings, "VERTEX_AI_PROJECT_ID", None)
            or getattr(settings, "GCP_PROJECT_ID", None)
            or getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
        )
        location = (
            getattr(settings, "VERTEX_AI_LOCATION", None)
            or getattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
        )

        if project:
            vertexai.init(project=project, location=location)

        model = TextEmbeddingModel.from_pretrained(MODEL_ID)
        inputs = [
            TextEmbeddingInput(text=t[:2048], task_type="RETRIEVAL_QUERY")
            for t in texts
        ]
        embeddings = model.get_embeddings(inputs)

        results: List[Optional[List[float]]] = []
        for emb in embeddings:
            if emb and emb.values:
                results.append(emb.values)
            else:
                results.append(None)

        return results

    except Exception as exc:
        logger.debug(f"EmbeddingService: batch embedding failed: {exc}")
        return [None] * len(texts)
