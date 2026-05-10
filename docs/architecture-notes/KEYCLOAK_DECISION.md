# Architecture Decision — Keycloak as optional auth provider, not replacement

> **Status** : decided 2026-05-10
> **Audience** : tech-leads, security-auditors, operators evaluating IAM strategy for Facil deployments
> **Context** : raised during planning of treasury V1.1 capabilities — should Facil Framework replace its internal JWT-based auth with Keycloak (open-source IAM platform) to facilitate enterprise / gov deployments?

## Decision

**Keep internal JWT as default, add Keycloak as optional provider.** Do NOT replace.

## Reasoning

### Why Keycloak is attractive

- Mature LDAP/AD federation (better than rolling our own with `ldap3`)
- SAML 2.0 + OIDC IdP both included
- Production-grade MFA (TOTP, WebAuthn, SMS plugin, recovery codes)
- Account linking / identity brokering (one user = LDAP + Google + cert smart card)
- Group/role/permission mapper UI (replaces J.7 + J.12 extensions)
- Multi-tenant via realms (1 realm per ministry possible)
- Themes / i18n / login customization
- Admin console for IT staff (no need to build Studio cert/role mgmt UI from scratch)
- Token introspection, refresh rotation, etc. — battle-tested
- Reduces Facil's surface area for security audits (delegate to mature Apache 2.0 project backed by Red Hat)
- Free (Apache 2.0)

### Why NOT making Keycloak mandatory

#### Operational complexity
- Java/Quarkus runtime + JVM tuning required
- Separate process to deploy, monitor, upgrade independently
- Adds an SPF (single point of failure) — auth down = portal down
- ~512 MB RAM minimum, scales with concurrent sessions
- Requires its own database (or shared schema with Facil = coupling)

#### Developer experience degradation
- Every dev needs Keycloak running locally → slows iteration
- Local Keycloak + local Postgres + local Redis + local backend + local frontend = heavy stack for laptop
- Hot-reload broken if Keycloak config changes require restart

#### Latency overhead
- Every auth check = HTTP call to Keycloak (10-50ms)
- Token introspection on every API request adds compounding cost
- Embedded JWT = zero network hop, sub-ms validation

#### Abstraction leakage
- Facil Studio UI would expose Keycloak-specific concepts (realms, clients, mappers)
- Operator must learn TWO admin UIs (Facil Studio + Keycloak Console)
- Documentation surface explodes (Facil docs + Keycloak docs)

#### Customization friction
- Keycloak themes are FreeMarker templates — different stack from Facil's Next.js
- UX hop : Facil portal → redirect Keycloak login → redirect back
- Branding consistency requires syncing themes across two systems

#### Migration cost
- Existing TaxasGE users would need migration to Keycloak (non-trivial)
- Token format changes (JWT signed by Facil → JWT signed by Keycloak)
- Session migration (revoke old, issue new)

#### Compliance complexity
- Keycloak audit logs separate from Facil audit logs
- Need bridging for unified audit trail
- ENS / SOC2 / ISO 27001 audit becomes 2-system audit (vs 1 for embedded auth)

#### Profile philosophy mismatch
- Facil Open Core promise : « lightweight default, options for enterprise »
- Mandating Keycloak would push Facil from « zero-config framework » to « IAM-platform-required framework »
- Different profiles want different auth UX (banking ≠ gov ≠ saas)
- Forcing Keycloak forces ALL profiles to inherit its constraints

### Where Keycloak does NOT help

For the treasury V1.1 capabilities (Phases O / P / Q / R / S / T), Keycloak adds **zero value**. It only helps with **M7 (AD/SSO)** of PIMEPE. The remaining 7 modules (ERP, audit chain, signature, numbering, banking, adapters, PWA) are completely independent of auth choice.

So « Keycloak facilitates the new modules » is **not technically true** — it only facilitates ONE of them, and even then only marginally vs. our own LDAPProvider extension (which is ~3-5 days of work and produces a tightly integrated component).

## Hybrid approach (decided)

### Phase J baseline (already planned)
- JWT internal (default, lightweight, embedded)
- OAuth Google / Microsoft
- SAML 2.0 (federation with external IdPs)
- Magic link
- OTP SMS

### Phase J extension TREASURY (already planned)
- LDAP/AD direct (LDAPS via ldap3, multi-tenant, group RBAC)
- AD attribute mapping

### Phase J extension KEYCLOAK (planned, ~2-3 days, NEW)
- `KeycloakProvider(AuthProvider)` — OIDC client to external Keycloak instance
- Group/role mapping from Keycloak claims to Facil RBAC
- Studio UI : « Use Keycloak instance » toggle + base URL + realm + client ID/secret config
- Documentation : when to use, deployment guide, troubleshooting

### Profile recommendations

| Profile | Recommended auth |
|---|---|
| `empty` | JWT |
| `private-services-company` | JWT or OAuth |
| `gov-emergent-country` | LDAP direct (small gov), Keycloak (100+ agents, multi-AD) |
| `saas-multitenant` | OAuth + JWT |
| `banking` | LDAP direct OR Keycloak (depends on bank IT) |

For `gov-emergent-country` specifically :
- **Default** in `install.yaml` : `auth.primary: jwt` (works out of the box)
- **Recommended** for production deployments with 100+ agents : Keycloak (documented in `docs/KEYCLOAK_SETUP.md`)
- **Pragmatic intermediate** : LDAP/AD direct (no Keycloak ops burden, still federates with AD)

## Alternative considered and rejected

### Alternative A : Replace JWT with Keycloak entirely
**Rejected** because :
- Forces ALL Facil deployments (small + enterprise) to run Keycloak
- Slows down dev environment significantly
- Lock-in : if Keycloak project changes direction or Red Hat shifts strategy, hard to migrate back
- Kills Facil's « zero-config » value prop for small deployments

### Alternative B : Use Ory Hydra / Kratos instead
**Rejected** because :
- Less mature LDAP federation than Keycloak
- Smaller community
- Requires more glue code (Hydra = OAuth server only, Kratos = identity, separate)
- Same operational complexity as Keycloak without same maturity

### Alternative C : Use Auth0 / Okta / Cognito
**Rejected** because :
- Not open-source / not free
- Vendor lock-in
- Cloud-only (some gov deployments are on-prem only)
- Cost scales with users (problematic at 1M+ citizens)

### Alternative D : Don't add Keycloak at all
**Rejected** because :
- Some operators legitimately want it
- LDAP/AD direct extension covers 80 % but not 100 % (no centralized IAM admin UI)
- Easier to add now (small phase, ~2-3 days) than retrofit later
- Doesn't add cost if not enabled (gated by `install.yaml` toggle)

## Implementation roadmap

| Step | Phase | Effort | Status |
|---|---|---|---|
| Add `KeycloakProvider` class | New Phase J extension | ~2-3 days | 📋 To plan after validation |
| Studio UI Keycloak config tab | Phase J extension | (included above) | 📋 To plan |
| `docs/KEYCLOAK_SETUP.md` per profile | Phase M | Already drafted in `gov-emergent-country/docs/` | ✅ Done 2026-05-10 |
| Architecture decision note (this doc) | — | — | ✅ Done 2026-05-10 |

## Re-evaluation triggers

This decision should be re-evaluated if :
- Keycloak adds an embedded mode (« run inside main process ») — would eliminate ops complexity
- Facil Cloud (managed SaaS) is launched — could ship Keycloak managed, removing dev burden
- A major customer mandates Keycloak as contractual requirement (case-by-case, not framework default)
- Java ecosystem becomes default in Facil (currently Python — not foreseen)

## See also

- `profiles/gov-emergent-country/docs/KEYCLOAK_SETUP.md` — operator-facing setup guide
- `.claude/plans/phases/PHASE_J_AUTH_PROVIDERS.md` — Phase J baseline (gitignored, internal)
- `.claude/plans/phases/PHASE_J_TREASURY_EXTENSIONS.md` — LDAP/AD direct extension (gitignored, internal)
- [Keycloak project](https://www.keycloak.org/)
