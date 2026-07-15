# D4-A — Éditeur de règles de validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le textarea JSON brut des règles de champ par un éditeur type-aware (inputs UI par type + « Règles avancées (JSON) » à clés disjointes), et étendre le jeu de règles réellement appliqué (backend `_coerce` + miroir zod).

**Architecture:** Le backend `app/core/schema/pydantic_gen.py:_coerce` est l'autorité : on lui ajoute des branches de règles par type (numeric/money d'abord, puis date/temps/multiselect/boolean/file). Le client `web/src/lib/schema/to-zod.ts:rulesToZod` reflète pour le feedback UX (non-autoritaire ; le 422 backend tranche). Le formulaire Studio (`web/src/modules/fields/fields.ts`, un `RecordForm`) troque son unique champ `rules` (JSON) contre des `FieldDef` type-aware `visible_if` + un champ `rules_advanced`, reliés à l'objet `rules` par des adaptateurs purs `flattenRules`/`nestRules` (garde disjointe).

**Tech Stack:** FastAPI/pydantic (backend), Next.js 15 + React 19 + zod + TanStack (frontend), pytest, Vitest, TypeScript strict.

## Global Constraints

- **Backend autoritaire d'abord** : chaque règle est appliquée dans `_coerce` (pytest vert) AVANT son miroir zod. Le miroir client est best-effort ; toute divergence est tranchée par le 422 (déjà mappé par `RecordForm.ApiError.fieldErrors()`).
- **Parité stricte** : aucun input UI sans règle backend correspondante ; aucune règle appliquée non éditable — sauf différés documentés (`max_size` fichier, offsets de dates relatifs type `today+30d`, règles inter-champs) qui restent accessibles via `rules_advanced`.
- **`rules` = JSONB additif, ZÉRO migration.** Backend `FieldSpec.rules` est déjà `dict[str, Any]` (spec.py:33) → aucun changement de type backend. Seul le type **frontend** `FieldRules` (types.ts) gagne des clés.
- **DRY descripteur** : « max decimal places » réutilise la clé EXISTANTE `rules.precision` (déjà dans `FieldRules`, non encore appliquée), pas une nouvelle clé.
- **`min`/`max`** deviennent `number | string` (numérique OU date ISO/token) dans `FieldRules`.
- **Tokens de dates** : seuls `today` (date) et `now` (datetime) sont supportés, résolus **UTC** au moment de la validation. `time` = ISO statique uniquement. Résolution via helpers `_today_utc()`/`_now_utc()` **monkeypatchables** (assertions déterministes).
- **i18n** : toute chaîne visible = clé `en`/`fr`/`es` dans le namespace `fields` (`web/src/i18n/messages/{en,fr,es}.json`).
- **Outils** : pytest via `C:\facil_framework\.venv\Scripts\python.exe -m pytest` ; vitest/tsc via `C:/facil_framework/node_modules/.bin/{vitest,tsc}` depuis `C:/facil_framework/packages/web`. Env vitest = `node` (pas de render-test lourd — tester les fonctions pures).
- **Branche** : `feat/field-rules-editor` (déjà créée). Commits `<type>(<scope>): <sujet>`, scope `frontend`/`backend`, header ≤ 100, corps via `git commit -F -`.

## File Structure

- `packages/backend/app/core/schema/pydantic_gen.py` — additions de règles dans `_coerce` + helpers `_today_utc`/`_now_utc`/`_resolve_dt_bound`.
- `packages/backend/tests/test_schema_pydantic_gen.py` — tests pytest (étend le fichier existant).
- `packages/web/src/lib/schema/types.ts` — étend `FieldRules`.
- `packages/web/src/lib/schema/to-zod.ts` — miroir zod des nouvelles règles.
- `packages/web/src/lib/schema/to-zod.test.ts` — tests vitest (étend l'existant).
- `packages/web/src/modules/fields/rules-adapter.ts` **(créer)** — `flattenRules`/`nestRules` + `UI_RULE_KEYS` + presets pattern.
- `packages/web/src/modules/fields/rules-adapter.test.ts` **(créer)** — tests vitest des adaptateurs.
- `packages/web/src/modules/fields/fields.ts` — remplace le champ `rules`, câble `flattenDefinition`/`buildDefinitionPayload`.
- `packages/web/src/i18n/messages/{en,fr,es}.json` — clés `fields.*` des nouveaux labels/hints/messages.

---

### Task 1 : Backend — règles numériques & money (`_coerce`)

Ajoute `step` (multiple-de) pour number/decimal, `precision` (max décimales) pour decimal, et `min`/`max` sur le montant `money`. Autorité serveur d'abord.

**Files:**
- Modify: `packages/backend/app/core/schema/pydantic_gen.py` (bloc `number/decimal` l.47-64 ; bloc `money` l.66-80)
- Test: `packages/backend/tests/test_schema_pydantic_gen.py`

**Interfaces:**
- Consumes: `validate_blob(specs, values)`, `field(...)` (from `app.core.schema.spec`), `SchemaViolation`.
- Produces: `rules` keys `step: number` (number/decimal), `precision: int` (decimal), `min`/`max` (money, comparés sur `Decimal(amount)`).

- [ ] **Step 1: Write the failing tests**

Ajouter à `test_schema_pydantic_gen.py` :
```python
def test_number_step_multiple_enforced():
    specs = [field("qty", L, type="number", rules={"step": 5})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"qty": 7})
    assert e.value.errors[0]["loc"] == ["qty"]
    assert "multiple of 5" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"qty": 10}) == {"qty": 10}

def test_decimal_precision_enforced():
    specs = [field("rate", L, type="decimal", rules={"precision": 2})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"rate": "1.234"})
    assert "at most 2 decimal places" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"rate": "1.23"}) == {"rate": "1.23"}

def test_money_amount_bounds_enforced():
    specs = [field("price", L, type="money", rules={"min": 10, "max": 100})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"price": {"amount": "5.00", "currency": "usd"}})
    assert e.value.errors[0]["loc"] == ["price"]
    assert "≥ 10" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"price": {"amount": "50.00", "currency": "usd"}}) \
        == {"price": {"amount": "50.00", "currency": "USD"}}
```

- [ ] **Step 2: Run — RED**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_schema_pydantic_gen.py -k "step or precision or money_amount_bounds" -v`
Expected: FAIL (règles non appliquées).

- [ ] **Step 3: Implement**

Dans le bloc `number/decimal`, après le check `max` et AVANT `if ftype == "number":` :
```python
        if "step" in rules:
            step = Decimal(str(rules["step"]))
            if step > 0 and (num % step) != 0:
                out.append(_err(key, f"must be a multiple of {rules['step']}"))
```
Puis, juste avant `return str(num)` (branche decimal) :
```python
        if "precision" in rules:
            exp = num.as_tuple().exponent
            places = -exp if isinstance(exp, int) and exp < 0 else 0
            if places > rules["precision"]:
                out.append(_err(key, f"at most {rules['precision']} decimal places"))
```
Dans le bloc `money`, après la validation de `value["amount"]` (après le `Decimal(value["amount"])` réussi, avant le `return`) :
```python
        amt = Decimal(value["amount"])
        if "min" in rules and amt < Decimal(str(rules["min"])):
            out.append(_err(key, f"amount must be ≥ {rules['min']}"))
        if "max" in rules and amt > Decimal(str(rules["max"])):
            out.append(_err(key, f"amount must be ≤ {rules['max']}"))
```

- [ ] **Step 4: Run — GREEN + non-régression**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_schema_pydantic_gen.py -v`
Expected: PASS (nouveaux + anciens).

- [ ] **Step 5: Commit**
```
git add packages/backend/app/core/schema/pydantic_gen.py packages/backend/tests/test_schema_pydantic_gen.py
git commit -F - <<'EOF'
feat(backend): regles number/decimal step+precision & money min/max (_coerce)
EOF
```

---

### Task 2 : Backend — dates/temps, multiselect, boolean, file (`_coerce`)

Ajoute `min`/`max` (date/datetime/time, avec tokens `today`/`now`), `min_items`/`max_items` (multiselect), `must_be_true` (boolean), `allowed_extensions` (file).

**Files:**
- Modify: `packages/backend/app/core/schema/pydantic_gen.py` (helpers en tête + blocs `date/datetime/time`, `multiselect`, `boolean`, `relation/file`)
- Test: `packages/backend/tests/test_schema_pydantic_gen.py`

**Interfaces:**
- Consumes: idem Task 1.
- Produces: `rules` keys `min`/`max` (date-like : ISO ou `"today"`/`"now"`), `min_items`/`max_items` (int, multiselect), `must_be_true` (bool), `allowed_extensions` (list[str], file). Helpers `_today_utc()->date`, `_now_utc()->datetime` (monkeypatchables).

- [ ] **Step 1: Write the failing tests**
```python
import datetime as _dt
from app.core.schema import pydantic_gen as pg

def test_date_min_static_iso():
    specs = [field("d", L, type="date", rules={"min": "2026-01-01"})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"d": "2025-12-31"})
    assert "≥ 2026-01-01" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"d": "2026-06-01"}) == {"d": "2026-06-01"}

def test_date_max_today_token(monkeypatch):
    monkeypatch.setattr(pg, "_today_utc", lambda: _dt.date(2026, 7, 15))
    specs = [field("birth", L, type="date", rules={"max": "today"})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"birth": "2026-07-16"})  # future
    assert "≤ today" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"birth": "2026-07-15"}) == {"birth": "2026-07-15"}

def test_multiselect_item_count_bounds():
    specs = [field("tags", L, type="multiselect", rules={"min_items": 1, "max_items": 2},
                   options=[{"value": v, "label": L} for v in ("a", "b", "c")])]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"tags": ["a", "b", "c"]})
    assert "at most 2" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"tags": ["a"]}) == {"tags": ["a"]}

def test_boolean_must_be_true():
    specs = [field("consent", L, type="boolean", rules={"must_be_true": True})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"consent": False})
    assert "must be accepted" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"consent": True}) == {"consent": True}

def test_file_allowed_extensions():
    specs = [field("doc", L, type="file", rules={"allowed_extensions": ["pdf", "png"]})]
    with pytest.raises(SchemaViolation) as e:
        validate_blob(specs, {"doc": "https://x/report.txt"})
    assert "must be one of" in e.value.errors[0]["msg"]
    assert validate_blob(specs, {"doc": "https://x/report.PDF"}) == {"doc": "https://x/report.PDF"}
```

- [ ] **Step 2: Run — RED**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_schema_pydantic_gen.py -k "date_min or today_token or item_count or must_be_true or allowed_extensions" -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

En tête du module (après les imports) :
```python
def _today_utc() -> _dt.date:
    return _dt.datetime.now(_dt.timezone.utc).date()

def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)

def _resolve_dt_bound(ftype: str, b: Any, parser) -> Any:
    if ftype == "date" and b == "today":
        return _today_utc()
    if ftype == "datetime" and b == "now":
        return _now_utc()
    return parser(b)  # ISO string of the same type
```
Dans le bloc `date/datetime/time`, remplacer le corps par (garder le parse existant, nommer `parsed`) :
```python
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
        if "min" in rules and parsed < _resolve_dt_bound(ftype, rules["min"], parser):
            out.append(_err(key, f"must be ≥ {rules['min']}"))
        if "max" in rules and parsed > _resolve_dt_bound(ftype, rules["max"], parser):
            out.append(_err(key, f"must be ≤ {rules['max']}"))
        return value
```
Dans le bloc `multiselect`, avant `return value` :
```python
        n = len(value)
        if "min_items" in rules and n < rules["min_items"]:
            out.append(_err(key, f"select at least {rules['min_items']}"))
        if "max_items" in rules and n > rules["max_items"]:
            out.append(_err(key, f"select at most {rules['max_items']}"))
```
Dans le bloc `boolean`, avant `return value` :
```python
        if rules.get("must_be_true") and value is not True:
            out.append(_err(key, "must be accepted"))
```
Dans le bloc `relation/file`, avant `return value` :
```python
        if ftype == "file" and rules.get("allowed_extensions"):
            exts = [str(e).lower().lstrip(".") for e in rules["allowed_extensions"]]
            ext = value.rsplit(".", 1)[-1].lower() if "." in value else ""
            if ext not in exts:
                out.append(_err(key, f"must be one of {exts}"))
```

- [ ] **Step 4: Run — GREEN + suite complète**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_schema_pydantic_gen.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```
git add packages/backend/app/core/schema/pydantic_gen.py packages/backend/tests/test_schema_pydantic_gen.py
git commit -F - <<'EOF'
feat(backend): regles date/temps (today/now) + multiselect/boolean/file (_coerce)
EOF
```

---

### Task 3 : Frontend — type `FieldRules` + miroir zod

Étend `FieldRules` (nouvelles clés) et `rulesToZod` (miroir des règles là où la forme RecordForm le permet proprement : number/decimal `step`/`precision`, date/datetime/time `min`/`max`). Les mirrors multiselect/boolean/money/file restent **backend-autoritaires** (formes RecordForm non-scalaires ; le 422 tranche) — documenté, pas un trou de parité (la règle EST appliquée).

**Files:**
- Modify: `packages/web/src/lib/schema/types.ts` (`FieldRules`)
- Modify: `packages/web/src/lib/schema/to-zod.ts` (`rulesToZod`)
- Test: `packages/web/src/lib/schema/to-zod.test.ts`

**Interfaces:**
- Consumes: `FieldSpec`, `FieldRules`.
- Produces: `FieldRules` avec `step?`, `precision?` (déjà), `min_items?`, `max_items?`, `must_be_true?`, `allowed_extensions?`, et `min?`/`max?` élargis à `number | string`. `rulesToZod(spec)` inchangé en signature.

- [ ] **Step 1: Write the failing tests**

Ajouter à `to-zod.test.ts` :
```typescript
it("number step: rejects non-multiples, accepts multiples", () => {
  const s = rulesToZod({ key: "q", type: "number", rules: { step: 5 } } as FieldSpec);
  expect(s.safeParse("7").success).toBe(false);
  expect(s.safeParse("10").success).toBe(true);
});

it("date min (static ISO): rejects earlier dates", () => {
  const s = rulesToZod({ key: "d", type: "date", rules: { min: "2026-01-01" } } as FieldSpec);
  expect(s.safeParse("2025-12-31").success).toBe(false);
  expect(s.safeParse("2026-06-01").success).toBe(true);
});
```

- [ ] **Step 2: Run — RED**

Run (depuis `packages/web`): `"C:/facil_framework/node_modules/.bin/vitest" run src/lib/schema/to-zod.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

Dans `types.ts`, remplacer `FieldRules` par :
```typescript
export interface FieldRules {
  min?: number | string;   // numeric OR date ISO/token ("today"/"now")
  max?: number | string;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  precision?: number;      // decimal: max decimal places (now enforced)
  step?: number;           // number/decimal: multiple-of
  min_items?: number;      // multiselect
  max_items?: number;      // multiselect
  must_be_true?: boolean;  // boolean
  allowed_extensions?: string[]; // file
  visible_if?: Condition;
  required_if?: Condition;
}
```
Dans `to-zod.ts`, dans le bloc `number`/`decimal`, après le refine `max` :
```typescript
    if (r.step !== undefined)
      s = s.refine((v) => v === "" || Number(v) % r.step! === 0, `${label} must be a multiple of ${r.step}`);
    if (r.precision !== undefined)
      s = s.refine((v) => v === "" || (v.split(".")[1]?.length ?? 0) <= r.precision!,
        `${label}: at most ${r.precision} decimal places`);
```
Ajouter, AVANT le fallback string (l.27), un bloc date :
```typescript
  if (spec.type === "date" || spec.type === "datetime" || spec.type === "time") {
    const resolve = (b: number | string): string =>
      b === "today" ? new Date().toISOString().slice(0, 10)
        : b === "now" ? new Date().toISOString().slice(0, 19)
        : String(b);
    let d: z.ZodTypeAny = z.string();
    if (r.min !== undefined)
      d = d.refine((v) => v === "" || v >= resolve(r.min!), `${label} must be ≥ ${r.min}`);
    if (r.max !== undefined)
      d = d.refine((v) => v === "" || v <= resolve(r.max!), `${label} must be ≤ ${r.max}`);
    if (spec.required) d = d.refine((v) => v !== "", `${label} is required`);
    return d;
  }
```
(La comparaison lexicographique de chaînes ISO est correcte pour date/datetime/time bien formés — feedback UX ; le backend reste l'autorité.)

- [ ] **Step 4: Run — GREEN + tsc**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/lib/schema/to-zod.test.ts` puis `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0.

- [ ] **Step 5: Commit**
```
git add packages/web/src/lib/schema/types.ts packages/web/src/lib/schema/to-zod.ts packages/web/src/lib/schema/to-zod.test.ts
git commit -F - <<'EOF'
feat(frontend): FieldRules etendu + miroir zod (step/precision, dates min/max)
EOF
```

---

### Task 4 : Frontend — adaptateurs `flattenRules`/`nestRules` (garde disjointe)

Fonctions pures qui traduisent l'objet `rules` ⇄ valeurs de formulaire plates, avec presets pattern et garde disjointe (clé UI dans le JSON avancé → erreur).

**Files:**
- Create: `packages/web/src/modules/fields/rules-adapter.ts`
- Test: `packages/web/src/modules/fields/rules-adapter.test.ts`

**Interfaces:**
- Consumes: `FieldRules` (types.ts).
- Produces:
  - `UI_RULE_KEYS: readonly string[]` — les clés `rules` possédées par l'UI (`min,max,min_length,max_length,pattern,step,precision,min_items,max_items,must_be_true,allowed_extensions`).
  - `PATTERN_PRESETS: { value: string; pattern: string }[]` — `email,phone,url,slug,alphanumeric` (+ `custom` = "").
  - `flattenRules(rules: FieldRules): { form: Record<string, unknown>; advanced: Record<string, unknown> }` — répartit les clés UI vers `form.rule_<key>` (dates → `rule_date_min`/`rule_date_max` ; money min/max → `rule_money_min`/`rule_money_max` ; numeric min/max → `rule_min`/`rule_max`), le reste dans `advanced`.
  - `nestRules(form: Record<string, unknown>, advanced: Record<string, unknown>): { rules: FieldRules; error?: string }` — recompose `rules` = clés UI (coalescées : `min = rule_min ?? rule_date_min ?? rule_money_min`) ∪ `advanced` ; si `advanced` contient une `UI_RULE_KEYS` → `{ rules: {}, error: "<key> is managed via the UI — remove it from Advanced JSON" }`.

- [ ] **Step 1: Write the failing tests**
```typescript
import { describe, it, expect } from "vitest";
import { flattenRules, nestRules, UI_RULE_KEYS } from "./rules-adapter";

describe("rules-adapter", () => {
  it("flattenRules splits UI keys from advanced", () => {
    const { form, advanced } = flattenRules({ min_length: 2, pattern: "^x$", foo: 1 } as any);
    expect(form.rule_min_length).toBe(2);
    expect(form.rule_pattern).toBe("^x$");
    expect(advanced).toEqual({ foo: 1 });
  });
  it("nestRules merges UI + advanced and coalesces min/max", () => {
    const { rules, error } = nestRules({ rule_date_min: "2026-01-01" }, { foo: 1 });
    expect(error).toBeUndefined();
    expect(rules).toEqual({ min: "2026-01-01", foo: 1 });
  });
  it("nestRules rejects a UI-owned key placed in Advanced JSON (disjoint guard)", () => {
    const { error } = nestRules({}, { min_length: 3 });
    expect(error).toMatch(/min_length/);
  });
  it("UI_RULE_KEYS covers the managed set", () => {
    expect(UI_RULE_KEYS).toContain("must_be_true");
    expect(UI_RULE_KEYS).toContain("allowed_extensions");
  });
});
```

- [ ] **Step 2: Run — RED**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/modules/fields/rules-adapter.test.ts`
Expected: FAIL (module absent).

- [ ] **Step 3: Implement**

Créer `packages/web/src/modules/fields/rules-adapter.ts` :
```typescript
import type { FieldRules } from "@/lib/schema/types";

export const UI_RULE_KEYS = [
  "min", "max", "min_length", "max_length", "pattern", "step", "precision",
  "min_items", "max_items", "must_be_true", "allowed_extensions",
] as const;

export const PATTERN_PRESETS: { value: string; pattern: string }[] = [
  { value: "email", pattern: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$" },
  { value: "phone", pattern: "^[+]?[0-9 ()-]{6,}$" },
  { value: "url", pattern: "^https?://.+" },
  { value: "slug", pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$" },
  { value: "alphanumeric", pattern: "^[a-zA-Z0-9]+$" },
  { value: "custom", pattern: "" },
];

// Split the rules object into flat form values (rule_<key>) + leftover advanced.
export function flattenRules(rules: FieldRules): {
  form: Record<string, unknown>; advanced: Record<string, unknown>;
} {
  const r = { ...(rules ?? {}) } as Record<string, unknown>;
  const form: Record<string, unknown> = {};
  const put = (k: string, v: unknown) => { if (v !== undefined) form[k] = v; };
  // numeric min/max, dates, money all read from rules.min/max — the visible input
  // per type owns it; we pre-fill all three targets, hidden ones are ignored.
  put("rule_min", r.min); put("rule_max", r.max);
  put("rule_date_min", r.min); put("rule_date_max", r.max);
  put("rule_money_min", r.min); put("rule_money_max", r.max);
  put("rule_min_length", r.min_length); put("rule_max_length", r.max_length);
  put("rule_pattern", r.pattern); put("rule_step", r.step); put("rule_precision", r.precision);
  put("rule_min_items", r.min_items); put("rule_max_items", r.max_items);
  put("rule_must_be_true", r.must_be_true); put("rule_allowed_extensions", r.allowed_extensions);
  const advanced: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r)) {
    if (!(UI_RULE_KEYS as readonly string[]).includes(k) && k !== "visible_if" && k !== "required_if")
      advanced[k] = v;
  }
  // keep condition keys in advanced so they round-trip untouched
  if (r.visible_if !== undefined) advanced.visible_if = r.visible_if;
  if (r.required_if !== undefined) advanced.required_if = r.required_if;
  return { form, advanced };
}

// Recompose rules from flat form values + the advanced JSON; disjoint guard.
export function nestRules(
  form: Record<string, unknown>, advanced: Record<string, unknown>,
): { rules: FieldRules; error?: string } {
  const adv = advanced ?? {};
  for (const k of Object.keys(adv)) {
    if ((UI_RULE_KEYS as readonly string[]).includes(k))
      return { rules: {}, error: `${k} is managed via the UI — remove it from Advanced JSON` };
  }
  const out: Record<string, unknown> = { ...adv };
  const first = (...vs: unknown[]) => vs.find((v) => v !== undefined && v !== "" && v !== null);
  const set = (k: string, v: unknown) => { if (v !== undefined && v !== "" && v !== null) out[k] = v; };
  set("min", first(form.rule_min, form.rule_date_min, form.rule_money_min));
  set("max", first(form.rule_max, form.rule_date_max, form.rule_money_max));
  set("min_length", form.rule_min_length); set("max_length", form.rule_max_length);
  set("pattern", form.rule_pattern); set("step", form.rule_step); set("precision", form.rule_precision);
  set("min_items", form.rule_min_items); set("max_items", form.rule_max_items);
  set("allowed_extensions", form.rule_allowed_extensions);
  if (form.rule_must_be_true === true) out.must_be_true = true;
  return { rules: out as FieldRules };
}
```

- [ ] **Step 4: Run — GREEN + tsc**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/modules/fields/rules-adapter.test.ts` + `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0.

- [ ] **Step 5: Commit**
```
git add packages/web/src/modules/fields/rules-adapter.ts packages/web/src/modules/fields/rules-adapter.test.ts
git commit -F - <<'EOF'
feat(frontend): adaptateurs flattenRules/nestRules + garde disjointe UI/JSON
EOF
```

---

### Task 5 : Frontend — UI Studio type-aware (RecordForm)

Remplace le champ unique `rules` (JSON) par des `FieldDef` type-aware `visible_if` + le select preset pattern + « Règles avancées (JSON) », relie via les adaptateurs, ajoute la sanity zod et l'i18n.

**Files:**
- Modify: `packages/web/src/modules/fields/fields.ts` (`buildFieldDefFields` l.186-226 ; `flattenDefinition` l.266-290 ; `buildDefinitionPayload` l.292-305)
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json` (namespace `fields`)
- Test: `packages/web/src/modules/fields/rules-adapter.test.ts` (couvre déjà la logique ; ajouter un test de sanity si une fonction pure est extraite)

**Interfaces:**
- Consumes: `flattenRules`, `nestRules`, `UI_RULE_KEYS`, `PATTERN_PRESETS` (Task 4) ; `FieldDef` (record-form.tsx) ; `visible_if` conditions.
- Produces: le formulaire Studio expose les inputs de règles selon `type` ; `buildDefinitionPayload` renvoie l'erreur de `nestRules` comme erreur de champ `rules_advanced`.

- [ ] **Step 1: Write the failing test (sanity helper)**

Extraire une petite fonction pure `ruleSanity(form)` dans `rules-adapter.ts` (min≤max, step>0, min_length≤max_length, min_items≤max_items, regex compilable) et la tester :
```typescript
import { ruleSanity } from "./rules-adapter";
it("ruleSanity flags min>max and bad regex", () => {
  expect(ruleSanity({ rule_min: 5, rule_max: 1 }).error).toMatch(/min/);
  expect(ruleSanity({ rule_pattern: "([" }).error).toMatch(/pattern|regex/i);
  expect(ruleSanity({ rule_min_length: 1, rule_max_length: 3 }).error).toBeUndefined();
});
```

- [ ] **Step 2: Run — RED**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/modules/fields/rules-adapter.test.ts`
Expected: FAIL (`ruleSanity` absent).

- [ ] **Step 3: Implement**

Ajouter `ruleSanity` à `rules-adapter.ts` :
```typescript
export function ruleSanity(form: Record<string, unknown>): { error?: string } {
  const n = (v: unknown) => (v === "" || v === undefined || v === null ? undefined : Number(v));
  const pairs: [unknown, unknown, string][] = [
    [n(form.rule_min), n(form.rule_max), "min must be ≤ max"],
    [n(form.rule_min_length), n(form.rule_max_length), "min length must be ≤ max length"],
    [n(form.rule_min_items), n(form.rule_max_items), "min items must be ≤ max items"],
  ];
  for (const [lo, hi, msg] of pairs)
    if (lo !== undefined && hi !== undefined && (lo as number) > (hi as number)) return { error: msg };
  const step = n(form.rule_step);
  if (step !== undefined && step <= 0) return { error: "step must be > 0" };
  const p = form.rule_pattern;
  if (typeof p === "string" && p) { try { new RegExp(p); } catch { return { error: "pattern is not a valid regex" }; } }
  return {};
}
```
Dans `fields.ts` `buildFieldDefFields`, **supprimer** la ligne `{ name: "rules", type: "json", ... }` (l.224) et insérer à la place la section Validation (chaque champ `visible_if` sur `type`; `t()` = le traducteur `fields` déjà en place) — exemples représentatifs (répliquer le motif pour toutes les clés de la matrice) :
```typescript
    // --- Validation (type-aware) ---
    { name: "rule_min_length", label: t("rule.min_length"), type: "number",
      rules: { visible_if: { field: "type", op: "in", value: ["string", "text", "richtext"] } } },
    { name: "rule_max_length", label: t("rule.max_length"), type: "number",
      rules: { visible_if: { field: "type", op: "in", value: ["string", "text", "richtext"] } } },
    { name: "rule_pattern_preset", label: t("rule.pattern_preset"), type: "select",
      selectOptions: PATTERN_PRESETS.map((p) => ({ value: p.value, label: ft(locale, `fields.rule.preset.${p.value}`) })),
      rules: { visible_if: { field: "type", op: "in", value: ["string", "text", "richtext"] } } },
    { name: "rule_pattern", label: t("rule.pattern"), hint: t("rule.pattern_hint"),
      rules: { visible_if: { field: "type", op: "in", value: ["string", "text", "richtext"] } } },
    { name: "rule_min", label: t("rule.min"), type: "number",
      rules: { visible_if: { field: "type", op: "in", value: ["number", "decimal"] } } },
    { name: "rule_max", label: t("rule.max"), type: "number",
      rules: { visible_if: { field: "type", op: "in", value: ["number", "decimal"] } } },
    { name: "rule_step", label: t("rule.step"), type: "number",
      rules: { visible_if: { field: "type", op: "in", value: ["number", "decimal"] } } },
    { name: "rule_precision", label: t("rule.precision"), type: "number",
      rules: { visible_if: { field: "type", op: "eq", value: "decimal" } } },
    { name: "rule_money_min", label: t("rule.money_min"), type: "number",
      rules: { visible_if: { field: "type", op: "eq", value: "money" } } },
    { name: "rule_money_max", label: t("rule.money_max"), type: "number",
      rules: { visible_if: { field: "type", op: "eq", value: "money" } } },
    { name: "rule_date_min", label: t("rule.date_min"), hint: t("rule.date_token_hint"),
      rules: { visible_if: { field: "type", op: "in", value: ["date", "datetime", "time"] } } },
    { name: "rule_date_max", label: t("rule.date_max"), hint: t("rule.date_token_hint"),
      rules: { visible_if: { field: "type", op: "in", value: ["date", "datetime", "time"] } } },
    { name: "rule_min_items", label: t("rule.min_items"), type: "number",
      rules: { visible_if: { field: "type", op: "eq", value: "multiselect" } } },
    { name: "rule_max_items", label: t("rule.max_items"), type: "number",
      rules: { visible_if: { field: "type", op: "eq", value: "multiselect" } } },
    { name: "rule_must_be_true", label: t("rule.must_be_true"), type: "checkbox",
      rules: { visible_if: { field: "type", op: "eq", value: "boolean" } } },
    { name: "rule_allowed_extensions", label: t("rule.allowed_extensions"), hint: t("rule.exts_hint"),
      rules: { visible_if: { field: "type", op: "eq", value: "file" } } },
    { name: "rules_advanced", label: t("rules_advanced"), type: "json", hint: t("rules_advanced_hint"), colSpan: 2 },
```
(Note : `rule_allowed_extensions` est saisie texte « pdf, png » ; `flattenRules`/`nestRules` gèrent la liste — dans `buildDefinitionPayload`, splitter la chaîne par virgules en tableau avant `nestRules`, et joindre en chaîne dans `flattenDefinition`. Le preset pattern : dans `buildDefinitionPayload`, si `rule_pattern_preset` ≠ `custom`/"" et `rule_pattern` vide, utiliser le `PATTERN_PRESETS` correspondant.)

Câbler les adaptateurs :
- `flattenDefinition` (l.266) : remplacer `rules: row.rules ?? {}` par l'étalement de `flattenRules(row.rules ?? {})` :
```typescript
  const { form: ruleForm, advanced } = flattenRules(row.rules ?? {});
  // ... dans l'objet retourné, retirer `rules`, ajouter :
  ...ruleForm,
  rule_allowed_extensions: Array.isArray(row.rules?.allowed_extensions)
    ? (row.rules!.allowed_extensions as string[]).join(", ") : "",
  rules_advanced: advanced,
```
- `buildDefinitionPayload` (l.292) : remplacer `rules: payload.rules ?? {}` par :
```typescript
  const exts = typeof payload.rule_allowed_extensions === "string" && payload.rule_allowed_extensions.trim()
    ? payload.rule_allowed_extensions.split(",").map((s) => s.trim()).filter(Boolean) : undefined;
  const form = { ...payload, rule_allowed_extensions: exts };
  const sanity = ruleSanity(form);
  if (sanity.error) throw new FieldError("rules_advanced", sanity.error); // or the offending field
  const { rules, error } = nestRules(form, (payload.rules_advanced as Record<string, unknown>) ?? {});
  if (error) throw new FieldError("rules_advanced", error);
  // ... rules dans le payload retourné
```
(Adapter `FieldError` au mécanisme d'erreur de champ existant du module — si `buildDefinitionPayload` ne peut pas throw d'erreur de champ, faire remonter `{error}` au caller `page.tsx` qui pose l'erreur sur `rules_advanced` ; suivre le pattern d'erreur déjà utilisé par la page Studio. LIRE `page.tsx` pour le mécanisme exact avant d'implémenter.)

Ajouter les clés i18n `fields.rule.*`, `fields.rules_advanced`, `fields.rules_advanced_hint`, `fields.rule.preset.*` dans `en.json`/`fr.json`/`es.json` (mêmes clés, 3 langues).

- [ ] **Step 4: Run — GREEN + tsc + vitest complet**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run` + `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0. (Si la stack est up : smoke live `/fields` — créer une def string avec min/max length via UI, vérifier l'aperçu ; optionnel.)

- [ ] **Step 5: Commit**
```
git add packages/web/src/modules/fields/fields.ts packages/web/src/modules/fields/rules-adapter.ts packages/web/src/modules/fields/rules-adapter.test.ts packages/web/src/i18n/messages/
git commit -F - <<'EOF'
feat(frontend): Studio /fields — editeur de regles type-aware + JSON avance + i18n
EOF
```

---

### Task 6 : Gate finale — parité, suites, tsc

Vérifier l'ensemble par exécution réelle et la parité.

**Files:** aucun code neuf (corrections issues de la revue seulement).

- [ ] **Step 1: Suites backend + frontend**

Run:
```
"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_schema_pydantic_gen.py packages/backend/tests/test_api_field_definitions.py -v
cd packages/web && "C:/facil_framework/node_modules/.bin/vitest" run && "C:/facil_framework/node_modules/.bin/tsc" --noEmit
```
Expected: tout vert, tsc exit 0.

- [ ] **Step 2: Revue parité (checklist)**

Vérifier point par point : chaque clé de la matrice §2 de la spec a (a) une branche `_coerce`, (b) un input UI `visible_if` sur le bon type, (c) — quand pertinent — un miroir zod ; et réciproquement aucun input UI sans règle backend. Consigner les différés (`max_size`, offsets relatifs, inter-champs) comme accessibles via `rules_advanced`. Corriger tout écart avant de clore.

- [ ] **Step 3: Commit (si corrections)**
```
git add -A && git commit -F - <<'EOF'
chore(frontend): gate D4-A — corrections parite/revue
EOF
```
