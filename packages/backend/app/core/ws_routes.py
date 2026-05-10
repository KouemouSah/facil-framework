"""
WebSocket Routes — Admin real-time notifications

Endpoint: ws://host/ws/admin?token=<jwt>
Only admin/supervisor users can connect. Broadcasts RBAC events in real-time.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from app.core.ws_manager import ws_manager

router = APIRouter()


@router.websocket("/ws/admin")
async def ws_admin_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="JWT access token (query param, legacy)"),
):
    """
    WebSocket endpoint for admin real-time notifications.

    Authentication (in priority order):
        1. Sec-WebSocket-Protocol header containing the JWT token
        2. ?token= query parameter (legacy, visible in logs — deprecated)

    Events broadcasted:
        - rbac.permission.granted/revoked
        - rbac.role.updated/created/deleted
        - rbac.user.role_changed
        - rbac.agent.deactivated
    """
    # Extract token: prefer Sec-WebSocket-Protocol header over query param
    ws_protocol_token = None
    for protocol in websocket.headers.get("sec-websocket-protocol", "").split(","):
        p = protocol.strip()
        if p and p != "websocket":
            ws_protocol_token = p
            break

    effective_token = ws_protocol_token or token
    if not effective_token:
        await websocket.close(code=4001, reason="no_token")
        return

    # Validate JWT token
    user_id = None
    try:
        from app.modules.auth.services.auth_service import get_auth_service

        auth_service = get_auth_service()
        user = await auth_service.validate_access_token(effective_token)
        if not user:
            await websocket.close(code=4001, reason="invalid_token")
            return

        user_id = str(user.get("sub", ""))
        if not user_id:
            await websocket.close(code=4001, reason="no_user_id")
            return

        role = user.get("role", "") or ""

        # Admin role can connect directly via JWT
        if role == "admin":
            pass
        elif role == "agent":
            # Agents need DB check — supervisors have role=agent but role_code=supervisor_*
            from app.database.connection import db_manager
            try:
                async with db_manager.get_connection() as conn:
                    role_code = await conn.fetchval(
                        "SELECT r.code FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = $1::uuid",
                        user_id,
                    )
                    if not role_code or not role_code.startswith("supervisor"):
                        await websocket.close(code=4003, reason="admin_only")
                        return
            except Exception:
                await websocket.close(code=4003, reason="admin_only")
                return
        else:
            await websocket.close(code=4003, reason="admin_only")
            return

    except Exception as e:
        logger.warning(f"WS auth failed: {e}")
        await websocket.close(code=4001, reason="auth_error")
        return

    # Accept with subprotocol echo if token was sent via Sec-WebSocket-Protocol
    if ws_protocol_token:
        await websocket.accept(subprotocol=ws_protocol_token)
    else:
        await websocket.accept()
    await ws_manager.connect(websocket, user_id, already_accepted=True)

    try:
        # Keep connection alive — client sends pings, we echo pongs
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WS error for {user_id}: {e}")
    finally:
        await ws_manager.disconnect(user_id)
