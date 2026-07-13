"""Merge a validated patch into an existing JSON blob.

Strict on input, tolerant on what is already stored:
  * a key arriving in the REQUEST that is not declared  → 422 (SchemaViolation)
  * a key already IN THE DB that is not declared        → preserved untouched

This is what lets us impose an allowlist on data that was never validated,
without a 422 avalanche on historic rows — and without destroying them.
"""

from __future__ import annotations

from typing import Any

from app.core.schema.pydantic_gen import validate_blob


def merge_blob(existing: dict[str, Any], incoming: dict[str, Any],
               specs: list[dict[str, Any]]) -> dict[str, Any]:
    clean = validate_blob(specs, incoming)          # raises SchemaViolation
    declared = {s["key"] for s in specs}
    preserved = {k: v for k, v in (existing or {}).items() if k not in declared}
    return {**preserved, **clean}
