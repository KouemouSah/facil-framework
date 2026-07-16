# D4-B — Horaires d'ouverture production-grade — Design

> **Sous-projet** : D4-B. **Cette spec = B-i** (modèle hebdomadaire production-grade **+ exceptions/fériés** : stockage, édition, validation). **B-ii** (multi-sites) et **B-iii** (consommation/affichage) = specs séparées, cadrées en §10. Après D4-A mergé.
> **Branche** : `feat/opening-hours` depuis `develop`, mergeable seule.
> **Date** : 2026-07-16.

## 0. Contexte & état actuel (vérifié dans le code)

`Site.operating_hours` (JSONB, `modules/location/models.py:51`) porte aujourd'hui `{"mon": ["09:00-17:00"], "sat": [], …}`, saisie par le widget bespoke `WeeklyHoursField` (`web/src/components/ui/weekly-hours-field.tsx`). **Aucun code ne consomme cette forme pour une logique métier** (vérifié : `models.as_dict` la passe telle quelle ; `schemas.py:28,72` = `dict` opaque ; seuls le widget la rend et `core/schema/types.py:43` la commente comme « shape inconsistante »). ⇒ on peut adopter une forme canonique plus riche avec un **normaliseur rétro-compatible**, sans casser de logique.

Manques vs systèmes de production (Google Business, Square, OSM `opening_hours`, Odoo `resource.calendar`) :
- pas de **plages nocturnes** (traversent minuit) ; pas d'état **« Ouvert 24h »** ; pas d'**anti-chevauchement** ; pas de **dates spéciales/fériés** ;
- **validité fantôme** : le widget appelle toujours `onChange(next, true)` (l.59) → une plage inversée/malformée n'est jamais signalée ; `RecordForm.validate()` (`record-form.tsx:225-232`) bloque pourtant déjà un champ json dont `jsonOk[name]=false` — seul le widget ne rapporte jamais `false` ;
- **affichage** vertical qui n'exploite pas la largeur en plein page.

## 1. Objectif & non-objectifs

**Objectif (B-i)** : modèle d'horaires **production-grade** — hebdomadaire (Fermé / 24h / plages avec **overnight** + **anti-chevauchement**) **+ exceptions datées** (fériés, fermetures ponctuelles) — saisi rapidement (remplissage en bulk + copie), fiable (validité réelle, **gate backend**), affiché en 2 colonnes en plein page. Frontend + validateur backend.

**Non-objectifs (B-i)** :
- **Pas de multi-sites** (action groupée sur un lot) → **B-ii** (§10).
- **Pas de consommation/affichage** (« ouvert maintenant », table publique) → **B-iii** (§10).
- **Pas de récurrence d'exceptions** (ex. « tous les 25/12 ») ni d'exceptions par plage horaire multi-jours : une exception = **une date** avec un `DaySchedule`.
- **Pas de conversion de fuseau** : les heures sont du **wall-clock local** au `Site.timezone` (note UI). Aucun stockage timezone nouveau.

## 2. Forme canonique de `operating_hours`

```jsonc
{
  "weekly": { "mon": DaySchedule, "tue": DaySchedule, ... },   // jour omis = fermé
  "exceptions": [ { "date": "2026-12-25", ...DaySchedule } ]    // overrides datés, triés asc
}
// DaySchedule (union discriminée) :
//   { "closed": true }
//   { "h24": true }                                  // « Ouvert 24h »
//   { "ranges": ["09:00-17:00", "22:00-02:00"] }     // 1..N plages
```

- **Plage** `"HH:MM-HH:MM"` = `(from,to)` en minutes. `from < to` = même jour `[from,to)` ; **`from > to` = nocturne** `[from,1440) ∪ [0,to)` (traverse minuit) ; **`from == to` = invalide**.
- **Anti-chevauchement** : au sein d'un jour, les ensembles de minutes couverts par les plages sont **disjoints** (le calcul tient compte du wrap nocturne). Plages triées par `from`.
- **Exceptions** : `date` = date ISO calendaire valide, **unique** dans la liste ; chaque exception porte un `DaySchedule` (Fermé férié, 24h, ou plages). Borné ≤ **366** exceptions/site. (Sémantique de priorité date>hebdo = **B-iii**, consommation ; B-i ne fait que stocker/valider/éditer.)
- **Normaliseur rétro-compatible** (fonction pure) : ancienne forme `{"mon":["09:00-17:00"],"sat":[]}` → `{weekly:{mon:{ranges:[...]}, sat:{closed:true}}, exceptions:[]}` ; `{}` → `{weekly:{},exceptions:[]}`. La forme canonique est aussi acceptée telle quelle. ⇒ **zéro migration DB** (JSONB, normalisé à la lecture ; données existantes vides).

## 3. Module logique pur — `web/src/components/ui/weekly-hours.ts`

Fonctions **pures** (testables vitest, env `node`, sans rendu — pattern `rules-adapter` de D4-A) ; le widget et (miroir) le front les importent.

```ts
export const DAYS = ["mon","tue","wed","thu","fri","sat","sun"] as const;
export type Day = (typeof DAYS)[number];
export type DaySchedule = { closed: true } | { h24: true } | { ranges: string[] };
export type Exception = { date: string } & DaySchedule;
export type OperatingHours = { weekly: Partial<Record<Day, DaySchedule>>; exceptions: Exception[] };
export type Target = "weekdays" | "weekend" | "all";
```

- `normalize(v: unknown): OperatingHours` — accepte ancienne/nouvelle forme → canonique ; entrée illégale → `{weekly:{},exceptions:[]}`.
- `targetDays(t: Target): Day[]` — weekdays=mon-fri, weekend=sat,sun, all=mon-sun.
- `toMinutes(hhmm): number` ; `parseRange(r): {from:number,to:number} | null` (null si RE KO).
- `RANGE_RE = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/`.
- `isRangeValid(r): boolean` — `RANGE_RE.test(r)` **et** `from !== to`.
- `rangesOverlap(a: string, b: string): boolean` — vrai si les minutes couvertes (avec wrap nocturne) s'intersectent.
- `isValidDay(d: DaySchedule): boolean` — `closed`/`h24` toujours valides ; `ranges` : chaque plage `isRangeValid` **et** aucune paire `rangesOverlap`.
- `isValidException(e, seenDates): boolean` — `date` ISO valide, non déjà vue, `DaySchedule` valide.
- `isValid(oh: OperatingHours): boolean` — tous les `weekly` valides **et** toutes les exceptions valides (dates uniques) **et** ≤366 exceptions.
- `applyQuickFill(oh, from, to, target): OperatingHours` — pour chaque jour de `target`, **écrase** `weekly[day] = {ranges:[\`${from}-${to}\`]}`.
- `copyDay(oh, src: Day, target): OperatingHours` — copie `weekly[src]` (le `DaySchedule` complet) vers chaque jour de `target` (≠ src).
- `sortExceptions(list): Exception[]` — tri par `date` asc.
- Toutes retournent un **nouvel** objet (pas de mutation).

## 4. Widget — `weekly-hours-field.tsx` (conserve la clé `weekly_hours`)

Réutilise les helpers ci-dessus (supprime les copies locales redondantes). État interne = `OperatingHours` via `normalize(value)`.

**Section hebdomadaire** (grille `grid-cols-1 lg:grid-cols-2`, pile sur étroit) :
- **Barre remplissage rapide** (pleine largeur) : `time` from/to (déf. 09:00/17:00) + `select` cible (Weekdays/Weekend/All) + **Appliquer** → `applyQuickFill`.
- Par jour : un **mode** (Fermé / 24h / Personnalisé). En **Personnalisé** : éditeur de plages (from/to `time`, +plage, supprimer ; overnight autorisé) + un **« copier vers »** (Weekdays/Weekend/All) → `copyDay`. Plage invalide/chevauchante → `border-destructive`.

**Section exceptions** :
- Liste triée (`sortExceptions`) des overrides ; chaque item : date + mode (Fermé/24h/Personnalisé + plages) + supprimer.
- **« Ajouter une exception »** : `<input type="date">` + mode. Bloque une date déjà présente (message). Cap 366.

**Validité** : chaque `commit` appelle `onChange(next, isValid(next))` → `RecordForm` bloque la sauvegarde (via `jsonOk`) et affiche l'erreur. **Note timezone** : hint « Heures locales du site (`timezone`) ».

## 5. Backend — validateur (autorité)

`modules/location/schemas.py` : `normalize_operating_hours(v: dict) -> dict` (accepte ancienne/nouvelle forme → canonique) + `_validate_operating_hours(oh: dict)` (miroir exact de `isValid` : modes valides, plages `RE` + `from!=to` + anti-chevauchement, dates d'exception ISO uniques, ≤366). Un **`@field_validator("operating_hours", mode="before")` partagé** sur **`SiteCreate` ET `SiteUpdate`** normalise puis valide (`ValueError` → 422). Le backend **stocke la forme canonique**. Autorité ; le widget est le miroir UX (une saisie contournant le front → 422). Tests via une fonction partagée (DRY).

## 6. i18n (namespace `weekly_hours`, en/fr/es, mêmes clés, vraies trads)

Ajouter : `quick_fill`, `target.weekdays|weekend|all`, `apply`, `copy_to`, `mode.closed|h24|custom`, `invalid_range`, `overlap`, `exceptions.title`, `exceptions.add`, `exceptions.date`, `exceptions.none`, `exceptions.duplicate`, `tz_note`.

## 7. Données & parité

- **Forme JSONB, normalisée à la lecture — zéro migration.** Ancienne donnée (vide) upgrade transparent.
- **Parité** : le widget expose exactement ce que le backend applique (modes, overnight, anti-chevauchement, exceptions). Aucun contrôle UI sans gate backend ; l'« autorité » est le validateur pydantic.
- **Endpoints inchangés** (site create/update) ; seul le schéma gagne un validateur. Aucun endpoint orphelin.

## 8. Tests (vraie validation)

- **vitest** (`weekly-hours.test.ts`) : `normalize` (ancienne→nouvelle, canonique idempotente, illégal→vide) ; `isRangeValid` (même-jour, overnight, `from==to`→KO, malformé→KO) ; `rangesOverlap` (même-jour, overnight qui chevauche, disjoint) ; `isValidDay` (closed/h24/ranges valides+chevauchement KO) ; `isValid` (exceptions dates uniques, cap) ; `applyQuickFill` (weekdays/weekend/all écrase) ; `copyDay` (copie DaySchedule, ignore soi) ; `sortExceptions`.
- **pytest** (`test_location_schemas`) : `normalize_operating_hours` (ancienne→canonique) ; validateur — canonique OK, overnight OK, chevauchement rejeté, `from==to` rejeté, mode inconnu rejeté, date d'exception invalide/doublon rejetée, >366 rejeté ; sur **SiteCreate ET SiteUpdate**.
- **Optionnel** (stack up) : smoke Playwright `/locations` — 2 colonnes, Appliquer, ajouter une exception, plage inversée bloque la sauvegarde.

## 9. Découpage (pour le plan)

1. `weekly-hours.ts` (types + `normalize` + helpers purs) + vitest.
2. Backend `normalize_operating_hours` + `_validate_operating_hours` + `@field_validator` (Create/Update) + pytest.
3. Widget — section hebdo (modes + remplissage rapide + copie + 2 colonnes) + section exceptions + validité réelle + note tz + i18n.
4. Gate finale : vitest + pytest + tsc + revue parité.

## 10. Roadmap D4-B (sous-projets suivants — chacun sa spec→plan→impl)

- **B-ii — Édition multi-sites (bulk)** : ajouter le **multi-select au DataGrid** (capacité réutilisable pour toutes les listes admin) + un **endpoint bulk transactionnel** (`PATCH /sites/bulk/operating-hours` : liste d'ids ≤500, scope-enforced par item, audité) + un **dialog** réutilisant le widget B-i pour définir les horaires d'un lot de sites. Dépend de B-i (réutilise le widget + le validateur).
- **B-iii — Consommation & affichage** : côté partagé/back, `is_open_at(oh, dt, tz) → {open, until, next_change}` (exceptions **priment** l'hebdo pour la date ; gère l'overnight) ; côté UI, un **badge « Ouvert / Fermé — ouvre à … »** + une **table d'horaires** lisible (surfaces agent/citoyen). Ferme la boucle « stocké → utilisé ». Dépend de B-i (forme canonique).

Chaque sous-projet est tracé en tâche ; B-ii puis B-iii après B-i mergé.

## 11. Isolation

Branche `feat/opening-hours` depuis `develop`, mergeable seule. B-ii/B-iii = branches et specs distinctes.
