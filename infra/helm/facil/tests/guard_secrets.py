#!/usr/bin/env python3
"""Garde-secret PARSEE sur le rendu `helm template` (remplace un grep contournable).

Invariants verifies sur TOUS les conteneurs (init inclus) de TOUS les manifests :
  1. toute env var dont le nom evoque un credential DOIT venir de `valueFrom`
     (secretKeyRef), jamais d'un `value:` litteral ;
  2. aucune URL ne porte de credential inline (`scheme://user:pass@host`), sauf
     interpolation k8s `$(VAR)` -- qui, elle, resout depuis un secretKeyRef ;
  3. le chart ne definit AUCUN `kind: Secret` (les Secrets sont crees hors Helm
     par deploy/providers/k3s.py -- sinon les valeurs finiraient versionnees).

L'ancienne garde (grep) ratait : les connection strings (REDIS_URL/DATABASE_URL
rendent en `value:`, jamais verifiees -- faux negatif le plus dangereux), ne
couvrait que 4 cles figees, ne regardait qu'UNE ligne apres `- name:` (un
commentaire YAML intercale la contournait), et ne matchait pas le style flow
(`{name: X, value: y}`) que le chart utilise deja ailleurs. Voir
tests/test_guard_secrets.py pour la preuve par mutation de chaque invariant.

Usage : helm template ... | python guard_secrets.py
Exit 0 = propre, 1 = fuite.
"""
from __future__ import annotations

import re
import sys

import yaml

# Un nom d'env var qui evoque un credential. Suffisamment large pour couvrir les
# ajouts futurs (le point aveugle de l'ancienne garde : une liste de 4 cles figee).
CREDENTIAL_RE = re.compile(
    r"(PASSWORD|PASSWD|SECRET|TOKEN|_KEY$|APIKEY|API_KEY|CREDENTIAL|_URL$|_DSN$)",
    re.I,
)

# Env vars a `value:` litteral autorisees malgre un nom credential-like : ce
# sont des URLs SANS credential embarque (nom de service + port). Toute
# addition ici DOIT etre justifiee -- une entree qui ne correspond a AUCUNE env
# var du rendu reel est un defaut symetrique ("un test qui ne peut pas echouer
# est un defaut grave" s'applique aussi a une allowlist jamais exercee).
# Verifie contre le rendu reel (helm template) : voir
# test_every_allowlist_entry_is_load_bearing dans test_guard_secrets.py, qui
# echouerait si une de ces entrees devenait morte.
ALLOWED_LITERAL = {
    # frontend.yaml -> `http://facil-backend:8080` : nom de service k8s + port
    # interne, pas de user:pass@. Matche `_URL$` a cause du NOM de la variable,
    # mais ce n'est pas un secret -- c'est juste l'URL backend<->frontend, et
    # elle ne peut techniquement pas venir d'un secretKeyRef (rien a y stocker).
    "INTERNAL_API_URL",
}
# credential inline dans une URL : scheme://user:pass@host (hors interpolation
# $(VAR)). Le nom d'utilisateur est OPTIONNEL (`*`, pas `+`) : nos URLs Redis
# rendent en `redis://:PASSWORD@host` (convention redis -- pas de username),
# et un `+` laissait passer sans le detecter la mutation `redis://:hunter2@...`
# (capturee par TDD : voir test_catches_inline_credential_in_redis_url).
INLINE_CRED_RE = re.compile(r"://[^/\s:]*:(?!\$\()[^/\s@]+@")


def iter_containers(doc: dict):
    spec = (doc.get("spec") or {})
    tmpl = (spec.get("template") or {}).get("spec") or spec
    for key in ("containers", "initContainers"):
        for c in (tmpl.get(key) or []):
            yield c


def check(stream: str) -> list[str]:
    problems: list[str] = []
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind", "")
        name = (doc.get("metadata") or {}).get("name", "?")

        if kind == "Secret":
            problems.append(
                f"{name}: le chart definit un `kind: Secret` -- interdit. Les Secrets "
                f"sont crees hors Helm par deploy/providers/k3s.py.")

        for c in iter_containers(doc):
            for env in (c.get("env") or []):
                ename, val = env.get("name", ""), env.get("value")
                if val is None:
                    continue  # valueFrom -> conforme
                val = str(val)
                if CREDENTIAL_RE.search(ename) and ename not in ALLOWED_LITERAL:
                    if not INLINE_CRED_RE.search(val) and "$(" not in val:
                        problems.append(
                            f"{name}/{c.get('name')}: env `{ename}` a un `value:` "
                            f"litteral alors que son nom evoque un credential.")
                if INLINE_CRED_RE.search(val):
                    problems.append(
                        f"{name}/{c.get('name')}: credential inline dans l'URL de "
                        f"`{ename}` (attendu : $(VAR) resolue depuis un secretKeyRef).")
    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-secret (parsee) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-secret (parsee)")
