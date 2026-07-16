# D4-B (B-ii) — Édition multi-sites des horaires d'ouverture — Design

> **Sous-projet** : D4-B, **partie B-ii** (après B-i mergé, PR #68). B-iii (consommation) = spec séparée.
> **Branche** : `feat/sites-bulk-hours` depuis `develop`, mergeable seule.
> **Date** : 2026-07-16.

## 0. Contexte & état actuel (vérifié dans le code)

B-i a livré la forme canonique `operating_hours = {weekly, exceptions}`, le widget `WeeklyHoursField`, le module pur `weekly-hours.ts` et le validateur backend (`normalize_operating_hours` + `_validate_operating_hours` + `@field_validator` sur `SiteUpdate`). B-ii ajoute l'**édition groupée** de ces horaires sur un lot de sites.

Faits établis :
- **Le DataGrid supporte DÉJÀ le multi-select** : prop optionnelle `selection: {selected:Set<string>, onToggle, onToggleAll, allOnPage}` (colonne cases + « tout sélectionner sur la page »), `data-grid.tsx` — mais **aucun caller ne la passe** aujourd'hui (`location/page.tsx` n'utilise que `onRowClick`/`selectedId`). ⇒ multi-select = câblage, pas net-new.
- **Précédent d'endpoint bulk** à mirrorer (pas inventer) : `POST /api/v1/admin/accounts/bulk-status` (`api/admin_accounts.py:181-217`) — **scope-enforced par item** (`rbac_repo.resolve_scope` + `rbac_service.has_permission` sur l'org de chaque cible), borné `≤500`, dédup `dict.fromkeys`, `audit.record(...)` par item, **un seul `session.commit()`** (transaction unique), réponse `{updated:[ids], errors:[{id,detail}]}`. Les échecs par item vont dans `errors`, ne 403 pas tout l'appel.
- **Update site** : `PUT /sites/{id}` gardé `require_permission("location.update")` ; scope résolu contre la LIGNE (l'org du site override l'appelant — invariant anti-confused-deputy, `rbac/repository.py:33-41`) ; `SiteUpdate.operating_hours` déjà validé par B-i ; **`If-Match`** (etag contenu) en single-item.
- **Trou d'audit** : `update_site` n'appelle `audit.record` que si `custom_fields` change — **une modif d'horaires ne génère AUCUN audit**, et il n'existe pas de constante `SITE_UPDATED`/`LOCATION_*` dans `auth/audit.py`. Contredit « toute mutation sensible → audit » (CLAUDE.md). B-ii corrige.
- **Concurrence en bulk** : les 2 endpoints bulk existants **ignorent `If-Match`** par item (liste d'ids brute, écrasement inconditionnel) = pattern établi du repo.
- **Liste sites = mono-org** (gate `orgId` + `OrgCombobox`) : une sélection est naturellement dans l'org courante.

## 1. Objectif & non-objectifs

**Objectif** : définir les horaires d'ouverture d'un lot de sites sélectionnés en une action, en 3 **modes** (remplacer tout / remplacer l'hebdo seulement / ajouter une exception), via un endpoint bulk transactionnel scope-enforced/audité/borné, et un dialog réutilisant le widget B-i.

**Non-objectifs (assumés)** :
- **Pas de sélection inter-orgs** : la liste est mono-org ; une sélection reste dans l'org courante. Le backend enforce quand même le scope **par item** (une requête forgée inter-orgs est rejetée item par item).
- **Pas de concurrence par item (`If-Match`)** en bulk : on suit le précédent (last-wins ; l'admin choisit explicitement les sites). Ajout ultérieur possible (`[{site_id, if_match}]`) = net-new différé.
- **Pas de multi-select générique sur toutes les listes** : on câble `selection` sur la liste sites seulement (la capacité DataGrid existe déjà et reste réutilisable ; l'étendre aux autres listes = hors périmètre).

## 2. Modes & sémantique de merge (par item, backend)

Payload d'entrée composé côté dialog selon le mode. Merge appliqué **par site** contre ses horaires actuels, puis le RÉSULTAT est **re-validé** par le validateur B-i avant écriture.

| Mode | Entrée requise | Merge par site (result) |
|---|---|---|
| `replace_all` | `operating_hours` (canonique complet) | `result = operating_hours` |
| `replace_weekly` | `weekly` (`{jour: DaySchedule}`) | `result = {weekly, exceptions: existing.exceptions}` |
| `add_exception` | `exception` (`{date, ...DaySchedule}`) | `result = {weekly: existing.weekly, exceptions: dédup_par_date(existing.exceptions, exception)}` — une exception existante à la **même date est écrasée** par la nouvelle |

`existing` = `normalize_operating_hours(site.operating_hours)` (rétro-compat). `result` re-validé → si invalide (ne devrait pas arriver, le dialog valide déjà), item en `errors`.

## 3. Backend — endpoint bulk + audit

**Nouvelle route** `PATCH /api/v1/modules/location/sites/bulk/operating-hours` (module location router), gardée `require_permission("location.update")` — mirroir de `bulk-status` :

```python
class BulkHoursIn(BaseModel):
    site_ids: list[str]
    mode: Literal["replace_all", "replace_weekly", "add_exception"]
    operating_hours: dict | None = None   # replace_all
    weekly: dict | None = None            # replace_weekly
    exception: dict | None = None         # add_exception
    # validateurs pydantic : le champ requis par le mode est présent + bien formé
    # (réutilise normalize/_validate de B-i pour operating_hours ; weekly/exception validés en conséquence)
```
Handler :
1. `ids = list(dict.fromkeys(body.site_ids))` ; `if not ids: 422` ; `if len(ids) > 500: 422`.
2. `bg = principal.get("break_glass")`.
3. Boucle par `sid` : `site = repo.get_site(...)` ; absent → `errors.append({site_id, "not found"})` ; sinon `scope = resolve_scope(session, {"site_id": sid})` (l'org de la LIGNE fait autorité) ; `if not bg and not has_permission(session, sub, "location.update", scope): errors.append({site_id, "forbidden"})` ; sinon appliquer le merge (§2), re-valider, `service.update_site(session, sid, SiteUpdate(operating_hours=result))` (ou une méthode dédiée qui ne touche QUE `operating_hours`), `audit.record(session, audit.LOCATION_HOURS_CHANGED, account_id=sub, detail={"site_id": sid, "mode": mode, "bulk": True})`, `updated.append(sid)`.
4. `await session.commit()` (unique) ; retour `{"updated": updated, "errors": errors}`.

**Audit** : ajouter `LOCATION_HOURS_CHANGED = "location_hours_changed"` dans `auth/audit.py`. **Backfill single-item** : dans `update_site`, émettre `audit.record(..., audit.LOCATION_HOURS_CHANGED, ...)` quand `body.operating_hours is not None` (ferme le trou d'audit existant).

**Skip `If-Match`** en bulk (précédent). Le merge lit `existing` au moment du bulk (read-modify-write par item) : last-wins assumé.

## 4. Frontend — sélection + dialog

- `location/page.tsx` : `const [selected, setSelected] = useState<Set<string>>(new Set())` ; `onToggle(id)` (toggle dans le Set), `onToggleAll()` (toggle les ids de la page courante), `allOnPage` (tous les ids de la page ∈ selected) ; passer `selection={{selected, onToggle, onToggleAll, allOnPage}}` au DataGrid. Reset de la sélection au changement d'org/de page.
- **Barre d'action bulk** : quand `selected.size > 0`, un bouton **« Horaires (N) »** (gated `can("location.update")`) dans la toolbar existante (`:120-139`) → ouvre le dialog. (Coexiste avec `onRowClick`/`sel` : les cases `stopPropagation`.)
- **Dialog** (`ConfirmDialog`/pattern master-detail) : sélecteur de **mode** (Remplacer tout / Remplacer l'hebdo / Ajouter une exception) → rend l'éditeur adéquat :
  - *replace_all* → `WeeklyHoursField` complet (compose `operating_hours`).
  - *replace_weekly* → la section hebdo du widget (compose `weekly`). (Réutiliser le widget en masquant/ignorant les exceptions, OU un flag `weeklyOnly` — à trancher au plan, réutilisation d'abord.)
  - *add_exception* → un éditeur d'exception unique (date + mode Fermé/24h/Custom+plages), réutilisant les helpers B-i.
- Validité client via `isValid`/le widget avant submit ; submit → `apiFetch(PATCH bulk)` → toast succès `{updated}` + liste `{errors}` (site+raison) ; `setSelected(new Set())` au succès + `table.refetch()`.
- i18n en/fr/es (namespace `location` ou `weekly_hours`) : titres modes, bouton, résultats.

## 5. Parité, RBAC, audit

- **Parité** : le bulk n'expose que ce que le single-item + le validateur B-i appliquent (mêmes modes/forme). Réponse `{updated, errors}` rendue (aucune erreur silencieuse).
- **RBAC** : `location.update` requis ; **scope-enforced par item** (org de la ligne fait autorité) ; break-glass respecté. Un item hors scope → `errors`, pas un 403 global.
- **Audit** : `LOCATION_HOURS_CHANGED` par item réussi (bulk **et** single-item) — trou existant fermé.
- **Bornage** : ≤500 ; dédup ids.

## 6. Tests

- **pytest** (`test_location_bulk_hours` + `test_location_schemas`/api) : `replace_all`/`replace_weekly`/`add_exception` (merge correct par item, exception même-date écrasée) ; **scope par item** (un site d'une autre org / sans perm → `errors`, les autres réussissent) ; `>500` → 422 ; ids vides → 422 ; dédup ; résultat invalide → item en `errors` ; **audit émis** (`LOCATION_HOURS_CHANGED`, bulk + single-item backfill) ; forme `{updated, errors}` ; break-glass bypass.
- **vitest** : logique pure du dialog si extraite (composition mode→payload) ; sinon la couverture repose sur `weekly-hours.ts` (déjà testé) + les fonctions pures d'assemblage du payload.
- **e2e (optionnel, stack up)** : sélectionner 2 sites, « Horaires », mode replace_all, appliquer, vérifier les 2 mis à jour.

## 7. Découpage (pour le plan)

1. Backend : constante `LOCATION_HOURS_CHANGED` + backfill audit single-item `update_site` + pytest.
2. Backend : endpoint `PATCH /sites/bulk/operating-hours` (BulkHoursIn + merge par mode + scope/borné/audit/commit unique) + pytest (mirroir bulk-status).
3. Frontend : câbler `selection` dans `location/page.tsx` + barre d'action bulk (gated) + reset.
4. Frontend : dialog multi-mode (replace_all/replace_weekly/add_exception) réutilisant le widget B-i + soumission `{updated,errors}` + i18n.
5. Gate finale : pytest + vitest + tsc + revue parité/RBAC/audit.

## 8. Isolation

Branche `feat/sites-bulk-hours` depuis `develop`, mergeable seule. B-iii (consommation) = spec/branche distinctes.
