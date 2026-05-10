"""
Push Notification Sending Service - Firebase Cloud Messaging
=============================================================

Provides a unified async interface for sending push notifications via FCM.
Used by NotificationEventHandler.

This service:
- Sends push notifications via Firebase Cloud Messaging
- Supports both single device and topic-based notifications
- Fetches user device tokens from database

@module communications/services/push_sending_service
@version 1.0.0
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from loguru import logger

try:
    import firebase_admin
    from firebase_admin import messaging, credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("firebase-admin not installed, push notifications disabled")


@dataclass
class PushSendResult:
    """Result of a push notification send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    failed_tokens: Optional[List[str]] = None


class PushSendingService:
    """
    Centralized service for sending push notifications via Firebase.

    Usage:
        service = PushSendingService()
        result = await service.send_to_user(
            db=db_connection,
            user_id="user-uuid",
            title="Payment Confirmed",
            body="Your payment of 5000 XAF has been received",
            data={"payment_id": "..."}
        )
    """

    def __init__(self):
        self._initialized = False
        self._initialize_firebase()

    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK if not already done."""
        if not FIREBASE_AVAILABLE:
            logger.warning("[PUSH] Firebase Admin SDK not available")
            return

        try:
            # Check if already initialized (by storage_service or other module)
            if firebase_admin._apps:
                self._initialized = True
                logger.info("[PUSH] Firebase already initialized, reusing existing app")
                return

            # Initialize Firebase
            from app.config import get_settings
            settings = get_settings()

            # Try to get service account from config
            service_account_json = None
            if settings.FIREBASE_ADMIN_KEY_DEV:
                service_account_json = settings.FIREBASE_ADMIN_KEY_DEV
            elif settings.FIREBASE_ADMIN_KEY_PRO:
                service_account_json = settings.FIREBASE_ADMIN_KEY_PRO
            elif settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV:
                service_account_json = settings.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV

            if service_account_json:
                service_account_info = json.loads(service_account_json)
                cred = credentials.Certificate(service_account_info)
            else:
                # Use default credentials (for Cloud Run)
                cred = credentials.ApplicationDefault()

            firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("[PUSH] Firebase Admin SDK initialized for push notifications")

        except Exception as e:
            logger.error(f"[PUSH] Failed to initialize Firebase: {e}")
            self._initialized = False

    async def send_to_device(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> PushSendResult:
        """
        Send push notification to a single device.

        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL for rich notifications

        Returns:
            PushSendResult with success status
        """
        if not FIREBASE_AVAILABLE or not self._initialized:
            return PushSendResult(
                success=False,
                error="Firebase not initialized"
            )

        try:
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )

            # Build message
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        click_action="FLUTTER_NOTIFICATION_CLICK"
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound="default",
                            badge=1
                        )
                    )
                )
            )

            # Send in thread pool (FCM SDK is sync)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send,
                message
            )

            logger.info(f"[PUSH] Sent to device, message_id={response}")
            return PushSendResult(
                success=True,
                message_id=response
            )

        except messaging.UnregisteredError:
            logger.warning(f"[PUSH] Device token unregistered: {token[:20]}...")
            return PushSendResult(
                success=False,
                error="Device token unregistered",
                failed_tokens=[token]
            )

        except Exception as e:
            logger.error(f"[PUSH] Send error: {e}")
            return PushSendResult(
                success=False,
                error=str(e)
            )

    async def send_to_devices(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> PushSendResult:
        """
        Send push notification to multiple devices.

        Args:
            tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Additional data payload

        Returns:
            PushSendResult with success status and any failed tokens
        """
        if not FIREBASE_AVAILABLE or not self._initialized:
            return PushSendResult(
                success=False,
                error="Firebase not initialized"
            )

        if not tokens:
            return PushSendResult(
                success=False,
                error="No tokens provided"
            )

        try:
            notification = messaging.Notification(
                title=title,
                body=body
            )

            message = messaging.MulticastMessage(
                notification=notification,
                data=data or {},
                tokens=tokens,
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default")
                    )
                )
            )

            # Send in thread pool
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send_each_for_multicast,
                message
            )

            # Collect failed tokens
            failed_tokens = []
            for idx, send_response in enumerate(response.responses):
                if not send_response.success:
                    failed_tokens.append(tokens[idx])
                    if send_response.exception:
                        logger.warning(
                            f"[PUSH] Failed for token {idx}: {send_response.exception}"
                        )

            success_count = response.success_count
            failure_count = response.failure_count

            logger.info(
                f"[PUSH] Multicast: {success_count} success, {failure_count} failed"
            )

            return PushSendResult(
                success=success_count > 0,
                message_id=f"multicast:{success_count}/{len(tokens)}",
                failed_tokens=failed_tokens if failed_tokens else None,
                error=f"{failure_count} failed" if failure_count > 0 else None
            )

        except Exception as e:
            logger.error(f"[PUSH] Multicast error: {e}")
            return PushSendResult(
                success=False,
                error=str(e)
            )

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> PushSendResult:
        """
        Send push notification to a topic.

        Args:
            topic: FCM topic name
            title: Notification title
            body: Notification body
            data: Additional data payload

        Returns:
            PushSendResult with success status
        """
        if not FIREBASE_AVAILABLE or not self._initialized:
            return PushSendResult(
                success=False,
                error="Firebase not initialized"
            )

        try:
            notification = messaging.Notification(
                title=title,
                body=body
            )

            message = messaging.Message(
                notification=notification,
                data=data or {},
                topic=topic
            )

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send,
                message
            )

            logger.info(f"[PUSH] Sent to topic '{topic}', message_id={response}")
            return PushSendResult(
                success=True,
                message_id=response
            )

        except Exception as e:
            logger.error(f"[PUSH] Topic send error: {e}")
            return PushSendResult(
                success=False,
                error=str(e)
            )

    async def send_to_user(
        self,
        db,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> PushSendResult:
        """
        Send push notification to a user (all their registered devices).

        Args:
            db: Database connection
            user_id: User UUID
            title: Notification title
            body: Notification body
            data: Additional data payload

        Returns:
            PushSendResult with success status
        """
        try:
            # Get user's device tokens from database
            tokens = await self._get_user_device_tokens(db, user_id)

            if not tokens:
                logger.debug(f"[PUSH] No device tokens for user {user_id}")
                return PushSendResult(
                    success=False,
                    error="No device tokens registered"
                )

            if len(tokens) == 1:
                return await self.send_to_device(
                    token=tokens[0],
                    title=title,
                    body=body,
                    data=data
                )
            else:
                return await self.send_to_devices(
                    tokens=tokens,
                    title=title,
                    body=body,
                    data=data
                )

        except Exception as e:
            logger.error(f"[PUSH] Error sending to user {user_id}: {e}")
            return PushSendResult(
                success=False,
                error=str(e)
            )

    async def _get_user_device_tokens(
        self,
        db,
        user_id: str
    ) -> List[str]:
        """
        Get all active device tokens for a user.

        Args:
            db: Database connection
            user_id: User UUID

        Returns:
            List of FCM device tokens
        """
        try:
            # Query device_push_token from users table (set by mobile app on login)
            query = """
                SELECT device_push_token
                FROM users
                WHERE id = $1 AND device_push_token IS NOT NULL
            """
            row = await db.fetchrow(query, user_id)

            if row and row["device_push_token"]:
                return [row["device_push_token"]]

            return []

        except Exception as e:
            logger.warning(f"[PUSH] Error fetching device tokens: {e}")
            return []

    def is_available(self) -> bool:
        """Check if push notifications are available."""
        return FIREBASE_AVAILABLE and self._initialized


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_push_sending_service: Optional[PushSendingService] = None


def get_push_sending_service() -> PushSendingService:
    """Get singleton PushSendingService instance."""
    global _push_sending_service
    if _push_sending_service is None:
        _push_sending_service = PushSendingService()
    return _push_sending_service
