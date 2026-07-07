# Security follow-ups (open debt)

Tracked, deliberately-deferred security hardening. Each entry: where it lives, the
risk, the recommended fix, and the review/commit that surfaced it. Close an item by
implementing it + deleting its entry here (and its inline `NOTE (SEC-Fx)` marker).

> Convention: sensitive gaps found during a verification pass that are **not**
> immediate blockers are logged here (committed, in-repo) rather than only in a
> gitignored plan or local memory — so any future session finds them from git.

---

## SEC-F2 — provider secret denylist is exact-match + case-sensitive + top-level-only  ·  MED

- **Where:** `packages/backend/app/models/provider.py` — `SECRET_CONFIG_KEYS`,
  `public_config()`, `secret_keys_in()` (and their `ai.providers` cousins
  `public_provider_map()` / `provider_map_secret_keys()`).
- **Risk (leak-half only):** the write-reject (422) and read-strip match secret
  keys by **exact, case-sensitive, top-level** membership. Variants bypass both —
  `API_KEY`, `apikey`, `smtp_password`, `Password`, `aws_secret_access_key`,
  `connection_string`, `dsn`, or a **nested** `config: {extra: {api_key: …}}`.
  A human/script that stores a real secret under such a key persists it plaintext
  and it is echoed to a lower-privileged `provider.read` / `/llm/routing` reader.
  Not a *live* credential injection today (providers read the exact canonical
  lowercase keys), so severity is MED, but it defeats the control with a
  one-character change — the classic denylist weakness.
- **Recommended fix (durable):** **allowlist by `config_schema`.** The backend
  already owns each provider's declared non-secret keys (`Provider.config_schema()`);
  on PUT, reject any `config` key not in the provider's schema for `(capability,
  code)`. Unknown key → reject inverts the risk and closes the case/variant/nested
  gaps structurally. For `ai.providers` (a generic settings blob with no per-entry
  schema), keep the denylist but make it **case-insensitive + substring-aware**
  (careful: `api_key_secret` is a *reference*, must stay allowed).
- **Surfaced by:** independent verification of sub-project A — commit `0662958`,
  PR #32 (F1/F3 fixed; F2 deferred by decision — criticals only).

## SEC-F4 — `ProviderSetting.as_dict()` returns raw `config`  ·  LOW

- **Where:** `packages/backend/app/models/provider.py` — `ProviderSetting.as_dict()`.
- **Risk (fragility, not a live bug):** the "no plaintext secret echoed" invariant
  is enforced by every API caller remembering to wrap the row in `_public()`
  (`admin_providers.py`). Today the only `as_dict()` caller is `_public()` (verified),
  so it is correct — but any future endpoint that returns `as_dict()` directly
  reopens SEC-001.
- **Recommended fix:** make `as_dict()` itself emit `public_config(self.config)`,
  and add an explicit raw accessor (e.g. `as_dict_raw()`) for the legitimate
  internal callers that need real values (`registry.build()`, `check_provider()` —
  which currently read `row.config` directly, not via `as_dict()`).
- **Surfaced by:** commit `0662958`, PR #32 (deferred — LOW).

---

**Next natural window:** sub-project **B (Settings / config-store)** touches the
same config-store zone — fold F2 (schema-allowlist) + F4 in there.
