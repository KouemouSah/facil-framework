"""
WebSocket Manager for Real-Time Admin Notifications

Broadcasts RBAC change events to connected admin clients.
Architecture:
  PostgreSQL NOTIFY → RBACListener → EventBus → WebSocketManager → Admin clients

Only admin users (role_code starts with 'admin') can connect.
"""
import asyncio
import json
from typing import Dict, Optional
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class WebSocketManager:
    """Manages WebSocket connections for real-time admin notifications."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}  # user_id → ws
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, already_accepted: bool = False) -> None:
        if not already_accepted:
            await websocket.accept()
        async with self._lock:
            # Close existing connection for same user (prevent stale)
            if user_id in self._connections:
                try:
                    await self._connections[user_id].close(code=1000, reason="new_connection")
                except Exception:
                    pass
            self._connections[user_id] = websocket
        logger.debug(f"WS admin connected: {user_id} (total: {len(self._connections)})")

    async def disconnect(self, user_id: str) -> None:
        async with self._lock:
            self._connections.pop(user_id, None)
        logger.debug(f"WS admin disconnected: {user_id} (total: {len(self._connections)})")

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast an RBAC event to all connected admin clients."""
        if not self._connections:
            return

        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        async def _send(user_id: str, ws: WebSocket) -> str | None:
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=5.0)
                return None
            except Exception:
                return user_id

        async with self._lock:
            tasks = [_send(uid, ws) for uid, ws in self._connections.items()]
            results = await asyncio.gather(*tasks)
            disconnected = [uid for uid in results if uid is not None]

            for uid in disconnected:
                self._connections.pop(uid, None)

        if disconnected:
            logger.debug(f"WS: cleaned {len(disconnected)} stale connections")

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton
ws_manager = WebSocketManager()
