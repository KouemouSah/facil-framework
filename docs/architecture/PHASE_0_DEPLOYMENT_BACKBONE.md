# Phase 0 — Backbone Déploiement / Installation / Activation

> Statut : **SPEC — en attente de validation** · Date : 2026-06-11
> Réf. : ADR-0001..0005 · `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md` · `PHASE_C_STORAGE.md`, `PHASE_A5_MODULE_LOADER.md`, `PHASE_D_PROFILES.md`

## 0. Pourquoi Phase 0 d'abord

Pour un **framework** multi-usage hybride, le produit n'est pas les fonctionnalités métier —
c'est le **système qui déploie, installe, active et configure** l'application, de façon
reproductible, idempotente et **auto-validée**. On spécifie et on monte **ce backbone d'abord**,
**sans aucun code métier**. Une fois validé → on rend la config **dynamique** (Studio) → puis on
migre les modules métier depuis `legacy/`.

## 1. Principe directeur (validé)

**Tout provider SÉLECTIONNÉ (par profil + config) s'installe automatiquement, est validé
opérationnel ; l'installation est ATOMIQUE et IDEMPOTENTE, et échoue vite (fail-fast) si un
provider sélectionné ne monte pas.** Aucun provider sélectionné n'est laissé derrière ni à
moitié configuré. *Nuance : les providers sont pluggables/sélectionnables — on n'installe pas
tous les providers possibles, mais tous ceux choisis.*

## 2. Matrice des composants / providers

| Catégorie | Options (pluggables) | Défaut on-prem souverain | Défaut cloud | Présence |
|---|---|---|---|---|
| Base de données | Postgres (+pgvector) | conteneur durci | Cloud SQL / RDS | **toujours** |
| Cache / file | Redis (→ cluster à l'échelle) | conteneur | managé | **toujours** |
| **Stockage fichiers** | **MinIO** (S3-compat) / S3 / GCS(Firebase) / Azure Blob / local-fs(dev) | **MinIO** | GCS | **toujours** (un backend) |
| Inférence LLM | Ollama / vLLM / TGI / Vertex / Bedrock | Ollama → vLLM | Vertex | conditionnel (si IA) |
| Secrets | OpenBao + SOPS / GCP SM / AWS SM / Azure KV | OpenBao(+SOPS) | GCP SM | **toujours** |
| Auth / IdP | natif / Keycloak+AD | natif + Keycloak(agents) | natif | natif **toujours**, Keycloak conditionnel |
| Reverse-proxy / TLS | Caddy / externe (LB) | Caddy + **OpenBao PKI** (step-ca écarté, ADR-0006) | LB cloud | conditionnel |
| Paiement | natif / BANGE / Ecobank / MPGS / Stripe | selon profil | selon profil | conditionnel |
| Observabilité | Sentry / Grafana(OTLP) / LogRocket | optionnel | optionnel | conditionnel |
| Workers | OCR / async / échelle | selon profil | selon profil | conditionnel |

## 3. Ordre d'installation (bootstrap orchestré)

```
[1] Infra services        Postgres, Redis, [Storage], [Inférence], [Secrets], [Proxy]   → health-gated
[2] Résolution secrets    via SecretsProvider sélectionné                                → env / Docker secrets
[3] Bootstrap BD          schéma + migrations (db-init, idempotent)                       → exit 0 requis
[4] Backend               charge UNIQUEMENT les modules activés par le profil             → health-gated
[5] Frontend              (si frontend_enabled)
[6] Post-install          seed, création admin, activation profil                         → idempotent
```
Chaque étape : **health-gated**, **idempotente**, **fail-fast**, et alimente un **rapport de
disponibilité** (`/system/info`).

## 4. Stockage fichiers — MinIO (détail)

`StorageProvider` (ABC) : `put / get / delete / exists / stat / presign`. Impls : `minio`/`s3`
(souverain défaut), `gcs`, `azure_blob`, `local_fs` (dev). Service MinIO dans la stack (image
épinglée, console, **buckets bootstrappés par profil**, policies privées, presigned URLs à TTL,
chiffrement at-rest SSE).

- **Compression dynamique** : politique **par content-type** — compresser texte/JSON/CSV/XML
  (gzip/zstd) ; **ne pas** recompresser formats déjà compressés (JPG/PNG/PDF/ZIP) ; images →
  optimisation optionnelle. Algo stocké en métadonnée → décompression transparente au `get`.
  Seuil de taille minimal (ne pas compresser les très petits objets).
- **Dédup (restriction doublons)** : **adressage par contenu** — clé = `SHA-256(contenu)`. Table
  `file_objects` (`logical_id → content_hash → storage_key, size, mime, refcount, created_at`).
  Upload : si hash existe → `refcount++` + référence (pas de re-stockage). Delete : `refcount--`,
  suppression physique quand `refcount = 0`. (Modèle object-store Git.)

## 5. Interfaces de configuration (en couches)

1. **Install-time** : `deploy/config.yaml` (validé `DeployConfig`) + `init.py --profile=X`
   (**wizard d'installation** : pose les questions, génère config + secrets).
2. **Profil** : `profiles/*/install.yaml` (modules activés, branding, seed, providers recommandés).
3. **Runtime dynamique** (Phase 0.5) : **Studio admin** → modifier la config **sans redeploy**.
4. **Persistance** : tables de config en BD (`system_rules`, provider settings…).

## 6. Activation

Module-loader (active/désactive les modules au boot selon le profil) + **sélection des providers**
(storage, LLM, secrets, auth, payment) + feature flags. Le backend ne **charge** que l'activé.

## 7. Backend minimal *config-aware* (véhicule de validation — PAS de feature)

- `GET /health` — liveness (process up).
- `GET /health/ready` — readiness (BD + cache + storage joignables).
- `GET /system/info` — **profil actif, modules chargés, providers résolus + santé de chacun**,
  version, environnement. C'est la **preuve** que le backbone lit la config, applique le profil et
  installe/valide les providers sélectionnés.

## 8. Validation Phase 0 (Definition of Done)

- [ ] `init.py --profile=empty` génère config + secrets valides
- [ ] `deploy --apply` monte tous les providers **sélectionnés**, health-gated, idempotent (re-run = no-op)
- [ ] `/system/info` liste profil + modules + providers + santé (tous *healthy*)
- [ ] Storage : upload/get OK ; compression appliquée selon content-type ; dédup vérifiée (2 uploads identiques = 1 objet physique)
- [ ] Secrets : aucun en clair ; résolus via le provider sélectionné
- [ ] Re-`apply` = idempotent ; `--down` propre ; volumes préservés
- [ ] Rapport critique Phase 0

## 9. Reséquencement du plan

```
Phase 0   Backbone déploiement/install/activation (+ providers auto, storage MinIO)   [CE SPEC]
Phase 0.5 Config dynamique (Studio minimal : rendre la config opérationnelle/admin)
Phase 1+  Migration des modules métier depuis legacy/ (auth, users, … un par un)
```
