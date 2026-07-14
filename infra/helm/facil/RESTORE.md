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
  --if-exists --single-transaction` supprime les objets existants avant de les
  recréer ; `mc mirror --overwrite --remove` écrase les objets MinIO déjà
  présents **et supprime ceux qui n'existaient pas à l'horodatage**. Restaurer
  sur une base qui contient des données plus récentes que la sauvegarde
  **détruit** ces données plus récentes — des deux côtés, Postgres comme MinIO.
  *(Avant le durcissement E2, `mc mirror` n'avait pas `--remove` et
  **fusionnait** : les objets créés après l'horodatage survivaient à une
  restauration qui, côté Postgres, rembobinait tout — les deux datastores
  finissaient à deux époques différentes, sous un même « [OK] ».)*
- **La restauration Postgres est tout-ou-rien.** `--single-transaction` implique
  `--exit-on-error` : si elle déraille en cours de route, ROLLBACK, et la base
  d'avant la restauration est **intacte**. Sans cela, `--clean` ayant déjà
  supprimé les objets, un échec à mi-parcours laissait la base à moitié détruite
  et à moitié rechargée.
- **Les étapes sont séquentielles et pré-volées.** Un conteneur `preflight`
  vérifie que le dump existe et n'est pas vide (et que le volet MinIO est présent
  quand MinIO doit être restauré) **avant** la première opération destructive.
  Puis Postgres, puis MinIO — jamais en parallèle.
- **`--list` distingue « vide » de « indéterminé ».** Si le Job de listage n'a
  pas pu tourner (RBAC, nœud saturé, PVC déjà monté ailleurs), la commande sort
  **2** et le dit — elle n'affirme **jamais** « aucune sauvegarde » sur la foi
  d'une lecture qui a échoué. Exit 0 + « aucune sauvegarde » signifie que le PVC
  a réellement été lu et qu'il est vide.
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
- **Le PVC `facil-backups` n'est PAS créé par Helm.** Il est appliqué par
  `deploy/providers/k3s.py --apply` (`build_pvc_manifest()`, via `kubectl
  apply`), hors du chart — sorti de Helm parce que, en hook `pre-install`, il
  provoquait un interblocage avec `--wait`. Il survit donc à un `helm uninstall`
  du seul fait qu'aucun `kubectl delete` ne le vise, **pas** grâce à une
  annotation `helm.sh/resource-policy: keep` (le fichier
  `templates/backup-pvc.yaml` qui la portait **n'existe plus**).
  Conséquence opérationnelle : un `helm upgrade` lancé **directement** sur un
  cluster où `k3s.py --apply` n'a jamais tourné n'a pas de PVC → le Job
  `facil-backup` reste `Pending` → timeout → rollback `--atomic`. C'est
  fail-closed (aucune migration ne passe), mais le diagnostic est opaque :
  passer par `k3s.py --apply`.

## Smoke — résultats observés (task-E1, cluster k3d jetable, 2026-07-14)

**Contexte** : `helm lint`/`helm template`/646 tests unitaires étaient déjà
tous verts sur ce chart avant ce smoke. Rien ci-dessous ne re-décrit ces
résultats statiques — tout ce qui suit a été **observé sur un vrai cluster
k3d**, avec de **vraies données** insérées puis détruites. **4 bugs réels**
ont été trouvés (aucun visible par lint/template/tests), corrigés, re-testés
en conditions réelles, et sont chacun couverts par un test de non-régression.

### Tableau des critères

| # | Critère | Résultat réel observé |
|---|---|---|
| 1 | Cluster k3d jetable, stack saine | ✅ `k3d cluster create facil-smoke -p "8090:80@loadbalancer"` ; 1er `--apply` a nécessité **3 corrections** (voir « Bugs trouvés ») avant de réussir de bout en bout |
| 2 | Données réelles insérées (Postgres + MinIO) | ✅ ligne `organization` (`code=SMOKE-E1`, `id=bab64b0c-7ec4-4e46-979d-83868e5d8f1c`) + objet MinIO `facil-documents/smoke-e1/proof.txt` (61 B) |
| 3 | `facil-backup` s'exécute **avant** `db-role`/`db-init` (upgrade normal, 1 passe) | ✅ **prouvé par `startTime` réel** (`kubectl get jobs -o json`), pas par les annotations : `facil-backup` 15:21:30→15:21:43, `facil-db-role` 15:21:43→15:21:49, `facil-db-init` 15:21:49→15:22:08 — strictement séquentiel, dans l'ordre des poids |
| 4 | PVC contient un dump non vide + le mirror MinIO | ✅ `postgres.dump` = 286 256 octets ; `minio/facil-documents/smoke-e1/proof.txt` présent dans le même horodatage `20260714T152136Z` |
| 5 | **Destruction réelle** (DELETE sur la table métier + objet MinIO) | ✅ `DELETE FROM organization WHERE code='SMOKE-E1'` → `count=0` ; `mc rm` de l'objet → listing vide confirmé |
| 6 | `--rollback` : manifestes reviennent, **données NE reviennent PAS** | ✅ `helm rollback` réussi (revision 4, « Rollback to 2 ») ; avertissement affiché à l'écran (texte exact ci-dessous) ; **après rollback**, `organization` `count=0` toujours, objet MinIO toujours absent |
| 7 | `restore_backup.py --list` puis `--restore <ts>` : **les données reviennent** | ✅ **LE critère qui compte** — voir « Preuve que les données sont revenues » ci-dessous |
| 8 | Fail-closed : mot de passe cassé sur `facil-backup-secret` → `db-init` ne démarre **jamais** | ✅ `facil-backup` échoue 2× (`BackoffLimitExceeded`, `FATAL: password authentication failed for user "facil"`) ; `helm upgrade --atomic` rollback auto ; **UID Kubernetes de `facil-db-init`/`facil-db-role` inchangé** avant/après (jamais recréés) |
| 9 | Cluster détruit en fin de smoke | ✅ `k3d cluster delete facil-smoke` + `docker system prune -f` |

### Preuve que les données sont revenues

**Avant destruction** (insérées manuellement pour ce smoke) :
- Postgres, table `organization` : `id=bab64b0c-7ec4-4e46-979d-83868e5d8f1c`,
  `code=SMOKE-E1`, `legal_name=Smoke Test Org E1 - task-E1 restore proof`,
  `display_name=Smoke E1`.
- MinIO, bucket `facil-documents` : objet `smoke-e1/proof.txt`, contenu
  `smoke-e1-object-content bab64b0c-7ec4-4e46-979d-83868e5d8f1c` (61 octets).

**Après destruction** (`DELETE` Postgres + `mc rm` MinIO) :
- `SELECT count(*) FROM organization WHERE code='SMOKE-E1'` → **0**.
- `mc ls facil/facil-documents/smoke-e1/` → **vide**.
- `helm rollback` exécuté entre-temps : les deux résultats ci-dessus restent
  identiques (0 / vide) — confirme que le rollback Helm ne touche jamais aux
  données.

**Après `restore_backup.py --restore 20260714T152136Z`** :
```
$ psql -U facil -d facil -c "SELECT id, code, legal_name, display_name FROM organization WHERE code='SMOKE-E1';"
                  id                  |   code   |                legal_name                 | display_name
--------------------------------------+----------+-------------------------------------------+--------------
 bab64b0c-7ec4-4e46-979d-83868e5d8f1c | SMOKE-E1 | Smoke Test Org E1 - task-E1 restore proof | Smoke E1

$ mc cat facil/facil-documents/smoke-e1/proof.txt
smoke-e1-object-content bab64b0c-7ec4-4e46-979d-83868e5d8f1c
```
Identiques bit pour bit à l'état pré-destruction, sur les deux systèmes.

### Avertissement `--rollback` (texte exact affiché à l'écran)

```
*** ATTENTION : la BASE DE DONNEES n'est PAS restauree. ***
`helm rollback` rend les MANIFESTES a leur etat anterieur -- jamais les
donnees. Si la migration etait destructive (DROP COLUMN/TABLE), le schema
reste casse et le code rollbacke tournera dessus.
Pour restaurer la base depuis la sauvegarde pre-upgrade :
    python deploy/scripts/restore_backup.py --list
    python deploy/scripts/restore_backup.py --restore <horodatage>
```

### Preuve du fail-closed (mot de passe cassé)

```
$ kubectl -n facil logs facil-backup-k6x87 -c dump-postgres
sauvegarde Postgres -> /backups/20260714T162032Z/postgres.dump
pg_dump: error: connection to server at "facil-postgres" (10.43.236.65), port 5432 failed: FATAL:  password authentication failed for user "facil"

$ helm -n facil upgrade --install facil infra/helm/facil -f infra/helm/facil/values-onprem.yaml --atomic --wait --timeout 10m
Error: UPGRADE FAILED: release facil failed, and has been rolled back due to atomic being set: pre-upgrade hooks failed: 1 error occurred:
	* job facil-backup failed: BackoffLimitExceeded
```
UID Kubernetes de `facil-db-init`/`facil-db-role` **avant** cette tentative :
`5172b811-...` / `35105e29-...` — **identiques après** l'échec : ni l'un ni
l'autre Job n'a été recréé. La migration n'a jamais tourné.

### Bugs réels trouvés et corrigés (aucun visible par lint/template/tests)

1. **PVC `facil-backups` bloquait `--wait` au 1er install** — `WaitForFirstConsumer`
   (StorageClass `local-path`) + aucun pod consommateur avant le 1er `helm
   upgrade` (le Job de sauvegarde est `pre-upgrade` seul) ⇒ `helm install --wait`
   expirait systématiquement (5 min), **aucun Job jamais créé**. Essai rejeté :
   StorageClass `Immediate` dédiée — `rancher.io/local-path` ne la supporte pas
   (`configuration error, no node was specified`, erreur observée en direct).
   1er fix : la PVC devient un hook `pre-install` **seul** — les hooks ne sont
   pas comptés par `--wait`. **Fix final** : la PVC sort de Helm entièrement
   (`kubectl apply` depuis `k3s.py::build_pvc_manifest()`) ; `templates/backup-pvc.yaml`
   n'existe plus.
2. **NetworkPolicy `allow-datastores-from-backend` oubliait `backup`** — le Job
   de sauvegarde recevait `ECONNREFUSED` sur Postgres **et** MinIO
   (`pg_dump: ... Connection refused`). `infra/helm/facil/templates/networkpolicy.yaml`.
   Le même trou existait, séparément, dans les Jobs de `restore_backup.py`
   (aucun `facil.component` du tout ⇒ bloqués inconditionnellement) —
   `deploy/scripts/restore_backup.py` (label `facil.component: backup` ajouté
   au pod-template du Job de restauration).
3. **`facil-backup`/le Job de restauration n'avaient pas d'attente `wait-postgres`**
   (contrairement à `db-role`/`db-init`, qui l'ont déjà) — une fenêtre
   transitoire (redémarrage Postgres, convergence NetworkPolicy sur un pod
   fraîchement labellisé) faisait échouer `pg_dump`/`pg_restore` sans retry,
   alors que `mc mirror` voisin réussissait grâce à sa propre résilience.
   `infra/helm/facil/templates/backup-job.yaml` + `deploy/scripts/restore_backup.py`.
4. **`k3s.py::release_exists()` traitait une release `failed` comme « déjà
   installée »** — `helm status` renvoie `returncode==0` même pour une release
   au statut `failed` (ex. un `--apply` précédent avorté au pre-install). Un
   `--apply` de reprise prenait alors le chemin une-passe au lieu de la danse
   deux-passes du 1er install, reproduisant tel quel le deadlock original
   (task-V1) que cette danse existe pour éviter. Fix : lire `.info.status`
   (JSON), n'accepter que `"deployed"`. `deploy/providers/k3s.py`.

Chacun des 4 bugs est désormais couvert par un test de non-régression
(`deploy/providers/test_k3s.py`, `deploy/scripts/test_restore_backup.py`) —
648 tests verts après correction, dont les 4 nouveaux.

### Note annexe (hors config du smoke, corrigée localement)

`deploy/config.yaml` (gitignored) avait `meta.version: latest` — ce tag n'est
jamais poussé sur la branche `develop` (voir le commentaire de
`values.yaml::global.imageTag`), ce qui cassait le tout premier `--apply`
(`ImagePullBackOff` sur le frontend). Corrigé en local (`version: develop`) ;
fichier gitignoré, aucun commit associé — mentionné ici pour la traçabilité du
smoke, pas comme un bug du chart.
