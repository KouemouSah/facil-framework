"""
Database connection management for TaxasGE Backend
Supports both direct PostgreSQL and Supabase connections
"""

import asyncio
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from loguru import logger

from app.config import settings


class DatabaseManager:
    """Database connection manager with connection pooling"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize database connection pool"""
        if self.pool is not None:
            return

        async with self._lock:
            if self.pool is not None:
                return

            try:
                logger.info("= Initializing database connection pool...")

                # Use Supabase connection string if available, fallback to direct PostgreSQL
                connection_string = settings.DATABASE_URL
                if not connection_string:
                    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
                        # Construct Supabase PostgreSQL connection string
                        supabase_host = settings.SUPABASE_URL.replace('https://', '').replace('http://', '')
                        connection_string = (
                            f"postgresql://postgres:{settings.SUPABASE_SERVICE_ROLE_KEY}"
                            f"@db.{supabase_host}:5432/postgres"
                        )
                    else:
                        raise ValueError("No database connection configuration found")

                pool_min = settings.DATABASE_MIN_CONNECTIONS
                pool_max = settings.DATABASE_MAX_CONNECTIONS
                logger.info(f"  Connection pool: min={pool_min}, max={pool_max}")

                self.pool = await asyncpg.create_pool(
                    connection_string,
                    min_size=pool_min,
                    max_size=pool_max,
                    command_timeout=60,
                    max_queries=50000,  # Recycle connections after 50k queries
                    max_inactive_connection_lifetime=300,  # Close idle connections after 5min
                    server_settings={
                        'jit': 'off',  # Disable JIT for faster connection
                        'application_name': f'taxasge-{settings.ENVIRONMENT}',
                        'statement_timeout': '60000',  # 60s (override Supabase 2min default)
                    }
                )

                # Test connection
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

                logger.success(f" Database pool initialized ({settings.DATABASE_MIN_CONNECTIONS}-{settings.DATABASE_MAX_CONNECTIONS} connections)")

            except Exception as e:
                logger.error(f"L Failed to initialize database pool: {e}")
                if settings.ENVIRONMENT == "development":
                    logger.warning("= Continuing in development mode without database")
                    self.pool = None
                else:
                    raise

    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("= Database pool closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get database connection from pool"""
        if self.pool is None:
            await self.connect()

        if self.pool is None:
            raise RuntimeError("Database connection not available")

        async with self.pool.acquire() as connection:
            yield connection

    async def execute_query(self, query: str, *args) -> list:
        """Execute a query and return results"""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)

    async def execute_single(self, query: str, *args):
        """Execute a query and return single result"""
        async with self.get_connection() as conn:
            return await conn.fetchrow(query, *args)

    async def execute_scalar(self, query: str, *args):
        """Execute a query and return scalar value"""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

    async def execute_command(self, query: str, *args) -> str:
        """Execute a command (INSERT, UPDATE, DELETE)"""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)


# Global database manager instance
db_manager = DatabaseManager()


# FastAPI dependency for database connection
async def get_database() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency to get database connection"""
    async with db_manager.get_connection() as conn:
        yield conn


# Direct connection getter (for repositories that need raw connection)
async def get_db_connection() -> asyncpg.Connection:
    """Get a database connection directly (not as generator).

    Use this for repositories that need direct connection access.
    Caller is responsible for using connection within context of request.
    """
    return await db_manager.pool.acquire()


async def release_db_connection(conn: asyncpg.Connection):
    """Release a database connection back to the pool."""
    await db_manager.pool.release(conn)


# Convenience functions for common operations
async def fetch_all(query: str, *args) -> list:
    """Fetch all rows from query"""
    return await db_manager.execute_query(query, *args)


async def fetch_one(query: str, *args):
    """Fetch single row from query"""
    return await db_manager.execute_single(query, *args)


async def fetch_val(query: str, *args):
    """Fetch single value from query"""
    return await db_manager.execute_scalar(query, *args)


async def execute(query: str, *args) -> str:
    """Execute command query"""
    return await db_manager.execute_command(query, *args)


async def get_db_pool() -> asyncpg.Pool:
    """
    Get the database connection pool directly.

    Used by event handlers and other components that need direct pool access.
    Ensures pool is initialized before returning.

    Returns:
        asyncpg.Pool: The database connection pool

    Raises:
        RuntimeError: If pool cannot be initialized
    """
    if db_manager.pool is None:
        await db_manager.connect()

    if db_manager.pool is None:
        raise RuntimeError("Database pool not available")

    return db_manager.pool