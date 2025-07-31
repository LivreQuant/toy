# source/orchestration/replay/gap_detector.py
"""
Gap detection functionality for market data timestamps
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from source.utils.timezone_utils import ensure_timezone_aware


class GapDetector:
    """Handles detection of gaps in market data timestamps"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def detect_gap(self, last_market_time: datetime, incoming_market_time: datetime) -> Optional[
        Tuple[datetime, datetime]]:
        """
        Detect if there's a gap between MARKET timestamps only.
        Returns (gap_start, gap_end) if there are missing bins, None otherwise.
        Normal 1-minute progression (60 seconds) should NOT trigger replay mode.
        """
        try:
            last_market_time = ensure_timezone_aware(last_market_time)
            incoming_market_time = ensure_timezone_aware(incoming_market_time)

            # Calculate time difference between MARKET timestamps
            time_diff = incoming_market_time - last_market_time

            self.logger.info(f"🔍 MARKET DATA GAP DETECTION:")
            self.logger.info(f"   Last Market Time: {last_market_time}")
            self.logger.info(f"   Incoming Market Time: {incoming_market_time}")
            self.logger.info(f"   Market Time Diff: {time_diff}")
            self.logger.info(f"   Time diff seconds: {time_diff.total_seconds()}")

            # Check for normal 1-minute progression first
            if time_diff == timedelta(minutes=1):
                self.logger.info(f"✅ NORMAL 1-MINUTE PROGRESSION: Exactly 60 seconds - no gap")
                return None

            # Only consider it a gap if > 90 seconds (missing at least one bin)
            if time_diff > timedelta(seconds=90):
                gap_start = last_market_time + timedelta(minutes=1)
                gap_end = incoming_market_time - timedelta(minutes=1)

                # Validate that there are actually missing minutes
                if gap_end >= gap_start:
                    self.logger.warning(f"🚨 MARKET GAP DETECTED:")
                    self.logger.warning(f"   Gap Start: {gap_start}")
                    self.logger.warning(f"   Gap End: {gap_end}")
                    self.logger.warning(f"   Gap Duration: {gap_end - gap_start}")
                    self.logger.warning(f"   Missing bins: {int((gap_end - gap_start).total_seconds() / 60) + 1}")

                    result = (gap_start, gap_end)
                    self.logger.info(f"🔍 RETURNING GAP INFO: {result}")
                    return result
                else:
                    self.logger.info(f"✅ NO ACTUAL MISSING BINS: gap_end ({gap_end}) < gap_start ({gap_start})")
                    return None
            else:
                self.logger.info(
                    f"✅ NORMAL MARKET PROGRESSION: Time difference ({time_diff.total_seconds():.1f}s) ≤ 90s threshold")
                return None

        except Exception as e:
            self.logger.error(f"❌ Error in gap detection: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return None
