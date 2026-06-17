"""Optimistic concurrency via content ETags (backlog ERP item 1).

HTTP `If-Match` semantics, no schema change — works for collection-shaped resources
(branding setting keys, role grants) as well as single rows. The GET returns an
`etag` (a stable hash of the resource state); the client echoes it as `If-Match`
on the mutating request; if it no longer matches the current state, the resource
was changed since the client loaded it (lost-update) → 409.

See docs/ENGINEERING_STANDARDS.md §4.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, Request


def etag_for(value: object) -> str:
    """Stable short hash of any JSON-serialisable value (sorted keys → order
    independent)."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def row_etag(entity: object) -> str:
    """Generic per-row etag for any UUIDAuditBase entity, from (id, updated_at).
    `updated_at` bumps on every UPDATE (ORM and Core), so this is a free, uniform
    concurrency token for single-row resources — no schema change. Used by the
    CRUD layer so every module gets optimistic concurrency the same way."""
    return etag_for({"id": getattr(entity, "id", None),
                     "u": str(getattr(entity, "updated_at", ""))})


def enforce_if_match(request: Request, current: str) -> None:
    """If the caller sent `If-Match`, require it to equal the current etag, else
    409 (the resource changed since they loaded it). Absent header = no check
    (backwards compatible; the web UI always sends it)."""
    provided = request.headers.get("if-match")
    if provided is not None and provided.strip().strip('"') != current:
        raise HTTPException(
            409, "the record was modified by someone else; reload and retry")
