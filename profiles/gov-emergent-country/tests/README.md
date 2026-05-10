# Tests — `gov-emergent-country` profile

> **Status** : skeleton. E2E tests to be implemented by **Phase L** (E2E tests per profile).

## Test scenarios planned

### Core scenarios (Phase L)
1. **Profile boot** : `python deploy/init.py --profile=gov-emergent-country --non-interactive` succeeds without error
2. **Admin login** : default admin user can log in via JWT
3. **i18n switch** : user can switch es / fr / en
4. **Branding** : custom theme.json applied correctly

### Treasury V1.1 scenarios (Phases O / P / Q / R / S / T)

#### Phase O — ERP Connector
5. **Sage X3 sandbox sync** : 1 test revenue posts in Sage X3 sandbox in < 5 min, idempotency replay-safe

#### Phase P — Audit Chain
6. **Hash chain integrity** : insert 100 events, modify 1 event in DB, integrity check detects tampering
7. **Co-signature quorum** : 2/3 authorities sign anchor, 3rd unavailable → degraded mode OK
8. **Sigstore Rekor anchor** : weekly anchor pushed, verifiable from public Rekor UI

#### Phase Q — Numbering & Public Accounting
9. **IUI generation** : 10k IDs generated, 0 collision, 100 % checksum valid
10. **PCE-GE catalog import** : CSV bulk import 1000 codes < 1 min

#### Phase R — ISO 20022 Banking
11. **pain.001 emit** : XML valid against XSD, signed XAdES, sent to mock bank
12. **camt.053 ingest** : parse fixture, reconcile with IUI in label, match rate > 95 %
13. **MT940 fallback** : parse MT940 fixture for non-ISO 20022 bank

#### Phase S — External Adapters
14. **Circuit breaker** : 5 consecutive failures → open, recover after 30s
15. **DLQ replay** : message in DLQ replayable from Studio UI

#### Phase T — PWA Offline + Recours + Training
16. **PWA offline** : Cypress throttle 3G + offline → write to queue → back online → sync OK, no data loss
17. **Recours workflow** : citizen submits → agent assigns → supervisor decides → notification sent
18. **Training tooltips** : Joyride covers 80 % of primary user paths

### Auth extensions (Phase J + extensions)
19. **LDAP login** : test agent logs in via ApacheDS test LDAP
20. **Multi-AD routing** : 2 ADs configured, login routed by domain email
21. **Group RBAC mapping** : user in AD group X gets Facil role Y at login
22. **Keycloak login** (if enabled) : redirect to Keycloak, login, return with token, role mapped

### Signature extensions (Phase N.5 + extensions)
23. **AATL PAdES sign** : PDF signed with DigiCert AATL cert, verified by Adobe Reader (badge « Signed and certified »)
24. **XAdES sign pain.001** : XML signed, verified by xmlsec1 CLI
25. **OCSP real-time** : verify queries OCSP < 500 ms p95, fallback CRL if timeout

## Test infrastructure required

- **Postgres** test DB (docker-compose)
- **Redis** test instance
- **Mock Sage X3** (WireMock or custom FastAPI mock)
- **Mock LDAP** (ApacheDS Docker container)
- **Mock Keycloak** (Keycloak Docker, ephemeral realm per test)
- **Mock OCSP responder**
- **Mock TSA** (FreeTSA or local fake)
- **Cypress** for PWA / E2E web tests
- **Playwright** alternative for cross-browser

## How to run

```bash
# All tests for this profile
pytest tests/profiles/gov-emergent-country/ -v

# Specific phase tests
pytest tests/profiles/gov-emergent-country/test_treasury_phase_o.py -v
pytest tests/profiles/gov-emergent-country/test_treasury_phase_p.py -v

# E2E (Cypress)
cd packages/web && npm run e2e -- --profile=gov-emergent-country
```

## CI integration

Phase L will set up CI matrix to run all profile tests on every commit. Treasury features tests are gated by feature flags in `install.yaml` (don't run if feature disabled).

## Acceptance criteria for V1.1 release

- [ ] All 25 scenarios passing
- [ ] 0 flaky tests over 10 consecutive runs
- [ ] Test coverage > 80 % on treasury modules (O / P / Q / R / S / T)
- [ ] Pen-test report clean (security audit during Phase L)
