"""FieldSpec — the single declarative field descriptor.

One source, two consumers: pydantic (server, authoritative) and zod (client,
reflection). A descriptor is validated the moment it is built, so a malformed
product schema fails at IMPORT time, never at request time.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schema.types import (
    DEFAULT_WIDGET, FIELD_TYPES, INDEXABLE_TYPES, LEGACY_TYPE_ALIASES,
    WIDGETS_BY_TYPE,
)

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
LOCALES = ("en", "fr", "es")
CONDITION_OPS = ("eq", "ne", "in")


class FieldSpec(BaseModel):
    key: str
    type: str = "string"
    widget: str = ""
    label: dict[str, str]
    hint: dict[str, str] = Field(default_factory=dict)
    required: bool = False
    default: Any = None
    rules: dict[str, Any] = Field(default_factory=dict)
    options: list[dict[str, Any]] = Field(default_factory=list)
    relation_resource: str = ""
    relation_filter: dict[str, str] = Field(default_factory=dict)
    group: str = ""
    order: int = 0
    col_span: int = 1
    indexed: bool = False
    # Runtime state, NOT a declarative attribute: it is set by the indexing job,
    # never by the author of the field. It lives here because `sortable_keys()`
    # (indexing.py) reads it off the resolved spec — `indexed` alone is not
    # enough to allow a sort; the index must actually be READY.
    index_state: str = "none"

    @field_validator("key")
    @classmethod
    def _key_shape(cls, v: str) -> str:
        if not KEY_RE.match(v):
            raise ValueError(
                f"key {v!r} must match {KEY_RE.pattern} (snake_case, ≤60 chars)")
        return v

    @field_validator("label")
    @classmethod
    def _label_localised(cls, v: dict[str, str]) -> dict[str, str]:
        missing = [loc for loc in LOCALES if not v.get(loc)]
        if missing:
            raise ValueError(f"label must provide en, fr and es (missing: {missing})")
        return v

    @model_validator(mode="after")
    def _coherent(self) -> FieldSpec:
        if self.type not in FIELD_TYPES:
            raise ValueError(f"unknown field type {self.type!r}; one of {FIELD_TYPES}")
        if self.widget not in WIDGETS_BY_TYPE[self.type]:
            raise ValueError(
                f"widget {self.widget!r} is not valid for type {self.type!r}; "
                f"one of {WIDGETS_BY_TYPE[self.type]}")
        if self.indexed and self.type not in INDEXABLE_TYPES:
            raise ValueError(
                f"type {self.type!r} cannot be indexed (blob types are not sortable)")
        if self.type in ("select", "multiselect") and not self.options:
            raise ValueError(f"{self.type} requires options")
        if self.type == "relation" and not self.relation_resource:
            raise ValueError("relation requires relation_resource")
        for cond in ("visible_if", "required_if"):
            rule = self.rules.get(cond)
            if rule is None:
                continue
            if not isinstance(rule, dict) or "field" not in rule:
                raise ValueError(f"{cond} must be {{field, op, value}}")
            if rule.get("op") not in CONDITION_OPS:
                raise ValueError(f"{cond}.op must be one of {CONDITION_OPS}")
        return self


def field(key: str, label: dict[str, str], *, type: str = "string",
          widget: str = "", **kw: Any) -> dict[str, Any]:
    """Declare one field. Returns a plain dict (the wire format the registry and
    the providers already speak) — validated eagerly, so a bad descriptor blows
    up at import, not in production."""
    ftype, alias_widget = LEGACY_TYPE_ALIASES.get(type, (type, ""))
    if ftype not in FIELD_TYPES:
        raise ValueError(f"unknown field type {type!r}; one of {FIELD_TYPES}")
    resolved_widget = widget or alias_widget or DEFAULT_WIDGET[ftype]
    spec = FieldSpec.model_validate(
        {"key": key, "type": ftype, "widget": resolved_widget, "label": label, **kw})
    return spec.model_dump()
