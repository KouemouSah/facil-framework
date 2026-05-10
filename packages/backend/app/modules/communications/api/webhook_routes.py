"""
API routes for webhook configurations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any
import asyncpg

from ..models.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookListResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookLogResponse
)
from ..services.webhook_service import WebhookService
from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.users.models.user import UserResponse

router = APIRouter(prefix="/communications/webhooks", tags=["Communications - Webhooks"])
service = WebhookService()


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook configuration"
)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: asyncpg.Connection = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("communication.manage"))
):
    """
    Create a new webhook configuration.

    **Required permissions:** `manage:communications`

    **Webhook types:**
    - `whatsapp`: WhatsApp Business API integration
    - `custom`: Custom webhook endpoint

    **Authentication types:**
    - `none`: No authentication
    - `api_key`: API key in custom header
    - `bearer`: Bearer token in Authorization header
    - `basic`: Basic authentication (username:password)

    **Payload template:**
    Use `{{variable_name}}` syntax for variable substitution from event data.

    **Example:**
    ```json
    {
      "name": "WhatsApp Notifications",
      "webhook_type": "whatsapp",
      "endpoint_url": "https://api.whatsapp.com/v1/messages",
      "http_method": "POST",
      "auth_type": "bearer",
      "auth_config": {
        "bearer_token": "your-token"
      },
      "payload_template": {
        "to": "{{phone_number}}",
        "type": "template",
        "template": {
          "name": "{{template_name}}"
        }
      },
      "events": ["payment_received", "declaration_submitted"]
    }
    ```
    """
    user_id = current_user.id
    return await service.create_webhook(db, webhook_data, user_id)


@router.get(
    "",
    response_model=WebhookListResponse,
    summary="List webhook configurations"
)
async def list_webhooks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    webhook_type: Optional[str] = Query(None, description="Filter by webhook type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.view"))
):
    """
    List all webhook configurations with pagination and filters.

    **Required permissions:** `read:communications`

    **Query parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 50, max: 100)
    - `webhook_type`: Filter by type (`whatsapp`, `custom`)
    - `is_active`: Filter by active status
    """
    return await service.list_webhooks(
        db,
        page=page,
        page_size=page_size,
        webhook_type=webhook_type,
        is_active=is_active
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook configuration"
)
async def get_webhook(
    webhook_id: int,
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.view"))
):
    """
    Get webhook configuration by ID.

    **Required permissions:** `read:communications`
    """
    return await service.get_webhook(db, webhook_id)


@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook configuration"
)
async def update_webhook(
    webhook_id: int,
    webhook_data: WebhookUpdate,
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.manage"))
):
    """
    Update webhook configuration.

    **Required permissions:** `manage:communications`

    All fields are optional. Only provided fields will be updated.
    """
    return await service.update_webhook(db, webhook_id, webhook_data)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook configuration"
)
async def delete_webhook(
    webhook_id: int,
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.manage"))
):
    """
    Delete webhook configuration.

    **Required permissions:** `manage:communications`

    **Warning:** This will permanently delete the webhook and all associated logs.
    """
    await service.delete_webhook(db, webhook_id)


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook configuration"
)
async def test_webhook(
    webhook_id: int,
    test_request: WebhookTestRequest,
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.manage"))
):
    """
    Test webhook by sending a test request.

    **Required permissions:** `manage:communications`

    This will:
    1. Send a real HTTP request to the webhook endpoint
    2. Log the execution result
    3. Update the webhook's last triggered status
    4. Return detailed response information

    **Optional test payload:**
    Provide custom test data. If payload template exists, variables will be substituted.

    **Example:**
    ```json
    {
      "test_payload": {
        "phone_number": "+240222123456",
        "template_name": "payment_confirmation",
        "message": "Test message"
      }
    }
    ```

    **Response includes:**
    - Success status
    - HTTP status code
    - Response body (truncated to 1000 chars)
    - Request duration in milliseconds
    - Masked request headers (sensitive data hidden)
    - Full request payload
    """
    return await service.test_webhook(db, webhook_id, test_request)


@router.get(
    "/{webhook_id}/logs",
    summary="Get webhook execution logs"
)
async def get_webhook_logs(
    webhook_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: asyncpg.Connection = Depends(get_database),
    _: None = Depends(get_current_user),
    __: None = Depends(permission_required("communication.view"))
):
    """
    Get execution logs for webhook.

    **Required permissions:** `read:communications`

    Returns paginated list of webhook execution logs including:
    - Event type
    - Request payload
    - Response status and body
    - Duration
    - Error messages (if any)
    - Timestamp

    **Query parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 50, max: 100)
    """
    return await service.get_webhook_logs(
        db,
        webhook_id,
        page=page,
        page_size=page_size
    )
