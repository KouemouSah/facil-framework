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

Deux invariants supplementaires, EUX AUSSI verifies PAR WORKLOAD (et non par
un comptage global -- meme biais tautologique qu'un `grep -c`, ou une
compensation entre deux workloads passerait inapercue) :
  - SEC-018 : `spec.selector.matchLabels` (Deployment/StatefulSet) doit porter
    `app.kubernetes.io/instance` -- sinon deux releases dans le meme namespace
    se volent leurs pods (le seul discriminant restant, `facil.component`,
    est identique entre releases).
  - Hardening runAsNonRoot/runAsUser : `runAsNonRoot: true` seul ne suffit pas
    -- nos images declarent leur USER par nom (`appuser`, `nextjs`), que le
    kubelet ne resout pas ; tout podSpec `runAsNonRoot: true` doit donc porter
    un `runAsUser` numerique, sous peine de `CreateContainerConfigError`.

Usage : helm template ... | python guard_resources.py
Exit 0 = propre, 1 = un ou plusieurs conteneurs/pods non durcis.
"""
from __future__ import annotations

import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "Job"}
# Kinds dont le selector est un vrai `spec.selector.matchLabels` cible par un
# Service (SEC-018). Les Job n'en ont pas -- Helm ne le rend pas (verifie sur
# le rendu reel : `spec.selector` est absent des deux Jobs de hook) et aucun
# Service ne les cible.
SELECTOR_CHECKED_KINDS = {"Deployment", "StatefulSet"}


def _iter_workload_docs(stream: str):
    """(kind, name, doc) pour chaque Deployment/StatefulSet/Job du rendu -- le
    doc COMPLET (pas seulement son pod_spec), pour que les invariants au niveau
    workload (ex. spec.selector) puissent aussi etre verifies PAR WORKLOAD."""
    for doc in yaml.safe_load_all(stream):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind not in WORKLOAD_KINDS:
            continue
        name = (doc.get("metadata") or {}).get("name", "?")
        yield kind, name, doc


def iter_workloads(stream: str):
    """(kind, name, pod_spec) pour chaque Deployment/StatefulSet/Job du rendu."""
    for kind, name, doc in _iter_workload_docs(stream):
        pod_spec = (((doc.get("spec") or {}).get("template") or {}).get("spec")) or {}
        yield kind, name, pod_spec


def check(stream: str) -> list[str]:
    problems: list[str] = []
    for kind, name, doc in _iter_workload_docs(stream):
        label = f"{kind}/{name}"
        pod = (((doc.get("spec") or {}).get("template") or {}).get("spec")) or {}

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

        if pod_sc.get("runAsNonRoot") is True and not isinstance(pod_sc.get("runAsUser"), int):
            problems.append(
                f"{label}: securityContext.runAsNonRoot=true sans runAsUser "
                f"numerique -- nos images declarent leur USER par nom (non "
                f"resolu par le kubelet), le pod serait refuse "
                f"(CreateContainerConfigError).")

        if kind in SELECTOR_CHECKED_KINDS:
            selector = ((doc.get("spec") or {}).get("selector")) or {}
            match_labels = selector.get("matchLabels") or {}
            if "app.kubernetes.io/instance" not in match_labels:
                problems.append(
                    f"{label}: spec.selector.matchLabels sans "
                    f"app.kubernetes.io/instance (SEC-018) -- deux releases "
                    f"dans le meme namespace se voleraient leurs pods, "
                    f"facil.component seul ne les distingue pas.")

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
