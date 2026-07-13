"""The field contract — pure constants, no logic.

Three orthogonal axes (spec §5):
  TYPE   = storage + comparison + indexability  (15, and they suffice)
  WIDGET = presentation only                    (marginal cost → generous)
  RULES  = declarative validation               (see spec.py)

Admission test for a new TYPE: *does it change storage, comparison or
indexing?* If not, it is a WIDGET, not a type. Odoo ships ~16 types after
20 years; richness comes from widgets, not from type count.
"""

from __future__ import annotations

FIELD_TYPES: tuple[str, ...] = (
    "string", "text", "richtext",
    "number", "decimal", "money",
    "boolean",
    "date", "datetime", "time",
    "select", "multiselect",
    "relation",
    "file",
    "json",
)

WIDGETS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "string": ("plain", "email", "password", "url", "phone", "color",
               "timezone", "badge", "copyable", "masked"),
    "text": ("plain", "code"),
    "richtext": ("editor",),
    "number": ("plain", "percent", "rating", "progress", "slider"),
    "decimal": ("plain", "percent"),
    "money": ("plain",),
    "boolean": ("checkbox", "switch"),
    "date": ("date", "month", "quarter", "year"),
    "datetime": ("datetime",),
    "time": ("time",),
    "select": ("dropdown", "radio", "segmented"),
    "multiselect": ("tags", "checkboxes"),
    "relation": ("combobox", "radio", "cards"),
    "file": ("document", "image", "avatar", "gallery"),
    # `weekly_hours` is the bespoke control that finally pins down
    # Site.operating_hours, whose shape is inconsistent today (spec §12).
    "json": ("raw", "weekly_hours"),
}

DEFAULT_WIDGET: dict[str, str] = {t: w[0] for t, w in WIDGETS_BY_TYPE.items()}

# Blob-ish types cannot be sorted/filtered → `indexed` is refused on them.
INDEXABLE_TYPES: frozenset[str] = frozenset(FIELD_TYPES) - {
    "richtext", "multiselect", "file", "json",
}

# JSONB stores TEXT. Indexing without a typed cast yields a LEXICOGRAPHIC sort
# ("10" < "9") — a silent, ERP-fatal bug. The very same expression must appear
# in ORDER BY / WHERE, or Postgres will not use the index (see indexing.py).
INDEX_CAST: dict[str, str] = {
    "string": "(custom_fields->>'{key}')",
    "text": "(custom_fields->>'{key}')",
    "select": "(custom_fields->>'{key}')",
    "relation": "(custom_fields->>'{key}')",
    "number": "((custom_fields->>'{key}')::numeric)",
    "decimal": "((custom_fields->>'{key}')::numeric)",
    "money": "((custom_fields->'{key}'->>'amount')::numeric)",
    "boolean": "((custom_fields->>'{key}')::boolean)",
    "date": "((custom_fields->>'{key}')::date)",
    "datetime": "((custom_fields->>'{key}')::timestamptz)",
    "time": "((custom_fields->>'{key}')::time)",
}

# RecordForm's original 15 `FieldType`s (record-form.tsx:30-32) that are really
# (type, widget) pairs. Accepted forever as aliases → zero regression on the
# hand-written field lists already in the repo.
#
# NOTE: "text" is DELIBERATELY absent. It is the ONE legacy name that collides:
#   OLD "text" = single-line <Input> → NEW "string" (not "text")
#   NEW "text" = multi-line (← OLD "textarea")
# If we aliased "text" here, field() would consult this table first and silently
# downgrade every NEW multi-line "text" declaration to single-line — a worse bug
# than omitting the alias. The collision is resolved at the BOUNDARY in cfg()'s
# _CFG_TYPE_MAP which maps provider vocabulary names to the new taxonomy.
LEGACY_TYPE_ALIASES: dict[str, tuple[str, str]] = {
    "email": ("string", "email"),
    "password": ("string", "password"),
    "color": ("string", "color"),
    "timezone": ("string", "timezone"),
    "textarea": ("text", "plain"),
    "checkbox": ("boolean", "checkbox"),
    "image": ("file", "image"),
    "org": ("relation", "combobox"),
    "party": ("relation", "combobox"),
    "ref": ("relation", "combobox"),
    "address": ("relation", "combobox"),
}
