"""Shared CSV export helper (backlog ERP — export across tables, DRY).

Builds a `text/csv` Response with a Content-Disposition attachment from a list of
`as_dict()`-able rows and an ordered column list. Capped to keep exports bounded;
`X-Truncated` reports when the match set exceeded the cap (no silent truncation).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from fastapi import Response

EXPORT_CAP = 10_000


def csv_response(rows: Sequence, columns: Sequence[str], filename: str,
                 total: int | None = None) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        d = r.as_dict()
        writer.writerow([d.get(c, "") for c in columns])
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    if total is not None and total > len(rows):
        headers["X-Truncated"] = f"{len(rows)}/{total}"
    return Response(content=buf.getvalue(), media_type="text/csv", headers=headers)
