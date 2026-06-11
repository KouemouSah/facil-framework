"""
Dynamic Few-Shot Retriever — retrieve similar past successful queries for Gemini prompting.

Architecture (dual-mode):
    Mode A (pgvector): If embeddings exist in agent_query_logs, use Vertex AI embedding
        + pgvector cosine distance (<=> operator) for SEMANTIC similarity.
        Understands "plata" ~ "dinero" ~ "ingresos".
    Mode B (TF-IDF): Fallback when embeddings not yet populated (cold start).
        Uses IntentClassifier's TF-IDF vectorizer for LEXICAL similarity.
        ~1ms in-memory, no API call.

Cold start: < MIN_EXAMPLES successful logs → return empty (no few-shot).
All exceptions are swallowed — few-shot is enhancement, never blocks response.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.jsonb import ensure_list

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from app.modules.shared.services.nlp_preprocessor import (
    _intent_classifier,
    _SKLEARN_AVAILABLE,
    normalize_text,
)

# Minimum successful logs before few-shot kicks in
MIN_EXAMPLES = 10

# Number of similar examples to inject
TOP_K = 3

# Cache TTL: 1 hour (logs don't change fast enough to need real-time)
CACHE_TTL = 3600

# Max examples to fetch from DB (performance guard)
MAX_FETCH = 500

# Minimum similarity threshold (filter noise)
MIN_SIMILARITY = 0.1


@dataclass
class FewShotExample:
    """A past successful question with its ground truth intent and tools used."""
    question: str
    intent: str
    tools_used: List[str]
    similarity: float


# ── Mode A: pgvector semantic similarity ─────────────────────────────────────

async def _fetch_similar_pgvector(
    question: str, agent_type: str
) -> List[FewShotExample]:
    """
    Use Vertex AI embedding + pgvector cosine distance for semantic similarity.
    Returns top-K similar examples, or empty list if embeddings not available.
    """
    try:
        from app.modules.shared.services.embedding_service import get_embedding
        from app.database.connection import db_manager

        # Get embedding for the current question
        query_embedding = await get_embedding(question)
        if not query_embedding:
            return []

        embedding_str = str(query_embedding)

        async with db_manager.get_connection() as conn:
            # Check if we have enough embedded logs
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM agent_query_logs
                WHERE agent_type = $1
                  AND was_successful = TRUE
                  AND ground_truth_intent IS NOT NULL
                  AND embedding IS NOT NULL
                """,
                agent_type,
            )

            if count < MIN_EXAMPLES:
                return []

            # pgvector cosine similarity search
            # 1 - (a <=> b) converts cosine distance to similarity
            rows = await conn.fetch(
                """
                SELECT question, ground_truth_intent, actual_functions_called,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM agent_query_logs
                WHERE agent_type = $2
                  AND was_successful = TRUE
                  AND ground_truth_intent IS NOT NULL
                  AND embedding IS NOT NULL
                  AND created_at > NOW() - INTERVAL '90 days'
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_str,
                agent_type,
                TOP_K,
            )

            examples = []
            for row in rows:
                sim = float(row["similarity"])
                if sim < MIN_SIMILARITY:
                    break
                examples.append(FewShotExample(
                    question=row["question"],
                    intent=row["ground_truth_intent"],
                    tools_used=ensure_list(row["actual_functions_called"]),
                    similarity=sim,
                ))

            if examples:
                logger.debug(
                    f"FewShotRetriever(pgvector): {len(examples)} examples "
                    f"(best sim={examples[0].similarity:.3f})"
                )

            return examples

    except Exception as exc:
        logger.debug(f"FewShotRetriever(pgvector): failed (will try TF-IDF): {exc}")
        return []


# ── Mode B: TF-IDF lexical similarity (fallback) ────────────────────────────

async def _fetch_successful_logs(agent_type: str) -> List[Dict[str, Any]]:
    """Fetch recent successful query logs from DB, with Redis cache."""
    cache_key = f"fewshot:logs:{agent_type}"

    try:
        from app.core.cache import get_cache
        cache = get_cache()
        cached = await cache.get(cache_key)
        if cached and isinstance(cached, str):
            return json.loads(cached)
    except Exception:
        pass

    try:
        from app.database.connection import db_manager

        async with db_manager.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT question, ground_truth_intent, actual_functions_called
                FROM agent_query_logs
                WHERE agent_type = $1
                  AND was_successful = TRUE
                  AND ground_truth_intent IS NOT NULL
                  AND created_at > NOW() - INTERVAL '90 days'
                ORDER BY created_at DESC
                LIMIT $2
                """,
                agent_type,
                MAX_FETCH,
            )

        logs = [
            {
                "question": row["question"],
                "intent": row["ground_truth_intent"],
                "tools": ensure_list(row["actual_functions_called"]),
            }
            for row in rows
        ]

        # Cache for 1 hour
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            await cache.set(cache_key, json.dumps(logs), ttl=CACHE_TTL)
        except Exception:
            pass

        return logs
    except Exception as exc:
        logger.debug(f"FewShotRetriever: DB fetch failed (non-fatal): {exc}")
        return []


def _compute_similarities(
    query: str, logs: List[Dict[str, Any]]
) -> List[Tuple[int, float]]:
    """
    Compute cosine similarities between query and log questions using TF-IDF.

    Uses the IntentClassifier's TF-IDF vectorizer (already trained on 500+ seeds).
    Returns: sorted list of (index, similarity) descending.
    """
    if not _SKLEARN_AVAILABLE or not _NUMPY_AVAILABLE:
        return []

    pipeline = _intent_classifier._pipeline
    if pipeline is None:
        return []

    try:
        tfidf = pipeline.named_steps["tfidf"]

        # Normalize all texts consistently
        query_norm = normalize_text(query)
        log_texts = [normalize_text(log["question"]) for log in logs]

        # Transform query and all logs in one batch
        all_texts = [query_norm] + log_texts
        vectors = tfidf.transform(all_texts)

        # Cosine similarity: query (row 0) vs all logs (rows 1..N)
        query_vec = vectors[0]
        log_vectors = vectors[1:]

        norm_q = float(query_vec.multiply(query_vec).sum() ** 0.5)
        if norm_q < 1e-10:
            return []

        similarities = []
        for i in range(log_vectors.shape[0]):
            log_vec = log_vectors[i]
            dot = float(query_vec.multiply(log_vec).sum())
            norm_l = float(log_vec.multiply(log_vec).sum() ** 0.5)
            if norm_l < 1e-10:
                similarities.append((i, 0.0))
            else:
                sim = dot / (norm_q * norm_l)
                similarities.append((i, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities
    except Exception as exc:
        logger.debug(f"FewShotRetriever(TF-IDF): similarity failed: {exc}")
        return []


async def _fetch_similar_tfidf(
    question: str, agent_type: str
) -> List[FewShotExample]:
    """TF-IDF fallback when pgvector embeddings are not available."""
    logs = await _fetch_successful_logs(agent_type)
    if len(logs) < MIN_EXAMPLES:
        return []

    similarities = _compute_similarities(question, logs)
    if not similarities:
        return []

    examples = []
    for idx, sim in similarities[:TOP_K]:
        if sim < MIN_SIMILARITY:
            break
        log = logs[idx]
        examples.append(FewShotExample(
            question=log["question"],
            intent=log["intent"],
            tools_used=log["tools"],
            similarity=sim,
        ))

    if examples:
        logger.debug(
            f"FewShotRetriever(TF-IDF): {len(examples)} examples "
            f"(best sim={examples[0].similarity:.3f})"
        )

    return examples


# ── Public API ───────────────────────────────────────────────────────────────

async def get_few_shot_examples(
    question: str, agent_type: str
) -> List[FewShotExample]:
    """
    Retrieve top-K most similar past successful queries as few-shot examples.

    Strategy:
      1. Try pgvector (semantic) — best quality, requires embeddings
      2. Fall back to TF-IDF (lexical) — always available with sklearn

    Returns empty list if:
    - < MIN_EXAMPLES successful logs (cold start)
    - sklearn/numpy not available AND pgvector fails
    - Any error (graceful degradation)
    """
    try:
        # Mode A: pgvector (semantic similarity via Vertex AI embeddings)
        examples = await _fetch_similar_pgvector(question, agent_type)
        if examples:
            return examples

        # Mode B: TF-IDF fallback (lexical similarity)
        return await _fetch_similar_tfidf(question, agent_type)

    except Exception as exc:
        logger.debug(f"FewShotRetriever: get_few_shot_examples failed (non-fatal): {exc}")
        return []


def format_few_shot_prompt(examples: List[FewShotExample]) -> str:
    """
    Format few-shot examples as a prompt section for Gemini.

    Example output:
        [EJEMPLOS SIMILARES EXITOSOS]
        - "Resumen de ingresos del mes" → intent: revenue, tools: get_revenue_summary
        - "¿Hay pagos vencidos?" → intent: sla, tools: get_pending_payments_sla
    """
    if not examples:
        return ""

    lines = ["[EJEMPLOS SIMILARES EXITOSOS]"]
    for ex in examples:
        tools_str = ", ".join(ex.tools_used[:3]) if ex.tools_used else "N/A"
        lines.append(
            f'- "{ex.question[:80]}" → intent: {ex.intent}, '
            f"tools: {tools_str}"
        )
    lines.append("")
    return "\n".join(lines)
