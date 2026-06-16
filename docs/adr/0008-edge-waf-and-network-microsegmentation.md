# ADR-0008 — Edge WAF + network microsegmentation (scale/zero-trust)

Status: Accepted (baseline) — 2026-06-16
Deciders: platform/security

## Context

At 1M+ agents the platform needs defense-in-depth beyond the application layer.
Two controls were requested: a **WAF** and **network microsegmentation**. Both are
**infrastructure** concerns — not backend code — and must be placed at the correct
layer; implementing them inside the FastAPI app would be wrong (and ineffective).

The app already provides: input validation (Pydantic), parameterized SQL
(SQLAlchemy — no SQLi), scope-aware RBAC, app-level rate-limiting + payload caps
(D4.8), shared-state rate-limit/revocation at scale (D4.12). The edge and network
layers complement these.

## Decision

1. **WAF at the edge (not in the app).** The `edge` (Caddy) origin runs an
   OWASP-CRS WAF via the Coraza (ModSecurity-compatible) module, plus security
   headers and an edge rate-limit; or, in cloud, a managed WAF (Cloudflare / AWS /
   Azure) in front of the edge. Baseline + config: `deploy/edge/README.md`. CRS
   starts at paranoia level 1 and is raised progressively.

2. **Network microsegmentation via Kubernetes NetworkPolicies (default-deny) +
   mTLS.** On k3s/k8s (ADR-0006), a default-deny policy plus least-privilege
   allow-rules: public ingress only to the edge; edge→backend only; backend→its
   data-plane deps only; data-plane services accept ingress only from the backend
   (no lateral movement). Baseline manifests: `deploy/k8s/networkpolicies.yaml`.
   Service-to-service **mTLS** (Linkerd/Istio, or Caddy internal TLS) adds identity
   + in-transit encryption.

## Consequences

- Blast radius is contained: a compromised pod cannot reach services it doesn't
  need, and common web attacks are filtered before reaching the app.
- These are **deployment-layer** artifacts (P-phases): the manifests/config ship in
  the repo as a baseline; wiring them into the edge image and the Helm chart is the
  P3/P8/P12 hardening work, parameterised per environment.
- No application code change. The app remains portable (cloud WAF or self-hosted
  Coraza; any CNI that supports NetworkPolicy).

## Not in scope here

- IGA / access certification (SailPoint-class) — separate product layer.
- SCIM provisioning is implemented in the app (D4.13), not here.
