# Roadmap

> Public roadmap for Facil Framework. Detailed phase plans live in `.claude/plans/phases/` (internal, gitignored). This file is the public-facing summary.

## Status: 🚧 Pre-bootstrap

Active development has not yet started. The framework is undergoing planning and architectural design.

**Conditions to start active development**:

- TaxasGE (the reference deployment) reaches production stability
- Trademark "Facil" verified on USPTO / EUIPO / OAPI markets
- Team recruited (1 FTE for ~8 months OR 2 devs for ~4-5 months)
- Domain `facil.io` acquired
- Business setup complete (legal entity, cloud infrastructure)

## Total scope

- **V1** : **144 – 209 days** of focused development (~7-10 months at 1 FTE, or 4-6 months at 2 devs)
- **V1.1** : **+44 – 68 days** for treasury / government payment capabilities (Phases O → T + extensions on Phase J / Phase N.5) → **188 – 277 days** total (~9-14 months at 1 FTE, or 5-7 months at 2 devs)

## Phase overview (A → N.5)

### Foundations

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| A | Bootstrap | 2j | ✅ Done 2026-05-10 |
| A.5 | Module Loader | 5-7j | 📋 Next |
| B | LLM Abstraction | 5-7j | 📋 Planned |
| B.5 | Payment Gateway Abstraction | 4-6j | 📋 Planned |
| B.6 | Embedding / RAG Abstraction | 32-45j | 📋 Planned |
| C | Storage Abstraction | 3-5j | 📋 Planned |

### Profiles & Studio Backend

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| D | Profile templates × 5 | 6-9j | 📋 Planned |
| E | Customization Studio backend | 4-6j | 📋 Planned |

### Studio UI

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| F | Studio UI — Branding / Languages / RBAC | 5-7j | 📋 Planned |
| G | Studio UI — Taxonomies / Catalog | 5-7j | 📋 Planned |
| H | Workflow Designer ⭐ R&D | 15-25j | 📋 Planned |
| H.5 | Module Manager UI | 2-3j | 📋 Planned |
| I | Studio UI — Providers (LLM/Storage/Payment/Auth/Deploy) | 5-7j | 📋 Planned |
| I.bis | Studio UI — Knowledge Base | 5-7j | 📋 Planned |

### Auth & Apps

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| J | Auth Providers (JWT / OAuth / SAML / Magic / OTP) | 7-10j | 📋 Planned |
| K | Mobile + Inspector adaptations | 5-7j | 📋 Planned |

### Documents

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| N | Document Designer + Schemas | 15-22j | 📋 Planned |
| N.5 | Document Signature (LocalCA + Cloud) | 6-9j | 📋 Planned |

### Tests & Documentation

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| L | E2E tests per profile | 7-10j | 📋 Planned |
| M | Documentation + tutorials per profile | 7-10j | 📋 Planned |

### Treasury / Government Payment Capabilities (V1.1)

> Added 2026-05-10. Triggered by analysis of TDR PIMEPE (Equatorial Guinea Treasury Portal RFP, December 2025). These phases enrich the `gov-emergent-country` profile with capabilities required to respond to government treasury / payment portal RFPs in CEMAC, UEMOA, OHADA, Maghreb regions. **Total : 44-68 days** (6 new phases + 2 extension plans on Phase J / Phase N.5), increasing V1 scope by ~25-35 % (V1: 144-209d → V1.1: 188-277d). Detailed plan : [`TREASURY_CAPABILITIES_UPGRADE_PLAN.md`](.claude/plans/TREASURY_CAPABILITIES_UPGRADE_PLAN.md) (gitignored, internal).

| Phase | Name | Effort | Status |
|-------|------|--------|--------|
| **J ext** | Auth providers — LDAP/AD direct + multi-AD + group RBAC mapping | +3-5j | 📋 Planned (V1.1 ext) |
| **N.5 ext** | Document signature — AATL provider + XAdES + OCSP real-time | +3-5j | 📋 Planned (V1.1 ext) |
| O | ERP Connector Abstraction (Sage X3 first) | 8-12j | 📋 Planned (V1.1) |
| P | Immutable Audit Chain (Postgres + Trillian + Sigstore Rekor) | 5-8j | 📋 Planned (V1.1) |
| Q | Government Numbering & Public Accounting (PCE-GE, IUI/IUG, NIF, SIRET, RCCM) | 5-7j | 📋 Planned (V1.1) |
| R | ISO 20022 Banking Gateway (pain.001, camt.053/054 + MT940 fallback) | 6-9j | 📋 Planned (V1.1) |
| S | External System Adapters Framework (REST polling/webhook + SOAP + OpenAPI generator) | 5-8j | 📋 Planned (V1.1) |
| T | PWA Offline + Recours Workflow + Formation In-App | 9-14j | 📋 Planned (V1.1) |

**Architecture notes** (technical references for treasury contexts):

- [Hyperledger Alternatives](docs/architecture-notes/HYPERLEDGER_ALTERNATIVES.md) — TCO 5-year comparison Hyperledger Fabric vs Postgres hash chain + Trillian + Rekor
- [eIDAS Alternatives](docs/architecture-notes/EIDAS_ALTERNATIVES.md) — phased approach for countries without national qualified TSP (AATL → national CA → ETSI audit)
- [Pre-project Audit Checklist](docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md) — to scope ERP / banks / AD / legal framework / infrastructure / skills before quoting

## Critical path

The critical path runs through the foundations: A → A.5 → B → B.6 → D → E → H → L → M.

Phase **B.6 (Embedding / RAG Abstraction)** is the longest single phase (32-45 days). Phase **H (Workflow Designer)** is the highest R&D risk (15-25 days, may extend).

## Tiered delivery

Facil Framework follows an **Open Core + Cloud SaaS hybrid** model.

### Open Core (this repo, AGPL-3.0)

All phases A → N.5 land here. Free, self-hosted, AGPL.

### Facil Cloud (planned, hosted on facil.io)

Managed hosting with usage-based pricing. Built on top of Open Core. Targets teams who want to skip operations.

### Facil Enterprise (planned, commercial license)

For large customers needing:

- SSO via SAML / Active Directory
- Strict multi-tenancy isolation
- 24/7 SLA support
- Custom modules and integrations
- Audit certifications (SOC2, ISO 27001)

## Profile readiness

| Profile | Use case | Status |
|---------|----------|--------|
| empty | Build from scratch | 📋 Planned (Phase D) |
| private-services-company | B2B services platform | 📋 Planned (Phase D, MVP target) |
| gov-emergent-country | Government digital services | 📋 Planned (Phase D, ports TaxasGE) |
| saas-multitenant | Multi-tenant SaaS | 📋 Planned (Phase D) |
| banking | KYC + lending workflows | 📋 Planned (Phase D, MVP scope) |

## How to follow progress

- ⭐ Star this repo for release notifications
- 👀 Watch for new releases
- 📋 Check open milestones for active phases
- 💬 Discussions for design conversations
- 📝 CHANGELOG for shipped changes

## How to influence the roadmap

Open a [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) or start a [Discussion](https://github.com/KouemouSah/facil-framework/discussions). The roadmap is reviewed quarterly.

Items currently out of scope (may revisit post-V1):

- Multimodal embeddings (vision / audio)
- Real-time collaboration on workflows
- Distributed RAG indexing
- WebAuthn passwordless login
- Smart card / HSM integration
- Notary integration for qualified signatures
- App store auto-publish
