"""
User Profile API for TaxasGE Backend
Self-service user profile management endpoints
"""

import asyncpg
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from loguru import logger

from app.modules.users.models import (
    UserUpdate, UserResponse, PasswordChange, UserActivity, AccountDeleteRequest
)
from app.modules.users.repositories import UserRepository
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.auth.services.password_service import PasswordService
from app.database.connection import get_database, db_manager

# Create router
router = APIRouter(tags=["Users - Profile"])
security = HTTPBearer()

# Initialize repository
user_repository = UserRepository()


@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current user profile

    Returns authenticated user's profile information
    """
    try:
        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            action="view_profile",
            resource="user_profile",
            timestamp=datetime.now(timezone.utc)
        )
        await user_repository.log_user_activity(activity)

        return current_user
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user profile"
        )


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update current user profile

    **VALIDATION:**
    - Email format: EmailStr (RFC 5322)
    - Email uniqueness: 409 Conflict if duplicate
    - Phone E.164 format: +240XXXXXXXXX
    - Users cannot update their own status
    """
    try:
        # Convert update model to dict, excluding None values
        update_data = {
            k: v for k, v in user_update.dict(exclude_unset=True).items()
            if v is not None
        }

        # Email uniqueness check
        if "email" in update_data and update_data["email"] != current_user.email:
            existing_user = await user_repository.find_by_email(update_data["email"])
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already in use"
                )

        # Users cannot update their own status (admin only)
        if "status" in update_data:
            del update_data["status"]

        if not update_data:
            return current_user

        updated_user = await user_repository.update(current_user.id, update_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            action="update_profile",
            resource="user_profile",
            metadata={"updated_fields": list(update_data.keys())},
            timestamp=datetime.now(timezone.utc)
        )
        await user_repository.log_user_activity(activity)

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user profile"
        )


@router.post("/profile/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_change: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Change user password

    **VALIDATION:**
    - Old password must match current password
    - New password must be different from old password
    - New password must meet strength requirements (8+ chars)

    **NOTIFICATIONS:**
    - Sends email notification to user (ONLY if password change succeeds)
    - Sends SMS notification if user has phone number configured
    """
    import uuid

    try:
        # Convert user_id to UUID for database operations
        try:
            user_uuid = uuid.UUID(str(current_user.id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        # Use database connection manager for all DB operations
        async with db_manager.get_connection() as db:
            # Get hashed password from database
            query = "SELECT password_hash FROM users WHERE id = $1"
            result = await db.fetchrow(query, user_uuid)

            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Verify old password
            password_service = PasswordService()
            if not password_service.verify_password(
                password_change.old_password,
                result["password_hash"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )

            # Hash new password
            new_password_hash = password_service.hash_password(password_change.new_password)

            # Update password in database with RETURNING to confirm update
            update_query = """
                UPDATE users
                SET password_hash = $1, updated_at = NOW()
                WHERE id = $2
                RETURNING id
            """
            update_result = await db.fetchrow(update_query, new_password_hash, user_uuid)

            # Verify the update was successful
            if not update_result:
                logger.error(f"Password update failed for user {current_user.id} - no rows affected")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update password"
                )

            logger.info(f"Password successfully updated for user {current_user.id}")

            # Log activity (non-blocking - errors won't affect response)
            try:
                activity = UserActivity(
                    user_id=current_user.id,
                    action="change_password",
                    resource="user_password",
                    timestamp=datetime.now(timezone.utc)
                )
                await user_repository.log_user_activity(activity)
            except Exception as log_error:
                logger.warning(f"Failed to log password change activity: {log_error}")

        # =================================================================
        # SEND SECURITY NOTIFICATIONS via EventBus (SMS + Email)
        # IMPORTANT: Only send AFTER password change is confirmed
        # Uses fire-and-forget pattern (non-blocking)
        # =================================================================
        try:
            from app.core.events import EventBus, EventType

            now = datetime.now(timezone.utc)

            # Publish password changed event - notification handler will send email + SMS
            EventBus.publish_nowait(EventType.USER_PASSWORD_CHANGED, {
                "user_id": str(current_user.id),
                "user_email": current_user.email,
                "user_phone": current_user.phone_number,
                "user_name": f"{current_user.first_name} {current_user.last_name}",
                "preferred_language": current_user.preferred_language or "es",
                "date": now.strftime("%d/%m/%Y"),
                "time": now.strftime("%H:%M"),
            })
            logger.info(f"USER_PASSWORD_CHANGED event published for user {current_user.id}")

        except Exception as event_error:
            # Log but don't fail - password change was successful
            logger.error(f"Failed to publish password change event: {event_error}")

        return {
            "message": "Password changed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error changing password"
        )


class DeviceTokenRequest(BaseModel):
    """Register a device push token for mobile notifications."""
    device_token: str = Field(..., min_length=10, max_length=500)
    platform: str = Field(..., pattern=r'^(android|ios)$')
    app: str = Field('inspector', pattern=r'^(citizen|inspector)$')


@router.post("/profile/device-token", status_code=status.HTTP_200_OK)
async def register_device_token(
    data: DeviceTokenRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """
    Register a device push token (Expo/FCM) for the authenticated user.
    Called on login from mobile apps. One token per user (last device wins).

    PRIOR BUG (fixed): the previous implementation called
    `db = await get_database()`, but `get_database` is an async generator
    (yields the connection from `db_manager.get_connection()`). Awaiting it
    returned the generator object itself, so `db.execute(...)` raised
    AttributeError on every call and the route 500'd silently. The mobile
    boot path hits this once per cold start (cf. the Sentry POST 500 trace
    captured at 2026-04-28T10:00:32 with body_size=198, response_size=87).
    Using `Depends(get_database)` for proper dependency injection fixes it.
    """
    try:
        await db.execute(
            """
            UPDATE users
            SET device_push_token = $1,
                device_push_platform = $2,
                device_push_app = $3,
                device_push_updated_at = NOW()
            WHERE id = $4
            """,
            data.device_token,
            data.platform,
            data.app,
            current_user.id,
        )
        return {"status": "ok", "token_registered": True}

    except Exception as e:
        logger.error(f"Error registering device token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error registering device token",
        )


@router.post("/profile/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Upload user avatar

    **VALIDATION:**
    - File must be an image (jpeg, jpg, png, gif)
    - Max file size: 5MB
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file.content_type} not allowed. Allowed types: jpeg, jpg, png, gif"
            )

        # Read file content
        content = await file.read()

        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of 5MB"
            )

        # TODO: Upload to Firebase Storage
        # For now, we'll just return a placeholder URL
        avatar_url = f"https://storage.googleapis.com/taxasge-avatars/{current_user.id}/{file.filename}"

        # Update user avatar URL
        updated_user = await user_repository.update(
            current_user.id,
            {"avatar_url": avatar_url}
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            action="upload_avatar",
            resource="user_avatar",
            metadata={"filename": file.filename, "content_type": file.content_type},
            timestamp=datetime.now(timezone.utc)
        )
        await user_repository.log_user_activity(activity)

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading avatar"
        )


@router.delete("/profile/avatar", response_model=UserResponse)
async def delete_avatar(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete user avatar

    Removes the user's profile picture
    """
    try:
        # TODO: Delete from Firebase Storage
        # For now, we'll just remove the URL

        # Update user avatar URL to None
        updated_user = await user_repository.update(
            current_user.id,
            {"avatar_url": None}
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            action="delete_avatar",
            resource="user_avatar",
            timestamp=datetime.now(timezone.utc)
        )
        await user_repository.log_user_activity(activity)

        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting avatar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting avatar"
        )


@router.get("/profile/export", status_code=status.HTTP_200_OK)
async def export_user_data(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Export the authenticated user's data as a JSON document — RGPD art. 20
    (right to data portability).

    V1: synchronous aggregation, capped to a 90-day window for the high-cardinality
    tables (payments, service_requests, audit_logs) so the response stays small
    enough to ship without an async job pipeline.

    Returns: a JSON body with `Content-Disposition: attachment` so mobile clients
    can write it straight to a file and let the user share it.
    """
    import uuid

    from fastapi.responses import JSONResponse

    try:
        try:
            user_uuid = uuid.UUID(str(current_user.id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

        async with db_manager.get_connection() as db:
            profile = await db.fetchrow(
                """
                SELECT id, email, first_name, last_name, full_name, phone_number,
                       document_type, document_number, role, status, preferred_language,
                       email_notifications, push_notifications, sms_notifications,
                       email_verified, phone_verified, address, city, avatar_url,
                       two_factor_enabled, last_login, created_at, updated_at
                FROM users
                WHERE id = $1
                """,
                user_uuid,
            )
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            payments = await db.fetch(
                """
                SELECT id, base_amount, penalties, interest, currency, payment_type,
                       payment_method, status, bank_reference, bank_transaction_id,
                       paid_at, created_at, updated_at
                FROM payments
                WHERE user_id = $1
                  AND created_at >= NOW() - INTERVAL '90 days'
                ORDER BY created_at DESC
                LIMIT 1000
                """,
                user_uuid,
            )
            # Total count for truncation signaling — only counts when we hit the
            # limit so we don't pay the COUNT cost for the common case.
            payments_total = (
                await db.fetchval(
                    """
                    SELECT COUNT(*) FROM payments
                    WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '90 days'
                    """,
                    user_uuid,
                )
                if len(payments) >= 1000
                else len(payments)
            )

            service_requests = await db.fetch(
                """
                SELECT id, reference, workflow_code, status::text AS status,
                       payment_status, paid_at, created_at, updated_at
                FROM service_requests
                WHERE user_id = $1
                  AND created_at >= NOW() - INTERVAL '90 days'
                ORDER BY created_at DESC
                LIMIT 1000
                """,
                user_uuid,
            )
            service_requests_total = (
                await db.fetchval(
                    """
                    SELECT COUNT(*) FROM service_requests
                    WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '90 days'
                    """,
                    user_uuid,
                )
                if len(service_requests) >= 1000
                else len(service_requests)
            )

        # Pydantic / asyncpg records: serialise the values explicitly so JSON
        # encoding can't trip on UUID / Decimal / datetime types.
        def _to_dict(row):
            return {k: (str(v) if v is not None else None) for k, v in dict(row).items()}

        payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_for_user_id": str(user_uuid),
            "rgpd_basis": "Article 20 — right to data portability",
            "window_days": 90,
            "profile": _to_dict(profile),
            "payments": [_to_dict(p) for p in payments],
            "service_requests": [_to_dict(r) for r in service_requests],
            "counts": {
                "payments_returned": len(payments),
                "payments_total_in_window": int(payments_total or len(payments)),
                "payments_truncated": payments_total is not None
                and int(payments_total) > len(payments),
                "service_requests_returned": len(service_requests),
                "service_requests_total_in_window": int(
                    service_requests_total or len(service_requests)
                ),
                "service_requests_truncated": service_requests_total is not None
                and int(service_requests_total) > len(service_requests),
            },
        }

        # Activity log — the user is auditing themselves, but we still record
        # the request so a future incident response can see who pulled what.
        try:
            activity = UserActivity(
                user_id=current_user.id,
                action="export_data",
                resource="user_profile",
                timestamp=datetime.now(timezone.utc),
            )
            await user_repository.log_user_activity(activity)
        except Exception as log_error:
            logger.warning(f"Failed to log export activity: {log_error}")

        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": f'attachment; filename="facil-export-{user_uuid}.json"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting data for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting data",
        )


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: AccountDeleteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Delete (soft-delete) the authenticated user's account — RGPD art. 17.

    The account is not erased synchronously. Instead:

    1. The supplied password is verified via bcrypt — wrong password ⇒ 400.
    2. The Pydantic validator on `confirmation` enforces the exact literal
       string `"DELETE"` so a misclick or replay cannot trigger this route.
    3. `users.deleted_at` is set to NOW() (migration 313 introduced the column).
       The email is suffixed with `.deleted-<uuid>` so the address can be reused
       for a fresh registration without colliding on the unique index.
    4. All refresh_tokens for the user are revoked, and active sessions are
       marked `revoked` — the next API call from any device will fail.
    5. An audit-log entry records the deletion (entity_type=`user`,
       action=`soft_delete`).

    A separate cron purges `deleted_at < NOW() - 30 days` rows, giving the user
    a 30-day grace period in case of mistake (regulatory best practice).

    Returns: 204 No Content on success.
    """
    import uuid

    try:
        try:
            user_uuid = uuid.UUID(str(current_user.id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

        async with db_manager.get_connection() as db:
            row = await db.fetchrow(
                "SELECT password_hash, deleted_at, email FROM users WHERE id = $1",
                user_uuid,
            )
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            if row["deleted_at"] is not None:
                # Idempotent — already deleted, but signal it for the client.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Account already scheduled for deletion",
                )

            password_service = PasswordService()
            if not password_service.verify_password(body.password, row["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect",
                )

            # All state changes in a single transaction so a failure leaves
            # neither a half-deleted account nor zombie sessions.
            async with db.transaction():
                deleted_email = f"{row['email']}.deleted-{user_uuid}"
                await db.execute(
                    """
                    UPDATE users
                    SET deleted_at = NOW(),
                        email = $1,
                        status = 'deactivated',
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    deleted_email,
                    user_uuid,
                )
                await db.execute(
                    """
                    UPDATE refresh_tokens
                    SET is_revoked = TRUE, revoked_at = NOW(), updated_at = NOW()
                    WHERE user_id = $1 AND is_revoked = FALSE
                    """,
                    user_uuid,
                )
                await db.execute(
                    """
                    UPDATE sessions
                    SET status = 'revoked'
                    WHERE user_id = $1 AND status = 'active'
                    """,
                    user_uuid,
                )
                await db.execute(
                    """
                    INSERT INTO audit_logs (
                        user_id, entity_type, entity_id, action, new_values
                    ) VALUES ($1, 'user', $2, 'soft_delete', $3::jsonb)
                    """,
                    user_uuid,
                    str(user_uuid),
                    '{"reason": "user_requested_account_deletion"}',
                )

        logger.info(
            f"User {user_uuid} soft-deleted (email rotated, tokens+sessions revoked)"
        )
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting account",
        )
