# Security follow-ups (open debt)

Tracked, deliberately-deferred security hardening. Each entry: where it lives, the
risk, the recommended fix, and the review/commit that surfaced it. Close an item by
implementing it + deleting its entry here (and its inline `NOTE (SEC-Fx)` marker).

> Convention: sensitive gaps found during a verification pass that are **not**
> immediate blockers are logged here (committed, in-repo) rather than only in a
> gitignored plan or local memory — so any future session finds them from git.

---

## SEC-F5 — `settings.read` exposes every config-store value (potential plaintext secret)  ·  LOW

- **Where:** `packages/backend/app/api/admin_settings.py` — `_public_setting` strips
  only the `ai.providers` map; every other setting `value` is returned verbatim to
  any `settings.read` principal.
- **Risk (admin-gated):** an operator who stores a credential as an ordinary string
  value (`smtp.password = "…"`) instead of using `secret_ref` leaks it to all
  `settings.read` holders. Mitigation by design = `secret_ref`; `settings.read` is a
  high-trust admin permission. Frontend rendering is XSS-safe (React-escaped).
- **Recommended fix:** either scan/reject nested-object values for secret-bearing
  keys on write (like the provider path), or formally document `settings.read` as a
  secret-bearing permission and keep it tightly scoped.
- **Surfaced by:** sub-project B security review.

## SEC-F6 — `settings.manage` is a single super-permission over security-critical keys  ·  LOW

- **Where:** `admin_settings.py` (`auth.*`, `ai.routing`, `rbac`, `branding` all
  behind one `settings.manage`); `admin_providers.py` `/check` + `/llm/routing/check`
  trigger outbound requests gated only at router-level `provider.read`.
- **Risk (bounded, all high-perm):** (a) no per-namespace authorization — the
  config-store editor is a privilege-concentration point; (b) SSRF-by-config: a
  `provider.read` user can trigger a probe of a `manage`-configured internal URL; (c)
  `put_setting` validates `value_type ∈ VALUE_TYPES` but not that `value` matches the
  declared type (a JSON object can be stored under a scalar key).
- **Recommended fix:** a protected-key allowlist behind a stronger permission;
  gate `/check` on `provider.manage`; server-side value/type coercion.
- **Surfaced by:** sub-project B security review (design observation, no new bug).

---

Closed:
- **SEC-F2** (provider secret denylist was exact/case-sensitive/top-level) — fully
  fixed. Registered providers: `config` is ALLOWLISTED to the type's `config_schema()`
  keys on write + read (`admin_providers._public` + `registry.schema_keys`), and
  `ai.providers` entries to `AI_PROVIDER_ALLOWED`. Unregistered-code FALLBACK (the
  former residual): the denylist `secret_keys_in`/`public_config` are now
  **case-insensitive + substring + recursive** (`_SECRET_INDICATORS`), so credential
  variants (`API_KEY`, `smtp_password`, `aws_secret_access_key`, nested blobs) are
  rejected on write and stripped on read — closing the residual. Safe to be broad:
  these run only on provider-row config / `as_dict()`, never on `ai.providers`.
  `test_no_registered_schema_declares_a_secret_key` (now using the substring matcher)
  guards against a future schema re-opening the gap (SEC-005).
- **SEC-F4** (`ProviderSetting.as_dict()` returned raw `config`) — fixed: `as_dict()`
  strips via `public_config()`; `as_dict_raw()` for internal raw callers.
- **BFF dropped `If-Match`** (SEC-001, sub-project B review) — the BFF proxy forwarded
  only `{method, body}`, silently voiding optimistic concurrency for every admin write
  end-to-end. Fixed: the BFF now forwards the `If-Match`/`If-None-Match` allowlist.
- **`ai.providers` non-dict shape bypass** (SEC-002) — fixed: `provider_map_shape_ok`
  rejects a non-dict value/entry on write; `public_provider_map` collapses malformed
  shapes to `{}` on read instead of echoing raw.
