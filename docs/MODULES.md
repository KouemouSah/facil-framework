# Modules — activation & manifeste de ressources

Le framework livre chaque module métier sous forme de code ; un déploiement en
active un sous-ensemble via `MODULES_ENABLED` (rendu depuis `config.yaml
modules.enabled`). Ce document décrit le **manifeste de module** et la
**réconciliation de ressources** au boot (Phase 1bis, cadre ADR-0010).

## Manifeste de module (opt-in)

Un module peut déclarer ses besoins de ressources dans
`app.modules.<name>.manifest` :

```python
from app.core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    config_defaults={"billing.invoice_prefix": "INV"},  # seedés dans le config-store
    required_secret_keys=["BILLING_API_KEY"],           # validés (jamais forgés)
    required_buckets=["billing-invoices"],              # ensured via le provider storage
    depends_on=["organization"],                         # info (documentaire pour l'instant)
)
```

Tout est **optionnel** et **rétro-compatible** : un module sans `manifest` garde
le comportement actuel (inclusion de routers seulement).

## Réconciliation au boot

À chaque boot, pour chaque module activé qui déclare un manifeste
(`reconcile_module_resources`, non-fatal, rapport dans `/health`) :

| Besoin | Traitement | Pourquoi |
|---|---|---|
| `config_defaults` | **seed** dans le config-store **si la clé est absente** | jamais de surcharge d'un choix admin/runtime ; idempotent |
| `required_secret_keys` | **validation** via le SecretsProvider actif ; manquant → signalé (loud) | un runtime **ne peut pas forger** un secret — c'est la couche deploy/vault qui le provisionne |
| `required_buckets` | **`ensure_bucket`** via le StorageProvider actif (best-effort) | création idempotente ; échec capturé, non-fatal (voir buckets ci-dessous) |

**Frontière (ADR-0010)** : le module **déclare** ; le provider **système** (un seul
MinIO/OpenBao/… pour tout le déploiement) **exécute**. Un module ne configure jamais
son propre provider.

## Buckets : deux couches coopérantes (sécurité)

Le StorageProvider souverain (MinIO) donne au backend un **service account
least-privilege** dont la policy n'autorise que les buckets déclarés. Créer un
bucket au runtime via ce SA échoue **par conception** (pas de `CreateBucket`, pas
d'accès hors policy). D'où **deux couches** :

1. **Bootstrap deploy (voie sécurisée, MinIO)** — l'opérateur liste les buckets dans
   `config.yaml` :
   ```yaml
   storage:
     minio:
       module_buckets: ["billing-invoices"]
   ```
   Le bootstrap les **crée** (creds root, versionnés/privés) **et les autorise** (rw)
   dans la policy du SA backend. Sans cette autorisation, un bucket resterait
   **inaccessible** au backend.
2. **Runtime `ensure_bucket` (agilité dynamique, tous providers)** — le reconcilieur
   appelle `ensure_bucket` sur le provider actif. Sur MinIO, le bucket existe déjà
   (créé en couche 1) → no-op idempotent. Sur un provider à creds larges (S3 IAM
   permissif, memory) → création dynamique directe.

**Relation des deux sources** : `manifest.required_buckets` = le besoin du module
(source de vérité fonctionnelle, pilote le runtime) ; `config.yaml
storage.minio.module_buckets` = l'autorisation/pré-création explicite côté opérateur
(sécurité, least-privilege). Pour un déploiement MinIO souverain, **les buckets du
manifeste doivent figurer dans `module_buckets`** ; sinon le backend ne pourra pas
les atteindre. *(Amélioration future : une garde de cohérence
`module_buckets ⊇ ⋃ required_buckets`.)*

## Knobs d'activation (boot)

| Env | Défaut | Effet |
|---|---|---|
| `MODULES_ENABLED` | (profil) | modules dont les routers sont montés |
| `MODULE_RESOURCES_ON_BOOT` | `1` | réconciliation des manifestes au boot (`0` = off) |
| `PROVIDERS_SEED_ON_BOOT` | `1` | seed des providers système par défaut (storage/email) |
