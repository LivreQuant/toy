# source/orchestration/coordination/gap_detection.py
from datetime import datetime, timedelta
import logging


def detect_gap(last_time: datetime, incoming_time: datetime, replay_manager=None) -> tuple:
    """Check for gaps between market timestamps with comprehensive logging"""
    # Use the GapDetection logger that's configured in exchange_logging
    logger = logging.getLogger("GapDetection")

    try:
        from source.utils.timezone_utils import ensure_utc
        from datetime import timedelta

        last_time = ensure_utc(last_time)
        incoming_time = ensure_utc(incoming_time)

        # COMPREHENSIVE LOGGING - this will now write to gap_detection log
        logger.info("=" * 80)
        logger.info("🔍 MARKET DATA GAP ANALYSIS STARTING")
        logger.info("=" * 80)
        logger.info(f"📅 Last market time (UTC): {last_time}")
        logger.info(f"📅 Incoming market time (UTC): {incoming_time}")

        # Calculate time difference
        time_diff = incoming_time - last_time
        expected_diff = timedelta(minutes=1)

        logger.info(f"⏱️  Time difference: {time_diff}")
        logger.info(f"⏱️  Expected difference: {expected_diff}")
        logger.info(f"⏱️  Difference in seconds: {time_diff.total_seconds()}")
        logger.info(f"⏱️  Expected seconds: {expected_diff.total_seconds()}")

        # Check if we have a gap (more than 1 minute difference)
        if abs(time_diff.total_seconds() - expected_diff.total_seconds()) > 30:  # 30 second tolerance
            logger.warning("🚨 POTENTIAL GAP DETECTED!")
            logger.warning(f"🚨 Gap size: {time_diff}")
            logger.warning(f"🚨 Gap exceeds normal 1-minute progression by: {time_diff - expected_diff}")

            if replay_manager:
                logger.info("🎬 Checking replay manager for gap handling...")
                gap_info = replay_manager.detect_gap(last_time, incoming_time)

                if gap_info:
                    gap_start, gap_end = gap_info
                    gap_duration = gap_end - gap_start

                    logger.warning("📊 CONFIRMED MARKET DATA GAP:")
                    logger.warning(f"   Gap start: {gap_start} UTC")
                    logger.warning(f"   Gap end: {gap_end} UTC")
                    logger.warning(f"   Gap duration: {gap_duration}")
                    logger.warning(f"   Gap duration seconds: {gap_duration.total_seconds()}")

                    if gap_duration <= timedelta(hours=2):
                        logger.info("✅ Gap is reasonable for backfilling (≤ 2 hours)")
                        logger.info("🎬 Recommending replay mode activation")
                        logger.info("=" * 80)
                        return gap_info
                    else:
                        logger.warning("⚠️ Gap too large for backfilling (> 2 hours)")
                        logger.warning("⚠️ Will skip to current data instead")
                        logger.info("=" * 80)
                        return None
                else:
                    logger.info("ℹ️ Replay manager determined no actionable gap")
                    logger.info("=" * 80)
                    return None
            else:
                logger.warning("⚠️ No replay manager available for gap handling")
                logger.info("=" * 80)
                return None
        else:
            logger.info("✅ NO GAP DETECTED")
            logger.info("✅ Market data progression is normal (within 30-second tolerance)")
            logger.info("✅ Continuing with normal processing")
            logger.info("=" * 80)
            return None

    except Exception as e:
        logger.error("❌ ERROR IN GAP DETECTION")
        logger.error(f"❌ Error details: {e}")
        logger.error("❌ Returning None to continue with normal processing")

        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        logger.info("=" * 80)
        return None


def load_missing_data(gap_start: datetime, gap_end: datetime, replay_manager):
    """Load missing market data for the gap period with comprehensive logging"""
    logger = logging.getLogger("GapDetection")

    logger.info("=" * 80)
    logger.info("🔄 LOADING MISSING DATA FOR GAP")
    logger.info("=" * 80)
    logger.info(f"📅 Gap start: {gap_start}")
    logger.info(f"📅 Gap end: {gap_end}")
    logger.info(f"⏱️  Gap duration: {gap_end - gap_start}")

    if not replay_manager:
        logger.error("❌ No replay manager available for data loading")
        logger.info("=" * 80)
        return False

    try:
        logger.info("🎬 Activating replay manager for gap filling")
        success = replay_manager.load_missing_data(gap_start, gap_end)

        if success:
            logger.info("✅ Successfully loaded missing data")
            logger.info("✅ Gap has been filled")
        else:
            logger.warning("⚠️ Failed to load missing data")
            logger.warning("⚠️ Will continue with available data")

        logger.info("=" * 80)
        return success

    except Exception as e:
        logger.error("❌ ERROR LOADING MISSING DATA")
        logger.error(f"❌ Error details: {e}")

        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        logger.info("=" * 80)
        return False