"""Tests TDD pour la garde-Ingress PARSEE (SEC-024) — infra/helm/facil/tests/guard_ingress.py.

Piege documente dans le brief de la tache H3 : avec `pathType: Prefix`, `/`
matche TOUT chemin -- si `/api` etait avale par la regle `/` (mauvais ordre,
mauvais Service, mauvais port), un simple `grep -q "kind: Ingress"` +
`grep -q "ingressClassName: traefik"` continuerait de passer alors qu'AUCUNE
requete API ne fonctionnerait. Ce guard verifie -- comme guard_secrets.py /
guard_resources.py / guard_networkpolicy.py (meme convention, DRY) -- des
invariants STRUCTURELS sur le rendu reel : classe d'ingress, et pour chaque
route attendue (`/api` -> backend, `/` -> frontend) : pathType, Service
resolu (via le VRAI selector.facil.component du Service rendu, pas son nom),
et port qui correspond au port REELLEMENT declare par ce Service.

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
import guard_ingress  # noqa: E402


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
    assert guard_ingress.check(default_render) == []


def test_clean_onprem_overlay_render_has_no_problems():
    rendered = _helm_template("-f", str(CHART_DIR / "values-onprem.yaml"))
    assert guard_ingress.check(rendered) == []


def test_exactly_one_ingress_rendered_by_default(default_render):
    docs = guard_ingress._load_docs(default_render)
    ingresses = guard_ingress.iter_ingresses(docs)
    assert len(ingresses) == 1, ingresses


def test_ingress_can_be_disabled_no_crash_no_false_pass():
    rendered = _helm_template("--set", "ingress.enabled=false")
    assert "kind: Ingress" not in rendered
    problems = guard_ingress.check(rendered)
    assert any("aucun objet kind: Ingress" in p for p in problems), problems


# --- Invariant 1 : ingressClassName == traefik -------------------------------

def test_ingress_class_is_traefik(default_render):
    docs = guard_ingress._load_docs(default_render)
    ing = guard_ingress.iter_ingresses(docs)[0]
    assert ing["spec"]["ingressClassName"] == "traefik"


def test_catches_wrong_ingress_class(default_render):
    mutated = default_render.replace(
        "ingressClassName: traefik", "ingressClassName: nginx", 1
    )
    problems = guard_ingress.check(mutated)
    assert any("ingressClassName" in p and "nginx" in p for p in problems), problems


# --- Invariant 2 (central) : /api -> backend, / -> frontend, bon port -------

def test_api_path_routes_to_backend_service(default_render):
    docs = guard_ingress._load_docs(default_render)
    ing = guard_ingress.iter_ingresses(docs)[0]
    paths = ing["spec"]["rules"][0]["http"]["paths"]
    api_path = next(p for p in paths if p["path"] == "/api")
    assert api_path["backend"]["service"]["name"] == "facil-backend"


def test_root_path_routes_to_frontend_service(default_render):
    docs = guard_ingress._load_docs(default_render)
    ing = guard_ingress.iter_ingresses(docs)[0]
    paths = ing["spec"]["rules"][0]["http"]["paths"]
    root_path = next(p for p in paths if p["path"] == "/")
    assert root_path["backend"]["service"]["name"] == "facil-frontend"


def _mutate_api_backend_service_name(rendered: str, new_service_name: str) -> str:
    """Repointe UNIQUEMENT le Service cible du path `/api` de l'Ingress (round-trip
    YAML, pas un remplacement texte global qui muterait aussi le Service lui-meme
    ou d'autres references au meme nom)."""
    docs = list(yaml.safe_load_all(rendered))
    mutated_one = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Ingress":
            for rule in doc["spec"]["rules"]:
                for p in rule["http"]["paths"]:
                    if p["path"] == "/api":
                        p["backend"]["service"]["name"] = new_service_name
                        mutated_one = True
    assert mutated_one, "fixture n'a pas trouve le path /api de l'Ingress -- test casse silencieusement"
    return yaml.safe_dump_all(docs)


def test_catches_api_path_swapped_to_frontend_service(default_render):
    # Preuve par mutation EXPLICITEMENT demandee par le brief : `/api` route vers
    # le Service frontend au lieu du backend -- toutes les requetes API iraient
    # au frontend (404/mauvaise app). Un grep "kind: Ingress" ne le detecterait
    # jamais puisque l'Ingress existe toujours et reste par ailleurs valide.
    mutated = _mutate_api_backend_service_name(default_render, "facil-frontend")
    problems = guard_ingress.check(mutated)
    assert any(
        "/api" in p and "facil-frontend" in p and "backend" in p for p in problems
    ), problems


def test_catches_route_to_nonexistent_service(default_render):
    mutated = _mutate_api_backend_service_name(default_render, "facil-does-not-exist")
    problems = guard_ingress.check(mutated)
    assert any("n'existe PAS" in p for p in problems), problems


def _mutate_api_backend_port(rendered: str, new_port: int) -> str:
    docs = list(yaml.safe_load_all(rendered))
    mutated_one = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Ingress":
            for rule in doc["spec"]["rules"]:
                for p in rule["http"]["paths"]:
                    if p["path"] == "/api":
                        p["backend"]["service"]["port"]["number"] = new_port
                        mutated_one = True
    assert mutated_one, "fixture n'a pas trouve le path /api de l'Ingress -- test casse silencieusement"
    return yaml.safe_dump_all(docs)


def test_catches_wrong_port_on_correct_service(default_render):
    mutated = _mutate_api_backend_port(default_render, 9999)
    problems = guard_ingress.check(mutated)
    assert any("port errone" in p or "9999" in p for p in problems), problems


def test_catches_path_type_exact_instead_of_prefix(default_render):
    mutated = default_render.replace(
        "path: /api\n            pathType: Prefix",
        "path: /api\n            pathType: Exact",
        1,
    )
    assert "pathType: Exact" in mutated, "mutation non appliquee -- verifier l'indentation du rendu"
    problems = guard_ingress.check(mutated)
    assert any("pathType" in p and "Exact" in p for p in problems), problems


def test_catches_missing_api_route_entirely():
    doc = """
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: facil-ingress
spec:
  ingressClassName: traefik
  rules:
    - host: facil.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: facil-frontend
                port:
                  number: 3000
---
apiVersion: v1
kind: Service
metadata:
  name: facil-frontend
spec:
  selector:
    facil.component: frontend
  ports:
    - port: 3000
"""
    problems = guard_ingress.check(doc)
    assert any("/api" in p for p in problems), problems


# --- CLI (stdin) --------------------------------------------------------------

def test_cli_exits_nonzero_and_reports_on_mutation(default_render):
    mutated = _mutate_api_backend_service_name(default_render, "facil-frontend")
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_ingress.py")],
        input=mutated, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "SEC-024" in result.stderr


def test_cli_exits_zero_on_clean_render(default_render):
    result = subprocess.run(
        [sys.executable, str(TESTS_DIR / "guard_ingress.py")],
        input=default_render, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "OK garde-ingress" in result.stdout
