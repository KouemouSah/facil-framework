# ADR-0005 — Stockage fichiers : abstraction S3 + MinIO souverain (compression + dédup)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : `PHASE_C_STORAGE.md`, `docs/architecture/PHASE_0_DEPLOYMENT_BACKBONE.md`, ADR-0003

## Context

Le stockage de fichiers (documents, reçus PDF, uploads, vault) doit être **souverain** en
on-premise (données non sortantes) et **portable** en cloud. Le legacy utilise Firebase Storage
(GCS). Besoin exprimé : équivalent **local** type « Firebase local », + **compression dynamique**
et **restriction des doublons**.

## Decision

- **Abstraction `StorageProvider`** (`put/get/delete/exists/stat/presign`) avec impls :
  **`minio`/`s3`** (souverain, défaut on-prem), `gcs` (Firebase/cloud), `azure_blob`, `local_fs`
  (dev). Sélectionnable par config/profil.
- **On-prem souverain → MinIO** (S3-compatible, self-hosted) comme service de la stack, buckets
  bootstrappés par profil, privés, presigned URLs à TTL, chiffrement at-rest.
- **Compression dynamique** : politique par content-type (compresser texte/JSON/CSV/XML ; ne pas
  recompresser JPG/PNG/PDF/ZIP). Algo en métadonnée, décompression transparente.
- **Dédup par adressage-contenu** : clé = `SHA-256(contenu)`, table `file_objects` avec
  `refcount` ; un contenu identique n'est stocké qu'une fois ; suppression physique à `refcount=0`.

## Consequences

**Positives** : souveraineté (MinIO local), portabilité (même interface en cloud), économie de
stockage (dédup), bande passante/stockage réduits (compression), zéro réécriture applicative au
changement de backend.

**Négatives / risques** : MinIO est un service à opérer (HA, sauvegarde — cf P13) ; la dédup ajoute
une table + une logique de refcount à tester rigoureusement (corruption de refcount = fuite ou
suppression prématurée).

## Alternatives — rejetées

- **Firebase/GCS partout** — *rejeté* comme défaut souverain (données sortantes). Conservé en cloud.
- **Stockage filesystem nu** — *rejeté* (pas d'API S3, pas de presign, pas scalable).
