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

**144 – 209 days** of focused development to reach V1 (~7-10 months at 1 FTE, or 4-6 months at 2 devs).

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
