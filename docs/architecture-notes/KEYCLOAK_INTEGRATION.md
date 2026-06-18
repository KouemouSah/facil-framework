# Keycloak / OIDC federated auth (Phase K)

How the framework wires **Keycloak** as a federated OIDC identity provider for the
agent surface — and how to enable it. The generic OIDC federation is provider-agnostic
(`app/auth/federation.py` + `KeycloakOIDCProvider`); this note covers the *concrete*
Keycloak binding (realm/client provisioning + env wiring).

## Status

- **Native auth** (email/password, `app/auth`) is the default and always on.
- **Keycloak OIDC** is **opt-in** (`auth.keycloak.enabled: false` by default) and
  profile-gated (`docker compose --profile auth`). Default deploys are unaffected.
- Dev uses Keycloak `start-dev` (in-memory H2 — **non-prod**). Production needs a
  real DB-backed Keycloak + TLS + `KC_HOSTNAME` (Phase J / P11).

## Enabling it (local/dev)

1. `deploy/config.yaml` → `auth.keycloak.enabled: true` (a surface must use
   `keycloak_oidc`; the agent surface does by default).
2. `python deploy/providers/docker_local.py --apply`. The apply then:
   - generates `KEYCLOAK_ADMIN_PASSWORD` (`ensure_secrets`, strong — never the weak
     `:-admin` compose fallback),
   - brings up the `auth`-profile Keycloak,
   - runs the **keycloak bootstrap provisioner**: waits for the API (host-side
     readiness retry — Keycloak has no compose healthcheck and `start-dev` takes
     20-40 s), then provisions the realm + confidential client + `facil-contract`
     scope (groups/org mappers) + group taxonomy, capturing the OIDC facts to
     `deploy/.bootstrap-state.json`,
   - renders the backend env (`AUTH_METHODS`, `AUTH_OIDC_*`) and the frontend env
     (`OIDC_*`, `NEXT_PUBLIC_OIDC_ENABLED=1`),
   - rebuilds the frontend with `NEXT_PUBLIC_OIDC_ENABLED=1` (build-arg — the login
     page is a client component, so the flag is inlined at build, not runtime).
3. The login page shows **"Sign in with your organization (SSO)"**.

Create users/groups in the Keycloak admin console (`http://localhost:8088`, admin /
`KEYCLOAK_ADMIN_PASSWORD`); map a group to an RBAC role via `auth.oidc.role_map`.

## Split-horizon OIDC (important)

The token `iss` must equal what the **browser** reaches, while the **backend** fetches
JWKS over the Docker network. The framework keeps these as two keys:

| Key | Value (dev) | Used by |
|---|---|---|
| `AUTH_OIDC_ISSUER` / `OIDC_ISSUER` | `http://localhost:8088/realms/facil` | browser redirect + `iss` check |
| `AUTH_OIDC_JWKS_URI` | `http://keycloak:8080/realms/facil/protocol/openid-connect/certs` | backend (in-network) |

## Security posture

- **No wildcard redirect.** The client is created/enforced with the exact BFF callback
  (`/api/auth/oidc/callback`); `redirectUris: ["*"]` is an open-redirect (CWE-601) and is
  never used. `webOrigins: ["+"]` derives CORS from the registered redirect URIs.
- **Confidential client.** `publicClient=false`; the `client_secret` is delivered ONLY to
  the frontend BFF (`OIDC_CLIENT_SECRET`, server-side) for the code→token exchange. It is
  **not** placed in the backend env (the verifier validates JWTs via JWKS; the secret is
  only needed for optional RFC 7662 introspection).
- **Secrets** live in `deploy/.bootstrap-state.json` + the gitignored `.env.deploy.gen`
  files (same trust level as `.env.secrets`). The admin password is auto-generated.
- **Session revocation.** Back-channel logout is wired (Redis revocation set) so an
  IdP-side logout disconnects the federated session.

## Production (Phase J / P11 — not done here)

- DB-backed Keycloak (not `start-dev`/H2), `start` mode, TLS, `KC_HOSTNAME` set so `iss`
  is the public URL; JWKS over HTTPS.
- LDAP/AD or upstream IdP federation, MFA policies, realm export/import in CI.
- First admin from an IdP group mapped to the `admin` role (the federated bootstrap
  model — complements the native break-glass installer).
