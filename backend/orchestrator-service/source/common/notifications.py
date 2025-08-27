# source/common/notifications.py
import logging
from typing import Dict, Any, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SimpleNotification:
    def __init__(self, level: NotificationLevel, title: str, message: str, data: Dict[str, Any] = None):
        self.level = level
        self.title = title
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.utcnow()


class SimpleNotificationManager:
    """Simple notification manager - just logs for now"""

    def __init__(self):
        self.notifications: List[SimpleNotification] = []
        self.max_notifications = 1000  # Keep last 1000

    def send_notification(self, level: NotificationLevel, title: str, message: str, data: Dict[str, Any] = None):
        """Send a notification"""
        notification = SimpleNotification(level, title, message, data)

        # Add to history
        self.notifications.append(notification)
        if len(self.notifications) > self.max_notifications:
            self.notifications.pop(0)

        # Log the notification
        emoji = self._get_emoji(level)
        logger_method = self._get_logger_method(level)
        logger_method(f"{emoji} {title}: {message}")

        # In the future, could send to Slack, email, etc.

    def _get_emoji(self, level: NotificationLevel) -> str:
        return {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }.get(level, "📢")

    def _get_logger_method(self, level: NotificationLevel):
        return {
            NotificationLevel.INFO: logger.info,
            NotificationLevel.WARNING: logger.warning,
            NotificationLevel.ERROR: logger.error,
            NotificationLevel.CRITICAL: logger.critical
        }.get(level, logger.info)

    def get_recent_notifications(self, count: int = 50) -> List[SimpleNotification]:
        """Get recent notifications"""
        return self.notifications[-count:]

    def clear_notifications(self):
        """Clear notification history"""
        self.notifications.clear()
        logger.info("🧹 Cleared notification history")


# Global notification manager
notification_manager = SimpleNotificationManager()


# Convenience functions
def send_info(title: str, message: str, data: Dict[str, Any] = None):
    notification_manager.send_notification(NotificationLevel.INFO, title, message, data)


def send_warning(title: str, message: str, data: Dict[str, Any] = None):
    notification_manager.send_notification(NotificationLevel.WARNING, title, message, data)


def send_error(title: str, message: str, data: Dict[str, Any] = None):
    notification_manager.send_notification(NotificationLevel.ERROR, title, message, data)


def send_critical(title: str, message: str, data: Dict[str, Any] = None):
    notification_manager.send_notification(NotificationLevel.CRITICAL, title, message, data)