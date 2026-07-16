"""Pydantic schemas for the location module (Site Create/Update)."""

from __future__ import annotations

import re
from datetime import date as _date
from typing import Any

from pydantic import BaseModel, Field, field_validator

_CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$"

# --- operating_hours: canonical-form normalization + validation ------------
# Mirrors packages/web/src/components/ui/weekly-hours.ts (Task 1) exactly:
# the frontend widget is the UX mirror, this module is the authority — a
# shape that would fail `isValid`/`normalize` there must 422 here.

_RANGE_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_MAX_EXCEPTIONS = 366


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _covered(r: str) -> list[tuple[int, int]]:
    f, t = r.split("-")
    a, b = _to_min(f), _to_min(t)
    return [(a, b)] if a < b else [(a, 1440), (0, b)]


def _ranges_overlap(a: str, b: str) -> bool:
    return any(a0 < b1 and b0 < a1 for a0, a1 in _covered(a) for b0, b1 in _covered(b))


def _norm_day(v: Any) -> dict | None:
    if isinstance(v, list):
        rs = [x for x in v if isinstance(x, str)]
        return {"ranges": rs} if rs else {"closed": True}
    if isinstance(v, dict):
        if v.get("h24") is True:
            return {"h24": True}
        if v.get("closed") is True:
            return {"closed": True}
        if isinstance(v.get("ranges"), list):
            return {"ranges": [x for x in v["ranges"] if isinstance(x, str)]}
    return None


def normalize_operating_hours(v: Any) -> dict:
    """Old shape `{day: [ranges]}` OR canonical `{weekly, exceptions}` -> canonical."""
    if not isinstance(v, dict):
        return {"weekly": {}, "exceptions": []}
    weekly: dict = {}
    if "weekly" in v or "exceptions" in v:
        w = v.get("weekly") if isinstance(v.get("weekly"), dict) else {}
        for day in _DAYS:
            if day not in w:
                continue
            d = _norm_day(w[day])
            # Day key present but unrecognized shape (e.g. {"nope": True}):
            # pass the raw value through so _validate_day rejects it below,
            # instead of silently dropping it (which would normalize a
            # malformed payload down to "no restriction").
            weekly[day] = d if d is not None else w[day]
        exceptions = []
        for raw in v.get("exceptions") or []:
            if isinstance(raw, dict) and isinstance(raw.get("date"), str):
                d = _norm_day(raw)
                if d is None:
                    d = {k: val for k, val in raw.items() if k != "date"}
                exceptions.append({"date": raw["date"], **d})
        return {"weekly": weekly, "exceptions": exceptions}
    for day in _DAYS:
        if day not in v:
            continue
        d = _norm_day(v[day])
        if d is None:
            # Day key present but unrecognized shape (e.g. {"foo": "bar"}):
            # pass the raw value through so _validate_day rejects it below,
            # instead of silently dropping it (which would normalize a
            # malformed payload down to "no restriction"). Mirrors the
            # canonical branch above.
            weekly[day] = v[day]
        elif "closed" not in d:
            weekly[day] = d
    return {"weekly": weekly, "exceptions": []}


def _validate_day(d: Any) -> None:
    if d in ({"closed": True}, {"h24": True}):
        return
    if not isinstance(d, dict):
        raise ValueError(f"invalid day schedule {d!r}")
    ranges = d.get("ranges")
    if not isinstance(ranges, list) or "closed" in d or "h24" in d:
        raise ValueError(f"invalid day schedule {d!r}")
    for r in ranges:
        m = _RANGE_RE.match(r) if isinstance(r, str) else None
        if not m:
            raise ValueError(f"invalid range {r!r}")
        f, t = r.split("-")
        if _to_min(f) == _to_min(t):
            raise ValueError(f"empty range {r!r}")
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            if _ranges_overlap(ranges[i], ranges[j]):
                raise ValueError(f"overlapping ranges {ranges[i]!r}/{ranges[j]!r}")


def _validate_operating_hours(oh: dict) -> None:
    for day, d in oh["weekly"].items():
        if day not in _DAYS:
            raise ValueError(f"unknown day {day!r}")
        _validate_day(d)
    if len(oh["exceptions"]) > _MAX_EXCEPTIONS:
        raise ValueError("too many exceptions")
    seen: set[str] = set()
    for e in oh["exceptions"]:
        d = e["date"]
        # Gate with the same regex as the front mirror (weekly-hours.ts
        # ISO_DATE_RE) FIRST: Python 3.11+'s date.fromisoformat also accepts
        # "20260101"/"2026-W01-1" (basic ISO / week-date forms) which the
        # front rejects on read-back — reject those here before the
        # calendar-validity check.
        if not isinstance(d, str) or not _ISO_DATE_RE.match(d):
            raise ValueError(f"invalid exception date {d!r}")
        try:
            _date.fromisoformat(d)
        except ValueError as exc:
            raise ValueError(f"invalid exception date {d!r}") from exc
        if d in seen:
            raise ValueError(f"duplicate exception date {d!r}")
        seen.add(d)
        _validate_day({k: v for k, v in e.items() if k != "date"})


def _oh_validator(cls, v):  # noqa: ARG001 - cls required by field_validator signature
    """Shared before-validator wired onto SiteCreate AND SiteUpdate (DRY, single impl)."""
    if v is None:  # SiteUpdate.operating_hours is optional
        return v
    oh = normalize_operating_hours(v)
    _validate_operating_hours(oh)
    return oh


class SiteCreate(BaseModel):
    organization_id: str
    org_unit_id: str | None = None
    parent_site_id: str | None = None
    code: str = Field(..., pattern=_CODE)
    name: str = Field(..., min_length=1, max_length=255)
    site_type: str = Field("branch", max_length=40)
    address_id: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = Field(None, max_length=120)
    region: str | None = Field(None, max_length=120)
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = Field(None, max_length=20)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    operating_hours: dict = Field(default_factory=dict, validate_default=True)
    timezone: str | None = Field(None, max_length=64)
    is_primary: bool = False
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)
    # User-defined fields (SP1) — allowlisted against `site.custom_fields`.
    custom_fields: dict = Field(default_factory=dict)
    # Optional issuer-identity override (SP1 D1) — allowlisted against
    # `site.document_identity` (product_schemas.DOCUMENT_IDENTITY_OVERRIDE).
    document_identity: dict = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return v.strip()

    @field_validator("country_code")
    @classmethod
    def _upper_cc(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("org_unit_id", "parent_site_id", "address_id", mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v

    _validate_hours = field_validator("operating_hours", mode="before")(classmethod(_oh_validator))


class SiteUpdate(BaseModel):
    """All optional; `code` and `organization_id` are immutable."""
    org_unit_id: str | None = None
    parent_site_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    site_type: str | None = Field(None, max_length=40)
    address_id: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    postal_code: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = None
    email: str | None = None
    operating_hours: dict | None = None
    timezone: str | None = None
    is_primary: bool | None = None
    notes: str | None = None
    metadata: dict | None = None
    custom_fields: dict | None = None
    document_identity: dict | None = None
    is_active: bool | None = None

    @field_validator("org_unit_id", "parent_site_id", "address_id", mode="before")
    @classmethod
    def _blank_fk_to_none(cls, v: object) -> object:
        return None if v == "" else v

    _validate_hours = field_validator("operating_hours", mode="before")(classmethod(_oh_validator))
