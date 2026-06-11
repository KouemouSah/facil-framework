"""
Service for webhook configurations and execution
"""
import asyncpg
import httpx
import base64
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from loguru import logger

from ..models.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookListResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookLogCreate,
    WebhookLogResponse,
    AuthType
)
from ..repositories.webhook_repository import WebhookRepository
from fastapi import HTTPException, status


class WebhookService:
    """Business logic for webhook operations"""

    def __init__(self):
        self.repository = WebhookRepository()

    async def create_webhook(
        self,
        db: asyncpg.Connection,
        webhook_data: WebhookCreate,
        created_by: int
    ) -> WebhookResponse:
        """Create a new webhook configuration"""
        try:
            webhook = await self.repository.create(db, webhook_data, created_by)
            logger.info(f"Webhook created: {webhook.id} by user {created_by}")
            return webhook
        except Exception as e:
            logger.error(f"Error creating webhook: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create webhook configuration"
            )

    async def get_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int
    ) -> WebhookResponse:
        """Get webhook configuration by ID"""
        webhook = await self.repository.find_by_id(db, webhook_id)
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        return webhook

    async def list_webhooks(
        self,
        db: asyncpg.Connection,
        page: int = 1,
        page_size: int = 50,
        webhook_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> WebhookListResponse:
        """List webhook configurations with pagination"""
        offset = (page - 1) * page_size

        webhooks = await self.repository.find_all(
            db,
            limit=page_size,
            offset=offset,
            webhook_type=webhook_type,
            is_active=is_active
        )

        total = await self.repository.count(
            db,
            webhook_type=webhook_type,
            is_active=is_active
        )

        total_pages = (total + page_size - 1) // page_size

        return WebhookListResponse(
            webhooks=webhooks,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    async def update_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        webhook_data: WebhookUpdate
    ) -> WebhookResponse:
        """Update webhook configuration"""
        # Check if webhook exists
        existing = await self.repository.find_by_id(db, webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )

        webhook = await self.repository.update(db, webhook_id, webhook_data)
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update webhook configuration"
            )

        logger.info(f"Webhook updated: {webhook_id}")
        return webhook

    async def delete_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int
    ) -> None:
        """Delete webhook configuration"""
        # Check if webhook exists
        existing = await self.repository.find_by_id(db, webhook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )

        deleted = await self.repository.delete(db, webhook_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete webhook configuration"
            )

        logger.info(f"Webhook deleted: {webhook_id}")

    async def test_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        test_request: WebhookTestRequest
    ) -> WebhookTestResponse:
        """Test webhook by sending a test request"""
        webhook = await self.get_webhook(db, webhook_id)

        # Prepare test payload
        test_payload = test_request.test_payload or {"test": True, "timestamp": datetime.now(timezone.utc).isoformat()}

        # If payload template exists, merge with test data
        if webhook.payload_template:
            payload = self._merge_payload_template(webhook.payload_template, test_payload)
        else:
            payload = test_payload

        # Execute webhook
        start_time = datetime.now(timezone.utc)
        result = await self._execute_webhook(webhook, payload, "test_event")
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Log test execution
        log_data = WebhookLogCreate(
            webhook_id=webhook_id,
            event_type="test_event",
            request_payload=payload,
            response_status=result.get("status_code"),
            response_body=result.get("response_body"),
            duration_ms=duration_ms,
            error_message=result.get("error_message")
        )
        await self.repository.create_log(db, log_data)

        # Update last triggered
        await self.repository.update_last_triggered(
            db,
            webhook_id,
            "success" if result.get("success") else "error"
        )

        # Mask sensitive data in headers
        masked_headers = self._mask_auth_headers(result.get("request_headers", {}))

        return WebhookTestResponse(
            success=result.get("success", False),
            status_code=result.get("status_code"),
            response_body=result.get("response_body"),
            duration_ms=duration_ms,
            error_message=result.get("error_message"),
            request_url=webhook.endpoint_url,
            request_method=webhook.http_method.value,
            request_headers=masked_headers,
            request_payload=payload
        )

    async def trigger_webhook(
        self,
        db: asyncpg.Connection,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> List[WebhookLogResponse]:
        """Trigger all webhooks listening to specific event"""
        webhooks = await self.repository.find_by_event(db, event_type)

        if not webhooks:
            logger.info(f"No active webhooks found for event: {event_type}")
            return []

        logs = []
        for webhook in webhooks:
            try:
                # Prepare payload
                if webhook.payload_template:
                    payload = self._merge_payload_template(webhook.payload_template, event_data)
                else:
                    payload = event_data

                # Execute webhook
                start_time = datetime.now(timezone.utc)
                result = await self._execute_webhook(webhook, payload, event_type)
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)

                # Log execution
                log_data = WebhookLogCreate(
                    webhook_id=webhook.id,
                    event_type=event_type,
                    request_payload=payload,
                    response_status=result.get("status_code"),
                    response_body=result.get("response_body"),
                    duration_ms=duration_ms,
                    error_message=result.get("error_message")
                )
                log = await self.repository.create_log(db, log_data)
                logs.append(log)

                # Update last triggered
                await self.repository.update_last_triggered(
                    db,
                    webhook.id,
                    "success" if result.get("success") else "error"
                )

            except Exception as e:
                logger.error(f"Error triggering webhook {webhook.id}: {str(e)}")
                # Log error
                log_data = WebhookLogCreate(
                    webhook_id=webhook.id,
                    event_type=event_type,
                    request_payload=event_data,
                    error_message=str(e)
                )
                log = await self.repository.create_log(db, log_data)
                logs.append(log)

        return logs

    async def get_webhook_logs(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get execution logs for webhook"""
        # Check if webhook exists
        webhook = await self.repository.find_by_id(db, webhook_id)
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )

        offset = (page - 1) * page_size
        logs = await self.repository.find_logs_by_webhook(db, webhook_id, page_size, offset)
        total = await self.repository.count_logs_by_webhook(db, webhook_id)
        total_pages = (total + page_size - 1) // page_size

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    # Private helper methods
    async def _execute_webhook(
        self,
        webhook: WebhookResponse,
        payload: Dict[str, Any],
        event_type: str
    ) -> Dict[str, Any]:
        """Execute webhook HTTP request"""
        try:
            # Prepare headers
            headers = webhook.headers.copy()
            headers.setdefault("Content-Type", "application/json")

            # Add authentication
            headers = self._add_authentication(headers, webhook.auth_type, webhook.auth_config)

            # Make HTTP request
            async with httpx.AsyncClient(timeout=webhook.timeout_seconds) as client:
                response = await client.request(
                    method=webhook.http_method.value,
                    url=webhook.endpoint_url,
                    json=payload,
                    headers=headers
                )

                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response_body": response.text[:1000],  # Limit response size
                    "request_headers": headers
                }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error_message": f"Request timeout after {webhook.timeout_seconds} seconds",
                "request_headers": headers
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error_message": f"Request error: {str(e)}",
                "request_headers": headers
            }
        except Exception as e:
            return {
                "success": False,
                "error_message": f"Unexpected error: {str(e)}",
                "request_headers": headers
            }

    def _add_authentication(
        self,
        headers: Dict[str, str],
        auth_type: AuthType,
        auth_config: Dict[str, Any]
    ) -> Dict[str, str]:
        """Add authentication headers based on auth type"""
        if auth_type == AuthType.api_key:
            api_key = auth_config.get("api_key")
            api_key_header = auth_config.get("api_key_header", "X-API-Key")
            if api_key:
                headers[api_key_header] = api_key

        elif auth_type == AuthType.bearer:
            bearer_token = auth_config.get("bearer_token")
            if bearer_token:
                headers["Authorization"] = f"Bearer {bearer_token}"

        elif auth_type == AuthType.basic:
            username = auth_config.get("basic_username")
            password = auth_config.get("basic_password")
            if username and password:
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"

        return headers

    def _merge_payload_template(
        self,
        template: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge payload template with event data (simple variable substitution)"""
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # Variable substitution: {{variable_name}}
                var_name = value[2:-2].strip()
                result[key] = data.get(var_name, value)
            elif isinstance(value, dict):
                result[key] = self._merge_payload_template(value, data)
            elif isinstance(value, list):
                result[key] = [
                    self._merge_payload_template(item, data) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _mask_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive authentication headers"""
        masked = headers.copy()
        sensitive_headers = ["authorization", "x-api-key", "api-key"]

        for key in masked:
            if key.lower() in sensitive_headers:
                masked[key] = "***"

        return masked
