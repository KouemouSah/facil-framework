# Security follow-ups (open debt)

Tracked, deliberately-deferred security hardening. Each entry: where it lives, the
risk, the recommended fix, and the review/commit that surfaced it. Close an item by
implementing it + deleting its entry here (and its inline `NOTE (SEC-Fx)` marker).

> Convention: sensitive gaps found during a verification pass that are **not**
> immediate blockers are logged here (committed, in-repo) rather than only in a
> gitignored plan or local memory — so any future session finds them from git.

---

_No open items._

---

Closed:
- **SEC-F5** (`settings.read` could expose a plaintext secret stored as a setting
  value) — fixed: `put_setting` rejects a dict value carrying a secret-bearing key
  and a scalar under a credential-named key (exact last-segment, e.g. `smtp.password`)
  — credentials go via `secret_ref`. `_public_setting` strips nested secret keys from
  dict values and masks a legacy credential-keyed scalar on read.
- **SEC-F6** — fixed all three: (a) security-critical namespaces (`auth.*`, `rbac`,
  `security.*`) now require the elevated `settings.manage_protected` permission via an
  in-handler `enforce()` (break-glass / global-`*` admin still pass); (b) the
  outbound-probe endpoints `/{cap}/{code}/check` + `/llm/routing/check` are
  `provider.manage`-gated (SSRF-by-config); (c) `put_setting` validates that `value`
  matches its declared `value_type` (no JSON object smuggled under a scalar key).
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
