#!/usr/bin/env python3
"""Restauration assistee depuis la sauvegarde pre-upgrade (Job `facil-backup`).

`helm rollback` (deploy/providers/k3s.py --rollback) NE RESTAURE PAS la base --
il rend les MANIFESTES a leur etat anterieur, jamais les DONNEES. Cet outil est
le SEUL chemin qui restaure reellement Postgres (`pg_restore`) et MinIO
(`mc mirror`) depuis une sauvegarde horodatee du PVC `facil-backups`.

Decision assumee (ne pas re-debattre) : PAS de restauration automatique.
Ecraser une base en cours d'exploitation est une operation destructive qui
exige une decision humaine -- un `--restore` declenche automatiquement au
milieu d'un rollback serait un pistolet charge. On outille l'operateur, on ne
decide pas a sa place. La confirmation exige donc de RETAPER l'horodatage EXACT
(jamais un simple y/N, trop facile a valider par reflexe).

CWE-214 : ni PGPASSWORD ni le mot de passe MinIO ne transitent JAMAIS par un
argv de subprocess -- ce script ne lit d'ailleurs jamais leur VALEUR : le Job
de restauration les recoit via `secretKeyRef` (le Secret `facil-backup-secret`,
deja cree par `deploy/providers/k3s.py --apply`), resolu par le kubelet, jamais
par ce process Python ni par la ligne de commande d'un conteneur.

Aucune image nouvelle : le Job de liste et le Job de restauration reutilisent
l'image Postgres DEJA epinglee sur le cluster (introspectee en direct depuis le
StatefulSet `facil-postgres` -- jamais depuis deploy/config.yaml, qui peut etre
absent ou perime par rapport a ce qui tourne reellement), meme principe que
backup-job.yaml.

Usage
-----
    python deploy/scripts/restore_backup.py --list
    python deploy/scripts/restore_backup.py --restore 20260714T091500Z

Exit codes
----------
0  Succes.
1  Horodatage invalide/introuvable, ou confirmation refusee (l'operateur a
   retape autre chose que l'horodatage exact) -- annulation volontaire.
2  kubectl introuvable, StatefulSet Postgres introuvable, ou une etape
   kubectl/Job (apply/wait/logs) a echoue.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROVIDERS_DIR = SCRIPTS_DIR.parent / "providers"
sys.path.insert(0, str(PROVIDERS_DIR))
from k3s import find_kubectl, SECRET_NAMES  # noqa: E402  (reuse -- pas de duplication)

NAMESPACE_DEFAULT = "facil"
BACKUPS_PVC = "facil-backups"
POSTGRES_STS = "facil-postgres"
MINIO_STS = "facil-minio"
BACKUP_SECRET = SECRET_NAMES["backup"]  # "facil-backup-secret" -- source unique (k3s.py)
LIST_JOB = "facil-restore-list"
RESTORE_JOB = "facil-restore-apply"

# Format ecrit par backup-job.yaml : `date -u +%Y%m%dT%H%M%SZ`.
TIMESTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


def _kubectl_get_field(kubectl: str, namespace: str, resource: str, jsonpath: str) -> str | None:
    """`kubectl get <resource> -o jsonpath=<jsonpath>`, lecture seule. None si absent/echec."""
    proc = subprocess.run(
        [kubectl, "-n", namespace, "get", resource, "-o", f"jsonpath={jsonpath}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _introspect_postgres(kubectl: str, namespace: str) -> dict[str, str] | None:
    """Image/utilisateur/base REELLEMENT deployes (StatefulSet `facil-postgres`).

    Introspection EN DIRECT plutot que via deploy/config.yaml : ce dernier peut
    etre absent (poste fraichement clone) ou avoir change depuis le dernier
    `--apply` -- la seule verite est ce qui tourne sur le cluster.
    """
    jsonpath = ('{.spec.template.spec.containers[0].image}{"|"}'
                '{.spec.template.spec.containers[0].env[?(@.name=="POSTGRES_USER")].value}{"|"}'
                '{.spec.template.spec.containers[0].env[?(@.name=="POSTGRES_DB")].value}')
    raw = _kubectl_get_field(kubectl, namespace, f"statefulset/{POSTGRES_STS}", jsonpath)
    if not raw:
        return None
    parts = (raw.split("|") + ["", "", ""])[:3]
    image, user, db = parts
    if not image or not user or not db:
        return None
    return {"image": image, "user": user, "db": db}


def _introspect_minio(kubectl: str, namespace: str) -> dict[str, str] | None:
    """Image/utilisateur root REELLEMENT deployes (StatefulSet `facil-minio`).

    None si MinIO est desactive (storage.provider != minio) -- pas une erreur,
    juste "rien a restaurer cote objet" (asymetrie deliberee, cf. backup-job.yaml).
    """
    jsonpath = ('{.spec.template.spec.containers[0].image}{"|"}'
                '{.spec.template.spec.containers[0].env[?(@.name=="MINIO_ROOT_USER")].value}')
    raw = _kubectl_get_field(kubectl, namespace, f"statefulset/{MINIO_STS}", jsonpath)
    if not raw:
        return None
    parts = (raw.split("|") + ["", ""])[:2]
    image, user = parts
    if not image or not user:
        return None
    return {"image": image, "user": user}


def _run_job(kubectl: str, namespace: str, job_name: str, manifest: str, *,
            timeout: str = "120s") -> tuple[int, str]:
    """Applique un Job jetable (manifest sur STDIN, jamais l'argv -- SEC-006),
    attend sa fin, recupere ses logs, le supprime. FAIL-CLOSED : toute etape en
    echec renvoie un code non-zero, jamais une erreur avalee silencieusement.

    Nettoyage AVANT (idempotent -- un Job du meme nom peut trainer d'une
    execution precedente en echec) ET APRES (ne laisse jamais de Job zombie).
    """
    subprocess.run([kubectl, "-n", namespace, "delete", "job", job_name,
                    "--ignore-not-found", "--wait=true"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   check=False)

    apply = subprocess.run(
        [kubectl, "-n", namespace, "apply", "-f", "-"],
        input=manifest, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    if apply.returncode != 0:
        print(f"ERREUR: impossible de creer le Job '{job_name}' (kubectl apply a echoue).",
              file=sys.stderr)
        return 2, ""

    wait = subprocess.run(
        [kubectl, "-n", namespace, "wait", f"job/{job_name}",
         "--for=condition=complete", f"--timeout={timeout}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    logs = subprocess.run(
        [kubectl, "-n", namespace, "logs", f"job/{job_name}", "--all-containers=true"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    subprocess.run([kubectl, "-n", namespace, "delete", "job", job_name, "--ignore-not-found"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   check=False)

    if wait.returncode != 0:
        print(f"ERREUR: le Job '{job_name}' a echoue ou a expire (timeout={timeout}).\n"
              f"{logs.stdout}", file=sys.stderr)
        return 2, logs.stdout
    return 0, logs.stdout


def _list_job_manifest(image: str) -> str:
    """Job lecture seule : monte le PVC des sauvegardes en RO, liste les repertoires
    horodates. Aucune image nouvelle : reutilise l'image Postgres deja epinglee."""
    return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {LIST_JOB}
  labels: {{app.kubernetes.io/name: facil-restore}}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 120
  template:
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999
        seccompProfile: {{type: RuntimeDefault}}
      containers:
        - name: list-backups
          image: "{image}"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {{drop: ["ALL"]}}
          command: ["sh", "-c"]
          args:
            - "cd /backups && ls -1d 2*Z 2>/dev/null | sort"
          volumeMounts:
            - {{name: backups, mountPath: /backups, readOnly: true}}
      volumes:
        - name: backups
          persistentVolumeClaim: {{claimName: {BACKUPS_PVC}, readOnly: true}}
"""


def list_backups(kubectl: str, namespace: str) -> list[str]:
    """Sauvegardes horodatees disponibles sur le PVC, triees (plus recente en dernier).

    Liste VIDE (pas d'exception) si Postgres est introuvable ou si le Job de
    liste echoue -- l'appelant (main()) est responsable d'expliquer pourquoi a
    l'operateur ; cette fonction reste une primitive silencieuse-sur-echec
    volontairement simple, reutilisee par --list ET par la validation de
    --restore (garde l'horodatage demande contre la liste reelle).
    """
    postgres = _introspect_postgres(kubectl, namespace)
    if postgres is None:
        return []
    rc, out = _run_job(kubectl, namespace, LIST_JOB, _list_job_manifest(postgres["image"]))
    if rc != 0:
        return []
    return sorted(line.strip() for line in out.splitlines() if TIMESTAMP_RE.match(line.strip()))


def _restore_job_manifest(*, timestamp: str, postgres: dict[str, str],
                          minio: dict[str, str] | None) -> str:
    """Job de restauration : `pg_restore` (toujours) + `mc mirror` (si MinIO deploye).

    PGPASSWORD/MINIO_ROOT_PASSWORD : `secretKeyRef` vers `facil-backup-secret`
    (deja cree par k3s.py --apply) -- jamais une valeur en clair dans ce texte.
    MC_HOST_facil : interpolation NATIVE k8s `$(VAR)` (resolue par le kubelet
    AVANT l'exec du conteneur), meme convention que backup-job.yaml -- jamais
    `${{VAR}}` shell, qui ferait apparaitre `scheme://user:pass@` en TEXTE dans
    ce manifest.
    """
    dest = f"/backups/{timestamp}"
    containers = [f"""        - name: restore-postgres
          image: "{postgres['image']}"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {{drop: ["ALL"]}}
          env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: {BACKUP_SECRET}
                  key: POSTGRES_PASSWORD
            - name: PGHOST
              value: "{POSTGRES_STS}"
            - name: PGUSER
              value: "{postgres['user']}"
            - name: PGDATABASE
              value: "{postgres['db']}"
          command: ["sh", "-c"]
          args:
            - |
              set -eu
              # BUG REEL CORRIGE (smoke k3d task-E1, 2026-07-14) : sans cette
              # attente, `pg_restore` echouait "Connection refused" sur un
              # cluster fraichement joint (meme fenetre transitoire que le Job
              # facil-backup avant son propre correctif -- voir backup-job.yaml)
              # -- alors que le mirroir MinIO (container voisin, commande `mc`)
              # reussissait grace a sa PROPRE resilience interne ("Unable to
              # list comparison retrying...") : `pg_restore` n'a aucune retry
              # logic, il faut la lui fournir. Meme motif `until pg_isready`
              # que db-role-job.yaml/db-init-job.yaml/backup-job.yaml (DRY par
              # copie, deja accepte entre ces Jobs).
              until pg_isready -h "$PGHOST" -U "$PGUSER"; do
                echo "postgres pas pret, attente..." >&2
                sleep 2
              done
              echo "restauration Postgres depuis {dest}/postgres.dump" >&2
              pg_restore --clean --if-exists --no-owner -d "$PGDATABASE" "{dest}/postgres.dump"
          volumeMounts:
            - {{name: backups, mountPath: /backups, readOnly: true}}
            - {{name: tmp, mountPath: /tmp}}
"""]
    if minio is not None:
        containers.append(f"""        - name: restore-minio
          image: "{minio['image']}"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {{drop: ["ALL"]}}
          env:
            - name: MINIO_ROOT_USER
              value: "{minio['user']}"
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {BACKUP_SECRET}
                  key: MINIO_ROOT_PASSWORD
            - name: MC_HOST_facil
              value: http://$(MINIO_ROOT_USER):$(MINIO_ROOT_PASSWORD)@{MINIO_STS}:9000
            - name: MC_CONFIG_DIR
              value: /tmp/.mc
          command: ["sh", "-c"]
          args:
            - |
              set -eu
              echo "restauration MinIO depuis {dest}/minio" >&2
              mc mirror --quiet --overwrite "{dest}/minio" facil
          volumeMounts:
            - {{name: backups, mountPath: /backups, readOnly: true}}
            - {{name: tmp, mountPath: /tmp}}
""")
    body = "\n".join(containers)
    return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {RESTORE_JOB}
  labels: {{app.kubernetes.io/name: facil-restore}}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      # BUG REEL CORRIGE (smoke k3d task-E1, 2026-07-14) : sans ce label, ce
      # Job recevait "Connection refused" sur Postgres ET MinIO -- la
      # NetworkPolicy default-deny (infra/helm/facil/templates/
      # networkpolicy.yaml, SEC-012) n'autorise l'ingress sur ces datastores
      # QU'aux pods portant `facil.component in [backend, db-init, db-role,
      # backup]`. Ce Job n'en portait AUCUN (seuls les labels auto-generes par
      # Kubernetes -- job-name/controller-uid) -> bloque inconditionnellement.
      # "backup" est reutilise ici (pas une nouvelle valeur) : restauration et
      # sauvegarde partagent la meme legitimite d'acces aux datastores.
      labels: {{facil.component: backup}}
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999
        seccompProfile: {{type: RuntimeDefault}}
      containers:
{body}
      volumes:
        - name: backups
          persistentVolumeClaim: {{claimName: {BACKUPS_PVC}, readOnly: true}}
        - name: tmp
          emptyDir: {{}}
"""


def confirm_exact_timestamp(timestamp: str) -> bool:
    """Confirmation destructive : l'operateur doit RETAPER l'horodatage exact.

    PAS un y/N -- trop facile a valider par reflexe (Entree/'y' machinal) sur
    l'operation la plus destructive de cet outil (ecrase la base en place).
    Appelle `input()` directement (jamais lie en defaut de parametre) : les
    tests monkeypatchent `builtins.input`, resolu a CHAQUE appel -- meme
    mecanisme deja utilise par k3s.py::main() pour la confirmation --apply.
    """
    typed = input(f"Retapez EXACTEMENT l'horodatage pour confirmer [{timestamp}]: ").strip()
    return typed == timestamp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--namespace", default=NAMESPACE_DEFAULT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true",
                      help="Liste les sauvegardes horodatees disponibles sur le PVC.")
    mode.add_argument("--restore", metavar="HORODATAGE", default=None,
                      help="Restaure Postgres (+MinIO si deploye) depuis la sauvegarde "
                           "<HORODATAGE> (ex. 20260714T091500Z). Confirmation interactive "
                           "OBLIGATOIRE (retaper l'horodatage exact). JAMAIS automatique.")
    args = parser.parse_args(argv)

    kubectl = find_kubectl()
    if not kubectl:
        print("ERREUR: kubectl introuvable dans le PATH.", file=sys.stderr)
        return 2

    if args.list:
        backups = list_backups(kubectl, args.namespace)
        if not backups:
            print("Aucune sauvegarde trouvee (ou StatefulSet Postgres introuvable dans "
                  f"le namespace '{args.namespace}').")
            return 0
        print("Sauvegardes disponibles (la plus recente en dernier) :")
        for ts in backups:
            print(f"  {ts}")
        return 0

    # --restore : valider le FORMAT avant toute autre chose -- un horodatage
    # malforme ne doit JAMAIS atteindre un manifest ou un appel subprocess
    # (defense en profondeur : meme si le reste du chemin est correct, un
    # format inattendu ne doit pas se retrouver interpole dans un script shell).
    ts = args.restore
    if not TIMESTAMP_RE.match(ts):
        print(f"ERREUR: horodatage invalide: {ts!r} (attendu YYYYMMDDTHHMMSSZ, ex. "
              "20260714T091500Z).", file=sys.stderr)
        return 1

    available = list_backups(kubectl, args.namespace)
    if ts not in available:
        print(f"ERREUR: sauvegarde '{ts}' introuvable. Sauvegardes disponibles : "
              f"{', '.join(available) if available else '(aucune)'}.\n"
              "Lancer --list pour la liste a jour.", file=sys.stderr)
        return 1

    print(
        "\n*** ATTENTION : operation DESTRUCTIVE et IRREVERSIBLE. ***\n"
        f"Ceci va ECRASER la base Postgres actuelle (et les buckets MinIO, si\n"
        f"deployes) avec la sauvegarde '{ts}'. Toute donnee ecrite depuis cette\n"
        "sauvegarde sera PERDUE. AUCUNE restauration automatique n'existe dans ce\n"
        "projet : c'est a vous, humain, de decider maintenant.\n")
    if not confirm_exact_timestamp(ts):
        print("Annule : l'horodatage tape ne correspond pas exactement.", file=sys.stderr)
        return 1

    postgres = _introspect_postgres(kubectl, args.namespace)
    if postgres is None:
        print(f"ERREUR: StatefulSet '{POSTGRES_STS}' introuvable dans le namespace "
              f"'{args.namespace}' -- impossible de restaurer sans cible Postgres.",
              file=sys.stderr)
        return 2
    minio = _introspect_minio(kubectl, args.namespace)
    if minio is None:
        print(f"AVERTISSEMENT: StatefulSet '{MINIO_STS}' introuvable -- restauration "
              "Postgres SEULEMENT (les objets MinIO ne seront pas restaures).",
              file=sys.stderr)

    manifest = _restore_job_manifest(timestamp=ts, postgres=postgres, minio=minio)
    rc, logs = _run_job(kubectl, args.namespace, RESTORE_JOB, manifest, timeout="15m")
    if rc != 0:
        return rc
    print(f"[OK] restauration '{ts}' terminee.\n{logs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
