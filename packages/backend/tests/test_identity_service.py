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
