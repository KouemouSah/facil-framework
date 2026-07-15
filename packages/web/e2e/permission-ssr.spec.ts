import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * End-to-end proof for D3 (Pattern A) — the `settings.manage`-gated "Edit"
 * button on `/providers`' RoutingCard is rendered SERVER-SIDE, not bolted on
 * client-side after a permissions fetch resolves:
 *
 *   1. Admin: the RAW SSR HTML (fetched with the session cookie, before any
 *      JS runs) already contains `data-testid="routing-edit"`.
 *   2. Admin: the button is visible at `domcontentloaded` — i.e. it's there
 *      from the first paint, not a few hundred ms later once a client fetch
 *      resolves (that lag IS the pop-in this task closes).
 *   3. Low-privilege (`member`, no `settings.manage`): the raw SSR HTML does
 *      NOT contain the testid at all — the server itself withheld the
 *      markup, it isn't just hidden/disabled client-side.
 *
 * `(app)/layout.tsx` (Task 1-2, same branch) is what makes this true: it
 * prefetches session + permissions server-side and dehydrates them into a
 * `HydrationBoundary` around `AppShell`, so `RoutingCard`'s `canEdit` check
 * already has the real answer during SSR. Mutation-tested (see the task
 * report): reverting that layout to a bare `<AppShell>{children}</AppShell>`
 * makes the admin test FAIL (SSR HTML loses the testid — pop-in returns).
 *
 * Auth: same env-var convention as e2e/custom-fields.spec.ts
 * (`E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD`, `E2E_READONLY_EMAIL`/
 * `E2E_READONLY_PASSWORD`) — CI seeds a low-priv account, local dev doesn't
 * (test.skip with an explicit reason, never a silent pass).
 */
const ADMIN = {
  id: process.env.E2E_ADMIN_EMAIL || "e2e@x.com",
  pw: process.env.E2E_ADMIN_PASSWORD || "Sup3rStr0ng!pw",
};
const RO = {
  id: process.env.E2E_READONLY_EMAIL,
  pw: process.env.E2E_READONLY_PASSWORD,
};

// Logs in through the real BFF route (not a fixture/mock) and returns the
// `Cookie:` header value for the resulting httpOnly session — this lets the
// raw-HTML assertions below use a plain `fetch` (no browser, no JS) to prove
// the markup came from the SERVER, not from client-side rendering.
async function authCookieHeader(request: APIRequestContext, id: string, pw: string) {
  const res = await request.post("/api/auth/login", { data: { identifier: id, password: pw } });
  expect(res.ok()).toBeTruthy();
  const state = await request.storageState();
  return state.cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

test("admin: the settings.manage-gated action is in the SSR HTML (no pop-in)", async ({ page, request, baseURL }) => {
  const cookie = await authCookieHeader(request, ADMIN.id, ADMIN.pw);

  // 1) SSR proof: the raw server HTML (fetched directly, no browser/JS
  // involved) already contains the guarded button's markup.
  const html = await (await fetch(`${baseURL}/providers`, { headers: { cookie } })).text();
  expect(html).toContain('data-testid="routing-edit"');

  // 2) anti-pop-in: present at `domcontentloaded` — i.e. before hydration
  // has had any real chance to run a client-side permissions fetch.
  const state = await request.storageState();
  await page.context().addCookies(state.cookies);
  await page.goto("/providers", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("routing-edit")).toBeVisible({ timeout: 3_000 });
});

test("low-privilege: the guarded action is ABSENT from the SSR HTML", async ({ request, baseURL }) => {
  test.skip(
    !RO.id || !RO.pw,
    "E2E_READONLY_EMAIL/E2E_READONLY_PASSWORD not set — no low-privilege " +
    "account to test permission-gating against (see ci.yml's low-privilege " +
    "seed step; set both env vars locally to run this test).",
  );
  const cookie = await authCookieHeader(request, RO.id!, RO.pw!);
  const html = await (await fetch(`${baseURL}/providers`, { headers: { cookie } })).text();
  expect(html).not.toContain('data-testid="routing-edit"');
});
