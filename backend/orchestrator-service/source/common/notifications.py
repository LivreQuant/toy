# source/common/notifications.py
import logging
from typing import Dict, List, Any
from datetime import datetime
from enum import Enum
import asyncio
import json

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"


class NotificationManager:
    """Manages notifications and alerts"""

    def __init__(self):
        self.notification_channels = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.SMS: self._send_sms_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.DASHBOARD: self._send_dashboard_notification
        }

        # Notification configuration
        self.notification_config = {
            "email": {
                "enabled": True,
                "smtp_server": "smtp.company.com",
                "from_address": "trading-alerts@company.com"
            },
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/..."
            },
            "sms": {
                "enabled": False,  # Disabled for demo
                "provider": "twilio"
            }
        }

        # Subscription rules
        self.notification_rules = {
            "SOD_SUCCESS": [NotificationChannel.SLACK, NotificationChannel.DASHBOARD],
            "SOD_FAILED": [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.SMS],
            "EOD_SUCCESS": [NotificationChannel.SLACK, NotificationChannel.DASHBOARD],
            "EOD_FAILED": [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.SMS],
            "SYSTEM_ERROR": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
            "RISK_LIMIT_BREACH": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
            "SETTLEMENT_FAILURE": [NotificationChannel.EMAIL, NotificationChannel.SLACK]
        }

    async def send_notification(self, event_type: str, message: str,
                                context: Dict[str, Any] = None,
                                level: NotificationLevel = NotificationLevel.INFO) -> Dict[str, Any]:
        """Send notification based on event type"""
        logger.info(f"📧 Sending notification: {event_type} - {message}")

        results = {
            "event_type": event_type,
            "message": message,
            "level": level.value,
            "channels_attempted": 0,
            "channels_succeeded": 0,
            "channels_failed": 0,
            "channel_results": {}
        }

        # Get channels for this event type
        channels = self.notification_rules.get(event_type, [NotificationChannel.DASHBOARD])

        # Send to each channel
        for channel in channels:
            results["channels_attempted"] += 1

            try:
                if channel in self.notification_channels:
                    channel_result = await self.notification_channels[channel](
                        event_type, message, context, level
                    )

                    if channel_result.get('success', False):
                        results["channels_succeeded"] += 1
                    else:
                        results["channels_failed"] += 1

                    results["channel_results"][channel.value] = channel_result

            except Exception as e:
                logger.error(f"❌ Failed to send notification via {channel.value}: {e}")
                results["channels_failed"] += 1
                results["channel_results"][channel.value] = {
                    "success": False,
                    "error": str(e)
                }

        return results

    async def send_critical_alert(self, event_type: str, message: str,
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send critical alert to all channels"""
        return await self.send_notification(
            event_type, message, context, NotificationLevel.CRITICAL
        )

    async def _send_email_notification(self, event_type: str, message: str,
                                       context: Dict[str, Any],
                                       level: NotificationLevel) -> Dict[str, Any]:
        """Send email notification"""
        if not self.notification_config["email"]["enabled"]:
            return {"success": False, "error": "Email notifications disabled"}

        # Simulate email sending
        await asyncio.sleep(0.1)

        # Get recipients based on event type and level
        recipients = self._get_email_recipients(event_type, level)

        email_subject = f"[{level.value.upper()}] Trading System Alert: {event_type}"
        email_body = self._format_email_body(event_type, message, context, level)

        # Simulate successful email send
        logger.info(f"📧 Email sent: {email_subject} to {len(recipients)} recipients")

        return {
            "success": True,
            "recipients_count": len(recipients),
            "subject": email_subject
        }

    async def _send_slack_notification(self, event_type: str, message: str,
                                       context: Dict[str, Any],
                                       level: NotificationLevel) -> Dict[str, Any]:
        """Send Slack notification"""
        if not self.notification_config["slack"]["enabled"]:
            return {"success": False, "error": "Slack notifications disabled"}

        # Simulate Slack API call
        await asyncio.sleep(0.05)

        # Format Slack message
        slack_message = self._format_slack_message(event_type, message, context, level)

        # Simulate successful Slack send
        logger.info(f"💬 Slack message sent: {event_type}")

        return {
            "success": True,
            "channel": "#trading-alerts",
            "message_length": len(slack_message)
        }

    async def _send_sms_notification(self, event_type: str, message: str,
                                     context: Dict[str, Any],
                                     level: NotificationLevel) -> Dict[str, Any]:
        """Send SMS notification"""
        if not self.notification_config["sms"]["enabled"]:
            return {"success": False, "error": "SMS notifications disabled"}

        # SMS only for critical alerts
        if level != NotificationLevel.CRITICAL:
            return {"success": False, "error": "SMS only for critical alerts"}

        # Simulate SMS sending
        await asyncio.sleep(0.2)

        recipients = self._get_sms_recipients(event_type, level)
        sms_message = f"TRADING ALERT: {event_type} - {message[:100]}..."

        logger.info(f"📱 SMS sent: {event_type} to {len(recipients)} recipients")

        return {
            "success": True,
            "recipients_count": len(recipients),
            "message_length": len(sms_message)
        }

    async def _send_webhook_notification(self, event_type: str, message: str,
                                         context: Dict[str, Any],
                                         level: NotificationLevel) -> Dict[str, Any]:
        """Send webhook notification"""
        # Simulate webhook call
        await asyncio.sleep(0.1)

        webhook_payload = {
            "event_type": event_type,
            "message": message,
            "level": level.value,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context
        }

        logger.info(f"🔗 Webhook sent: {event_type}")

        return {
            "success": True,
            "payload_size": len(json.dumps(webhook_payload))
        }

    async def _send_dashboard_notification(self, event_type: str, message: str,
                                           context: Dict[str, Any],
                                           level: NotificationLevel) -> Dict[str, Any]:
        """Send dashboard notification"""
        # Simulate dashboard update
        await asyncio.sleep(0.01)

        logger.info(f"📊 Dashboard updated: {event_type}")

        return {
            "success": True,
            "dashboard_widget": "system_alerts",
            "level": level.value
        }

    def _get_email_recipients(self, event_type: str, level: NotificationLevel) -> List[str]:
        """Get email recipients based on event type and level"""
        recipients = []

        # Base recipients
        if level == NotificationLevel.CRITICAL:
            recipients.extend([
                "trading-team@company.com",
                "risk-team@company.com",
                "operations@company.com"
            ])
        elif level == NotificationLevel.ERROR:
            recipients.extend([
                "trading-team@company.com",
                "operations@company.com"
            ])
        else:
            recipients.extend([
                "trading-team@company.com"
            ])

        # Event-specific recipients
        if "RISK" in event_type:
            recipients.append("risk-team@company.com")
        elif "SETTLEMENT" in event_type:
            recipients.append("settlements@company.com")

        return list(set(recipients))  # Remove duplicates

    def _get_sms_recipients(self, event_type: str, level: NotificationLevel) -> List[str]:
        """Get SMS recipients for critical alerts"""
        return [
            "+1-555-0101",  # Trading Manager
            "+1-555-0102",  # Risk Manager
            "+1-555-0103"  # Operations Manager
        ]

    def _format_email_body(self, event_type: str, message: str,
                           context: Dict[str, Any], level: NotificationLevel) -> str:
        """Format email message body"""
        lines = [
            f"Trading System Alert: {event_type}",
            f"Level: {level.value.upper()}",
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Message:",
            message,
        ]

        if context:
            lines.extend([
                "",
                "Additional Details:",
                json.dumps(context, indent=2, default=str)
            ])

        lines.extend([
            "",
            "This is an automated notification from the Trading Orchestrator System."
        ])

        return "\n".join(lines)

    def _format_slack_message(self, event_type: str, message: str,
                              context: Dict[str, Any], level: NotificationLevel) -> str:
        """Format Slack message"""
        level_emoji = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }

        emoji = level_emoji.get(level, "📢")

        slack_message = f"{emoji} *{event_type}* ({level.value.upper()})\n{message}"

        if context:
            # Add key context items
            context_items = []
            for key, value in context.items():
                if key in ['execution_time', 'error', 'failed_tasks', 'duration_seconds']:
                    context_items.append(f"• {key}: {value}")

            if context_items:
                slack_message += "\n\n" + "\n".join(context_items)

        return slack_message
