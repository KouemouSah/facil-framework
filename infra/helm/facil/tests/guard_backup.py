#!/usr/bin/env python3
"""Garde-backup PARSEE (P2/A3) sur le rendu `helm template` — l'ordre est l'invariant.

Le chart pose un Job `facil-backup` (hook `pre-upgrade`, poids `-2`) qui dump
Postgres (+ mirror MinIO) AVANT que `db-role` (poids `-1`) et `db-init` (poids
`0`, la migration Alembic) ne s'executent. C'est la SEULE chose qui separe un
client d'une perte de donnees irreversible : `--atomic` (helm upgrade --install)
rollback les MANIFESTES sur un echec de hook, jamais la BASE deja mutee par une
migration destructive (DROP COLUMN, DROP TABLE).

Un `grep -q "kind: Job"` ne prouve RIEN : le Job peut exister, le rendu peut
passer `helm lint`, et la protection avoir disparu en silence si quelqu'un
change un jour le poids du backup vers une valeur qui ne precede plus les
migrations. Ce parseur verifie l'invariant qui compte reellement -- l'ORDRE --
pas seulement la presence :

  0. AUCUN Job du rendu (pas seulement facil-backup) ne porte le hook
     `pre-install` (B1) -- generalisation, PAR KIND, du grep global qu'il
     remplace dans test_render.sh : un Job pre-install s'execute avant que
     Postgres n'existe (APPLY-002), alors qu'une ressource SANS pod
     consommateur (ex. un PersistentVolumeClaim) peut legitimement l'etre.
  1. Le Job `facil-backup` existe (quand `backup.enabled`) et porte le hook
     `pre-upgrade` (jamais `post-install` -- rien a sauvegarder a la 1ere
     installation, decision de conception verrouillee : voir backup-job.yaml).
  2. Son `helm.sh/hook-weight` est STRICTEMENT INFERIEUR, NUMERIQUEMENT, a
     celui de `facil-db-role` ET de `facil-db-init`. Piege deliberement evite :
     en tri LEXICOGRAPHIQUE, `"-2" < "-1"` est FAUX (`"-" < "-"`, puis `"2" >
     "1"` comme caracteres) -- un test qui comparerait les poids comme des
     chaines de caracteres validerait a tort un ordre INVERSE. On parse
     chaque poids en `int` avant de comparer.
  3. Il est fail-closed : `restartPolicy: Never` (jamais de retry automatique
     qui masquerait un dump vide/echoue), `backoffLimit` present et BORNE (ni
     absent -- Kubernetes defaut a 6 --, ni enorme -- un chiffre proche de
     l'infini n'est fail-closed que sur le papier), et aucun `|| true` dans
     command/args d'un conteneur du Job -- un tel motif annule explicitement
     le code de sortie d'echec d'une commande precedente, ce qui romprait le
     `set -eu` du script et laisserait passer un dump/mirror rate comme un
     succes.

Ce que cette garde NE fait PAS (delibere, pas un oubli) : verifier l'absence
de credential en argv/env -- deja couvert GLOBALEMENT par guard_secrets.py sur
TOUS les conteneurs de TOUS les manifests (y compris ceux de ce Job) ; dupliquer
ici serait une violation DRY. Voir test_guard_backup.py pour la preuve par
mutation de chaque invariant, et test_guard_secrets.py pour la preuve que ce
Job y est bien soumis (le mirror-minio y utilise MC_HOST_facil, deja couvert).

Usage : helm template ... | python guard_backup.py
Exit 0 = ordre et fail-closed intacts, 1 = invariant viole.
"""
from __future__ import annotations

import sys

import yaml

BACKUP_JOB_NAME = "facil-backup"
# Les deux Jobs de migration que le backup DOIT strictement preceder -- voir
# db-role-job.yaml (poids -1) et db-init-job.yaml (poids 0).
MIGRATION_JOB_NAMES = ("facil-db-role", "facil-db-init")

# Borne haute deliberement stricte : un backoffLimit "enorme" (ex. 1000000)
# revient en pratique a un retry quasi-infini -- pas fail-closed, meme si la
# valeur est techniquement finie. Le chart reel utilise 1.
MAX_BACKOFF_LIMIT = 5


def _iter_jobs(stream: str):
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict) or doc.get("kind") != "Job":
            continue
        name = (doc.get("metadata") or {}).get("name", "?")
        yield name, doc


def _hook_weight(doc: dict) -> int | None:
    """Le poids du hook, parse en int -- None si absent ou non numerique.
    JAMAIS de comparaison sur la chaine brute : `"-2" < "-1"` est FAUX en tri
    lexicographique (piege documente en tete de fichier)."""
    annotations = (doc.get("metadata") or {}).get("annotations") or {}
    raw = annotations.get("helm.sh/hook-weight")
    if raw is None:
        return None
    try:
        return int(str(raw))
    except ValueError:
        return None


def _hooks(doc: dict) -> set[str]:
    annotations = (doc.get("metadata") or {}).get("annotations") or {}
    raw = str(annotations.get("helm.sh/hook") or "")
    return {h.strip() for h in raw.split(",") if h.strip()}


def _container_argv_text(c: dict) -> str:
    """Concatene `command` + `args` d'un conteneur -- meme helper que
    guard_secrets.py (DRY conceptuel ; duplique ici volontairement pour garder
    chaque garde independamment executable en script unique, comme les autres
    gardes de ce repertoire)."""
    parts: list[str] = []
    for key in ("command", "args"):
        val = c.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val)
        elif isinstance(val, str):
            parts.append(val)
    return "\n".join(parts)


def check(stream: str) -> list[str]:
    problems: list[str] = []
    jobs = dict(_iter_jobs(stream))

    # --- Invariant 0 (B1) : AUCUN Job ne doit porter le hook `pre-install` --
    # generalise a TOUS les Jobs du rendu, pas seulement facil-backup. Un hook
    # pre-install s'execute AVANT que les ressources normales de la release
    # (Postgres inclus) n'existent -- c'est exactement le bug APPLY-002 deja
    # corrige une fois (voir db-role-job.yaml/db-init-job.yaml). Remplace
    # l'ancien grep GLOBAL de test_render.sh (`grep -qE '"?helm\.sh/hook"?:
    # pre-install'` sur tout le rendu) : ce grep textuel ne distinguait pas un
    # Job (qui EXIGE Postgres deja debout) d'une simple ressource sans pod
    # consommateur -- ex. un PersistentVolumeClaim, pour qui pre-install est
    # legitime (rien a attendre, voir l'historique de backup-pvc.yaml). Scope
    # volontairement etroit : `kind: Job` uniquement, jamais un grep du rendu
    # entier.
    for job_name, doc in jobs.items():
        if "pre-install" in _hooks(doc):
            problems.append(
                f"{job_name}: hook `pre-install` present sur un Job -- il "
                f"s'executerait AVANT que les ressources de la release "
                f"(Postgres inclus) n'existent (APPLY-002).")

    if BACKUP_JOB_NAME not in jobs:
        # Absence n'est pas automatiquement une violation : `backup.enabled:
        # false` desactive intentionnellement le Job (cf. values.yaml). Rien a
        # verifier sur un composant volontairement absent du rendu -- meme
        # convention "fail-closed sans faux positif" que guard_resources.py /
        # guard_secrets.py quand un composant est `.enabled=false`.
        return problems

    backup_doc = jobs[BACKUP_JOB_NAME]

    # --- Invariant 1 : hook pre-upgrade -------------------------------------
    hooks = _hooks(backup_doc)
    if "pre-upgrade" not in hooks:
        problems.append(
            f"{BACKUP_JOB_NAME}: hook `pre-upgrade` absent (hooks presents : "
            f"{sorted(hooks) or ['aucun']}) -- la sauvegarde ne se declenche "
            f"plus avant `helm upgrade`, elle ne protege plus rien.")

    # --- Invariant 2 : ordre NUMERIQUE strict vs les Jobs de migration ------
    backup_weight = _hook_weight(backup_doc)
    if backup_weight is None:
        problems.append(
            f"{BACKUP_JOB_NAME}: helm.sh/hook-weight absent ou non numerique -- "
            f"impossible de prouver qu'il precede les migrations.")
    else:
        for mig_name in MIGRATION_JOB_NAMES:
            mig_doc = jobs.get(mig_name)
            if mig_doc is None:
                continue  # composant absent du rendu -- rien a comparer
            mig_weight = _hook_weight(mig_doc)
            if mig_weight is None:
                continue
            if not (backup_weight < mig_weight):
                problems.append(
                    f"{BACKUP_JOB_NAME}: hook-weight={backup_weight} n'est PAS "
                    f"strictement inferieur a celui de {mig_name}="
                    f"{mig_weight} -- inversion d'ordre : la sauvegarde "
                    f"tournerait apres (ou en meme temps que) la migration, "
                    f"ce qui ne protege plus les donnees.")

    # --- Invariant 3 : fail-closed -------------------------------------------
    pod_spec = (((backup_doc.get("spec") or {}).get("template") or {}).get("spec")) or {}
    restart_policy = pod_spec.get("restartPolicy")
    if restart_policy != "Never":
        problems.append(
            f"{BACKUP_JOB_NAME}: restartPolicy={restart_policy!r} -- attendu "
            f"`Never` (un restart automatique masquerait un dump vide/echoue "
            f"derriere un pod qui finit par tourner).")

    backoff = (backup_doc.get("spec") or {}).get("backoffLimit")
    if not isinstance(backoff, int) or isinstance(backoff, bool):
        problems.append(
            f"{BACKUP_JOB_NAME}: backoffLimit absent ou non numerique "
            f"({backoff!r}) -- sans borne explicite, Kubernetes retente "
            f"jusqu'a 6 fois par defaut, ce n'est pas un choix fail-closed "
            f"assume.")
    elif backoff < 0 or backoff > MAX_BACKOFF_LIMIT:
        problems.append(
            f"{BACKUP_JOB_NAME}: backoffLimit={backoff} hors de la borne "
            f"raisonnable [0, {MAX_BACKOFF_LIMIT}] -- un retry quasi-infini "
            f"n'est pas fail-closed, meme si la valeur est finie.")

    for c in list(pod_spec.get("initContainers") or []) + list(pod_spec.get("containers") or []):
        argv_text = _container_argv_text(c)
        if "|| true" in argv_text:
            problems.append(
                f"{BACKUP_JOB_NAME}/{c.get('name', '?')}: command/args contient "
                f"`|| true` -- annule le code de sortie d'echec de la commande "
                f"precedente ; un dump ou un mirror rate serait rapporte comme "
                f"un succes, rompant le fail-closed du hook.")

    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-backup (ordre avant migration) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-backup (ordre avant migration)")
