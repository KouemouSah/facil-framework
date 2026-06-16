# Edge security baseline — WAF + headers + rate-limit (INFRA, not app code)

The edge (Caddy, `edge` Compose profile / k8s) is the single public origin. This is
the **defense-in-depth layer in FRONT of the backend** — the app already does input
validation (Pydantic), parameterized SQL (no SQLi), authz (RBAC) and app-level
rate-limiting (D4.8); the edge adds an OWASP-rule WAF, security headers and a
network-level rate limit. **No Python here** — it's edge config.

## WAF — OWASP CRS via Coraza (ModSecurity-compatible)

Use the [Caddy + Coraza](https://github.com/corazawaf/coraza-caddy) module (a
ModSecurity-compatible engine) loaded with the **OWASP Core Rule Set**. Build a
Caddy image with the module, then in the Caddyfile:

```caddyfile
{
    order coraza_waf first
}

:8443 {
    coraza_waf {
        directives `
            Include @coraza.conf-recommended
            Include @crs-setup.conf.example
            Include @owasp_crs/*.conf
            SecRuleEngine On
            SecDefaultAction "phase:1,log,auditlog,deny,status:403"
        `
    }

    # Security headers (defense-in-depth)
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
        Content-Security-Policy "default-src 'self'"
        -Server
    }

    # Edge rate-limit (caddy-ratelimit module) — complements the app limiter
    rate_limit {
        zone api { key {remote_host}; events 600; window 1m }
    }

    reverse_proxy backend:8080
}
```

- Start CRS at **paranoia level 1**, watch the audit log, then raise progressively
  (PL2/PL3) to cut false positives — never enable PL3 blind in front of users.
- Tune `SecRuleRemoveById` for endpoints CRS over-flags (e.g. rich JSON bodies).

## Managed alternative

In cloud, a **managed WAF** (Cloudflare, AWS WAF, Azure Front Door) in front of the
edge is equivalent and lower-ops — point it at the edge origin and enable the OWASP
managed ruleset + rate-limiting + bot management.

## Status

Baseline / guidance for the **edge** profile (P-phases). The `edge` Compose service
exists (anti-CORS single-origin); wiring Coraza + CRS into the edge image and the
k8s ingress is the P3/P8/P12 hardening work. See `docs/adr/0008`.
