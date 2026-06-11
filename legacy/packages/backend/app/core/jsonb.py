"""
JSONB helpers — defensive parsing for asyncpg JSONB columns.

asyncpg may return JSONB columns as Python dicts/lists OR as JSON strings
depending on driver version, connection pooling, and column type inference.
The `or []` / `or {}` pattern fails because non-empty strings are truthy.

Usage:
    from app.core.jsonb import ensure_list, ensure_dict

    data = ensure_list(row["my_jsonb_array"])   # always returns list
    data = ensure_dict(row["my_jsonb_object"])  # always returns dict
"""

import json
from typing import Any


def ensure_list(val: Any) -> list:
    """Ensure JSONB value is a Python list."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def ensure_dict(val: Any) -> dict:
    """Ensure JSONB value is a Python dict."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
