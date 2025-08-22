# source/orchestration/app_state/market_timing.py
"""
Market Timing - Handles market bins and timing
"""
import logging
from threading import RLock
from datetime import datetime, timedelta
from typing import Optional
import traceback
import threading

from source.utils.timezone_utils import ensure_utc


class MarketTiming:
    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Market timing state
        self.base_date: Optional[datetime] = None
        self.market_open: Optional[datetime] = None
        self.market_close: Optional[datetime] = None

        # Bin tracking
        self._current_bin = None
        self._next_bin = None
        self._current_timestamp = None
        self._next_timestamp = None

        # THIS WAS MISSING - moved from SnapshotState
        self._received_first_market_data = False

    def set_base_date(self, date: datetime):
        with self._lock:
            self.base_date = ensure_utc(date)

    def get_current_bin(self) -> Optional[str]:
        with self._lock:
            result = self._current_bin
            self.logger.debug(f"🕐 GET_CURRENT_BIN called: {result}")
            return result

    def get_next_bin(self) -> Optional[str]:
        with self._lock:
            result = self._next_bin
            self.logger.debug(f"🕐 GET_NEXT_BIN called: {result}")
            return result

    def get_current_timestamp(self) -> Optional[datetime]:
        with self._lock:
            return self._current_timestamp

    def get_next_timestamp(self) -> Optional[datetime]:
        with self._lock:
            return self._next_timestamp

    def advance_bin(self):
        with self._lock:
            # ✅ ADD DETAILED LOGGING
            self.logger.info("🚨 ADVANCE_BIN CALLED! 🚨")
            self.logger.info(f"🧵 Thread: {threading.current_thread().name}")
            self.logger.info(f"🔍 Call stack:")

            # Log the call stack to see who called this
            stack = traceback.extract_stack()
            for i, frame in enumerate(stack[-6:-1]):  # Show last 5 frames
                self.logger.info(f"   [{i}] {frame.filename}:{frame.lineno} in {frame.name}")
                self.logger.info(f"       {frame.line}")

            old_current = self._current_bin
            old_next = self._next_bin
            old_current_timestamp = self._current_timestamp
            old_next_timestamp = self._next_timestamp

            if self._next_bin and self._next_timestamp:
                self._current_timestamp = self._next_timestamp
                self._next_timestamp = self._next_timestamp + timedelta(minutes=1)

                self._current_bin = self._current_timestamp.strftime('%H%M')
                self._next_bin = self._next_timestamp.strftime('%H%M')

            # Enhanced logging
            self.logger.info(f"⏰ BIN_ADVANCED:")
            self.logger.info(f"   Current Bin: {old_current} -> {self._current_bin}")
            self.logger.info(f"   Next Bin: {old_next} -> {self._next_bin}")
            self.logger.info(f"   Current Time: {old_current_timestamp} -> {self._current_timestamp}")
            self.logger.info(f"   Next Time: {old_next_timestamp} -> {self._next_timestamp}")
            self.logger.info("🚨 ADVANCE_BIN COMPLETE! 🚨")

    """
    def advance_bin(self):
        with self._lock:
            old_current = self._current_bin
            old_next = self._next_bin

            if self._next_bin and self._next_timestamp:
                self._current_timestamp = self._next_timestamp
                self._next_timestamp = self._next_timestamp + timedelta(minutes=1)

                self._current_bin = self._current_timestamp.strftime('%H%M')
                self._next_bin = self._next_timestamp.strftime('%H%M')

            # Bin advancement logging
            self.logger.info(f"⏰ BIN_ADVANCED:")
            self.logger.info(f"   Current: {old_current} -> {self._current_bin}")
            self.logger.info(f"   Next: {old_next} -> {self._next_bin}")
            self.logger.info(f"   Current Time (UTC): {self._current_timestamp}")
            self.logger.info(f"   Next Time (UTC): {self._next_timestamp}")
    """

    def mark_first_market_data_received(self, timestamp: datetime):
        with self._lock:
            timestamp = ensure_utc(timestamp)
            self._received_first_market_data = True
            self.initialize_bin(timestamp)

    def initialize_bin(self, timestamp: datetime):
        with self._lock:
            timestamp = ensure_utc(timestamp)

            # Set current bin to starting state
            self._current_bin = "0000"
            self._current_timestamp = ensure_utc(self.market_open) if self.market_open else None

            # Set next bin to the timestamp we just received
            self._next_bin = timestamp.strftime('%H%M')
            self._next_timestamp = timestamp

    def is_market_open(self, check_time: Optional[datetime] = None) -> bool:
        with self._lock:
            time_to_check = check_time or self.get_current_timestamp()
            if time_to_check is None or not self.market_open or not self.market_close:
                return False

            time_to_check = ensure_utc(time_to_check)
            market_open = ensure_utc(self.market_open)
            market_close = ensure_utc(self.market_close)

            return market_open.time() <= time_to_check.time() < market_close.time()

    def get_status_summary(self):
        with self._lock:
            return {
                "base_date": self.base_date.isoformat() if self.base_date else None,
                "current_timestamp": self._current_timestamp.isoformat() if self._current_timestamp else None,
                "next_timestamp": self._next_timestamp.isoformat() if self._next_timestamp else None,
                "current_bin": self._current_bin,
                "next_bin": self._next_bin,
                "received_first_market_data": self._received_first_market_data,
                "market_open": self.market_open.isoformat() if self.market_open else None,
                "market_close": self.market_close.isoformat() if self.market_close else None
            }
