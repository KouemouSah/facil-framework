"""
NLP Intent Classifier — Weekly Auto-Retrain Service.

Called by Cloud Scheduler cron (Sunday 02:00 UTC).
Pipeline:
  1. Fetch last 90 days of agent_query_logs with ground_truth_intent
  2. Cold start guard: < 50 samples → skip (seeds are sufficient)
  3. Combine seed data (1×) + real data (3×) → retrain TF-IDF + LR
  4. Evaluate on held-out 20% split → report accuracy
  5. Save retrained model to Redis (7-day TTL)
  6. All running Cloud Run instances pick up new model on next request

Design: the classifier already has retrain() + save_to_redis() + load_from_redis().
This service is the orchestrator — fetch data, evaluate, call those methods.
"""

import json
import random
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Minimum samples to retrain (below this, seed model is good enough)
MIN_SAMPLES_FOR_RETRAIN = 50


async def retrain_nlp_classifier() -> Dict[str, Any]:
    """
    Orchestrate full retrain pipeline.

    Returns a report dict with:
      - status: "retrained" | "skipped_cold_start" | "skipped_no_sklearn" | "error"
      - n_real_samples, n_total_samples, n_intents
      - accuracy (held-out 20%)
      - intent_distribution
      - message
    """
    from app.modules.shared.services.nlp_preprocessor import (
        _intent_classifier,
        _SKLEARN_AVAILABLE,
        normalize_text,
    )

    if not _SKLEARN_AVAILABLE:
        return {
            "status": "skipped_no_sklearn",
            "message": "sklearn not available — retrain impossible",
        }

    # 1. Fetch real training data from agent_query_logs
    try:
        from app.database.connection import db_manager

        async with db_manager.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT question, ground_truth_intent
                FROM agent_query_logs
                WHERE ground_truth_intent IS NOT NULL
                  AND was_successful = TRUE
                  AND created_at > NOW() - INTERVAL '90 days'
                ORDER BY created_at DESC
                LIMIT 10000
                """
            )
    except Exception as exc:
        logger.error(f"Retrain: failed to fetch training data: {exc}")
        return {"status": "error", "message": f"DB fetch failed: {exc}"}

    n_real = len(rows)
    logger.info(f"Retrain: fetched {n_real} labeled examples from agent_query_logs")

    # 2. Cold start guard
    if n_real < MIN_SAMPLES_FOR_RETRAIN:
        return {
            "status": "skipped_cold_start",
            "n_real_samples": n_real,
            "min_required": MIN_SAMPLES_FOR_RETRAIN,
            "message": (
                f"Only {n_real} labeled samples (need {MIN_SAMPLES_FOR_RETRAIN}). "
                f"Seed model is sufficient. Will retry next week."
            ),
        }

    # 3. Prepare data
    real_texts  = [row["question"] for row in rows]
    real_labels = [row["ground_truth_intent"] for row in rows]

    # Deduplicate (same question can appear multiple times)
    seen = set()
    dedup_texts, dedup_labels = [], []
    for t, l in zip(real_texts, real_labels):
        key = (normalize_text(t), l)
        if key not in seen:
            seen.add(key)
            dedup_texts.append(t)
            dedup_labels.append(l)

    n_dedup = len(dedup_texts)
    intent_dist = dict(Counter(dedup_labels).most_common())

    # 4. Held-out evaluation (80/20 split)
    accuracy: Optional[float] = None
    try:
        combined = list(zip(dedup_texts, dedup_labels))
        random.shuffle(combined)
        split_idx = max(1, int(len(combined) * 0.8))
        train_data = combined[:split_idx]
        test_data  = combined[split_idx:]

        if len(test_data) >= 5:
            # Train on train split + seeds, evaluate on test split
            train_texts  = [t for t, _ in train_data]
            train_labels = [l for _, l in train_data]

            # Retrain (updates the singleton classifier in-place)
            pipeline = _intent_classifier.retrain(train_texts, train_labels)
            if pipeline is None:
                return {"status": "error", "message": "retrain() returned None"}

            # Evaluate on held-out set
            test_texts  = [normalize_text(t) for t, _ in test_data]
            test_labels = [l for _, l in test_data]
            predictions = pipeline.predict(test_texts)
            correct = sum(1 for p, t in zip(predictions, test_labels) if p == t)
            accuracy = correct / len(test_labels)

            logger.info(
                f"Retrain eval: {accuracy:.1%} accuracy on {len(test_labels)} held-out samples"
            )

            # Now retrain on ALL data (no held-out) for the production model
            pipeline = _intent_classifier.retrain(dedup_texts, dedup_labels)
            if pipeline is None:
                return {"status": "error", "message": "Final retrain() returned None"}
        else:
            # Not enough for proper eval — retrain on everything
            pipeline = _intent_classifier.retrain(dedup_texts, dedup_labels)
            if pipeline is None:
                return {"status": "error", "message": "retrain() returned None"}
    except Exception as exc:
        logger.error(f"Retrain: training failed: {exc}")
        return {"status": "error", "message": f"Training failed: {exc}"}

    # 5. Save to Redis
    try:
        await _intent_classifier.save_to_redis(pipeline)
    except Exception as exc:
        logger.warning(f"Retrain: Redis save failed (model still active in memory): {exc}")

    # 6. Save metadata to Redis for monitoring
    try:
        from app.core.cache import get_cache

        metadata = {
            "n_real_samples": n_real,
            "n_dedup_samples": n_dedup,
            "accuracy": accuracy,
            "intent_distribution": intent_dist,
            "n_intents": len(intent_dist),
        }
        cache = get_cache()
        await cache.set(
            "nlp:intent_classifier:metadata",
            json.dumps(metadata),
            ttl=8 * 24 * 3600,  # 8 days (survives until next retrain)
        )
    except Exception as exc:
        logger.debug(f"Retrain: metadata save failed (non-critical): {exc}")

    report = {
        "status": "retrained",
        "n_real_samples": n_real,
        "n_dedup_samples": n_dedup,
        "n_intents": len(intent_dist),
        "accuracy": accuracy,
        "intent_distribution": intent_dist,
        "message": (
            f"Retrained on {n_dedup} unique real examples + 524 seeds. "
            f"Accuracy: {accuracy:.1%}." if accuracy else
            f"Retrained on {n_dedup} unique real examples + 524 seeds. "
            f"(insufficient test data for accuracy eval)"
        ),
    }
    logger.info(f"Retrain complete: {report['message']}")
    return report
