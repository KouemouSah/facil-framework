"""Tests TDD -- knob `frontend.port` mal cable (dette #4).

`frontend.yaml` ne posait PAS d'env `PORT`, alors que l'image bake `PORT=3000`
(`packages/web/Dockerfile:27`, Next standalone lit `process.env.PORT` pour
choisir son port d'ecoute). Surcharger `frontend.port: 3001` changeait donc le
Service (port + targetPort) et le `containerPort` de la Deployment, mais le
process Next continuait d'ecouter sur 3000 -- PANNE SILENCIEUSE (connection
refused, aucune erreur au deploy ni au smoke superficiel). Le backend, lui,
posait deja son PORT correctement (`backend.yaml`) -- asymetrie.

Preuve par mutation : ce test echoue sur l'etat AVANT ce correctif (env PORT
absent de la Deployment frontend) et passe apres. Voir aussi le rapport pour
la demonstration explicite (retirer l'env PORT de frontend.yaml -> rouge).
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


def _helm_template(*extra_args: str) -> list[dict]:
    cmd = ["helm", "template", "rel", str(CHART_DIR), *extra_args]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [d for d in yaml.safe_load_all(result.stdout) if isinstance(d, dict)]


def _deployment(docs: list[dict], name: str) -> dict:
    return next(
        d for d in docs if d.get("kind") == "Deployment"
        and (d.get("metadata") or {}).get("name") == name
    )


def _service(docs: list[dict], name: str) -> dict:
    return next(
        d for d in docs if d.get("kind") == "Service"
        and (d.get("metadata") or {}).get("name") == name
    )


def _env_value(container: dict, name: str) -> str | None:
    for env in (container.get("env") or []):
        if env.get("name") == name:
            return env.get("value")
    return None


# --- Frontend : le knob dont le cablage etait casse --------------------------

def test_frontend_port_env_matches_default_value():
    docs = _helm_template()
    dep = _deployment(docs, "facil-frontend")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert _env_value(container, "PORT") == "3000"


def test_frontend_port_override_flows_to_container_env_service_and_port():
    # LE test qui aurait attrape la dette : surcharger frontend.port=3001 doit
    # faire converger TOUT (env PORT, containerPort, Service port/targetPort)
    # vers 3001 -- sinon le process ecoute encore sur l'ancien port par defaut
    # de l'image (3000) pendant que le Service route vers 3001 : panne
    # silencieuse (ECONNREFUSED), invisible sans lire l'env du conteneur.
    docs = _helm_template("--set", "frontend.port=3001")
    dep = _deployment(docs, "facil-frontend")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    svc = _service(docs, "facil-frontend")

    assert _env_value(container, "PORT") == "3001", (
        "PORT absent/desynchronise de frontend.port -- le process Next "
        "continuerait d'ecouter sur le port bake dans l'image (3000)."
    )
    assert container["ports"][0]["containerPort"] == 3001
    assert svc["spec"]["ports"][0]["port"] == 3001
    assert svc["spec"]["ports"][0]["targetPort"] == 3001


def test_frontend_readiness_probe_port_stays_in_sync():
    # La readinessProbe (backend.yaml + frontend.yaml) pointe deja sur
    # .Values.*.port -- non-regression : elle doit suivre le meme override.
    docs = _helm_template("--set", "frontend.port=3001")
    dep = _deployment(docs, "facil-frontend")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["httpGet"]["port"] == 3001


# --- Backend : deja correct -- non-regression / parite ----------------------

def test_backend_port_env_matches_default_value():
    docs = _helm_template()
    dep = _deployment(docs, "facil-backend")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert _env_value(container, "PORT") == "8080"


def test_backend_port_override_flows_to_container_env_service_and_port():
    docs = _helm_template("--set", "backend.port=9090")
    dep = _deployment(docs, "facil-backend")
    container = dep["spec"]["template"]["spec"]["containers"][0]
    svc = _service(docs, "facil-backend")

    assert _env_value(container, "PORT") == "9090"
    assert container["ports"][0]["containerPort"] == 9090
    assert svc["spec"]["ports"][0]["port"] == 9090
    assert svc["spec"]["ports"][0]["targetPort"] == 9090
