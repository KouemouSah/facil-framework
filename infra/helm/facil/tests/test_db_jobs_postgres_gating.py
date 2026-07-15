"""Tests TDD -- db-init-job.yaml sans garde `postgres.enabled` (dette #5).

`db-role-job.yaml` porte deja `{{- if .Values.postgres.enabled }}` ; `db-init-
job.yaml` ne l'avait pas. Avec `postgres.enabled=false`, `db-role` disparaissait
(plus de role applicatif cree) mais `db-init` tournait quand meme -- son
initContainer `wait-postgres` boucler ait indefiniment contre un hote Postgres
inexistant (`until pg_isready ...`), et `backoffLimit: 2` finirait par faire
echouer le Job, rompant `helm upgrade --install --atomic` pour une dependance
explicitement desactivee. Asymetrie entre deux Jobs qui partagent la meme
dependance dure sur Postgres.

Preuve par mutation : ce test echoue sur l'etat AVANT ce correctif (le Job
db-init est toujours rendu meme avec postgres.enabled=false) et passe apres.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

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


def _job_names(docs: list[dict]) -> set[str]:
    return {
        (d.get("metadata") or {}).get("name")
        for d in docs if d.get("kind") == "Job"
    }


def test_both_hook_jobs_present_by_default():
    docs = _helm_template()
    names = _job_names(docs)
    assert "facil-db-role" in names
    assert "facil-db-init" in names


def test_both_hook_jobs_disappear_when_postgres_disabled():
    # LE test qui aurait attrape la dette : db-init doit disparaitre en meme
    # temps que db-role quand postgres.enabled=false -- sinon il tenterait de
    # joindre un Postgres qui n'existe pas dans le rendu (aucun Service/
    # StatefulSet facil-postgres), boucle indefiniment dans wait-postgres puis
    # echoue apres backoffLimit=2, rompant --atomic pour une dependance
    # explicitement desactivee.
    docs = _helm_template("--set", "postgres.enabled=false")
    names = _job_names(docs)
    assert "facil-db-role" not in names
    assert "facil-db-init" not in names, (
        "db-init reste rendu sans Postgres -- son wait-postgres cible un "
        "hote qui n'existe pas dans le rendu (asymetrie avec db-role-job.yaml)."
    )
    # Non-regression : aucun objet Postgres (Service/StatefulSet) n'est rendu
    # non plus, sinon le test ci-dessus serait un faux negatif par accident.
    assert not any(
        (d.get("metadata") or {}).get("name") == "facil-postgres" for d in docs
    ), "postgres.enabled=false devrait aussi retirer le Service/StatefulSet facil-postgres"


def test_db_init_job_still_renders_when_postgres_enabled_explicitly():
    # Non-regression : `--set postgres.enabled=true` (valeur deja par defaut)
    # ne doit rien casser -- le Job reste present.
    docs = _helm_template("--set", "postgres.enabled=true")
    assert "facil-db-init" in _job_names(docs)
