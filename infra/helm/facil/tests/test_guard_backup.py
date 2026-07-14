"""Tests TDD pour la garde-backup PARSEE (P2/A3) — infra/helm/facil/tests/guard_backup.py.

L'invariant qui compte n'est PAS "le Job existe" (un `grep -q "kind: Job"` ne
prouve rien) mais l'ORDRE : la sauvegarde doit tourner STRICTEMENT avant les
migrations. Chaque invariant ci-dessous est prouve par MUTATION (on fabrique la
regression et on verifie que la garde rougit) -- "un test qui ne peut pas
echouer est un defaut grave" (cf. CLAUDE.md).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).parent
CHART_DIR = TESTS_DIR.parent
REPO_ROOT = CHART_DIR.parent.parent.parent

sys.path.insert(0, str(TESTS_DIR))
import guard_backup  # noqa: E402


def _helm_template(*extra_args: str) -> str:
    cmd = ["helm", "template", "rel", str(CHART_DIR), *extra_args]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture(scope="module")
def default_render() -> str:
    return _helm_template()


def _mutate_backup_job(rendered: str, mutate):
    """Round-trip YAML : localise le Job facil-backup, applique `mutate` sur
    son doc, re-serialise. Meme convention que guard_resources.py/
    test_guard_resources.py (mutation structurelle, jamais un remplacement de
    texte fragile a l'indentation exacte du rendu Helm)."""
    docs = list(yaml.safe_load_all(rendered))
    found = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Job" and \
                (doc.get("metadata") or {}).get("name") == "facil-backup":
            mutate(doc)
            found = True
    assert found, "fixture n'a pas trouve le Job facil-backup -- test casse silencieusement"
    return yaml.safe_dump_all(docs)


# --- Invariant 0 : rendu reel propre ----------------------------------------

def test_clean_default_render_has_no_problems(default_render):
    assert guard_backup.check(default_render) == []


def test_clean_onprem_overlay_render_has_no_problems():
    rendered = _helm_template("-f", str(CHART_DIR / "values-onprem.yaml"))
    assert guard_backup.check(rendered) == []


def test_backup_job_is_present_in_real_render(default_render):
    # Non-regression du parseur lui-meme : si `_iter_jobs` cessait de
    # reconnaitre le Job, tous les invariants ci-dessous passeraient "propre"
    # par absence -- faux negatif silencieux (meme piege documente dans
    # guard_resources.py: test_all_expected_workloads_are_seen).
    jobs = dict(guard_backup._iter_jobs(default_render))
    assert "facil-backup" in jobs
    assert "facil-db-role" in jobs
    assert "facil-db-init" in jobs


# --- Invariant 0 (B1) : AUCUN Job (pas seulement facil-backup) en pre-install -

def test_catches_pre_install_on_a_job_that_is_not_facil_backup():
    # Generalisation du grep global que ce fichier remplace dans
    # test_render.sh : n'importe quel Job du rendu, pas seulement
    # facil-backup, doit etre refuse s'il porte pre-install.
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-some-other-job
  annotations:
    helm.sh/hook: pre-install
    helm.sh/hook-weight: "-3"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
"""
    problems = guard_backup.check(doc)
    assert any(
        "facil-some-other-job" in p and "pre-install" in p for p in problems
    ), problems


def test_pre_install_on_a_non_job_resource_is_not_flagged():
    # Scope volontairement etroit (kind: Job UNIQUEMENT) : une ressource sans
    # pod consommateur (ex. un PersistentVolumeClaim) peut legitimement porter
    # pre-install -- rien a attendre pour elle (voir l'historique de
    # backup-pvc.yaml). Prouve que le parseur ne generalise pas au-dela des Jobs.
    doc = """
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: facil-backups
  annotations:
    helm.sh/hook: pre-install
spec:
  accessModes: ["ReadWriteOnce"]
"""
    assert guard_backup.check(doc) == []


def test_real_render_has_no_job_with_pre_install(default_render):
    # Non-regression sur le rendu REEL : aucun Job du chart ne doit porter
    # pre-install (db-role/db-init sont post-install,pre-upgrade ; backup est
    # pre-upgrade seul).
    problems = guard_backup.check(default_render)
    assert not any("pre-install" in p for p in problems), problems


# --- Invariant 1 : hook `pre-upgrade` obligatoire ----------------------------

def test_catches_pre_upgrade_hook_removed(default_render):
    mutated = _mutate_backup_job(
        default_render,
        lambda doc: doc["metadata"]["annotations"].__setitem__("helm.sh/hook", "post-install"),
    )
    problems = guard_backup.check(mutated)
    assert any("facil-backup" in p and "pre-upgrade" in p for p in problems), problems


def test_catches_hook_annotation_entirely_missing():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook-weight: "-2"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: backup-complete
          command: ["sh", "-c", "echo done"]
"""
    problems = guard_backup.check(doc)
    assert any("facil-backup" in p and "pre-upgrade" in p for p in problems), problems


# --- Invariant 2 (coeur de la tache) : ordre NUMERIQUE strict ---------------

def test_catches_weight_moved_after_migrations(default_render):
    # Le scenario exact du brief : le poids du backup passe a 1 (APRES les
    # migrations, poids -1 et 0) -- la garde doit rougir en NOMMANT l'inversion.
    mutated = _mutate_backup_job(
        default_render,
        lambda doc: doc["metadata"]["annotations"].__setitem__("helm.sh/hook-weight", "1"),
    )
    problems = guard_backup.check(mutated)
    assert any(
        "facil-backup" in p and "facil-db-role" in p and "n'est PAS" in p
        for p in problems
    ), problems
    assert any(
        "facil-backup" in p and "facil-db-init" in p and "n'est PAS" in p
        for p in problems
    ), problems


def test_lexicographic_string_comparison_would_be_a_trap():
    # Preuve directe du piege documente en tete de guard_backup.py :
    # en tri lexicographique "-2" < "-1" est FAUX ("-2" > "-1" comme chaines,
    # car '2' > '1'). Une garde qui comparerait les poids comme des chaines
    # validerait a tort l'ordre actuel -- ce test le demontre independamment
    # de tout rendu Helm, puis prouve que guard_backup.py compare bien
    # NUMERIQUEMENT (le rendu reel, backup=-2 < db-role=-1, doit passer).
    assert not ("-2" < "-1")  # lexicographique : FAUX, alors que -2 < -1 est vrai numeriquement
    assert -2 < -1  # numerique : vrai, c'est ce que guard_backup.py doit verifier
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
---
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-db-role
  annotations:
    helm.sh/hook: post-install,pre-upgrade
    helm.sh/hook-weight: "-1"
spec:
  template:
    spec: {}
"""
    assert guard_backup.check(doc) == []


def test_weight_equal_to_migration_is_still_a_violation():
    # "strictement inferieur" : une egalite (meme poids) laisse l'ordre
    # d'execution indetermine entre les deux Jobs -- ce n'est PAS une garantie
    # d'ordre, donc ce n'est pas conforme.
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-1"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
---
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-db-role
  annotations:
    helm.sh/hook: post-install,pre-upgrade
    helm.sh/hook-weight: "-1"
spec:
  template:
    spec: {}
"""
    problems = guard_backup.check(doc)
    assert any("facil-db-role" in p and "n'est PAS" in p for p in problems), problems


def test_missing_or_non_numeric_hook_weight_is_flagged():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "not-a-number"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
"""
    problems = guard_backup.check(doc)
    assert any("facil-backup" in p and "hook-weight" in p for p in problems), problems


# --- Invariant 3 : fail-closed ------------------------------------------------

def test_catches_restart_policy_on_failure(default_render):
    mutated = _mutate_backup_job(
        default_render,
        lambda doc: doc["spec"]["template"]["spec"].__setitem__("restartPolicy", "OnFailure"),
    )
    problems = guard_backup.check(mutated)
    assert any("facil-backup" in p and "restartPolicy" in p for p in problems), problems


def test_catches_unbounded_backoff_limit(default_render):
    mutated = _mutate_backup_job(
        default_render,
        lambda doc: doc["spec"].__setitem__("backoffLimit", 1_000_000),
    )
    problems = guard_backup.check(mutated)
    assert any("facil-backup" in p and "backoffLimit" in p for p in problems), problems


def test_catches_missing_backoff_limit():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
"""
    problems = guard_backup.check(doc)
    assert any("facil-backup" in p and "backoffLimit" in p for p in problems), problems


def test_catches_negative_backoff_limit():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
spec:
  backoffLimit: -1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
"""
    problems = guard_backup.check(doc)
    assert any("facil-backup" in p and "backoffLimit" in p for p in problems), problems


def test_catches_or_true_in_args_masking_a_failed_command():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      initContainers:
        - name: mirror-minio
          command: ["sh", "-c"]
          args:
            - |
              mc mirror --quiet facil "$DEST" || true
      containers:
        - name: c
          command: ["sh", "-c", "echo ok"]
"""
    problems = guard_backup.check(doc)
    assert any(
        "facil-backup" in p and "mirror-minio" in p and "|| true" in p for p in problems
    ), problems


def test_or_true_in_a_different_container_is_still_caught():
    # `|| true` est banni sur TOUT conteneur (init inclus) du Job, pas
    # seulement le premier de la liste.
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: facil-backup
  annotations:
    helm.sh/hook: pre-upgrade
    helm.sh/hook-weight: "-2"
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      initContainers:
        - name: dump-postgres
          command: ["sh", "-c", "pg_dump -Fc -f /backups/x.dump"]
      containers:
        - name: backup-complete
          command: ["sh", "-c", "echo done || true"]
"""
    problems = guard_backup.check(doc)
    assert any(
        "facil-backup" in p and "backup-complete" in p and "|| true" in p for p in problems
    ), problems


def test_real_backup_job_has_no_or_true_anywhere(default_render):
    # Non-regression explicite sur le rendu REEL : le mirror-minio du chart
    # utilise `|| { echo FAIL... ; exit 1 ; }`, jamais `|| true`.
    docs = list(yaml.safe_load_all(default_render))
    backup_doc = next(
        d for d in docs if isinstance(d, dict) and d.get("kind") == "Job"
        and (d.get("metadata") or {}).get("name") == "facil-backup"
    )
    pod_spec = backup_doc["spec"]["template"]["spec"]
    for c in list(pod_spec.get("initContainers") or []) + list(pod_spec.get("containers") or []):
        assert "|| true" not in guard_backup._container_argv_text(c)
    assert guard_backup.check(default_render) == []


# --- B3 : backup.retain doit etre >= 1, et le dump re-verifie APRES la purge -

def test_retain_zero_is_refused_at_render_time(default_render):
    # Mutation-guard (B3) : retain=0 purgerait le dump du jour lui-meme (le
    # repertoire horodate qui vient d'etre cree est compte parmi les
    # candidats de la retention) -- le rendu doit refuser cette valeur
    # AVANT meme que le Job ne tourne (`{{ fail ... }}` -> `helm template`
    # sort non-zero).
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _helm_template("--set", "backup.retain=0")
    stderr = (excinfo.value.stderr or "")
    assert "backup.retain doit etre >= 1" in stderr


def test_retain_one_is_the_minimum_accepted_value():
    # Non-regression : 1 (la plus petite valeur permise) rend toujours,
    # contrairement a 0.
    rendered = _helm_template("--set", "backup.retain=1")
    assert "facil-backup" in rendered


def test_default_render_re_verifies_the_dump_after_the_retention_purge(default_render):
    # B3(b) : la garde fail-closed historique (dump vide juste apres pg_dump)
    # NE SUFFISAIT PAS -- la purge de retention peut supprimer ce meme dump
    # ensuite. Cette 2e verification, placee APRES la boucle `rm -rf`, doit
    # etre presente dans le rendu reel.
    docs = list(yaml.safe_load_all(default_render))
    backup_doc = next(
        d for d in docs if isinstance(d, dict) and d.get("kind") == "Job"
        and (d.get("metadata") or {}).get("name") == "facil-backup")
    dump_container = next(
        c for c in backup_doc["spec"]["template"]["spec"]["initContainers"]
        if c.get("name") == "dump-postgres")
    argv = guard_backup._container_argv_text(dump_container)
    # Deux verifications `[ ! -s ... ]` distinctes : une juste apres pg_dump,
    # une seconde apres la purge de retention.
    assert argv.count('[ ! -s "${DEST}/postgres.dump" ]') == 2, argv
    assert "disparu apres la purge de retention" in argv


# --- Fail-closed quand le composant est desactive (pas de faux positif) ------

def test_no_problem_when_backup_disabled():
    rendered = _helm_template("--set", "backup.enabled=false")
    assert "facil-backup" not in rendered
    assert guard_backup.check(rendered) == []


def test_no_problem_when_minio_disabled_backup_still_guarded(default_render):
    # backup.enabled reste true, minio.enabled=false -- l'initContainer
    # mirror-minio disparait (asymetrie documentee dans backup-job.yaml) mais
    # le Job persiste et reste soumis a la garde d'ordre/fail-closed.
    rendered = _helm_template("--set", "minio.enabled=false")
    assert "facil-backup" in rendered
    # `name: mirror-minio` (le conteneur), pas juste la sous-chaine
    # "mirror-minio" -- un commentaire shell du script dump-postgres
    # ("Retention ICI (pas dans mirror-minio)") la mentionne en PROSE et reste
    # dans le rendu que minio soit active ou non.
    assert "name: mirror-minio" not in rendered
    assert guard_backup.check(rendered) == []


# --- CLI (stdin) --------------------------------------------------------------

def test_cli_exits_nonzero_and_reports_on_weight_inversion(default_render):
    mutated = _mutate_backup_job(
        default_render,
        lambda doc: doc["metadata"]["annotations"].__setitem__("helm.sh/hook-weight", "1"),
    )
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_backup.py")],
        input=mutated, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "facil-db-role" in result.stderr


def test_cli_exits_zero_on_clean_render(default_render):
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_backup.py")],
        input=default_render, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK garde-backup" in result.stdout
