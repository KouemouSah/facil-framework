"""identity — accounts + the generic account_number (NIU) generation (D4.1).

Core (always-on) infrastructure, NOT a business module: every deployment has
accounts. The account_number is a generic, configurable unique identifier
(NIU / matricule / customer number) auto-generated at registration and usable
as a login identifier alongside email. See PHASE_D4_AUTH_RBAC_PLAN.md.
"""
