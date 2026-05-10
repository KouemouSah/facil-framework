# Profile — `gov-emergent-country`

> **Status** : 🚧 SKELETON (pre-bootstrap). Phase D will populate seeds, workflows, and tests. Treasury V1.1 phases (O→T + extensions on J/N.5) will activate the treasury features below.
> **Target use case** : digital service portals for emerging-country governments — fiscal services, treasury, citizen administration, multi-directional collaboration.
> **Reference deployment** : TaxasGE (Equatorial Guinea fiscal services platform).
> **Treasury V1.1 ready** : adds capabilities for treasury / public payment portals (TDR-PIMEPE-class : ERP integration, immutable audit chain, qualified signature, ISO 20022 banking, AD federation, government numbering schemes).

## What this profile includes (when fully populated)

### Core (V1)
- Authentication : JWT default + LDAP/AD direct + SAML 2.0 + Keycloak optional (recommended for 100+ agents)
- Multilingual UI : Spanish (primary), French (regional), English (international)
- Multi-tenant ready (1 deploy = 1 country, 1 tenant per administration if needed)
- Document workflows (forms, OCR, signatures)
- Mobile companion app (Expo / React Native, optional)
- Inspector tablet app (field operations, optional)
- AI chatbot (Gemini / Ollama / LLM provider abstraction)
- Audit logs append-only

### Treasury V1.1
- **ERP connector** : Sage X3 (REST v12+ / SOAP v9-v11) — extensible to SAP, Oracle, Odoo
- **Immutable audit chain** : PostgreSQL hash chain + Trillian + Sigstore Rekor + co-signature 3 authorities (Hyperledger Fabric alternative — see `docs/architecture-notes/HYPERLEDGER_ALTERNATIVES.md`)
- **Qualified signature** : PAdES + XAdES via AATL providers (DigiCert / GlobalSign / Sectigo / Entrust) + RFC 3161 TSA + OCSP real-time (alternative to national qualified TSP — see `docs/architecture-notes/EIDAS_ALTERNATIVES.md`)
- **Government numbering schemes** : module 11 (IUI/IUG-style PIMEPE), Luhn, SIRET, RCCM-OHADA, NIF-ES — extensible
- **Public accounting catalog** : PCE-GE template (Equatorial Guinea), extensible to PCG-FR, OHADA SYSCOA, etc.
- **ISO 20022 banking** : pain.001 / camt.053 / camt.054 + MT940 fallback for banks not yet ISO 20022 ready
- **External system adapters** : SIGREF / SYDONIA / CONTFIN-style (REST polling, REST webhook, SOAP/XML) + OpenAPI spec generator
- **PWA offline** : service worker + IndexedDB queue + background sync (for low-connectivity zones)
- **Recours / claims workflow** : citizens can submit administrative appeals or installment payment requests
- **In-app training** : guided tooltips (Joyride) + embedded video player + LMS-light progress tracking
- **Auth federation extensions** : multi-AD (5 directions = 5 directories), group-based RBAC mapping (AD groups → Facil roles), AD attribute mapping (employee ID, department, function)

## Quick start (post-Phase D bootstrap)

```bash
# From facil_framework repo root
python deploy/init.py --profile=gov-emergent-country --interactive
```

The wizard will prompt for :
1. Country / language defaults (es / fr / en)
2. Authentication backend (JWT internal / LDAP direct / SAML / Keycloak)
3. Treasury features to activate (ERP / audit chain / ISO 20022 / etc.)
4. Branding (logo, colors)
5. Database connection (Supabase / RDS / Cloud SQL / Neon / docker-local)

Result : `deploy/config.yaml` + `.env.secrets` generated, ready to deploy.

## Pre-deployment audit

Before deploying for a new country, complete the pre-project audit checklist :
[`/docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md`](../../docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md) (9 sections : ERP, banks, AD/SSO, legal framework, infrastructure, skills).

## File layout

```
gov-emergent-country/
├── README.md                          ← you are here
├── install.yaml                       ← central profile config (modules + features + providers)
├── branding/
│   └── theme.json                     ← color tokens + typography (extends Facil default)
├── i18n/
│   ├── es.json                        ← Spanish (primary)
│   ├── fr.json                        ← French (regional)
│   └── en.json                        ← English (international)
├── seed_data/
│   ├── numbering_schemes/             ← templates for IUI/IUG/NIF/SIRET/RCCM
│   ├── public_accounting_catalogs/    ← PCE-GE template (real codes to be filled by operator)
│   ├── workflow_templates/            ← recettes / dépenses / recours / réclamations
│   └── document_templates/            ← PAdES-signable PDF templates (Phase N library)
├── docs/
│   ├── DEPLOYMENT_CHECKLIST.md        ← deployment-time gov-specific checks
│   └── KEYCLOAK_SETUP.md              ← optional Keycloak federation setup
└── tests/
    └── README.md                      ← E2E scenarios for this profile (Phase L)
```

## What this profile is NOT

- ❌ Not a complete TaxasGE clone — Phase D will port reusable seeds, but real-country deployments require their own seeds
- ❌ Not pre-certified ISO 27001 / eIDAS / ENS — these are organizational certifications independent of code
- ❌ Not a substitute for legal / fiscal / accounting expertise — operator must validate accounting catalog with public-accounting expert
- ❌ Not a turnkey treasury portal — treasury V1.1 features are activatable but require pre-project audit + ERP/bank credentials + AC qualified or AATL certificate procurement

## Roadmap

| Component | Status | Triggered by |
|---|---|---|
| Skeleton structure | ✅ Done 2026-05-10 | this commit |
| `install.yaml` schema validation | 📋 Planned | Phase D |
| Seeds (numbering, accounting, workflows) | 📋 Planned | Phase D + Phase Q |
| TaxasGE seed importer | 📋 Planned | Phase D.4.a |
| Treasury features wiring | 📋 Planned | Phases O / P / Q / R / S / T + extensions J / N.5 |
| E2E tests | 📋 Planned | Phase L |

## Contributing

This profile is part of Facil Framework Open Core (AGPL-3.0). Contributions welcome via PRs to `facil-framework` repo. Country-specific seeds (PCE-GE, RCCM-OHADA codes) should be community-contributed and reviewed by relevant accounting experts.
