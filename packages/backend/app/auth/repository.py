"""Data access for credentials (auth)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Credential


async def get_credential(session: AsyncSession, account_id: str) -> Credential | None:
    return await session.scalar(
        select(Credential).where(Credential.account_id == account_id))
