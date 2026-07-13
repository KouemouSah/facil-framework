# SP1 — Socle « Field Schema & Custom Fields »

> **Date** : 2026-07-13
> **Statut** : design validé, prêt pour plan d'implémentation
> **Sous-projet** : SP1 (socle). Prérequis de **SP2 — Moteur documentaire & Studio**.

---

## 1. Contexte et problème

Facil Framework se positionne comme une plateforme **customisable sans code**. Or aujourd'hui,
la configuration structurée se saisit **en JSON brut** dans l'interface d'administration :

| Surface | Preuve dans le code | Symptôme |
|---|---|---|
| `organization.document_identity` | `packages/web/src/modules/organization/fields.ts:34` (`type: "json"`) | l'administrateur tape du JSON à la main |
| `organization.settings` | `packages/web/src/modules/organization/fields.ts:39` | idem |
| `site.operating_hours` | `packages/web/src/modules/location/fields.ts:35` | idem |
| `site.metadata`, `org_unit.metadata` | `packages/web/src/modules/location/fields.ts:36` | idem |
| page `/config` (config-store) | `packages/web/src/modules/settings/page.tsx` | valeur JSON éditée brute |

Le libellé montré à l'utilisateur assume le format : *« Horaires d'ouverture **(JSON)** »*
(`packages/web/src/i18n/messages/fr.json:302`).

**Ce n'est pas seulement un défaut d'ergonomie — c'est une incohérence de données.**
`operating_hours` porte aujourd'hui **deux formes contradictoires** parce que rien ne le valide :

- le test backend écrit `{"monday": {"open": "08:00", "close": "16:00"}}`
  (`packages/backend/tests/test_modules_org_location.py:33`) ;
- l'aide affichée à l'utilisateur documente `{"mon": ["09:00-17:00"], "sat": []}`
  (`packages/web/src/i18n/messages/fr.json:305`).

En parallèle, il n'existe **aucun mécanisme permettant à une organisation de définir ses propres
champs** sur les entités métier — capacité attendue d'une plateforme de ce type (équivalent du
*Studio* d'Odoo), et exigée pour l'identification des documents par entité (SP2).

### Le pattern correct existe déjà dans le repo, mais n'a jamais été généralisé

La chaîne complète **« schéma déclaré côté serveur → formulaire généré côté client »**
fonctionne **déjà en production**, pour un seul consommateur : les **providers**.

- `packages/backend/app/core/providers/base.py:18` — `cfg(key, label, type=, required=, default=, hint=)`
  déclare un champ de configuration.
- `packages/backend/app/core/providers/base.py:37-43` — `Provider.config_schema()` expose la liste.
- `packages/backend/app/api/admin_providers.py` — `GET /registered` renvoie le schéma ; le `config`
  écrit est **allowlisté aux clés déclarées** (garde SEC-F2).
- `packages/web/src/modules/providers/fields.ts:14-22` — `configFieldToFieldDef()` transforme le
  schéma serveur en `FieldDef[]` → **formulaire généré, zéro dérive client/serveur**.

Le commentaire de `base.py:14` énonce déjà l'intention :
*« Field types the admin config form understands (**mirrors the web RecordForm**) »*.

**Le maillon pauvre est le backend, pas le frontend.** `RecordForm`
(`packages/web/src/components/ui/record-form.tsx:30-32`) sait rendre **15 types** de contrôles :
`text`, `email`, `password`, `textarea`, `number`, `checkbox`, `ref`, `org`, `party`, `address`,
`json`, `select`, `image`, `color`, `timezone`. Le descripteur backend n'en connaît que **4**
(`text | number | boolean | json`, `base.py:15`).

**SP1 = mener cette généralisation à son terme, et l'ouvrir aux champs définis par l'utilisateur.**

---

## 2. Périmètre

### Dans le périmètre

1. Un **descripteur de champ unique** (`FieldSpec`), à trois axes : **type × widget × rules**.
2. Un **résolveur de schéma** fusionnant les schémas **déclarés en code** (produit) et les
   **définitions en base** (champs custom, scopés par organisation).
3. Un **endpoint** `GET /api/v1/schema/{target}` servant le schéma résolu.
4. La **génération** de la validation **pydantic** (serveur) et **zod** (client) depuis ce
   descripteur unique.
5. Une **UI de création de champs** (« Studio »), scopée par organisation.
6. La **suppression des JSON bruts** que le produit maîtrise (`document_identity`, `settings`,
   `/config`).
7. **Isolation inter-organisations garantie par construction** et **prouvée par test**.

### Hors périmètre (différé, décision délibérée)

| Élément | Raison | Reporté à |
|---|---|---|
| Colonnes `meta` / `metadata` | Sacs d'extension **opaques par nature** (imports, refs externes). Y appliquer une allowlist est contradictoire. Restent en `json`. | Jamais (exception assumée) |
| **Groupes répétables** (`One2many` : lignes de facture, horaires par jour) | Capacité à part entière ; les schémas v1 sont **plats**. | v2 |
| `operating_hours` en schéma générique | Structure répétable → incompatible avec un schéma plat. Traité par un **widget dédié `weekly_hours`** (voir §12). | — |
| Champs custom **globaux** (non rattachés à une organisation) | Vecteur exact de la corruption inter-organisations à éviter. **Interdit par le modèle** (`organization_id` NOT NULL). | Jamais |
| Champs **calculés** (formules) | Surface de sécurité (évaluation d'expressions) disproportionnée en v1. | v2 |
| Héritage de **valeurs** (ex. pied de page du siège hérité par la succursale) | Problème distinct — c'est du ressort de SP2 sur `document_identity`. SP1 hérite les **définitions**, pas les valeurs. | SP2 |

---

## 3. Principes directeurs

1. **UI-first, littéralement.** Le descripteur est défini par ce que `RecordForm` sait rendre.
   Un type que l'UI ne sait pas afficher n'existe pas dans le descripteur. Le JSON résultant est
   un **détail de stockage que l'utilisateur ne voit jamais**.
2. **Une source, deux consommateurs.** Un descripteur → **pydantic** (serveur) **et** **zod**
   (client). Jamais deux définitions à synchroniser.
3. **Le schéma est une allowlist.** Une clé non déclarée est **rejetée (422)**, jamais ignorée en
   silence. La sécurité est un effet de bord du design (précédent SEC-F2).
4. **Zéro DDL de mutation à l'exécution.** Créer un champ ne modifie **aucune colonne**. Le seul
   DDL émis est **additif et concurrent** (index d'expression), sur demande explicite et plafonné.
5. **Strict sur les types, généreux sur les widgets.** Un type coûte 7 surfaces (contrôle, zod,
   pydantic, sémantique de tri/index, export CSV, rendu documentaire, tests) ; un widget en coûte 1.
6. **Le JSON brut est relégué, pas supprimé.** `JsonField` reste — pour l'opaque uniquement.
   Il devient l'exception documentée, plus le défaut.
7. **Rien n'est détruit.** Supprimer une définition = **archiver**. Les valeurs restent.

---

## 4. Architecture

```text
                     ┌─────────────────────────────────────────┐
   Schémas PRODUIT   │  Registre en CODE (versionné avec le    │
   (non éditables)   │  code, calqué sur default_registry())   │
                     │  ex. organization.document_identity      │
                     └──────────────────┬──────────────────────┘
                                        │
                                        ▼
                     ┌─────────────────────────────────────────┐
   Champs CUSTOM     │  Table field_definition                 │
   (org-scopés)      │  organization_id NOT NULL               │──┐
                     └──────────────────┬──────────────────────┘  │
                                        │                         │
                                        ▼                         │
                     ┌─────────────────────────────────────────┐  │
                     │  RÉSOLVEUR DE SCHÉMA                    │  │ visible_orgs
                     │  fusion + héritage (OrgUnit.path,       │◄─┘ (RBAC existant)
                     │  Organization.parent_id borné)          │
                     │  → cache Redis (clé org+target)         │
                     └──────────────────┬──────────────────────┘
                                        │
                     GET /api/v1/schema/{target}  → FieldSpec[]
                                        │
                 ┌──────────────────────┴───────────────────────┐
                 ▼                                              ▼
   ┌──────────────────────────┐              ┌──────────────────────────────┐
   │ Générateur pydantic      │              │ fieldSpecToFieldDef()        │
   │ (validation SERVEUR      │              │ → FieldDef[] → RecordForm    │
   │  = la vérité)            │              │   (validation zod, reflet)   │
   └──────────────────────────┘              └──────────────────────────────┘
```

**Le backend tranche, le frontend reflète** (règle du repo). Toute règle exprimée dans le
descripteur — y compris `visible_if` / `required_if` — est évaluée **des deux côtés**, et le
serveur fait autorité.

---

## 5. Le contrat de champ — trois axes

### Justification du modèle

Odoo, référence explicitement citée pour ce projet, expose ~**16 types** de champs après 20 ans
(`Char`, `Text`, `Html`, `Integer`, `Float`, `Monetary`, `Boolean`, `Date`, `Datetime`, `Binary`,
`Image`, `Selection`, `Many2one`, `One2many`, `Many2many`, `Reference`). Sa richesse ne vient pas
du **nombre de types**, mais de trois axes orthogonaux : **type × widget × attrs**.

**Test d'admission d'un type** : *change-t-il le stockage, la comparaison ou l'indexation ?*
Si non, ce n'est pas un type — c'est un **widget**.

### Axe 1 — TYPES (15)

| Type | Indexable / triable | Notes |
|---|---|---|
| `string` | ✅ | |
| `text` | ✅ | |
| `richtext` | ❌ | **Type le plus dangereux.** Sanitization allowlist **à l'écriture ET au rendu**. Indispensable à SP2 (corps de document) → traité proprement plutôt qu'interdit. |
| `number` | ✅ | |
| `decimal` | ✅ | La précision vit dans les `rules` (`precision`), ce n'est pas un type de plus. |
| `money` | ✅ | Stocké **comme objet** : `{"amount": "1234.56", "currency": "XAF"}` (montant en **chaîne décimale**, jamais en flottant — pas d'arrondi binaire sur de l'argent). Devise par défaut = `Organization.currency` (`organization/models.py:40`). Indexé sur le **montant casté** (§11). **Prérequis de la facture (SP2).** |
| `boolean` | ✅ | |
| `date` | ✅ | |
| `datetime` | ✅ | |
| `time` | ✅ | |
| `select` | ✅ | |
| `multiselect` | ❌ | Tags. |
| `relation` | ✅ | **Généralisation clé** — voir ci-dessous. |
| `file` | ❌ | Pièce jointe. `packages/backend/app/api/assets.py` **refuse aujourd'hui les PDF** (`tests/test_assets_validation.py:21,67-69`) → à étendre pour SP2. |
| `json` | ❌ | Échappatoire, pour l'opaque uniquement. |

**`relation` remplace `org`, `party`, `ref`.** Ce sont aujourd'hui **trois pickers codés en dur**
(`record-form.tsx:218-235`). Un seul type paramétré par sa ressource cible les subsume — c'est le
`Many2one` d'Odoo. **Les trois anciens sont conservés comme alias** → zéro régression sur les
formulaires existants.

### Axe 2 — WIDGETS (présentation ; coût marginal, donc extensible à volonté)

| Type | Widgets |
|---|---|
| `string` | `plain` · `email` · `password` · `url` · `phone` · `color` · `timezone` · `badge` · `copyable` · `masked` |
| `text` | `plain` · `code` |
| `number` / `decimal` | `plain` · `percent` · `rating` · `progress` · `slider` |
| `date` | `date` · `month` · `quarter` · `year` |
| `select` | `dropdown` · `radio` · `segmented` |
| `multiselect` | `tags` · `checkboxes` |
| `relation` | `combobox` · `radio` · `cards` |
| `file` | `image` · `avatar` · `document` · `gallery` |
| `json` | `raw` · **`weekly_hours`** (voir §12) |

Ajouter un widget = **un composant React**. Aucun changement du contrat serveur, du tri, de
l'index, de l'export ou du rendu documentaire.

**Note de compatibilité** : `color` et `timezone` sont aujourd'hui des **types** dans `RecordForm`
(`record-form.tsx:32`). Ils deviennent des **widgets de `string`**. Les valeurs existantes sont des
chaînes → **aucune migration de données**. Les anciens noms restent acceptés comme alias.

### Axe 3 — RULES (déclaratives, sérialisables)

`required` · `min` · `max` · `min_length` · `max_length` · `pattern` · `enum` · `precision` ·
**`visible_if`** · **`required_if`**.

**Contrainte technique dure** : `FieldDef.zod?: z.ZodTypeAny` (`record-form.tsx:45`) est un **objet
JavaScript non sérialisable** — un champ défini en base ne peut donc **jamais** porter un `zod`.
D'où les `rules` déclaratives, que le client **compile** en zod. L'attribut `zod?` existant est
conservé pour les champs codés en dur → zéro régression.

**`visible_if` / `required_if`** (les `attrs` d'Odoo) : *« Numéro de TVA n'apparaît que si
Assujetti = oui »*. Forme v1 volontairement simple : `{ field, op: "eq"|"ne"|"in", value }`.

> **Garde impérative** : évaluées **serveur ET client**. Un champ masqué mais requis, **non
> envoyé**, doit être **accepté** ; **envoyé alors qu'il devrait être masqué**, il doit être
> **rejeté**. Sans l'évaluation serveur, la logique conditionnelle se contourne trivialement.

---

## 6. Modèle de données

### Le concept unificateur

> **Un schéma décrit le contenu d'une colonne JSON d'une entité.**

Une **cible** (`target`) = `entité.colonne_json`.

| Cible | Origine du schéma | Colonne de valeurs | État |
|---|---|---|---|
| `organization.document_identity` | **code** | existe — `organization/models.py:43` | JSON brut → à migrer |
| `organization.settings` | **code** | existe — `organization/models.py:44` | JSON brut → à migrer |
| `organization.custom_fields` | **base** | **à créer** | — |
| `org_unit.custom_fields` | **base** | **à créer** | — |
| `site.custom_fields` | **base** | **à créer** | — |
| `party.custom_fields` | **base** | **existe déjà** — `party/models.py:38` | inexploitée |

`party.custom_fields` **pose déjà la convention de nommage** dans le repo. On s'y aligne.

> **`site.operating_hours` n'est PAS une cible.** Ce n'est pas un blob à sous-champs : c'est **un
> champ unique** du formulaire Site, de type `json` et de widget `weekly_hours` (§12) — exactement
> comme aujourd'hui (`location/fields.ts:35`), mais avec un contrôle dédié au lieu d'un éditeur JSON.
> Ne pas le confondre avec un `target`.

### Décision : `custom_fields` ≠ `meta`

`org_unit.meta` / `site.meta` (colonne DB `metadata`, `organization/models.py:101`,
`location/models.py:56`) sont des sacs d'extension **non contrôlés**. Y mélanger des champs à
schéma **détruirait la garantie d'allowlist** : on ne pourrait plus rejeter une clé inconnue,
puisque `meta` accepte tout par construction.

**Colonnes séparées, garanties séparées.**

### Migration Alembic (additive, unique, à l'installation)

```sql
ALTER TABLE organization ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
ALTER TABLE org_unit     ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
ALTER TABLE site         ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
-- party.custom_fields existe déjà.
```

C'est une migration **normale, au déploiement** — **pas** du DDL à l'exécution déclenché par un
utilisateur. Cette distinction est **toute** la sécurité du design.

### Table `field_definition` (nouvelle)

| Colonne | Type | Note |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK **NOT NULL** | **L'énoncé formel de l'isolation** — voir §7 |
| `target` | String(60) | ex. `site.custom_fields` — restreint à un **registre opt-in** |
| `key` | String(60) | `^[a-z][a-z0-9_]{0,59}$`, noms réservés interdits |
| `type` | String(20) | un des 15 types |
| `widget` | String(30) | défaut = widget canonique du type |
| `label_en` / `label_fr` / `label_es` | Text | **obligatoires** (règle repo : toute chaîne = clé i18n) |
| `hint_en` / `hint_fr` / `hint_es` | Text | optionnels |
| `required` | Boolean | |
| `default` | JSONB | |
| `rules` | JSONB | `min`, `max`, `pattern`, `visible_if`… |
| `options` | JSONB | pour `select` / `multiselect` (libellés localisés) |
| `relation_resource` / `relation_filter` | String / JSONB | pour `relation` |
| `group` / `order` / `col_span` | String(60) / Integer / Integer | mise en page |
| `indexed` | Boolean | voir §11 |
| `index_state` | String(10) | `none` \| `pending` \| `ready` \| `failed` |
| `inherit_to_suborgs` | Boolean | voir §7 |
| `archived` | Boolean | **jamais de suppression destructive** |
| `created_at` / `updated_at` / `updated_by` | | concurrence optimiste + audit |

Contrainte : `UNIQUE(organization_id, target, key)`.

### Les schémas produit ne vont PAS en base

Ils sont déclarés **en code**, dans un registre calqué sur `default_registry()`
(`core/providers/registry.py:68-112`) — **versionnés avec le code, non éditables, non
corruptibles**. Un administrateur *remplit* `document_identity` ; il n'en *redéfinit* pas la forme.

### `cfg()` est étendu, pas remplacé

`core/providers/base.py:18` passe de 4 à 15 types et gagne `widget` / `rules` / `options` /
`group` / `order`. **Les 13 providers existants continuent de fonctionner sans modification**
(nouveaux attributs optionnels, valeurs par défaut). C'est le test de non-régression du socle.

---

## 7. Résolution scopée et héritage

**Trois règles, et elles suffisent à garantir la non-corruption inter-organisations.**

### Règle 1 — Une définition appartient toujours à une organisation

`field_definition.organization_id` est **NOT NULL**. Il n'existe **aucun champ custom global**.

Ce n'est pas une contrainte d'intégrité de plus : c'est **l'énoncé formel de l'isolation**. Aucune
ligne ne peut exister « au-dessus » des organisations, donc **aucune ne peut les traverser**.
L'isolation devient une **propriété du schéma, vérifiable par la base** — pas une promesse du code
applicatif.

Le produit livre des schémas globaux (en code) ; **l'utilisateur ne crée que du scopé**.

### Règle 2 — Une définition descend dans le sous-arbre de son organisation

Un champ défini sur l'organisation A s'applique à :

- la fiche de **A** elle-même (`target = organization.custom_fields`) ;
- **toutes ses unités et tous ses sites** — qui lui sont liés par **clé étrangère**
  (`OrgUnit.organization_id`, `Site.organization_id`). La portée est donc **structurelle**, pas
  conventionnelle ;
- **si `inherit_to_suborgs` est activé**, à ses **organisations filles**, en remontant la chaîne
  `Organization.parent_id` (`organization/models.py:50-52`) avec une **profondeur bornée** —
  même garde que le RBAC (`rbac/service.py:22`, `_MAX_INHERITANCE_DEPTH = 20`).

L'organisation B ne voit **jamais** la définition de A. Le filtre appliqué est
`visible_orgs` (`security/permission_dep.py:47-53`) — **le même filtre qui protège déjà tout le
backend**, pas un filtre spécifique qu'on risquerait d'oublier.

### Règle 3 — On hérite les *définitions*, pas les *valeurs*

Si l'organisation A définit « Numéro de convention », ses trois sites ont chacun **leur propre
valeur**, dans leur propre ligne. **Aucune valeur ne coule d'un niveau à l'autre.**

> L'héritage de **valeurs** (le pied de page du siège hérité par la succursale qui n'en a pas
> défini) est le travail de **SP2** sur `document_identity`, en remontant `OrgUnit.path`. C'est un
> problème **différent**. Les confondre produit le bug le plus vicieux de ce genre de système :
> ne plus savoir, devant une valeur vide, si elle est **absente** ou **héritée du parent**.

### Cache

Le schéma résolu est mis en cache (clé `organization_id + target`), invalidé à chaque écriture de
définition. Sans cache, chaque ouverture de formulaire déclencherait une requête — intenable avec
100+ agents simultanés. Le cache **fail-closed** (`CACHE_REQUIRED`) est déjà en place dans le repo.

---

## 8. API

| Méthode | Route | Permission | Rôle |
|---|---|---|---|
| `GET` | `/api/v1/schema/{target}?organization_id=…` | lecture de l'entité cible | Schéma résolu (code + base + héritage) → `FieldSpec[]` |
| `GET` | `/api/v1/admin/field-definitions` | `fields.manage` | Liste (keyset, tri, filtres — standard repo), scope-filtrée |
| `POST` | `/api/v1/admin/field-definitions` | `fields.manage` | Créer (enforce sur le scope de la **cible**) |
| `PUT` | `/api/v1/admin/field-definitions/{id}` | `fields.manage` | Modifier — **`If-Match`** obligatoire |
| `POST` | `/api/v1/admin/field-definitions/{id}/archive` | `fields.manage` | Archiver (réversible) |
| `POST` | `/api/v1/admin/field-definitions/{id}/purge` | `fields.manage` | **Purge définitive** — explicite, auditée, distincte |
| `POST` | `/api/v1/admin/field-definitions/{id}/index` | `fields.manage` | Demander l'indexation (job async, §11) |

Les écritures des **entités métier** (Organization / OrgUnit / Site / Party) acceptent désormais
`custom_fields`, **filtré par l'allowlist du schéma résolu**. Toute clé non déclarée → **422**.

---

## 9. Interface utilisateur

### Écran A — « Champs personnalisés » (le Studio)

Nouvelle entrée de navigation, groupe **Système**, gardée par `fields.manage`
(UI permission-driven : masquée si absente).

- **Liste** : `DataGrid` standard (tri colonne, filtres colonne, pagination avec total, densité,
  états vide/chargement/erreur), filtrée par **entité cible** et **scopée à l'organisation**.
- **Création / édition** : un **`RecordForm`** (§11bis, obligatoire). *Le formulaire de création
  de champ est lui-même rendu par le composant générique — le socle se mange lui-même.*
  Champs : clé, libellé en/fr/es, type, widget, obligatoire, valeur par défaut, aide, règles,
  options, groupe, ordre, largeur, `inherit_to_suborgs`, `indexed`.
- **Aperçu live** à droite : le **vrai `RecordForm`** rend le contrôle tel qu'il apparaîtra.
  Pas de simulation.
- **État d'index** affiché (`pending` / `ready` / `failed`) — un champ non `ready` est
  explicitement signalé comme **non triable**, jamais silencieusement lent.
- Layout **master-detail / split-view** (règle repo), deep-linkable.

### Écran B — les formulaires métier, enrichis

Les fiches **Organisation / Unité / Site / Tiers** affichent nativement les champs custom, sous une
section **« Informations complémentaires »** (issue de `FieldSpec.group`).

**Aucune page à réécrire** : elles consomment déjà `FieldDef[]` (`useOrgFields`, `useSiteFields`,
`usePartyFields`) — elles en recevront simplement davantage, servis par le serveur.

### Écran C — la fin des JSON bruts

`document_identity`, `Organization.settings` et la page `/config` deviennent de **vrais
formulaires**, alimentés par les schémas déclarés en code.

**Contraintes transverses** (règles du repo, non négociables) : responsive mobile→desktop ·
a11y AA · i18n en/fr/es sur **toute** chaîne · TanStack Query (optimistic + rollback) ·
`If-Match` · 422→champ / 409→reload · coque fixe, seule la data défile.

---

## 10. Sécurité et RBAC

**Nouvelle permission** : `fields.manage`, de **niveau protégé** (au rang de
`settings.manage_protected`, `api/admin_settings.py:41`). Écriture **enforcée sur le scope de la
cible**, pas sur celui de l'appelant (règle repo). Toute mutation de définition → `audit.record`.

### Le schéma est l'allowlist

À l'écriture d'une entité, `custom_fields` est filtré aux clés **déclarées, non archivées et
visibles pour cette organisation**. Une clé inconnue → **422 explicite**. **Jamais un `ignore`
silencieux** (règle anti-échec-silencieux du repo).

### Quatre gardes sur la définition d'un champ

1. **Noms réservés** — la liste est **dérivée par introspection SQLAlchemy** des colonnes réelles
   du modèle cible. Jamais codée en dur : une liste codée en dur dérive dès la première migration.
2. **Secrets** — la garde `_SECRET_INDICATORS` existante (`api/admin_settings.py`) s'applique :
   une clé ressemblant à un secret est **refusée à la définition** ; une valeur secrète en clair
   est **refusée à l'écriture**.
3. **Types à risque encadrés** :
   - `richtext` → **sanitization allowlist serveur à l'écriture ET au rendu** (balises et
     attributs autorisés explicitement ; ni `script`, ni `on*`, ni `javascript:`, ni `style`
     arbitraire). C'est le point de sécurité n°1 de SP1.
   - `file` / widget `image` → transite **obligatoirement** par `/api/v1/assets` (déjà : sniff
     magic-bytes, SVG interdit, cap 5 Mio — `api/assets.py:39`).
   - `relation` → **restreint aux ressources déclarées** dans un registre. Jamais une URL libre
     (SSRF).
4. **Concurrence optimiste** (`If-Match` → 409) sur les définitions, comme partout ailleurs.

### Logique conditionnelle

`visible_if` / `required_if` sont évaluées **serveur ET client**. Le serveur tranche.

---

## 11. Échelle et indexation

Le repo cible **des millions d'utilisateurs et 100+ agents simultanés**. Les contraintes suivantes
ne sont pas des optimisations, ce sont des conditions de viabilité.

### Plafonds durs

- **50 champs** par `(organisation, cible)`.
- **10 champs indexés** par `(organisation, cible)`.

Dépassement → **refus explicite (422)**. Sans cette borne, **une seule organisation peut saturer la
base pour toutes les autres**. Odoo ne pose pas cette limite ; nous si.

### Un champ n'est triable/filtrable que s'il est indexé

L'index créé est **partiel et isolé à l'organisation** :

```sql
CREATE INDEX CONCURRENTLY ix_site_cf_convention_no
  ON site ((custom_fields->>'convention_no'))
  WHERE organization_id = '…';
```

→ **additif**, **sans verrou**, **invisible pour les autres organisations**.

### Le type détermine l'expression d'index

JSONB ne stocke que du texte : indexer sans **cast typé** produirait un tri **lexicographique**
(`"10" < "9"`) — un bug silencieux et redoutable. L'expression est donc **dérivée du type** :

| Type | Expression indexée |
|---|---|
| `string`, `text`, `select`, `relation` | `(custom_fields->>'k')` |
| `number`, `decimal` | `((custom_fields->>'k')::numeric)` |
| `money` | `((custom_fields->'k'->>'amount')::numeric)` |
| `boolean` | `((custom_fields->>'k')::boolean)` |
| `date` | `((custom_fields->>'k')::date)` |
| `datetime` | `((custom_fields->>'k')::timestamptz)` |
| `time` | `((custom_fields->>'k')::time)` |
| `richtext`, `multiselect`, `file`, `json` | **non indexables** — refus explicite de `indexed` |

Le **même cast** est appliqué dans la clause `ORDER BY` / `WHERE` générée, sinon Postgres n'utilise
pas l'index. **C'est ce que vérifie le test `EXPLAIN` du §13.**

Une valeur non castable (JSONB mal formé hérité) ferait échouer la création d'index → l'état passe
à `failed`, il est **affiché**, et le champ reste non triable. Aucun échec silencieux.

### Contrainte technique assumée

`CREATE INDEX CONCURRENTLY` **ne peut pas s'exécuter dans une transaction**. La création d'index
est donc un **job asynchrone**, avec un état (`index_state`) **affiché dans l'UI**.

Un champ dont l'index n'est pas `ready` **n'est pas proposé au tri**. Il n'est pas silencieusement
lent : il est **explicitement indisponible**.

### Whitelist de tri/filtre

La whitelist existante (`ENGINEERING_STANDARDS`, tri sur colonnes autorisées) **s'étend aux clés
custom `indexed` + `ready`, et à elles seules**. Toute autre clé → **422**.

**Jamais de scan séquentiel silencieux sur des millions de lignes.**

### Dialecte

Indexation **Postgres uniquement**. Sous SQLite (tests), dégradation propre — la règle « SQL
Postgres gardé par dialecte » existe déjà dans le repo.

### Suppression = archivage

`archived = true` retire le champ des formulaires ; **les valeurs restent dans le JSONB**.
Réactivable. Une purge définitive existe, mais **explicite, auditée et distincte**.
**Un clic ne détruit pas des années de données.**

---

## 12. Migration des JSON bruts

**Principe : aucune migration de données.** Le JSON déjà stocké **est** la forme qu'on déclare.
On migre la **validation et l'interface**, pas le contenu.

### Règle de non-destruction (non négociable)

Le formulaire généré n'écrit que les clés **déclarées**, **en fusion** (merge), jamais en
remplacement. Une clé pré-existante non déclarée est **conservée intacte** et affichée en lecture
seule dans un repli « Champs non reconnus ». **Jamais supprimée en silence.**

En revanche, l'API **rejette (422)** toute clé non déclarée **arrivant dans une requête**.

> **Entrée stricte, existant préservé.** C'est ce qui permet d'imposer une allowlist sur des
> données jamais validées auparavant sans déclencher une avalanche de 422 sur des lignes
> historiques.

### Ordre (chaque étape livrable et testable seule)

| | Cible | Pourquoi cet ordre | Risque |
|---|---|---|---|
| **M0** | Socle : `cfg()` étendu, `FieldSpec`, `/api/v1/schema/{target}`, générateurs pydantic + zod, `RecordForm` accepte `rules` / `widget` / `relation` | Rien de visible ne change. **Filet : les 13 providers existants doivent fonctionner à l'identique.** | Nul |
| **M1** | **Providers** (déjà schema-driven) | Bascule du **seul consommateur déjà en place** → le socle est prouvé end-to-end **avec un oracle** (le comportement actuel) et **zéro donnée en jeu**. | Très faible |
| **M2** | **`organization.document_identity`** | Premier JSON brut tué. **Déblocage de SP2.** Structure plate → aucune capacité nouvelle requise. | Faible |
| **M3** | **`organization.settings`** + page `/config` (formulaire par namespace) | Plus large, mais le socle est éprouvé par M1/M2. | Moyen |
| **M4** | **`custom_fields`** : table `field_definition` + colonnes + Écran A | **Rien à migrer** — naissance vierge → **allowlist stricte dès le premier jour**, sans clause de grand-père. | Faible |

### Cas `operating_hours`

Structure **répétable** (7 jours × plages) → **incompatible avec un schéma plat**, et aujourd'hui
**incohérente en production** (deux formes coexistent, cf. §1).

**Décision : widget dédié `weekly_hours`** sur le type `json`. Un contrôle sur mesure, une forme
**enfin définie une bonne fois**, sans attendre la machinerie générique des groupes répétables (v2).
La forme canonique retenue est celle du **test backend** — `{"monday": {"open": "08:00", "close":
"16:00"}, …}` (`tests/test_modules_org_location.py:33`) — car c'est la seule attestée par du code
exécuté. L'aide i18n contradictoire (`fr.json:305`) est corrigée en conséquence.

### Cas `meta` / `metadata`

**Exclusion assumée et documentée.** Sacs opaques → restent en `json` (widget `raw`).

---

## 13. Stratégie de tests

> Les tests ne « couvrent » pas ce design : ils **sont** la garantie d'isolation demandée. Une
> promesse d'isolation n'a de valeur que si **un test échouerait si on la cassait**.

### Backend — pytest

- **Isolation multi-organisation** *(le test central, permanent)* : l'organisation A définit un
  champ ; un compte de l'organisation B ne le voit **pas** dans `/schema`, ne peut **pas** l'écrire,
  ne peut **pas** le lire.
- **Héritage** : champ défini sur A → visible sur ses unités et sites ; `inherit_to_suborgs` →
  visible sur l'organisation fille ; profondeur bornée respectée ; **aucune fuite latérale** vers
  une organisation sœur.
- **Descripteur** : table-driven sur les 15 types × widgets → le modèle pydantic généré accepte /
  rejette correctement.
- **Allowlist** : clé non déclarée → **422** ; clé archivée → 422 ; clé réservée (introspection) →
  refus à la définition.
- **Secrets** : clé `api_key` / `password` refusée à la définition ; valeur secrète en clair
  refusée à l'écriture.
- **`richtext`** : `<script>`, `on*=`, `javascript:` → strippés à l'écriture **et** au rendu.
- **Plafonds** : 51ᵉ champ → refus ; 11ᵉ champ indexé → refus.
- **Tri / filtre** : clé non indexée → 422 ; clé `indexed` mais `index_state ≠ ready` → 422 ;
  clé `ready` → tri correct.
- **`visible_if` / `required_if`** : champ masqué-mais-obligatoire **non envoyé** → accepté ;
  **envoyé alors qu'il devrait être masqué** → rejeté.
- **Non-destruction** : clé pré-existante non déclarée dans `document_identity` → **survit** à un
  `PUT` du formulaire.
- **Non-régression providers** : les 13 providers built-in rendent exactement le même schéma
  qu'avant M0.
- **Concurrence** : `If-Match` → 409. **Audit** : toute mutation de définition enregistrée.
  **Migration Alembic idempotente.**

### Frontend — Vitest (`.test.ts` purs, pas de render-test — règle repo)

- `fieldSpecToFieldDef` : 15 types × widgets → le bon `FieldDef` (table-driven).
- Compilation `rules` → zod : chaque règle produit le bon validateur.
- Évaluation `visible_if` / `required_if` (fonction pure).
- `buildPayload` avec champs custom → `custom_fields` correct.

### Playwright — e2e (preuve visuelle, règle repo)

- Créer un champ dans l'Écran A → il apparaît sur la fiche Site → saisir une valeur → recharger →
  **valeur persistée**.
- Un utilisateur sans `fields.manage` ne voit **ni l'écran ni le bouton**.
- Capture avant/après du formulaire `document_identity` : **JSON brut → vrai formulaire**.

### Performance — le test qui valide ou invalide le design

100 000 lignes, tri sur un champ custom indexé → **`EXPLAIN` doit montrer l'usage de l'index**, pas
un *seq scan*. **Si ce test échoue, le modèle de stockage est faux — et il faut le savoir avant la
production.**

---

## 14. Risques

| Risque | Gravité | Mitigation |
|---|---|---|
| **XSS via `richtext`** | **Critique** | Sanitization allowlist **serveur**, à l'écriture **et** au rendu. Tests dédiés. Point de sécurité n°1 — revue `security-auditor` obligatoire. |
| Contournement de `required_if` | Élevé | Évaluation **serveur** faisant autorité. Test dédié. |
| Fuite inter-organisations | **Critique** | `organization_id NOT NULL` + `visible_orgs` (filtre déjà universel) + **test d'isolation permanent**. |
| Saturation de la base par une organisation | Élevé | Plafonds durs (50 / 10) + index partiels par organisation. |
| Tri sur champ non indexé → seq scan | Élevé | Whitelist stricte : `indexed` + `ready` **uniquement**. Test `EXPLAIN`. |
| Régression sur les 13 providers | Moyen | M1 les migre **avec le comportement actuel comme oracle** ; test de non-régression avant tout autre chantier. |
| Perte de données à la migration | Élevé | **Merge, jamais remplacement.** Clés inconnues préservées. Archivage ≠ purge. Test dédié. |
| Explosion du périmètre | Moyen | Groupes répétables, champs calculés, champs globaux : **explicitement hors périmètre** (§2). |

---

## 15. Références au code existant

**À réutiliser (ne rien réécrire) :**

- `packages/web/src/components/ui/record-form.tsx` — le formulaire générique (§11bis). **Seule
  modification** : accepter `rules` / `widget` / `relation`.
- `packages/web/src/modules/providers/fields.ts:14-22` — `configFieldToFieldDef()`, à généraliser
  en `fieldSpecToFieldDef()`.
- `packages/backend/app/core/providers/base.py:18` — `cfg()`, à étendre.
- `packages/backend/app/core/providers/registry.py:68-112` — `default_registry()`, modèle du
  registre de schémas produit.
- `packages/backend/app/security/permission_dep.py:47-53` — `visible_orgs()`, **le** filtre
  d'isolation.
- `packages/backend/app/rbac/scope.py` / `rbac/repository.py` — résolution de scope, `unit_path`.
- `packages/backend/app/api/assets.py` — upload validé (à étendre aux documents pour SP2).
- `packages/backend/app/api/admin_settings.py` — `_SECRET_INDICATORS`, `enforce_if_match`,
  `row_etag`.

**À créer :**

- `packages/backend/app/core/schema/` — `FieldSpec`, registre produit, résolveur, générateur
  pydantic, gardes.
- `packages/backend/app/models/field_definition.py` + migration Alembic.
- `packages/backend/app/api/schema.py` + `api/admin_field_definitions.py`.
- `packages/web/src/modules/fields/` — Écran A (liste, RecordForm, aperçu live).
- `packages/web/src/lib/schema-to-zod.ts` — compilation des `rules`.

---

## 16. Ce que SP1 débloque

- **SP2 — Moteur documentaire & Studio** : `document_identity` devient un vrai formulaire, et
  l'identité de l'émetteur (nom, code, logo, mentions légales par département / service /
  succursale) devient configurable **sans JSON**. C'est le prérequis direct du besoin initial :
  *« chaque entité peut avoir son propre nom ou code sur le rapport »*.
- Le type `money` et le type `file` sont **posés d'avance** pour la facture et les pièces jointes
  documentaires.
- La discipline « schéma = allowlist » s'étend mécaniquement à toute nouvelle ressource.
