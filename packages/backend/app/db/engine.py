"""Async engine + session factory (SQLAlchemy 2.0, asyncpg driver)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(url, echo=echo, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Database:
    """Holds the engine + session factory for the app lifespan."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = make_engine(url, echo=echo)
        self.session_factory = make_session_factory(self.engine)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as s:
            yield s

    async def dispose(self) -> None:
        await self.engine.dispose()
