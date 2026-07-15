# D3 — Amorçage serveur des permissions + squelettes DRY — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supprimer le pop-in de l'UI permission-gated en amorçant côté serveur (RSC) le cache react-query des permissions/session, + une primitive `Skeleton` réutilisable pour le contenu asynchrone.

**Architecture:** Le layout protégé `(app)/layout.tsx` (Server Component) précharge `/auth/me` et `/auth/me/permissions` via un helper serveur **lecture-seule** (forward du cookie `facil_at`, `null` sur échec, **aucune mutation de cookie**), amorce un `QueryClient` serveur avec les **mêmes clés** que les hooks (`["session"]`, `["my-permissions"]`), `dehydrate`, et enveloppe l'`AppShell` dans `<HydrationBoundary>`. Les hooks `useSession`/`usePermissions` sont **inchangés** : ils trouvent la donnée à l'hydratation. Pattern B : une primitive `Skeleton` câblée dans les surfaces partagées pour les états de chargement des données.

**Tech Stack:** Next.js 15 (App Router, RSC), React 19, TanStack Query v5 (`HydrationBoundary`/`dehydrate`), TypeScript strict, Vitest, Playwright.

## Global Constraints

- **Zéro nouvel endpoint backend** — réutiliser uniquement `/api/v1/auth/me` et `/api/v1/auth/me/permissions` (déjà consommés côté client). Parité par construction.
- **Validation par exécution réelle** : `tsc --noEmit` (vert obligatoire — `next dev` ignore les types), `vitest run`, e2e Playwright headless.
- **Monorepo workspaces** : binaires dans `C:/facil_framework/node_modules/.bin/` (PAS dans `packages/web/node_modules`). Toutes les commandes se lancent depuis `C:/facil_framework/packages/web`.
- **e2e prérequis** : backend Docker up (`facil_framework-backend-1` healthy sur :8080), `next dev` sur :3000, comptes seedés (admin avec `display_name` non-null + une organisation existante — cf. fixes #63/#64). En local, `admin1@facil.local` / `REDACTED_LOCAL_ADMIN_PW` a un `display_name`, et le stack de dev a des orgs.
- **RSC** : interdit de muter un cookie dans un Server Component (`cookies().set/delete` throw) → le helper de prefetch ne rafraîchit jamais le token.
- **Fail-safe** : un prefetch en échec (`null`) n'amorce pas la clé ; le client fetch comme aujourd'hui — jamais de crash.
- **Branche** : `fix/permission-ssr-popin` (déjà créée depuis `develop`).
- **Commits** : convention `<type>(<scope>): <sujet>` ; scope `frontend` ; header ≤ 100 caractères ; corps préféré via heredoc `git commit -F -` (éviter les backticks dans `-m "..."`).

---

### Task 1 : Helper serveur lecture-seule `readForPrefetch`

Un GET serveur qui forwarde le cookie access et renvoie le JSON parsé, ou `null` sur tout échec, **sans jamais toucher aux cookies** (contrairement à `backendProxy` qui refait un refresh + `setAuthCookies`, interdit en RSC).

**Files:**
- Modify: `packages/web/src/lib/server/backend.ts` (ajouter la fonction + l'exporter ; réutilise le `rawCall` interne existant)
- Test: `packages/web/src/lib/server/backend.test.ts` (créer)

**Interfaces:**
- Consumes: `rawCall(path: string, init: RequestInit, token?: string): Promise<Response>` (interne au module), `ACCESS = "facil_at"`, `cookies()` de `next/headers`.
- Produces: `export async function readForPrefetch<T = unknown>(path: string): Promise<T | null>` — GET `path` sur le backend avec le cookie access ; `T` (JSON) sur 2xx ; `null` sur 401/non-2xx/exception. **Ne mute aucun cookie.**

- [ ] **Step 1: Write the failing test**

`next/headers` et `rawCall` (module-private) sont mockés via `vi.mock`. On prouve : (a) 2xx → JSON ; (b) 401 → `null` ; (c) exception réseau → `null` ; (d) **aucun** appel à `cookies().set`/`delete` (le mock de `cookies()` expose des spies).

```typescript
// packages/web/src/lib/server/backend.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

const setSpy = vi.fn();
const deleteSpy = vi.fn();
const fetchMock = vi.fn();

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (n: string) => (n === "facil_at" ? { value: "tok-abc" } : undefined),
    set: setSpy,
    delete: deleteSpy,
  }),
}));

beforeEach(() => {
  setSpy.mockClear();
  deleteSpy.mockClear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("readForPrefetch", () => {
  it("returns parsed JSON on 2xx and forwards the access token, never mutating cookies", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ permissions: ["*"] }), { status: 200 }),
    );
    const { readForPrefetch } = await import("./backend");
    const out = await readForPrefetch<{ permissions: string[] }>("/api/v1/auth/me/permissions");
    expect(out).toEqual({ permissions: ["*"] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/auth/me/permissions");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-abc");
    expect(setSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it("returns null on 401 WITHOUT attempting a refresh or mutating cookies", async () => {
    fetchMock.mockResolvedValue(new Response("", { status: 401 }));
    const { readForPrefetch } = await import("./backend");
    expect(await readForPrefetch("/api/v1/auth/me")).toBeNull();
    // exactly ONE call — no refresh round-trip like backendProxy does
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(setSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it("returns null on a network error", async () => {
    fetchMock.mockRejectedValue(new Error("ECONNREFUSED"));
    const { readForPrefetch } = await import("./backend");
    expect(await readForPrefetch("/api/v1/auth/me")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `C:/facil_framework/packages/web`):
```
"C:/facil_framework/node_modules/.bin/vitest" run src/lib/server/backend.test.ts
```
Expected: FAIL — `readForPrefetch` n'est pas exporté (`readForPrefetch is not a function`).

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `packages/web/src/lib/server/backend.ts`, après `rawCall` (qui existe déjà) :

```typescript
/** Read-only server GET for RSC PREFETCH: forwards the access cookie, returns
 *  parsed JSON on 2xx, `null` on 401/any failure. NEVER mutates cookies — unlike
 *  `backendProxy`, it does NOT refresh (a Server Component cannot call
 *  `cookies().set`, Next throws). On an expired token it simply returns null and
 *  the client re-fetches (and can refresh via the /api/auth/session route). */
export async function readForPrefetch<T = unknown>(path: string): Promise<T | null> {
  try {
    const jar = await cookies();
    const access = jar.get(ACCESS)?.value;
    const res = await rawCall(path, { method: "GET" }, access);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/lib/server/backend.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Typecheck**

Run: `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: exit 0.

- [ ] **Step 6: Commit**

```
git add packages/web/src/lib/server/backend.ts packages/web/src/lib/server/backend.test.ts
git commit -F - <<'EOF'
feat(frontend): readForPrefetch — GET serveur lecture-seule pour l'amorçage RSC

Forward du cookie access, JSON sur 2xx, null sur 401/echec, AUCUNE mutation de
cookie (contrairement a backendProxy qui refresh + setAuthCookies, interdit en
Server Component). Base de l'amorcage react-query cote serveur (D3).
EOF
```

---

### Task 2 : Amorçage react-query dans `(app)/layout.tsx`

Précharger session + permissions au SSR, déshydrater dans le cache client via `HydrationBoundary`. Les hooks restent inchangés.

**Files:**
- Modify: `packages/web/src/app/(app)/layout.tsx` (le layout protégé — contenu actuel : `getInstallStatus` → `redirect("/install")`, garde cookie → `redirect("/login")`, puis `<AppShell>{children}</AppShell>`)
- Create: `packages/web/src/app/(app)/prefetch-session.ts` (helper serveur qui construit l'état déshydraté)
- Test: `packages/web/src/app/(app)/prefetch-session.test.ts` (créer)

**Interfaces:**
- Consumes: `readForPrefetch<T>(path)` (Task 1) ; `QueryClient`, `dehydrate` de `@tanstack/react-query` ; `HydrationBoundary` de `@tanstack/react-query`.
- Produces: `export async function dehydratedAuthState(): Promise<DehydratedState>` — précharge `/api/v1/auth/me` (→ clé `["session"]` = `{ authenticated: true, ...me }`) et `/api/v1/auth/me/permissions` (→ clé `["my-permissions"]`), n'amorce que les clés dont le prefetch a réussi, renvoie `dehydrate(client)`.

- [ ] **Step 1: Write the failing test**

On mocke `readForPrefetch` pour prouver le mapping clé→donnée et le fail-safe (une clé absente si son prefetch renvoie `null`). On lit le résultat via un `QueryClient` réhydraté.

```typescript
// packages/web/src/app/(app)/prefetch-session.test.ts
import { describe, it, expect, vi } from "vitest";
import { QueryClient, hydrate } from "@tanstack/react-query";

const readMock = vi.fn();
vi.mock("@/lib/server/backend", () => ({ readForPrefetch: readMock }));

async function rehydrated() {
  const { dehydratedAuthState } = await import("./prefetch-session");
  const state = await dehydratedAuthState();
  const qc = new QueryClient();
  hydrate(qc, state);
  return qc;
}

describe("dehydratedAuthState", () => {
  it("seeds [session] as {authenticated:true, ...me} and [my-permissions]", async () => {
    readMock.mockImplementation(async (path: string) =>
      path.endsWith("/permissions")
        ? { break_glass: false, permissions: ["*"] }
        : { break_glass: false, account: { id: "a1", display_name: null } });
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toEqual({
      authenticated: true, break_glass: false, account: { id: "a1", display_name: null },
    });
    expect(qc.getQueryData(["my-permissions"])).toEqual({ break_glass: false, permissions: ["*"] });
  });

  it("omits a key whose prefetch returned null (fail-safe, no crash)", async () => {
    readMock.mockImplementation(async (path: string) =>
      path.endsWith("/permissions") ? null : { break_glass: false, account: { id: "a1" } });
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toBeDefined();
    expect(qc.getQueryData(["my-permissions"])).toBeUndefined();
  });

  it("returns an empty dehydrated state when both prefetches fail", async () => {
    readMock.mockResolvedValue(null);
    const qc = await rehydrated();
    expect(qc.getQueryData(["session"])).toBeUndefined();
    expect(qc.getQueryData(["my-permissions"])).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/app/\(app\)/prefetch-session.test.ts`
Expected: FAIL — module `./prefetch-session` introuvable.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/app/(app)/prefetch-session.ts
import { QueryClient, dehydrate, type DehydratedState } from "@tanstack/react-query";
import { readForPrefetch } from "@/lib/server/backend";

// Same keys the client hooks use (use-session.ts -> ["session"],
// use-permissions.ts -> ["my-permissions"]). Seeding these means useSession /
// usePermissions find data at hydration -> no permission pop-in in the first paint.
export async function dehydratedAuthState(): Promise<DehydratedState> {
  const [me, perms] = await Promise.all([
    readForPrefetch<{ break_glass: boolean; account?: unknown }>("/api/v1/auth/me"),
    readForPrefetch<{ permissions: string[] }>("/api/v1/auth/me/permissions"),
  ]);
  const qc = new QueryClient();
  // `{authenticated:true, ...me}` mirrors what the /api/auth/session route returns
  // (and what parseSession/useSession expect); /auth/me itself omits `authenticated`.
  if (me) qc.setQueryData(["session"], { authenticated: true, ...me });
  if (perms) qc.setQueryData(["my-permissions"], perms);
  return dehydrate(qc);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/app/\(app\)/prefetch-session.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Wire the HydrationBoundary into the protected layout**

Modifier `packages/web/src/app/(app)/layout.tsx` — ajouter le prefetch + `HydrationBoundary` autour de `AppShell`, **après** la garde `redirect("/login")` :

```tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { HydrationBoundary } from "@tanstack/react-query";
import { ACCESS, REFRESH, getInstallStatus } from "@/lib/server/backend";
import { AppShell } from "@/components/app-shell";
import { dehydratedAuthState } from "./prefetch-session";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { installed } = await getInstallStatus();
  if (!installed) redirect("/install");
  const jar = await cookies();
  if (!jar.get(ACCESS) && !jar.get(REFRESH)) {
    redirect("/login");
  }
  // Seed react-query with the principal's session + permissions so the shell nav
  // and permission-gated actions render CORRECTLY in the first paint (no pop-in).
  // Fail-safe: dehydratedAuthState() omits any key it couldn't prefetch.
  const dehydratedState = await dehydratedAuthState();
  return (
    <HydrationBoundary state={dehydratedState}>
      <AppShell>{children}</AppShell>
    </HydrationBoundary>
  );
}
```

- [ ] **Step 6: Typecheck**

Run: `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: exit 0.

- [ ] **Step 7: Commit**

```
git add "packages/web/src/app/(app)/prefetch-session.ts" "packages/web/src/app/(app)/prefetch-session.test.ts" "packages/web/src/app/(app)/layout.tsx"
git commit -F - <<'EOF'
feat(frontend): amorcage serveur de la session + permissions (fin du pop-in)

Le layout protege precharge /auth/me + /auth/me/permissions (helper lecture-seule)
et deshydrate dans les cles react-query ["session"]/["my-permissions"] via
HydrationBoundary. useSession/usePermissions sont inchanges : ils trouvent la
donnee a l'hydratation, la nav + les actions gardees sont correctes au 1er paint.
Fail-safe : une cle non prechargee laisse le client fetch comme avant.
EOF
```

---

### Task 3 : e2e Pattern A — SSR permission-driven + anti-pop-in

Prouver, sur un vrai rendu SSR, que l'action gardée est présente pour un admin et absente pour un low-priv, et qu'elle est là dès le `domcontentloaded` (pas de pop-in).

**Files:**
- Modify: `packages/web/src/modules/providers/page.tsx` (ajouter `data-testid="routing-edit"` au bouton gardé de `RoutingCard` — hook de test stable, locale-indépendant)
- Create: `packages/web/e2e/permission-ssr.spec.ts`

**Interfaces:**
- Consumes: l'action gardée `settings.manage` de `RoutingCard` (`canEdit && <Button>…</Button>`), les comptes seedés (`E2E_ADMIN_*` avec la perm, `E2E_READONLY_*` sans).
- Produces: (test uniquement).

- [ ] **Step 1: Add the stable test hook to the guarded button**

Dans `packages/web/src/modules/providers/page.tsx`, le bouton edit de `RoutingCard` (`{canEdit && !editing && (<Button …>{t("routing.edit")}</Button>)}`) reçoit un `data-testid` :

```tsx
{canEdit && !editing && (
  <Button data-testid="routing-edit" variant="outline" size="sm" onClick={() => setEditing(true)}>{t("routing.edit")}</Button>
)}
```

- [ ] **Step 2: Write the e2e test**

```typescript
// packages/web/e2e/permission-ssr.spec.ts
import { expect, test } from "@playwright/test";

const ADMIN = { id: process.env.E2E_ADMIN_EMAIL || "e2e@x.com", pw: process.env.E2E_ADMIN_PASSWORD || "Sup3rStr0ng!pw" };
const RO = { id: process.env.E2E_READONLY_EMAIL, pw: process.env.E2E_READONLY_PASSWORD };

async function authCookies(request, id, pw) {
  const r = await request.post("http://localhost:3000/api/auth/login", { data: { identifier: id, password: pw } });
  expect(r.status()).toBe(200);
  return (await request.storageState()).cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

test("admin: the settings.manage-gated action is in the SSR HTML (no pop-in)", async ({ page, request }) => {
  const cookie = await authCookies(request, ADMIN.id, ADMIN.pw);
  // 1) SSR proof: raw server HTML already contains the guarded button.
  const html = await (await fetch("http://localhost:3000/providers", { headers: { cookie } })).text();
  expect(html).toContain('data-testid="routing-edit"');
  // 2) anti-pop-in: present at domcontentloaded, not appearing seconds later.
  await page.context().addCookies((await request.storageState()).cookies);
  await page.goto("http://localhost:3000/providers", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("routing-edit")).toBeVisible({ timeout: 3_000 });
});

test("low-privilege: the guarded action is ABSENT from the SSR HTML", async ({ request }) => {
  test.skip(!RO.id || !RO.pw, "no readonly account provisioned");
  const cookie = await authCookies(request, RO.id!, RO.pw!);
  const html = await (await fetch("http://localhost:3000/providers", { headers: { cookie } })).text();
  expect(html).not.toContain('data-testid="routing-edit"');
});
```

- [ ] **Step 3: Ensure the stack is up + seeded**

Prérequis (voir Global Constraints) : `facil_framework-backend-1` healthy, `next dev` sur :3000, et un compte admin (`display_name` non-null, perm `settings.manage`) + un compte low-priv (`member`) + une org existante. En local :
```
# backend up ?
docker exec facil_framework-backend-1 python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8080/health',timeout=5).status)"
# next dev (depuis packages/web, en arriere-plan) :
"C:/facil_framework/node_modules/.bin/next" dev -p 3000
```
Exporter `E2E_ADMIN_EMAIL=admin1@facil.local E2E_ADMIN_PASSWORD=REDACTED_LOCAL_ADMIN_PW` (+ un compte readonly à la volée si besoin).

- [ ] **Step 4: Run the e2e test to verify it PASSES with the fix**

Run (depuis `packages/web`, stack up) :
```
E2E_ADMIN_EMAIL=admin1@facil.local E2E_ADMIN_PASSWORD=REDACTED_LOCAL_ADMIN_PW \
"C:/facil_framework/node_modules/.bin/playwright" test permission-ssr.spec.ts --project=chromium
```
Expected: PASS (admin ; readonly skip si non provisionné en local — il tournera en CI où le seed existe).

- [ ] **Step 5: Prove the test has teeth (mutation)**

Commenter temporairement le `HydrationBoundary`/prefetch dans `(app)/layout.tsx` (revenir au `<AppShell>{children}</AppShell>` nu), relancer le test admin : il doit **ÉCHOUER** (le SSR HTML ne contient plus `routing-edit` — pop-in). Puis rétablir la Task 2.
Run: idem Step 4. Expected: le test admin ÉCHOUE sans l'amorçage, PASSE avec.

- [ ] **Step 6: Commit**

```
git add packages/web/e2e/permission-ssr.spec.ts packages/web/src/modules/providers/page.tsx
git commit -F - <<'EOF'
test(frontend): e2e SSR permission-driven + anti-pop-in (D3 Pattern A)

Prouve sur le vrai HTML SSR : l'action gardee settings.manage est presente pour
un admin, absente pour un low-priv, et visible des le domcontentloaded (pas de
pop-in). data-testid stable, locale-independant. A dents (mutation verifiee :
echoue sans l'amorcage serveur, passe avec).
EOF
```

---

### Task 4 : Primitive `Skeleton`

**Files:**
- Create: `packages/web/src/components/ui/skeleton.tsx`
- Test: `packages/web/src/components/ui/skeleton.test.tsx` (créer)

**Interfaces:**
- Consumes: `cn` de `@/lib/utils` (helper de classes — présent dans le repo, utilisé par les autres primitives `ui/`).
- Produces: `export function Skeleton(props: React.HTMLAttributes<HTMLDivElement>): JSX.Element` — un bloc `animate-pulse rounded-md bg-muted`, `className`/props fusionnés, `data-testid="skeleton"`, `aria-hidden`.

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/src/components/ui/skeleton.test.tsx
import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("renders a pulsing, aria-hidden placeholder and merges className", () => {
    const html = renderToStaticMarkup(<Skeleton className="h-4 w-20" />);
    expect(html).toContain("animate-pulse");
    expect(html).toContain("h-4 w-20");
    expect(html).toContain('aria-hidden');
    expect(html).toContain('data-testid="skeleton"');
  });
});
```

> Note : test de rendu pur via `renderToStaticMarkup` (pas de DOM/testing-library — cohérent avec la convention vitest du repo : `.test.ts(x)` logique, pas de render-test lourd). `react-dom/server` est déjà dispo (Next).

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/skeleton.test.tsx`
Expected: FAIL — `./skeleton` introuvable.

- [ ] **Step 3: Write minimal implementation**

```tsx
// packages/web/src/components/ui/skeleton.tsx
import { cn } from "@/lib/utils";

/** Loading placeholder. Theme-aware (bg-muted), aria-hidden (decorative).
 *  Compose with h-*/w-* utilities for the shape of the content it replaces. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-testid="skeleton"
      aria-hidden
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/skeleton.test.tsx`
Expected: PASS.

- [ ] **Step 5: Typecheck + commit**

Run: `"C:/facil_framework/node_modules/.bin/tsc" --noEmit` (exit 0), puis :
```
git add packages/web/src/components/ui/skeleton.tsx packages/web/src/components/ui/skeleton.test.tsx
git commit -F - <<'EOF'
feat(frontend): primitive Skeleton reutilisable (etats de chargement, D3 Pattern B)

Bloc animate-pulse theme-aware, aria-hidden, className fusionne. Cablee ensuite
dans les surfaces partagees.
EOF
```

---

### Task 5 : Câbler `Skeleton` dans les surfaces partagées

Exposer un état de chargement DRY sur `Card`, `RecordSurface`, `detail-panel` (le DataGrid a déjà ses états — ne pas le toucher). Chaque surface accepte une prop `loading?: boolean` qui, si vraie, rend des `Skeleton` à la place du contenu.

**Files:**
- Modify: `packages/web/src/components/ui/card.tsx` (ajouter un sous-composant `CardSkeleton` OU une prop `loading` sur `CardContent` — voir Step 1)
- Modify: `packages/web/src/components/shared/record-surface.tsx`
- Modify: `packages/web/src/components/ui/detail-panel.tsx`
- Test: `packages/web/src/components/ui/skeleton-surfaces.test.tsx` (créer)

**Interfaces:**
- Consumes: `Skeleton` (Task 4).
- Produces: chaque surface rend un/des `Skeleton` (`data-testid="skeleton"`) en état `loading`. Contrat exact figé au Step 1 après lecture des composants réels.

- [ ] **Step 1: Read the three surfaces to fix the exact contract**

Lire le contenu réel avant d'éditer (ne pas inventer les props/structure) :
```
sed -n '1,80p' packages/web/src/components/ui/card.tsx
sed -n '1,80p' packages/web/src/components/shared/record-surface.tsx
sed -n '1,80p' packages/web/src/components/ui/detail-panel.tsx
```
Décision à figer ici : le mécanisme le plus simple non-invasif est un **sous-composant exporté** `CardSkeleton` / `DetailPanelSkeleton` (3 lignes de `Skeleton`) que les pages rendent conditionnellement, plutôt qu'une prop `loading` sur chaque surface (moins de surface d'API modifiée). Choisir selon le style existant du fichier ; si les surfaces ont déjà une prop `loading`/`isLoading`, s'y brancher.

- [ ] **Step 2: Write the failing test**

Test générique (indépendant du mécanisme retenu au Step 1) : le sous-composant/rendu loading de chaque surface produit au moins un `Skeleton`.

```tsx
// packages/web/src/components/ui/skeleton-surfaces.test.tsx
import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CardSkeleton } from "./card";
import { DetailPanelSkeleton } from "./detail-panel";

describe("shared surfaces expose a DRY loading skeleton", () => {
  it("CardSkeleton renders Skeleton placeholders", () => {
    expect(renderToStaticMarkup(<CardSkeleton />)).toContain('data-testid="skeleton"');
  });
  it("DetailPanelSkeleton renders Skeleton placeholders", () => {
    expect(renderToStaticMarkup(<DetailPanelSkeleton />)).toContain('data-testid="skeleton"');
  });
});
```

> Si le Step 1 a retenu une prop `loading` plutôt que des sous-composants, adapter le test pour rendre la surface avec `loading` (et retirer les imports de sous-composants inexistants).

- [ ] **Step 3: Run test to verify it fails**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/skeleton-surfaces.test.tsx`
Expected: FAIL — `CardSkeleton`/`DetailPanelSkeleton` non exportés.

- [ ] **Step 4: Implement the loading rendering in each surface**

Exemple pour `card.tsx` (ajouter, sans casser l'API existante) :
```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function CardSkeleton() {
  return (
    <div className="space-y-3 p-6">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}
```
Idem `DetailPanelSkeleton` dans `detail-panel.tsx`, et le rendu loading de `record-surface.tsx` (suivre sa structure lue au Step 1). Réutiliser `Skeleton` partout — pas de bloc pulse ad-hoc.

- [ ] **Step 5: Run test to verify it passes**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run src/components/ui/skeleton-surfaces.test.tsx`
Expected: PASS.

- [ ] **Step 6: Typecheck + commit**

Run: `"C:/facil_framework/node_modules/.bin/tsc" --noEmit` (exit 0), puis :
```
git add packages/web/src/components/ui/card.tsx packages/web/src/components/shared/record-surface.tsx packages/web/src/components/ui/detail-panel.tsx packages/web/src/components/ui/skeleton-surfaces.test.tsx
git commit -F - <<'EOF'
feat(frontend): squelettes de chargement DRY sur Card/RecordSurface/detail-panel

Reutilisent la primitive Skeleton (le DataGrid a deja ses etats, non touche).
Les pages heritent d'un etat de chargement coherent, zero travail par page.
EOF
```

---

### Task 6 : Gate finale

**Files:** aucun (validation + revue).

- [ ] **Step 1: Full typecheck**

Run (depuis `packages/web`): `"C:/facil_framework/node_modules/.bin/tsc" --noEmit`
Expected: exit 0. (Rappel : `next dev` ignore les types — cette étape est non négociable.)

- [ ] **Step 2: Full vitest**

Run: `"C:/facil_framework/node_modules/.bin/vitest" run`
Expected: tous verts (dont les 4 nouveaux fichiers de test).

- [ ] **Step 3: Full e2e (stack up)**

Run (backend + next dev up, env admin exportées) :
```
E2E_ADMIN_EMAIL=admin1@facil.local E2E_ADMIN_PASSWORD=REDACTED_LOCAL_ADMIN_PW \
"C:/facil_framework/node_modules/.bin/playwright" test permission-ssr.spec.ts custom-fields.spec.ts smoke.spec.ts --project=chromium
```
Expected: PASS (non-régression des e2e existants + le nouveau).

- [ ] **Step 4: Revue parité + §11bis (checklist manuelle)**

- Parité : `git diff develop...HEAD` ne touche **aucun** fichier backend (`packages/backend/**`) ni endpoint. Confirmer visuellement. Aucun endpoint consommé qui n'existe pas (`/auth/me`, `/auth/me/permissions` existent).
- §11bis / standards : la primitive `Skeleton` et les surfaces respectent a11y (`aria-hidden` sur les placeholders décoratifs), theme-aware (`bg-muted`), et le pattern DRY (aucun `animate-pulse` ad-hoc réintroduit — `grep -rn "animate-pulse" packages/web/src | grep -v skeleton.tsx` doit être vide ou justifié).

- [ ] **Step 5: Revue par agents (gate anti-régression du repo)**

Sur le diff : `code-reviewer` (bugs/régressions) + `silent-failure-hunter` (le fail-safe du prefetch avale-t-il quelque chose de mal ?). Corriger les findings.

- [ ] **Step 6: Push + PR (accord explicite requis)**

Ne PAS pousser sans accord (règle du repo). Une fois accordé : `git push -u origin fix/permission-ssr-popin` puis PR vers `develop` (titre `fix(frontend): amorçage serveur des permissions — fin du pop-in SSR (D3)`), et surveiller la CI (dont l'e2e, désormais couvert par le seed #63).

---

## Self-Review

**Spec coverage (spec §1-§8) :**
- §2 Pattern A (helper lecture-seule) → Task 1. ✅
- §2 Pattern A (amorçage layout, HydrationBoundary, fail-safe) → Task 2. ✅
- §3 Pattern B (primitive Skeleton) → Task 4 ; câblage surfaces → Task 5. ✅
- §5 tests (e2e SSR admin/low-priv + anti-pop-in) → Task 3 ; (unit fail-safe helper) → Task 1 ; (vitest Skeleton) → Task 4/5. ✅
- §6 parité (zéro backend) → Global Constraints + Task 6 Step 4. ✅
- §7 branche → Global Constraints. ✅

**Placeholders :** aucun « TBD/TODO » ; chaque étape porte le code réel. Task 5 Step 1 demande de LIRE les fichiers réels avant d'éditer (adaptation au réel, pas un trou) car la structure exacte de `Card`/`RecordSurface`/`detail-panel` n'est pas figée par la spec ; le test du Step 2 est conditionné au mécanisme retenu.

**Type consistency :** `readForPrefetch<T>(path): Promise<T|null>` (Task 1) consommé par `dehydratedAuthState()` (Task 2) ; clés `["session"]`/`["my-permissions"]` identiques à `use-session.ts`/`use-permissions.ts` ; `Skeleton` (Task 4) consommé par les surfaces (Task 5) ; `data-testid="routing-edit"` (Task 3 Step 1) asserté au même nom (Task 3 Step 2).
