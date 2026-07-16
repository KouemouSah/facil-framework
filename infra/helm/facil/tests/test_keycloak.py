"""Phase 2 — template Helm keycloak (auth fédérée, gated OFF par défaut).

Parité avec le profil `auth` du compose : Keycloak `start-dev` (H2 in-memory,
NON-PROD) est l'IdP OIDC. Durci comme le reste du chart, mot de passe admin par
Secret. L'apply k3d prouve le démarrage.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).parent
CHART_DIR = TESTS_DIR.parent
REPO_ROOT = CHART_DIR.parent.parent.parent
sys.path.insert(0, str(TESTS_DIR))

import guard_resources  # noqa: E402


def _render(*extra: str) -> str:
    cmd = ["helm", "template", "rel", str(CHART_DIR), *extra]
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                          check=True).stdout


def _docs(out: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def _keycloak_netpol(docs: list[dict]) -> dict | None:
    for d in docs:
        if d.get("kind") != "NetworkPolicy":
            continue
        sel = (d["spec"].get("podSelector") or {}).get("matchLabels") or {}
        if sel.get("facil.component") == "keycloak":
            return d
    return None


def test_keycloak_off_by_default():
    assert "facil-keycloak" not in _render()


def test_keycloak_enabled_renders_deployment_and_service():
    docs = _docs(_render("--set", "keycloak.enabled=true"))
    pairs = {(d["kind"], d["metadata"]["name"]) for d in docs
             if d.get("kind") in ("Deployment", "Service")}
    assert ("Deployment", "facil-keycloak") in pairs
    assert ("Service", "facil-keycloak") in pairs


def test_keycloak_passes_resources_hardening_guard():
    assert guard_resources.check(_render("--set", "keycloak.enabled=true")) == []


def test_keycloak_service_exposes_8080():
    docs = _docs(_render("--set", "keycloak.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-keycloak")
    assert 8080 in {p["port"] for p in svc["spec"]["ports"]}


def test_keycloak_admin_password_comes_from_secret_never_inline():
    docs = _docs(_render("--set", "keycloak.enabled=true"))
    dep = next(d for d in docs if d.get("kind") == "Deployment"
               and d["metadata"]["name"] == "facil-keycloak")
    c = dep["spec"]["template"]["spec"]["containers"][0]
    pw = next(e for e in c["env"] if e["name"] == "KC_BOOTSTRAP_ADMIN_PASSWORD")
    assert "valueFrom" in pw and "value" not in pw


def test_keycloak_seeds_install_dir_to_keep_readonly_rootfs():
    # start-dev augmente Quarkus dans son install -> incompatible readOnly:true.
    # Solution : initContainer seede /opt/keycloak dans un emptyDir writable, le
    # container principal garde readOnly:true. Image stock, aucune exemption de garde.
    docs = _docs(_render("--set", "keycloak.enabled=true"))
    dep = next(d for d in docs if d.get("kind") == "Deployment"
               and d["metadata"]["name"] == "facil-keycloak")
    spec = dep["spec"]["template"]["spec"]
    init = spec["initContainers"][0]
    assert "cp -r /opt/keycloak" in " ".join(init["command"])   # seed prouve par apply (Ready readOnly:true)
    c = spec["containers"][0]
    assert c["securityContext"]["readOnlyRootFilesystem"] is True
    assert "/opt/keycloak" in {m["mountPath"] for m in c["volumeMounts"]}


def test_keycloak_networkpolicy_allows_backend_oidc_and_ui():
    np = _keycloak_netpol(_docs(_render("--set", "keycloak.enabled=true")))
    assert np is not None, "no NetworkPolicy targets keycloak"
    pod_srcs, ns_srcs = set(), set()
    for rule in np["spec"]["ingress"]:
        for frm in rule.get("from", []):
            pm = (frm.get("podSelector") or {}).get("matchLabels") or {}
            nm = (frm.get("namespaceSelector") or {}).get("matchLabels") or {}
            if "facil.component" in pm:
                pod_srcs.add(pm["facil.component"])
            if "kubernetes.io/metadata.name" in nm:
                ns_srcs.add(nm["kubernetes.io/metadata.name"])
    assert "backend" in pod_srcs            # token exchange / JWKS
    assert "kube-system" in ns_srcs          # login UI via Traefik/Ingress
