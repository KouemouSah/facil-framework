# D4-B (B-i) — Amélioration du widget d'horaires d'ouverture (WeeklyHoursField) — Design

> **Sous-projet** : D4-B, **partie B-i** (le multi-sites = B-ii, spec séparée). Après D4-A (éditeur de règles) mergé.
> **Branche** : `feat/opening-hours` depuis `develop`, mergeable seule.
> **Date** : 2026-07-16.

## 0. Contexte & état actuel (vérifié dans le code)

`Site.operating_hours` (JSONB, `modules/location/models.py:51`) porte la forme `{"mon": ["09:00-17:00"], "sat": [], …}`. Elle est saisie par un widget bespoke **`WeeklyHoursField`** (`web/src/components/ui/weekly-hours-field.tsx`) — une ligne par jour (`mon`..`sun`), case ouvert/fermé + plages `HH:MM-HH:MM` (deux `<input type="time">`), câblé dans le `RecordForm` du site via `widget: "weekly_hours"`.

Deux manques constatés :
- **Aucune saisie en bulk** : chaque jour se remplit à la main (fastidieux pour « Lun-Ven 09:00-17:00 »).
- **Validité fantôme** : le widget appelle **toujours** `onChange(next, true)` (l.59) — une plage inversée (`from ≥ to`) ou malformée n'est jamais signalée comme invalide, et le backend stocke `operating_hours` en **`dict` opaque** sans validation (`schemas.py:28,72`). `RecordForm.validate()` (`record-form.tsx:225-232`) bloque pourtant déjà la sauvegarde d'un champ json dont `jsonOk[name]` est `false` — le plombage existe, seul le widget ne rapporte jamais `false`.
- **Affichage** : pile verticale de 7 lignes ; en plein page elle n'exploite pas la largeur.

## 1. Objectif & non-objectifs

**Objectif** : rendre la saisie des horaires rapide (copie inter-jours) et fiable (validité réelle, gate backend), avec un affichage 2 colonnes en plein page. Contained, frontend + un petit validateur backend.

**Non-objectifs (assumés)** :
- **Pas de multi-sites** (action groupée sur un lot de sites) — c'est **B-ii**, sa propre spec (multi-select DataGrid réutilisable + endpoint bulk).
- **Pas de plages nocturnes** (traversant minuit) : validité = **même jour** (`from < to`). Le nocturne est différé (documenté).
- **Pas de contrôle de chevauchement** entre plages d'un même jour (choix user : validation simple).
- **Pas de day-picker custom** pour les cibles bulk : 3 presets (weekdays/weekend/all). Les jours restent éditables un à un après.
- **Forme de données inchangée** (`{day: [ranges]}`) → **zéro migration**.

## 2. Module logique pur — `weekly-hours.ts`

Nouveau `web/src/components/ui/weekly-hours.ts` (à côté du widget) : fonctions **pures** (testables vitest, env `node`, sans rendu — même pattern que `rules-adapter` en D4-A). Le widget les importe.

```ts
export const DAYS = ["mon","tue","wed","thu","fri","sat","sun"] as const; // ordre existant du widget
export type Day = (typeof DAYS)[number];
export type WeeklyHours = Partial<Record<Day, string[]>>;
export type Target = "weekdays" | "weekend" | "all";
```

- `targetDays(target: Target): Day[]` — `weekdays` → mon-fri ; `weekend` → sat,sun ; `all` → mon-sun.
- `applyQuickFill(hours: WeeklyHours, from: string, to: string, target: Target): WeeklyHours` — pour chaque jour de `target` : **écrase** le jour → ouvert avec l'unique plage `\`${from}-${to}\``. (Les autres jours inchangés.)
- `copyDay(hours: WeeklyHours, src: Day, target: Target): WeeklyHours` — copie le **tableau complet** de plages de `src` vers chaque jour de `target` (écrase). Un jour cible = `src` est ignoré (pas de copie sur soi).
- `RANGE_RE = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/` (déplacée ici depuis le widget).
- `isRangeValid(r: string): boolean` — `RANGE_RE.test(r)` **ET** `from < to` (comparaison lexicographique de `HH:MM`, correcte car zéro-paddé).
- `isValidHours(hours: WeeklyHours): boolean` — toutes les plages de tous les jours ouverts sont `isRangeValid`. (Un jour ouvert avec `[]` est valide — « ouvert sans plage » = à compléter, mais pas invalide ; un jour fermé = absent.)

Ces fonctions ne mutent jamais `hours` (retour d'un nouvel objet).

## 3. Widget — `weekly-hours-field.tsx`

Réutilise les helpers ci-dessus (supprime les copies locales `RANGE_RE`/`isWeeklyHours`/`normalize` redondantes ou les ré-exporte depuis `weekly-hours.ts` pour DRY).

1. **Barre « remplissage rapide »** (pleine largeur, au-dessus de la grille) : deux `<input type="time">` (from/to, défaut 09:00/17:00) + un `<select>` cible (Weekdays/Weekend/All) + bouton **Appliquer** → `commit(applyQuickFill(hours, from, to, target))`. Désactivée si `disabled`.
2. **Copie par jour** : sur chaque jour **ouvert**, un petit contrôle « copier vers » (Weekdays/Weekend/All) → `commit(copyDay(hours, day, target))`. (Un `<select>`+bouton compact, ou un menu ; réutiliser le style bouton-ghost existant.)
3. **Layout 2 colonnes** : la grille des 7 jours passe de `space-y-2` à `grid grid-cols-1 gap-x-6 gap-y-2 lg:grid-cols-2`. Chaque cellule-jour garde sa structure (`grid-cols-[7rem_1fr]`). Sur `< lg` → 1 colonne (pile actuelle). Responsive par défaut (règle repo).
4. **Validité réelle** : `commit` appelle `onChange(next, isValidHours(next))` (au lieu de `true`). Les plages invalides gardent déjà `border-destructive` (calculé via `isRangeValid`). `RecordForm` bloque alors la sauvegarde (via `jsonOk`) et affiche l'erreur de champ.

## 4. Backend — validateur `operating_hours` (autorité)

`modules/location/schemas.py` : une fonction partagée `validate_operating_hours(v: dict) -> dict` + `@field_validator("operating_hours")` sur **`SiteCreate` ET `SiteUpdate`** (DRY, une seule impl). Rejette (`ValueError` → 422) :
- une valeur non-`dict` ; une clé hors `{mon..sun}` ; une valeur de jour non-`list[str]` ;
- une plage qui n'est pas `HH:MM-HH:MM` (même regex que le front) **ou** avec `from ≥ to`.
Un `dict` vide et un jour à `[]` restent valides. Le backend est le **gate** ; le widget est le miroir UX (même split autorité/miroir que D4-A ; une saisie qui contournerait le front est rejetée en 422).

## 5. i18n

Namespace `weekly_hours` existant (en/fr/es) — ajouter : `quick_fill` (label), `target.weekdays`/`target.weekend`/`target.all`, `apply`, `copy_to`, `invalid_range` (message). Mêmes clés dans les 3 fichiers, vraies traductions fr/es.

## 6. Données & parité

- **Forme inchangée** `{day: [ranges]}` — **aucune migration**.
- **Parité** : le widget expose exactement ce que le backend applique (forme + `from < to`). Aucun contrôle UI sans gate backend.
- **Backend inchangé côté endpoints** : mêmes routes site create/update ; seul le schéma gagne un validateur. Aucun endpoint orphelin.

## 7. Tests (vraie validation)

- **vitest** (`weekly-hours.test.ts`, fonctions pures) : `applyQuickFill` (weekdays/weekend/all, écrase la cible, laisse le reste), `copyDay` (copie le tableau complet, ignore soi-même), `isValidHours`/`isRangeValid` (plage valide, `from ≥ to` → invalide, malformée → invalide, jour `[]`/fermé → valide), `targetDays`.
- **pytest** (`test_location_schemas` ou existant) : `validate_operating_hours` — dict vide OK ; `{"mon":["09:00-17:00"]}` OK ; `{"mon":["17:00-09:00"]}` rejeté ; `{"mon":["9-17"]}` rejeté ; clé `"funday"` rejetée ; valeur non-liste rejetée. Sur `SiteCreate` **et** `SiteUpdate`.
- **Optionnel** (stack up) : smoke visuel du 2 colonnes + Appliquer sur `/locations` (Playwright headless).

## 8. Découpage (pour le plan)

1. `weekly-hours.ts` (helpers purs) + vitest.
2. Backend `validate_operating_hours` + `@field_validator` sur SiteCreate/SiteUpdate + pytest.
3. Widget : barre remplissage rapide + copie par jour + layout 2 colonnes + validité réelle (`onChange` avec `isValidHours`) + i18n en/fr/es.
4. Gate finale : vitest + pytest + tsc + revue parité.

## 9. Isolation

Branche `feat/opening-hours` depuis `develop`, mergeable seule. Ne pas mélanger avec B-ii (multi-sites).
