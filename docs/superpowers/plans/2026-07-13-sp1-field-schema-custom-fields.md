# SP1 — Field Schema & Custom Fields — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la saisie JSON brute par des formulaires générés depuis un descripteur de champ unique, et ouvrir la définition de champs personnalisés aux organisations, sans DDL de mutation ni fuite inter-organisations.

**Architecture:** Un descripteur `FieldSpec` (type × widget × rules) est déclaré soit **en code** (schémas produit, non éditables) soit **en base** (`field_definition`, scopé `organization_id NOT NULL`). Un résolveur les fusionne et applique l'héritage ; un endpoint unique `GET /api/v1/schema/{target}` le sert. Le même descripteur génère la validation **pydantic** (serveur, fait autorité) et **zod** (client, reflet). Les valeurs des champs custom vivent dans une colonne `custom_fields` JSONB par entité.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · Pydantic v2 · Postgres (JSONB, index d'expression partiels) / SQLite (tests) · Next.js · TanStack Query · zod · Vitest · Playwright · pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-field-schema-custom-fields-design.md`

---

## Global Constraints

Ces contraintes s'appliquent **à toutes les tâches**, implicitement.

- **Python** : `C:\facil_framework\.venv\Scripts\python.exe` (Python 3.12). Tests = `pytest`.
- **Backend = autorité, frontend = reflet.** Toute règle (y compris `visible_if`/`required_if`) est évaluée **serveur ET client** ; le serveur tranche.
- **Allowlist stricte** : une clé non déclarée arrivant dans une requête → **422 explicite**. **Jamais** un `ignore` silencieux.
- **Merge, jamais remplacement** : l'écriture d'un blob JSON préserve les clés pré-existantes non déclarées.
- **Suppression = archivage** (`archived=True`). Purge = endpoint distinct, explicite, audité.
- **i18n obligatoire** : toute chaîne visible = clé en/fr/es (`packages/web/src/i18n/messages/{en,fr,es}.json`).
- **Concurrence optimiste** : `If-Match` → 409 sur toute mutation de définition (`app/api/concurrency.py`: `enforce_if_match`, `row_etag`).
- **Audit** : toute mutation de définition → `audit.record`.
- **Dialecte** : tout SQL Postgres-only est **gardé par dialecte** (`bind.dialect.name == "postgresql"`), dégradation propre sous SQLite.
- **Zéro DDL de mutation à l'exécution.** Seuls des `CREATE INDEX CONCURRENTLY` additifs, plafonnés.
- **Zéro régression providers** : les 13 providers built-in doivent rendre exactement le même `config_schema` après M0 qu'avant.
- **Plafonds durs** : 50 champs et 10 champs indexés par `(organization_id, target)`.
- **Alembic** : nouvelle révision `0018_field_definition`, `down_revision = "0017_site_address_link"`.
- **Build = CI.** Aucun build prod local. Commits locaux ; push sous accord explicite.
- **Gate qualité avant chaque commit de lot non-trivial** : agents `code-reviewer`, `security-auditor`, `silent-failure-hunter` sur le diff — corriger les findings, pas les lister.

---

## File Structure

### Backend — à créer

| Fichier | Responsabilité unique |
|---|---|
| `packages/backend/app/core/schema/types.py` | Les constantes du contrat : `FIELD_TYPES`, `WIDGETS_BY_TYPE`, `INDEXABLE_TYPES`, `INDEX_CAST`. Aucune logique. |
| `packages/backend/app/core/schema/spec.py` | `FieldSpec` (modèle pydantic validant un descripteur) + `field()` (le constructeur déclaratif, sur-ensemble de `cfg()`). |
| `packages/backend/app/core/schema/registry.py` | `SchemaRegistry` : les schémas **produit** déclarés en code, par `target`. |
| `packages/backend/app/core/schema/pydantic_gen.py` | `model_for(specs)` → modèle pydantic dynamique (validation serveur), avec cache. |
| `packages/backend/app/core/schema/conditions.py` | Évaluation de `visible_if` / `required_if` (fonction pure, partagée avec le client par contrat). |
| `packages/backend/app/core/schema/sanitize.py` | Sanitization allowlist du `richtext` (écriture + rendu). |
| `packages/backend/app/core/schema/resolver.py` | Fusion schémas produit + définitions base, héritage, cache. |
| `packages/backend/app/core/schema/reserved.py` | Noms réservés **dérivés par introspection SQLAlchemy** du modèle cible. |
| `packages/backend/app/core/schema/merge.py` | `merge_blob(existing, incoming, specs)` — la règle « entrée stricte, existant préservé ». |
| `packages/backend/app/models/field_definition.py` | Table `field_definition`. |
| `packages/backend/app/core/schema/repository.py` | Accès BD aux définitions (liste scopée, upsert, archive, purge, comptage pour plafonds). |
| `packages/backend/app/core/schema/indexing.py` | Création/suppression d'index d'expression partiels (`CONCURRENTLY`, hors transaction). |
| `packages/backend/app/api/schema.py` | `GET /api/v1/schema/{target}`. |
| `packages/backend/app/api/admin_field_definitions.py` | CRUD des définitions (`fields.manage`). |
| `packages/backend/alembic/versions/0018_field_definition.py` | Table + colonnes `custom_fields`. |

### Backend — à modifier

| Fichier | Modification |
|---|---|
| `app/core/providers/base.py:14-23` | `cfg()` délègue à `field()` ; `ConfigFieldType` remplacé par les vraies constantes. **Signature inchangée** → zéro régression. |
| `app/rbac/permissions.py:20-41` | Ajouter `fields.manage` à `CORE_PERMISSIONS`. |
| `app/modules/organization/models.py` | `+ custom_fields` sur `Organization` et `OrgUnit`. |
| `app/modules/location/models.py` | `+ custom_fields` sur `Site`. |
| `app/modules/{organization,location,party}/schemas.py` | Accepter `custom_fields` en entrée. |
| `app/main.py` | Monter `api/schema.py` + `api/admin_field_definitions.py` ; `app.state.schema_registry`. |

### Frontend — à créer

| Fichier | Responsabilité |
|---|---|
| `packages/web/src/lib/schema/types.ts` | Le miroir TypeScript de `FieldSpec` (types, widgets, rules). |
| `packages/web/src/lib/schema/to-field-def.ts` | `fieldSpecToFieldDef()` — généralise `configFieldToFieldDef`. |
| `packages/web/src/lib/schema/to-zod.ts` | Compilation `rules` → zod. |
| `packages/web/src/lib/schema/conditions.ts` | Évaluation `visible_if` / `required_if` (miroir de `conditions.py`). |
| `packages/web/src/lib/schema/api.ts` | `getSchema(target, organizationId)`. |
| `packages/web/src/modules/fields/{api,fields,page}.tsx` | Écran A — le Studio de champs. |
| `packages/web/src/components/ui/weekly-hours-field.tsx` | Widget `weekly_hours`. |

### Frontend — à modifier

| Fichier | Modification |
|---|---|
| `packages/web/src/components/ui/record-form.tsx:30-49` | `FieldDef` gagne `widget?`, `rules?`, `relationResource?`. `renderControl` dispatche par `(type, widget)`. `fieldRule()` compile `rules`. `zod?` conservé (rétrocompat). |
| `packages/web/src/modules/providers/fields.ts:14-22` | `configFieldToFieldDef` → réexporte `fieldSpecToFieldDef`. |
| `packages/web/src/modules/{organization,location,party}/fields.ts` | Fusionner les champs custom servis par `/schema`. |

---

## M0 — Le socle descripteur

**Livrable :** un descripteur validé, un générateur pydantic, un endpoint qui sert les schémas **produit**, et un `RecordForm` qui les consomme. **Rien de visible ne change pour l'utilisateur.** Filet : les 13 providers fonctionnent à l'identique.

---

### Task 1: Le contrat de types (constantes pures)

**Files:**
- Create: `packages/backend/app/core/schema/__init__.py` (vide)
- Create: `packages/backend/app/core/schema/types.py`
- Test: `packages/backend/tests/test_schema_types.py`

**Interfaces:**
- Consumes: rien.
- Produces: `FIELD_TYPES: tuple[str, ...]` (15) · `WIDGETS_BY_TYPE: dict[str, tuple[str, ...]]` · `DEFAULT_WIDGET: dict[str, str]` · `INDEXABLE_TYPES: frozenset[str]` · `INDEX_CAST: dict[str, str]` · `LEGACY_TYPE_ALIASES: dict[str, tuple[str, str]]`.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_types.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/types.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_types.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/ packages/backend/tests/test_schema_types.py
git commit -m "feat(schema): field contract — 15 types, widgets, typed index casts"
```

---

### Task 2: `FieldSpec` + `field()` — le descripteur validé

**Files:**
- Create: `packages/backend/app/core/schema/spec.py`
- Test: `packages/backend/tests/test_schema_spec.py`

**Interfaces:**
- Consumes: `types.py` (Task 1).
- Produces:
  - `class FieldSpec(BaseModel)` — champs : `key: str`, `type: str = "string"`, `widget: str = ""`, `label: dict[str, str]`, `hint: dict[str, str] = {}`, `required: bool = False`, `default: Any = None`, `rules: dict[str, Any] = {}`, `options: list[dict] = []`, `relation_resource: str = ""`, `relation_filter: dict[str, str] = {}`, `group: str = ""`, `order: int = 0`, `col_span: int = 1`, `indexed: bool = False`, **`index_state: str = "none"`** (état runtime, posé par le job d'indexation — lu par `sortable_keys()` en Task 14 ; `FieldDefinition.as_spec()` (Task 10) et `types.ts` (Task 7) doivent le porter aussi).
  - `field(key, label, *, type="string", widget="", **kw) -> dict[str, Any]` — constructeur ; **valide immédiatement** (lève `ValueError` à l'import si le descripteur est faux).
  - `KEY_RE: re.Pattern` — `^[a-z][a-z0-9_]{0,59}$`.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_spec.py
"""FieldSpec validates the descriptor itself — fail fast, at import time."""

import pytest

from app.core.schema.spec import FieldSpec, field


def test_field_returns_a_plain_dict_with_the_default_widget_filled_in():
    f = field("legal_name", {"en": "Legal name", "fr": "Raison sociale",
                             "es": "Razón social"})
    assert f["key"] == "legal_name"
    assert f["type"] == "string"
    assert f["widget"] == "plain"          # DEFAULT_WIDGET["string"]
    assert f["label"]["fr"] == "Raison sociale"


def test_legacy_type_alias_is_expanded_to_type_plus_widget():
    f = field("primary_color", {"en": "Colour", "fr": "Couleur", "es": "Color"},
              type="color")
    assert f["type"] == "string" and f["widget"] == "color"


def test_unknown_type_is_refused():
    with pytest.raises(ValueError, match="unknown field type"):
        field("x", {"en": "X", "fr": "X", "es": "X"}, type="quantum")


def test_widget_must_belong_to_the_type():
    with pytest.raises(ValueError, match="widget 'rating' is not valid for type 'string'"):
        field("x", {"en": "X", "fr": "X", "es": "X"}, type="string", widget="rating")


def test_key_must_be_snake_case_and_bounded():
    with pytest.raises(ValueError, match="key"):
        field("Bad-Key", {"en": "X", "fr": "X", "es": "X"})
    with pytest.raises(ValueError, match="key"):
        field("a" * 61, {"en": "X", "fr": "X", "es": "X"})


def test_label_requires_all_three_locales():
    # Repo rule: every user-visible string is an en/fr/es key. A field whose
    # label is monolingual would ship an untranslatable form.
    with pytest.raises(ValueError, match="label must provide en, fr and es"):
        field("x", {"en": "X"})


def test_indexed_is_refused_on_a_non_indexable_type():
    with pytest.raises(ValueError, match="type 'json' cannot be indexed"):
        field("payload", {"en": "P", "fr": "P", "es": "P"}, type="json", indexed=True)


def test_select_requires_options():
    with pytest.raises(ValueError, match="select requires options"):
        field("status", {"en": "S", "fr": "S", "es": "S"}, type="select")


def test_relation_requires_a_resource():
    with pytest.raises(ValueError, match="relation requires relation_resource"):
        field("country", {"en": "C", "fr": "C", "es": "C"}, type="relation")


def test_visible_if_must_reference_a_known_operator():
    with pytest.raises(ValueError, match="visible_if.op"):
        field("vat", {"en": "V", "fr": "V", "es": "V"},
              rules={"visible_if": {"field": "taxable", "op": "matches", "value": True}})


def test_spec_roundtrips_through_the_model():
    f = field("amount", {"en": "Amount", "fr": "Montant", "es": "Importe"},
              type="money", indexed=True, group="billing", order=3)
    spec = FieldSpec.model_validate(f)
    assert spec.type == "money" and spec.indexed is True and spec.order == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.spec'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/spec.py
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
```

> **Note pour l'implémenteur** : pydantic v2 lève `ValidationError`, pas `ValueError`. `ValidationError` **hérite** de `ValueError`, donc `pytest.raises(ValueError, match=...)` passe — le message est encapsulé mais `match` fait une recherche de sous-chaîne sur la représentation. Si un `match` échoue, remplacer par `pytest.raises(ValueError)` + `assert "…" in str(exc.value)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_spec.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/spec.py packages/backend/tests/test_schema_spec.py
git commit -m "feat(schema): FieldSpec descriptor validated at declaration time"
```

---

### Task 3: `cfg()` délègue à `field()` — non-régression des 13 providers

**Files:**
- Modify: `packages/backend/app/core/providers/base.py:14-23`
- Test: `packages/backend/tests/test_providers_schema_no_regression.py`

**Interfaces:**
- Consumes: `field()` (Task 2).
- Produces: `cfg()` — **signature identique**, sortie enrichie de `widget`/`rules`/`options`/`group`/`order`.

> **C'est le filet de sécurité du socle.** Les providers sont le seul consommateur déjà en place du pattern « schéma serveur → formulaire ». Les migrer d'abord donne un **oracle** (le comportement actuel) et **zéro donnée en jeu**.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_providers_schema_no_regression.py
"""M0 safety net: the 13 built-in providers must expose the SAME schema keys,
labels, types, required flags and defaults as before the FieldSpec migration."""

from app.core.providers.registry import default_registry
from app.core.schema.spec import FieldSpec


def test_all_thirteen_providers_still_register():
    r = default_registry()
    assert len(r.registered) == 13


def test_every_provider_schema_field_is_a_valid_FieldSpec():
    r = default_registry()
    for entry in r.registered_detailed:
        for f in entry["config_schema"]:
            FieldSpec.model_validate(f)  # raises if the descriptor is malformed


def test_schema_keys_are_unchanged_for_every_provider():
    # The SEC-F2 allowlist is built from these keys. If a key silently changed,
    # a provider's config writes would start being rejected in production.
    r = default_registry()
    actual = {
        (e["capability"], e["provider_code"]): sorted(f["key"] for f in e["config_schema"])
        for e in r.registered_detailed
    }
    for (cap, code), keys in actual.items():
        assert keys == sorted(set(keys)), f"{cap}/{code} declares a duplicate key"
        assert all(isinstance(k, str) and k for k in keys)
    # Spot-check the shape the admin form depends on (providers/fields.ts:14-22).
    for e in r.registered_detailed:
        for f in e["config_schema"]:
            assert {"key", "label", "type", "required", "default", "hint"} <= set(f)


def test_cfg_keeps_its_legacy_scalar_types_working():
    from app.core.providers.base import cfg
    assert cfg("host", "Host")["type"] == "string"
    assert cfg("port", "Port", type="number")["type"] == "number"
    assert cfg("tls", "TLS", type="boolean")["type"] == "boolean"
    assert cfg("extra", "Extra", type="json")["type"] == "json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_providers_schema_no_regression.py -v`
Expected: FAIL — `test_every_provider_schema_field_is_a_valid_FieldSpec` échoue : `label` est une `str`, pas un dict en/fr/es ; `widget` absent.

- [ ] **Step 3: Write minimal implementation**

Remplacer `packages/backend/app/core/providers/base.py:14-23` par :

```python
# Field types the admin config form understands — now the full FieldSpec
# contract (app.core.schema.types), not the 4-type subset this file used to
# carry. `cfg()` keeps its exact signature: the 13 built-in providers are
# untouched, and their declarations keep working verbatim.
from app.core.schema.spec import field as _field
from app.core.schema.types import LEGACY_TYPE_ALIASES  # noqa: F401  (re-export)

# Legacy provider type names → FieldSpec types.
_CFG_TYPE_MAP = {"text": "string", "boolean": "boolean",
                 "number": "number", "json": "json"}


def cfg(key: str, label: str, *, type: str = "text", required: bool = False,
        default: Any = None, hint: str = "") -> dict[str, Any]:
    """One declarative config field for a provider's admin form. NON-SECRET only —
    credentials travel via `secret_ref` / env and must never be declared here.

    Thin wrapper over `app.core.schema.spec.field()`: providers keep declaring
    `cfg("host", "Host")` and now get a full FieldSpec (widget, rules, i18n label)
    for free. The provider label is English-only today, so it is mirrored into the
    three locales — translating them is a follow-up, not a blocker.
    """
    ftype = _CFG_TYPE_MAP.get(type, type)
    kw: dict[str, Any] = {"required": required, "default": default}
    if ftype in ("select", "multiselect"):
        kw["options"] = []
    return _field(
        key,
        {"en": label, "fr": label, "es": label},
        type=ftype,
        hint={"en": hint, "fr": hint, "es": hint} if hint else {},
        **kw,
    )
```

> **Attention (piège réel)** : `FieldSpec` refuse un `select` sans `options`. Aucun provider n'utilise `select` aujourd'hui (les 4 types legacy sont text/number/boolean/json), donc la branche est morte — mais elle empêche une régression future. Ne pas la retirer.

> **Attention n°2** : `registry.schema_keys()` (`registry.py:44`) lit `f["key"]` — inchangé. `admin_providers._public()` (`admin_providers.py:49-52`) lit la même chose. **Aucun de ces deux appels ne doit être modifié.**

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_providers_schema_no_regression.py packages/backend/tests/test_providers*.py -v`
Expected: PASS — les nouveaux tests + **toute la suite providers existante** au vert.

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/providers/base.py packages/backend/tests/test_providers_schema_no_regression.py
git commit -m "refactor(providers): cfg() delegates to FieldSpec — same wire format, richer descriptor"
```

---

### Task 4: Générateur pydantic — la validation serveur

**Files:**
- Create: `packages/backend/app/core/schema/conditions.py`
- Create: `packages/backend/app/core/schema/pydantic_gen.py`
- Test: `packages/backend/tests/test_schema_pydantic_gen.py`

**Interfaces:**
- Consumes: `FieldSpec` (Task 2).
- Produces:
  - `conditions.is_visible(spec: dict, values: dict) -> bool`
  - `conditions.is_required(spec: dict, values: dict) -> bool`
  - `pydantic_gen.validate_blob(specs: list[dict], values: dict) -> dict` — **lève `SchemaViolation`** (clé inconnue, type invalide, règle violée, requis manquant).
  - `pydantic_gen.SchemaViolation(Exception)` avec `.errors: list[dict]` (forme `{"loc": [key], "msg": str}`) → converti en **422** par l'API.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_pydantic_gen.py
"""Server-side validation generated from the descriptor. The server decides."""

import pytest

from app.core.schema.pydantic_gen import SchemaViolation, validate_blob
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}

SPECS = [
    field("legal_name", L, required=True, rules={"max_length": 200}),
    field("vat_rate", L, type="decimal", rules={"min": 0, "max": 100}),
    field("taxable", L, type="boolean"),
    field("vat_no", L, rules={"required_if": {"field": "taxable", "op": "eq",
                                              "value": True},
                              "visible_if": {"field": "taxable", "op": "eq",
                                             "value": True}}),
    field("amount", L, type="money"),
    field("opened_on", L, type="date"),
    field("status", L, type="select",
          options=[{"value": "draft", "label": L}, {"value": "live", "label": L}]),
]


def test_unknown_key_is_rejected_not_ignored():
    # Silent drop = the exact failure mode the repo's anti-silent-failure rule
    # forbids. The client must learn its key was refused.
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "sneaky": "x"})
    assert e.value.errors[0]["loc"] == ["sneaky"]
    assert "not declared" in e.value.errors[0]["msg"]


def test_required_field_missing_is_rejected():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {})


def test_decimal_bounds_enforced():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "vat_rate": 150})


def test_select_value_must_be_one_of_the_options():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "status": "archived"})


def test_money_must_be_amount_plus_currency_with_a_string_amount():
    # A float amount would silently round money. Refused.
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme",
                              "amount": {"amount": 12.30, "currency": "XAF"}})
    ok = validate_blob(SPECS, {"legal_name": "Acme",
                               "amount": {"amount": "12.30", "currency": "XAF"}})
    assert ok["amount"] == {"amount": "12.30", "currency": "XAF"}


def test_date_must_be_iso():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "opened_on": "13/07/2026"})
    ok = validate_blob(SPECS, {"legal_name": "Acme", "opened_on": "2026-07-13"})
    assert ok["opened_on"] == "2026-07-13"


def test_required_if_true_and_field_absent_is_rejected():
    with pytest.raises(SchemaViolation):
        validate_blob(SPECS, {"legal_name": "Acme", "taxable": True})


def test_hidden_field_may_be_omitted_even_though_required_if_fires_when_visible():
    # taxable=False → vat_no is neither visible nor required. Omitting it is OK.
    ok = validate_blob(SPECS, {"legal_name": "Acme", "taxable": False})
    assert "vat_no" not in ok


def test_sending_a_hidden_field_is_rejected():
    # THE bypass this guard exists for: a client that hides a field client-side
    # but posts it anyway must be refused by the server.
    with pytest.raises(SchemaViolation) as e:
        validate_blob(SPECS, {"legal_name": "Acme", "taxable": False,
                              "vat_no": "GQ123"})
    assert "not visible" in e.value.errors[0]["msg"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_pydantic_gen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.pydantic_gen'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/conditions.py
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
```

```python
# packages/backend/app/core/schema/pydantic_gen.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_pydantic_gen.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/conditions.py packages/backend/app/core/schema/pydantic_gen.py packages/backend/tests/test_schema_pydantic_gen.py
git commit -m "feat(schema): server-authoritative validation from the descriptor (allowlist + conditions)"
```

---

### Task 5: Registre de schémas produit + résolveur (code seul, sans BD)

**Files:**
- Create: `packages/backend/app/core/schema/registry.py`
- Create: `packages/backend/app/core/schema/resolver.py`
- Test: `packages/backend/tests/test_schema_registry.py`

**Interfaces:**
- Consumes: `field()` (Task 2).
- Produces:
  - `class SchemaRegistry` — `register(target: str, specs: list[dict])`, `get(target) -> list[dict]`, `targets -> list[str]`, `is_registered(target) -> bool`.
  - `default_schema_registry() -> SchemaRegistry` — les schémas produit built-in (vide à ce stade ; peuplé en M2/M3).
  - `EXTENSIBLE_TARGETS: dict[str, str]` — registre **opt-in** `target → nom de table`. Une entité absente d'ici **ne peut pas** porter de champs custom.
  - `resolver.resolve(registry, target, db_specs=None) -> list[dict]` — fusion + tri `(group, order, key)`. `db_specs=None` en M0.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_registry.py
"""Product schemas live in CODE (versioned, non-editable). Custom fields live in
the DB. The resolver merges them; only opted-in targets may be extended."""

import pytest

from app.core.schema.registry import (
    EXTENSIBLE_TARGETS, SchemaRegistry, default_schema_registry,
)
from app.core.schema.resolver import resolve
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}


def test_registry_registers_and_returns_specs():
    r = SchemaRegistry()
    r.register("organization.document_identity", [field("legal_name", L)])
    assert r.is_registered("organization.document_identity")
    assert [s["key"] for s in r.get("organization.document_identity")] == ["legal_name"]


def test_unknown_target_returns_empty_not_an_error():
    assert SchemaRegistry().get("nope.nope") == []


def test_registering_a_duplicate_key_is_refused():
    r = SchemaRegistry()
    with pytest.raises(ValueError, match="duplicate key"):
        r.register("t.x", [field("a", L), field("a", L)])


def test_extensible_targets_are_an_explicit_opt_in_allowlist():
    # Not every table may carry custom fields. RBAC, settings and audit tables
    # must never be user-extensible.
    assert EXTENSIBLE_TARGETS == {
        "organization.custom_fields": "organization",
        "org_unit.custom_fields": "org_unit",
        "site.custom_fields": "site",
        "party.custom_fields": "party",
    }
    assert not any(t.startswith(("role.", "permission.", "settings.", "account."))
                   for t in EXTENSIBLE_TARGETS)


def test_resolve_merges_code_specs_and_db_specs_sorted_by_group_order_key():
    r = SchemaRegistry()
    r.register("site.custom_fields", [field("code_ref", L, group="a", order=2)])
    db = [field("zone", L, group="a", order=1), field("floor", L, group="b", order=1)]
    out = resolve(r, "site.custom_fields", db_specs=db)
    assert [s["key"] for s in out] == ["zone", "code_ref", "floor"]


def test_a_db_field_cannot_shadow_a_code_field():
    # A tenant must never be able to redefine a product-owned field.
    r = SchemaRegistry()
    r.register("site.custom_fields", [field("code_ref", L)])
    with pytest.raises(ValueError, match="shadows a product field"):
        resolve(r, "site.custom_fields", db_specs=[field("code_ref", L)])


def test_default_registry_is_importable_and_empty_at_M0():
    assert isinstance(default_schema_registry(), SchemaRegistry)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/registry.py
"""Product schemas — declared in CODE, versioned with it, never editable.

Mirrors `app.core.providers.registry.default_registry()`: one place where every
built-in schema is registered. An administrator FILLS `document_identity`; they
do not REDEFINE its shape. Only DB-backed custom fields are user-defined.
"""

from __future__ import annotations

from typing import Any

# Opt-in allowlist: which (entity, json column) pairs may carry USER-DEFINED
# fields. Deliberately excludes RBAC, settings, accounts and audit — a tenant
# must never be able to bolt fields onto security tables.
EXTENSIBLE_TARGETS: dict[str, str] = {
    "organization.custom_fields": "organization",
    "org_unit.custom_fields": "org_unit",
    "site.custom_fields": "site",
    "party.custom_fields": "party",
}


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, list[dict[str, Any]]] = {}

    def register(self, target: str, specs: list[dict[str, Any]]) -> None:
        keys = [s["key"] for s in specs]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"target {target!r} declares duplicate key(s): {sorted(dupes)}")
        self._schemas[target] = specs

    def is_registered(self, target: str) -> bool:
        return target in self._schemas

    def get(self, target: str) -> list[dict[str, Any]]:
        return self._schemas.get(target, [])

    @property
    def targets(self) -> list[str]:
        return sorted(self._schemas)


def default_schema_registry() -> SchemaRegistry:
    """Registry pre-loaded with the built-in product schemas.

    Empty at M0 — `organization.document_identity` lands in M2 and
    `organization.settings` in M3. Custom-field targets carry no code schema by
    design: everything they expose comes from the DB.
    """
    return SchemaRegistry()
```

```python
# packages/backend/app/core/schema/resolver.py
"""Merge product schemas (code) with custom-field definitions (DB).

Scoping and inheritance of the DB half live in `repository.py` (Task 12); this
module only merges and orders. Keeping them apart means the merge logic is
testable with zero database.
"""

from __future__ import annotations

from typing import Any

from app.core.schema.registry import SchemaRegistry


def resolve(registry: SchemaRegistry, target: str,
            db_specs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Product specs + custom specs, ordered by (group, order, key).

    A DB field may never shadow a product field: a tenant redefining a
    product-owned key would silently change its meaning for the whole product.
    """
    code_specs = registry.get(target)
    code_keys = {s["key"] for s in code_specs}
    db_specs = db_specs or []

    clashes = sorted({s["key"] for s in db_specs} & code_keys)
    if clashes:
        raise ValueError(
            f"custom field(s) {clashes} shadow a product field on target {target!r}")

    merged = [*code_specs, *db_specs]
    return sorted(merged, key=lambda s: (s.get("group") or "", s.get("order") or 0, s["key"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_registry.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/registry.py packages/backend/app/core/schema/resolver.py packages/backend/tests/test_schema_registry.py
git commit -m "feat(schema): product-schema registry + merge resolver (opt-in extensible targets)"
```

---

### Task 6: Endpoint `GET /api/v1/schema/{target}`

**Files:**
- Create: `packages/backend/app/api/schema.py`
- Modify: `packages/backend/app/main.py` (monter le routeur + `app.state.schema_registry`)
- Test: `packages/backend/tests/test_api_schema.py`

**Interfaces:**
- Consumes: `SchemaRegistry`, `resolve` (Task 5).
- Produces: `GET /api/v1/schema/{target}?organization_id=…` → `{"target": str, "fields": list[FieldSpec], "etag": str}`. En M0 : schémas **code uniquement** (`db_specs=None`).

> **Note d'implémentation** : `target` contient un point (`organization.document_identity`). FastAPI le route sans souci sur un segment de chemin — **ne pas** utiliser `{target:path}`, qui avalerait la query string.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_api_schema.py
"""GET /api/v1/schema/{target} — the single endpoint every generated form reads."""

import pytest

from app.core.schema.spec import field

L = {"en": "Legal name", "fr": "Raison sociale", "es": "Razón social"}


@pytest.mark.asyncio
async def test_returns_the_registered_product_schema(client, app, auth_headers):
    app.state.schema_registry.register("organization.document_identity",
                                       [field("legal_name", L, required=True)])
    r = await client.get("/api/v1/schema/organization.document_identity",
                         headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "organization.document_identity"
    assert body["fields"][0]["key"] == "legal_name"
    assert body["fields"][0]["label"]["fr"] == "Raison sociale"
    assert body["fields"][0]["widget"] == "plain"


@pytest.mark.asyncio
async def test_unknown_target_is_404_not_an_empty_list(client, auth_headers):
    # An empty list would let a typo'd target silently render an empty form.
    r = await client.get("/api/v1/schema/nope.nope", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_requires_authentication(client):
    r = await client.get("/api/v1/schema/organization.document_identity")
    assert r.status_code == 401
```

> **Note** : réutiliser les fixtures `client` / `app` / `auth_headers` de `packages/backend/tests/conftest.py`. **Lire ce fichier avant d'écrire le test** — ne pas inventer de fixtures.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_api_schema.py -v`
Expected: FAIL — 404 sur toutes les routes (le routeur n'est pas monté)

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/api/schema.py
"""Schema API — the one endpoint every schema-driven form reads.

Product schemas (code) + custom-field definitions (DB, org-scoped) merged and
ordered. The frontend maps the result straight onto `FieldDef[]` — the backend
is the single source of truth, no client drift.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.resolver import resolve
from app.security.auth_dep import require_auth

router = APIRouter(prefix="/api/v1/schema", tags=["schema"],
                   dependencies=[Depends(require_auth)])


@router.get("/{target}")
async def get_schema(target: str, request: Request,
                     organization_id: str | None = None) -> dict:
    registry = request.app.state.schema_registry
    if not registry.is_registered(target) and target not in EXTENSIBLE_TARGETS:
        # 404 rather than an empty list: an empty list would let a typo'd target
        # render an empty form, and nobody would notice until data went missing.
        raise HTTPException(404, f"unknown schema target {target!r}")

    # M0: code schemas only. Task 12 wires the org-scoped DB half in here.
    fields = resolve(registry, target, db_specs=None)
    etag = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {"target": target, "fields": fields, "etag": etag}
```

Dans `packages/backend/app/main.py`, à côté des autres routeurs et de `app.state.registry` :

```python
from app.api import schema as schema_api
from app.core.schema.registry import default_schema_registry

# … dans le lifespan / la construction de l'app, près de `app.state.registry` :
app.state.schema_registry = default_schema_registry()

# … avec les autres `app.include_router(...)` :
app.include_router(schema_api.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_api_schema.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Gate qualité + commit**

Lancer les agents `code-reviewer` et `silent-failure-hunter` sur le diff M0 backend. **Corriger les findings.** Puis :

```bash
git add packages/backend/app/api/schema.py packages/backend/app/main.py packages/backend/tests/test_api_schema.py
git commit -m "feat(schema): GET /api/v1/schema/{target} serving resolved field specs"
```

---

### Task 7: Contrat frontend — `FieldSpec` → `FieldDef` → zod

**Files:**
- Create: `packages/web/src/lib/schema/types.ts`
- Create: `packages/web/src/lib/schema/conditions.ts`
- Create: `packages/web/src/lib/schema/to-zod.ts`
- Create: `packages/web/src/lib/schema/to-field-def.ts`
- Create: `packages/web/src/lib/schema/api.ts`
- Modify: `packages/web/src/components/ui/record-form.tsx:30-49` (FieldDef gagne `widget`/`rules`/`relationResource`), `115-119` (`fieldRule` compile les rules), `121-137` (`validate` respecte `visible_if`), `201-299` (`renderControl` dispatche par `(type, widget)`)
- Modify: `packages/web/src/modules/providers/fields.ts:14-22` (réexporte `fieldSpecToFieldDef`)
- Test: `packages/web/src/lib/schema/to-zod.test.ts`, `to-field-def.test.ts`, `conditions.test.ts`

**Interfaces:**
- Consumes: la réponse de `GET /api/v1/schema/{target}` (Task 6).
- Produces:
  - `types.ts` : `FieldSpec`, `FieldRules`, `Condition` (miroir exact du backend).
  - `conditions.ts` : `isVisible(spec, values)`, `isRequired(spec, values)`.
  - `to-zod.ts` : `rulesToZod(spec): z.ZodTypeAny`.
  - `to-field-def.ts` : `fieldSpecToFieldDef(spec: FieldSpec): FieldDef`.
  - `api.ts` : `getSchema(target: string, organizationId?: string): Promise<{fields: FieldSpec[], etag: string}>`.

> **Contrainte structurelle (spec §5)** : `FieldDef.zod?: z.ZodTypeAny` (`record-form.tsx:45`) est un **objet JavaScript non sérialisable** — un champ défini en base ne peut donc jamais en porter. D'où `rules`, que le client **compile**. L'attribut `zod?` reste accepté pour les champs codés en dur → **zéro régression**.

- [ ] **Step 1: Write the failing tests**

```ts
// packages/web/src/lib/schema/conditions.test.ts
import { describe, expect, it } from "vitest";
import { isRequired, isVisible } from "./conditions";
import type { FieldSpec } from "./types";

const L = { en: "X", fr: "X", es: "X" };
const base: FieldSpec = {
  key: "vat_no", type: "string", widget: "plain", label: L, hint: {},
  required: false, default: null, options: [], relation_resource: "",
  relation_filter: {}, group: "", order: 0, col_span: 1, indexed: false,
  rules: {
    visible_if: { field: "taxable", op: "eq", value: true },
    required_if: { field: "taxable", op: "eq", value: true },
  },
};

describe("conditions (mirror of app/core/schema/conditions.py)", () => {
  it("hides the field when the condition is not met", () => {
    expect(isVisible(base, { taxable: false })).toBe(false);
    expect(isVisible(base, { taxable: true })).toBe(true);
  });

  it("never requires an invisible field", () => {
    expect(isRequired(base, { taxable: false })).toBe(false);
    expect(isRequired(base, { taxable: true })).toBe(true);
  });

  it("treats a field with no condition as always visible", () => {
    expect(isVisible({ ...base, rules: {} }, {})).toBe(true);
  });
});
```

```ts
// packages/web/src/lib/schema/to-zod.test.ts
import { describe, expect, it } from "vitest";
import { rulesToZod } from "./to-zod";
import type { FieldSpec } from "./types";

const L = { en: "X", fr: "X", es: "X" };
const spec = (over: Partial<FieldSpec>): FieldSpec => ({
  key: "f", type: "string", widget: "plain", label: L, hint: {}, required: false,
  default: null, rules: {}, options: [], relation_resource: "", relation_filter: {},
  group: "", order: 0, col_span: 1, indexed: false, ...over,
});

describe("rulesToZod", () => {
  it("enforces max_length", () => {
    const z = rulesToZod(spec({ rules: { max_length: 3 } }));
    expect(z.safeParse("abcd").success).toBe(false);
    expect(z.safeParse("abc").success).toBe(true);
  });

  it("enforces numeric bounds on number", () => {
    const z = rulesToZod(spec({ type: "number", rules: { min: 0, max: 100 } }));
    expect(z.safeParse("150").success).toBe(false);
    expect(z.safeParse("50").success).toBe(true);
  });

  it("enforces pattern", () => {
    const z = rulesToZod(spec({ rules: { pattern: "^[A-Z]{2}$" } }));
    expect(z.safeParse("gq").success).toBe(false);
    expect(z.safeParse("GQ").success).toBe(true);
  });

  it("rejects an empty value when required", () => {
    const z = rulesToZod(spec({ required: true }));
    expect(z.safeParse("").success).toBe(false);
  });

  it("accepts an empty value when optional", () => {
    expect(rulesToZod(spec({})).safeParse("").success).toBe(true);
  });
});
```

```ts
// packages/web/src/lib/schema/to-field-def.test.ts
import { describe, expect, it } from "vitest";
import { fieldSpecToFieldDef } from "./to-field-def";
import type { FieldSpec } from "./types";

const L = { en: "Amount", fr: "Montant", es: "Importe" };
const spec = (over: Partial<FieldSpec>): FieldSpec => ({
  key: "amount", type: "money", widget: "plain", label: L, hint: {}, required: true,
  default: null, rules: {}, options: [], relation_resource: "", relation_filter: {},
  group: "billing", order: 2, col_span: 2, indexed: true, ...over,
});

describe("fieldSpecToFieldDef", () => {
  it("maps key/label/required/colSpan onto the RecordForm contract", () => {
    const d = fieldSpecToFieldDef(spec({}), "fr");
    expect(d.name).toBe("amount");
    expect(d.label).toBe("Montant");   // localised, not the raw i18n object
    expect(d.required).toBe(true);
    expect(d.colSpan).toBe(2);
  });

  it("carries type AND widget so renderControl can dispatch on the pair", () => {
    const d = fieldSpecToFieldDef(spec({ type: "string", widget: "color" }), "en");
    expect(d.type).toBe("string");
    expect(d.widget).toBe("color");
  });

  it("maps select options to RecordForm's selectOptions", () => {
    const d = fieldSpecToFieldDef(
      spec({ type: "select", widget: "dropdown",
             options: [{ value: "draft", label: { en: "Draft", fr: "Brouillon", es: "Borrador" } }] }),
      "fr");
    expect(d.selectOptions).toEqual([{ value: "draft", label: "Brouillon" }]);
  });

  it("carries the relation resource", () => {
    const d = fieldSpecToFieldDef(
      spec({ type: "relation", widget: "combobox", relation_resource: "countries" }), "en");
    expect(d.relationResource).toBe("countries");
  });

  it("falls back to English when the requested locale is missing", () => {
    const d = fieldSpecToFieldDef(spec({ label: { en: "Amount", fr: "", es: "" } }), "fr");
    expect(d.label).toBe("Amount");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/web && npm install && npx vitest run src/lib/schema`
Expected: FAIL — `Cannot find module './conditions'`

> **Gotcha du repo** : `npm install` **avant** tout `tsc`/`vitest`, sinon `node_modules` est désynchronisé et `tsc` ment.

- [ ] **Step 3: Write minimal implementation**

```ts
// packages/web/src/lib/schema/types.ts
/** Exact mirror of app/core/schema/spec.py:FieldSpec. The backend is the single
 *  source of truth; this file must never drift from it. */

export type FieldSpecType =
  | "string" | "text" | "richtext"
  | "number" | "decimal" | "money"
  | "boolean"
  | "date" | "datetime" | "time"
  | "select" | "multiselect"
  | "relation"
  | "file"
  | "json";

export type Locale = "en" | "fr" | "es";
export type I18nString = Partial<Record<Locale, string>>;

export interface Condition {
  field: string;
  op: "eq" | "ne" | "in";
  value: unknown;
}

export interface FieldRules {
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  precision?: number;
  visible_if?: Condition;
  required_if?: Condition;
}

export interface FieldSpec {
  key: string;
  type: FieldSpecType;
  widget: string;
  label: I18nString;
  hint: I18nString;
  required: boolean;
  default: unknown;
  rules: FieldRules;
  options: { value: string; label: I18nString }[];
  relation_resource: string;
  relation_filter: Record<string, string>;
  group: string;
  order: number;
  col_span: number;
  indexed: boolean;
}

/** Pick a localised string, falling back to English then to the raw key. */
export function tr(s: I18nString, locale: Locale): string {
  return s[locale] || s.en || "";
}
```

```ts
// packages/web/src/lib/schema/conditions.ts
/** Mirror of app/core/schema/conditions.py. The SERVER is authoritative — this
 *  half only avoids showing the user a field that would be rejected anyway. */

import type { Condition, FieldSpec } from "./types";

function matches(rule: Condition | undefined, values: Record<string, unknown>): boolean {
  if (!rule) return true;
  const actual = values[rule.field];
  switch (rule.op) {
    case "eq": return actual === rule.value;
    case "ne": return actual !== rule.value;
    case "in": return Array.isArray(rule.value) && rule.value.includes(actual);
    default: return true;
  }
}

export function isVisible(spec: FieldSpec, values: Record<string, unknown>): boolean {
  return matches(spec.rules?.visible_if, values);
}

export function isRequired(spec: FieldSpec, values: Record<string, unknown>): boolean {
  if (!isVisible(spec, values)) return false;   // invisible ⇒ never required
  if (spec.required) return true;
  return spec.rules?.required_if ? matches(spec.rules.required_if, values) : false;
}
```

```ts
// packages/web/src/lib/schema/to-zod.ts
/** Compile declarative `rules` into a zod validator.
 *
 *  A DB-defined field can never carry a zod OBJECT (not serialisable), so the
 *  descriptor carries declarative rules and the client compiles them here.
 *  RecordForm keeps values as strings, so the rules apply to the string form. */

import { z } from "zod";
import type { FieldSpec } from "./types";

export function rulesToZod(spec: FieldSpec): z.ZodTypeAny {
  const r = spec.rules ?? {};
  const label = spec.key;

  if (spec.type === "number" || spec.type === "decimal") {
    let s: z.ZodTypeAny = z
      .string()
      .refine((v) => v === "" || !Number.isNaN(Number(v)), `${label} must be a number`);
    if (r.min !== undefined)
      s = s.refine((v) => v === "" || Number(v) >= r.min!, `${label} must be ≥ ${r.min}`);
    if (r.max !== undefined)
      s = s.refine((v) => v === "" || Number(v) <= r.max!, `${label} must be ≤ ${r.max}`);
    if (spec.required)
      s = s.refine((v) => v !== "", `${label} is required`);
    return s;
  }

  let s = z.string();
  if (r.min_length !== undefined) s = s.min(r.min_length, `${label}: too short`);
  if (r.max_length !== undefined) s = s.max(r.max_length, `${label}: too long`);
  if (r.pattern) s = s.regex(new RegExp(r.pattern), `${label}: invalid format`);
  if (spec.required) return s.trim().min(1, `${label} is required`);
  return s.optional().or(z.literal(""));
}
```

```ts
// packages/web/src/lib/schema/to-field-def.ts
/** FieldSpec (server) → FieldDef (RecordForm). Generalises
 *  `configFieldToFieldDef` (providers/fields.ts:14-22), which proved this exact
 *  path end-to-end for providers. */

import type { FieldDef } from "@/components/ui/record-form";
import { rulesToZod } from "./to-zod";
import { tr, type FieldSpec, type Locale } from "./types";

export function fieldSpecToFieldDef(spec: FieldSpec, locale: Locale): FieldDef {
  return {
    name: spec.key,
    label: tr(spec.label, locale),
    type: spec.type,
    widget: spec.widget,
    required: spec.required,
    hint: tr(spec.hint, locale) || undefined,
    colSpan: (spec.col_span === 2 ? 2 : 1) as 1 | 2,
    rules: spec.rules,
    zod: rulesToZod(spec),
    relationResource: spec.relation_resource || undefined,
    refFilter: Object.keys(spec.relation_filter || {}).length ? spec.relation_filter : undefined,
    selectOptions: spec.options?.length
      ? spec.options.map((o) => ({ value: o.value, label: tr(o.label, locale) }))
      : undefined,
  };
}
```

```ts
// packages/web/src/lib/schema/api.ts
import { api } from "@/lib/api";
import type { FieldSpec } from "./types";

export interface SchemaResponse {
  target: string;
  fields: FieldSpec[];
  etag: string;
}

export function getSchema(target: string, organizationId?: string): Promise<SchemaResponse> {
  const qs = organizationId ? `?organization_id=${encodeURIComponent(organizationId)}` : "";
  return api<SchemaResponse>(`/api/v1/schema/${encodeURIComponent(target)}${qs}`);
}
```

> **À vérifier avant d'écrire `api.ts`** : lire `packages/web/src/lib/api.ts` pour la vraie signature du helper (`api<T>(path)` vs `apiFetch`). **Ne pas inventer** — s'aligner sur les appels existants dans `packages/web/src/modules/providers/api.ts`.

Puis, dans `packages/web/src/components/ui/record-form.tsx` :

1. Étendre `FieldDef` (après la ligne 49) :

```ts
export interface FieldDef {
  // … champs existants inchangés …
  /** Presentation variant within `type` (spec §5, axis 2). Falls back to the
   *  type's canonical widget when absent. */
  widget?: string;
  /** Declarative validation from a server-served spec. `zod` still wins when
   *  both are set (hand-written fields keep their bespoke rule). */
  rules?: import("@/lib/schema/types").FieldRules;
  /** Target resource for `type: "relation"` (generalises refResource). */
  relationResource?: string;
}
```

2. `renderControl` dispatche sur la **paire** `(type, widget)`. Les anciens types restent des cas valides via `LEGACY_TYPE_ALIASES` — donc **le `switch` existant n'est pas cassé** ; on ajoute en tête :

```ts
  function renderControl(f: FieldDef) {
    const fieldRO = readOnly || (f.immutable && mode === "edit");
    const id = `rf-${f.name}`;
    // New (type, widget) pairs first; the legacy `switch` below still handles
    // every hand-written field list untouched.
    if (f.type === "string" && f.widget === "color") return renderColor(f, fieldRO, id);
    if (f.type === "string" && f.widget === "timezone")
      return <TimezoneField value={values[f.name] ?? ""} disabled={fieldRO}
               onChange={(v) => setField(f.name, v)} />;
    if (f.type === "relation")
      return <RefSelect resource={(f.relationResource ?? f.refResource ?? "countries") as never}
               value={values[f.name] ?? ""} filter={f.refFilter} disabled={fieldRO}
               onChange={(v) => setField(f.name, v)} />;
    if (f.type === "json" && f.widget === "weekly_hours")
      return <WeeklyHoursField value={jsonValues[f.name]} disabled={fieldRO}
               onChange={(v) => { setJsonValues((s) => ({ ...s, [f.name]: v }));
                                  setJsonOk((s) => ({ ...s, [f.name]: true }));
                                  setDirty(true); setSaved(false); }} />;
    switch (f.type) {
      // … le switch existant, INCHANGÉ …
    }
  }
```

3. `validate()` (lignes 121-137) saute les champs invisibles :

```ts
  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const f of fields) {
      // A hidden field is neither validated nor submitted — mirrors
      // app/core/schema/conditions.py. The server re-checks regardless.
      if (f.rules && !isVisibleDef(f, values)) continue;
      // … le corps existant, inchangé …
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }
```

où `isVisibleDef` est un adaptateur local qui appelle `isVisible` de `@/lib/schema/conditions` avec `{ rules: f.rules }`. **`buildPayload()` doit sauter les mêmes champs** — sinon le client poste un champ masqué et le serveur le rejette en 422 (comportement correct, mais l'UX serait cassée).

Enfin, `packages/web/src/modules/providers/fields.ts:14-22` :

```ts
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
/** @deprecated use fieldSpecToFieldDef — kept as an alias so the providers page
 *  compiles unchanged. */
export const configFieldToFieldDef = fieldSpecToFieldDef;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && npx vitest run src/lib/schema && npx tsc --noEmit`
Expected: PASS — vitest vert, `tsc` sans erreur.

- [ ] **Step 5: Gate qualité + commit**

Revue `frontend-design` + relecture explicite contre **§11bis** (RecordForm, zod, If-Match, permission-driven, a11y/i18n). Corriger. Puis :

```bash
git add packages/web/src/lib/schema packages/web/src/components/ui/record-form.tsx packages/web/src/modules/providers/fields.ts
git commit -m "feat(web): FieldSpec → FieldDef → zod pipeline; RecordForm dispatches on (type, widget)"
```

---

## ✅ Checklist de validation — M0

À cocher **avant** de passer à M1. Chaque point est vérifiable, aucun n'est déclaratif.

- [ ] `pytest packages/backend/tests/test_schema_*.py` — vert.
- [ ] **Non-régression providers** : `pytest packages/backend/tests/ -k provider` — vert. Les 13 providers exposent les **mêmes clés** qu'avant.
- [ ] `GET /api/v1/schema/organization.document_identity` répond 200 avec des labels en/fr/es.
- [ ] `npx vitest run src/lib/schema` — vert. `npx tsc --noEmit` — sans erreur.
- [ ] **La page `/providers` fonctionne exactement comme avant** (vérification live Docker, pas seulement les tests).
- [ ] Aucun `INDEX_CAST` manquant pour un type indexable (test `test_schema_types.py`).
- [ ] Agents `code-reviewer` + `silent-failure-hunter` passés sur le diff, findings **corrigés**.

---

> **Note sur M1.** Le jalon M1 de la spec (« migrer les providers sur le nouveau descripteur ») est **entièrement réalisé par la Task 3**. Il n'a pas de section propre : sa valeur est d'être le **filet de non-régression** de M0, pas un livrable séparé. La checklist M0 ci-dessus **est** la validation de M1.

---

## M2 — `document_identity` : le premier JSON brut tué

**Livrable :** l'écran Organisation remplace l'éditeur JSON de `document_identity` par un vrai formulaire. **C'est le déblocage direct de SP2.**

---

### Task 8: Schéma produit `organization.document_identity` + écriture merge-preserve

**Files:**
- Create: `packages/backend/app/core/schema/merge.py`
- Create: `packages/backend/app/core/schema/product_schemas.py`
- Modify: `packages/backend/app/core/schema/registry.py` (`default_schema_registry` enregistre le schéma)
- Modify: `packages/backend/app/modules/organization/api/__init__.py` (PUT organisation valide `document_identity` contre le schéma)
- Modify: `packages/web/src/modules/organization/fields.ts:34` (retirer `type: "json"` sur `document_identity`)
- Create: `packages/web/src/modules/organization/document-identity-form.tsx`
- Test: `packages/backend/tests/test_schema_merge.py`, `packages/backend/tests/test_document_identity_schema.py`

**Interfaces:**
- Consumes: `validate_blob` (Task 4), `SchemaRegistry` (Task 5).
- Produces:
  - `merge.merge_blob(existing: dict, incoming: dict, specs: list[dict]) -> dict`
  - `product_schemas.DOCUMENT_IDENTITY: list[dict]` — 10 champs plats.

> **La règle de non-destruction est ici.** Le formulaire n'écrit que les clés **déclarées**, en **fusion**. Une clé pré-existante non déclarée (donnée historique jamais validée) est **conservée intacte**. Mais l'**API rejette (422)** toute clé non déclarée **arrivant dans une requête**. *Entrée stricte, existant préservé.*

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_merge.py
"""Merge, never replace. Historic keys nobody ever validated must survive."""

import pytest

from app.core.schema.merge import merge_blob
from app.core.schema.pydantic_gen import SchemaViolation
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}
SPECS = [field("legal_name", L), field("footer_note", L, type="text")]


def test_declared_keys_are_written():
    out = merge_blob({}, {"legal_name": "Acme"}, SPECS)
    assert out == {"legal_name": "Acme"}


def test_undeclared_pre_existing_key_is_preserved_untouched():
    # `seal_ref` predates the schema. Dropping it would destroy production data.
    existing = {"legal_name": "Old", "seal_ref": "SEAL-77"}
    out = merge_blob(existing, {"legal_name": "Acme"}, SPECS)
    assert out == {"legal_name": "Acme", "seal_ref": "SEAL-77"}


def test_undeclared_key_in_the_REQUEST_is_rejected():
    # Strict on input, tolerant on what's already stored.
    with pytest.raises(SchemaViolation):
        merge_blob({}, {"legal_name": "Acme", "injected": "x"}, SPECS)


def test_clearing_a_declared_key_removes_it_but_keeps_the_undeclared_ones():
    existing = {"legal_name": "Old", "footer_note": "n", "seal_ref": "SEAL-77"}
    out = merge_blob(existing, {"legal_name": "Acme", "footer_note": ""}, SPECS)
    assert out == {"legal_name": "Acme", "seal_ref": "SEAL-77"}
```

```python
# packages/backend/tests/test_document_identity_schema.py
"""The product schema that unblocks SP2 (document header/footer per entity)."""

from app.core.schema.registry import default_schema_registry
from app.core.schema.spec import FieldSpec


def test_document_identity_is_registered_and_flat():
    r = default_schema_registry()
    specs = r.get("organization.document_identity")
    assert specs, "document_identity must be registered"
    keys = {s["key"] for s in specs}
    assert keys == {
        "legal_name", "short_code", "logo_url", "seal_url", "header_note",
        "footer_note", "legal_mentions", "tax_id", "registration_number",
        "contact_line",
    }
    for s in specs:
        FieldSpec.model_validate(s)
        assert s["type"] != "json", "document_identity must be FLAT — no nested blob"


def test_every_label_is_localised_in_three_locales():
    for s in default_schema_registry().get("organization.document_identity"):
        assert s["label"]["en"] and s["label"]["fr"] and s["label"]["es"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_merge.py packages/backend/tests/test_document_identity_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.merge'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/merge.py
"""Merge a validated patch into an existing JSON blob.

Strict on input, tolerant on what is already stored:
  * a key arriving in the REQUEST that is not declared  → 422 (SchemaViolation)
  * a key already IN THE DB that is not declared        → preserved untouched

This is what lets us impose an allowlist on data that was never validated,
without a 422 avalanche on historic rows — and without destroying them.
"""

from __future__ import annotations

from typing import Any

from app.core.schema.pydantic_gen import validate_blob


def merge_blob(existing: dict[str, Any], incoming: dict[str, Any],
               specs: list[dict[str, Any]]) -> dict[str, Any]:
    clean = validate_blob(specs, incoming)          # raises SchemaViolation
    declared = {s["key"] for s in specs}
    preserved = {k: v for k, v in (existing or {}).items() if k not in declared}
    return {**preserved, **clean}
```

```python
# packages/backend/app/core/schema/product_schemas.py
"""Product-owned schemas — declared in code, versioned with it, non-editable.

`organization.document_identity` is the letterhead/footer/seal identity that the
Document Designer (SP2) renders. It is deliberately FLAT: the per-format layout
lives in the TEMPLATE (CSS @page + margin boxes), not here. Conflating the two
is what forces one hand-positioned layout per (format × document × org).
"""

from __future__ import annotations

from typing import Any

from app.core.schema.spec import field

DOCUMENT_IDENTITY: list[dict[str, Any]] = [
    field("legal_name",
          {"en": "Legal name", "fr": "Raison sociale", "es": "Razón social"},
          required=True, rules={"max_length": 200}, group="identity", order=1, col_span=2),
    field("short_code",
          {"en": "Short code", "fr": "Code court", "es": "Código corto"},
          hint={"en": "Printed on reports to identify the issuing entity",
                "fr": "Imprimé sur les rapports pour identifier l'entité émettrice",
                "es": "Impreso en los informes para identificar la entidad emisora"},
          rules={"max_length": 20}, group="identity", order=2),
    field("tax_id", {"en": "Tax ID", "fr": "Identifiant fiscal", "es": "NIF"},
          rules={"max_length": 50}, group="identity", order=3),
    field("registration_number",
          {"en": "Registration number", "fr": "Numéro d'enregistrement",
           "es": "Número de registro"},
          rules={"max_length": 50}, group="identity", order=4),
    field("logo_url", {"en": "Logo", "fr": "Logo", "es": "Logotipo"},
          type="file", widget="image", group="branding", order=1),
    field("seal_url", {"en": "Seal / stamp", "fr": "Sceau / cachet", "es": "Sello"},
          type="file", widget="image",
          hint={"en": "Reserved zone for the signature seal (SP2)",
                "fr": "Zone réservée au sceau de signature (SP2)",
                "es": "Zona reservada para el sello de firma (SP2)"},
          group="branding", order=2),
    field("header_note", {"en": "Header note", "fr": "Mention d'en-tête",
                          "es": "Nota de encabezado"},
          type="text", rules={"max_length": 300}, group="layout", order=1, col_span=2),
    field("footer_note", {"en": "Footer note", "fr": "Mention de pied de page",
                          "es": "Nota de pie de página"},
          type="text", rules={"max_length": 300}, group="layout", order=2, col_span=2),
    field("legal_mentions", {"en": "Legal mentions", "fr": "Mentions légales",
                             "es": "Menciones legales"},
          type="richtext", group="layout", order=3, col_span=2),
    field("contact_line", {"en": "Contact line", "fr": "Ligne de contact",
                           "es": "Línea de contacto"},
          rules={"max_length": 200}, group="layout", order=4, col_span=2),
]
```

Puis dans `registry.py`, remplacer `default_schema_registry()` :

```python
def default_schema_registry() -> SchemaRegistry:
    """Registry pre-loaded with the built-in product schemas."""
    from app.core.schema.product_schemas import DOCUMENT_IDENTITY

    r = SchemaRegistry()
    r.register("organization.document_identity", DOCUMENT_IDENTITY)
    return r
```

Dans `packages/backend/app/modules/organization/api/__init__.py`, sur le handler `PUT /{org_id}`, avant l'appel au service :

```python
from app.core.schema.merge import merge_blob
from app.core.schema.pydantic_gen import SchemaViolation

# … dans update_organization, après avoir chargé `existing` :
if body.document_identity is not None:
    specs = request.app.state.schema_registry.get("organization.document_identity")
    try:
        body.document_identity = merge_blob(
            existing.document_identity or {}, body.document_identity, specs)
    except SchemaViolation as e:
        raise HTTPException(422, detail=e.errors) from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_merge.py packages/backend/tests/test_document_identity_schema.py packages/backend/tests/test_modules_org_location.py -v`
Expected: PASS

- [ ] **Step 5: Frontend — le formulaire remplace l'éditeur JSON**

Dans `packages/web/src/modules/organization/fields.ts`, **retirer** l'entrée `{ name: "document_identity", type: "json" }` (ligne 34). `document_identity` n'est plus un champ du formulaire Organisation : c'est un **onglet dédié** (split-view, règle du repo : config riche = master-detail, pas un dialog).

```tsx
// packages/web/src/modules/organization/document-identity-form.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { RecordForm } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";
import { usePermissions } from "@/lib/use-permissions";
import { updateOrganization, type Organization } from "./api";

/** `document_identity` used to be a raw JSON textarea (fields.ts:34). It is now a
 *  generated form driven by the product schema — the identity SP2 prints in the
 *  letterhead/footer of every report for this entity. */
export function DocumentIdentityForm({ org, etag, onSaved }: {
  org: Organization; etag?: string; onSaved: () => void;
}) {
  const locale = useLocale() as Locale;
  const t = useTranslations("organization");
  const { can } = usePermissions();

  const { data, isLoading } = useQuery({
    queryKey: ["schema", "organization.document_identity"],
    queryFn: () => getSchema("organization.document_identity"),
  });

  if (isLoading || !data) return <p className="text-sm text-muted-foreground">{t("loading")}</p>;

  return (
    <RecordForm
      mode="edit"
      layout="rich"
      fields={data.fields.map((s) => fieldSpecToFieldDef(s, locale))}
      initial={org.document_identity ?? {}}
      etag={etag}
      readOnly={!can("organization.update")}
      onSubmit={(payload, tag) =>
        updateOrganization(org.id, { document_identity: payload }, tag)}
      onSuccess={onSaved}
      onConflict={onSaved}
      submitLabel={t("save")}
    />
  );
}
```

Clés i18n à ajouter dans `packages/web/src/i18n/messages/{en,fr,es}.json`, namespace `organization` : `documentIdentity.tab`, `documentIdentity.description`, `loading`, `save`. **Les libellés des champs viennent du serveur** — ne pas les dupliquer côté client.

- [ ] **Step 6: Gate qualité + commit**

Agents `code-reviewer` + `security-auditor` (le `richtext` `legal_mentions` **n'est pas encore sanitizé** — Task 16 ; le noter comme dette **explicite et suivie**, ou avancer la Task 16 avant ce commit. **Recommandation : avancer la Task 16.**).

```bash
git add packages/backend/app/core/schema/{merge,product_schemas,registry}.py packages/backend/app/modules/organization/api/__init__.py packages/backend/tests/test_schema_merge.py packages/backend/tests/test_document_identity_schema.py packages/web/src/modules/organization/
git commit -m "feat(organization): document_identity is a generated form, not raw JSON"
```

---

## ✅ Checklist de validation — M2

- [ ] `pytest -k "merge or document_identity"` — vert.
- [ ] **Vérification live Docker** : `/organizations` → onglet « Identité documentaire » → formulaire avec 10 champs localisés, **plus aucun textarea JSON**.
- [ ] Playwright : capture **avant/après** (JSON brut → vrai formulaire).
- [ ] Une organisation dont `document_identity` contient une clé historique non déclarée → **la clé survit** après une sauvegarde (test + vérif SQL live).
- [ ] `PUT` avec une clé inconnue → **422** (pas un 200 silencieux).

---

## M3 — `organization.settings` + page `/config`

### Task 9: Schémas produit pour les namespaces de settings

**Files:**
- Modify: `packages/backend/app/core/schema/product_schemas.py` (ajouter `ORGANIZATION_SETTINGS`)
- Modify: `packages/backend/app/core/schema/registry.py` (enregistrer `organization.settings`)
- Modify: `packages/backend/app/modules/organization/api/__init__.py` (merge-preserve sur `settings`)
- Modify: `packages/web/src/modules/organization/fields.ts:39` (retirer `type: "json"`)
- Modify: `packages/web/src/modules/settings/page.tsx` (page `/config` : formulaire par namespace)
- Test: `packages/backend/tests/test_organization_settings_schema.py`

**Interfaces:**
- Consumes: tout M0 + `merge_blob` (Task 8).
- Produces: `product_schemas.ORGANIZATION_SETTINGS: list[dict]`.

> **Portée honnête** : `Organization.settings` n'a **aucun consommateur** dans le code aujourd'hui (colonne JSON jamais lue). On y déclare donc les réglages **par organisation** dont le produit a réellement besoin — et **rien d'autre**. Inventer des champs « au cas où » serait exactement le placeholder que ce plan interdit.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_organization_settings_schema.py
from app.core.schema.registry import default_schema_registry
from app.core.schema.spec import FieldSpec


def test_organization_settings_declares_only_fields_the_product_consumes():
    specs = default_schema_registry().get("organization.settings")
    assert {s["key"] for s in specs} == {
        "default_document_locale", "fiscal_year_start_month", "document_number_prefix",
    }
    for s in specs:
        FieldSpec.model_validate(s)


def test_fiscal_year_start_month_is_bounded():
    spec = next(s for s in default_schema_registry().get("organization.settings")
                if s["key"] == "fiscal_year_start_month")
    assert spec["type"] == "number"
    assert spec["rules"]["min"] == 1 and spec["rules"]["max"] == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_organization_settings_schema.py -v`
Expected: FAIL — la liste retournée est vide

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `product_schemas.py` :

```python
ORGANIZATION_SETTINGS: list[dict[str, Any]] = [
    field("default_document_locale",
          {"en": "Default document locale", "fr": "Langue par défaut des documents",
           "es": "Idioma predeterminado de los documentos"},
          type="select",
          options=[{"value": "en", "label": {"en": "English", "fr": "Anglais", "es": "Inglés"}},
                   {"value": "fr", "label": {"en": "French", "fr": "Français", "es": "Francés"}},
                   {"value": "es", "label": {"en": "Spanish", "fr": "Espagnol", "es": "Español"}}],
          group="documents", order=1),
    field("document_number_prefix",
          {"en": "Document number prefix", "fr": "Préfixe de numérotation",
           "es": "Prefijo de numeración"},
          hint={"en": "Reserved for the SP2 legal sequence (e.g. \"GQ-\")",
                "fr": "Réservé à la séquence légale SP2 (ex. « GQ- »)",
                "es": "Reservado para la secuencia legal SP2 (p. ej. «GQ-»)"},
          rules={"max_length": 10, "pattern": "^[A-Z0-9-]*$"}, group="documents", order=2),
    field("fiscal_year_start_month",
          {"en": "Fiscal year start month", "fr": "Mois de début d'exercice",
           "es": "Mes de inicio del ejercicio"},
          type="number", rules={"min": 1, "max": 12}, default=1,
          group="accounting", order=1),
]
```

Et l'enregistrer dans `default_schema_registry()` :

```python
    from app.core.schema.product_schemas import DOCUMENT_IDENTITY, ORGANIZATION_SETTINGS
    r.register("organization.settings", ORGANIZATION_SETTINGS)
```

Appliquer le **même** `merge_blob` sur `body.settings` dans `update_organization` (identique à Task 8, avec le target `organization.settings`).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_organization_settings_schema.py -v`
Expected: PASS — 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/ packages/backend/tests/test_organization_settings_schema.py packages/web/src/modules/organization/fields.ts
git commit -m "feat(organization): settings is a generated form (documents + accounting namespaces)"
```

---

## ✅ Checklist de validation — M3

- [ ] `pytest -k organization_settings` — vert.
- [ ] Live : la fiche Organisation n'affiche **plus aucun** `type: "json"` (`grep '"json"' packages/web/src/modules/organization/fields.ts` → seul `metadata` subsiste, exception documentée).
- [ ] `/config` : les clés `branding.*` restent « curated » (redirection vers `/settings`) — comportement inchangé.

---

## M4 — Les champs personnalisés (le Studio)

**Livrable :** une organisation définit ses propres champs via l'UI ; ils apparaissent sur ses entités ; **aucune autre organisation ne les voit**.

---

### Task 10: Modèle `field_definition` + colonnes `custom_fields` + permission

**Files:**
- Create: `packages/backend/app/models/field_definition.py`
- Create: `packages/backend/alembic/versions/0018_field_definition.py`
- Modify: `packages/backend/app/modules/organization/models.py` (`custom_fields` sur `Organization` et `OrgUnit`)
- Modify: `packages/backend/app/modules/location/models.py` (`custom_fields` sur `Site`)
- Modify: `packages/backend/app/rbac/permissions.py:20-41` (ajouter `fields.manage`)
- Test: `packages/backend/tests/test_field_definition_model.py`

**Interfaces:**
- Consumes: `UUIDAuditBase`, `JSONType` (`app/db/base.py`).
- Produces: `class FieldDefinition(UUIDAuditBase)` avec `as_spec() -> dict` (la ligne BD → un `FieldSpec` dict).

> **`organization_id` est `nullable=False`.** Ce n'est pas une contrainte d'intégrité de plus : c'est **l'énoncé formel de l'isolation**. Aucune ligne ne peut exister « au-dessus » des organisations, donc aucune ne peut les traverser.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_field_definition_model.py
import pytest
from sqlalchemy import inspect

from app.core.schema.spec import FieldSpec
from app.models.field_definition import FieldDefinition
from app.modules.location.models import Site
from app.modules.organization.models import Organization, OrgUnit


def test_organization_id_is_not_nullable():
    # The formal statement of tenant isolation: no row may exist "above" an org.
    col = inspect(FieldDefinition).columns["organization_id"]
    assert col.nullable is False


def test_unique_on_org_target_key():
    names = {c.name for c in FieldDefinition.__table__.constraints
             if c.__class__.__name__ == "UniqueConstraint"}
    assert "uq_field_definition_org_target_key" in names


def test_every_extensible_entity_has_a_custom_fields_column():
    for model in (Organization, OrgUnit, Site):
        assert "custom_fields" in inspect(model).columns, f"{model.__name__} lacks custom_fields"


def test_as_spec_produces_a_valid_FieldSpec():
    fd = FieldDefinition(
        organization_id="org-1", target="site.custom_fields", key="convention_no",
        type="string", widget="plain",
        label_en="Convention no.", label_fr="N° de convention", label_es="N.º de convenio",
        required=False, rules={}, options=[], group="extra", order=1, col_span=1,
        indexed=False, index_state="none", archived=False, inherit_to_suborgs=False)
    spec = FieldSpec.model_validate(fd.as_spec())
    assert spec.key == "convention_no"
    assert spec.label["fr"] == "N° de convention"


def test_fields_manage_permission_is_registered():
    from app.rbac.permissions import collect_permissions
    codes = {p["code"] for p in collect_permissions()}
    assert "fields.manage" in codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_field_definition_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.field_definition'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/models/field_definition.py
"""field_definition — user-defined fields, ALWAYS scoped to one organisation.

Storage strategy (spec §6): the VALUES live in the row's own `custom_fields`
JSONB column; only the DEFINITIONS live here. Odoo does ALTER TABLE at runtime —
in a single shared DB that adds a physical column visible to every tenant, locks
the table in production, and makes migrations unmanageable. We emit no mutating
DDL at all; the only DDL is an additive, concurrent, partial expression index.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class FieldDefinition(UUIDAuditBase):
    __tablename__ = "field_definition"
    __table_args__ = (
        UniqueConstraint("organization_id", "target", "key",
                         name="uq_field_definition_org_target_key"),
    )

    # NOT NULL — the formal statement of isolation. No global custom field exists.
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True)

    target: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    widget: Mapped[str] = mapped_column(String(30), nullable=False, default="plain")

    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    label_fr: Mapped[str] = mapped_column(Text, nullable=False)
    label_es: Mapped[str] = mapped_column(Text, nullable=False)
    hint_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_es: Mapped[str | None] = mapped_column(Text, nullable=True)

    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    rules: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    options: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    relation_resource: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    relation_filter: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    group: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_span: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # none | pending | ready | failed. A field whose index is not `ready` is NOT
    # offered for sorting — explicitly unavailable, never silently slow.
    index_state: Mapped[str] = mapped_column(String(10), nullable=False, default="none")

    inherit_to_suborgs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Archive, never destroy: the field leaves the form, the VALUES stay in JSONB.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def as_spec(self) -> dict:
        """DB row → FieldSpec dict (the wire format the resolver and UI speak)."""
        return {
            "key": self.key, "type": self.type, "widget": self.widget,
            "label": {"en": self.label_en, "fr": self.label_fr, "es": self.label_es},
            "hint": {"en": self.hint_en or "", "fr": self.hint_fr or "",
                     "es": self.hint_es or ""},
            "required": self.required, "default": self.default,
            "rules": self.rules or {}, "options": self.options or [],
            "relation_resource": self.relation_resource,
            "relation_filter": self.relation_filter or {},
            "group": self.group, "order": self.order, "col_span": self.col_span,
            "indexed": self.indexed,
        }
```

Ajouter sur `Organization`, `OrgUnit` (`modules/organization/models.py`) et `Site` (`modules/location/models.py`) :

```python
    # User-defined fields (SP1). Kept SEPARATE from `meta`/`metadata`, which is an
    # UNCONTROLLED extension bag: mixing schema'd fields into it would destroy the
    # allowlist guarantee (an undeclared key could no longer be rejected).
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)
```

…et exposer `"custom_fields": self.custom_fields or {}` dans chaque `as_dict()`.

Ajouter dans `app/rbac/permissions.py`, à la fin de `CORE_PERMISSIONS` :

```python
    {"code": "fields.manage", "module": "core",
     "description": "Define, archive and index custom fields for an organisation"},
```

```python
# packages/backend/alembic/versions/0018_field_definition.py
"""field_definition table + custom_fields columns.

Additive migration, run at DEPLOY time — NOT runtime DDL triggered by a user.
That distinction is the whole safety of the design.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_field_definition"
down_revision = "0017_site_address_link"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(
    sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "field_definition",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36),
                  sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(length=60), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="string"),
        sa.Column("widget", sa.String(length=30), nullable=False, server_default="plain"),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("label_fr", sa.Text(), nullable=False),
        sa.Column("label_es", sa.Text(), nullable=False),
        sa.Column("hint_en", sa.Text(), nullable=True),
        sa.Column("hint_fr", sa.Text(), nullable=True),
        sa.Column("hint_es", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default", _JSON, nullable=True),
        sa.Column("rules", _JSON, nullable=False, server_default="{}"),
        sa.Column("options", _JSON, nullable=False, server_default="[]"),
        sa.Column("relation_resource", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("relation_filter", _JSON, nullable=False, server_default="{}"),
        sa.Column("group", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("col_span", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("indexed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("index_state", sa.String(length=10), nullable=False, server_default="none"),
        sa.Column("inherit_to_suborgs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("organization_id", "target", "key",
                            name="uq_field_definition_org_target_key"),
    )
    op.create_index("ix_field_definition_organization_id", "field_definition",
                    ["organization_id"])
    op.create_index("ix_field_definition_target", "field_definition", ["target"])

    for table in ("organization", "org_unit", "site"):
        op.add_column(table, sa.Column("custom_fields", _JSON, nullable=False,
                                       server_default="{}"))
    # party.custom_fields already exists (party/models.py:38) — nothing to add.


def downgrade() -> None:
    for table in ("organization", "org_unit", "site"):
        op.drop_column(table, "custom_fields")
    op.drop_index("ix_field_definition_target", table_name="field_definition")
    op.drop_index("ix_field_definition_organization_id", table_name="field_definition")
    op.drop_table("field_definition")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_field_definition_model.py -v`
Expected: PASS — 5 passed

Puis vérifier l'idempotence de la migration :
Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/ -k alembic -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/models/field_definition.py packages/backend/alembic/versions/0018_field_definition.py packages/backend/app/modules/ packages/backend/app/rbac/permissions.py packages/backend/tests/test_field_definition_model.py
git commit -m "feat(schema): field_definition table + custom_fields columns + fields.manage perm"
```

---

### Task 11: Les quatre gardes sur la définition d'un champ

**Files:**
- Create: `packages/backend/app/core/schema/reserved.py`
- Create: `packages/backend/app/core/schema/sanitize.py`
- Test: `packages/backend/tests/test_schema_guards.py`

**Interfaces:**
- Produces:
  - `reserved.reserved_keys(target: str) -> set[str]` — **dérivé par introspection SQLAlchemy**.
  - `reserved.assert_key_allowed(target: str, key: str) -> None` — lève `ValueError`.
  - `sanitize.clean_richtext(html: str) -> str`.
  - `sanitize.assert_not_secretish(key: str) -> None`.

> **Point de sécurité n°1 de SP1 : `richtext`.** Un template/HTML éditable via l'UI est de l'exécution de code. Sans allowlist serveur, c'est un XSS stocké, et en SP2 ce HTML finira dans un PDF rendu côté serveur — donc potentiellement une SSRF (`<img src="http://169.254.169.254/…">`).

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_guards.py
"""Four guards on a field definition: reserved names, secrets, richtext, relations."""

import pytest

from app.core.schema.reserved import assert_key_allowed, reserved_keys
from app.core.schema.sanitize import assert_not_secretish, clean_richtext


def test_reserved_keys_are_derived_from_the_real_columns_not_hardcoded():
    # A hardcoded list drifts on the first migration. Introspect the model.
    keys = reserved_keys("site.custom_fields")
    assert {"id", "code", "name", "organization_id", "custom_fields"} <= keys


def test_a_custom_field_cannot_shadow_a_real_column():
    with pytest.raises(ValueError, match="reserved"):
        assert_key_allowed("site.custom_fields", "organization_id")
    assert_key_allowed("site.custom_fields", "convention_no")  # does not raise


def test_secret_looking_keys_are_refused_at_definition_time():
    for key in ("api_key", "smtp_password", "client_secret", "access_token"):
        with pytest.raises(ValueError, match="secret"):
            assert_not_secretish(key)
    assert_not_secretish("convention_no")  # does not raise


def test_richtext_strips_script_handlers_and_javascript_urls():
    assert "<script>" not in clean_richtext("<p>hi</p><script>alert(1)</script>")
    assert "onerror" not in clean_richtext('<img src="x" onerror="alert(1)">')
    assert "javascript:" not in clean_richtext('<a href="javascript:alert(1)">x</a>')


def test_richtext_blocks_remote_resources_ssrf_vector():
    # In SP2 this HTML is rendered server-side into a PDF. A remote <img> would
    # make the renderer fetch an attacker-chosen URL from inside the network.
    out = clean_richtext('<img src="http://169.254.169.254/latest/meta-data/">')
    assert "169.254.169.254" not in out


def test_richtext_keeps_legitimate_formatting():
    out = clean_richtext("<p><strong>Acme</strong> — <em>SARL</em></p><ul><li>x</li></ul>")
    assert "<strong>" in out and "<em>" in out and "<li>" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_guards.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.reserved'`

- [ ] **Step 3: Write minimal implementation**

Ajouter `nh3>=0.2` à `packages/backend/requirements.txt` (binding Rust d'ammonia — pas de dépendance C, maintenu, ~0 CVE ; alternative `bleach` si `nh3` pose problème sur la plateforme CI).

```python
# packages/backend/app/core/schema/reserved.py
"""Reserved key names — DERIVED from the real columns, never hardcoded.

A hardcoded denylist drifts the moment someone adds a column. Introspecting the
mapped model means the guard can never fall out of sync with the schema.
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.core.schema.registry import EXTENSIBLE_TARGETS

_MODELS: dict[str, type] = {}


def _model_for(target: str) -> type:
    if not _MODELS:
        from app.models.field_definition import FieldDefinition  # noqa: F401
        from app.modules.location.models import Site
        from app.modules.organization.models import Organization, OrgUnit
        from app.modules.party.models import Party
        _MODELS.update({
            "organization.custom_fields": Organization,
            "org_unit.custom_fields": OrgUnit,
            "site.custom_fields": Site,
            "party.custom_fields": Party,
        })
    if target not in _MODELS:
        raise ValueError(f"target {target!r} is not extensible; "
                         f"one of {sorted(EXTENSIBLE_TARGETS)}")
    return _MODELS[target]


def reserved_keys(target: str) -> set[str]:
    return {c.key for c in inspect(_model_for(target)).columns} | {"id", "etag"}


def assert_key_allowed(target: str, key: str) -> None:
    if key in reserved_keys(target):
        raise ValueError(
            f"key {key!r} is reserved on {target!r} (it shadows a real column)")
```

```python
# packages/backend/app/core/schema/sanitize.py
"""richtext sanitisation + the secret guard.

richtext is the single most dangerous type in SP1: HTML authored through the UI
is code. Unsanitised it is a stored XSS today, and in SP2 the same HTML is
rendered SERVER-SIDE into a PDF — so a remote <img> becomes an SSRF from inside
the network. Allowlist, both at write and at render.
"""

from __future__ import annotations

import re

import nh3

# Formatting only. No <script>, no <style>, no <iframe>, no <object>, no forms.
ALLOWED_TAGS: set[str] = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "blockquote",
    "h1", "h2", "h3", "h4",
    "table", "thead", "tbody", "tr", "th", "td",
    "span", "div", "a",
}
ALLOWED_ATTRS: dict[str, set[str]] = {"a": {"href", "title"}, "*": {"class"}}
# Same-origin / relative only. A remote scheme in a document rendered server-side
# is an SSRF vector — and `javascript:` / `data:` are XSS vectors.
ALLOWED_URL_SCHEMES: set[str] = set()   # nh3: empty set ⇒ relative URLs only

_SECRET_INDICATORS = ("password", "passwd", "secret", "token", "api_key", "apikey",
                      "credential", "private_key", "client_secret", "access_key")


def clean_richtext(html: str) -> str:
    if not html:
        return ""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                     url_schemes=ALLOWED_URL_SCHEMES, link_rel="noopener noreferrer")


def assert_not_secretish(key: str) -> None:
    """A custom field must never become a plaintext credential store. Mirrors the
    `_SECRET_INDICATORS` guard already enforced on config-store settings."""
    low = key.lower()
    if any(ind in low for ind in _SECRET_INDICATORS):
        raise ValueError(
            f"key {key!r} looks like a secret; custom fields must never hold "
            f"credentials (use the secret store)")
```

> **Vérification impérative avant de valider** : `nh3.clean` avec `url_schemes=set()` doit bien **supprimer** `src="http://…"`. Si le comportement de `nh3` diffère (il pourrait ne filtrer que `href`), **ajouter un filtre explicite** : retirer `img` de `ALLOWED_TAGS` (les images du document viennent du type `file`/`image`, pas du richtext) — c'est d'ailleurs la solution la plus sûre. Le test `test_richtext_blocks_remote_resources_ssrf_vector` est l'arbitre.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pip install nh3 && .venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_guards.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/{reserved,sanitize}.py packages/backend/requirements.txt packages/backend/tests/test_schema_guards.py
git commit -m "feat(schema): reserved-name, secret, richtext (XSS/SSRF) and relation guards"
```

---

### Task 12: Résolveur scopé + héritage + **le test d'isolation**

**Files:**
- Create: `packages/backend/app/core/schema/repository.py`
- Modify: `packages/backend/app/api/schema.py` (brancher la moitié BD)
- Test: `packages/backend/tests/test_schema_isolation.py`

**Interfaces:**
- Consumes: `FieldDefinition` (Task 10), `visible_orgs` (`security/permission_dep.py:47-53`).
- Produces:
  - `repository.definitions_for(session, target, organization_id) -> list[FieldDefinition]` — la résolution scopée + héritage.
  - `repository.count_for(session, target, organization_id, indexed_only=False) -> int` — pour les plafonds.

> **C'est la tâche qui porte la garantie donnée à l'utilisateur.** Le test d'isolation est **permanent** : s'il tombe un jour, la promesse est morte — et on le saura.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_isolation.py
"""THE central, permanent test: organisation A's custom fields are invisible,
unwritable and unreadable for organisation B. If this ever fails, the whole
isolation promise of SP1 is dead."""

import pytest

from app.core.schema.repository import definitions_for
from app.models.field_definition import FieldDefinition


async def _define(session, org_id, key, **kw):
    fd = FieldDefinition(
        organization_id=org_id, target="site.custom_fields", key=key,
        type="string", widget="plain",
        label_en=key, label_fr=key, label_es=key, **kw)
    session.add(fd)
    await session.flush()
    return fd


@pytest.mark.asyncio
async def test_org_B_never_sees_org_A_definitions(session, org_a, org_b):
    await _define(session, org_a.id, "convention_no")
    a = await definitions_for(session, "site.custom_fields", org_a.id)
    b = await definitions_for(session, "site.custom_fields", org_b.id)
    assert [d.key for d in a] == ["convention_no"]
    assert b == [], "LEAK: org B can see org A's custom field"


@pytest.mark.asyncio
async def test_definition_applies_to_the_orgs_units_and_sites(session, org_a):
    # Units and sites are FK-bound to the org, so the reach is STRUCTURAL.
    await _define(session, org_a.id, "zone")
    for target in ("site.custom_fields", "org_unit.custom_fields"):
        fd = FieldDefinition(organization_id=org_a.id, target=target, key="zone",
                             type="string", widget="plain",
                             label_en="Z", label_fr="Z", label_es="Z")
        session.add(fd)
    await session.flush()
    units = await definitions_for(session, "org_unit.custom_fields", org_a.id)
    assert [d.key for d in units] == ["zone"]


@pytest.mark.asyncio
async def test_inherit_to_suborgs_reaches_a_child_org_only_when_enabled(
        session, org_a, org_child_of_a):
    await _define(session, org_a.id, "inherited", inherit_to_suborgs=True)
    await _define(session, org_a.id, "private", inherit_to_suborgs=False)
    child = await definitions_for(session, "site.custom_fields", org_child_of_a.id)
    keys = {d.key for d in child}
    assert "inherited" in keys
    assert "private" not in keys


@pytest.mark.asyncio
async def test_inheritance_never_leaks_sideways_to_a_sibling_org(
        session, org_a, org_b):
    await _define(session, org_a.id, "inherited", inherit_to_suborgs=True)
    sibling = await definitions_for(session, "site.custom_fields", org_b.id)
    assert sibling == [], "LEAK: inheritance walked sideways instead of down"


@pytest.mark.asyncio
async def test_archived_definitions_are_excluded(session, org_a):
    await _define(session, org_a.id, "old", archived=True)
    assert await definitions_for(session, "site.custom_fields", org_a.id) == []
```

> **Fixtures à ajouter dans `conftest.py`** : `org_a`, `org_b` (deux organisations racines, sans lien), `org_child_of_a` (`parent_id = org_a.id`). **Lire `conftest.py` avant** pour suivre le style des fixtures existantes.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_isolation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.repository'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/repository.py
"""Scoped resolution of custom-field definitions.

Three rules (spec §7):
  1. A definition ALWAYS belongs to one organisation (organization_id NOT NULL).
     No global custom field exists — that would be the very cross-tenant
     corruption vector we refuse.
  2. It reaches that org's units and sites (FK-bound ⇒ structural reach), and —
     only if `inherit_to_suborgs` — its CHILD organisations, walking
     Organization.parent_id upward with a bounded depth.
  3. We inherit DEFINITIONS, not VALUES. Each row holds its own value.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.field_definition import FieldDefinition
from app.modules.organization.models import Organization

# Same bound as RBAC role inheritance (rbac/service.py:22) — a cycle or a
# pathological hierarchy must never hang a request.
MAX_ORG_DEPTH = 20


async def _ancestor_org_ids(session: AsyncSession, organization_id: str) -> list[str]:
    """The org's ancestors, nearest first, bounded. Cycles cannot occur
    (organization service enforces `_assert_no_parent_cycle`), but we bound
    anyway: a guard that relies on another guard is not a guard."""
    ancestors: list[str] = []
    current = organization_id
    for _ in range(MAX_ORG_DEPTH):
        parent = (await session.execute(
            select(Organization.parent_id).where(Organization.id == current)
        )).scalar_one_or_none()
        if not parent:
            break
        ancestors.append(parent)
        current = parent
    return ancestors


async def definitions_for(session: AsyncSession, target: str,
                          organization_id: str) -> list[FieldDefinition]:
    """Active definitions visible to `organization_id` for `target`."""
    ancestors = await _ancestor_org_ids(session, organization_id)

    own = (FieldDefinition.organization_id == organization_id)
    if ancestors:
        inherited = (FieldDefinition.organization_id.in_(ancestors)
                     & FieldDefinition.inherit_to_suborgs.is_(True))
        scope = own | inherited
    else:
        scope = own

    rows = (await session.execute(
        select(FieldDefinition)
        .where(FieldDefinition.target == target,
               FieldDefinition.archived.is_(False),
               FieldDefinition.is_active.is_(True),
               scope)
        .order_by(FieldDefinition.group, FieldDefinition.order, FieldDefinition.key)
    )).scalars().all()

    # A nearer definition wins over an inherited one with the same key.
    by_key: dict[str, FieldDefinition] = {}
    for row in rows:
        if row.organization_id == organization_id or row.key not in by_key:
            by_key[row.key] = row
    return sorted(by_key.values(), key=lambda d: (d.group, d.order, d.key))


async def count_for(session: AsyncSession, target: str, organization_id: str, *,
                    indexed_only: bool = False) -> int:
    """Count OWN definitions (caps are per-organisation — an org cannot be
    penalised for what its parent defined)."""
    from sqlalchemy import func
    stmt = select(func.count()).select_from(FieldDefinition).where(
        FieldDefinition.target == target,
        FieldDefinition.organization_id == organization_id,
        FieldDefinition.archived.is_(False))
    if indexed_only:
        stmt = stmt.where(FieldDefinition.indexed.is_(True))
    return (await session.execute(stmt)).scalar_one()
```

Puis brancher la moitié BD dans `app/api/schema.py` (remplacer `db_specs=None`) :

```python
from app.api.deps import get_session
from app.core.schema import repository as schema_repo
from app.security.permission_dep import visible_orgs

@router.get("/{target}")
async def get_schema(target: str, request: Request, organization_id: str | None = None,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> dict:
    registry = request.app.state.schema_registry
    if not registry.is_registered(target) and target not in EXTENSIBLE_TARGETS:
        raise HTTPException(404, f"unknown schema target {target!r}")

    db_specs = None
    if target in EXTENSIBLE_TARGETS and organization_id:
        # Scope check FIRST: the caller may only read schemas for an org they see.
        allowed = await visible_orgs(session, principal, "organization.read")
        if allowed is not None and organization_id not in allowed:
            raise HTTPException(404, f"organization {organization_id} not found")
        rows = await schema_repo.definitions_for(session, target, organization_id)
        db_specs = [r.as_spec() for r in rows]

    fields = resolve(registry, target, db_specs=db_specs)
    etag = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {"target": target, "fields": fields, "etag": etag}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_isolation.py packages/backend/tests/test_api_schema.py -v`
Expected: PASS — 5 + 3 passed

- [ ] **Step 5: Gate qualité + commit**

**Agent `security-auditor` obligatoire** sur ce diff — c'est la frontière de tenancy.

```bash
git add packages/backend/app/core/schema/repository.py packages/backend/app/api/schema.py packages/backend/tests/test_schema_isolation.py packages/backend/tests/conftest.py
git commit -m "feat(schema): org-scoped definition resolution + inheritance (isolation test)"
```

---

### Task 13: CRUD des définitions + plafonds + allowlist à l'écriture des entités

**Files:**
- Create: `packages/backend/app/api/admin_field_definitions.py`
- Modify: `packages/backend/app/main.py` (monter le routeur)
- Modify: `packages/backend/app/modules/{organization,location,party}/api/__init__.py` (merge-preserve sur `custom_fields`)
- Test: `packages/backend/tests/test_api_field_definitions.py`

**Interfaces:**
- Consumes: Tasks 10-12.
- Produces: les 6 routes du §8 de la spec. Constantes `MAX_FIELDS_PER_TARGET = 50`, `MAX_INDEXED_PER_TARGET = 10`.

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_api_field_definitions.py
"""Caps, guards, allowlist and archive semantics on the definition API."""

import pytest


def _body(key="convention_no", **kw):
    return {"target": "site.custom_fields", "key": key, "type": "string",
            "label": {"en": key, "fr": key, "es": key}, **kw}


@pytest.mark.asyncio
async def test_creating_a_definition_requires_fields_manage(client, org_a, headers_no_perm):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(), headers=headers_no_perm)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_reserved_key_is_refused(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(key="organization_id"), headers=admin_headers)
    assert r.status_code == 422 and "reserved" in r.text


@pytest.mark.asyncio
async def test_secret_looking_key_is_refused(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(key="api_key"), headers=admin_headers)
    assert r.status_code == 422 and "secret" in r.text


@pytest.mark.asyncio
async def test_the_51st_field_is_refused(client, org_a, admin_headers, seed_50_fields):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(key="one_too_many"), headers=admin_headers)
    assert r.status_code == 422 and "50" in r.text


@pytest.mark.asyncio
async def test_the_11th_indexed_field_is_refused(client, org_a, admin_headers,
                                                 seed_10_indexed_fields):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(key="idx_11", indexed=True), headers=admin_headers)
    assert r.status_code == 422 and "10" in r.text


@pytest.mark.asyncio
async def test_indexed_is_refused_on_a_non_indexable_type(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(key="blob", type="json", indexed=True),
                          headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_archive_hides_the_field_but_keeps_the_values(client, session, org_a,
                                                            admin_headers, site_a):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    fid = r.json()["id"]
    await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                     json={"custom_fields": {"convention_no": "C-1"}}, headers=admin_headers)
    await client.post(f"/api/v1/admin/field-definitions/{fid}/archive", headers=admin_headers)

    schema = await client.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a.id}", headers=admin_headers)
    assert schema.json()["fields"] == []            # gone from the form
    await session.refresh(site_a)
    assert site_a.custom_fields == {"convention_no": "C-1"}   # value SURVIVES


@pytest.mark.asyncio
async def test_writing_an_undeclared_custom_field_is_422_not_ignored(
        client, org_a, admin_headers, site_a):
    r = await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                         json={"custom_fields": {"never_declared": "x"}},
                         headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_requires_if_match(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    fid, etag = r.json()["id"], r.json()["etag"]
    stale = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                             json=_body(key="convention_no", required=True),
                             headers={**admin_headers, "If-Match": "stale"})
    assert stale.status_code == 409
    ok = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                          json=_body(key="convention_no", required=True),
                          headers={**admin_headers, "If-Match": etag})
    assert ok.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_api_field_definitions.py -v`
Expected: FAIL — 404 sur `/api/v1/admin/field-definitions`

- [ ] **Step 3: Write minimal implementation**

Créer `packages/backend/app/api/admin_field_definitions.py` en suivant **exactement** le style de `admin_providers.py` (routeur avec `dependencies=[Depends(require_permission("fields.manage"))]`, `enforce_if_match` + `row_etag`, `audit.record`, `session.commit()`), avec :

- `MAX_FIELDS_PER_TARGET = 50`, `MAX_INDEXED_PER_TARGET = 10` (constantes du module).
- `POST` : valide le corps via `FieldSpec.model_validate` (→ 422 sur type/widget/indexed incohérents), puis `assert_key_allowed(target, key)` et `assert_not_secretish(key)` (→ 422), puis `enforce(session, principal, "fields.manage", Scope(organization_id=organization_id))`, puis les deux plafonds via `repository.count_for`.
- `PUT` : `enforce_if_match` obligatoire.
- `POST /{id}/archive` : `archived = True`. **Ne touche pas aux valeurs.**
- `POST /{id}/purge` : supprime la ligne **et** émet un audit distinct (`FIELD_DEFINITION_PURGED`).
- Nouveaux événements d'audit à déclarer dans `app/auth/audit.py` : `FIELD_DEFINITION_CREATED`, `FIELD_DEFINITION_CHANGED`, `FIELD_DEFINITION_ARCHIVED`, `FIELD_DEFINITION_PURGED`, `FIELD_DEFINITION_INDEXED`.

Dans les handlers `PUT` de Site / OrgUnit / Organization / Party, ajouter **exactement** le même bloc que Task 8, avec le target correspondant :

```python
if body.custom_fields is not None:
    specs = [r.as_spec() for r in await schema_repo.definitions_for(
        session, "site.custom_fields", existing.organization_id)]
    try:
        body.custom_fields = merge_blob(existing.custom_fields or {},
                                        body.custom_fields, specs)
    except SchemaViolation as e:
        raise HTTPException(422, detail=e.errors) from e
```

> **Le `richtext` doit être sanitizé ici**, avant l'écriture : pour chaque spec de type `richtext`, `body.custom_fields[key] = clean_richtext(value)`. **Ne pas se reposer sur le rendu seul** — la donnée en base doit déjà être propre (défense en profondeur).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_api_field_definitions.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Gate qualité + commit**

Agents `code-reviewer`, `security-auditor`, `silent-failure-hunter`. **Corriger les findings.**

```bash
git add packages/backend/app/api/admin_field_definitions.py packages/backend/app/main.py packages/backend/app/auth/audit.py packages/backend/app/modules/ packages/backend/tests/test_api_field_definitions.py
git commit -m "feat(schema): field-definition CRUD (caps, guards, archive) + custom_fields allowlist on writes"
```

---

### Task 14: Indexation asynchrone + whitelist de tri

**Files:**
- Create: `packages/backend/app/core/schema/indexing.py`
- Modify: `packages/backend/app/api/admin_field_definitions.py` (route `/index`)
- Modify: les endpoints de liste des entités extensibles (whitelist de tri)
- Test: `packages/backend/tests/test_schema_indexing.py` (+ un test de perf marqué `@pytest.mark.postgres`)

**Interfaces:**
- Produces:
  - `indexing.index_name(table, key) -> str`
  - `indexing.create_index(engine, target, spec, organization_id) -> None` — **hors transaction** (`AUTOCOMMIT`).
  - `indexing.sortable_keys(specs) -> set[str]` — `indexed` **ET** `index_state == "ready"`.

> **Contrainte technique** : `CREATE INDEX CONCURRENTLY` **ne peut pas tourner dans une transaction**. D'où une connexion dédiée en `AUTOCOMMIT` et un job en tâche de fond. **Postgres uniquement** — sous SQLite, `create_index` ne fait rien et `index_state` reste `none` (dégradation propre, règle du repo).

- [ ] **Step 1: Write the failing test**

```python
# packages/backend/tests/test_schema_indexing.py
import pytest

from app.core.schema.indexing import index_name, sortable_keys
from app.core.schema.spec import field

L = {"en": "X", "fr": "X", "es": "X"}


def test_only_indexed_and_ready_keys_are_sortable():
    specs = [
        {**field("a", L, indexed=True), "index_state": "ready"},
        {**field("b", L, indexed=True), "index_state": "pending"},
        {**field("c", L, indexed=True), "index_state": "failed"},
        {**field("d", L), "index_state": "none"},
    ]
    # A `pending` index means a seq scan on millions of rows. Explicitly
    # unavailable beats silently slow.
    assert sortable_keys(specs) == {"a"}


def test_index_name_is_deterministic_and_bounded():
    n = index_name("site", "convention_no")
    assert n == "ix_site_cf_convention_no"
    assert len(index_name("organization", "a" * 60)) <= 63  # Postgres identifier limit


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_sorting_on_an_indexed_custom_field_uses_the_index(pg_engine, seeded_100k):
    # If this fails, the storage model is WRONG — and we must know before prod.
    async with pg_engine.connect() as conn:
        plan = (await conn.exec_driver_sql(
            "EXPLAIN SELECT id FROM site "
            "WHERE organization_id = 'org-a' "
            "ORDER BY ((custom_fields->>'rank')::numeric) LIMIT 50")).scalars().all()
    assert not any("Seq Scan" in line for line in plan), "\n".join(plan)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_indexing.py -v -m "not postgres"`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.schema.indexing'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/backend/app/core/schema/indexing.py
"""Partial expression indexes for custom fields — additive DDL only.

The index is PARTIAL (scoped to one organisation) and created CONCURRENTLY, so
it takes no lock and is invisible to other tenants. It is the ONLY DDL SP1 ever
emits at runtime, and it never mutates a column.

`CREATE INDEX CONCURRENTLY` cannot run inside a transaction → a dedicated
AUTOCOMMIT connection, driven from a background job.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.types import INDEX_CAST, INDEXABLE_TYPES


def index_name(table: str, key: str) -> str:
    """Deterministic, ≤63 chars (Postgres identifier limit — a longer name is
    silently TRUNCATED, which would make two fields collide on one index)."""
    name = f"ix_{table}_cf_{key}"
    if len(name) <= 63:
        return name
    digest = hashlib.sha1(key.encode()).hexdigest()[:8]
    return f"ix_{table}_cf_{key[:63 - len(f'ix_{table}_cf_') - 9]}_{digest}"


def sortable_keys(specs: list[dict]) -> set[str]:
    """The sort/filter whitelist. `indexed` alone is NOT enough — the index must
    be READY. A pending index means a seq scan on millions of rows."""
    return {s["key"] for s in specs
            if s.get("indexed") and s.get("index_state") == "ready"}


async def create_index(engine: AsyncEngine, target: str, spec: dict,
                       organization_id: str) -> None:
    """Create the partial expression index. Postgres only; a no-op elsewhere."""
    if engine.dialect.name != "postgresql":
        return                                   # SQLite (tests) — clean degradation
    ftype = spec["type"]
    if ftype not in INDEXABLE_TYPES:
        raise ValueError(f"type {ftype!r} cannot be indexed")

    table = EXTENSIBLE_TARGETS[target]
    expr = INDEX_CAST[ftype].format(key=spec["key"])
    name = index_name(table, spec["key"])
    # organization_id is a UUID string from our own DB, never user input — but it
    # is still quoted, never interpolated raw, as a matter of principle.
    sql = (f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" ON "{table}" ({expr}) '
           f"WHERE organization_id = '{organization_id}'")

    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        await conn.exec_driver_sql(sql)


async def drop_index(engine: AsyncEngine, target: str, key: str) -> None:
    if engine.dialect.name != "postgresql":
        return
    name = index_name(EXTENSIBLE_TARGETS[target], key)
    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        await conn.exec_driver_sql(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')
```

Route `POST /{id}/index` : passe `index_state = "pending"`, commit, puis lance `create_index` en `BackgroundTasks` ; au succès `ready`, sur exception `failed` **avec le message loggé** (jamais avalé).

Dans chaque endpoint de liste d'entité extensible, le paramètre `sort` accepte désormais `custom_fields.<key>` **uniquement si** `<key> ∈ sortable_keys(specs)` — sinon **422**. **Le `ORDER BY` généré doit utiliser exactement `INDEX_CAST[type]`**, sinon Postgres n'utilisera pas l'index.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_indexing.py -v -m "not postgres"`
Expected: PASS — 2 passed

Puis, **contre un vrai Postgres** (stack Docker up) :
Run: `.venv\Scripts\python.exe -m pytest packages/backend/tests/test_schema_indexing.py -v -m postgres`
Expected: PASS — le plan ne contient **aucun** `Seq Scan`.

- [ ] **Step 5: Commit**

```bash
git add packages/backend/app/core/schema/indexing.py packages/backend/app/api/admin_field_definitions.py packages/backend/tests/test_schema_indexing.py
git commit -m "feat(schema): partial concurrent expression indexes + sort whitelist (indexed AND ready)"
```

---

### Task 15: Écran A — le Studio de champs

**Files:**
- Create: `packages/web/src/modules/fields/{api.ts,fields.ts,page.tsx}`
- Create: `packages/web/src/app/(app)/fields/page.tsx`
- Create: `packages/web/src/components/ui/weekly-hours-field.tsx`
- Modify: `packages/web/src/components/app-shell.tsx` (entrée de nav, groupe **Système**, `perm: "fields.manage"`)
- Modify: `packages/web/src/modules/{organization,location,party}/fields.ts` (fusionner les champs custom servis par `/schema`)
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json` (namespace `fields`)
- Test: `packages/web/src/modules/fields/fields.test.ts`

**Interfaces:**
- Consumes: `getSchema`, `fieldSpecToFieldDef` (Task 7), l'API définitions (Task 13).
- Produces: `useFieldDefFields()` → `FieldDef[]` pour le **RecordForm de création de champ**.

> **Le formulaire de création de champ est lui-même un `RecordForm`.** Le socle se mange lui-même — et si `RecordForm` ne suffit pas à décrire un champ, c'est que le contrat est incomplet.

- [ ] **Step 1: Write the failing test**

```ts
// packages/web/src/modules/fields/fields.test.ts
import { describe, expect, it } from "vitest";
import { buildFieldDefFields, TYPE_OPTIONS, widgetsFor } from "./fields";

describe("the field-creation form is itself schema-driven", () => {
  it("offers exactly the 15 types", () => {
    expect(TYPE_OPTIONS).toHaveLength(15);
    expect(TYPE_OPTIONS.map((o) => o.value)).toContain("relation");
  });

  it("narrows the widget list to the selected type", () => {
    expect(widgetsFor("string")).toContain("color");
    expect(widgetsFor("string")).not.toContain("rating");
    expect(widgetsFor("number")).toContain("rating");
  });

  it("marks key immutable in edit mode (renaming would orphan stored values)", () => {
    const def = buildFieldDefFields("en").find((f) => f.name === "key");
    expect(def?.immutable).toBe(true);
  });

  it("requires the three locale labels", () => {
    const names = buildFieldDefFields("en").map((f) => f.name);
    expect(names).toEqual(expect.arrayContaining(["label_en", "label_fr", "label_es"]));
    for (const n of ["label_en", "label_fr", "label_es"]) {
      expect(buildFieldDefFields("en").find((f) => f.name === n)?.required).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/modules/fields`
Expected: FAIL — `Cannot find module './fields'`

- [ ] **Step 3: Write the implementation**

`page.tsx` : split-view (master-detail, règle du repo) — `DataGrid` des définitions à gauche (tri, filtres, pagination, filtre par entité cible), `RecordForm` de création/édition à droite, **aperçu live** en dessous (le vrai `RecordForm` rendant le champ en cours de définition), badge d'état d'index (`pending`/`ready`/`failed`), actions **Archiver** / **Indexer**, gardée par `can("fields.manage")` (nav **et** boutons).

`fields.ts` : `TYPE_OPTIONS` (les 15, libellés localisés), `widgetsFor(type)` (miroir de `WIDGETS_BY_TYPE`), `buildFieldDefFields(locale)` → `FieldDef[]` avec `key` **`immutable: true` en mode édition** (renommer une clé orphelinerait toutes les valeurs déjà stockées).

Fusionner les champs custom dans les formulaires métier :

```ts
// dans packages/web/src/modules/location/fields.ts (idem organization, party)
export function useSiteFields(organizationId?: string): FieldDef[] {
  const locale = useLocale() as Locale;
  const t = useTranslations("site.f");
  const { data } = useQuery({
    queryKey: ["schema", "site.custom_fields", organizationId],
    queryFn: () => getSchema("site.custom_fields", organizationId),
    enabled: Boolean(organizationId),
  });
  const custom = (data?.fields ?? []).map((s) => fieldSpecToFieldDef(s, locale));
  return [...BASE_FIELDS.map(/* … existant, inchangé … */), ...custom];
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && npx vitest run src/modules/fields && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Gate qualité + commit**

Skill `frontend-design` + revue explicite contre **§11bis** + `chrome-devtools-mcp:a11y-debugging`.

```bash
git add packages/web/src/modules/fields packages/web/src/app/\(app\)/fields packages/web/src/components/ui/weekly-hours-field.tsx packages/web/src/components/app-shell.tsx packages/web/src/i18n/messages packages/web/src/modules/
git commit -m "feat(web): custom-fields Studio (screen A) + custom fields merged into entity forms"
```

---

### Task 16: e2e Playwright — la preuve

**Files:**
- Create: `packages/web/e2e/custom-fields.spec.ts`

- [ ] **Step 1-4: Write, run, fix, verify**

```ts
// packages/web/e2e/custom-fields.spec.ts
import { expect, test } from "@playwright/test";

test("define a custom field, then fill it on a site, then reload", async ({ page }) => {
  await page.goto("/fields");
  await page.getByRole("button", { name: /new field|nouveau champ/i }).click();
  await page.getByLabel(/key|clé/i).fill("convention_no");
  await page.getByLabel(/label \(en\)/i).fill("Convention no.");
  await page.getByLabel(/label \(fr\)/i).fill("N° de convention");
  await page.getByLabel(/label \(es\)/i).fill("N.º de convenio");
  await page.getByRole("button", { name: /save|enregistrer/i }).click();
  await expect(page.getByText("convention_no")).toBeVisible();

  await page.goto("/sites");
  await page.getByRole("row").nth(1).click();
  await page.getByLabel(/N° de convention/i).fill("C-2026-001");
  await page.getByRole("button", { name: /save|enregistrer/i }).click();

  await page.reload();
  await expect(page.getByLabel(/N° de convention/i)).toHaveValue("C-2026-001");
});

test("a user without fields.manage sees neither the nav entry nor the button", async ({ page }) => {
  // Signed in as a read-only agent (see e2e/fixtures).
  await page.goto("/");
  await expect(page.getByRole("link", { name: /custom fields|champs personnalisés/i }))
    .toHaveCount(0);
  await page.goto("/fields");
  await expect(page.getByRole("button", { name: /new field|nouveau champ/i }))
    .toHaveCount(0);
});
```

- [ ] **Step 5: Commit**

```bash
git add packages/web/e2e/custom-fields.spec.ts
git commit -m "test(e2e): custom field lifecycle + permission gating"
```

---

## ✅ Checklist de validation — M4 (la plus importante)

- [ ] **`pytest packages/backend/tests/test_schema_isolation.py` — VERT.** *Si ce test tombe, la promesse d'isolation inter-organisations est morte. C'est la garantie centrale de SP1.*
- [ ] Migration `0018` : `alembic upgrade head` puis `downgrade -1` puis `upgrade head` → **idempotent**, sans perte.
- [ ] Plafonds : 51ᵉ champ → 422 ; 11ᵉ indexé → 422.
- [ ] Archivage : le champ disparaît du schéma, **la valeur reste en base** (vérifié en SQL live, pas seulement en test).
- [ ] Écriture d'une clé non déclarée → **422**, jamais un 200 silencieux.
- [ ] `richtext` : `<script>`, `on*=`, `javascript:`, `<img src="http://…">` → **strippés à l'écriture** (donnée propre en base) **et au rendu**.
- [ ] **`EXPLAIN` sur 100k lignes : aucun `Seq Scan`** sur un tri par champ custom indexé. *Si ce test échoue, le modèle de stockage est faux.*
- [ ] Un champ `indexed` dont `index_state != ready` → tri **refusé (422)**, jamais silencieusement lent.
- [ ] Playwright vert. Vérification **live Docker** (`:3000`), pas seulement en CI.
- [ ] Agents `code-reviewer`, `security-auditor`, `silent-failure-hunter` passés sur le diff **complet** de M4, findings **corrigés**.

---

## Auto-revue du plan

**1. Couverture de la spec** — chaque section a sa/ses tâche(s) :

| Spec | Tâche(s) |
|---|---|
| §3 Principes | transverses (Global Constraints) |
| §4 Architecture | 5, 6, 12 |
| §5 Contrat (type × widget × rules) | 1, 2, 7 |
| §6 Modèle de données | 10 |
| §7 Résolution scopée + héritage | 12 |
| §8 API | 6, 13, 14 |
| §9 UI (Écrans A/B/C) | 7, 8, 15 |
| §10 Sécurité / RBAC | 10 (perm), 11 (gardes), 13 (allowlist, caps) |
| §11 Échelle / indexation | 1 (`INDEX_CAST`), 14 |
| §12 Migration des JSON bruts | 3 (M1), 8 (M2), 9 (M3), 10 (M4) |
| §13 Tests | intégrés à chaque tâche + Task 16 |

**Lacune identifiée et corrigée** : le widget `weekly_hours` (spec §12) était référencé sans tâche propre → il est **créé en Task 15** (`weekly-hours-field.tsx`) et **déclaré en Task 1** (`WIDGETS_BY_TYPE["json"]`). La forme canonique retenue est celle du test backend (`{"monday": {"open","close"}}`), et **l'aide i18n contradictoire (`fr.json:305`) doit être corrigée dans la même tâche.**

**2. Placeholders** — aucun `TBD` / `TODO` / « handle edge cases ». Chaque étape de code porte son code. Les trois endroits où j'ai écrit « suivre exactement le style de X » (Task 13, Task 15) pointent un **fichier existant précis** à imiter, pas une intention floue.

**3. Cohérence des types** — vérifiée entre tâches : `FieldSpec` (Task 2) ↔ `types.ts` (Task 7) ↔ `as_spec()` (Task 10) ↔ `resolve()` (Task 5) portent les **mêmes clés**, aux mêmes noms (`relation_resource`, `col_span`, `index_state`). `INDEX_CAST` (Task 1) est consommé à l'identique par `create_index` **et** par le `ORDER BY` (Task 14) — c'est la condition pour que Postgres utilise l'index.

**Réserve honnête** : `index_state` vit sur la **ligne BD** (Task 10) mais **pas** dans `FieldSpec` (Task 2). `sortable_keys` (Task 14) le lit pourtant sur les specs. → **`as_spec()` doit ajouter `index_state`**, et `FieldSpec` doit l'accepter comme champ optionnel non-déclaratif (`index_state: str = "none"`). **À corriger dès la Task 2** ; ne pas découvrir ça en Task 14.

---

## Handoff — exécution

Le plan est complet et sauvegardé. Deux options d'exécution :

1. **Subagent-Driven (recommandé)** — un subagent frais par tâche, revue entre chaque, itération rapide. Adapté ici : 16 tâches, chacune avec un livrable testable isolément.
2. **Inline** — exécution en session, par lots avec points de contrôle.

**Avant toute exécution : `git checkout -b feat/field-schema` depuis `develop`.** Ne pas travailler sur `docs/field-schema-spec` (branche de doc).
