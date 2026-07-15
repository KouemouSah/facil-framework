# D3 — Amorçage serveur des permissions + squelettes DRY — Design

> **Sous-projet** : dette SP1 **D3**, reformulée. Branche **`fix/permission-ssr-popin`** depuis `develop`, mergeable seule.
> **Date** : 2026-07-15.

## 0. Correction de diagnostic (important)

Le doc de dettes (`2026-07-14-sp1-debts-d1-d5.md` §D3) décrivait D3 comme une **erreur d'hydratation React** :
« le SSR ne rend pas le bouton, le client le rend → erreur d'hydratation ». **C'est factuellement faux**,
vérifié par lecture du code **et** reproduction :

- `providers.tsx` monte react-query **sans déshydratation/prefetch SSR** → `usePermissions().can()` renvoie
  `false` au SSR **et** au 1er rendu client (query non résolue). Un bouton `{can && <Button/>}` est donc **caché
  des deux côtés** au 1er rendu → le HTML serveur et le 1er rendu client **coïncident** → **pas de mismatch**.
- Reproduction (Playwright, `/providers`, admin) : **2 boutons au rendu initial → 25 après 4 s**, et **aucun**
  warning/erreur console (aucun « Hydration failed / did not match »).

Le vrai symptôme est un **pop-in** : l'UI permission-gated (nav de la coque incluse) est absente du HTML serveur
et surgit quand les queries client (`/auth/me`, `/auth/me/permissions`, …) résolvent. Effet : flicker, CLS, et un
bref « flash de capacité réduite » (un admin voit un instant moins d'actions qu'il n'en a).

Conséquence sur les livrables : le test de validation n'est **pas** « zéro warning d'hydratation » (il n'y en a
pas — ce serait un test vide), mais « **l'UI gardée est présente dans le HTML SSR pour un user qui a la
permission, absente sinon** ».

## 1. Objectif & non-objectifs

**Objectif** : que l'UI dépendante des permissions soit **correcte dès le HTML serveur** (pas de pop-in des
actions), via un amorçage serveur des permissions/session ; plus une primitive de squelette réutilisable pour le
contenu réellement asynchrone.

**Non-objectifs (assumés)** :
- Pas de chasse au warning d'hydratation (il n'y en a pas).
- Pas de prefetch serveur des **données métier** page par page (les listes/cartes restent client-fetched, avec
  squelette). Ce serait un chantier distinct, page-par-page, hors périmètre.
- **Aucun endpoint / capacité backend nouveau** (cf. §6, parité).

## 2. Pattern A — permissions/session résolues au serveur (déshydratation react-query)

**Où** : `packages/web/src/app/(app)/layout.tsx` (Server Component ; a déjà accès au cookie et fait la garde
`redirect("/login")`).

**Nouveau helper serveur lecture-seule** (`lib/server/backend.ts`) — nécessaire car `backendProxy` tente un
refresh + `setAuthCookies()` sur 401, or **muter un cookie est interdit dans un Server Component** (Next :
« Cookies can only be modified in a Server Action or Route Handler »). Le helper :
- forwarde le cookie `facil_at` (via le `rawCall` interne déjà présent) ;
- renvoie le JSON parsé sur 2xx, **`null` sur 401/tout échec** ;
- **ne mute aucun cookie** (pas de refresh en RSC).

**Amorçage** : le layout précharge **en parallèle** `/api/v1/auth/me` et `/api/v1/auth/me/permissions`, puis
amorce un `QueryClient` serveur avec les **mêmes clés** que les hooks :
- `["session"]` ← `{ authenticated: true, ...me }` (forme identique à celle que la route `/api/auth/session`
  renvoie et que `parseSession`/`useSession` attendent — `/auth/me` renvoie `{ break_glass, account }` sans
  `authenticated`, qu'on ajoute) ;
- `["my-permissions"]` ← `{ permissions: [...] }`.

Puis `dehydrate(queryClient)` → `<HydrationBoundary state={…}>` autour de l'`AppShell` (children).

**Les hooks `useSession`/`usePermissions` restent inchangés** : ils trouvent la donnée dans le cache dès
l'hydratation → nav + actions gardées présentes dans le 1er paint.

**Fail-safe** : si un prefetch renvoie `null` (access token expiré/absent au SSR), on **n'amorce pas** cette clé →
le hook client fetch comme aujourd'hui (le pop-in réapparaît pour ce seul rendu, **jamais de crash**). Le refresh
se fait alors via la Route Handler `/api/auth/session`, qui, elle, a le droit de muter les cookies. La garde
`redirect("/login")` du layout reste inchangée et s'exécute avant le prefetch.

## 3. Pattern B — primitive `Skeleton` DRY

- **Nouveau** `packages/web/src/components/ui/skeleton.tsx` : primitive pure (bloc `animate-pulse`, theme-aware
  via tokens `bg-muted`), zéro logique.
- **Câblage dans les surfaces partagées** pour l'état de chargement des **données** : `Card` (corps),
  `RecordSurface`, `detail-panel`. Le **DataGrid a déjà** ses états vide/load/erreur → on s'aligne dessus, on ne
  le duplique pas.
- Les pages en héritent, **zéro travail par page**.
- Portée réelle réduite par le Pattern A : la coque et les actions ne « chargent » plus (amorcées serveur) ; B ne
  concerne que le contenu réellement async (lignes de liste, corps de carte, panneau de détail).

## 4. Flux de données

**SSR** : `(app)/layout` lit le cookie → helper lecture-seule → `me` + `perms` → `dehydrate` → le HTML contient la
nav + les actions gardées **correctes** (pour ce principal). **Client** : hydrate avec le cache amorcé → **aucun
pop-in** perms/session ; les queries de données affichent un `Skeleton` jusqu'à résolution.

## 5. Tests (le vrai test, pas « zéro warning »)

**Pattern A — e2e Playwright (preuve du HTML SSR réel)** :
- Récupérer le **HTML SSR** de `/providers` (fetch avec cookie d'auth) :
  - **admin** → l'action gardée (« edit routing », gate `settings.manage`) **EST présente** dans le markup serveur ;
  - **compte low-priv** (`member`, sans la perm) → elle **est ABSENTE**.
- Check « pas de pop-in » : le bouton gardé est présent au `domcontentloaded` (pas 4 s plus tard) — l'inverse
  exact du symptôme reproduit (2→25). Compte low-priv : réutilise le seed CI existant (`member`,
  `e2e-readonly@x.com`) ; en local, équivalent créé à la volée.

**Pattern A — unit** : le helper lecture-seule renvoie `null` sur 401 **sans muter de cookie** (fail-safe
mutation-proof).

**Pattern B — vitest** : les surfaces partagées rendent `Skeleton` en état loading.

## 6. Parité backend ⇄ frontend

**D3 n'ajoute AUCUNE capacité backend.** Il consomme uniquement `/api/v1/auth/me` et
`/api/v1/auth/me/permissions` — **déjà** consommés côté client par `useSession`/`usePermissions`. Le helper
serveur lecture-seule et la primitive `Skeleton` sont **100 % frontend**. Donc : **zéro endpoint orphelin**,
**zéro UI vers un endpoint inexistant**. La règle de parité est satisfaite **par construction**.

## 7. Isolation & nommage

- Branche **`fix/permission-ssr-popin`** depuis `develop`, mergeable seule (le nom d'origine
  `fix/ssr-permission-hydration` décrivait un bug d'hydratation inexistant).
- Ne pas mélanger avec d'autres dettes.

## 8. Découpage (pour le plan)

1. Helper serveur lecture-seule + son test unit (fail-safe).
2. Amorçage react-query dans `(app)/layout` (prefetch me+perms, dehydrate, HydrationBoundary).
3. e2e Pattern A (SSR admin/low-priv + anti-pop-in).
4. Primitive `Skeleton` + test vitest.
5. Câblage Skeleton dans `Card`/`RecordSurface`/`detail-panel`.
6. Gate finale : `tsc --noEmit`, vitest, e2e ; revue parité + §11bis.
