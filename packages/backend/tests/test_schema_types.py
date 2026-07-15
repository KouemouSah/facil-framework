"""The field contract: 15 types, widgets per type, index expressions per type."""

from app.core.schema.types import (
    DEFAULT_WIDGET, FIELD_TYPES, INDEXABLE_TYPES, INDEX_CAST,
    LEGACY_TYPE_ALIASES, WIDGETS_BY_TYPE,
)


def test_fifteen_types_exactly():
    assert len(FIELD_TYPES) == 15
    assert set(FIELD_TYPES) == {
        "string", "text", "richtext", "number", "decimal", "money", "boolean",
        "date", "datetime", "time", "select", "multiselect", "relation",
        "file", "json",
    }


def test_every_type_has_widgets_and_a_default_widget():
    for t in FIELD_TYPES:
        assert WIDGETS_BY_TYPE[t], f"{t} declares no widget"
        assert DEFAULT_WIDGET[t] in WIDGETS_BY_TYPE[t]


def test_non_indexable_types_are_exactly_the_blob_types():
    assert INDEXABLE_TYPES == frozenset(FIELD_TYPES) - {
        "richtext", "multiselect", "file", "json",
    }


def test_every_indexable_type_declares_an_index_cast():
    # JSONB stores text. Without a typed cast the sort would be lexicographic
    # ("10" < "9") — a silent, ERP-fatal bug. Every indexable type MUST cast.
    for t in INDEXABLE_TYPES:
        assert t in INDEX_CAST, f"{t} is indexable but declares no cast"
    for t in frozenset(FIELD_TYPES) - INDEXABLE_TYPES:
        assert t not in INDEX_CAST


def test_numeric_and_temporal_casts_are_typed_not_text():
    assert INDEX_CAST["number"] == "((custom_fields->>'{key}')::numeric)"
    assert INDEX_CAST["decimal"] == "((custom_fields->>'{key}')::numeric)"
    assert INDEX_CAST["money"] == "((custom_fields->'{key}'->>'amount')::numeric)"
    assert INDEX_CAST["date"] == "((custom_fields->>'{key}')::date)"
    assert INDEX_CAST["datetime"] == "((custom_fields->>'{key}')::timestamptz)"
    assert INDEX_CAST["time"] == "((custom_fields->>'{key}')::time)"
    assert INDEX_CAST["boolean"] == "((custom_fields->>'{key}')::boolean)"
    assert INDEX_CAST["string"] == "(custom_fields->>'{key}')"


def test_legacy_record_form_types_map_to_type_plus_widget():
    # color/timezone/email/password were TYPES in RecordForm; they become widgets
    # of `string`. Existing values are plain strings → no data migration.
    assert LEGACY_TYPE_ALIASES["color"] == ("string", "color")
    assert LEGACY_TYPE_ALIASES["timezone"] == ("string", "timezone")
    assert LEGACY_TYPE_ALIASES["email"] == ("string", "email")
    assert LEGACY_TYPE_ALIASES["password"] == ("string", "password")
    assert LEGACY_TYPE_ALIASES["image"] == ("file", "image")
    assert LEGACY_TYPE_ALIASES["checkbox"] == ("boolean", "checkbox")
    assert LEGACY_TYPE_ALIASES["textarea"] == ("text", "plain")
    assert LEGACY_TYPE_ALIASES["org"] == ("relation", "combobox")
    assert LEGACY_TYPE_ALIASES["party"] == ("relation", "combobox")
    assert LEGACY_TYPE_ALIASES["ref"] == ("relation", "combobox")


def test_legacy_text_is_deliberately_not_aliased():
    # `text` is the ONE colliding legacy name: old `text` = single-line <Input>
    # (-> new `string`), while new `text` = multi-line (<- old `textarea`).
    # Aliasing it here would silently downgrade every NEW multi-line `text`
    # declaration to single-line, because field() consults this table first.
    # The collision is resolved at the boundary, in cfg()'s _CFG_TYPE_MAP.
    assert "text" not in LEGACY_TYPE_ALIASES
    assert LEGACY_TYPE_ALIASES["textarea"] == ("text", "plain")
