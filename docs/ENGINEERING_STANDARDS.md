# Engineering Standards — Facil Framework

Référentiel d'implémentation **obligatoire** (backend + frontend), aligné sur les
pratiques des grands ERP/plateformes (SAP Fiori, Salesforce, Odoo, ServiceNow,
Workday, Keycloak). Objectif : configuration et actions utilisateur **fluides,
sûres et scalables** (cible 1M utilisateurs, 100+ agents simultanés).

Ces règles **complètent** `CLAUDE.md` (qui en contient le résumé impératif) et
s'appliquent à tout nouveau code. Toute exception doit être justifiée dans la PR.

## 1. Contrat de liste (collections) — le cœur des écrans d'admin

Toute route qui renvoie une collection DOIT exposer un contrat uniforme :

- **Pagination — deux contrats selon l'échelle de la collection** :
  - **Keyset / curseur — DÉFAUT pour toute liste scale-sensible** (volume potentiel > 10⁴) :
    `?cursor=<token>&limit=<≤200>&sort=&filter=` → `{"items":[...], "next_cursor": str|null,
    "count": int, "capped": bool}`. Préc/Suiv (forward backend + pile de curseurs côté front via
    `useServerTable`), **count plafonné** (« N+ » au-delà de `COUNT_CAP=1000`) — **pas de `COUNT(*)`
    exact ni d'`OFFSET` deep-scan**. NULL-safe (`NULLS LAST`/`FIRST` explicite, parité PG/SQLite).
    Helper `app.api.list_query.keyset_page` ; **index composite `(tri, id)` requis** (migration 0014).
    Front : `DataGrid mode="cursor"`. *(Listes admin core en keyset : accounts, organizations, sites,
    roles, federation.)*
  - **Offset — petites listes bornées / fabrique CRUD interne** : `?limit=<≤200>&offset=&sort=&filter=`
    → `{"items":[...], "total": N, "limit", "offset"}`. Acceptable quand le volume reste borné ;
    au-delà, migrer en keyset. Helper `paginated` ; `DataGrid mode="offset"` (défaut). Exports = offset (cap `EXPORT_CAP`).
- `sort` : `champ` (asc) ou `-champ` (desc), **whitelist** de champs triables (**422** si hors whitelist).
- `filter` : filtres structurés par champ (`eq`, `contains`, `in`, plages dates) —
  pas seulement une recherche texte globale.
- **Scope RBAC** : filtrer par `visible_orgs(principal, perm)` (isolation tenant),
  jamais renvoyer hors périmètre.
- **Jamais de liste non bornée** ni de cap silencieux : si on tronque, on le **signale**
  (log backend + indication UI). Le `count` keyset plafonné « N+ » est un cap **assumé et affiché**, pas silencieux.

## 2. Sécurité & RBAC (backend)

- Chaque endpoint **déclare une permission** (`resource.verb`) ; lectures =
  scope-filtrées, écritures = `enforce` sur le scope **de la cible** (body/record),
  jamais le path seul. Wildcards `*` / `resource.*`.
- Le **frontend n'autorise jamais** : il *reflète* (masque/désactive) ; le backend tranche.
- **Break-glass** (admin-token) : seul bypass RBAC, tracé (audit), fail-closed si non configuré.
- **Auth** : statut/`is_active` enforced sur **tous** les chemins (natif ET fédéré) ;
  suspension/désactivation → **révocation immédiate des sessions**.
- **Secrets** jamais en clair dans `config` jsonb → `resolve_secret` ; dégradation propre si absent.
- Pas d'oracle d'énumération (réponses uniformes sur identifiants inconnus/bloqués).

## 3. Audit & traçabilité

Toute **mutation sensible** (create/update/delete/status/assign/révoque/config/branding)
écrit une ligne d'audit (`audit.record`, acteur + cible + détail). L'audit ne doit
jamais casser le flux métier (best-effort, log si échec).

## 4. Concurrence optimiste (mutations)

Les ressources mutables exposent `updated_at`/`version`. Les `PUT/PATCH` acceptent
un `If-Match`/version attendue et renvoient **409** en cas de conflit (write-skew),
au lieu d'un dernier-écrivain-gagne silencieux. (Pattern SAP/Salesforce.)

## 5. Opérations en masse (bulk)

- Endpoints bulk **transactionnels** (tout-ou-rien) **ou** rapport par item
  (`{updated: [...], errors: [...]}`), **scope-enforced par item**, **audités**, **bornés** (≤ 500 ids).
- Idempotents quand c'est possible ; jamais de boucle N+1 d'appels unitaires côté client.

## 6. Erreurs, validation, idempotence

- Forme d'erreur cohérente (`{"detail": ...}`), bons statuts (400/401/403/404/409/422).
- **Pydantic** systématique : bornes de longueur, formats (regex légère plutôt que
  nouvelle dépendance lourde sauf justification), valeurs énum validées.
- **Seeds & migrations idempotents** ; SQL spécifique Postgres **gardé par dialecte**
  (no-op SQLite). **Build = CI uniquement** (jamais manuel).
- **Soft-state** (`is_active`/`status`) plutôt que hard-delete là où l'audit/restauration comptent.

## 7. Performance & scale (backend)

- Index adaptés aux requêtes réelles (ex. `pg_trgm` GIN pour recherche `ILIKE '%x%'`).
- Pagination/scope **dans SQL**, pas en mémoire. Cache (Redis) pour l'état partagé multi-réplica.
- Penser 1M lignes : pas de `COUNT(*)` non borné sur chemin chaud sans index/estimation.

## 8. Frontend — DataGrid (listes)

Une liste de niveau ERP fournit, **côté serveur** :

- **Tri par colonne** (clic sur l'en-tête, indicateur asc/desc).
- **Filtres par colonne** (texte, énum/statut, date) + recherche globale.
- **Pagination** : keyset Préc/Suiv + count plafonné « N+ » (`mode="cursor"`, défaut scale) ou
  offset « 1-50 sur N » (`mode="offset"`, petites listes). Hook `useServerTable` = état + pile de curseurs.
- **Densité** (confort/compact), en-têtes **sticky**, **virtualisation** au-delà de ~100 lignes.
- États **vide / chargement (skeleton) / erreur** explicites.
- **Multi-sélection** + **barre d'actions contextuelle** (bulk) quand des actions de masse existent.
- Export CSV/Excel pour les vues de données (quand pertinent).

Composant **générique réutilisable** (pas de réimplémentation par page).

## 9. Frontend — Master-detail / split-view

- **Dialogs** : uniquement create rapide / confirmation / action courte.
- **Configuration riche et répétée** (rôles+permissions, agent+rôles, branding) :
  **layout 2-panneaux** (liste à gauche, détail/éditeur à droite), **deep-linkable**
  (`/roles/{id}`), garde le contexte, pas de piège modal. (Fiori FCL / Salesforce Split View.)

## 10. Frontend — UI guidée par les permissions

- Masquer/désactiver nav **et actions** selon les permissions effectives
  (`/me/permissions` + `hasPerm`, miroir des wildcards serveur). Jamais de lien/bouton mort.
- La sécurité reste backend ; l'UI ne fait que réduire le bruit.

## 11. Frontend — données, état, formes

- **TanStack Query** : cache, dédup, **optimistic update + rollback**, invalidation ciblée.
- **Formulaires** : `react-hook-form` + `zod` (validation = même forme que l'API). Toasts d'issue.
- **BFF** : tokens en cookies httpOnly (zéro token en JS) ; intercepteur **401 → /login**.

## 11bis. Création / édition de records — formulaire ERP-grade (OBLIGATOIRE)

Référence : Salesforce Lightning *record forms* · Odoo *form views* (génériques, metadata-driven).
**Interdiction des formulaires ad-hoc réécrits par page.** Un **composant `RecordForm` réutilisable**
(définition de champs → rendu + validation + save), exactement comme le DataGrid l'est pour les listes :
toute création/édition passe par lui ; un champ personnalisé (`field_definition`, F.6) s'y rend
automatiquement. C'est la règle qui empêche les régressions form-par-form.

Contrat **obligatoire** de toute création/édition :
- **Rendu adaptatif** : record simple → **slide-over / quick-create** ; record riche → **page plein écran**
  (header + onglets + related lists). Même `RecordForm`, deux conteneurs.
- **Validation défense-en-profondeur** : **client `react-hook-form` + `zod`** (erreurs inline immédiates,
  miroir des contraintes API) **ET** serveur (pydantic). Jamais l'un sans l'autre.
- **Erreurs serveur mappées** : **422 → erreurs par champ** ; **409** (conflit) → message + reload ;
  401 → login ; jamais d'erreur avalée (toast form-level + erreur champ-level).
- **Concurrence optimiste** : l'édition envoie **`If-Match`** (ETag du GET) → 409/412 géré (recharge la
  version courante). Obligatoire dès qu'un record est éditable par plusieurs acteurs.
- **Actions** : **Save**, **Save & New** (création), **Cancel** avec **garde « modifications non
  enregistrées »** (dirty-check avant fermeture/navigation). **Anti double-submit** (disabled + pending).
- **Permission-driven** : create/edit/delete masqués/désactivés selon `hasPerm` (le backend tranche).
- **Pickers relationnels** : combobox **recherche serveur** (jamais de `<select>` cap 200) + **inline-create**
  (« Créer '<terme>' », Odoo *Create & Edit*).
- **A11y AA · i18n** (toute chaîne = clé) · **TanStack Query** (optimistic + rollback + invalidation au save) ·
  toasts d'issue · états loading/disabled.
- **Import en masse** : pour les entités à fort volume, fournir l'**import CSV** (validation **par ligne**,
  rapport d'erreurs, **jamais de drop silencieux**) en complément du formulaire unitaire.

**Sécurité** : la validation client ne remplace **jamais** la validation serveur (RBAC + pydantic + audit) ;
elle ne fait que guider et réduire les allers-retours. Auth = cookies httpOnly via le BFF, zéro secret en JS.

⚠️ **Dette connue (à résorber)** : `RefForm` (admin référentiels) et les dialogs create écrits à la main ne
respectent pas encore tout ce contrat (pas de `zod`, pas d'`If-Match`) → **migrer vers `RecordForm`**.

## 12. Frontend — ergonomie, a11y, i18n, perf, thème

- **Coque fixe** (sidebar/topbar/filtres/barre d'actions ne défilent pas) ; **seule la zone
  data défile** ; vues d'aperçu sans-scroll. Priorité densité/sans-scroll.
- **A11y AA** : primitives Radix/shadcn, ARIA, clavier, contraste.
- **i18n** : `next-intl`, **toute** chaîne visible est une clé (en/fr/es), zéro texte en dur.
- **Perf** : RSC + code-split par route, budget JS < ~150KB/route, `next/image`,
  **cache des fetch serveur** (`revalidate` + `tags`, invalidation explicite au save).
- **Thème** : variables CSS pilotées par `branding.*` (white-label, dark mode).

## 13bis. Parité backend ⇄ frontend (couverture intégrale)

Le frontend doit refléter **fidèlement et exhaustivement** le contrat backend.

- Pour chaque ressource, l'UI couvre **toutes** les capacités exposées : opérations
  (list / get / create / update / delete), **actions métier**, **transitions d'état**,
  **tous les champs** (lecture **et** écriture), tri / filtres / pagination, et tous les
  états/erreurs (401 / 403 / 404 / 409 / 422).
- **Aucune capacité backend orpheline** (un endpoint/champ sans accès UI), **aucun champ
  d'API** ni affiché ni éditable sans raison, **aucune UI** ne référence un endpoint/champ
  inexistant.
- **Exclusions admises uniquement si délibérées et documentées** — surfaces non destinées
  à l'utilisateur final : break-glass admin-token, `/health`, métriques, SCIM côté IdP,
  endpoints internes/bulk techniques.
- **Livraison couplée** : tout ajout/évolution backend livre l'UI correspondante **dans le
  même lot** ; au démarrage de tout écran, vérifier la couverture complète du contrat (et
  réciproquement). La **fabrique CRUD** (§1/§8) est le moyen privilégié de garantir cette
  parité sans dérive pour les nouveaux modules.

## 13. Transverse

- **Tests = vraie validation** (pytest / Vitest / Playwright), **gate CI** ; pas d'auto-checklist.
- **Réutilisation d'abord** (primitives UI, hooks, repos) ; DRY ; pas de duplication de patron.
- Commits **conventionnels** ; **push = accord explicite** ; remote vérifié (`facil-framework`).
- Documenter toute limite assumée (cap, no-retry, échantillonnage) — pas de troncature silencieuse.

## État d'application (2026-06-17)

Déjà conforme : RBAC scope-aware, audit, auth status+revoke, config-store en couches,
providers pluggables, BFF httpOnly, UI permission-driven (nav), pagination serveur (partielle),
cache branding, `pg_trgm`, primitive `Select`.

À livrer (chantier ERP-grade, priorité **bulk → DataGrid → master-detail**) :
contrat de liste complet (sort/filter/total), DataGrid générique, bulk transactionnel,
concurrence optimiste, export/saved views, formes rhf+zod sur les écrans existants.
