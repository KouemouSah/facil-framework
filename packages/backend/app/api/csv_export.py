"""Shared tabular export helpers (CSV + XLSX) — backlog ERP, DRY across tables.

Builds an attachment Response from a list of `as_dict()`-able rows and an ordered
column list. Capped to keep exports bounded; `X-Truncated` reports when the match
set exceeded the cap (no silent truncation). `export_response` dispatches on a
`format` (csv|xlsx) so every resource exposes both with one call.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from fastapi import Response

EXPORT_CAP = 10_000

_CSV_MEDIA = "text/csv"
_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


#: Leading characters that trigger formula evaluation in Excel/Sheets (CWE-1236).
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> object:
    """Normalise a cell for export: None -> "", numeric/bool primitives pass
    through (so xlsx keeps typed cells), everything else is stringified. A string
    beginning with a formula-trigger character is prefixed with a single quote so
    it opens as inert text, not an executed formula (CWE-1236 CSV injection)."""
    if value is None:
        return ""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    if text[:1] in _FORMULA_TRIGGERS:
        return "'" + text
    return text


def _truncation_headers(filename: str, rows_len: int, total: int | None) -> dict:
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    if total is not None and total > rows_len:
        headers["X-Truncated"] = f"{rows_len}/{total}"
    return headers


def csv_response(rows: Sequence, columns: Sequence[str], filename: str,
                 total: int | None = None) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        d = r.as_dict()
        writer.writerow([_cell(d.get(c, "")) for c in columns])
    headers = _truncation_headers(filename, len(rows), total)
    return Response(content=buf.getvalue(), media_type=_CSV_MEDIA, headers=headers)


def xlsx_response(rows: Sequence, columns: Sequence[str], filename: str,
                  total: int | None = None) -> Response:
    """Build a real .xlsx workbook (typed cells, frozen header row)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(columns))
    ws.freeze_panes = "A2"  # keep the header visible while scrolling
    for r in rows:
        d = r.as_dict()
        ws.append([_cell(d.get(c, "")) for c in columns])
    buf = io.BytesIO()
    wb.save(buf)
    headers = _truncation_headers(filename, len(rows), total)
    return Response(content=buf.getvalue(), media_type=_XLSX_MEDIA, headers=headers)


def export_response(rows: Sequence, columns: Sequence[str], base_filename: str,
                    fmt: str = "csv", total: int | None = None) -> Response:
    """Dispatch to CSV or XLSX. `base_filename` carries no extension; the chosen
    format appends it. Any value other than 'xlsx' falls back to CSV."""
    if fmt == "xlsx":
        return xlsx_response(rows, columns, f"{base_filename}.xlsx", total=total)
    return csv_response(rows, columns, f"{base_filename}.csv", total=total)
