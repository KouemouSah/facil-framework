"""SEC-003 — only a genuine OIDC back-channel logout token may revoke a session."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.logout_token import is_backchannel_logout_token  # noqa: E402

_EVENT = "http://schemas.openid.net/event/backchannel-logout"


def test_genuine_logout_token_accepted():
    assert is_backchannel_logout_token({"sub": "u", "sid": "s", "events": {_EVENT: {}}}) is True


def test_plain_access_token_rejected():
    # A normal access token (no events claim) must NOT be usable to revoke.
    assert is_backchannel_logout_token({"sub": "u", "sid": "s"}) is False


def test_token_with_nonce_rejected():
    # OIDC back-channel logout §2.4: a logout token MUST NOT contain a nonce.
    assert is_backchannel_logout_token(
        {"sub": "u", "events": {_EVENT: {}}, "nonce": "n"}) is False


def test_events_without_logout_key_rejected():
    assert is_backchannel_logout_token({"events": {"some/other/event": {}}}) is False
