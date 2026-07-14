# Restauration des données — chart `infra/helm/facil`

> **À lire avant un `helm rollback`.** `helm rollback` (`deploy/providers/k3s.py
> --rollback`) rend les **manifestes** Helm à leur état antérieur — **jamais**
> les données. Si la migration qui a précédé le rollback était destructive
> (`DROP COLUMN`, `DROP TABLE`), le schéma reste cassé et le code rollbacké
> tourne dessus. Ce document décrit le **seul** chemin qui restaure réellement
> Postgres et MinIO : `deploy/scripts/restore_backup.py`.

## D'où viennent les sauvegardes

Le Job `facil-backup` (`infra/helm/facil/templates/backup-job.yaml`, hook
`pre-upgrade`, poids `-2` — **avant** les Jobs `db-role`/`db-init`) tourne à
**chaque** `helm upgrade` (jamais au premier `helm install` — rien à sauvegarder
encore) et écrit, sur le PVC dédié `facil-backups` :

```text
/backups/<HORODATAGE>/postgres.dump   # pg_dump -Fc (format custom, compressé)
/backups/<HORODATAGE>/minio/          # mc mirror des buckets (si MinIO déployé)
/backups/.latest                      # horodatage de la sauvegarde la plus récente
```

`<HORODATAGE>` est au format `date -u +%Y%m%dT%H%M%SZ` (ex. `20260714T091500Z`).
Rétention : `values.yaml::backup.retain` sauvegardes conservées (5 par défaut) —
les plus anciennes sont purgées automatiquement par le Job lui-même.

Le Job est **fail-closed** : un dump vide ou un `mc mirror` en échec fait échouer
le Job → le hook échoue → `helm upgrade` avorte **avant** la migration. Une
sauvegarde absente bloque donc le déploiement au lieu de laisser croire, à tort,
qu'il y en a une.

## Procédure de restauration

```bash
# 1. Lister les sauvegardes disponibles sur le cluster
python deploy/scripts/restore_backup.py --list

# 2. Restaurer une sauvegarde précise (confirmation interactive OBLIGATOIRE)
python deploy/scripts/restore_backup.py --restore 20260714T091500Z
```

`--restore` :

1. Refuse tout horodatage qui ne colle pas exactement au format attendu, et
   tout horodatage absent de la liste réelle (`--list`) — **avant** de toucher
   quoi que ce soit sur le cluster.
2. Affiche un avertissement explicite (opération **destructive et
   irréversible**) puis exige de **retaper l'horodatage exact** pour confirmer
   — volontairement **pas** un simple `y/N`, trop facile à valider par réflexe
   sur l'action la plus destructive de cet outil.
3. Restaure Postgres (`pg_restore --clean --if-exists`) et, si MinIO est
   déployé, les buckets (`mc mirror`) — via un Job Kubernetes jetable qui monte
   le PVC `facil-backups` en lecture seule et lit les identifiants via
   `secretKeyRef` (jamais en clair : ni ce script ni la ligne de commande d'un
   conteneur ne voient la valeur du mot de passe).

**Il n'existe volontairement AUCUN mode automatique.** Écraser une base en
exploitation est une décision humaine, pas une étape de script — un `--restore`
déclenché tout seul au milieu d'un rollback serait un pistolet chargé pointé
sur la production. Cet outil **outille** l'opérateur ; il ne décide jamais à sa
place.

## Limites — à lire avant de faire confiance à cette sauvegarde

- **Les sauvegardes ne sont PAS chiffrées at-rest.** `pg_dump`/`mc mirror`
  écrivent en clair sur le PVC `facil-backups`, qui vit sur le disque du nœud
  k3s (StorageClass `local-path` par défaut). Le chiffrement, s'il est requis,
  relève du **volume** (LUKS sur le disque du nœud), pas de cet outil ni du
  chart — même approche que le chiffrement at-rest de MinIO (voir
  `reference_minio_encryption_at_rest` / plan `MINIO_SECURITY_ARCH_PLAN.md`).
  Un opérateur qui copie ce PVC ailleurs (backup externalisé, disque de
  rechange) copie des identifiants et des données métier **en clair**.
- **Un seul nœud, un seul PVC `ReadWriteOnce`.** Cohérent avec la cible k3s
  mono-nœud (ADR-0006) ; sur un cluster multi-nœud, ce PVC n'est monté que sur
  le nœud où il a été provisionné — pas une topologie qu'un `--restore` gère.
- **Pas de sauvegarde incrémentale ni de PITR (point-in-time recovery).**
  Chaque sauvegarde est un instantané complet, horodaté au moment du Job
  `pre-upgrade`. Toute donnée écrite **après** l'horodatage restauré est
  perdue — le message de confirmation le rappelle explicitement.
- **La restauration écrase, elle ne fusionne pas.** `pg_restore --clean
  --if-exists` supprime les objets existants avant de les recréer ; `mc mirror
  --overwrite` écrase les objets MinIO déjà présents. Restaurer sur une base
  qui contient des données plus récentes que la sauvegarde **détruit** ces
  données plus récentes.
- **Rétention bornée** (`backup.retain`, 5 par défaut) : une sauvegarde plus
  ancienne que les `retain` dernières a déjà été purgée par le Job lui-même —
  `--list` ne montre que ce qui existe réellement, jamais un horodatage fantôme.
- **`--restore` dépend d'un cluster accessible** (le Job de restauration tourne
  dans le namespace cible) : si le cluster est down, seule une restauration
  manuelle du PVC (hors de cet outil) reste possible.

## Voir aussi

- `deploy/providers/k3s.py --rollback` — rollback des manifestes Helm
  (n'affecte jamais les données ; affiche ce même avertissement et pointe vers
  ce document).
- `infra/helm/facil/templates/backup-job.yaml` — le Job qui produit les
  sauvegardes consommées ici.
- `infra/helm/facil/templates/backup-pvc.yaml` — le PVC `facil-backups`
  (`helm.sh/resource-policy: keep` : survit à un `helm uninstall`).
