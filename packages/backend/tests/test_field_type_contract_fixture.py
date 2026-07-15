"""MINORS fix (final fix wave) — contract test pinning the hand-mirrored type
tables: `FIELD_TYPES` / `WIDGETS_BY_TYPE` / `INDEXABLE_TYPES` /
`RELATION_RESOURCES` are duplicated BY HAND in `modules/fields/fields.ts`
(frontend, the Studio's type picker) with a "keep in sync" comment and, until
this fix, no test. A silent drift there means an admin picks a (type, widget)
pair the SERVER rejects with a 422 it cannot explain from the UI.

Mechanism chosen (cheapest honest one — see the task report): ONE JSON
fixture, `packages/web/src/modules/fields/__fixtures__/backend-field-
contract.json`, committed to git and hand-updated alongside any change to
`app/core/schema/types.py` / `reserved.py`. This test asserts the fixture
still matches the LIVE backend constants (drift on the backend side fails
here); a sibling Vitest test (`modules/fields/fields.test.ts`) asserts the
SAME fixture matches the TS mirror (drift on the frontend side fails there).
No live network call, no cross-language execution at test time — both sides
independently pin against one shared, offline artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.schema.reserved import RELATION_RESOURCES
from app.core.schema.types import FIELD_TYPES, INDEXABLE_TYPES, WIDGETS_BY_TYPE

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "web" / "src" / "modules" / "fields" / "__fixtures__" / "backend-field-contract.json"
)


def _load_fixture() -> dict:
    assert FIXTURE_PATH.exists(), (
        f"contract fixture missing at {FIXTURE_PATH} — see this test's module "
        "docstring for what it pins and why")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_field_types_matches_the_live_backend_constant():
    fixture = _load_fixture()
    assert fixture["FIELD_TYPES"] == list(FIELD_TYPES), (
        "FIELD_TYPES changed in app/core/schema/types.py without updating "
        f"{FIXTURE_PATH} — the frontend Studio's mirror (modules/fields/"
        "fields.ts) would silently drift out of sync")


def test_fixture_widgets_by_type_matches_the_live_backend_constant():
    fixture = _load_fixture()
    live = {t: list(w) for t, w in WIDGETS_BY_TYPE.items()}
    assert fixture["WIDGETS_BY_TYPE"] == live


def test_fixture_indexable_types_matches_the_live_backend_constant():
    fixture = _load_fixture()
    assert set(fixture["INDEXABLE_TYPES"]) == set(INDEXABLE_TYPES)


def test_fixture_relation_resources_matches_the_live_backend_constant():
    fixture = _load_fixture()
    assert set(fixture["RELATION_RESOURCES"]) == set(RELATION_RESOURCES)
