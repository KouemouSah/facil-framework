"""
RBAC Cache Invalidation Listener

Listens to PostgreSQL NOTIFY 'rbac_changes' channel and invalidates
Redis permission caches in real-time (< 50ms latency).

Architecture:
  PostgreSQL trigger → NOTIFY 'rbac_changes' → this listener → Redis invalidation

This replaces the 10min TTL-based cache expiry with instant invalidation.
"""
import asyncio
import json
from typing import Optional

import asyncpg
from loguru import logger

from app.core.cache import (
    invalidate_user_permissions_cache,
    invalidate_role_permissions_cache,
    invalidate_all_permissions_cache,
)
from app.core.events import EventBus
from app.core.events.event_types import EventType
from app.core.ws_manager import ws_manager


class RBACListener:
    """Listens to PostgreSQL NOTIFY for RBAC changes and invalidates caches."""

    def __init__(self):
        self._conn: Optional[asyncpg.Connection] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, pool: asyncpg.Pool) -> None:
        """Start listening for RBAC changes on a dedicated connection."""
        if self._running:
            return

        try:
            # Acquire a dedicated connection for LISTEN (not from pool — long-lived)
            self._conn = await pool.acquire()
            await self._conn.add_listener('rbac_changes', self._on_notification)
            self._running = True
            logger.info("RBAC cache listener started on channel 'rbac_changes'")
        except Exception as e:
            logger.warning(f"Failed to start RBAC listener (cache TTL fallback active): {e}")
            if self._conn:
                try:
                    await pool.release(self._conn)
                except Exception:
                    pass
                self._conn = None

    async def stop(self, pool: Optional[asyncpg.Pool] = None) -> None:
        """Stop listening and release the dedicated connection."""
        self._running = False
        if self._conn:
            try:
                await self._conn.remove_listener('rbac_changes', self._on_notification)
                if pool:
                    await pool.release(self._conn)
            except Exception as e:
                logger.debug(f"Error stopping RBAC listener: {e}")
            finally:
                self._conn = None
            logger.info("RBAC cache listener stopped")

    def _on_notification(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Handle PostgreSQL NOTIFY — runs in asyncpg's callback thread."""
        # Schedule the async handler on the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._handle_rbac_change(payload))
        except RuntimeError:
            logger.warning("No event loop for RBAC notification handler")

    async def _handle_rbac_change(self, payload: str) -> None:
        """Process RBAC change notification and invalidate appropriate caches."""
        try:
            data = json.loads(payload)
            table = data.get('table')
            op = data.get('op')

            if table == 'users' and op == 'ROLE_CHANGE':
                # User's role changed → invalidate that user's permission cache
                user_id = data.get('user_id')
                if user_id:
                    await invalidate_user_permissions_cache(str(user_id))
                    EventBus.publish_nowait(EventType.RBAC_USER_ROLE_CHANGED, {
                        "user_id": str(user_id),
                        "old_role_id": data.get("old_role_id"),
                        "new_role_id": data.get("new_role_id"),
                    })
                    logger.info(f"RBAC NOTIFY: user {user_id} role changed → cache invalidated")
                    # Broadcast to admin WebSocket clients
                    await ws_manager.broadcast("rbac.user.role_changed", {
                        "user_id": str(user_id),
                        "old_role_id": data.get("old_role_id"),
                        "new_role_id": data.get("new_role_id"),
                    })

            elif table == 'user_permissions':
                # User-level permission changed → invalidate that user
                user_id = data.get('user_id')
                if user_id:
                    await invalidate_user_permissions_cache(str(user_id))
                    event_name = "rbac.permission.granted" if op == 'INSERT' else "rbac.permission.revoked"
                    event = EventType.RBAC_PERMISSION_GRANTED if op == 'INSERT' else EventType.RBAC_PERMISSION_REVOKED
                    EventBus.publish_nowait(event, {"user_id": str(user_id), "source": "user_override"})
                    logger.debug(f"RBAC NOTIFY: user_permission {op} for {user_id}")
                    await ws_manager.broadcast(event_name, {
                        "user_id": str(user_id), "source": "user_override", "op": op,
                    })

            elif table in ('role_permissions', 'roles'):
                # Role-level change → invalidate all user caches (users inherit from roles)
                await invalidate_all_permissions_cache()
                if table == 'role_permissions':
                    event_name = "rbac.permission.granted" if op == 'INSERT' else "rbac.permission.revoked"
                    event = EventType.RBAC_PERMISSION_GRANTED if op == 'INSERT' else EventType.RBAC_PERMISSION_REVOKED
                    EventBus.publish_nowait(event, {"role_id": data.get("role_id"), "source": "role"})
                    await ws_manager.broadcast(event_name, {
                        "role_id": data.get("role_id"), "source": "role", "op": op,
                    })
                else:
                    EventBus.publish_nowait(EventType.RBAC_ROLE_UPDATED, {"role_id": data.get("role_id")})
                    await ws_manager.broadcast("rbac.role.updated", {
                        "role_id": data.get("role_id"), "op": op,
                    })
                logger.info(f"RBAC NOTIFY: {table} {op} → all permission caches invalidated")

        except json.JSONDecodeError:
            logger.warning(f"Invalid RBAC notification payload: {payload}")
        except Exception as e:
            logger.error(f"Error handling RBAC notification: {e}")


# Singleton instance
rbac_listener = RBACListener()
