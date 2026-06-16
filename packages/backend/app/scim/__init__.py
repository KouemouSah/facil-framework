"""SCIM 2.0 provisioning (D4.13) — IdP/IGA-driven user lifecycle.

Lets an upstream IdP / IGA (Okta, Azure AD, SailPoint, Keycloak) PUSH the user
lifecycle into the platform: pre-provision accounts, push attribute changes, and
— critically at scale — DEPROVISION instantly (active=false -> account disabled +
sessions revoked), rather than waiting for the next login / introspection TTL.

Maps a SCIM User onto our `account` (+ `federated_identity` via externalId, so a
later OIDC login links to the pre-provisioned account). Auth = a dedicated bearer
token (SCIM_TOKEN). Scope: Users (the lifecycle core); Groups->roles is a follow-up.
"""
