"""Identity service — register (unique NIU) + login-identifier resolution (D4.1)."""

from __future__ import annotations

import pytest

from app.identity import number as num
from app.identity import service
from app.identity.number import NumberStrategy


@pytest.mark.asyncio
async def test_register_mints_valid_unique_number(client):
    _, db = client
    s = NumberStrategy()
    async with db.session_factory() as session:
        a = await service.register(session, email="a@x.io")
        b = await service.register(session, email="b@x.io")
        await session.commit()
    assert num.validate(a.account_number, s) and num.validate(b.account_number, s)
    assert a.account_number != b.account_number
    assert a.email == "a@x.io" and a.status == "active"


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    _, db = client
    async with db.session_factory() as session:
        await service.register(session, email="dup@x.io")
        await session.commit()
    async with db.session_factory() as session:
        with pytest.raises(service.EmailTaken):
            await service.register(session, email="dup@x.io")


@pytest.mark.asyncio
async def test_register_without_email(client):
    _, db = client
    async with db.session_factory() as session:
        a = await service.register(session)  # NIU-only account
        await session.commit()
    assert a.email is None and a.account_number


@pytest.mark.asyncio
async def test_resolve_by_email_and_number(client):
    _, db = client
    async with db.session_factory() as session:
        a = await service.register(session, email="find@x.io")
        await session.commit()
        num_value = a.account_number
    async with db.session_factory() as session:
        by_email = await service.resolve_identifier(session, "find@x.io")
        by_number = await service.resolve_identifier(session, num_value)
        assert by_email is not None and by_number is not None
        assert by_email.id == by_number.id


@pytest.mark.asyncio
async def test_resolve_rejects_typo_and_unknown(client):
    _, db = client
    s = NumberStrategy()
    async with db.session_factory() as session:
        a = await service.register(session, email="t@x.io")
        await session.commit()
        n = a.account_number
    async with db.session_factory() as session:
        # flip one digit -> check-digit fails -> None (no DB hit needed)
        typo = n[:-3] + str((int(n[-3]) + 1) % 10) + n[-2:]
        assert await service.resolve_identifier(session, typo, s) is None
        assert await service.resolve_identifier(session, "", s) is None
        # a well-formed but non-existent number resolves to None
        async with db.session_factory():
            pass
        ghost = num.mint(s)
        assert await service.resolve_identifier(session, ghost, s) is None


_CAT_STRATEGY = NumberStrategy.from_config(
    {"category_prefixes": {"national": "1", "foreigner": "2"}, "body_length": 8})


@pytest.mark.asyncio
async def test_gated_policy_defers_niu_until_issued(client):
    _, db = client
    async with db.session_factory() as session:
        a = await service.register(session, email="kyc@x.io",
                                   policy="on_verified_document")
        await session.commit()
        assert a.account_number is None and a.status == "pending_identity"
        # later: identity verified -> issue NIU as a national
        await service.issue_number(session, a, category="national",
                                   strategy=_CAT_STRATEGY)
        await session.commit()
    assert a.account_number.startswith("1") and a.status == "active"
    assert a.subject_type == "national"
    assert num.validate(a.account_number, _CAT_STRATEGY)


@pytest.mark.asyncio
async def test_foreigner_distinguishable_from_national(client):
    _, db = client
    async with db.session_factory() as session:
        nat = await service.register(session, policy="on_verified_document")
        fgn = await service.register(session, policy="on_verified_document")
        await service.issue_number(session, nat, category="national", strategy=_CAT_STRATEGY)
        await service.issue_number(session, fgn, category="foreigner", strategy=_CAT_STRATEGY)
        await session.commit()
    assert nat.account_number[0] == "1" and fgn.account_number[0] == "2"


@pytest.mark.asyncio
async def test_niu_is_immutable_no_reissue(client):
    _, db = client
    async with db.session_factory() as session:
        a = await service.register(session, email="im@x.io")  # immediate -> has NIU
        await session.commit()
        with pytest.raises(service.AlreadyIssued):
            await service.issue_number(session, a, category="national",
                                       strategy=_CAT_STRATEGY)


@pytest.mark.asyncio
async def test_resolve_normalizes_separators(client):
    _, db = client
    async with db.session_factory() as session:
        a = await service.register(session)
        await session.commit()
        n = a.account_number
    async with db.session_factory() as session:
        spaced = " ".join([n[:4], n[4:8], n[8:]])
        assert (await service.resolve_identifier(session, spaced)).account_number == n
