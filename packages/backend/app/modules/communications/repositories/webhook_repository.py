"""
Repository for webhook configurations and logs
"""
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json

from ..models.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookLogCreate,
    WebhookLogResponse
)


class WebhookRepository:
    """Data access layer for webhook_configurations table"""

    async def create(
        self,
        db: asyncpg.Connection,
        webhook_data: WebhookCreate,
        created_by: int
    ) -> WebhookResponse:
        """Create a new webhook configuration"""
        query = """
            INSERT INTO webhook_configurations (
                name, webhook_type, endpoint_url, http_method, headers,
                auth_type, auth_config, payload_template, retry_config,
                timeout_seconds, events, is_active, created_by, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
            RETURNING id, name, webhook_type, endpoint_url, http_method, headers,
                      auth_type, auth_config, payload_template, retry_config,
                      timeout_seconds, events, is_active, last_triggered_at,
                      last_status, created_at, updated_at, created_by
        """
        row = await db.fetchrow(
            query,
            webhook_data.name,
            webhook_data.webhook_type.value,
            webhook_data.endpoint_url,
            webhook_data.http_method.value,
            json.dumps(webhook_data.headers),
            webhook_data.auth_type.value,
            json.dumps(webhook_data.auth_config),
            json.dumps(webhook_data.payload_template) if webhook_data.payload_template else None,
            json.dumps(webhook_data.retry_config.model_dump()),
            webhook_data.timeout_seconds,
            webhook_data.events,
            webhook_data.is_active,
            created_by
        )
        return self._row_to_webhook(row)

    async def find_by_id(
        self,
        db: asyncpg.Connection,
        webhook_id: int
    ) -> Optional[WebhookResponse]:
        """Find webhook configuration by ID"""
        query = """
            SELECT id, name, webhook_type, endpoint_url, http_method, headers,
                   auth_type, auth_config, payload_template, retry_config,
                   timeout_seconds, events, is_active, last_triggered_at,
                   last_status, created_at, updated_at, created_by
            FROM webhook_configurations
            WHERE id = $1
        """
        row = await db.fetchrow(query, webhook_id)
        return self._row_to_webhook(row) if row else None

    async def find_all(
        self,
        db: asyncpg.Connection,
        limit: int = 100,
        offset: int = 0,
        webhook_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[WebhookResponse]:
        """List all webhook configurations with pagination and filters"""
        conditions = []
        params = []
        param_count = 1

        if webhook_type is not None:
            conditions.append(f"webhook_type = ${param_count}")
            params.append(webhook_type)
            param_count += 1

        if is_active is not None:
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, name, webhook_type, endpoint_url, http_method, headers,
                   auth_type, auth_config, payload_template, retry_config,
                   timeout_seconds, events, is_active, last_triggered_at,
                   last_status, created_at, updated_at, created_by
            FROM webhook_configurations
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(query, *params)
        return [self._row_to_webhook(row) for row in rows]

    async def count(
        self,
        db: asyncpg.Connection,
        webhook_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """Count total webhook configurations"""
        conditions = []
        params = []
        param_count = 1

        if webhook_type is not None:
            conditions.append(f"webhook_type = ${param_count}")
            params.append(webhook_type)
            param_count += 1

        if is_active is not None:
            conditions.append(f"is_active = ${param_count}")
            params.append(is_active)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"SELECT COUNT(*) FROM webhook_configurations {where_clause}"
        return await db.fetchval(query, *params)

    async def update(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        webhook_data: WebhookUpdate
    ) -> Optional[WebhookResponse]:
        """Update webhook configuration"""
        # Build dynamic update query
        updates = []
        params = []
        param_count = 1

        update_fields = webhook_data.model_dump(exclude_unset=True)

        for field, value in update_fields.items():
            if field == "retry_config" and value is not None:
                updates.append(f"{field} = ${param_count}")
                params.append(json.dumps(value.model_dump()))
            elif field in ["headers", "auth_config", "payload_template"] and value is not None:
                updates.append(f"{field} = ${param_count}")
                params.append(json.dumps(value))
            elif field in ["webhook_type", "http_method", "auth_type"] and value is not None:
                updates.append(f"{field} = ${param_count}")
                params.append(value.value)
            else:
                updates.append(f"{field} = ${param_count}")
                params.append(value)
            param_count += 1

        if not updates:
            return await self.find_by_id(db, webhook_id)

        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.now(timezone.utc))
        param_count += 1

        params.append(webhook_id)

        query = f"""
            UPDATE webhook_configurations
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, name, webhook_type, endpoint_url, http_method, headers,
                      auth_type, auth_config, payload_template, retry_config,
                      timeout_seconds, events, is_active, last_triggered_at,
                      last_status, created_at, updated_at, created_by
        """

        row = await db.fetchrow(query, *params)
        return self._row_to_webhook(row) if row else None

    async def delete(self, db: asyncpg.Connection, webhook_id: int) -> bool:
        """Delete webhook configuration"""
        query = "DELETE FROM webhook_configurations WHERE id = $1"
        result = await db.execute(query, webhook_id)
        return result == "DELETE 1"

    async def update_last_triggered(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        status: str
    ) -> None:
        """Update last triggered timestamp and status"""
        query = """
            UPDATE webhook_configurations
            SET last_triggered_at = NOW(), last_status = $1, updated_at = NOW()
            WHERE id = $2
        """
        await db.execute(query, status, webhook_id)

    async def find_by_event(
        self,
        db: asyncpg.Connection,
        event_type: str
    ) -> List[WebhookResponse]:
        """Find active webhooks that listen to specific event"""
        query = """
            SELECT id, name, webhook_type, endpoint_url, http_method, headers,
                   auth_type, auth_config, payload_template, retry_config,
                   timeout_seconds, events, is_active, last_triggered_at,
                   last_status, created_at, updated_at, created_by
            FROM webhook_configurations
            WHERE is_active = true AND $1 = ANY(events)
            ORDER BY created_at ASC
        """
        rows = await db.fetch(query, event_type)
        return [self._row_to_webhook(row) for row in rows]

    # Webhook Logs
    async def create_log(
        self,
        db: asyncpg.Connection,
        log_data: WebhookLogCreate
    ) -> WebhookLogResponse:
        """Create a webhook execution log"""
        query = """
            INSERT INTO webhook_logs (
                webhook_id, event_type, request_payload, response_status,
                response_body, duration_ms, error_message, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING id, webhook_id, event_type, request_payload, response_status,
                      response_body, duration_ms, error_message, created_at
        """
        row = await db.fetchrow(
            query,
            log_data.webhook_id,
            log_data.event_type,
            json.dumps(log_data.request_payload),
            log_data.response_status,
            log_data.response_body,
            log_data.duration_ms,
            log_data.error_message
        )
        return self._row_to_log(row)

    async def find_logs_by_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[WebhookLogResponse]:
        """Find logs for specific webhook"""
        query = """
            SELECT id, webhook_id, event_type, request_payload, response_status,
                   response_body, duration_ms, error_message, created_at
            FROM webhook_logs
            WHERE webhook_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        rows = await db.fetch(query, webhook_id, limit, offset)
        return [self._row_to_log(row) for row in rows]

    async def count_logs_by_webhook(
        self,
        db: asyncpg.Connection,
        webhook_id: int
    ) -> int:
        """Count logs for specific webhook"""
        query = "SELECT COUNT(*) FROM webhook_logs WHERE webhook_id = $1"
        return await db.fetchval(query, webhook_id)

    # Helper methods
    def _row_to_webhook(self, row: asyncpg.Record) -> WebhookResponse:
        """Convert database row to WebhookResponse"""
        return WebhookResponse(
            id=row['id'],
            name=row['name'],
            webhook_type=row['webhook_type'],
            endpoint_url=row['endpoint_url'],
            http_method=row['http_method'],
            headers=json.loads(row['headers']) if isinstance(row['headers'], str) else row['headers'],
            auth_type=row['auth_type'],
            auth_config=json.loads(row['auth_config']) if isinstance(row['auth_config'], str) else row['auth_config'],
            payload_template=json.loads(row['payload_template']) if row['payload_template'] and isinstance(row['payload_template'], str) else row['payload_template'],
            retry_config=json.loads(row['retry_config']) if isinstance(row['retry_config'], str) else row['retry_config'],
            timeout_seconds=row['timeout_seconds'],
            events=row['events'],
            is_active=row['is_active'],
            last_triggered_at=row['last_triggered_at'],
            last_status=row['last_status'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            created_by=row['created_by']
        )

    def _row_to_log(self, row: asyncpg.Record) -> WebhookLogResponse:
        """Convert database row to WebhookLogResponse"""
        return WebhookLogResponse(
            id=row['id'],
            webhook_id=row['webhook_id'],
            event_type=row['event_type'],
            request_payload=json.loads(row['request_payload']) if isinstance(row['request_payload'], str) else row['request_payload'],
            response_status=row['response_status'],
            response_body=row['response_body'],
            duration_ms=row['duration_ms'],
            error_message=row['error_message'],
            created_at=row['created_at']
        )
