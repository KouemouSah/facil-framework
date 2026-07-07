# Frontend Foundation — final sweep (sub-project 0)

Status of the admin web surface after the Foundation sub-project (phases 1–8).
The Foundation built the reusable ERP layer (design system, `RecordSurface`,
`RecordForm`, `ConfirmDialog`, `DataGrid`, secure upload, toasts, i18n, auth) and
proved it on **two pilots**, then added permission-driven gating and a responsive
sweep. Pages migrate into the modular structure (`src/modules/<domain>/`) **when
their sub-project touches them** — this document records what was reached and what
is deliberately left for later.

## Migrated to the Foundation

| Page | Module | Adopted |
|---|---|---|
| `/organizations` | `modules/organization` | RecordSurface (create+edit), FileUpload logo, ConfirmDialog delete, optimistic+rollback, i18n, `usePermissions` gating |
| `/locations` | `modules/location` | idem |
| `/agents` | `modules/identity` | RecordSurface, RecordForm edit (audit 12), ConfirmDialog status (revokes sessions), bulk, roles, batch org-labels (E6), gating |

Shared surfaces used app-wide: `DataGrid` (now responsive — table ≥ md, stacked
cards < md), `RecordForm` (`readOnly` permission mode), `AuthCard`, `EmailVerifyBanner`,
`usePermissions`.

## Untouched pages (flat legacy layout — still functional)

These keep the pre-Foundation flat layout under `app/(app)/<route>/page.tsx`. They
work and are RBAC-gated at the backend; they are **not yet** migrated onto
`modules/*` + `RecordSurface`, and their toolbar actions are **not yet**
`usePermissions`-gated at the UI (the backend still enforces).

| Page | Deferred to |
|---|---|
| `/roles` (RBAC roles + permissions) | RBAC sub-project |
| `/reference` (referential data, CSV import) | Reference sub-project |
| `/federation` (SCIM / IdP) | Federation sub-project |
| `/settings` (branding editor) | Settings sub-project (B) |

**Migration recipe** (when a sub-project reaches one of these): extract
`{page,fields,api}.ts` into `modules/<domain>/`, replace any create-dialog with
`RecordSurface ?new=1`, adopt `RecordForm` + `ConfirmDialog`, gate actions with
`usePermissions().can(...)`, key all strings via `next-intl`.

## Residual DEFER (tracked to their sub-projects)

- **Audit 4 (full SecretField rollout), 13, 14, 16, 17, 18, 19** — dedicated sub-projects.
- **i18n of untouched pages** — with each page's migration (touched pages are keyed).
- **Live validations requiring the full stack** (not runnable in the node/CI-lite gate):
  authenticated Playwright flows (create-via-panel, logo upload → MinIO), live `axe`
  a11y audit, manual responsive review at 360/768/1280, and a per-route bundle-size
  budget CI gate (<150 KB). These are the remaining Phase 8 items; run them once the
  Docker stack is up. The code-level a11y baseline (global `:focus-visible`, skip-link,
  ARIA labels, WCAG-checked tokens) and responsive layout are in place.
