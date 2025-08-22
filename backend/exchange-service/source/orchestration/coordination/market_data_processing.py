# source/orchestration/coordination/market_data_processing.py
from datetime import datetime
from typing import List, Optional
import logging

from source.utils.timezone_utils import ensure_utc

def process_market_data_with_replay_awareness(equity_bars: List, fx: Optional[List],
                                              unified_replay_manager, last_snap_time: datetime,
                                              live_data_queue: List) -> bool:
    """Process market data with unified replay mode awareness"""
    logger = logging.getLogger("MarketDataProcessor")

    try:
        if not equity_bars:
            return True

        # Get incoming timestamp
        incoming_timestamp = datetime.fromisoformat(equity_bars[0].timestamp)
        incoming_timestamp = ensure_utc(incoming_timestamp)

        # Check if we need replay mode
        if unified_replay_manager and not unified_replay_manager.is_in_replay_mode():
            gap_info = unified_replay_manager.detect_gap(last_snap_time, incoming_timestamp)
            if gap_info:
                logger.info("🎬 Initiating unified replay mode due to gap detection")
                unified_replay_manager.enter_replay_mode(
                    last_snap_time=last_snap_time,
                    target_live_time=incoming_timestamp
                )
                # Queue this data for after replay
                live_data_queue.append((incoming_timestamp, equity_bars, fx))
                return True

        # If in replay mode, queue for later
        if unified_replay_manager and unified_replay_manager.is_in_replay_mode():
            live_data_queue.append((incoming_timestamp, equity_bars, fx))
            return True

        # Normal processing
        return process_normal_market_data(equity_bars, fx, unified_replay_manager)

    except Exception as e:
        logger.error(f"❌ Error in replay-aware market data processing: {e}")
        return False


def process_normal_market_data(equity_bars: List, fx: Optional[List], unified_replay_manager) -> bool:
    """Process market data in normal mode"""
    try:
        if unified_replay_manager and equity_bars:
            timestamp = datetime.fromisoformat(equity_bars[0].timestamp)
            unified_replay_manager.process_backfill_data([(timestamp, equity_bars, fx)])
            return True
        return False
    except Exception as e:
        logging.getLogger("MarketDataProcessor").error(f"❌ Error in normal market data processing: {e}")
        return False


def process_queued_live_data(live_data_queue: List, unified_replay_manager):
    """Process queued live data after replay is complete"""
    logger = logging.getLogger("MarketDataProcessor")

    try:
        logger.info(f"🎬 Processing {len(live_data_queue)} queued live data items")

        for timestamp, equity_bars, fx in live_data_queue:
            logger.info(f"📊 Processing queued data for {timestamp}")
            process_normal_market_data(equity_bars, fx, unified_replay_manager)

        live_data_queue.clear()
        logger.info("✅ All queued live data processed")

    except Exception as e:
        logger.error(f"❌ Error processing queued live data: {e}")