"""OIDC back-channel logout token validation (SEC-003).

`verify()` proves a token is signed by the realm with the right issuer/audience —
but that is also true of an ordinary access token. A back-channel *logout* token is
distinguished by its claims (OpenID Connect Back-Channel Logout 1.0 §2.4): it MUST
carry the `events` claim with the back-channel-logout event, and MUST NOT carry a
`nonce`. Without this check, any holder of a valid access token could drive the
revocation endpoint.
"""

from __future__ import annotations

_BACKCHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"


def is_backchannel_logout_token(claims: dict) -> bool:
    """True iff `claims` is a genuine OIDC back-channel logout token."""
    if "nonce" in claims:  # §2.4: a logout token MUST NOT contain a nonce
        return False
    events = claims.get("events")
    return isinstance(events, dict) and _BACKCHANNEL_LOGOUT_EVENT in events
