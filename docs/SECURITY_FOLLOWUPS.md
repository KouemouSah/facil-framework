# Security follow-ups (open debt)

Tracked, deliberately-deferred security hardening. Each entry: where it lives, the
risk, the recommended fix, and the review/commit that surfaced it. Close an item by
implementing it + deleting its entry here (and its inline `NOTE (SEC-Fx)` marker).

> Convention: sensitive gaps found during a verification pass that are **not**
> immediate blockers are logged here (committed, in-repo) rather than only in a
> gitignored plan or local memory — so any future session finds them from git.

---

_No open items._

Closed:
- **SEC-F2** (provider secret denylist was exact/case-sensitive/top-level) — fixed in
  sub-project B (`feat/settings-configstore`): provider `config` is now ALLOWLISTED to
  the type's `config_schema()` keys on write + read (`admin_providers._public` +
  `registry.schema_keys`), and `ai.providers` entries to `AI_PROVIDER_ALLOWED`
  (`admin_settings` + `public_provider_map`). Denylist kept only as the unregistered
  fallback. Closes case/variant/nested structurally.
- **SEC-F4** (`ProviderSetting.as_dict()` returned raw `config`) — fixed: `as_dict()`
  now strips via `public_config()`; `as_dict_raw()` added for the internal callers
  that need raw values.
