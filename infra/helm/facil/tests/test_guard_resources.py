"""Tests TDD pour la garde-resources PARSEE (SEC-015) — infra/helm/facil/tests/guard_resources.py.

Chaque invariant est prouve par MUTATION (on fabrique la regression et on
verifie que la garde rougit) -- "un test qui ne peut pas echouer est un
defaut grave" (cf. CLAUDE.md). En particulier : un comptage global du style
`grep -c 'limits:'` sur tout le rendu est une assertion TAUTOLOGIQUE (un autre
workload peut compenser le compte) -- ce test prouve que la garde reste rouge
meme quand UN SEUL container d'un SEUL workload perd ses limits, parmi tous
les autres qui les gardent.
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
import guard_resources  # noqa: E402


def _helm_template(*extra_args: str) -> str:
    cmd = ["helm", "template", "rel", str(CHART_DIR), *extra_args]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture(scope="module")
def default_render() -> str:
    return _helm_template()


# --- Invariant 0 : rendu reel propre -----------------------------------------

def test_clean_default_render_has_no_problems(default_render):
    assert guard_resources.check(default_render) == []


def test_clean_onprem_overlay_render_has_no_problems():
    rendered = _helm_template("-f", str(CHART_DIR / "values-onprem.yaml"))
    assert guard_resources.check(rendered) == []


def test_all_expected_workloads_are_seen(default_render):
    # Non-regression du parseur lui-meme : si `iter_workloads` cessait de
    # reconnaitre un kind ou un doc, les invariants ci-dessous passeraient
    # "propre" par absence -- faux negatif silencieux. On verifie qu'on voit
    # bien les 8 workloads attendus (2 Jobs de hook + 6 Deployment/StatefulSet).
    seen = {f"{kind}/{name}" for kind, name, _ in guard_resources.iter_workloads(default_render)}
    expected = {
        "StatefulSet/facil-postgres", "StatefulSet/facil-minio", "StatefulSet/facil-openbao",
        "Deployment/facil-redis", "Deployment/facil-backend", "Deployment/facil-frontend",
        "Job/facil-db-role", "Job/facil-db-init",
    }
    assert expected <= seen, seen


# --- Invariant 1 : resources.limits par conteneur, PAS un comptage global ---

def test_catches_single_container_missing_limits_among_many_workloads(default_render):
    # Mutation ciblee sur UN SEUL workload (postgres), les 7 AUTRES gardant
    # leurs limits intactes : un comptage global `grep -c limits:` resterait
    # vert grace a eux -- exactement le biais tautologique documente dans ce
    # projet ("sept" occurrences passees). On mute structurellement (yaml
    # round-trip) plutot que par un match de texte fragile a l'indentation.
    docs = list(yaml.safe_load_all(default_render))
    mutated_one = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "StatefulSet" and \
                (doc.get("metadata") or {}).get("name") == "facil-postgres":
            containers = doc["spec"]["template"]["spec"]["containers"]
            for c in containers:
                if c.get("name") == "postgres":
                    del c["resources"]["limits"]
                    mutated_one = True
    assert mutated_one, "fixture n'a pas trouve le container postgres -- test casse silencieusement"
    mutated = yaml.safe_dump_all(docs)

    problems = guard_resources.check(mutated)
    assert any("facil-postgres" in p and "resources.limits absent" in p for p in problems), problems
    # Les 7 autres workloads gardent leurs limits -- un seul finding, pas plus.
    limits_problems = [p for p in problems if "resources.limits absent" in p]
    assert len(limits_problems) == 1, limits_problems


def test_catches_missing_limits_via_direct_doc_mutation():
    # Preuve independante du format d'indentation exact du rendu Helm : on
    # construit directement un doc minimal avec limits absent.
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: evil
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
"""
    problems = guard_resources.check(doc)
    assert any("evil/evil" in p and "resources.limits absent" in p for p in problems), problems


def test_clean_doc_with_limits_is_not_flagged():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fine
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: fine
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    assert guard_resources.check(doc) == []


def test_init_containers_are_checked_too_for_limits():
    doc = """
apiVersion: batch/v1
kind: Job
metadata:
  name: evil-job
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      initContainers:
        - name: evil-init
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
      containers:
        - name: main
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    problems = guard_resources.check(doc)
    assert any("evil-job/evil-init" in p and "resources.limits absent" in p for p in problems), problems


# --- Invariant 2 : seccompProfile au niveau pod -------------------------------

def test_catches_missing_seccomp_profile(default_render):
    mutated = default_render.replace("seccompProfile: { type: RuntimeDefault }", "", 1)
    problems = guard_resources.check(mutated)
    assert any("seccompProfile" in p for p in problems), problems


def test_catches_wrong_seccomp_profile_type():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: Unconfined }
      containers:
        - name: evil
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    problems = guard_resources.check(doc)
    assert any("seccompProfile" in p for p in problems), problems


# --- Invariant 3 : automountServiceAccountToken: false ------------------------

def test_catches_missing_automount_false(default_render):
    mutated = default_render.replace("automountServiceAccountToken: false", "", 1)
    problems = guard_resources.check(mutated)
    assert any("automountServiceAccountToken" in p for p in problems), problems


def test_catches_automount_true():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      automountServiceAccountToken: true
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: evil
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    problems = guard_resources.check(doc)
    assert any("automountServiceAccountToken" in p for p in problems), problems


# --- Invariant 4 : readOnlyRootFilesystem: true, PAR CONTENEUR ----------------

def test_catches_single_container_missing_readonly_rootfs(default_render):
    mutated = default_render.replace("readOnlyRootFilesystem: true", "readOnlyRootFilesystem: false", 1)
    problems = guard_resources.check(mutated)
    assert any("readOnlyRootFilesystem != true" in p for p in problems), problems


# --- Invariant 5 : allowPrivilegeEscalation: false, capabilities.drop --------

def test_catches_allow_privilege_escalation_true():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: evil
          securityContext:
            allowPrivilegeEscalation: true
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    problems = guard_resources.check(doc)
    assert any("allowPrivilegeEscalation" in p for p in problems), problems


def test_catches_missing_capabilities_drop_all():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evil
spec:
  template:
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: evil
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["NET_RAW"] }
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { cpu: 200m, memory: 128Mi }
"""
    problems = guard_resources.check(doc)
    assert any("capabilities.drop" in p for p in problems), problems


def test_openbao_ipc_lock_exception_still_passes(default_render):
    # Exception documentee : openbao garde `capabilities.add: [IPC_LOCK]` en
    # plus de `drop: [ALL]` -- la garde ne doit PAS le rejeter.
    assert "IPC_LOCK" in default_render
    assert guard_resources.check(default_render) == []


# --- Non-regression : composant desactive -> pas de crash, rien a signaler --

def test_fail_closed_when_openbao_disabled_no_crash_no_silent_pass():
    rendered = _helm_template("--set", "openbao.enabled=false")
    assert "facil-openbao" not in rendered
    assert guard_resources.check(rendered) == []


# --- CLI (stdin) --------------------------------------------------------------

def test_cli_exits_nonzero_and_reports_on_mutation(default_render):
    mutated = default_render.replace("readOnlyRootFilesystem: true", "readOnlyRootFilesystem: false", 1)
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_resources.py")],
        input=mutated, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "readOnlyRootFilesystem" in result.stderr


def test_cli_exits_zero_on_clean_render(default_render):
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_resources.py")],
        input=default_render, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK garde-resources" in result.stdout
