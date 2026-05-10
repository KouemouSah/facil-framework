# Keycloak Setup — `gov-emergent-country` profile (optional)

> **Status** : optional federation, recommended for deployments with 100+ agents, multi-AD, or institutional SSO requirements.
> **Implementation phase** : Phase J + Phase J extension (LDAP/AD direct) + Phase J Keycloak provider extension (planned, ~2-3 days).
> **See also** : [KEYCLOAK_DECISION.md](../../../docs/architecture-notes/KEYCLOAK_DECISION.md) — when (and when NOT) to use Keycloak with Facil.

## When to use Keycloak

✅ **Recommended if** :
- 100+ agents across multiple administrative directions
- Existing Active Directory / LDAP federation in place
- IT department wants centralized IAM administration
- Compliance requires separate audit trail for identity events
- You already have Keycloak deployed in production (reuse existing instance)
- SAML 2.0 federation with external IdPs needed
- Multiple realms required (1 realm per ministry, for instance)

❌ **NOT recommended if** :
- Solo deployment / small team (< 20 agents)
- Dev / staging environments (use lightweight JWT default)
- No dedicated DevOps / IT staff to operate Keycloak (ops burden)
- Latency-sensitive workflows (every token introspection adds 10-50ms)
- Tight RAM/CPU budget (Keycloak needs ~512 MB RAM minimum)

## Architecture overview

```
[Citizen / Agent]
       │
       │ (login)
       ▼
[Facil Web / Mobile]
       │
       │ (OIDC redirect)
       ▼
[Keycloak — separate process]
       │
       │ (federate)
       ▼
[Active Directory / LDAP / SAML IdP]
       │
       ▼ (assertion)
[Keycloak issues token]
       │
       ▼
[Facil receives token, validates]
       │
       ▼
[Group/role mapping → Facil RBAC]
```

## Setup steps (post-Phase J extensions live)

### 1. Deploy Keycloak (separate process)

```bash
# Option A: Docker (quick start, dev / small prod)
docker run -d --name keycloak \
  -p 8443:8443 \
  -e KEYCLOAK_ADMIN=admin \
  -e KEYCLOAK_ADMIN_PASSWORD=<strong_password> \
  quay.io/keycloak/keycloak:latest \
  start --hostname=keycloak.gov.example --https-port=8443

# Option B: Kubernetes (production)
# See https://www.keycloak.org/operator/installation

# Option C: Bare-metal (legacy gov data centers)
# Download from https://www.keycloak.org/downloads
```

### 2. Create a realm (per ministry / direction if multi-tenant)

In Keycloak admin console :
1. Create realm `ministry-of-finance` (one per administrative entity)
2. Configure realm settings : token lifespans (access 30 min, refresh 30 days), MFA policies, password policies
3. Configure i18n (es / fr / en — match Facil profile)

### 3. Federate with Active Directory

In Keycloak admin console → User Federation :
1. Add provider : `LDAP`
2. Configure :
   - Connection URL : `ldaps://ad.mfpde.gov:636` (LDAPS strict TLS)
   - Bind DN : service account (read-only)
   - Bind credential : reference Vault / secret manager
   - Users DN : `OU=Users,DC=mfpde,DC=gov`
   - User object classes : `person, organizationalPerson, user`
   - Username LDAP attribute : `sAMAccountName` or `userPrincipalName`
3. Configure mappers :
   - Map `memberOf` → realm groups
   - Map `employeeID` → user attribute `matricule`
   - Map `department` → user attribute `direction`
   - Map `title` → user attribute `fonction`
4. Test sync (read-only — Facil never writes to AD)

Repeat for additional ADs (one User Federation per AD).

### 4. Configure Keycloak as Facil OIDC provider

Create a Facil client in Keycloak realm :
1. Client ID : `facil-portal`
2. Client protocol : `openid-connect`
3. Access type : `confidential`
4. Valid redirect URIs : `https://portal.gov.example/auth/callback/keycloak`
5. Web origins : `https://portal.gov.example`
6. Generate client secret

### 5. Configure Facil to use Keycloak

In `profiles/gov-emergent-country/install.yaml` :

```yaml
providers:
  auth:
    primary: keycloak
    keycloak:
      enabled: true
      base_url: https://keycloak.gov.example
      realm: ministry-of-finance
      client_id: facil-portal
      client_secret_ref: keycloak_client_secret
      group_role_mapping: true
```

In Facil Studio UI :
1. Navigate to Studio → Authentication → Providers
2. Enable Keycloak provider
3. Configure group role mapping :
   - `treasury-agents` (Keycloak group) → `treasury_agent` (Facil role)
   - `treasury-supervisors` → `treasury_supervisor`
   - `treasury-analysts` → `treasury_analyst`
   - etc.

### 6. Test end-to-end

1. Citizen / agent visits Facil portal
2. Click « Sign in with institutional SSO »
3. Redirected to Keycloak login page
4. Enter AD credentials + MFA (configured in Keycloak)
5. Redirected back to Facil with token
6. Facil receives token, extracts groups, maps to Facil roles
7. Audit log captures both Keycloak event and Facil session start

## Operations

### Monitoring

- Keycloak metrics : Prometheus endpoint `/metrics` → Grafana dashboard
- Keycloak audit logs : separate from Facil audit logs → consolidate via SIEM
- Health check : `GET /health/ready` (Keycloak)

### Backup

- Keycloak DB backup separate from Facil DB
- Recommended : daily logical dump + weekly snapshot
- Document realm configuration (export realm JSON for disaster recovery)

### Upgrades

- Keycloak follows quarterly release cycle
- LTS releases every 12 months (recommended for production)
- Upgrade path : test in staging first, blue/green deploy

### Cost

- Software : free (Apache 2.0)
- Infra : ~512 MB RAM minimum, ~1 GB recommended for production with 100+ users
- Ops : ~0.25 FTE for ongoing maintenance (depending on scale)
- Optional : Red Hat Build of Keycloak (commercial support, ~5-10 k€/year)

## Troubleshooting

| Issue | Diagnosis | Resolution |
|---|---|---|
| Login redirects loop | Mismatched redirect URI | Verify exact match in Keycloak client config + Facil callback URL |
| Token introspection latency > 200ms | Keycloak overloaded | Scale Keycloak (more replicas) or enable token caching in Facil |
| AD users can't log in | LDAPS cert invalid | Validate cert chain, ensure CA root trusted by Keycloak |
| Group mapping not applied | Mapper misconfigured | Re-check User Federation → Mappers → `memberOf` → realm role mapper |
| MFA not enforced | Realm policy weak | Set realm authentication flow → require OTP for treasury roles |

## See also

- [Keycloak official docs](https://www.keycloak.org/documentation)
- [Keycloak admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/)
- [PHASE_J_TREASURY_EXTENSIONS.md](../../../.claude/plans/phases/PHASE_J_TREASURY_EXTENSIONS.md) — LDAP/AD direct alternative if Keycloak not desired
- [PHASE_J_AUTH_PROVIDERS.md](../../../.claude/plans/phases/PHASE_J_AUTH_PROVIDERS.md) — Phase J baseline (JWT default + SAML / OAuth)
