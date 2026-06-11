"""Legal module — Privacy Policy + Terms of Service versions and acceptance.

Exposes:
- GET  /api/v1/legal/versions  : current versions (public, no auth)
- POST /api/v1/legal/accept    : record acceptance for current user (auth required, role-gated)
"""
