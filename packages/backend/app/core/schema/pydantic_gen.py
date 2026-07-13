"""Descriptor → server-side validation.

One descriptor, two consumers: this module (server, authoritative) and
`web/src/lib/schema/to-zod.ts` (client, reflection). Hand-rolled rather than a
dynamic `create_model`: the field set is dynamic and per-organisation, so a
cached pydantic class per (org, target) would churn; a direct pass is simpler,
allocation-free and yields the exact 422 shape the API needs.
"""

from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.schema.conditions import is_required, is_visible


class SchemaViolation(Exception):
    """Carries pydantic-shaped errors so the API can emit a 422 that RecordForm
    maps back onto the offending field (`ApiError.fieldErrors()`)."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} schema violation(s)")


def _err(key: str, msg: str) -> dict[str, Any]:
    return {"loc": [key], "msg": msg, "type": "schema_violation"}


def _coerce(spec: dict[str, Any], value: Any, out: list[dict[str, Any]]) -> Any:
    key, ftype, rules = spec["key"], spec["type"], spec.get("rules") or {}

    if ftype in ("string", "text", "richtext"):
        if not isinstance(value, str):
            out.append(_err(key, "must be a string")); return None
        if "max_length" in rules and len(value) > rules["max_length"]:
            out.append(_err(key, f"at most {rules['max_length']} characters"))
        if "min_length" in rules and len(value) < rules["min_length"]:
            out.append(_err(key, f"at least {rules['min_length']} characters"))
        if "pattern" in rules and not re.match(rules["pattern"], value):
            out.append(_err(key, "invalid format"))
        return value

    if ftype in ("number", "decimal"):
        try:
            num = Decimal(str(value))
        except (InvalidOperation, TypeError):
            out.append(_err(key, "must be a number")); return None
        if "min" in rules and num < Decimal(str(rules["min"])):
            out.append(_err(key, f"must be ≥ {rules['min']}"))
        if "max" in rules and num > Decimal(str(rules["max"])):
            out.append(_err(key, f"must be ≤ {rules['max']}"))
        return int(num) if ftype == "number" and num == num.to_integral_value() else str(num)

    if ftype == "money":
        # Object, and the amount is a DECIMAL STRING — never a float. A float
        # amount silently rounds money in binary; that is not acceptable.
        if not isinstance(value, dict) or "amount" not in value or "currency" not in value:
            out.append(_err(key, "must be {amount, currency}")); return None
        if not isinstance(value["amount"], str):
            out.append(_err(key, "amount must be a decimal STRING (no float — binary rounding)"))
            return None
        try:
            Decimal(value["amount"])
        except InvalidOperation:
            out.append(_err(key, "amount is not a valid decimal")); return None
        if not isinstance(value["currency"], str) or len(value["currency"]) != 3:
            out.append(_err(key, "currency must be a 3-letter code")); return None
        return {"amount": value["amount"], "currency": value["currency"].upper()}

    if ftype == "boolean":
        if not isinstance(value, bool):
            out.append(_err(key, "must be a boolean")); return None
        return value

    if ftype in ("date", "datetime", "time"):
        parser = {"date": _dt.date.fromisoformat,
                  "datetime": _dt.datetime.fromisoformat,
                  "time": _dt.time.fromisoformat}[ftype]
        if not isinstance(value, str):
            out.append(_err(key, "must be an ISO-8601 string")); return None
        try:
            parser(value)
        except ValueError:
            out.append(_err(key, f"must be a valid ISO-8601 {ftype}")); return None
        return value

    if ftype == "select":
        allowed = {o["value"] for o in spec.get("options") or []}
        if value not in allowed:
            out.append(_err(key, f"must be one of {sorted(allowed)}")); return None
        return value

    if ftype == "multiselect":
        allowed = {o["value"] for o in spec.get("options") or []}
        if not isinstance(value, list) or any(v not in allowed for v in value):
            out.append(_err(key, f"must be a subset of {sorted(allowed)}")); return None
        return value

    if ftype in ("relation", "file"):
        if not isinstance(value, str):
            out.append(_err(key, "must be an id/URL string")); return None
        return value

    if ftype == "json":
        return value  # opaque by design — the documented escape hatch

    out.append(_err(key, f"unsupported type {ftype!r}"))  # unreachable
    return None


def validate_blob(specs: list[dict[str, Any]], values: dict[str, Any]) -> dict[str, Any]:
    """Validate a JSON blob against its resolved schema. Raises SchemaViolation.

    The schema IS the allowlist: an undeclared key is REJECTED, never dropped.
    """
    by_key = {s["key"]: s for s in specs}
    errors: list[dict[str, Any]] = []

    for key in values:
        if key not in by_key:
            errors.append(_err(key, f"key {key!r} is not declared in this schema"))
    if errors:
        raise SchemaViolation(errors)

    clean: dict[str, Any] = {}
    for spec in specs:
        key = spec["key"]
        present = key in values

        if not is_visible(spec, values):
            if present:
                errors.append(_err(key, "field is not visible under the current values"))
            continue
        if not present or values[key] in (None, ""):
            if is_required(spec, values):
                errors.append(_err(key, "field is required"))
            continue
        coerced = _coerce(spec, values[key], errors)
        if coerced is not None:
            clean[key] = coerced

    if errors:
        raise SchemaViolation(errors)
    return clean
