#!/usr/bin/env python3
"""Garde-Ingress PARSEE (SEC-024) sur le rendu `helm template`.

Sans Ingress, la stack deployee n'est joignable de NULLE PART (aucun Ingress,
aucun NodePort) -- seul un `kubectl port-forward` y accede. La tache H3 pose un
Ingress Traefik single-origin (anti-CORS) : `/api` -> backend, `/` -> frontend,
sur le meme hote.

Un `grep -q "kind: Ingress"` + `grep -q "ingressClassName: traefik"` ne prouve
RIEN sur le ROUTAGE : un manifeste qui pointe `/api` vers le Service frontend
(ou un port qui ne correspond a aucun Service reel) rend toujours ces deux
chaines -- la garde-grep passe alors qu'aucune requete API ne fonctionnerait.
Ce parseur verifie -- comme guard_secrets.py / guard_resources.py /
guard_networkpolicy.py (meme convention, DRY) -- des invariants STRUCTURELS
sur le rendu reel :

  1. Exactement un objet `kind: Ingress` est rendu.
  2. `spec.ingressClassName` == la classe attendue (Traefik = l'ingress
     controller embarque de k3s ; un `ingressClassName` errone laisserait
     l'Ingress orphelin, aucun controller ne le prend en charge).
  3. Chaque route attendue (`/api` -> composant "backend", `/` -> composant
     "frontend") existe dans `spec.rules[].http.paths[]`, avec :
       a. `pathType: Prefix` (un `Exact` casserait tout sous-chemin, ex.
          `/api/v1/auth` ne matcherait plus `/api`) ;
       b. `backend.service.name` resout vers un `kind: Service` REELLEMENT
          rendu dont le `selector.facil.component` correspond au composant
          attendu (backend/frontend) -- pas juste un nom de Service qui
          "ressemble" au bon, l'invariant central de ce garde ;
       c. `backend.service.port.number` correspond au port REELLEMENT
          declare par ce Service (un port errone route vers le bon Service
          mais le mauvais port -- 404/connection-refused silencieux).

Ce que ce garde NE PROUVE PAS (documente, pas invente) : que Traefik applique
bien la priorite "plus long prefixe gagne" a l'execution (comportement du
controller, hors du rendu Helm) -- verifie par le smoke k3d, pas ce garde. Ni
que le backend sert reellement ses routes sous `/api/v1/...` (verifie par
lecture du code source, cf. task-H3-report.md), ni le comportement TLS (hors
perimetre, P2).

Usage : helm template ... | python guard_ingress.py
Exit 0 = routage coherent, 1 = Ingress absent, mal cible ou mal porte.
"""
from __future__ import annotations

import sys

import yaml

EXPECTED_CLASS = "traefik"
# (path, pathType attendu, composant facil.component attendu)
EXPECTED_ROUTES = [
    ("/api", "Prefix", "backend"),
    ("/", "Prefix", "frontend"),
]


def _load_docs(stream: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(stream) if isinstance(d, dict)]


def iter_ingresses(docs: list[dict]) -> list[dict]:
    return [d for d in docs if d.get("kind") == "Ingress"]


def service_component_and_ports(docs: list[dict]) -> dict[str, tuple[str | None, set[int]]]:
    """name -> (facil.component du selector, {ports declares}) pour chaque
    `kind: Service` REELLEMENT rendu."""
    out: dict[str, tuple[str | None, set[int]]] = {}
    for doc in docs:
        if doc.get("kind") != "Service":
            continue
        name = (doc.get("metadata") or {}).get("name")
        if not name:
            continue
        spec = doc.get("spec") or {}
        selector = spec.get("selector") or {}
        component = selector.get("facil.component")
        ports = {p.get("port") for p in (spec.get("ports") or []) if p.get("port") is not None}
        out[name] = (component, ports)
    return out


def check(stream: str) -> list[str]:
    docs = _load_docs(stream)
    ingresses = iter_ingresses(docs)
    problems: list[str] = []

    if len(ingresses) == 0:
        problems.append(
            "aucun objet kind: Ingress trouve dans le rendu (ingress.enabled ?) -- "
            "la stack resterait injoignable de partout.")
        return problems
    if len(ingresses) > 1:
        names = [(i.get("metadata") or {}).get("name") for i in ingresses]
        problems.append(f"plusieurs objets Ingress trouves (attendu 1) : {names}")

    services = service_component_and_ports(docs)

    for ing in ingresses:
        name = (ing.get("metadata") or {}).get("name", "?")
        spec = ing.get("spec") or {}

        cls = spec.get("ingressClassName")
        if cls != EXPECTED_CLASS:
            problems.append(
                f"{name}: ingressClassName={cls!r} -- attendu {EXPECTED_CLASS!r} "
                f"(l'ingress controller embarque de k3s) ; un autre nom laisse "
                f"l'Ingress orphelin, aucun controller ne le sert.")

        rendered_paths: dict[str, dict] = {}
        for rule in (spec.get("rules") or []):
            for p in (((rule.get("http") or {}).get("paths")) or []):
                path = p.get("path")
                if path is not None:
                    rendered_paths[path] = p

        for expected_path, expected_type, expected_component in EXPECTED_ROUTES:
            entry = rendered_paths.get(expected_path)
            if entry is None:
                problems.append(
                    f"{name}: aucune route pour le path {expected_path!r} -- "
                    f"attendu -> composant {expected_component!r}.")
                continue

            path_type = entry.get("pathType")
            if path_type != expected_type:
                problems.append(
                    f"{name}: path {expected_path!r} a pathType={path_type!r} -- "
                    f"attendu {expected_type!r} (un {path_type!r} casserait tout "
                    f"sous-chemin, ex. /api/v1/auth ne matcherait plus /api).")

            backend_svc = ((entry.get("backend") or {}).get("service")) or {}
            svc_name = backend_svc.get("name")
            svc_port = ((backend_svc.get("port")) or {}).get("number")

            if svc_name not in services:
                problems.append(
                    f"{name}: path {expected_path!r} pointe vers le Service "
                    f"{svc_name!r} qui n'existe PAS dans le rendu -- route morte.")
                continue

            observed_component, observed_ports = services[svc_name]
            if observed_component != expected_component:
                problems.append(
                    f"{name}: path {expected_path!r} route vers le Service "
                    f"{svc_name!r} dont le composant est {observed_component!r} -- "
                    f"attendu {expected_component!r}. Routage incorrect : les "
                    f"requetes iraient vers le mauvais composant.")

            if svc_port not in observed_ports:
                problems.append(
                    f"{name}: path {expected_path!r} route vers le Service "
                    f"{svc_name!r}:{svc_port} mais ce Service ne declare que les "
                    f"ports {sorted(observed_ports)} -- port errone (connexion "
                    f"refusee ou mauvais backend selon le kube-proxy).")

    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-ingress (SEC-024) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-ingress (SEC-024)")
