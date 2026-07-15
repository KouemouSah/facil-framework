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


def _today_utc() -> _dt.date:
    return _dt.datetime.now(_dt.timezone.utc).date()


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


def _resolve_dt_bound(ftype: str, b: Any, parser: Any) -> Any:
    if ftype == "date" and b == "today":
        return _today_utc()
    if ftype == "datetime" and b == "now":
        return _now_utc()
    return parser(b)  # ISO string of the same type


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
        if "step" in rules:
            step = Decimal(str(rules["step"]))
            if step > 0 and (num % step) != 0:
                out.append(_err(key, f"must be a multiple of {rules['step']}"))
        if ftype == "number":
            # `number` IS an integer (see types.py) — `decimal` is the type that
            # carries precision in `rules` and is stored as a decimal string.
            # A non-integral value here is a real type violation, not something
            # to silently stringify.
            if num != num.to_integral_value():
                out.append(_err(key, "must be a whole number")); return None
            return int(num)
        if "precision" in rules:
            exp = num.as_tuple().exponent
            places = -exp if isinstance(exp, int) and exp < 0 else 0
            if places > rules["precision"]:
                out.append(_err(key, f"at most {rules['precision']} decimal places"))
        return str(num)

    if ftype == "money":
        # Object, and the amount is a DECIMAL STRING — never a float. A float
        # amount silently rounds money in binary; that is not acceptable.
        if not isinstance(value, dict) or "amount" not in value or "currency" not in value:
            out.append(_err(key, "must be {amount, currency}")); return None
        if not isinstance(value["amount"], str):
            out.append(_err(key, "amount must be a decimal STRING (no float — binary rounding)"))
            return None
        try:
            amt = Decimal(value["amount"])
        except InvalidOperation:
            out.append(_err(key, "amount is not a valid decimal")); return None
        if not isinstance(value["currency"], str) or len(value["currency"]) != 3:
            out.append(_err(key, "currency must be a 3-letter code")); return None
        if "min" in rules and amt < Decimal(str(rules["min"])):
            out.append(_err(key, f"amount must be ≥ {rules['min']}"))
        if "max" in rules and amt > Decimal(str(rules["max"])):
            out.append(_err(key, f"amount must be ≤ {rules['max']}"))
        return {"amount": value["amount"], "currency": value["currency"].upper()}

    if ftype == "boolean":
        if not isinstance(value, bool):
            out.append(_err(key, "must be a boolean")); return None
        if rules.get("must_be_true") and value is not True:
            out.append(_err(key, "must be accepted"))
        return value

    if ftype in ("date", "datetime", "time"):
        parser = {"date": _dt.date.fromisoformat,
                  "datetime": _dt.datetime.fromisoformat,
                  "time": _dt.time.fromisoformat}[ftype]
        if not isinstance(value, str):
            out.append(_err(key, "must be an ISO-8601 string")); return None
        try:
            parsed = parser(value)
        except ValueError:
            out.append(_err(key, f"must be a valid ISO-8601 {ftype}")); return None
        # A bound is descriptor-authored, not user input — but a bad token
        # (e.g. "now" on a `date`) or a malformed static bound must still map
        # onto a clean 422, never escape as a raw ValueError → HTTP 500.
        for bkey, sym in (("min", "≥"), ("max", "≤")):
            if bkey not in rules:
                continue
            try:
                bound = _resolve_dt_bound(ftype, rules[bkey], parser)
            except ValueError:
                out.append(_err(key, f"invalid {bkey} bound {rules[bkey]!r}")); continue
            if (bkey == "min" and parsed < bound) or (bkey == "max" and parsed > bound):
                out.append(_err(key, f"must be {sym} {rules[bkey]}"))
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
        n = len(value)
        if "min_items" in rules and n < rules["min_items"]:
            out.append(_err(key, f"select at least {rules['min_items']}"))
        if "max_items" in rules and n > rules["max_items"]:
            out.append(_err(key, f"select at most {rules['max_items']}"))
        return value

    if ftype in ("relation", "file"):
        if not isinstance(value, str):
            out.append(_err(key, "must be an id/URL string")); return None
        if ftype == "file" and rules.get("allowed_extensions"):
            exts = [str(e).lower().lstrip(".") for e in rules["allowed_extensions"]]
            ext = value.rsplit(".", 1)[-1].lower() if "." in value else ""
            if ext not in exts:
                out.append(_err(key, f"must be one of {exts}"))
        return value

    if ftype == "json":
        return value  # opaque by design — the documented escape hatch

    out.append(_err(key, f"unsupported type {ftype!r}"))  # unreachable
    return None


def validate_blob(specs: list[dict[str, Any]], values: dict[str, Any]) -> dict[str, Any]:
    """Validate a JSON blob against its resolved schema. Raises SchemaViolation.

    The schema IS the allowlist: an undeclared key is REJECTED, never dropped.

    All errors are accumulated in ONE pass and raised together (ERP standard:
    a 422 maps every error onto its field in a single round trip — see
    RecordForm's `ApiError.fieldErrors()`). Undeclared keys do NOT short-circuit
    the per-field loop below: that loop iterates over `specs`, not `values`, and
    `visible_if`/`required_if` only ever reference DECLARED fields, so an
    unknown key cannot corrupt condition evaluation.

    CLEAR sentinel: `""` / `None` on a declared, visible, non-required field is
    NOT a silent drop — it is how a field is emptied. The frontend
    `RecordForm.buildPayload()` sends `null` to clear a field
    (`packages/web/src/components/ui/record-form.tsx:149`, "Blank → null
    uniformly"). A later `merge_blob` computes `{**preserved, **clean}`, so a
    declared key deliberately absent from `clean` is REMOVED from the stored
    blob — that removal IS the clear operation. A `required` visible field sent
    empty is still rejected (see the `is_required` check below).
    """
    by_key = {s["key"]: s for s in specs}
    errors: list[dict[str, Any]] = []

    for key in values:
        if key not in by_key:
            errors.append(_err(key, f"key {key!r} is not declared in this schema"))

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
