# `src/modules/` — domain modules (Foundation convention)

Each business domain owns a folder here. Route files under `app/(app)/<route>/page.tsx`
stay **thin** — they import and render the module's page component. This keeps every
page a single-purpose, isolated, testable unit (ERP-grade structure).

## Per-module shape

```
modules/<domain>/
  page.tsx        # the page component (rendered by the thin app/ route)
  components/     # domain-specific pieces (not reusable elsewhere)
  hooks/          # domain data hooks (TanStack Query)
  api.ts          # BFF calls for this domain (typed)
  fields.ts       # RecordForm FieldDef[] (shared by create + edit)
  schema.ts       # zod schemas mirroring the backend (client validation)
```

Domains: `organization · location · identity (agents) · rbac · reference · federation ·
branding` (+ `providers · settings · party` added by sub-projects A/B/D).

## Layering (no cycles)

```
app → modules → components/shared → components/ui → core
```

- **`components/ui`** = primitives (button, input, badge, toast, …).
- **`components/shared`** = composites (DataGrid, RecordSurface, RecordForm, …). Import via `@/components/shared`.
- **`components/layout`** = AppShell, Toaster, banners.
- **core = `src/lib/`** : the transverse layer (api, session/perm, table/cursor, form schemas,
  utils). We deliberately keep `lib/` as the core layer instead of adding redundant `core/*`
  re-export barrels (avoids ceremony/indirection for zero gain — YAGNI). New transverse code
  goes in `lib/`.

## Migration (incremental, not big-bang)

Pages migrate into this structure when their sub-project touches them. Pilots: `organization`
and `identity`. Untouched pages keep working under the old flat layout until their turn; a final
sweep documents any page no sub-project reached.
