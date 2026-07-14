import { expect, test, type Page } from "@playwright/test";

/**
 * End-to-end proof for SP1 (Field Schema & Custom Fields) — the human path:
 *
 *   1. An admin defines a custom field on Site from the Studio (`/fields`),
 *      the field shows up on a real Site's form, a value typed into it
 *      survives a page reload (round-trips through Postgres, not just React
 *      state).
 *   2. A signed-in user WITHOUT `fields.manage` gets neither the nav entry
 *      nor a live create form — including the `?new=1&sel=<id>` URL that a
 *      prior fix closed (surfaceOpen is true via `sel`, but
 *      `canRenderCreateSurface` still refuses to mount `CreateSurface`).
 *
 * Auth follows the existing pattern (see e2e/smoke.spec.ts + the task-7/
 * task-8 verification passes): log in through the real `/login` UI, no
 * fixture/mock harness. The UI's default locale is French
 * (`branding.default_locale`), so labels are matched with locale-tolerant
 * regexes (en/fr), exactly like the rest of this suite.
 */

// CRITICAL fix (final fix wave): this used to hardcode a real local admin
// account's password straight into the spec (now in this branch's git
// history — see the task report for the rotation notice) AND assume two
// accounts (`admin1@facil.local`, `e2e-readonly@facil.local`) that only ever
// existed on a developer's local stack. CI's e2e job (`.github/workflows/
// ci.yml`) seeds exactly ONE super-admin, `e2e@x.com` — neither hardcoded
// account exists there, so both tests below silently timed out in CI.
//
// Parameterised from `process.env`, following `playwright.config.ts`'s own
// `E2E_BASE_URL` convention. The admin default matches the account CI
// already seeds (role "admin" -> `['*']` grants, see `rbac/seeds/empty.
// yaml`), so the first test runs out of the box in both CI and local dev
// (`docker compose` local stack seeds the same super-admin — see README).
// There is NO safe default for the low-privilege account: CI must seed one
// explicitly (see the "Seed a low-privilege account" step added to
// `ci.yml`) and pass it through `E2E_READONLY_EMAIL`/`E2E_READONLY_PASSWORD`;
// locally, export the two vars yourself. Absent -> `test.skip()` with an
// explicit reason (never a silent pass).
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "e2e@x.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "Sup3rStr0ng!pw";
const READONLY_EMAIL = process.env.E2E_READONLY_EMAIL;
const READONLY_PASSWORD = process.env.E2E_READONLY_PASSWORD;

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/identifier|identifiant|correo/i).fill(email);
  // `input[type="password"]` (not getByLabel) — the show/hide toggle button's
  // aria-label also contains "mot de passe"/"password", which would make a
  // label-text locator match two elements (strict-mode violation).
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /sign in|se connecter|iniciar/i }).click();
  // Successful login redirects off /login. Generous timeout: first hit in a
  // freshly-started `next dev` server pays Next's on-demand route-compile
  // cost on top of the real network round trip.
  await expect(page).not.toHaveURL(/\/login/, { timeout: 20_000 });
}

test.describe.configure({ mode: "serial" });

test("define a custom field on Site, fill it on a Site's form, reload — the value persists", async ({ page }) => {
  const uniqueSuffix = Date.now().toString(36);
  const fieldKey = `e2e_convention_${uniqueSuffix}`;
  const siteCode = `E2E-${uniqueSuffix}`;

  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  // --- Screen A: the Studio — define the field on the Site target -----------
  await page.goto("/fields");

  // Target tabs are plain buttons labelled by `fields.target.*` — "Site" is
  // identical in en/fr ("Site"). Wait for the org to resolve first (the
  // "New field" button stays disabled until `effectiveOrgId` is truthy).
  await page.getByRole("button", { name: "Site", exact: true }).click();
  const newFieldButton = page.getByRole("button", { name: /new field|nouveau champ/i });
  await expect(newFieldButton).toBeEnabled({ timeout: 15_000 });
  await newFieldButton.click();

  // Required fields carry a trailing " *" in their accessible name (see
  // record-form.tsx's `<Label>` render), so match the label PREFIX, not the
  // full string. (No trailing `\b`: "é" isn't a `\w` char in JS regex by
  // default, so `\b` right after it never asserts a boundary.)
  await page.getByLabel(/^key|^clé/i).fill(fieldKey);
  await page.locator("#rf-type").selectOption("string");
  // Label (English) / Label (French) / Label (Spanish) — anchored on
  // "Label"/"Libellé" too: "(anglais)" alone also matches the unrelated
  // "Indice (anglais)" (Hint (English)) field (strict-mode violation).
  await page.getByLabel(/^label.*\(english\)|^libell.*\(anglais\)/i).fill("Convention no.");
  await page.getByLabel(/^label.*\(french\)|^libell.*\(fran.ais\)/i).fill("N° de convention");
  // fr.json spells this "espagnol" (French for "Spanish"), not "español".
  await page.getByLabel(/^label.*\(spanish\)|^libell.*\(espagnol\)/i).fill("N.º de convenio");

  // Scope to the <form> for the submit click — the toolbar's "New field"/
  // "Nouveau champ" button stays mounted (unconditionally rendered) while
  // the create form is open, so the generic role+name locator would match
  // two buttons at this point (strict-mode violation).
  await page.locator('form button[type="submit"]').click();

  // Create succeeds -> the surface closes and the new definition appears in
  // the Studio's own list. `getByRole("cell", ...)` (not `getByText`, which
  // the DataGrid's responsive card layout duplicates in the DOM) — one row,
  // unambiguous.
  await expect(page.getByRole("cell", { name: fieldKey })).toBeVisible({ timeout: 10_000 });

  // --- Screen B: the field shows up on a real Site's form --------------------
  await page.goto("/locations");
  const siteNewButton = page.getByRole("button", { name: /^new$|^nouveau$/i });
  await expect(siteNewButton).toBeEnabled({ timeout: 15_000 });
  await siteNewButton.click();

  // `code`/`name` are required on Site too, so their accessible name also
  // carries the trailing " *" — same prefix-match reasoning as `key` above.
  await page.getByLabel(/^code/i).fill(siteCode);
  await page.getByLabel(/^name|^nom/i).fill(`E2E site ${uniqueSuffix}`);
  // The custom field renders on the create form too (useSiteFields merges
  // the org's site.custom_fields schema) — filled here at create time so a
  // single submit both creates the site AND writes the custom value.
  // `#rf-<key>` (not a label-text locator): the field's own label text
  // ("N° de convention"/"Convention no.") is NOT unique per run — a re-run
  // that creates a second Site custom field would make a text/label locator
  // ambiguous (this bit a first pass: two leftover "e2e_convention_*"
  // definitions with the identical label from earlier failed attempts, since
  // purged). The DOM id IS unique (`fieldKey` embeds `uniqueSuffix`) and is
  // exactly how a real user would still find it VISUALLY (the label reads
  // "N° de convention"/"Convention no." either way) — asserted separately
  // below via the rendered label text itself.
  const customFieldInput = page.locator(`#rf-${fieldKey}`);
  await expect(page.getByText(/N° de convention|Convention no\./i).first()).toBeVisible();
  await customFieldInput.fill("C-2026-001");
  await page.locator('form button[type="submit"]').click();

  // Create succeeds -> back to the list. Find the new row and open it.
  // `getByRole("cell", ...)` — same DataGrid dual-render reasoning as the
  // Studio list above.
  const siteCell = page.getByRole("cell", { name: siteCode });
  await expect(siteCell).toBeVisible({ timeout: 10_000 });
  await siteCell.click();

  await expect(customFieldInput).toHaveValue("C-2026-001");

  // The URL now carries `?sel=<id>` (RecordSurface deep-link) — reload the
  // whole page (fresh React tree, fresh fetch from Postgres, not client
  // cache) and re-assert the value round-tripped through the database.
  await expect(page).toHaveURL(/[?&]sel=/);
  await page.reload();
  await expect(customFieldInput).toHaveValue("C-2026-001", { timeout: 10_000 });
});

test("a user without fields.manage sees neither the nav entry nor the create action — including the ?new=1&sel= URL", async ({ page }) => {
  test.skip(
    !READONLY_EMAIL || !READONLY_PASSWORD,
    "E2E_READONLY_EMAIL/E2E_READONLY_PASSWORD not set — no low-privilege " +
    "account to test permission-gating against (see ci.yml's low-privilege " +
    "seed step; set both env vars locally to run this test).",
  );
  await login(page, READONLY_EMAIL!, READONLY_PASSWORD!);

  // No nav entry.
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: /custom fields|champs personnalis.s/i }),
  ).toHaveCount(0);

  // Direct navigation to /fields: no create action, and the Studio's own
  // "define a field" form (#rf-key) never mounts.
  await page.goto("/fields");
  await expect(
    page.getByRole("button", { name: /new field|nouveau champ/i }),
  ).toHaveCount(0);
  await expect(page.locator("#rf-key")).toHaveCount(0);

  // The regression this task must pin: `?new=1&sel=<id>` makes `surfaceOpen`
  // true via the `sel` disjunct regardless of `canManage`, but
  // `canRenderCreateSurface(isNew, canManage)` must still refuse to mount a
  // live CreateSurface — the URL is inert, not just the button.
  await page.goto("/fields?new=1&sel=deliberately-nonexistent-id");
  await expect(page.locator("#rf-key")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /new field|nouveau champ/i }),
  ).toHaveCount(0);
});
