# Deployment Checklist — `gov-emergent-country` profile

> Pre-deployment, deployment, and post-deployment checks specific to government emerging-country deployments.
> **Companion** : complete the [Pre-Project Audit Checklist](../../../docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md) BEFORE this document.

## Phase 1 — Pre-deployment audit (MANDATORY)

- [ ] Pre-project audit completed (`docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md` filled in for the target country)
- [ ] ERP version and access confirmed (Sage X3 v12+ ideally)
- [ ] Bank list with ISO 20022 maturity matrix completed
- [ ] AD / LDAP infrastructure documented
- [ ] Legal framework for e-signature documented (national law + decrees)
- [ ] AATL CA selected (DigiCert / GlobalSign / Sectigo / Entrust) AND certs ordered (lead time 1-2 weeks)
- [ ] Co-signing authorities for audit chain identified (typically 3 : Treasury, Audit, Regulator)
- [ ] DR / BCP requirements documented (RTO / RPO targets)
- [ ] Pool of competent staff identified (ERP, security, accounting public)

## Phase 2 — Profile customization

- [ ] `install.yaml` edited per target country :
  - [ ] `profile.reference_deployment` updated
  - [ ] `features.numbering_schemes.default_scheme` matches local convention
  - [ ] `features.public_accounting.default_catalog` set (or new catalog imported)
  - [ ] `features.banking.iso20022.*` and `features.banking.mt940_fallback` per bank list
  - [ ] `providers.auth.primary` chosen (jwt / ldap / keycloak)
  - [ ] `providers.signature.primary` chosen (local_ca / aatl)
  - [ ] `providers.payment.mobile_money_operators` updated for local operators
- [ ] `branding/theme.json` adapted to national colors
- [ ] `branding/logo` set
- [ ] `i18n/` : country-specific terminology added (region names, ministry names)
- [ ] `seed_data/numbering_schemes/` : additional schemes if needed
- [ ] `seed_data/public_accounting_catalogs/` : real accounting codes imported (CSV via Phase Q.4)
- [ ] `seed_data/workflow_templates/` : country-specific workflows added if needed

## Phase 3 — Infrastructure provisioning

- [ ] Database (Supabase / RDS / Cloud SQL / Neon / docker-local) provisioned
- [ ] Redis (Upstash / managed / self-hosted) provisioned
- [ ] Storage (Supabase Storage / S3 / GCS) provisioned
- [ ] Secret manager configured (GCP Secret Manager / AWS Secrets Manager / Vault)
- [ ] Sentry / Grafana Cloud accounts set up (observability)
- [ ] Cloud Run / Kubernetes / VM target ready
- [ ] DNS configured (portal.gov.example, api.gov.example, etc.)
- [ ] TLS certs provisioned (Let's Encrypt / corporate CA)
- [ ] Firewall rules : ERP webhook IPs, bank webhook IPs whitelisted
- [ ] Keycloak instance deployed (if `providers.auth.primary == keycloak`)
- [ ] AC self-signed CA generated OR AATL certs uploaded (if `providers.signature.primary == local_ca` or `aatl`)

## Phase 4 — Wizard execution

```bash
python deploy/init.py --profile=gov-emergent-country --interactive
```

- [ ] Wizard completed without errors
- [ ] `deploy/config.yaml` generated and reviewed
- [ ] `.env.secrets` populated (all secrets referenced exist in secret manager)
- [ ] Schema migrations run successfully
- [ ] Seed data imported successfully

## Phase 5 — First boot validation

- [ ] Backend boot OK (logs clean, no errors)
- [ ] Frontend boot OK
- [ ] Health check endpoints respond (200) :
  - [ ] `GET /healthz` (backend)
  - [ ] `GET /api/v1/auth/healthz` (auth provider reachable)
  - [ ] `GET /api/v1/erp/healthz` (ERP if enabled)
  - [ ] `GET /api/v1/banking/healthz` (banks if enabled)
  - [ ] `GET /api/v1/audit-chain/healthz` (audit chain if enabled)
- [ ] Admin user can log in
- [ ] Studio UI accessible
- [ ] First page load < 3s p95 (citizen portal)

## Phase 6 — Treasury feature smoke tests

If treasury features enabled :

- [ ] Generate test IUI : sequence increments, checksum valid
- [ ] Post test entry in audit chain → verify hash chain integrity
- [ ] Co-signing authorities key ceremony done (3 keys generated, test signature OK)
- [ ] Sigstore Rekor anchor : first weekly anchor successful
- [ ] Sage X3 sandbox sync : 1 test revenue posts successfully (if ERP enabled)
- [ ] ISO 20022 emit : 1 test pain.001 generated, validated against XSD (if banking enabled)
- [ ] AATL signature : 1 test PDF signed, verified by Adobe Reader
- [ ] LDAP : 1 test agent logs in via AD (if LDAP enabled)
- [ ] Keycloak : 1 test agent logs in via Keycloak (if Keycloak enabled)
- [ ] Recours workflow : 1 test citizen submits appeal, agent assigns, supervisor decides
- [ ] PWA offline : 1 test scenario throttle 3G + offline + back online → sync OK

## Phase 7 — Conduite du changement

- [ ] Training sessions scheduled (typically 30-40 % of project budget)
- [ ] In-app training tooltips activated
- [ ] User guides translated (es / fr / en)
- [ ] Helpdesk / support process documented
- [ ] Escalation procedures documented (technical + business)

## Phase 8 — Go-live

- [ ] Soft launch with pilot directorate (1 ministry first)
- [ ] Monitor for 2-4 weeks before national rollout
- [ ] Daily standup with operations team
- [ ] Incident response plan tested
- [ ] Communications plan executed (announcements, press releases if applicable)

## Phase 9 — Post-go-live (first 90 days)

- [ ] Daily monitoring dashboards reviewed
- [ ] Audit chain anchor checked weekly (Sigstore Rekor verifications)
- [ ] ERP sync match rate > 95 % maintained
- [ ] Bank reconciliation match rate > 95 % maintained
- [ ] Recours workflow SLA tracked (decision in < 60 days standard)
- [ ] User feedback collected systematically
- [ ] Performance optimization based on real load
- [ ] Security audit semi-annual scheduled (penetration test)

## Phase 10 — Continuous improvement

- [ ] Quarterly review of profile updates from upstream Facil Framework releases
- [ ] Quarterly review of accounting catalog updates (PCE-GE versioning)
- [ ] Annual cert renewal (AATL, internal CA, Keycloak certs)
- [ ] Annual DR test
- [ ] Annual policy review (e-signature, RBAC mappings)
