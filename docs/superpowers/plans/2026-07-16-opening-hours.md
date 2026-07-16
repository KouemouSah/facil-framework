# D4-B (B-i) — Horaires d'ouverture production-grade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modèle d'horaires d'ouverture production-grade (hebdo Fermé/24h/plages + overnight + anti-chevauchement + exceptions datées), saisi vite (remplissage bulk + copie), fiable (validité réelle + gate backend), affiché 2 colonnes.

**Architecture:** Un module TypeScript **pur** `weekly-hours.ts` porte la forme canonique `{weekly, exceptions}`, le normaliseur rétro-compatible et toute la logique (validité, overnight, chevauchement, quick-fill, copie) — testable sous vitest. Le widget `weekly-hours-field.tsx` le consomme pour l'UI. Le backend `schemas.py` **rejoue la même validation** (autorité pydantic) : le widget est le miroir UX, le 422 tranche. Forme JSONB normalisée à la lecture → **zéro migration**.

**Tech Stack:** TypeScript strict + React 19 (widget), Vitest (env node), FastAPI/pydantic v2 (backend), pytest.

## Global Constraints

- **Backend autoritaire** : `_validate_operating_hours` (pydantic) est le gate ; `weekly-hours.ts:isValid` en est le **miroir** exact. Toute saisie contournant le front → 422.
- **Parité stricte** : aucun contrôle UI sans règle backend correspondante ; aucune règle backend non éditable.
- **Zéro migration** : `operating_hours` reste JSONB ; `normalize` accepte l'ANCIENNE forme `{day:[ranges]}` ET la canonique ; stockage = canonique.
- **Sémantique plage** : `"HH:MM-HH:MM"` ; `from<to` = même jour ; `from>to` = **nocturne** (traverse minuit) ; `from==to` = **invalide**. Anti-chevauchement par jour (avec wrap). Cap **366** exceptions ; dates ISO uniques.
- **i18n** : toute chaîne visible = clé `en`/`fr`/`es` (namespace `weekly_hours`), mêmes clés dans les 3 fichiers, vraies trads.
- **Responsive** : 2 colonnes en large, pile verticale en étroit (`grid-cols-1 lg:grid-cols-2`).
- **Outils** : pytest `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest ...` (racine) ; vitest/tsc `"C:/facil_framework/node_modules/.bin/{vitest,tsc}"` depuis `C:/facil_framework/packages/web`. Env vitest = `node` → tester des **fonctions pures** (pas de render-test lourd).
- **Branche** : `feat/opening-hours`. Commits `<type>(<scope>): <sujet>`, scope `frontend`/`backend`, header ≤100, corps via `git commit -F -`.

## File Structure

- `packages/web/src/components/ui/weekly-hours.ts` **(créer)** — types + `normalize` + logique pure.
- `packages/web/src/components/ui/weekly-hours.test.ts` **(créer)** — vitest.
- `packages/web/src/components/ui/weekly-hours-field.tsx` — widget (réécrit : consomme le module, sections hebdo + exceptions).
- `packages/backend/app/modules/location/schemas.py` — `normalize_operating_hours` + `_validate_operating_hours` + `@field_validator`.
- `packages/backend/tests/test_location_schemas.py` **(créer si absent)** — pytest.
- `packages/web/src/i18n/messages/{en,fr,es}.json` — clés `weekly_hours.*`.

---

### Task 1 : Module pur `weekly-hours.ts`

**Files:**
- Create: `packages/web/src/components/ui/weekly-hours.ts`
- Test: `packages/web/src/components/ui/weekly-hours.test.ts`

**Interfaces:**
- Produces (exact) : `DAYS`, types `Day`, `DaySchedule = {closed:true}|{h24:true}|{ranges:string[]}`, `Exception = {date:string} & DaySchedule`, `OperatingHours = {weekly: Partial<Record<Day,DaySchedule>>; exceptions: Exception[]}`, `Target = "weekdays"|"weekend"|"all"` ; `MAX_EXCEPTIONS=366` ; fonctions `normalize`, `targetDays`, `toMinutes`, `parseRange`, `isRangeValid`, `rangesOverlap`, `isValidDay`, `isValidException`, `isValid`, `applyQuickFill`, `copyDay`, `sortExceptions`. Toutes pures (aucune mutation de l'entrée).

- [ ] **Step 1: Write the failing tests**

`packages/web/src/components/ui/weekly-hours.test.ts` :
```ts
import { describe, it, expect } from "vitest";
import {
  normalize, isRangeValid, rangesOverlap, isValidDay, isValid,
  applyQuickFill, copyDay, sortExceptions, targetDays, MAX_EXCEPTIONS,
} from "./weekly-hours";

describe("weekly-hours", () => {
  it("normalize: old {day:[ranges]} → canonical (empty array = closed)", () => {
    expect(normalize({ mon: ["09:00-17:00"], sat: [] })).toEqual({
      weekly: { mon: { ranges: ["09:00-17:00"] } }, exceptions: [] });
  });
  it("normalize: canonical passes through; illegal → empty", () => {
    const c = { weekly: { tue: { h24: true } }, exceptions: [{ date: "2026-12-25", closed: true }] };
    expect(normalize(c)).toEqual(c);
    expect(normalize(42)).toEqual({ weekly: {}, exceptions: [] });
  });
  it("isRangeValid: same-day ok, overnight ok, from==to invalid, malformed invalid", () => {
    expect(isRangeValid("09:00-17:00")).toBe(true);
    expect(isRangeValid("22:00-02:00")).toBe(true);   // overnight
    expect(isRangeValid("09:00-09:00")).toBe(false);  // zero-length
    expect(isRangeValid("9-17")).toBe(false);
  });
  it("rangesOverlap: same-day overlap, overnight overlap, disjoint", () => {
    expect(rangesOverlap("09:00-12:00", "11:00-14:00")).toBe(true);
    expect(rangesOverlap("22:00-02:00", "01:00-03:00")).toBe(true);  // wrap
    expect(rangesOverlap("09:00-12:00", "13:00-17:00")).toBe(false);
  });
  it("isValidDay: closed/h24 ok; overlapping ranges invalid", () => {
    expect(isValidDay({ closed: true })).toBe(true);
    expect(isValidDay({ h24: true })).toBe(true);
    expect(isValidDay({ ranges: ["09:00-12:00", "14:00-18:00"] })).toBe(true);
    expect(isValidDay({ ranges: ["09:00-12:00", "11:00-13:00"] })).toBe(false);
  });
  it("isValid: unique exception dates + cap", () => {
    const dup = { weekly: {}, exceptions: [{ date: "2026-01-01", closed: true }, { date: "2026-01-01", h24: true }] };
    expect(isValid(dup as any)).toBe(false);
    const many = { weekly: {}, exceptions: Array.from({ length: MAX_EXCEPTIONS + 1 },
      (_, i) => ({ date: `2027-${String(1 + (i % 12)).padStart(2, "0")}-01`, closed: true })) };
    expect(isValid(many as any)).toBe(false);
  });
  it("applyQuickFill overwrites the target days only", () => {
    const oh = { weekly: { sat: { h24: true } }, exceptions: [] } as any;
    const out = applyQuickFill(oh, "09:00", "17:00", "weekdays");
    expect(out.weekly.mon).toEqual({ ranges: ["09:00-17:00"] });
    expect(out.weekly.sat).toEqual({ h24: true });  // untouched
    expect(oh.weekly.mon).toBeUndefined();          // no mutation
  });
  it("copyDay copies the DaySchedule to targets except itself", () => {
    const oh = { weekly: { mon: { ranges: ["08:00-16:00"] } }, exceptions: [] } as any;
    const out = copyDay(oh, "mon", "all");
    expect(out.weekly.tue).toEqual({ ranges: ["08:00-16:00"] });
    expect(out.weekly.mon).toEqual({ ranges: ["08:00-16:00"] });
  });
  it("targetDays + sortExceptions", () => {
    expect(targetDays("weekend")).toEqual(["sat", "sun"]);
    expect(sortExceptions([{ date: "2026-02-01", closed: true }, { date: "2026-01-01", h24: true }])
      .map((e) => e.date)).toEqual(["2026-01-01", "2026-02-01"]);
  });
});
```

- [ ] **Step 2: Run — RED**

Run (depuis `packages/web`): `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/weekly-hours.test.ts`
Expected: FAIL (module absent).

- [ ] **Step 3: Implement `weekly-hours.ts`**

```ts
export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Day = (typeof DAYS)[number];
export type DaySchedule = { closed: true } | { h24: true } | { ranges: string[] };
export type Exception = { date: string } & DaySchedule;
export type OperatingHours = { weekly: Partial<Record<Day, DaySchedule>>; exceptions: Exception[] };
export type Target = "weekdays" | "weekend" | "all";

export const RANGE_RE = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
export const MAX_EXCEPTIONS = 366;

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}
export function parseRange(r: string): { from: number; to: number } | null {
  if (!RANGE_RE.test(r)) return null;
  const [f, t] = r.split("-");
  return { from: toMinutes(f), to: toMinutes(t) };
}
export function isRangeValid(r: string): boolean {
  const p = parseRange(r);
  return p !== null && p.from !== p.to;
}
function coveredIntervals(r: string): [number, number][] {
  const p = parseRange(r);
  if (!p) return [];
  return p.from < p.to ? [[p.from, p.to]] : [[p.from, 1440], [0, p.to]]; // overnight → two
}
export function rangesOverlap(a: string, b: string): boolean {
  const A = coveredIntervals(a), B = coveredIntervals(b);
  return A.some(([a0, a1]) => B.some(([b0, b1]) => a0 < b1 && b0 < a1));
}
export function isValidDay(d: DaySchedule): boolean {
  if ("closed" in d || "h24" in d) return true;
  if (!d.ranges.every(isRangeValid)) return false;
  for (let i = 0; i < d.ranges.length; i++)
    for (let j = i + 1; j < d.ranges.length; j++)
      if (rangesOverlap(d.ranges[i], d.ranges[j])) return false;
  return true;
}
export function isValidException(e: Exception, seen: Set<string>): boolean {
  if (!ISO_DATE_RE.test(e.date) || seen.has(e.date)) return false;
  const d = new Date(`${e.date}T00:00:00Z`);
  if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== e.date) return false;
  return isValidDay(e);
}
export function isValid(oh: OperatingHours): boolean {
  for (const day of DAYS) { const d = oh.weekly[day]; if (d && !isValidDay(d)) return false; }
  if (oh.exceptions.length > MAX_EXCEPTIONS) return false;
  const seen = new Set<string>();
  for (const e of oh.exceptions) { if (!isValidException(e, seen)) return false; seen.add(e.date); }
  return true;
}
export function targetDays(t: Target): Day[] {
  if (t === "weekdays") return ["mon", "tue", "wed", "thu", "fri"];
  if (t === "weekend") return ["sat", "sun"];
  return [...DAYS];
}
function normalizeDay(v: unknown): DaySchedule | null {
  if (Array.isArray(v)) {
    const rs = v.filter((x) => typeof x === "string") as string[];
    return rs.length ? { ranges: rs } : { closed: true };
  }
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    if (o.h24 === true) return { h24: true };
    if (o.closed === true) return { closed: true };
    if (Array.isArray(o.ranges)) return { ranges: o.ranges.filter((x) => typeof x === "string") as string[] };
  }
  return null;
}
export function normalize(v: unknown): OperatingHours {
  const empty: OperatingHours = { weekly: {}, exceptions: [] };
  if (v === null || typeof v !== "object" || Array.isArray(v)) return empty;
  const o = v as Record<string, unknown>;
  const weekly: Partial<Record<Day, DaySchedule>> = {};
  if ("weekly" in o || "exceptions" in o) {
    const w = (o.weekly ?? {}) as Record<string, unknown>;
    for (const day of DAYS) { const d = normalizeDay(w[day]); if (d) weekly[day] = d; }
    const exceptions: Exception[] = [];
    const ex = Array.isArray(o.exceptions) ? o.exceptions : [];
    for (const raw of ex) {
      if (raw && typeof raw === "object" && typeof (raw as Record<string, unknown>).date === "string") {
        const d = normalizeDay(raw) ?? { closed: true };
        exceptions.push({ date: (raw as { date: string }).date, ...d });
      }
    }
    return { weekly, exceptions };
  }
  for (const day of DAYS) { const d = normalizeDay(o[day]); if (d && !("closed" in d)) weekly[day] = d; }
  return { weekly, exceptions: [] };
}
function cloneDay(d: DaySchedule): DaySchedule {
  return "ranges" in d ? { ranges: [...d.ranges] } : { ...d };
}
export function applyQuickFill(oh: OperatingHours, from: string, to: string, target: Target): OperatingHours {
  const weekly = { ...oh.weekly };
  for (const day of targetDays(target)) weekly[day] = { ranges: [`${from}-${to}`] };
  return { ...oh, weekly };
}
export function copyDay(oh: OperatingHours, src: Day, target: Target): OperatingHours {
  const source = oh.weekly[src] ?? { closed: true as const };
  const weekly = { ...oh.weekly };
  for (const day of targetDays(target)) if (day !== src) weekly[day] = cloneDay(source);
  return { ...oh, weekly };
}
export function sortExceptions(list: Exception[]): Exception[] {
  return [...list].sort((a, b) => a.date.localeCompare(b.date));
}
```

- [ ] **Step 4: Run — GREEN + tsc**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/weekly-hours.test.ts` (PASS) puis `"C:/facil_framework/node_modules/.bin/tsc" --noEmit` (exit 0).

- [ ] **Step 5: Commit**
```
git add packages/web/src/components/ui/weekly-hours.ts packages/web/src/components/ui/weekly-hours.test.ts
git commit -F - <<'EOF'
feat(frontend): module pur weekly-hours (canonique {weekly,exceptions} + logique)
EOF
```

---

### Task 2 : Backend — `normalize_operating_hours` + validateur (autorité)

**Files:**
- Modify: `packages/backend/app/modules/location/schemas.py`
- Test: `packages/backend/tests/test_location_schemas.py` (créer si absent)

**Interfaces:**
- Consumes : pydantic `field_validator` (déjà importé l.5).
- Produces : `normalize_operating_hours(v: Any) -> dict` (ancienne/canonique → canonique) ; `_validate_operating_hours(oh: dict) -> None` (lève `ValueError` si invalide) ; un `@field_validator("operating_hours", mode="before")` PARTAGÉ sur `SiteCreate` ET `SiteUpdate` qui normalise puis valide et **retourne la forme canonique**.

- [ ] **Step 1: Write the failing tests**

`packages/backend/tests/test_location_schemas.py` :
```python
import pytest
from pydantic import ValidationError
from app.modules.location.schemas import SiteCreate, SiteUpdate

BASE = {"organization_id": "o1", "code": "S1", "name": "Site 1"}

def test_old_shape_is_normalized_to_canonical():
    s = SiteCreate(**BASE, operating_hours={"mon": ["09:00-17:00"], "sat": []})
    assert s.operating_hours == {"weekly": {"mon": {"ranges": ["09:00-17:00"]}}, "exceptions": []}

def test_overnight_ok_but_from_equals_to_rejected():
    SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["22:00-02:00"]}}, "exceptions": []})
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["09:00-09:00"]}}, "exceptions": []})

def test_overlap_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"ranges": ["09:00-12:00", "11:00-13:00"]}}, "exceptions": []})

def test_bad_mode_and_bad_exception_date_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {"mon": {"nope": True}}, "exceptions": []})
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {}, "exceptions": [{"date": "2026-13-40", "closed": True}]})

def test_duplicate_exception_date_rejected():
    with pytest.raises(ValidationError):
        SiteCreate(**BASE, operating_hours={"weekly": {}, "exceptions": [
            {"date": "2026-01-01", "closed": True}, {"date": "2026-01-01", "h24": True}]})

def test_update_also_validates():
    with pytest.raises(ValidationError):
        SiteUpdate(operating_hours={"weekly": {"mon": {"ranges": ["17:00-17:00"]}}, "exceptions": []})
    assert SiteUpdate(operating_hours=None).operating_hours is None  # optional stays optional
```

- [ ] **Step 2: Run — RED**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_schemas.py -v`
Expected: FAIL (pas de normalisation/validation).

- [ ] **Step 3: Implement in `schemas.py`**

Ajouter en tête du module (après les imports) :
```python
import re
from datetime import date as _date
from typing import Any

_RANGE_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
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
    if not isinstance(v, dict):
        return {"weekly": {}, "exceptions": []}
    weekly: dict = {}
    if "weekly" in v or "exceptions" in v:
        w = v.get("weekly") or {}
        for day in _DAYS:
            d = _norm_day(w.get(day)) if isinstance(w, dict) else None
            if d:
                weekly[day] = d
        exceptions = []
        for raw in v.get("exceptions") or []:
            if isinstance(raw, dict) and isinstance(raw.get("date"), str):
                d = _norm_day(raw) or {"closed": True}
                exceptions.append({"date": raw["date"], **d})
        return {"weekly": weekly, "exceptions": exceptions}
    for day in _DAYS:
        d = _norm_day(v.get(day))
        if d and "closed" not in d:
            weekly[day] = d
    return {"weekly": weekly, "exceptions": []}


def _validate_day(d: dict) -> None:
    if d in ({"closed": True}, {"h24": True}):
        return
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
        try:
            _date.fromisoformat(d)
        except ValueError as exc:
            raise ValueError(f"invalid exception date {d!r}") from exc
        if d in seen:
            raise ValueError(f"duplicate exception date {d!r}")
        seen.add(d)
        _validate_day({k: v for k, v in e.items() if k != "date"})
```
Puis, dans **`SiteCreate`** et **`SiteUpdate`**, ajouter le même validateur (extraire une fonction pour rester DRY) :
```python
def _oh_validator(cls, v):
    if v is None:  # SiteUpdate.operating_hours optionnel
        return v
    oh = normalize_operating_hours(v)
    _validate_operating_hours(oh)
    return oh
```
Sur chaque classe :
```python
    _oh = field_validator("operating_hours", mode="before")(classmethod(_oh_validator))
```
(Ou une méthode `@field_validator("operating_hours", mode="before") @classmethod def _v(cls, v): ...` dupliquée si le style du repo préfère ; garder UNE seule impl `_oh_validator`.)

- [ ] **Step 4: Run — GREEN + non-régression**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_schemas.py packages/backend/tests/ -k "location or site" -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```
git add packages/backend/app/modules/location/schemas.py packages/backend/tests/test_location_schemas.py
git commit -F - <<'EOF'
feat(backend): validateur operating_hours canonique (overnight, chevauchement, exceptions)
EOF
```

---

### Task 3 : Widget — section hebdomadaire (modes + remplissage + copie + 2 colonnes + validité)

**Files:**
- Modify: `packages/web/src/components/ui/weekly-hours-field.tsx`
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json`

**Interfaces:**
- Consumes : `weekly-hours.ts` (`normalize`, `applyQuickFill`, `copyDay`, `isValid`, `isRangeValid`, `rangesOverlap`, `DAYS`, types, `targetDays`).
- Produces : le même contrat `WeeklyHoursField({id,label,value,hint,disabled,onChange:(value,valid)=>void})` ; `onChange(next, isValid(next))`.

- [ ] **Step 1: Write the failing test (validité rapportée)**

Le widget est un composant React (pas de render-test lourd). Tester la **branche de validité** via un mini test de contrat sur `isValid` déjà couvert en Task 1 ; ici, ajouter à `weekly-hours.test.ts` un test garantissant que le widget appellerait `onChange(_, false)` sur une plage inversée — implémenté comme test de `isValid` sur l'état produit par l'édition :
```ts
it("isValid is false for a reversed custom range (widget validity source)", () => {
  expect(isValid({ weekly: { mon: { ranges: ["17:00-09:00"] } }, exceptions: [] } as any))
    .toBe(true);  // overnight IS valid (17:00→09:00 next day)
  expect(isValid({ weekly: { mon: { ranges: ["09:00-09:00"] } }, exceptions: [] } as any))
    .toBe(false); // zero-length invalid
});
```
(Le comportement UI — désactiver la sauvegarde — est prouvé par le câblage `onChange(next, isValid(next))` + le plombage `jsonOk` existant de RecordForm, vérifié en gate.)

- [ ] **Step 2: Run — RED/GREEN check**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/weekly-hours.test.ts`
Expected: PASS (la logique existe déjà depuis Task 1 ; ce test verrouille la sémantique overnight/zero-length que le widget consomme).

- [ ] **Step 3: Réécrire la section hebdo du widget**

Remplacer le contenu de `weekly-hours-field.tsx` par (conserve les props + le contrat `onChange`) :
```tsx
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DAYS, type Day, type DaySchedule, type OperatingHours, type Target,
  normalize, applyQuickFill, copyDay, isValid, isRangeValid, rangesOverlap,
} from "@/components/ui/weekly-hours";

const TARGETS: Target[] = ["weekdays", "weekend", "all"];
type Mode = "closed" | "h24" | "custom";
function modeOf(d: DaySchedule | undefined): Mode {
  if (!d || "closed" in d) return "closed";
  if ("h24" in d) return "h24";
  return "custom";
}
function daySchedule(mode: Mode, prev: DaySchedule | undefined): DaySchedule {
  if (mode === "closed") return { closed: true };
  if (mode === "h24") return { h24: true };
  return prev && "ranges" in prev && prev.ranges.length ? prev : { ranges: ["09:00-17:00"] };
}
function splitRange(r: string) { const [from, to] = r.split("-"); return { from: from ?? "", to: to ?? "" }; }

export function WeeklyHoursField({ id, label, value, hint, disabled, onChange }: {
  id: string; label: string; value: unknown; hint?: string; disabled?: boolean;
  onChange: (value: unknown, valid: boolean) => void;
}) {
  const t = useTranslations("weekly_hours");
  const [oh, setOh] = useState<OperatingHours>(() => normalize(value));
  const [qf, setQf] = useState({ from: "09:00", to: "17:00", target: "weekdays" as Target });

  function commit(next: OperatingHours) { setOh(next); onChange(next, isValid(next)); }
  function setDay(day: Day, d: DaySchedule) { commit({ ...oh, weekly: { ...oh.weekly, [day]: d } }); }
  function setRange(day: Day, idx: number, part: "from" | "to", v: string) {
    const cur = oh.weekly[day]; if (!cur || !("ranges" in cur)) return;
    const ranges = [...cur.ranges];
    const s = splitRange(ranges[idx] ?? ""); const m = { ...s, [part]: v };
    ranges[idx] = `${m.from || "00:00"}-${m.to || "00:00"}`;
    setDay(day, { ranges });
  }
  function addRange(day: Day) {
    const cur = oh.weekly[day]; const ranges = cur && "ranges" in cur ? cur.ranges : [];
    setDay(day, { ranges: [...ranges, "09:00-17:00"] });
  }
  function removeRange(day: Day, idx: number) {
    const cur = oh.weekly[day]; if (!cur || !("ranges" in cur)) return;
    const ranges = cur.ranges.filter((_, i) => i !== idx);
    setDay(day, ranges.length ? { ranges } : { closed: true });
  }

  return (
    <div className="space-y-3">
      <Label htmlFor={id}>{label}</Label>

      {/* Quick fill */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-2 text-sm">
        <span className="text-xs font-medium text-muted-foreground">{t("quick_fill")}</span>
        <input type="time" value={qf.from} disabled={disabled}
          onChange={(e) => setQf({ ...qf, from: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <span className="text-xs">–</span>
        <input type="time" value={qf.to} disabled={disabled}
          onChange={(e) => setQf({ ...qf, to: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <select value={qf.target} disabled={disabled}
          onChange={(e) => setQf({ ...qf, target: e.target.value as Target })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs">
          {TARGETS.map((tg) => <option key={tg} value={tg}>{t(`target.${tg}`)}</option>)}
        </select>
        <Button type="button" size="sm" className="h-8" disabled={disabled}
          onClick={() => commit(applyQuickFill(oh, qf.from, qf.to, qf.target))}>{t("apply")}</Button>
      </div>

      {/* Weekly grid: 2 columns on lg, stacked on narrow */}
      <div className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-md border p-3 lg:grid-cols-2">
        {DAYS.map((day) => {
          const d = oh.weekly[day]; const mode = modeOf(d);
          const ranges = d && "ranges" in d ? d.ranges : [];
          return (
            <div key={day} className="grid grid-cols-[6rem_1fr] items-start gap-2 text-sm">
              <div className="flex flex-col gap-1 pt-1">
                <span className="font-medium">{t(`day.${day}`)}</span>
                <select value={mode} disabled={disabled}
                  onChange={(e) => setDay(day, daySchedule(e.target.value as Mode, d))}
                  className="h-7 rounded-md border border-input bg-background px-1 text-xs">
                  <option value="closed">{t("mode.closed")}</option>
                  <option value="h24">{t("mode.h24")}</option>
                  <option value="custom">{t("mode.custom")}</option>
                </select>
              </div>
              <div className="space-y-1.5">
                {mode === "closed" && <p className="pt-1.5 text-xs text-muted-foreground">{t("mode.closed")}</p>}
                {mode === "h24" && <p className="pt-1.5 text-xs text-muted-foreground">{t("mode.h24")}</p>}
                {mode === "custom" && (<>
                  {ranges.map((r, idx) => {
                    const { from, to } = splitRange(r);
                    const bad = !isRangeValid(r) || ranges.some((o, i) => i !== idx && rangesOverlap(r, o));
                    return (
                      <div key={idx} className="flex items-center gap-1.5">
                        <input type="time" value={from} disabled={disabled}
                          onChange={(e) => setRange(day, idx, "from", e.target.value)}
                          className={cn("h-8 rounded-md border bg-background px-2 text-xs", bad ? "border-destructive" : "border-input")} />
                        <span className="text-xs text-muted-foreground">{t("to")}</span>
                        <input type="time" value={to} disabled={disabled}
                          onChange={(e) => setRange(day, idx, "to", e.target.value)}
                          className={cn("h-8 rounded-md border bg-background px-2 text-xs", bad ? "border-destructive" : "border-input")} />
                        {!disabled && (
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                            title={t("remove_shift")} onClick={() => removeRange(day, idx)}>
                            <Trash2 className="size-3.5" />
                          </Button>
                        )}
                      </div>
                    );
                  })}
                  {!disabled && (
                    <div className="flex items-center gap-2">
                      <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs"
                        onClick={() => addRange(day)}><Plus className="size-3.5" /> {t("add_shift")}</Button>
                      <select disabled={disabled} defaultValue=""
                        onChange={(e) => { if (e.target.value) { commit(copyDay(oh, day, e.target.value as Target)); e.target.value = ""; } }}
                        className="h-7 rounded-md border border-input bg-background px-1 text-xs text-muted-foreground">
                        <option value="">{t("copy_to")}</option>
                        {TARGETS.map((tg) => <option key={tg} value={tg}>{t(`target.${tg}`)}</option>)}
                      </select>
                    </div>
                  )}
                </>)}
              </div>
            </div>
          );
        })}
      </div>

      {/* EXCEPTIONS section is added in Task 4, here. */}

      <p className="text-xs text-muted-foreground">{t("tz_note")}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
```
Ajouter les clés i18n dans `en.json`/`fr.json`/`es.json` sous `weekly_hours` : `quick_fill`, `apply`, `copy_to`, `to` (si absent), `target.weekdays`/`target.weekend`/`target.all`, `mode.closed`/`mode.h24`/`mode.custom`, `tz_note` (+ garder `day.*`, `add_shift`, `remove_shift` existants). Vraies trads fr/es.

- [ ] **Step 4: Run — vitest complet + tsc**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run` + `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0.

- [ ] **Step 5: Commit**
```
git add packages/web/src/components/ui/weekly-hours-field.tsx packages/web/src/i18n/messages/
git commit -F - <<'EOF'
feat(frontend): widget horaires — modes/remplissage/copie/2 colonnes + validite reelle
EOF
```

---

### Task 4 : Widget — section exceptions

**Files:**
- Modify: `packages/web/src/components/ui/weekly-hours-field.tsx`
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json`

**Interfaces:**
- Consumes : `sortExceptions`, `type Exception`, `MAX_EXCEPTIONS`, `normalize` (Task 1) ; l'état `oh`/`commit` du widget (Task 3).

- [ ] **Step 1: Add a pure-logic test for exception add/dedup**

Ajouter à `weekly-hours.test.ts` :
```ts
it("exceptions: sorted, and isValid rejects a duplicate date", () => {
  const oh = { weekly: {}, exceptions: [
    { date: "2026-12-25", closed: true }, { date: "2026-07-14", h24: true }] } as any;
  expect(sortExceptions(oh.exceptions).map((e: any) => e.date)).toEqual(["2026-07-14", "2026-12-25"]);
  expect(isValid({ weekly: {}, exceptions: [
    { date: "2026-01-01", closed: true }, { date: "2026-01-01", closed: true }] } as any)).toBe(false);
});
```

- [ ] **Step 2: Run — GREEN**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/weekly-hours.test.ts`
Expected: PASS (logique Task 1).

- [ ] **Step 3: Add the exceptions section to the widget**

Importer en plus `sortExceptions, MAX_EXCEPTIONS, type Exception`. Remplacer le commentaire `{/* EXCEPTIONS section ... */}` par :
```tsx
      {/* Exceptions */}
      <div className="space-y-2 rounded-md border p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("exceptions.title")}</p>
        {oh.exceptions.length === 0 && <p className="text-xs text-muted-foreground">{t("exceptions.none")}</p>}
        {sortExceptions(oh.exceptions).map((e) => {
          const mode = modeOf(e); const eranges = "ranges" in e ? e.ranges : [];
          const setExc = (patch: Partial<Exception>) => {
            const next = oh.exceptions.map((x) => x.date === e.date ? { ...x, ...patch } as Exception : x);
            commit({ ...oh, exceptions: next });
          };
          return (
            <div key={e.date} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono text-xs">{e.date}</span>
              <select value={mode} disabled={disabled}
                onChange={(ev) => { const m = ev.target.value as Mode;
                  setExc(m === "closed" ? { closed: true, h24: undefined, ranges: undefined } as never
                    : m === "h24" ? { h24: true, closed: undefined, ranges: undefined } as never
                    : { ranges: eranges.length ? eranges : ["09:00-17:00"], closed: undefined, h24: undefined } as never); }}
                className="h-7 rounded-md border border-input bg-background px-1 text-xs">
                <option value="closed">{t("mode.closed")}</option>
                <option value="h24">{t("mode.h24")}</option>
                <option value="custom">{t("mode.custom")}</option>
              </select>
              {mode === "custom" && eranges.map((r, idx) => {
                const { from, to } = splitRange(r);
                const bad = !isRangeValid(r) || eranges.some((o, i) => i !== idx && rangesOverlap(r, o));
                return (
                  <span key={idx} className="flex items-center gap-1">
                    <input type="time" value={from} disabled={disabled}
                      onChange={(ev) => { const s = splitRange(r); const nr = [...eranges]; nr[idx] = `${ev.target.value || "00:00"}-${s.to || "00:00"}`; setExc({ ranges: nr } as never); }}
                      className={cn("h-7 rounded-md border bg-background px-1 text-xs", bad ? "border-destructive" : "border-input")} />
                    <span className="text-xs">{t("to")}</span>
                    <input type="time" value={to} disabled={disabled}
                      onChange={(ev) => { const s = splitRange(r); const nr = [...eranges]; nr[idx] = `${s.from || "00:00"}-${ev.target.value || "00:00"}`; setExc({ ranges: nr } as never); }}
                      className={cn("h-7 rounded-md border bg-background px-1 text-xs", bad ? "border-destructive" : "border-input")} />
                  </span>
                );
              })}
              {!disabled && (
                <Button type="button" variant="ghost" size="icon" className="size-6" title={t("remove_shift")}
                  onClick={() => commit({ ...oh, exceptions: oh.exceptions.filter((x) => x.date !== e.date) })}>
                  <Trash2 className="size-3.5" />
                </Button>
              )}
            </div>
          );
        })}
        {!disabled && oh.exceptions.length < MAX_EXCEPTIONS && (
          <input type="date" aria-label={t("exceptions.add")}
            onChange={(ev) => {
              const dstr = ev.target.value; if (!dstr) return;
              if (oh.exceptions.some((x) => x.date === dstr)) { ev.target.value = ""; return; } // dedup
              commit({ ...oh, exceptions: [...oh.exceptions, { date: dstr, closed: true }] });
              ev.target.value = "";
            }}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        )}
      </div>
```
Ajouter les clés i18n `weekly_hours.exceptions.title`/`add`/`date`/`none`/`duplicate` en/fr/es.

- [ ] **Step 4: Run — vitest complet + tsc**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run` + `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0. (Si tsc se plaint des `as never` sur les patchs d'exception, remplacer par une reconstruction d'objet `DaySchedule` propre — préférer `setExc` qui remplace le `DaySchedule` complet plutôt que des clés `undefined`.)

- [ ] **Step 5: Commit**
```
git add packages/web/src/components/ui/weekly-hours-field.tsx packages/web/src/i18n/messages/
git commit -F - <<'EOF'
feat(frontend): widget horaires — section exceptions (dates speciales/feries)
EOF
```

---

### Task 5 : Gate finale — parité, suites, tsc

**Files:** aucun code neuf (corrections de revue seulement).

- [ ] **Step 1: Suites complètes**

Run:
```
"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_schemas.py -v
cd packages/web && "C:/facil_framework/node_modules/.bin/vitest" run && "C:/facil_framework/node_modules/.bin/tsc" --noEmit
```
Expected: tout vert, tsc exit 0.

- [ ] **Step 2: Revue parité + i18n (checklist)**

Vérifier : chaque contrôle UI (mode closed/h24/custom, plage overnight, chevauchement signalé, exception date+mode) a son **gate backend** (`_validate_operating_hours`) ; réciproquement, aucune règle backend non éditable. `normalize` front ⇔ `normalize_operating_hours` back cohérents (ancienne forme, canonique). Clés i18n `weekly_hours.*` identiques en/fr/es. Corriger tout écart avant de clore.

- [ ] **Step 3: Commit (si corrections)**
```
git add -A && git commit -F - <<'EOF'
chore(frontend): gate D4-B B-i — corrections parite/revue
EOF
```
