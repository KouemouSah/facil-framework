# D4 · Sous-projet A — Éditeur de règles de validation (basique via UI + avancé via JSON) — Design

> **Sous-projet** : D4 (passe Studio `/fields`), **sous-projet A**. Les autres items D4 (horaires d'ouverture bulk+plein-page ; référentiel villes) auront leur propre spec.
> **Branche** : `feat/field-rules-editor` depuis `develop`, mergeable seule.
> **Date** : 2026-07-15.

## 0. Contexte & état actuel (vérifié dans le code)

SP1 a livré un descripteur de champ (type×widget×rules) à **deux consommateurs** : le backend autoritatif `app/core/schema/pydantic_gen.py` (`_coerce`) et le miroir client `web/src/lib/schema/to-zod.ts` (`rulesToZod`). Les règles sont stockées dans `FieldDefinition.rules` (JSONB, `app/models/field_definition.py:50`), opaques en base.

Aujourd'hui, dans le Studio (`web/src/modules/fields/fields.ts` `buildFieldDefFields`, ligne 224), les règles se saisissent dans **un unique textarea JSON brut** (`{ name: "rules", type: "json" }`), sans aucune aide type-aware. L'ensemble des règles réellement **appliquées** est petit et fermé :

- `string`/`text`/`richtext` → `min_length`, `max_length`, `pattern` (`_coerce` l.39-44 ; `rulesToZod` l.28-30).
- `number`/`decimal` → `min`, `max` (`_coerce` l.52-55 ; `rulesToZod` l.18-21).
- `number` **est déjà entier par construction** (`_coerce` l.56-63 rejette tout non-entier) ; `decimal` est le type décimal. Il n'y a donc **pas** de règle « entier-seul » à ajouter : entier = choisir le type `number`.
- `money` → **aucune règle** (forme `{amount, currency}` codée en dur, l.66-80).
- `boolean`/`date`/`datetime`/`time`/`relation`/`file` → **aucune règle** (coercition de type seulement).
- `select`/`multiselect` → valeurs autorisées via `options` (éditeur séparé, l.222), **pas** via `rules`.
- `json` → opaque (l.116-117).
- `required` est une **colonne booléenne séparée** (toggle existant l.198), pas une clé de `rules`.

Le formulaire de def de champ est un **`RecordForm`** piloté par un `FieldDef[]` qui supporte des conditions `visible_if` (ex. `options` visible uniquement pour select/multiselect, l.222-223) et des **adaptateurs de payload** au bord du module (envelope `options`/`default`, cf. l.236-249). C'est le socle réutilisé ci-dessous.

## 1. Objectif & non-objectifs

**Objectif** : remplacer le textarea JSON brut par un **éditeur type-aware** : des entrées UI pour les règles courantes (par type), **plus** un champ « Règles avancées (JSON) » pour ce que l'UI ne couvre pas. Étendre le jeu de règles réellement **appliquées** (backend + zod) au-delà de l'existant. Rendre la config de champ plus riche et plus facile sans jamais afficher une règle non appliquée (parité).

**Non-objectifs (assumés)** :
- **Pas de `max_size` fichier** dans cet incrément (enforcement au niveau de l'API d'upload d'asset, pas du descripteur — chantier séparé). On livre `allowed_extensions` (contrôle descripteur, bon marché).
- **Pas de grammaire de dates relatives** au-delà des tokens `today`/`now` (pas de `today+30d`) — l'offset avancé passe par le JSON avancé.
- **Pas de règles inter-champs** (ex. `end_date > start_date`) — hors périmètre (relèverait du JSON avancé / d'un futur moteur de conditions).
- **Pas de changement du modèle de données** : `rules` reste un JSONB ; on n'ajoute que des **clés**. Zéro migration.

## 2. Matrice de règles (validée)

`required` reste le toggle séparé et s'applique à tous les types. Chaque règle ci-dessous est **appliquée backend** (`_coerce`) **et** miroir zod, sinon elle n'est pas exposée.

| Type | Règles UI (clés `rules`) |
|---|---|
| string / text / richtext | `min_length`, `max_length`, `pattern` (presets email/phone/url/slug/alphanumeric → remplissent la regex ; + custom) |
| number *(entier)* | `min`, `max`, `step` (multiple-de) |
| decimal | `min`, `max`, `step`, `max_decimal_places` |
| money | `min`, `max` (sur le montant, devise du champ) |
| date / datetime | `min`, `max` — ISO statique **ou** token relatif `today`/`now` |
| time | `min`, `max` (ISO statique) |
| multiselect | `min_items`, `max_items` (valeurs via `options`) |
| boolean | `must_be_true` (case obligatoirement cochée — consentement) |
| file | `allowed_extensions` (liste, ex. `["pdf","png"]`) — *`max_size` différé* |
| select / relation / json | aucune règle nouvelle (`options`/`relation_filter`/opaque) |

Sémantique clé :
- **`step`** (number/decimal) : `value` doit être un multiple de `step` (comparaison en `Decimal`, jamais float). `step > 0`.
- **`max_decimal_places`** (decimal) : nombre de décimales du montant ≤ N.
- **`money` min/max** : comparaison `Decimal(amount)` ; une seule devise assumée par champ (pas de comparaison inter-devises).
- **dates `min`/`max`** : soit une valeur ISO du même type, soit le token `today` (date) / `now` (datetime), résolu **au moment de la validation** en **UTC** (cohérent backend/serveur ; documenté). `time` : ISO statique uniquement (un `now` sur une heure est ambigu → exclu).
- **`min_items`/`max_items`** (multiselect) : `len(value)` dans `[min_items, max_items]` (après le contrôle « sous-ensemble de options » existant).
- **`must_be_true`** (boolean) : `value is True` obligatoire (indépendant de `required`, mais implique une valeur).
- **`allowed_extensions`** (file) : l'extension (dernier `.` du string id/URL, insensible à la casse) doit appartenir à la liste. Liste vide/absente = pas de contrainte.

## 3. Backend — `pydantic_gen._coerce` (autoritatif)

Additions ciblées, dans le bloc de chaque type, en accumulant les erreurs via `_err(key, msg)` (jamais de court-circuit sauf violation de type dure) :

- **number/decimal** (après min/max) : si `"step" in rules` et `step > 0` et `num % Decimal(str(step)) != 0` → `_err(key, f"must be a multiple of {step}")`. Pour `decimal` : si `"max_decimal_places" in rules` et le nombre de décimales de `num` > N → `_err`. (Le check entier de `number` reste inchangé.)
- **money** (après validation de forme) : `amt = Decimal(value["amount"])` ; si `min`/`max` présents, comparer et `_err` sinon.
- **date/datetime/time** (après parse réussi) : résoudre chaque borne `rules["min"]`/`["max"]` — token `today`→`_dt.date.today()` (UTC), `now`→`_dt.datetime.now(tz=utc)` ; sinon parser ISO. Comparer la valeur parsée aux bornes → `_err(key, f"must be ≥/≤ {bound}")`.
- **multiselect** (après le check sous-ensemble) : `n = len(value)` ; `min_items`/`max_items` → `_err` sinon.
- **boolean** : si `rules.get("must_be_true")` et `value is not True` → `_err(key, "must be accepted")`.
- **file** : si `allowed_extensions` non vide, extraire l'extension du string et vérifier l'appartenance (casse-insensible) → `_err(key, f"must be one of {exts}")` sinon.

Tous les messages suivent le style existant (`must be ≥ …`) et produisent le 422 mappé par `RecordForm.ApiError.fieldErrors()`.

## 4. Client — `to-zod.rulesToZod` (miroir, non-autoritatif)

`rulesToZod` applique les règles sur la **forme string** de RecordForm. Additions :
- number/decimal : `step` (`Number(v) % step === 0`), `max_decimal_places` (regex décimales).
- date/datetime/time : brancher hors du fallback string — `refine` ISO valide + comparaison de bornes (résoudre `today`/`now` côté client pour un feedback immédiat ; le backend reste l'autorité).
- multiselect : valeur = tableau ; `min`/`max` sur `.length`.
- boolean : `must_be_true` → `refine(v === true)`.
- money : refine sur `Decimal`-like du montant.
- file : `allowed_extensions` via regex d'extension.
Le miroir vise le **feedback UX** ; toute divergence est tranchée par le 422 backend (déjà géré par RecordForm).

## 5. Descripteur — type `rules`

Étendre le type `rules` du `FieldSpec` (`web/src/lib/schema/types.ts`) et sa contrepartie backend (le `FieldSpec`/`FieldDefinitionIn`) avec les clés optionnelles ci-dessus (toutes optionnelles, additives, rétro-compatibles). Aucune clé n'est requise ; un `rules` vide reste valide.

## 6. Studio — UI type-aware (dans le `RecordForm` existant)

Remplacer le champ unique `{ name: "rules", type: "json" }` (fields.ts:224) par :

1. **Des `FieldDef` par sous-clé de règle**, chacun `visible_if` sur `type` (même mécanisme que `options`/`relation_resource`). Ex. `rule_min_length`/`rule_max_length` (string/text/richtext), `rule_pattern` + un select **preset** (email/phone/url/slug/alphanumeric/custom) qui pré-remplit `rule_pattern`, `rule_min`/`rule_max`/`rule_step` (number/decimal), `rule_max_decimal_places` (decimal), `rule_money_min`/`rule_money_max` (money), `rule_date_min`/`rule_date_max` (date/datetime/time ; input date + case « aujourd'hui/maintenant »), `rule_min_items`/`rule_max_items` (multiselect), `rule_must_be_true` (boolean, checkbox), `rule_allowed_extensions` (file, liste). Regroupés visuellement sous un intitulé **« Validation »**.
2. **Un champ « Règles avancées (JSON) »** (`rules_advanced`, `type: "json"`, colSpan 2) pour **uniquement** les clés que l'UI ne possède pas.

**Adaptateurs au bord du module** (comme `splitPayload`/`flattenProvider`) :
- `flattenRules(rules)` (chargement) : répartit chaque clé connue vers son input ; le **reste** va dans `rules_advanced`.
- `nestRules(form)` (save) : reconstruit `rules` = { clés UI (typées/parsées) } ∪ { `rules_advanced` }. **Garde disjointe** : si `rules_advanced` contient une clé possédée par l'UI → **erreur de champ** (« géré via l'UI, retirez-le du JSON avancé »). Les deux surfaces ne peuvent donc jamais se contredire.

**Sanity client** (zod des inputs Studio, feedback immédiat, avant même le backend) : `min_length ≤ max_length`, `min ≤ max`, `step > 0`, `max_decimal_places ≥ 0`, regex `pattern` compilable, bornes date ISO ou token valide, `min_items ≤ max_items`.

**i18n** : toutes les chaînes (labels, hints, presets, messages) en clés `en/fr/es` (namespace `fields`).

## 7. Parité & données

- **Parité stricte** : chaque input UI ↔ une clé `rules` réellement appliquée par `_coerce`. Zéro règle affichée non appliquée ; zéro clé appliquée non éditable (sauf différés documentés : `max_size`, offsets relatifs, inter-champs → JSON avancé).
- **Données** : `rules` JSONB, additif ; **aucune migration**. Les defs existantes (ex. `{min_length, max_length}`) se chargent telles quelles dans les nouveaux inputs.
- **Backend inchangé côté endpoints** : mêmes routes `/api/v1/admin/field-definitions` ; seul `_coerce` gagne des branches. Pas d'endpoint orphelin.

## 8. Tests (vraie validation)

- **pytest** (`_coerce`) : un test par nouvelle règle × (pass / fail) — step multiple, max_decimal_places, money min/max, date min/max statique **et** `today`/`now`, multiselect items, boolean must_be_true, file allowed_extensions ; + non-régression des règles existantes. Le token `today`/`now` testé avec une valeur fixe injectée (pas d'appel horloge non déterministe dans l'assertion — passer la « now » de référence en paramètre ou monkeypatch).
- **vitest** (`rulesToZod` + `flattenRules`/`nestRules`) : miroir de chaque règle ; round-trip flatten→nest ; **garde disjointe** (clé UI dans le JSON avancé → erreur).
- **e2e (optionnel, si stack up)** : définir une règle via l'UI, la voir appliquée sur un vrai formulaire (422 → message de champ).

## 9. Découpage (pour le plan)

1. Backend `_coerce` : additions par type + tests pytest (autorité d'abord).
2. Descripteur : étendre le type `rules` (backend + `types.ts`).
3. Client `rulesToZod` : miroir + tests vitest.
4. Adaptateurs `flattenRules`/`nestRules` + garde disjointe + tests vitest.
5. Studio UI : `FieldDef` type-aware `visible_if` + presets pattern + « Règles avancées (JSON) » + sanity zod + i18n en/fr/es.
6. Gate finale : pytest + vitest + tsc ; revue parité (§11bis / parité) ; e2e optionnel.

## 10. Isolation

Branche `feat/field-rules-editor` depuis `develop`, mergeable seule. Ne pas mélanger avec les autres items D4 (horaires, villes) — specs séparées.
