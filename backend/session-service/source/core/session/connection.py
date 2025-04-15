"""
Connection utilities for session management.
Simplified for singleton mode.
"""
import logging
import time
from typing import Dict, Any, Tuple
from opentelemetry import trace

from source.models.session import ConnectionQuality

from source.utils.metrics import track_connection_quality, track_client_reconnection
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('connection')


class Connection:
    """Handles connection-related operations for sessions"""

    def __init__(self, session_manager):
        """
        Initialize with reference to session manager

        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("connection_utils")

    async def update_connection_quality(
            self,
            session_id: str,
            user_id: str,
            metrics: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """
        Update connection quality metrics based on client report.
        """
        with optional_trace_span(self.tracer, "update_connection_quality") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("metrics.latency_ms", metrics.get('latency_ms', -1))
            span.set_attribute("metrics.missed_heartbeats", metrics.get('missed_heartbeats', -1))
            span.set_attribute("metrics.connection_type", metrics.get('connection_type', 'unknown'))

            try:
                # Determine quality based on metrics
                latency_ms = metrics.get('latency_ms', 0)
                missed_heartbeats = metrics.get('missed_heartbeats', 0)
                quality = ConnectionQuality.GOOD  # Default
                reconnect_recommended = False

                if missed_heartbeats >= 3:
                    quality = ConnectionQuality.POOR
                    reconnect_recommended = True
                elif missed_heartbeats > 0 or latency_ms > 500:
                    quality = ConnectionQuality.DEGRADED
                    reconnect_recommended = False

                span.set_attribute("calculated_quality", quality.value)
                span.set_attribute("reconnect_recommended", reconnect_recommended)

                # Update database details
                update_success = await self.manager.update_session_details(session_id, {
                    'connection_quality': quality.value,
                    'heartbeat_latency': latency_ms,
                    'missed_heartbeats': missed_heartbeats,
                    'last_quality_update': time.time()
                })

                if not update_success:
                    logger.warning(f"Failed to update session details for connection quality on {session_id}")
                    span.set_attribute("db_update_failed", True)

                # Track connection quality metric
                track_connection_quality(quality.value)

                return quality.value, reconnect_recommended
            except Exception as e:
                logger.error(f"Error updating connection quality for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return "unknown", False

    async def reconnect_session(
            self,
            session_id: str,
            user_id: str,
            device_id: str,
            attempt: int = 1
    ) -> Tuple[Dict[str, Any], str]:
        """
        Handle session reconnection attempt.
        """
        with optional_trace_span(self.tracer, "reconnect_session") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("device_id", device_id)
            span.set_attribute("reconnect_attempt", attempt)

            # Get session data
            session = await self.manager.get_session(session_id)
            if not session:
                error_msg = "Session not found"
                span.set_attribute("error", error_msg)
                return {}, error_msg

            # Update reconnection counter in details
            details = session.details
            reconnect_count = getattr(details, 'reconnect_count', 0) + 1

            await self.manager.update_session_details(session_id, {
                'reconnect_count': reconnect_count,
                'last_reconnect': time.time()
            })

            # Log and track reconnection metrics
            logger.info(f"Session {session_id} reconnected successfully (Attempt: {attempt}, Count: {reconnect_count})")
            track_client_reconnection(min(5, reconnect_count))

            # Convert session to dict for response
            session_data = {
                'session_id': session.session_id,
                'user_id': session.user_id,
                'status': session.status.value,
                'created_at': session.created_at,
                'expires_at': session.expires_at,
                'simulator_status': getattr(details, 'simulator_status', 'NONE'),
                'connection_quality': getattr(details, 'connection_quality', 'GOOD'),
                'device_id': device_id
            }

            return session_data, ""
