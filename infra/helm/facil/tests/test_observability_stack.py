"""Phase 2 — observabilité souveraine en COMPOSANTS SÉPARÉS et durcis.

L'all-in-one grafana/otel-lgtm a été écarté (prouvé incompatible avec
readOnlyRootFilesystem par apply k3d). Chaque composant (Prometheus, Loki, Tempo,
Grafana, otel-collector) est un template durci (readOnly:true) toggleable
indépendamment. Ce fichier prouve le rendu + le durcissement par `guard_resources`
sur le rendu réel ; l'apply k3d prouve que chaque pod démarre.
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


def _kinds(docs: list[dict]) -> set[tuple[str, str]]:
    return {(d["kind"], d["metadata"]["name"]) for d in docs if d.get("kind")}


# --- Prometheus -------------------------------------------------------------

def test_prometheus_off_by_default():
    assert "facil-prometheus" not in _render()


def test_prometheus_enabled_renders_deployment_service_configmap():
    kinds = _kinds(_docs(_render("--set", "observability.prometheus.enabled=true")))
    assert ("Deployment", "facil-prometheus") in kinds
    assert ("Service", "facil-prometheus") in kinds
    assert ("ConfigMap", "facil-prometheus") in kinds


def test_prometheus_passes_resources_hardening_guard():
    # readOnlyRootFilesystem:true INCLUS — Prometheus ecrit son TSDB dans
    # l'emptyDir /prometheus, jamais le rootfs (contrairement a l'all-in-one).
    problems = guard_resources.check(
        _render("--set", "observability.prometheus.enabled=true"))
    assert problems == [], problems


def test_prometheus_service_exposes_9090():
    docs = _docs(_render("--set", "observability.prometheus.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-prometheus")
    assert 9090 in {p["port"] for p in svc["spec"]["ports"]}


def _component_netpol(docs: list[dict], component: str) -> dict | None:
    for d in docs:
        if d.get("kind") != "NetworkPolicy":
            continue
        sel = (d["spec"].get("podSelector") or {}).get("matchLabels") or {}
        if sel.get("facil.component") == component:
            return d
    return None


def _np_sources(np: dict) -> set[str]:
    out: set[str] = set()
    for rule in np["spec"].get("ingress", []):
        for frm in rule.get("from", []):
            ml = (frm.get("podSelector") or {}).get("matchLabels") or {}
            if "facil.component" in ml:
                out.add(ml["facil.component"])
    return out


def test_prometheus_networkpolicy_allows_grafana_on_9090():
    # Default-deny ingress : Prometheus doit explicitement accepter Grafana (PromQL)
    # sur 9090, sinon les dashboards ne peuvent pas l'interroger.
    np = _component_netpol(_docs(_render("--set", "observability.prometheus.enabled=true")),
                           "prometheus")
    assert np is not None, "no NetworkPolicy targets prometheus"
    ports = {p["port"] for r in np["spec"]["ingress"] for p in r.get("ports", [])}
    assert 9090 in ports
    assert "grafana" in _np_sources(np)


def test_backend_accepts_prometheus_scrape_when_enabled():
    # Prometheus scrape le backend sur /metrics -> le backend (dont l'ingress est
    # restreint a frontend + kube-system) doit aussi accepter prometheus, sinon la
    # cible est DOWN en silence.
    np = _component_netpol(_docs(_render("--set", "observability.prometheus.enabled=true")),
                           "backend")
    assert np is not None
    assert "prometheus" in _np_sources(np)


def test_backend_does_not_accept_prometheus_when_disabled():
    np = _component_netpol(_docs(_render()), "backend")  # prometheus OFF
    assert np is not None
    assert "prometheus" not in _np_sources(np)


# --- otel-collector (ingest OTLP -> exporte pour Prometheus) -----------------

def test_collector_off_by_default():
    assert "facil-otel-collector" not in _render()


def test_collector_enabled_renders_deployment_service_configmap():
    kinds = _kinds(_docs(_render("--set", "observability.otelCollector.enabled=true")))
    assert ("Deployment", "facil-otel-collector") in kinds
    assert ("Service", "facil-otel-collector") in kinds
    assert ("ConfigMap", "facil-otel-collector") in kinds


def test_collector_passes_resources_hardening_guard():
    problems = guard_resources.check(
        _render("--set", "observability.otelCollector.enabled=true"))
    assert problems == [], problems


def test_collector_service_exposes_otlp_and_prometheus_exporter():
    docs = _docs(_render("--set", "observability.otelCollector.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-otel-collector")
    ports = {p["port"] for p in svc["spec"]["ports"]}
    assert {4317, 4318, 8889} <= ports  # OTLP gRPC/HTTP + Prometheus exporter


def test_collector_networkpolicy_allows_backend_otlp_and_prometheus_scrape():
    np = _component_netpol(
        _docs(_render("--set", "observability.otelCollector.enabled=true")),
        "otel-collector")
    assert np is not None, "no NetworkPolicy targets otel-collector"
    ports = {p["port"] for r in np["spec"]["ingress"] for p in r.get("ports", [])}
    assert {4317, 4318, 8889} <= ports
    assert "backend" in _np_sources(np)      # OTLP ingest
    assert "prometheus" in _np_sources(np)   # scrape du /metrics exporte


def test_prometheus_scrapes_collector_when_both_enabled():
    # Le chemin metriques : Prometheus doit avoir un job qui scrape l'exporter
    # du collector (8889), sinon la telemetrie OTLP du backend n'atterrit nulle part.
    docs = _docs(_render("--set", "observability.prometheus.enabled=true",
                         "--set", "observability.otelCollector.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and d["metadata"]["name"] == "facil-prometheus")
    assert "facil-otel-collector" in cm["data"]["prometheus.yml"]


# --- Grafana (dashboards + datasources) -------------------------------------

def test_grafana_off_by_default():
    assert "facil-grafana" not in _render()


def test_grafana_enabled_renders_deployment_and_service():
    kinds = _kinds(_docs(_render("--set", "observability.grafana.enabled=true")))
    assert ("Deployment", "facil-grafana") in kinds
    assert ("Service", "facil-grafana") in kinds


def test_grafana_passes_resources_hardening_guard():
    problems = guard_resources.check(
        _render("--set", "observability.grafana.enabled=true"))
    assert problems == [], problems


def test_grafana_service_exposes_3000():
    docs = _docs(_render("--set", "observability.grafana.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-grafana")
    assert 3000 in {p["port"] for p in svc["spec"]["ports"]}


def test_grafana_admin_password_comes_from_secret_never_inline():
    # Discipline secrets (SEC-001) : le mot de passe admin arrive par secretKeyRef,
    # jamais en clair dans l'env du Deployment.
    docs = _docs(_render("--set", "observability.grafana.enabled=true"))
    dep = next(d for d in docs if d.get("kind") == "Deployment"
               and d["metadata"]["name"] == "facil-grafana")
    c = dep["spec"]["template"]["spec"]["containers"][0]
    pw = next(e for e in c["env"] if e["name"] == "GF_SECURITY_ADMIN_PASSWORD")
    assert "valueFrom" in pw and "value" not in pw


def test_grafana_provisions_prometheus_datasource_when_both_enabled():
    docs = _docs(_render("--set", "observability.grafana.enabled=true",
                         "--set", "observability.prometheus.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and "grafana" in d["metadata"]["name"]
              and "datasource" in d["metadata"]["name"])
    assert "facil-prometheus:9090" in str(cm["data"])


def test_grafana_disables_bundled_plugin_preinstall():
    # Sur rootfs read-only, Grafana echoue (log ERROR) a reinstaller ses plugins
    # bundled (elasticsearch/zipkin, inutilises) dans /usr/share/grafana/data. On
    # desactive le preinstall -> plus de bruit, aucun impact (Prometheus = datasource
    # cœur, pas un plugin). Prouve par apply : logs propres apres ce reglage.
    docs = _docs(_render("--set", "observability.grafana.enabled=true"))
    dep = next(d for d in docs if d.get("kind") == "Deployment"
               and d["metadata"]["name"] == "facil-grafana")
    c = dep["spec"]["template"]["spec"]["containers"][0]
    val = next((e["value"] for e in c["env"]
                if e["name"] == "GF_PLUGINS_PREINSTALL_DISABLED"), None)
    assert val == "true"


def test_grafana_networkpolicy_allows_ui_from_kube_system():
    np = _component_netpol(_docs(_render("--set", "observability.grafana.enabled=true")),
                           "grafana")
    assert np is not None, "no NetworkPolicy targets grafana"
    ports = {p["port"] for r in np["spec"]["ingress"] for p in r.get("ports", [])}
    assert 3000 in ports


# --- Loki (logs) ------------------------------------------------------------

def test_loki_off_by_default():
    assert "facil-loki" not in _render()


def test_loki_enabled_renders_deployment_service_configmap():
    kinds = _kinds(_docs(_render("--set", "observability.loki.enabled=true")))
    assert ("Deployment", "facil-loki") in kinds
    assert ("Service", "facil-loki") in kinds
    assert ("ConfigMap", "facil-loki") in kinds


def test_loki_passes_resources_hardening_guard():
    assert guard_resources.check(_render("--set", "observability.loki.enabled=true")) == []


def test_loki_service_exposes_3100():
    docs = _docs(_render("--set", "observability.loki.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-loki")
    assert 3100 in {p["port"] for p in svc["spec"]["ports"]}


def test_loki_networkpolicy_allows_collector_ingest_and_grafana_query():
    np = _component_netpol(_docs(_render("--set", "observability.loki.enabled=true")), "loki")
    assert np is not None
    srcs = _np_sources(np)
    assert "otel-collector" in srcs and "grafana" in srcs


def test_grafana_provisions_loki_datasource_when_both_enabled():
    docs = _docs(_render("--set", "observability.grafana.enabled=true",
                         "--set", "observability.loki.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and d["metadata"]["name"] == "facil-grafana-datasources")
    assert "facil-loki:3100" in str(cm["data"])


def test_collector_routes_logs_to_loki_when_both_enabled():
    docs = _docs(_render("--set", "observability.otelCollector.enabled=true",
                         "--set", "observability.loki.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and d["metadata"]["name"] == "facil-otel-collector")
    assert "facil-loki" in cm["data"]["config.yaml"]


# --- Tempo (traces) ---------------------------------------------------------

def test_tempo_off_by_default():
    assert "facil-tempo" not in _render()


def test_tempo_enabled_renders_deployment_service_configmap():
    kinds = _kinds(_docs(_render("--set", "observability.tempo.enabled=true")))
    assert ("Deployment", "facil-tempo") in kinds
    assert ("Service", "facil-tempo") in kinds
    assert ("ConfigMap", "facil-tempo") in kinds


def test_tempo_passes_resources_hardening_guard():
    assert guard_resources.check(_render("--set", "observability.tempo.enabled=true")) == []


def test_tempo_service_exposes_query_and_otlp_ingest():
    docs = _docs(_render("--set", "observability.tempo.enabled=true"))
    svc = next(d for d in docs if d.get("kind") == "Service"
               and d["metadata"]["name"] == "facil-tempo")
    ports = {p["port"] for p in svc["spec"]["ports"]}
    assert {3200, 4317} <= ports  # query API + OTLP gRPC ingest


def test_tempo_networkpolicy_allows_collector_otlp_and_grafana_query():
    np = _component_netpol(_docs(_render("--set", "observability.tempo.enabled=true")), "tempo")
    assert np is not None
    srcs = _np_sources(np)
    assert "otel-collector" in srcs and "grafana" in srcs


def test_grafana_provisions_tempo_datasource_when_both_enabled():
    docs = _docs(_render("--set", "observability.grafana.enabled=true",
                         "--set", "observability.tempo.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and d["metadata"]["name"] == "facil-grafana-datasources")
    assert "facil-tempo:3200" in str(cm["data"])


def test_collector_routes_traces_to_tempo_when_both_enabled():
    docs = _docs(_render("--set", "observability.otelCollector.enabled=true",
                         "--set", "observability.tempo.enabled=true"))
    cm = next(d for d in docs if d.get("kind") == "ConfigMap"
              and d["metadata"]["name"] == "facil-otel-collector")
    assert "facil-tempo" in cm["data"]["config.yaml"]
