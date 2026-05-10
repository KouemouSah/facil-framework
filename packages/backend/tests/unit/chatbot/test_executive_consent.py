"""
Unit tests for `executive_consent` — crypto & security critical path.

The Phase 5 Level 3 executive flow gates irreversible agent actions
(submit prepared request, book appointment) behind a single-use
confirmation code + SHA-256 args hash tamper detection. Any regression
here could allow a malicious or confused client to:
  - replay a consumed code (bypass "single-use")
  - tamper with the stored args between issue and redemption
  - exhaust server resources by issuing unlimited pending codes

These tests therefore exercise the critical boundary conditions rather
than the happy path alone.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.chatbot.services import executive_consent


# ---------------------------------------------------------------------------
# Canonicalization + hashing
# ---------------------------------------------------------------------------


class TestCanonicalizeArgs:
    def test_excludes_user_id_and_confirmation_code(self):
        args = {
            "user_id": "abc",
            "confirmation_code": "xyz",
            "session_id": "s1",
            "payment_method": "cash",
        }
        canon = executive_consent.canonicalize_args(args)
        assert "user_id" not in canon
        assert "confirmation_code" not in canon
        assert "session_id" in canon
        assert "payment_method" in canon

    def test_deterministic_ordering(self):
        args1 = {"b": 1, "a": 2, "session_id": "s"}
        args2 = {"a": 2, "session_id": "s", "b": 1}
        assert executive_consent.canonicalize_args(args1) == executive_consent.canonicalize_args(args2)

    def test_serializes_non_json_types(self):
        # Dates/UUIDs stringified via default=str — must not raise
        from datetime import date
        from uuid import UUID
        args = {
            "session_id": "s",
            "d": date(2026, 4, 12),
            "u": UUID("00000000-0000-0000-0000-000000000001"),
        }
        canon = executive_consent.canonicalize_args(args)
        assert "2026-04-12" in canon


class TestHashStability:
    def test_hash_args_deterministic(self):
        args = {"session_id": "s1", "payment_method": "cash"}
        assert executive_consent.hash_args(args) == executive_consent.hash_args(args)

    def test_hash_args_sha256_length(self):
        h = executive_consent.hash_args({"session_id": "s"})
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_different_args_different_hashes(self):
        a = executive_consent.hash_args({"session_id": "s1"})
        b = executive_consent.hash_args({"session_id": "s2"})
        assert a != b

    def test_user_id_does_not_affect_hash(self):
        # user_id is excluded from canonicalization, so changing it must
        # NOT change the hash — otherwise the args_hash check would fail
        # for legitimate redemptions across the issue/redeem boundary.
        a = executive_consent.hash_args({"user_id": "u1", "session_id": "s"})
        b = executive_consent.hash_args({"user_id": "u2", "session_id": "s"})
        assert a == b

    def test_hash_code_sha256(self):
        h = executive_consent.hash_code("some-random-code-value")
        assert len(h) == 64
        int(h, 16)


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------


class TestIssueConfirmationCode:
    @pytest.mark.asyncio
    async def test_unknown_tool_rejected(self):
        db = AsyncMock()
        code, err = await executive_consent.issue_confirmation_code(
            db, "user-1", "malicious_tool", {}, "summary"
        )
        assert code is None
        assert err == "executive.tool_not_allowed"

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_issuance(self):
        db = AsyncMock()
        with patch(
            "app.modules.chatbot.services.executive_consent.check_rate_limit",
            new=AsyncMock(return_value=(False, 0)),
        ):
            code, err = await executive_consent.issue_confirmation_code(
                db, "user-1", "submit_prepared_request", {"session_id": "s"}, "sum"
            )
        assert code is None
        assert err == "executive.rate_limited"

    @pytest.mark.asyncio
    async def test_issue_stores_payload_with_matching_hash(self):
        db = AsyncMock()
        cache = MagicMock()
        cache.set = AsyncMock()
        with patch(
            "app.modules.chatbot.services.executive_consent.check_rate_limit",
            new=AsyncMock(return_value=(True, 10)),
        ), patch(
            "app.modules.chatbot.services.executive_consent.get_cache",
            return_value=cache,
        ):
            code, err = await executive_consent.issue_confirmation_code(
                db,
                "user-1",
                "submit_prepared_request",
                {"session_id": "s1"},
                "summary",
            )

        assert err is None
        assert code is not None
        assert len(code) >= 20  # token_urlsafe(24) → ≥32 chars typically
        cache.set.assert_awaited_once()
        call_kwargs = cache.set.call_args
        stored_key = call_kwargs.args[0]
        stored_value = call_kwargs.args[1]
        assert stored_key.startswith("agent:exec_consent:user-1:")
        assert stored_value["tool"] == "submit_prepared_request"
        assert stored_value["summary"] == "summary"
        assert stored_value["args_hash"] == executive_consent.hash_args(
            {"session_id": "s1"}
        )


# ---------------------------------------------------------------------------
# Redeem — the security-critical half
# ---------------------------------------------------------------------------


class TestRedeemConfirmationCode:
    @pytest.mark.asyncio
    async def test_redeem_missing_key_fails(self):
        db = AsyncMock()
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.delete = AsyncMock()
        with patch(
            "app.modules.chatbot.services.executive_consent.get_cache",
            return_value=cache,
        ):
            payload, err = await executive_consent.redeem_confirmation_code(
                db, "user-1", "bogus-code"
            )
        assert payload is None
        assert err == "executive.code_expired_or_invalid"
        cache.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redeem_success_deletes_key(self):
        db = AsyncMock()
        args = {"session_id": "s1", "payment_method": "cash"}
        stored = {
            "tool": "submit_prepared_request",
            "args": args,
            "args_hash": executive_consent.hash_args(args),
            "summary": "sum",
        }
        cache = MagicMock()
        cache.get = AsyncMock(return_value=stored)
        cache.delete = AsyncMock()
        with patch(
            "app.modules.chatbot.services.executive_consent.get_cache",
            return_value=cache,
        ):
            payload, err = await executive_consent.redeem_confirmation_code(
                db, "user-1", "good-code"
            )
        assert err is None
        assert payload == stored
        cache.delete.assert_awaited_once()
        # The key deleted must match the user/code tuple
        assert cache.delete.call_args.args[0].startswith("agent:exec_consent:user-1:")

    @pytest.mark.asyncio
    async def test_redeem_detects_tampering_and_does_not_delete(self):
        """If an attacker modifies the cached args between issue and
        redemption, the recomputed SHA-256 will differ from the stored
        args_hash and the redemption must fail WITHOUT consuming the code
        (so the audit trail captures the tamper attempt)."""
        db = AsyncMock()
        stored = {
            "tool": "submit_prepared_request",
            "args": {"session_id": "s1"},
            "args_hash": "c" * 64,  # wrong hash — simulates tampering
            "summary": "sum",
        }
        cache = MagicMock()
        cache.get = AsyncMock(return_value=stored)
        cache.delete = AsyncMock()
        with patch(
            "app.modules.chatbot.services.executive_consent.get_cache",
            return_value=cache,
        ):
            payload, err = await executive_consent.redeem_confirmation_code(
                db, "user-1", "tampered-code"
            )
        assert payload is None
        assert err == "executive.invalid_args"
        cache.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_double_redeem_is_impossible(self):
        """First redemption succeeds + deletes the key. Second redemption
        finds nothing and must fail. Simulates the race where a client
        calls /execute-confirmed twice in quick succession."""
        db = AsyncMock()
        args = {"session_id": "s1"}
        stored = {
            "tool": "submit_prepared_request",
            "args": args,
            "args_hash": executive_consent.hash_args(args),
            "summary": "sum",
        }
        cache_state = {"payload": stored}

        async def fake_get(key):
            return cache_state["payload"]

        async def fake_delete(key):
            cache_state["payload"] = None

        cache = MagicMock()
        cache.get = AsyncMock(side_effect=fake_get)
        cache.delete = AsyncMock(side_effect=fake_delete)

        with patch(
            "app.modules.chatbot.services.executive_consent.get_cache",
            return_value=cache,
        ):
            payload1, err1 = await executive_consent.redeem_confirmation_code(
                db, "user-1", "code"
            )
            payload2, err2 = await executive_consent.redeem_confirmation_code(
                db, "user-1", "code"
            )

        assert err1 is None and payload1 is not None
        assert payload2 is None and err2 == "executive.code_expired_or_invalid"
