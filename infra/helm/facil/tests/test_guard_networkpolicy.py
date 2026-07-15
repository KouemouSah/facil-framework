"""Tests TDD pour la garde-NetworkPolicy PARSEE (SEC-012) — infra/helm/facil/tests/guard_networkpolicy.py.

Le piege documente dans le brief de la tache H2 : un `podSelector` mal cible ne
protege RIEN tout en ayant l'air correct (`kind: NetworkPolicy` + `policyTypes`
presents) -- ou pire, coupe la stack en ciblant un label que le chart ne rend
jamais. Un `grep -q "kind: NetworkPolicy"` ne prouve rien sur le ciblage. Ce
guard verifie -- comme guard_secrets.py / guard_resources.py (meme convention,
DRY) -- des invariants STRUCTURELS sur le rendu reel :

  1. Au moins une NetworkPolicy `default-deny` (podSelector: {}) existe, et son
     policyTypes est EXACTEMENT [Ingress] (pas Egress -- casserait le DNS vers
     kube-dns dans kube-system, hors du namespace de la release).
  2. AUCUNE NetworkPolicy du chart ne porte `Egress` dans policyTypes (durcissement
     partiel assume : seul l'ingress est deny-by-default).
  3. Toute valeur `facil.component` referencee par un podSelector (cible OU peer
     `ingress[].from[].podSelector`) DOIT correspondre a un `facil.component`
     REELLEMENT porte par un pod-template du rendu (Deployment/StatefulSet/Job).
     C'est l'invariant central : une regression du helper `facil.selectorLabels`
     (ex. renommage de la cle, tache H4) ou une faute de frappe dans un policy
     doit faire rougir ce test -- pas juste "passer avec un selecteur inerte".

Chaque invariant est prouve par MUTATION (fabriquer la regression, verifier
que la garde rougit, restaurer) -- "un test qui ne peut pas echouer est un
defaut grave" (cf. CLAUDE.md).
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
import guard_networkpolicy  # noqa: E402


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
    assert guard_networkpolicy.check(default_render) == []


def test_clean_onprem_overlay_render_has_no_problems():
    rendered = _helm_template("-f", str(CHART_DIR / "values-onprem.yaml"))
    assert guard_networkpolicy.check(rendered) == []


def test_all_expected_components_are_observed(default_render):
    # Non-regression du parseur : si `iter_observed_components` cessait de voir
    # un composant, les invariants ci-dessous "passeraient" par absence -- faux
    # negatif silencieux. On verifie les 8 composants attendus.
    observed = guard_networkpolicy.iter_observed_components(
        guard_networkpolicy._load_docs(default_render)
    )
    expected = {
        "postgres", "redis", "minio", "openbao",
        "backend", "frontend", "db-init", "db-role",
    }
    assert expected <= observed, observed


def test_at_least_four_networkpolicies_rendered(default_render):
    policies = guard_networkpolicy.iter_networkpolicies(
        guard_networkpolicy._load_docs(default_render)
    )
    assert len(policies) >= 4, policies


# --- Invariant 1 : default-deny existe, policyTypes == [Ingress] uniquement -

def test_default_deny_policy_present_with_ingress_only(default_render):
    docs = guard_networkpolicy._load_docs(default_render)
    policies = guard_networkpolicy.iter_networkpolicies(docs)
    deny_all = [p for p in policies if (p.get("spec") or {}).get("podSelector") == {}]
    assert len(deny_all) == 1, deny_all
    assert deny_all[0]["spec"]["policyTypes"] == ["Ingress"], deny_all[0]["spec"]


def test_catches_missing_default_deny_policy(default_render):
    # Mutation : on retire la policy default-deny (podSelector: {}) du rendu en
    # remplacant son marqueur unique -- simule une regression de template.
    mutated = default_render.replace(
        "name: facil-default-deny", "name: facil-oops-renamed", 1
    ).replace(
        "podSelector: {}", "podSelector:\n    matchLabels:\n      facil.component: backend",
        1,
    )
    problems = guard_networkpolicy.check(mutated)
    assert any("default-deny" in p for p in problems), problems


# --- Invariant 2 : jamais d'Egress dans policyTypes (DNS resterait ouvert) ---

def test_catches_egress_in_policy_types():
    doc = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: evil
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
"""
    problems = guard_networkpolicy.check(doc)
    assert any("Egress" in p for p in problems), problems


# --- Invariant 3 (central) : podSelector doit matcher un pod REEL du rendu --

def _mutate_backend_pod_label(rendered: str, new_value: str) -> str:
    """Renomme UNIQUEMENT le `facil.component` porte par le pod-template reel
    du Deployment `facil-backend` (round-trip YAML, pas un remplacement texte
    global qui muterait aussi -- de facon incoherente -- les selecteurs des
    NetworkPolicy qui reutilisent le meme libelle)."""
    docs = list(yaml.safe_load_all(rendered))
    mutated_one = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Deployment" and \
                (doc.get("metadata") or {}).get("name") == "facil-backend":
            doc["spec"]["template"]["metadata"]["labels"][guard_networkpolicy.COMPONENT_LABEL] = new_value
            mutated_one = True
    assert mutated_one, "fixture n'a pas trouve le pod-template facil-backend -- test casse silencieusement"
    return yaml.safe_dump_all(docs)


def test_catches_target_selector_matching_no_real_pod(default_render):
    # Preuve par mutation demandee explicitement par le brief : le pod REEL du
    # backend (Deployment) perd son label `facil.component: backend` (simule
    # une regression du helper `facil.selectorLabels`, tache H4) alors que la
    # NetworkPolicy `allow-backend-from-frontend` continue de cibler
    # `facil.component: backend` (matchLabels, valeur UNIQUE) -- elle devient
    # entierement inerte : plus aucun pod ne matche. Le guard doit rougir.
    mutated = _mutate_backend_pod_label(default_render, "backend-typo-inexistant")
    problems = guard_networkpolicy.check(mutated)
    assert any("backend" in p and "INERTE" in p for p in problems), problems


def test_catches_match_expressions_selector_entirely_invalid():
    # matchExpressions/In : semantique OR -- un selecteur n'est INERTE que si
    # TOUTES ses valeurs sont invalides (voir doc de check() : un typo sur UNE
    # SEULE valeur d'une liste par ailleurs valide n'est pas flag ici, pour ne
    # pas produire de faux-positif quand un composant est legitimement
    # desactive -- voir test_partial_typo_in_list_is_a_documented_tradeoff).
    doc = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: evil
spec:
  podSelector:
    matchExpressions:
      - key: facil.component
        operator: In
        values: [postgres-typo, redis-typo, minio-typo, openbao-typo]
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: facil.component
                operator: In
                values: [backend-typo]
"""
    problems = guard_networkpolicy.check(doc)
    assert any("postgres-typo" in p and "INERTE" in p for p in problems), problems


def test_partial_typo_in_list_is_a_documented_tradeoff(default_render):
    # Compromis assume (documente dans guard_networkpolicy.check()) : un typo
    # sur UNE SEULE valeur d'un matchExpressions/In par ailleurs valide (ex.
    # openbao -> openbao-typo, alors que postgres/redis/minio restent corrects)
    # N'EST PAS flag par ce guard generique -- sinon un composant legitimement
    # desactive (openbao.enabled=false) produirait un faux-positif identique.
    # Cette lacune precise EST couverte par une assertion dediee : voir
    # test_datastores_policy_allows_migration_jobs, qui verifie un sous-ensemble
    # EXACT {postgres, redis, minio, openbao} et rougirait sur ce meme typo.
    mutated = default_render.replace("values: [postgres, redis, minio, openbao]",
                                      "values: [postgres, redis, minio, openbao-typo]")
    assert "openbao-typo" in mutated, "mutation non appliquee -- verifier le format du rendu"
    problems = guard_networkpolicy.check(mutated)
    assert problems == [], problems


def test_catches_ingress_from_peer_selector_matching_no_real_pod():
    doc = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: evil
spec:
  podSelector:
    matchLabels:
      facil.component: backend
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              facil.component: frontend-typo
"""
    problems = guard_networkpolicy.check(doc)
    assert any("frontend-typo" in p for p in problems), problems


def test_clean_targeted_doc_with_real_components_not_flagged():
    doc = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: facil-backend
spec:
  template:
    metadata:
      labels:
        facil.component: backend
    spec:
      containers: []
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: facil-default-deny
spec:
  podSelector: {}
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: fine
spec:
  podSelector:
    matchLabels:
      facil.component: backend
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              facil.component: backend
"""
    assert guard_networkpolicy.check(doc) == []


# --- Invariant 4 : datastores acceptent backend + db-init + db-role ---------

def test_datastores_policy_allows_migration_jobs(default_render):
    docs = guard_networkpolicy._load_docs(default_render)
    policies = guard_networkpolicy.iter_networkpolicies(docs)
    datastore_pol = None
    for p in policies:
        targets = guard_networkpolicy.selector_components((p.get("spec") or {}).get("podSelector") or {})
        if {"postgres", "redis", "minio", "openbao"} <= targets:
            datastore_pol = p
            break
    assert datastore_pol is not None, policies
    peers: set[str] = set()
    for rule in (datastore_pol["spec"].get("ingress") or []):
        for frm in (rule.get("from") or []):
            if "podSelector" in frm:
                peers |= guard_networkpolicy.selector_components(frm["podSelector"])
    assert {"backend", "db-init", "db-role"} <= peers, peers
    # Le frontend ne doit PAS pouvoir atteindre les datastores directement.
    assert "frontend" not in peers, peers


# --- CLI (stdin) --------------------------------------------------------------

def test_cli_exits_nonzero_and_reports_on_mutation(default_render):
    mutated = _mutate_backend_pod_label(default_render, "backend-typo-inexistant")
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_networkpolicy.py")],
        input=mutated, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "INERTE" in result.stderr


def test_cli_exits_zero_on_clean_render(default_render):
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_networkpolicy.py")],
        input=default_render, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK garde-networkpolicy" in result.stdout


# --- Non-regression : composant desactive -> pas de crash, rien a signaler --

def test_fail_closed_when_openbao_disabled_no_crash_no_silent_pass():
    rendered = _helm_template("--set", "openbao.enabled=false")
    assert "facil-openbao" not in rendered
    assert guard_networkpolicy.check(rendered) == []
