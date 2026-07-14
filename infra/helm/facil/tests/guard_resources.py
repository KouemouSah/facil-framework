#!/usr/bin/env python3
"""Garde-resources PARSEE (SEC-015) sur le rendu `helm template`.

Sur un k3s **mono-noeud**, un pod sans `resources.limits` peut OOM-killer le
noeud entier (pas de cgroup parent qui l'isole) -- DoS trivial. Le profil PSS
`restricted` exige en plus `seccompProfile`, `allowPrivilegeEscalation: false`
et `capabilities.drop: [ALL]` ; aucun pod de ce chart n'appelle l'API k8s, donc
aucun n'a besoin du token de ServiceAccount monte par defaut.

Un comptage global (`grep -c 'limits:'` sur tout le rendu) est une assertion
TAUTOLOGIQUE : plusieurs conteneurs dans un workload peuvent porter des
`limits:` en nombre suffisant pour masquer qu'UN SEUL container/initContainer
d'un AUTRE workload n'en a pas. Ce parseur verifie l'invariant PAR CONTENEUR
(containers + initContainers) DE CHAQUE workload (Deployment/StatefulSet/Job),
comme guard_secrets.py le fait deja pour les env vars -- meme convention,
reutilisee ici (DRY). Voir test_guard_resources.py pour la preuve par
mutation de chaque invariant.

Usage : helm template ... | python guard_resources.py
Exit 0 = propre, 1 = un ou plusieurs conteneurs/pods non durcis.
"""
from __future__ import annotations

import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "Job"}


def iter_workloads(stream: str):
    """(kind, name, pod_spec) pour chaque Deployment/StatefulSet/Job du rendu."""
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind not in WORKLOAD_KINDS:
            continue
        name = (doc.get("metadata") or {}).get("name", "?")
        pod_spec = (((doc.get("spec") or {}).get("template") or {}).get("spec")) or {}
        yield kind, name, pod_spec


def check(stream: str) -> list[str]:
    problems: list[str] = []
    for kind, name, pod in iter_workloads(stream):
        label = f"{kind}/{name}"

        if pod.get("automountServiceAccountToken") is not False:
            problems.append(
                f"{label}: automountServiceAccountToken != false -- aucun pod "
                f"de ce chart n'appelle l'API k8s, le token ne doit pas etre monte.")

        pod_sc = pod.get("securityContext") or {}
        seccomp = pod_sc.get("seccompProfile") or {}
        if seccomp.get("type") != "RuntimeDefault":
            problems.append(
                f"{label}: securityContext.seccompProfile.type != RuntimeDefault "
                f"(requis par le profil PSS restricted).")

        containers = list(pod.get("containers") or []) + list(pod.get("initContainers") or [])
        for c in containers:
            cname = c.get("name", "?")
            clabel = f"{label}/{cname}"
            csc = c.get("securityContext") or {}
            resources = c.get("resources") or {}

            if not resources.get("limits"):
                problems.append(
                    f"{clabel}: resources.limits absent -- sur mono-noeud, ce "
                    f"conteneur peut OOM-killer le noeud entier.")
            if not resources.get("requests"):
                problems.append(f"{clabel}: resources.requests absent.")
            if csc.get("readOnlyRootFilesystem") is not True:
                problems.append(f"{clabel}: readOnlyRootFilesystem != true.")
            if csc.get("allowPrivilegeEscalation") is not False:
                problems.append(f"{clabel}: allowPrivilegeEscalation != false.")
            caps = csc.get("capabilities") or {}
            if caps.get("drop") != ["ALL"]:
                problems.append(f"{clabel}: capabilities.drop != [\"ALL\"].")
    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-resources (SEC-015) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-resources (SEC-015)")
