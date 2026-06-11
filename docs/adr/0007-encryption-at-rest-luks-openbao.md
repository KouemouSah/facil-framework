# ADR-0007 — Chiffrement at-rest souverain (LUKS volumes + clé custodiée OpenBao)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : ADR-0003 (secrets & cloud), ADR-0005 (storage MinIO), ADR-0006 (k3s + PKI interne), `docs/architecture/DATAPLANE_BOOTSTRAP.md`, `.claude/plans/MINIO_SECURITY_ARCH_PLAN.md`

## Context

Le socle souverain doit chiffrer les données **au repos** (MinIO objets, Postgres,
secrets OpenBao persistés) pour les déploiements on-prem/VPS. L'approche
« cloud-native » envisagée était le **SSE-S3 de MinIO via KES → OpenBao** (KES
comme middleware KMS, OpenBao comme keystore).

La vérification de la doc officielle (2026-06-11) **invalide cette voie** pour un
socle **AGPL souverain à viabilité long-terme** :

- `minio/kes` (Key Encryption Server **Community Edition**) est **officiellement
  déprécié** (le dépôt GitHub porte la mention « [Deprecated] »).
- Son remplaçant « MinIO KMS / MinKMS » est livré sous **licence Enterprise
  (AIStor)** → lock-in propriétaire incompatible avec l'Open Core AGPL.
- Le SSE-S3 *objet* de MinIO community **dépend obligatoirement** d'un KMS
  configuré via les variables KES ; `MINIO_KMS_SECRET_KEY` ne couvre pas (de
  façon documentée) le chiffrement des objets.
- Best practice souveraine 2026 (y compris doc MinIO) : **clés séparées des
  données**, custodiées dans Vault/OpenBao, récupérées au boot.

## Decision

1. **Le chiffrement at-rest se fait au niveau VOLUME (deployment-layer), pas au
   niveau objet via KES.** Chaque volume de données (MinIO, Postgres, OpenBao)
   est chiffré par **LUKS/dm-crypt** sur le serveur souverain (VPS/bare-metal/k3s).

2. **La clé LUKS est custodiée dans OpenBao**, jamais stockée sur le volume
   qu'elle protège. Au boot, l'hôte s'authentifie auprès d'OpenBao (AppRole) et
   récupère la passphrase pour déverrouiller le volume. OpenBao reste donc le
   **gardien souverain des clés qui chiffrent MinIO** — l'objectif d'intégration
   MinIO↔OpenBao est atteint, au niveau volume.

3. **KES / MinIO KMS Enterprise sont abandonnés.** Aucune dépendance à un
   composant déprécié ou propriétaire.

4. **Périmètre.** C'est un sujet **production on-prem (VPS/k3s)**. En dev Docker
   Desktop, le volume vit dans la VM Docker → LUKS n'est pas applicable :
   **no-op documenté** en dev. La défense applicative MinIO (WORM/Object-Lock,
   rétention, lifecycle, quotas, SA scopés — cf. `DATAPLANE_BOOTSTRAP.md`) reste
   active dans tous les environnements.

## Runbook (cible VPS/k3s — résumé d'implémentation)

1. Provisionner un volume dédié aux données (ex. `/dev/sdb`).
2. `cryptsetup luksFormat /dev/sdb` avec une passphrase forte générée.
3. Écrire la passphrase dans OpenBao : `bao kv put facil/luks/<host> passphrase=…`.
4. Au boot (unité systemd `before` les services, ou hook initramfs / k3s
   `StorageClass` chiffrée) : AppRole login → lecture de la passphrase →
   `cryptsetup luksOpen` → montage sous le point utilisé par les volumes
   MinIO/Postgres/OpenBao.
5. Rotation : `cryptsetup luksChangeKey` + mise à jour de la valeur OpenBao.

*Défense en profondeur* : LUKS protège le scénario « disque volé / accès offline »
(couvre **toutes** les données : objets + métadonnées + config, contrairement au
SSE-S3 qui ne chiffre que le corps des objets). Il ne protège pas contre une
compromission du service en cours d'exécution (MinIO sert les objets déchiffrés)
— même propriété que le SSE-S3 ; ce risque relève du durcissement réseau/RBAC.

## Consequences

**Positives** : 100 % AGPL/OSS (LUKS = noyau Linux), future-proof, zéro composant
déprécié/Enterprise ; couverture complète des données ; clés séparées des données
et custodiées par OpenBao (best practice souveraine) ; un seul outil de secrets
(OpenBao) déjà retenu (ADR-0003).

**Négatives / risques** : pas de chiffrement *par-objet* ni de rotation de clé
fine par objet (acceptable pour single-node souverain) ; le déverrouillage au
boot dépend de la disponibilité d'OpenBao (mitigation : unseal SOPS+age d'OpenBao
en amont, P7) ; non testable en dev Docker Desktop (validé en environnement
VPS/k3s lors de la phase déploiement).

**Réversibilité** : si un besoin de chiffrement par-objet émerge (multi-tenant
SaaS), la migration vers un KMS reste possible sans défaire LUKS (les deux couches
sont orthogonales).
