# Security Policy

## Supported versions

Facil Framework is in **pre-bootstrap status**. No production version is supported yet.

| Version | Supported |
|---------|-----------|
| 0.x (pre-V1) | ❌ Not for production use |
| 1.0 (planned) | ✅ Will be supported when released |

## Reporting a vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report privately via one of:

1. **Preferred** — GitHub Security Advisories: https://github.com/KouemouSah/facil-framework/security/advisories/new
2. Email: **libressai@gmail.com** (subject: `[SECURITY] facil-framework`)

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected version / commit hash
- Potential impact (data exposure, code execution, privilege escalation, etc.)
- Suggested fix if known
- Your contact info for follow-up

### Response timeline

| Action | Target |
|--------|--------|
| Acknowledge receipt | Within 48 hours |
| Initial assessment | Within 7 days |
| Fix or mitigation plan | Within 30 days for critical, 90 days for medium/low |
| Public disclosure | After fix is released, coordinated with reporter |

We follow **coordinated disclosure**. Please give us reasonable time to fix before public disclosure.

## Scope

In-scope for security reports:

- Authentication and authorization flaws
- Cryptographic weaknesses (signature verification, key storage)
- Injection vulnerabilities (SQL, command, prompt)
- Server-side request forgery, deserialization issues
- Information disclosure (secrets in logs, error messages)
- Dependency vulnerabilities with exploitable paths

Out of scope:

- Theoretical issues without proof of concept
- Issues only reproducible on outdated dependencies (please open a regular PR to bump)
- Social engineering of contributors
- Physical attacks
- Denial of service via brute resource exhaustion (without novel vector)

## Bug bounty

No bug bounty program is active. Acknowledgments will be added to a public Hall of Fame in `SECURITY_HALL_OF_FAME.md` after V1.

## Cryptographic implementation

Facil Framework includes signature features (Phase N.5) using:

- RSA-2048 / Ed25519 for digital signatures
- AES-256-GCM for private key encryption at rest
- PAdES (PDF Advanced Electronic Signatures, ISO 32000) via `pyhanko`
- TSA timestamping for long-term validity

Cryptographic concerns receive priority handling. Self-signed certificates produced by `LocalCAProvider` provide **simple electronic signature** under eIDAS, not advanced or qualified levels. Refer to `docs/STUDIO_SIGNATURE.md` for the provider-vs-eIDAS-level matrix.

## Data privacy

Facil Framework processes personal data depending on profile and configuration. Operators are responsible for GDPR / local privacy compliance. The framework provides:

- Audit logs for data access
- Soft delete with retention windows
- Encryption at rest for sensitive fields
- Right-to-erasure endpoints (when implemented in Phase E)

For privacy concerns specific to a deployment, contact the operator of that deployment.
