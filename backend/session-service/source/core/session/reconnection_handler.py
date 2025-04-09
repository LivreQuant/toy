"""
Connection quality assessment and management.
Handles client connection quality updates and metrics.
"""
import logging
import time
from typing import Dict, Any, Tuple
from opentelemetry import trace

from source.utils.metrics import track_connection_quality
from source.utils.tracing import optional_trace_span
from source.models.session import ConnectionQuality

logger = logging.getLogger('connection_quality')


class ReconnectionHandler:
    """Handles connection quality assessment and updates"""

    def __init__(self, session_manager):
        """
        Initialize with reference to session manager
        
        Args:
            session_manager: Parent SessionManager instance
        """
        self.manager = session_manager
        self.tracer = trace.get_tracer("connection_quality")

    async def update_connection_quality(
            self,
            session_id: str,
            token: str,
            metrics: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """
        Update connection quality metrics based on client report.

        Args:
            session_id: The session ID
            token: Authentication token
            metrics: Connection metrics dict (latency_ms, missed_heartbeats, connection_type)

        Returns:
            Tuple of (quality_string, reconnect_recommended_bool)
        """
        with optional_trace_span(self.tracer, "update_connection_quality") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("metrics.latency_ms", metrics.get('latency_ms', -1))
            span.set_attribute("metrics.missed_heartbeats", metrics.get('missed_heartbeats', -1))
            span.set_attribute("metrics.connection_type", metrics.get('connection_type', 'unknown'))

            # 1. Validate session
            user_id = await self.manager.session_ops.validate_session(session_id, token)  # Validation updates activity
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                span.set_attribute("error", "Invalid session or token")
                return "unknown", False

            try:
                # 2. Determine quality based on metrics (logic moved from Session model)
                latency_ms = metrics.get('latency_ms', 0)
                missed_heartbeats = metrics.get('missed_heartbeats', 0)
                quality = ConnectionQuality.GOOD  # Default
                reconnect_recommended = False

                if missed_heartbeats >= 3:
                    quality = ConnectionQuality.POOR
                    reconnect_recommended = True
                elif missed_heartbeats > 0 or latency_ms > 500:
                    quality = ConnectionQuality.DEGRADED
                    # Reconnect not usually recommended just for degraded
                    reconnect_recommended = False
                # else: quality remains GOOD

                span.set_attribute("calculated_quality", quality.value)
                span.set_attribute("reconnect_recommended", reconnect_recommended)

                # 3. Update database metadata
                update_success = await self.manager.db_manager.update_session_metadata(session_id, {
                    'connection_quality': quality.value,  # Store enum value as string
                    'heartbeat_latency': latency_ms,
                    'missed_heartbeats': missed_heartbeats,
                    'last_quality_update': time.time()  # Track update time
                })

                if not update_success:
                    logger.warning(f"Failed to update session metadata for connection quality on {session_id}")
                    span.set_attribute("db_update_failed", True)
                    # Don't fail the call, but log it

                # 4. Track connection quality metric
                track_connection_quality(quality.value, self.manager.pod_name)

                return quality.value, reconnect_recommended
            except Exception as e:
                logger.error(f"Error updating connection quality for session {session_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return "unknown", False
