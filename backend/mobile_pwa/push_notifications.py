"""
Push Notification Fallback System
Service Worker push notifications for mobile devices

PHASE4-PWA-004 (f9n8): Push Notification Fallback
- Service Worker push notifications for heartbeat when app backgrounded
- Wake device for critical coordinator messages
- FCM for Android, APNs for iOS
- Use WebSocket patterns for message format
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class PushPlatform(str, Enum):
    """Push notification platforms."""
    FCM = "fcm"           # Firebase Cloud Messaging (Android)
    APNS = "apns"         # Apple Push Notification service (iOS)
    WEB_PUSH = "web_push"  # Web Push API (browsers)


class PushPriority(str, Enum):
    """Push notification priority levels."""
    HIGH = "high"         # Immediate delivery, can wake device
    NORMAL = "normal"     # Battery-friendly delivery


class MessageType(str, Enum):
    """Types of push messages."""
    HEARTBEAT_WAKE = "heartbeat_wake"    # Wake device for heartbeat
    TASK_ASSIGNED = "task_assigned"       # New task assigned
    TASK_COMPLETED = "task_completed"     # Task result ready
    MESH_UPDATE = "mesh_update"           # Mesh status changed
    ALERT = "alert"                       # Critical alert


@dataclass
class PushMessage:
    """
    Push notification message.

    PHASE4-PWA-004: Message format compatible with WebSocket patterns.
    """
    message_id: str
    message_type: MessageType
    title: str
    body: str
    priority: PushPriority = PushPriority.NORMAL
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = 3600  # Time to live

    def to_fcm_format(self) -> dict[str, Any]:
        """
        Convert to FCM message format.

        PHASE4-PWA-004: FCM format for Android.
        """
        message = {
            "message": {
                "notification": {
                    "title": self.title,
                    "body": self.body,
                },
                "data": {
                    "message_id": self.message_id,
                    "message_type": self.message_type.value,
                    "timestamp": self.timestamp.isoformat(),
                    **{k: str(v) for k, v in self.data.items()},
                },
                "android": {
                    "priority": self.priority.value,
                    "ttl": f"{self.ttl_seconds}s",
                },
            }
        }

        return message

    def to_apns_format(self) -> dict[str, Any]:
        """
        Convert to APNs message format.

        PHASE4-PWA-004: APNs format for iOS.
        """
        payload = {
            "aps": {
                "alert": {
                    "title": self.title,
                    "body": self.body,
                },
                "sound": "default",
                "content-available": 1,  # Enable background processing
            },
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat(),
            **self.data,
        }

        return payload

    def to_web_push_format(self) -> dict[str, Any]:
        """
        Convert to Web Push API format.

        PHASE4-PWA-004: Web Push for browsers.
        """
        return {
            "notification": {
                "title": self.title,
                "body": self.body,
                "icon": "/icons/fogburst-192.png",
                "badge": "/icons/fogburst-badge.png",
                "data": {
                    "message_id": self.message_id,
                    "message_type": self.message_type.value,
                    "timestamp": self.timestamp.isoformat(),
                    **self.data,
                },
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to generic dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass
class DevicePushRegistration:
    """Push registration for a device."""
    device_id: str
    platform: PushPlatform
    push_token: str
    registered_at: datetime
    last_used: Optional[datetime] = None
    is_valid: bool = True
    error_count: int = 0


@dataclass
class ServiceWorkerConfig:
    """
    Service Worker configuration for PWA.

    PHASE4-PWA-004: Config for Service Worker push handling.
    """
    # Push endpoints
    push_public_key: str = ""
    push_private_key: str = ""

    # Service Worker settings
    sw_scope: str = "/"
    sw_path: str = "/service-worker.js"

    # Notification settings
    default_icon: str = "/icons/fogburst-192.png"
    default_badge: str = "/icons/fogburst-badge.png"
    notification_click_url: str = "/"

    # Background sync
    enable_background_sync: bool = True
    sync_tag: str = "fogburst-heartbeat"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for SW initialization."""
        return {
            "pushPublicKey": self.push_public_key,
            "swScope": self.sw_scope,
            "swPath": self.sw_path,
            "defaultIcon": self.default_icon,
            "defaultBadge": self.default_badge,
            "notificationClickUrl": self.notification_click_url,
            "enableBackgroundSync": self.enable_background_sync,
            "syncTag": self.sync_tag,
        }


class PushNotificationService:
    """
    Service for sending push notifications to mobile devices.

    PHASE4-PWA-004: Push notification fallback system.

    Supports:
    - FCM (Firebase Cloud Messaging) for Android
    - APNs (Apple Push Notification service) for iOS
    - Web Push API for browsers
    """

    def __init__(
        self,
        fcm_server_key: Optional[str] = None,
        apns_key_id: Optional[str] = None,
        apns_team_id: Optional[str] = None,
        apns_key_path: Optional[str] = None,
        web_push_private_key: Optional[str] = None,
        web_push_public_key: Optional[str] = None,
    ):
        """
        Initialize push notification service.

        Args:
            fcm_server_key: FCM server key for Android
            apns_key_id: APNs key ID for iOS
            apns_team_id: Apple team ID for iOS
            apns_key_path: Path to APNs .p8 key file
            web_push_private_key: VAPID private key
            web_push_public_key: VAPID public key
        """
        self.fcm_server_key = fcm_server_key
        self.apns_key_id = apns_key_id
        self.apns_team_id = apns_team_id
        self.apns_key_path = apns_key_path
        self.web_push_private_key = web_push_private_key
        self.web_push_public_key = web_push_public_key

        self._registrations: dict[str, DevicePushRegistration] = {}
        self._message_history: list[PushMessage] = []

        # Statistics
        self._stats = {
            "total_sent": 0,
            "fcm_sent": 0,
            "apns_sent": 0,
            "web_push_sent": 0,
            "failed": 0,
        }

        logger.info(
            f"PushNotificationService initialized: "
            f"fcm={'enabled' if fcm_server_key else 'disabled'}, "
            f"apns={'enabled' if apns_key_id else 'disabled'}, "
            f"web_push={'enabled' if web_push_private_key else 'disabled'}"
        )

    def register_device(
        self,
        device_id: str,
        platform: PushPlatform,
        push_token: str,
    ) -> bool:
        """
        Register a device for push notifications.

        Args:
            device_id: Device identifier
            platform: Push platform
            push_token: Platform-specific push token

        Returns:
            True if registered
        """
        registration = DevicePushRegistration(
            device_id=device_id,
            platform=platform,
            push_token=push_token,
            registered_at=datetime.now(UTC),
        )

        self._registrations[device_id] = registration
        logger.info(f"Device registered for push: {device_id} ({platform.value})")

        return True

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device from push notifications."""
        if device_id in self._registrations:
            del self._registrations[device_id]
            logger.info(f"Device unregistered from push: {device_id}")
            return True
        return False

    async def send_to_device(
        self,
        device_id: str,
        message: PushMessage,
    ) -> bool:
        """
        Send push notification to a specific device.

        PHASE4-PWA-004: Main send entry point.

        Args:
            device_id: Target device
            message: Message to send

        Returns:
            True if sent successfully
        """
        registration = self._registrations.get(device_id)
        if not registration:
            logger.warning(f"No push registration for device: {device_id}")
            return False

        if not registration.is_valid:
            logger.warning(f"Push registration invalid for device: {device_id}")
            return False

        try:
            if registration.platform == PushPlatform.FCM:
                success = await self._send_fcm(registration.push_token, message)
            elif registration.platform == PushPlatform.APNS:
                success = await self._send_apns(registration.push_token, message)
            elif registration.platform == PushPlatform.WEB_PUSH:
                success = await self._send_web_push(registration.push_token, message)
            else:
                logger.error(f"Unknown platform: {registration.platform}")
                return False

            if success:
                registration.last_used = datetime.now(UTC)
                registration.error_count = 0
                self._stats["total_sent"] += 1
                self._message_history.append(message)
            else:
                registration.error_count += 1
                if registration.error_count >= 5:
                    registration.is_valid = False
                self._stats["failed"] += 1

            return success

        except Exception as e:
            logger.error(f"Push send error: {e}")
            registration.error_count += 1
            self._stats["failed"] += 1
            return False

    async def _send_fcm(self, token: str, message: PushMessage) -> bool:
        """
        Send via Firebase Cloud Messaging.

        PHASE4-PWA-004: FCM for Android.
        """
        if not self.fcm_server_key:
            logger.warning("FCM server key not configured")
            return False

        try:
            import aiohttp

            url = "https://fcm.googleapis.com/fcm/send"
            headers = {
                "Authorization": f"key={self.fcm_server_key}",
                "Content-Type": "application/json",
            }

            payload = message.to_fcm_format()
            payload["message"]["token"] = token

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        self._stats["fcm_sent"] += 1
                        logger.debug(f"FCM sent: {message.message_id}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"FCM error: {response.status} - {error}")
                        return False

        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return False

    async def _send_apns(self, token: str, message: PushMessage) -> bool:
        """
        Send via Apple Push Notification service.

        PHASE4-PWA-004: APNs for iOS.
        """
        if not self.apns_key_id or not self.apns_team_id:
            logger.warning("APNs not configured")
            return False

        try:
            import aiohttp
            import jwt
            import time

            # Generate APNs JWT token
            headers = {
                "alg": "ES256",
                "kid": self.apns_key_id,
            }

            payload = {
                "iss": self.apns_team_id,
                "iat": int(time.time()),
            }

            # Load private key if path provided
            if self.apns_key_path:
                with open(self.apns_key_path, "rb") as f:
                    key = f.read()
            else:
                logger.error("APNs key path not provided")
                return False

            auth_token = jwt.encode(payload, key, algorithm="ES256", headers=headers)

            # Send to APNs
            url = f"https://api.push.apple.com/3/device/{token}"
            headers = {
                "authorization": f"bearer {auth_token}",
                "apns-push-type": "alert",
                "apns-priority": "10" if message.priority == PushPriority.HIGH else "5",
                "apns-topic": "com.fogburst.app",  # Your app bundle ID
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=message.to_apns_format(),
                    timeout=30
                ) as response:
                    if response.status == 200:
                        self._stats["apns_sent"] += 1
                        logger.debug(f"APNs sent: {message.message_id}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"APNs error: {response.status} - {error}")
                        return False

        except ImportError:
            logger.error("PyJWT not installed for APNs")
            return False
        except Exception as e:
            logger.error(f"APNs send error: {e}")
            return False

    async def _send_web_push(self, subscription_json: str, message: PushMessage) -> bool:
        """
        Send via Web Push API.

        PHASE4-PWA-004: Web Push for browsers.
        """
        if not self.web_push_private_key or not self.web_push_public_key:
            logger.warning("Web Push not configured")
            return False

        try:
            from pywebpush import webpush, WebPushException

            subscription = json.loads(subscription_json)

            webpush(
                subscription_info=subscription,
                data=json.dumps(message.to_web_push_format()),
                vapid_private_key=self.web_push_private_key,
                vapid_claims={"sub": "mailto:admin@fogburst.com"},
            )

            self._stats["web_push_sent"] += 1
            logger.debug(f"Web Push sent: {message.message_id}")
            return True

        except ImportError:
            logger.error("pywebpush not installed for Web Push")
            return False
        except Exception as e:
            logger.error(f"Web Push send error: {e}")
            return False

    async def send_heartbeat_wake(self, device_id: str) -> bool:
        """
        Send heartbeat wake notification.

        PHASE4-PWA-004: Wake device for heartbeat.
        """
        message = PushMessage(
            message_id=f"hb-wake-{device_id}-{int(datetime.now(UTC).timestamp())}",
            message_type=MessageType.HEARTBEAT_WAKE,
            title="Fogburst",
            body="Heartbeat required",
            priority=PushPriority.HIGH,
            data={"action": "send_heartbeat"},
        )

        return await self.send_to_device(device_id, message)

    async def send_task_notification(
        self,
        device_id: str,
        command_id: str,
        task_type: str,
        assigned: bool = True,
    ) -> bool:
        """
        Send task assignment/completion notification.

        Args:
            device_id: Target device
            command_id: Task command ID
            task_type: Type of task
            assigned: True for assigned, False for completed
        """
        message_type = MessageType.TASK_ASSIGNED if assigned else MessageType.TASK_COMPLETED
        title = "Task Assigned" if assigned else "Task Completed"
        body = f"{task_type} task {command_id[:8]}"

        message = PushMessage(
            message_id=f"task-{command_id}",
            message_type=message_type,
            title=title,
            body=body,
            priority=PushPriority.NORMAL,
            data={"command_id": command_id, "task_type": task_type},
        )

        return await self.send_to_device(device_id, message)

    def get_service_worker_config(self) -> ServiceWorkerConfig:
        """Get Service Worker configuration for PWA."""
        return ServiceWorkerConfig(
            push_public_key=self.web_push_public_key or "",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_sent": self._stats["total_sent"],
            "fcm_sent": self._stats["fcm_sent"],
            "apns_sent": self._stats["apns_sent"],
            "web_push_sent": self._stats["web_push_sent"],
            "failed": self._stats["failed"],
            "registered_devices": len(self._registrations),
            "message_history_size": len(self._message_history),
        }

    def is_device_registered(self, device_id: str) -> bool:
        """Check if device is registered for push."""
        return device_id in self._registrations

    def get_device_platform(self, device_id: str) -> Optional[PushPlatform]:
        """Get platform for a registered device."""
        reg = self._registrations.get(device_id)
        return reg.platform if reg else None
