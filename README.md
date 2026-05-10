# Facil Framework

> ⚠️ **Statut : pré-bootstrap** — environnement préparé, dev pas encore démarré.
> Le démarrage actif est conditionné au go-live de TaxasGE (le déploiement de référence).

**Facil Framework** est un framework générique de services digitaux (gov, entreprise privée, multi-tenant SaaS, banking, télécom, e-commerce, RH, immobilier...) déployable sur n'importe quel cloud ou en local, et **customisable sans code** par des utilisateurs non-techniques via une UI admin dédiée.

## Origine

Cloné en snapshot du déploiement concret **TaxasGE** (Guinée Équatoriale gov digital services, repo séparé `C:\taxasge\`) en date du 2026-05-10.

Aucun lien Git, ni submodule, ni symlink avec TaxasGE. Les deux repos évoluent indépendamment. Diffusion d'améliorations infrastructure se fait par cherry-pick manuel via `tools/sync-from-taxasge.sh` (à créer).

## Vision

- **Tous les modules** backend inclus, **activables/désactivables** au boot via config `MODULES_ENABLED`
- **5 profiles pré-faits** : `gov-emergent-country`, `private-services-company`, `saas-multitenant`, `banking`, `empty`
- **Customization Studio** UI admin pour personnaliser sans code : branding, langues, RBAC, taxonomies, catalogue, workflows, providers (LLM/Storage/Payment/Auth)
- **Default cloud-privé / on-prem** : Ollama (LLM + embeddings), Postgres+pgvector, MinIO storage. Zéro cloud externe requis.

## Modèle économique

**Open Core + Cloud SaaS hybride** :
- `Facil Framework` (AGPL-3.0, gratuit, self-hosted) — ce repo
- `Facil Cloud` (SaaS payant sur facil.io) — futur
- `Facil Enterprise` (license commerciale, SSO SAML/AD, multi-tenant strict, support 24/7) — futur

## Plans détaillés

Documents internes (gitignored) — voir `.claude/plans/` :

| Plan | Scope |
|---|---|
| `VOIE_B_FRAMEWORK_PLAN.md` | Plan parent — 18 phases A→M, 123-178j dev, ~8 mois 1 FTE |
| `LLM_ABSTRACTION_PLAN.md` | Sous-plan LLM swap (Gemini/Claude/Mistral/OpenAI/Ollama) |
| `EMBEDDING_RAG_ABSTRACTION_PLAN.md` | Sous-plan RAG provider-agnostic |

Ainsi que `docs/PRD.md` (Product Requirements Document, public).

## Pré-requis avant lancement actif

1. ✅ TaxasGE en prod stable depuis 1+ mois
2. ⏳ Trademark "Facil" vérifié (USPTO, EUIPO, OAPI)
3. ⏳ Équipe : 1 dev FTE sur 8 mois OU 2 devs sur 4-5 mois
4. ⏳ Setup business : société, domaine `facil.io`, infrastructure Cloud
5. ⏳ Décisions stratégiques validées (cf. PRD §11)

## Pour démarrer (futur)

```bash
git clone <facil-framework-repo>
cd facil-framework

# Phase 1 — Module Loader mechanism
# Phase 2 — LLM + Embedding abstractions
# Phase 3 — Profile templates
# Phase 4 — Customization Studio
# ... voir VOIE_B_FRAMEWORK_PLAN.md
```

## License

AGPL-3.0 (Affero GPL) — voir `LICENSE`.

Pourquoi AGPL et pas MIT : empêcher fork hostile cloud (cf. Elastic vs OpenSearch AWS). Tout SaaS hébergeur doit ouvrir ses modifications.

Pour un usage commercial sans contrainte AGPL, contacter pour Facil Enterprise license.
