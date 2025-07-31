import time
from datetime import datetime
from threading import RLock

from source.exchange_logging.utils import get_exchange_logger
from source.exchange_logging.context import transaction_scope
from source.utils.timezone_utils import ensure_timezone_aware, to_iso_string


class EnhancedVolumeTracker:
    """Enhanced volume tracking with time-based calculations and comprehensive logging"""

    def __init__(self):
        self._lock = RLock()
        self.minute_volume = {}  # Dict[datetime, int]
        self.current_bin_volume = 0
        self.total_volume = 0
        self.logger = get_exchange_logger(__name__)

        self.logger.info("EnhancedVolumeTracker initialized")

    def update_volume(self, timestamp: datetime, volume: int):
        """Update volume for a specific timestamp with detailed logging"""

        # Ensure timezone-aware timestamp
        timestamp = ensure_timezone_aware(timestamp)

        with transaction_scope("update_volume", self.logger,
                               timestamp=to_iso_string(timestamp), volume=volume) as txn_id:

            update_start_time = time.time()

            with self._lock:
                try:
                    # Store previous state for logging
                    prev_current_volume = self.current_bin_volume
                    prev_total_volume = self.total_volume

                    # Update current state
                    self.current_bin_volume = volume
                    self.total_volume += volume

                    # Update minute-level tracking
                    key = timestamp.replace(second=0, microsecond=0)
                    prev_minute_volume = self.minute_volume.get(key, 0)

                    if key not in self.minute_volume:
                        self.minute_volume[key] = 0
                    self.minute_volume[key] += volume

                    # Log the volume update
                    self.logger.log_state_change(
                        object_name="VolumeTracker",
                        old_state={
                            "current_bin_volume": prev_current_volume,
                            "total_volume": prev_total_volume,
                            "minute_volume": prev_minute_volume
                        },
                        new_state={
                            "current_bin_volume": self.current_bin_volume,
                            "total_volume": self.total_volume,
                            "minute_volume": self.minute_volume[key]
                        },
                        change_reason=f"volume_update[{txn_id}]"
                    )

                    # Log significant volume changes
                    if volume > 10000:  # Log large volume updates
                        self.logger.log_business_event("LARGE_VOLUME_UPDATE", {
                            "timestamp": to_iso_string(timestamp),
                            "volume": volume,
                            "minute_key": to_iso_string(key),
                            "cumulative_minute_volume": self.minute_volume[key],
                            "total_session_volume": self.total_volume,
                            "transaction_id": txn_id
                        })

                    # Performance logging
                    update_duration = (time.time() - update_start_time) * 1000

                    self.logger.log_performance(
                        operation="volume_update",
                        duration_ms=update_duration,
                        additional_metrics={
                            "volume": volume,
                            "minute_entries": len(self.minute_volume),
                            "total_volume": self.total_volume
                        }
                    )

                    self.logger.debug(f"Volume updated: {prev_current_volume} -> {volume} at {timestamp}")

                except Exception as e:
                    self.logger.error(f"Error updating volume for {timestamp}: {e}")
                    raise ValueError(f"Error updating volume: {e}")

    def get_current_minute_volume(self) -> int:
        """Get total volume for current minute with logging"""
        with self._lock:
            volume = self.current_bin_volume
            self.logger.debug(f"Retrieved current minute volume: {volume}")
            return volume

    def get_minute_volume(self, timestamp: datetime) -> int:
        """Get volume for a specific minute"""
        with self._lock:
            # Ensure timezone-aware timestamp
            timestamp = ensure_timezone_aware(timestamp)
            key = timestamp.replace(second=0, microsecond=0)
            volume = self.minute_volume.get(key, 0)
            self.logger.debug(f"Retrieved volume for {key}: {volume}")
            return volume

    def get_available_volume(self, start_time: datetime, end_time: datetime) -> float:
        """Calculate available volume based on remaining time in bin with detailed logging"""

        # Ensure timezone-aware timestamps
        start_time = ensure_timezone_aware(start_time)
        end_time = ensure_timezone_aware(end_time)

        with transaction_scope("calculate_available_volume", self.logger,
                               start_time=to_iso_string(start_time),
                               end_time=to_iso_string(end_time)) as txn_id:

            calculation_start_time = time.time()

            with self._lock:
                try:
                    # Convert to same timezone for calculation
                    if start_time.tzinfo != end_time.tzinfo:
                        start_time = start_time.astimezone(end_time.tzinfo)

                    # INCLUDE START_TIME, DO NOT INCLUDE END_TIME
                    remaining_seconds = int((end_time - start_time).total_seconds())
                    remaining_seconds = min(60, max(0, remaining_seconds))

                    # Calculate proportional volume available
                    proportion = remaining_seconds / 60.0
                    available = self.current_bin_volume * proportion

                    self.logger.log_calculation(
                        description="Available volume calculation",
                        inputs={
                            "start_time": to_iso_string(start_time),
                            "end_time": to_iso_string(end_time),
                            "current_bin_volume": self.current_bin_volume,
                            "remaining_seconds": remaining_seconds
                        },
                        result=available,
                        details={
                            "time_proportion": proportion,
                            "total_seconds_in_minute": 60,
                            "transaction_id": txn_id
                        }
                    )

                    # Log warning for unusual time calculations
                    if remaining_seconds <= 0:
                        self.logger.warning(f"Zero or negative remaining seconds: {remaining_seconds}")
                    elif remaining_seconds > 60:
                        self.logger.warning(f"Remaining seconds exceeds 60: {remaining_seconds}")

                    # Performance logging
                    calculation_duration = (time.time() - calculation_start_time) * 1000

                    self.logger.log_performance(
                        operation="available_volume_calculation",
                        duration_ms=calculation_duration,
                        additional_metrics={
                            "remaining_seconds": remaining_seconds,
                            "proportion": f"{proportion:.4f}",
                            "available_volume": f"{available:.2f}"
                        }
                    )

                    self.logger.debug(
                        f"Available volume: {available:.2f} = {self.current_bin_volume} * ({remaining_seconds}/60)")

                    return available

                except Exception as e:
                    self.logger.error(f"Error calculating available volume: {e}")
                    raise ValueError(f"Error calculating available volume: {e}")

    def get_total_volume(self) -> int:
        """Get total cumulative volume"""
        with self._lock:
            self.logger.debug(f"Retrieved total session volume: {self.total_volume}")
            return self.total_volume

    def get_volume_stats(self) -> dict:
        """Get comprehensive volume statistics"""
        with self._lock:
            stats = {
                "current_bin_volume": self.current_bin_volume,
                "total_session_volume": self.total_volume,
                "minute_entries": len(self.minute_volume),
                "avg_minute_volume": self.total_volume / max(1, len(self.minute_volume)),
                "max_minute_volume": max(self.minute_volume.values()) if self.minute_volume else 0,
                "min_minute_volume": min(self.minute_volume.values()) if self.minute_volume else 0
            }

            self.logger.debug(f"Volume statistics: {stats}")
            return stats

    def reset_volume(self):
        """Reset all volume tracking"""
        with self._lock:
            old_stats = self.get_volume_stats()

            self.minute_volume.clear()
            self.current_bin_volume = 0
            self.total_volume = 0

            self.logger.log_business_event("VOLUME_TRACKER_RESET", {
                "previous_stats": old_stats,
                "reset_timestamp": to_iso_string(datetime.now())
            })

    def log_volume_summary(self):
        """Log a summary of current volume state"""
        with self._lock:
            stats = self.get_volume_stats()

            self.logger.info("=== Volume Tracker Summary ===")
            self.logger.info(f"Current bin volume: {stats['current_bin_volume']:,}")
            self.logger.info(f"Total session volume: {stats['total_session_volume']:,}")
            self.logger.info(f"Minutes tracked: {stats['minute_entries']}")
            self.logger.info(f"Average per minute: {stats['avg_minute_volume']:,.0f}")
            self.logger.info(f"Max minute volume: {stats['max_minute_volume']:,}")
            self.logger.info(f"Min minute volume: {stats['min_minute_volume']:,}")

            if self.minute_volume:
                self.logger.info("Recent minute volumes:")
                # Show last 5 minutes
                recent_minutes = sorted(self.minute_volume.keys())[-5:]
                for minute in recent_minutes:
                    volume = self.minute_volume[minute]
                    self.logger.info(f"  {minute.strftime('%H:%M')}: {volume:,}")