"""visible_if / required_if — pure evaluation, mirrored client-side.

The SERVER is authoritative. A field hidden client-side but posted anyway is
rejected; a field hidden and omitted is accepted even when `required`.
Without the server half, conditional logic is trivially bypassed.
"""

from __future__ import annotations

from typing import Any


def _matches(rule: dict[str, Any] | None, values: dict[str, Any]) -> bool:
    if not rule:
        return True
    actual = values.get(rule["field"])
    expected = rule.get("value")
    op = rule.get("op")
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    return True  # unreachable: spec.py validates `op` at declaration time


def is_visible(spec: dict[str, Any], values: dict[str, Any]) -> bool:
    return _matches((spec.get("rules") or {}).get("visible_if"), values)


def is_required(spec: dict[str, Any], values: dict[str, Any]) -> bool:
    if not is_visible(spec, values):
        return False           # invisible ⇒ never required
    if spec.get("required"):
        return True
    rules = spec.get("rules") or {}
    if "required_if" not in rules:
        return False
    return _matches(rules["required_if"], values)
