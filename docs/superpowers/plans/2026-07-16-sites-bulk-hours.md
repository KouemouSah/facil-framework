# D4-B (B-ii) — Édition multi-sites des horaires — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Éditer les horaires d'ouverture d'un lot de sites en une action (3 modes : remplacer tout / remplacer l'hebdo / ajouter une exception), via un endpoint bulk transactionnel scope-enforced/audité/borné et un dialog réutilisant le widget B-i.

**Architecture:** Un endpoint `PATCH /sites/bulk/operating-hours` mirroir du précédent `bulk-status` : boucle par site, scope-enforced par item (org de la ligne fait autorité), merge selon le mode contre les horaires existants, RÉSULTAT re-validé par le validateur B-i, `audit.record` par item, **un seul commit**. Le front câble la prop `selection` (déjà supportée par le DataGrid) sur la liste sites + un dialog multi-mode réutilisant `WeeklyHoursField`.

**Tech Stack:** FastAPI/pydantic v2, pytest (backend) ; React 19 + TanStack + zod, Vitest, TypeScript strict (front).

## Global Constraints

- **Bulk ERP-grade** : transactionnel (**un seul `session.commit()`**), **scope-enforced par item** (`resolve_scope({"site_id": sid})` → l'org de la ligne fait autorité, invariant anti-confused-deputy), **audité par item**, **borné ≤500**, **dédup** ids. Échec item → `errors` (jamais un 403 global).
- **Backend autoritaire** : le RÉSULTAT du merge est re-validé par `_validate_operating_hours` (B-i) avant écriture ; le validateur pydantic de `SiteUpdate.operating_hours` s'applique aussi.
- **Parité / pas d'erreur silencieuse** : réponse `{updated:[ids], errors:[{site_id,detail}]}` rendue à l'UI.
- **RBAC** : `location.update` requis (route dep) ; break-glass (`principal.get("break_glass")`) bypasse le scope par item.
- **Skip `If-Match`** en bulk (précédent `bulk-status`/`bulk-roles` ; last-wins assumé).
- **Audit** : nouvelle action `LOCATION_HOURS_CHANGED` ; émise en bulk ET backfillée sur le single-item (trou existant).
- **i18n** : toute chaîne visible = clé en/fr/es, mêmes clés.
- **Outils** : pytest `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest …` (racine) ; vitest/tsc `"C:/facil_framework/node_modules/.bin/{vitest,tsc}"` depuis `packages/web` (env vitest = `node` → fonctions pures).
- **Branche** : `feat/sites-bulk-hours`. Commits `<type>(<scope>): <sujet>`, scope `backend`/`frontend`, header ≤100, corps via `git commit -F -`.

## File Structure

- `packages/backend/app/auth/audit.py` — constante `LOCATION_HOURS_CHANGED`.
- `packages/backend/app/modules/location/api/__init__.py` — backfill audit single-item + endpoint bulk.
- `packages/backend/app/modules/location/schemas.py` — `BulkHoursIn` (ou dans l'api ; garder près du validateur B-i réutilisé).
- `packages/backend/tests/test_location_bulk_hours.py` **(créer)** — pytest bulk.
- `packages/backend/tests/test_location_api.py` (ou existant) — pytest backfill audit single-item.
- `packages/web/src/modules/location/bulk-hours.ts` **(créer)** — helper pur `composeBulkPayload(mode, value)` (testable).
- `packages/web/src/modules/location/bulk-hours-dialog.tsx` **(créer)** — dialog multi-mode.
- `packages/web/src/modules/location/bulk-hours.test.ts` **(créer)** — vitest helper.
- `packages/web/src/modules/location/page.tsx` — câblage `selection` + barre d'action.
- `packages/web/src/modules/location/api.ts` — `bulkSetHours(...)`.
- `packages/web/src/i18n/messages/{en,fr,es}.json` — clés `location.bulk_hours.*`.

---

### Task 1 : Backend — audit `LOCATION_HOURS_CHANGED` + backfill single-item

**Files:**
- Modify: `packages/backend/app/auth/audit.py` (après `CUSTOM_FIELDS_CHANGED`, l.50)
- Modify: `packages/backend/app/modules/location/api/__init__.py` (`update_site`, l.225-228)
- Test: `packages/backend/tests/test_location_api.py` (ou créer `test_location_bulk_hours.py` et y mettre aussi ce test)

**Interfaces:**
- Produces : `audit.LOCATION_HOURS_CHANGED = "location_hours_changed"`. `update_site` émet cet audit quand `body.operating_hours is not None`.

- [ ] **Step 1: Write the failing test**

Dans `packages/backend/tests/test_location_bulk_hours.py` (créer) — test du backfill single-item via le service/route. Utiliser le harness de test existant du module location (regarder `test_location_*` pour le fixture de session + création de site). Test minimal au niveau service/route :
```python
import pytest
from app.auth import audit

def test_location_hours_changed_constant_exists():
    assert audit.LOCATION_HOURS_CHANGED == "location_hours_changed"
```
(Le test d'émission réelle sur `update_site` est ajouté avec le harness de route existant ; si absent, couvrir l'émission au niveau du handler dans le test bulk de Task 2 qui exerce le même `audit.record`. Ne PAS inventer un harness — réutiliser celui des tests location existants.)

- [ ] **Step 2: Run — RED**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_bulk_hours.py -k constant -v`
Expected: FAIL (constante absente).

- [ ] **Step 3: Implement**

Dans `audit.py`, après la ligne `CUSTOM_FIELDS_CHANGED = "custom_fields_changed"` :
```python
# Horaires d'ouverture d'un site (D4-B) — mutation sensible, auditée (single + bulk).
LOCATION_HOURS_CHANGED = "location_hours_changed"
```
Dans `update_site` (`api/__init__.py`), après le bloc d'audit `custom_fields` (l.225-228) et AVANT `_commit` :
```python
    if body.operating_hours is not None:
        await audit.record(session, audit.LOCATION_HOURS_CHANGED,
                           account_id=principal.get("sub"),
                           detail={"site_id": site_id})
```

- [ ] **Step 4: Run — GREEN**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_bulk_hours.py -k constant -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```
git add packages/backend/app/auth/audit.py packages/backend/app/modules/location/api/__init__.py packages/backend/tests/test_location_bulk_hours.py
git commit -F - <<'EOF'
feat(backend): audit LOCATION_HOURS_CHANGED + backfill update_site (horaires)
EOF
```

---

### Task 2 : Backend — endpoint bulk `PATCH /sites/bulk/operating-hours`

**Files:**
- Modify: `packages/backend/app/modules/location/api/__init__.py` (ajouter le modèle + la route ; ajouter l'import `from app.rbac import service as rbac_service`)
- Test: `packages/backend/tests/test_location_bulk_hours.py`

**Interfaces:**
- Consumes : `rbac_repo.resolve_scope`, `rbac_service.has_permission`, `repo.get_site`, `service.update_site`, `SiteUpdate`, `normalize_operating_hours`/`_validate_operating_hours` (schemas.py, B-i), `audit.record`, `audit.LOCATION_HOURS_CHANGED` (Task 1).
- Produces : route `PATCH /api/v1/modules/location/sites/bulk/operating-hours` ; réponse `{"updated": list[str], "errors": list[{"site_id","detail"}]}`.

- [ ] **Step 1: Write the failing tests**

`test_location_bulk_hours.py` — réutiliser le harness/fixtures des tests location existants (client authentifié + création de sites dans une org). Tests :
```python
# (imports/fixtures selon le harness location existant — client, org, sites)
def test_replace_all_sets_hours_on_all_selected(client, org, two_sites):
    r = client.patch("/api/v1/modules/location/sites/bulk/operating-hours", json={
        "site_ids": [two_sites[0], two_sites[1]], "mode": "replace_all",
        "operating_hours": {"weekly": {"mon": {"ranges": ["09:00-17:00"]}}, "exceptions": []}})
    assert r.status_code == 200
    body = r.json(); assert set(body["updated"]) == {two_sites[0], two_sites[1]}; assert body["errors"] == []

def test_replace_weekly_keeps_existing_exceptions(client, org, site_with_exception):
    r = client.patch(".../bulk/operating-hours", json={
        "site_ids": [site_with_exception], "mode": "replace_weekly",
        "weekly": {"tue": {"h24": True}}})
    assert r.status_code == 200
    # relire le site : weekly remplacé, exceptions préservées
    # (assert via GET /sites/{id})

def test_add_exception_overwrites_same_date(client, org, site_with_dec25_open):
    r = client.patch(".../bulk/operating-hours", json={
        "site_ids": [site_with_dec25_open], "mode": "add_exception",
        "exception": {"date": "2026-12-25", "closed": True}})
    assert r.status_code == 200  # la Dec-25 existante est écrasée par closed

def test_per_item_scope_other_org_goes_to_errors(client, org_a_site, org_b_site_user_a_cant):
    # user scoped to org A only : le site d'org B tombe en errors, celui d'org A réussit
    r = client.patch(".../bulk/operating-hours", json={
        "site_ids": [org_a_site, org_b_site_user_a_cant], "mode": "replace_all",
        "operating_hours": {"weekly": {}, "exceptions": []}})
    assert r.status_code == 200
    assert org_a_site in r.json()["updated"]
    assert any(e["site_id"] == org_b_site_user_a_cant for e in r.json()["errors"])

def test_bounds_and_dedup(client):
    assert client.patch(".../bulk/operating-hours", json={"site_ids": [], "mode": "replace_all", "operating_hours": {"weekly":{},"exceptions":[]}}).status_code == 422
    assert client.patch(".../bulk/operating-hours", json={"site_ids": ["x"]*501, "mode": "replace_all", "operating_hours": {"weekly":{},"exceptions":[]}}).status_code == 422

def test_invalid_result_rejected_per_item(client, org, one_site):
    r = client.patch(".../bulk/operating-hours", json={
        "site_ids": [one_site], "mode": "replace_all",
        "operating_hours": {"weekly": {"mon": {"ranges": ["17:00-17:00"]}}, "exceptions": []}})
    # from==to → 422 (validateur pydantic sur operating_hours), OU item en errors si validé plus tard
    assert r.status_code == 422
```
(Adapter les fixtures aux helpers du harness location existant. Si un test ne peut pas être écrit sans un fixture manquant, l'implémenteur le construit sur le modèle des tests location existants — ne PAS mocker le RBAC/DB, utiliser le vrai chemin comme les tests bulk-status.)

- [ ] **Step 2: Run — RED**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_bulk_hours.py -v`
Expected: FAIL (route absente / 404).

- [ ] **Step 3: Implement**

Ajouter l'import en tête de `api/__init__.py` : `from app.rbac import service as rbac_service`. Importer aussi `from typing import Literal` et depuis schemas : `from app.modules.location.schemas import SiteCreate, SiteUpdate, normalize_operating_hours, _validate_operating_hours` (exporter `_validate_operating_hours`/`normalize_operating_hours` si nécessaire — ils existent dans schemas.py depuis B-i). Puis :
```python
from pydantic import BaseModel, model_validator

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

class BulkHoursIn(BaseModel):
    site_ids: list[str]
    mode: Literal["replace_all", "replace_weekly", "add_exception"]
    operating_hours: dict | None = None
    weekly: dict | None = None
    exception: dict | None = None

    @model_validator(mode="after")
    def _check_mode_payload(self):
        if self.mode == "replace_all":
            if self.operating_hours is None:
                raise ValueError("operating_hours required for replace_all")
            _validate_operating_hours(normalize_operating_hours(self.operating_hours))
        elif self.mode == "replace_weekly":
            if self.weekly is None:
                raise ValueError("weekly required for replace_weekly")
            _validate_operating_hours({"weekly": self.weekly, "exceptions": []})
        elif self.mode == "add_exception":
            if self.exception is None or "date" not in self.exception:
                raise ValueError("exception (with date) required for add_exception")
            _validate_operating_hours({"weekly": {}, "exceptions": [self.exception]})
        return self


def _merge_hours(mode: str, existing: dict, body: BulkHoursIn) -> dict:
    if mode == "replace_all":
        return normalize_operating_hours(body.operating_hours)
    if mode == "replace_weekly":
        return {"weekly": body.weekly, "exceptions": existing["exceptions"]}
    # add_exception: same-date existing exception is overwritten by the new one
    date = body.exception["date"]
    kept = [e for e in existing["exceptions"] if e.get("date") != date]
    return {"weekly": existing["weekly"], "exceptions": kept + [body.exception]}


@router.patch("/sites/bulk/operating-hours",
              dependencies=[Depends(require_permission("location.update"))])
async def bulk_set_operating_hours(
        body: BulkHoursIn, principal: dict = Depends(require_auth),
        session: AsyncSession = Depends(get_session)) -> dict:
    ids = list(dict.fromkeys(body.site_ids))
    if not ids:
        raise HTTPException(422, "site_ids must not be empty")
    if len(ids) > 500:
        raise HTTPException(422, "too many sites (max 500)")
    bg = bool(principal.get("break_glass"))
    updated: list[str] = []
    errors: list[dict] = []
    for sid in ids:
        site = await repo.get_site(session, sid)
        if site is None:
            errors.append({"site_id": sid, "detail": "not found"}); continue
        scope = await rbac_repo.resolve_scope(session, {"site_id": sid})
        if not bg and not await rbac_service.has_permission(
                session, principal["sub"], "location.update", scope):
            errors.append({"site_id": sid, "detail": "forbidden"}); continue
        existing = normalize_operating_hours(site.operating_hours)
        result = _merge_hours(body.mode, existing, body)
        try:
            _validate_operating_hours(result)
        except ValueError as e:
            errors.append({"site_id": sid, "detail": str(e)}); continue
        await service.update_site(session, sid, SiteUpdate(operating_hours=result))
        await audit.record(session, audit.LOCATION_HOURS_CHANGED,
                           account_id=principal.get("sub"),
                           detail={"site_id": sid, "mode": body.mode, "bulk": True})
        updated.append(sid)
    await session.commit()
    return {"updated": updated, "errors": errors}
```
Note DRY : `require_permission("location.update")` en dep de route donne le gate global (l'appelant a la perm quelque part) ; le scope PAR ITEM est ré-enforce dans la boucle (org de la ligne). Si `resolve_scope({"site_id": sid})` échoue pour un id inexistant, il est déjà filtré par le `get_site is None` au-dessus.

- [ ] **Step 4: Run — GREEN**

Run: `"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_bulk_hours.py -v` puis `… -k "location or site" -v` (non-régression).
Expected: PASS.

- [ ] **Step 5: Commit**
```
git add packages/backend/app/modules/location/api/__init__.py packages/backend/tests/test_location_bulk_hours.py
git commit -F - <<'EOF'
feat(backend): endpoint bulk horaires sites (scope par item, audite, borne, {updated,errors})
EOF
```

---

### Task 3 : Frontend — sélection multi-lignes + barre d'action

**Files:**
- Modify: `packages/web/src/modules/location/page.tsx`
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json`

**Interfaces:**
- Consumes : la prop `selection: {selected:Set<string>, onToggle, onToggleAll, allOnPage}` du `DataGrid` (existe déjà) ; `table.rows` (les sites de la page) ; `usePermissions().can("location.update")`.
- Produces : un état de sélection + un bouton bulk qui ouvre `BulkHoursDialog` (Task 4).

- [ ] **Step 1: Wire selection state**

Dans le composant liste de `page.tsx`, ajouter :
```tsx
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const pageIds = table.rows.map((s) => s.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const toggle = (id: string) => setSelected((prev) => {
    const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next;
  });
  const toggleAll = () => setSelected((prev) => {
    const next = new Set(prev);
    allOnPage ? pageIds.forEach((id) => next.delete(id)) : pageIds.forEach((id) => next.add(id));
    return next;
  });
  // reset selection when the org changes (list scope changes)
  useEffect(() => { setSelected(new Set()); }, [orgId]);
```
Passer au `DataGrid` : `selection={{ selected, onToggle: toggle, onToggleAll: toggleAll, allOnPage }}` (en plus des props existantes).

- [ ] **Step 2: Add the bulk action button**

Dans la toolbar existante (`~l.120-139`), après les actions existantes, conditionnel :
```tsx
        {canUpdate && selected.size > 0 && (
          <Button size="sm" variant="outline" onClick={() => setBulkOpen(true)}>
            {t("bulk_hours.action", { count: selected.size })}
          </Button>
        )}
```
(`canUpdate = can("location.update")` existe déjà ; ajouter `const [bulkOpen, setBulkOpen] = useState(false);`.) Rendre `<BulkHoursDialog open={bulkOpen} siteIds={[...selected]} onClose={() => setBulkOpen(false)} onDone={() => { setBulkOpen(false); setSelected(new Set()); table.refetch(); }} />` (composant Task 4).

Ajouter la clé i18n `location.bulk_hours.action` (en/fr/es) avec le placeholder `{count}` (ex. EN "Hours ({count})").

- [ ] **Step 3: tsc + vitest**

Run: `"C:/facil_framework/node_modules/.bin/tsc" --noEmit` (exit 0, même si `BulkHoursDialog` n'existe pas encore → stub minimal ou implémenter Task 4 d'abord). **Note d'ordonnancement** : Task 4 crée `BulkHoursDialog` ; pour que Task 3 typecheck seul, créer un stub `bulk-hours-dialog.tsx` exportant un composant no-op `({open}) => open ? null : null` que Task 4 remplace. (Ou fusionner 3+4 si l'implémenteur préfère — garder la barre + le dialog cohérents.)
Expected: tsc exit 0.

- [ ] **Step 4: Commit**
```
git add packages/web/src/modules/location/page.tsx packages/web/src/modules/location/bulk-hours-dialog.tsx packages/web/src/i18n/messages/
git commit -F - <<'EOF'
feat(frontend): liste sites — selection multi-lignes + action bulk horaires
EOF
```

---

### Task 4 : Frontend — dialog multi-mode + soumission

**Files:**
- Create: `packages/web/src/modules/location/bulk-hours.ts` (helper pur)
- Create: `packages/web/src/modules/location/bulk-hours-dialog.tsx`
- Create: `packages/web/src/modules/location/bulk-hours.test.ts`
- Modify: `packages/web/src/modules/location/api.ts` (`bulkSetHours`)
- Modify: `packages/web/src/i18n/messages/{en,fr,es}.json`

**Interfaces:**
- Consumes : `WeeklyHoursField` + `weekly-hours.ts` (`OperatingHours`, `isValid`, types) ; `apiFetch`.
- Produces : `composeBulkPayload(mode, oh, exception)` (pur) ; `bulkSetHours(payload)` (api) ; `BulkHoursDialog`.

- [ ] **Step 1: Write the failing test (payload composition, pure)**

`bulk-hours.test.ts` :
```ts
import { describe, it, expect } from "vitest";
import { composeBulkPayload } from "./bulk-hours";

describe("composeBulkPayload", () => {
  const oh = { weekly: { mon: { ranges: ["09:00-17:00"] } }, exceptions: [{ date: "2026-12-25", closed: true }] } as any;
  it("replace_all sends the full operating_hours", () => {
    expect(composeBulkPayload("replace_all", oh)).toEqual({ mode: "replace_all", operating_hours: oh });
  });
  it("replace_weekly sends only weekly", () => {
    expect(composeBulkPayload("replace_weekly", oh)).toEqual({ mode: "replace_weekly", weekly: oh.weekly });
  });
  it("add_exception sends one exception", () => {
    const exc = { date: "2026-01-01", closed: true } as any;
    expect(composeBulkPayload("add_exception", oh, exc)).toEqual({ mode: "add_exception", exception: exc });
  });
});
```

- [ ] **Step 2: Run — RED**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/modules/location/bulk-hours.test.ts`
Expected: FAIL (module absent).

- [ ] **Step 3: Implement**

`bulk-hours.ts` :
```ts
import type { OperatingHours, Exception } from "@/components/ui/weekly-hours";

export type BulkMode = "replace_all" | "replace_weekly" | "add_exception";

export function composeBulkPayload(mode: BulkMode, oh: OperatingHours, exception?: Exception):
  Record<string, unknown> {
  if (mode === "replace_all") return { mode, operating_hours: oh };
  if (mode === "replace_weekly") return { mode, weekly: oh.weekly };
  return { mode, exception };
}
```
`api.ts` — ajouter :
```ts
export const bulkSetHours = (siteIds: string[], payload: Record<string, unknown>) =>
  apiFetch<{ updated: string[]; errors: { site_id: string; detail: string }[] }>(
    `${SITE_BASE}/bulk/operating-hours`,
    { method: "PATCH", body: JSON.stringify({ site_ids: siteIds, ...payload }) });
```
`bulk-hours-dialog.tsx` — un dialog (réutiliser le pattern `DetailPanel`/`ConfirmDialog` du module) avec :
- un `<select>` de mode (`replace_all`/`replace_weekly`/`add_exception`) ;
- pour `replace_all` **et** `replace_weekly` : un `WeeklyHoursField` (état `OperatingHours`) — en `replace_weekly` seul `.weekly` est envoyé (composeBulkPayload) ; le validité `isValid` gate le submit ;
- pour `add_exception` : un éditeur d'exception unique (input `date` + select mode Fermé/24h/Custom + éditeur de plages), construisant un `Exception`, validé via `isValid({weekly:{}, exceptions:[exc]})` ;
- Submit : `bulkSetHours(siteIds, composeBulkPayload(mode, oh, exc))` → toast succès `t("bulk_hours.done", {count: res.updated.length})` + si `res.errors.length` un détail (liste site+raison) ; puis `onDone()`.
Ajouter les clés i18n `location.bulk_hours.title/mode.replace_all/mode.replace_weekly/mode.add_exception/apply/done/errors/action` en/fr/es.

- [ ] **Step 4: Run — GREEN + tsc + vitest complet**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run` + `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: PASS + exit 0.

- [ ] **Step 5: Commit**
```
git add packages/web/src/modules/location/bulk-hours.ts packages/web/src/modules/location/bulk-hours.test.ts packages/web/src/modules/location/bulk-hours-dialog.tsx packages/web/src/modules/location/api.ts packages/web/src/i18n/messages/
git commit -F - <<'EOF'
feat(frontend): dialog bulk horaires (3 modes) + composition payload + i18n
EOF
```

---

### Task 5 : Gate finale — parité / RBAC / audit

**Files:** aucun code neuf (corrections de revue seulement).

- [ ] **Step 1: Suites**

Run:
```
"C:\facil_framework\.venv\Scripts\python.exe" -m pytest packages/backend/tests/test_location_bulk_hours.py packages/backend/tests/ -k "location or site" -v
cd packages/web && "C:/facil_framework/node_modules/.bin/vitest" run && "C:/facil_framework/node_modules/.bin/tsc" --noEmit
```
Expected: tout vert, tsc exit 0.

- [ ] **Step 2: Revue (checklist)**

Vérifier : **scope par item** (org ligne autoritaire ; item hors scope → `errors`, les autres réussissent) · **audit** émis par item réussi (bulk) ET single-item (backfill) · **bornage** ≤500 + dédup · **result re-validé** par le validateur B-i (aucune donnée invalide écrite) · **{updated,errors}** rendu à l'UI (aucune erreur silencieuse) · **RBAC** `location.update` + break-glass · **i18n** `location.bulk_hours.*` identiques en/fr/es · **parité** (le bulk n'expose que les modes/forme appliqués backend). Corriger tout écart.

- [ ] **Step 3: Commit (si corrections)**
```
git add -A && git commit -F - <<'EOF'
chore: gate D4-B B-ii — corrections revue (parite/RBAC/audit)
EOF
```
