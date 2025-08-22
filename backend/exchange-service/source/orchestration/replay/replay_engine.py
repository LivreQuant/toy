# source/orchestration/replay/replay_engine.py
"""
Core replay mode execution engine
"""

import time
import traceback
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Tuple

from .replay_types import ReplayModeState, ReplayProgress
from .data_loader import DataLoader
from source.utils.timezone_utils import ensure_utc


class ReplayEngine:
    """Handles the core replay mode execution logic"""

    def __init__(self, exchange_group_manager, market_data_processor, polling_interval: int = 5):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager
        self.market_data_processor = market_data_processor
        self.polling_interval = polling_interval

        # Replay mode state management
        self.state = ReplayModeState.LIVE
        self.current_progress: Optional[ReplayProgress] = None
        self.replay_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Track the latest live data timestamp
        self.latest_live_timestamp: Optional[datetime] = None

        # Callbacks for replay mode
        self.on_replay_complete: Optional[Callable] = None
        self.on_replay_progress: Optional[Callable[[ReplayProgress], None]] = None

        # Initialize data loader (environment-aware)
        self.data_loader = DataLoader()

    def enter_replay_mode(self, last_snap_time: datetime, target_live_time: datetime) -> None:
        """Enter replay mode to catch up missing bin snaps"""
        try:
            self.logger.info("")
            self.logger.info("🎬 ENTERING REPLAY MODE!!!")
            self.logger.info("=" * 100)
            self.logger.info(f"📍 Last snap time: {last_snap_time}")
            self.logger.info(f"🎯 Target live time: {target_live_time}")
            self.logger.info(f"🔄 Polling interval: {self.polling_interval} seconds")

            # Store the latest live timestamp
            self.latest_live_timestamp = ensure_utc(target_live_time)
            self.logger.info(f"📡 Stored latest live timestamp: {self.latest_live_timestamp}")

            # Calculate progress information
            total_minutes = int((target_live_time - last_snap_time).total_seconds() / 60)
            self.logger.info(f"⏰ Total minutes to replay: {total_minutes}")

            if total_minutes <= 0:
                self.logger.warning("⚠️ No replay needed - already at target time")
                return

            self.current_progress = ReplayProgress(
                current_time=ensure_utc(last_snap_time),
                target_time=ensure_utc(target_live_time),
                total_minutes=total_minutes,
                completed_minutes=0,
                remaining_minutes=total_minutes,
                state=ReplayModeState.REPLAY_WAITING,
                last_updated=datetime.now()
            )

            # Clear stop event and start replay thread
            self.stop_event.clear()
            self.replay_thread = threading.Thread(
                target=self._replay_thread_wrapper,
                name="ReplayModeThread",
                daemon=True
            )

            self.state = ReplayModeState.REPLAY_WAITING
            self.replay_thread.start()

            self.logger.info("✅ Replay mode thread started")
            self.logger.info(f"🧵 Thread ID: {self.replay_thread.ident}")
            self.logger.info(f"🧵 Thread name: {self.replay_thread.name}")

        except Exception as e:
            self.logger.error(f"❌ Error entering replay mode: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            self.state = ReplayModeState.ERROR
            if self.current_progress:
                self.current_progress.error_message = str(e)

    def _replay_thread_wrapper(self) -> None:
        """Thread wrapper for replay loop with error handling"""
        try:
            print("")
            print("🧵 REPLAY THREAD WRAPPER STARTED!")
            print(f"🧵 Thread ID: {threading.get_ident()}")
            print(f"🧵 Thread name: {threading.current_thread().name}")
            print(f"🧵 Stop event status: {self.stop_event.is_set()}")

            self.logger.info("")
            self.logger.info("🧵 REPLAY THREAD WRAPPER STARTED!")
            self.logger.info(f"🧵 Thread ID: {threading.get_ident()}")
            self.logger.info(f"🧵 Thread name: {threading.current_thread().name}")
            self.logger.info(f"🧵 Stop event status: {self.stop_event.is_set()}")

            print("🧵 CALLING _replay_loop()...")
            self.logger.info("🧵 CALLING _replay_loop()...")

            self._replay_loop()

            print("🧵 _replay_loop() COMPLETED")
            self.logger.info("🧵 _replay_loop() COMPLETED")

        except Exception as e:
            print("")
            print("❌ CRITICAL ERROR IN REPLAY THREAD WRAPPER!")
            print(f"❌ Exception type: {type(e).__name__}")
            print(f"❌ Exception message: {str(e)}")

            self.logger.error("")
            self.logger.error("❌ CRITICAL ERROR IN REPLAY THREAD WRAPPER!")
            self.logger.error(f"❌ Exception type: {type(e).__name__}")
            self.logger.error(f"❌ Exception message: {str(e)}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")

            self.state = ReplayModeState.ERROR
            if self.current_progress:
                self.current_progress.error_message = str(e)

    def _replay_loop(self) -> None:
        """Main replay loop that processes missing bin snaps with graceful live mode transition"""
        try:
            print("")
            print("🎬 STARTING REPLAY LOOP!!!")
            print("=" * 100)

            self.logger.info("")
            self.logger.info("🎬 STARTING REPLAY LOOP!!!")
            self.logger.info("=" * 100)
            self.logger.info("⚠️ REPLAY MODE: Will wait indefinitely for historical bins, briefly for live bins")
            self.logger.info(f"🔄 Polling interval: {self.polling_interval} seconds")

            self.state = ReplayModeState.REPLAY_PROCESSING
            self.logger.info(f"🎬 State changed to: {self.state.value}")
            print(f"🎬 State changed to: {self.state.value}")

            current_time = self.current_progress.current_time
            self.logger.info(f"⏰ Starting from: {current_time}")
            self.logger.info(f"🎯 Target time: {self.latest_live_timestamp}")
            print(f"⏰ Starting from: {current_time}")
            print(f"🎯 Target time: {self.latest_live_timestamp}")

            iteration_count = 0
            while not self.stop_event.is_set():
                iteration_count += 1
                print(f"")
                print(f"🔄 REPLAY LOOP ITERATION #{iteration_count}")
                self.logger.info(f"")
                self.logger.info(f"🔄 REPLAY LOOP ITERATION #{iteration_count}")

                # Get next minute timestamp
                next_minute = current_time + timedelta(minutes=1)
                print(f"🔍 PROCESSING BIN SNAP FOR: {next_minute}")
                self.logger.info(f"🔍 PROCESSING BIN SNAP FOR: {next_minute}")

                # Wait for and process the bin snap
                print(f"⏳ About to call _wait_and_process_bin_snap_pair for {next_minute}")
                self.logger.info(f"⏳ About to call _wait_and_process_bin_snap_pair for {next_minute}")

                process_result = self._wait_and_process_bin_snap_pair(next_minute)

                print(f"✅ _wait_and_process_bin_snap_pair returned: {process_result}")
                self.logger.info(f"✅ _wait_and_process_bin_snap_pair returned: {process_result}")

                if process_result:
                    print(f"✅ Successfully processed bin snap for {next_minute}")
                    self.logger.info(f"✅ Successfully processed bin snap for {next_minute}")

                    # Update current time AFTER successful processing
                    current_time = next_minute

                    # Update progress
                    self.current_progress.completed_minutes += 1
                    self.current_progress.remaining_minutes = max(0,
                                                                  self.current_progress.total_minutes - self.current_progress.completed_minutes)
                    self.current_progress.current_time = current_time
                    self.current_progress.last_updated = datetime.now()

                    # Notify progress callback
                    if self.on_replay_progress:
                        self.logger.info("📞 Calling progress callback")
                        self.on_replay_progress(self.current_progress)

                    progress_msg = f"📊 Replay progress: {self.current_progress.progress_percentage:.1f}% complete"
                    print(progress_msg)
                    self.logger.info(progress_msg)

                else:
                    print(f"❌ Failed to process bin snap for {next_minute}")
                    self.logger.error(f"❌ Failed to process bin snap for {next_minute}")
                    print("🎯 Cannot find next bin snap data - caught up to latest available data")
                    self.logger.info("🎯 Cannot find next bin snap data - caught up to latest available data")
                    print("🎯 TRANSITIONING TO LIVE MODE")
                    self.logger.info("🎯 TRANSITIONING TO LIVE MODE")
                    break

                # Small delay to prevent tight loop
                time.sleep(0.1)

            # Replay complete - transition to live mode
            print("")
            print("🎬 REPLAY LOOP COMPLETED")
            print("=" * 100)
            print("🎯 REPLAY COMPLETE - TRANSITIONING TO LIVE MODE")

            self.logger.info("")
            self.logger.info("🎬 REPLAY LOOP COMPLETED")
            self.logger.info("=" * 100)
            self.logger.info("🎯 REPLAY COMPLETE - TRANSITIONING TO LIVE MODE")

            self.state = ReplayModeState.REPLAY_COMPLETE

            # Update exchange group manager's last snap time to the final time
            self.exchange_group_manager.last_snap_time = ensure_utc(current_time)
            self.logger.info(f"📍 Updated exchange group manager last snap time to: {current_time}")
            print(f"📍 Updated exchange group manager last snap time to: {current_time}")

            # Notify completion
            if self.on_replay_complete:
                self.logger.info("📞 Calling completion callback")
                print("📞 Calling completion callback")
                self.on_replay_complete()

            # Transition to live mode
            print("🎯 SETTING STATE TO LIVE")
            self.logger.info("🎯 SETTING STATE TO LIVE")
            self.state = ReplayModeState.LIVE

            print("✅ REPLAY TO LIVE TRANSITION COMPLETE")
            self.logger.info("✅ REPLAY TO LIVE TRANSITION COMPLETE")

        except Exception as e:
            print("")
            print("❌ CRITICAL ERROR IN REPLAY LOOP!")
            print(f"❌ Exception type: {type(e).__name__}")
            print(f"❌ Exception message: {str(e)}")

            self.logger.error("")
            self.logger.error("❌ CRITICAL ERROR IN REPLAY LOOP!")
            self.logger.error(f"❌ Exception type: {type(e).__name__}")
            self.logger.error(f"❌ Exception message: {str(e)}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")

            self.state = ReplayModeState.ERROR
            if self.current_progress:
                self.current_progress.error_message = str(e)

    def _wait_and_process_bin_snap_pair(self, minute_time: datetime) -> bool:
        """Wait for and process bin snap data - Environment aware using data_loader"""
        try:
            print(f"⏳ ENTERING _wait_and_process_bin_snap_pair for {minute_time}")
            self.logger.info(f"⏳ ENTERING _wait_and_process_bin_snap_pair for {minute_time}")

            # Generate expected timestamp string
            timestamp_str = minute_time.strftime("%Y%m%d_%H%M")
            print(f"📅 Timestamp string: {timestamp_str}")
            self.logger.debug(f"📅 Timestamp string: {timestamp_str}")

            # Determine if this is a historical bin (should wait) or live bin (should exit quickly)
            latest_live_timestamp, latest_live_bin = self.get_latest_live_info()
            is_live_bin = latest_live_bin and timestamp_str >= latest_live_bin

            if is_live_bin:
                print(f"🎯 Bin {timestamp_str} is LIVE DATA - will check briefly then exit to live mode")
                self.logger.info(f"🎯 Bin {timestamp_str} is LIVE DATA - will check briefly then exit to live mode")
                max_checks = 3  # Quick exit for live data
            else:
                print(f"📚 Bin {timestamp_str} is HISTORICAL DATA - will wait indefinitely for data")
                self.logger.info(f"📚 Bin {timestamp_str} is HISTORICAL DATA - will wait indefinitely for data")
                max_checks = None  # Wait indefinitely for historical data

            # Check immediately first using environment-aware data loader
            print(f"🔍 Initial data check using environment-aware data loader...")
            self.logger.info(f"🔍 Initial data check using environment-aware data loader...")

            equity_bars = self.data_loader._load_equity_data_for_timestamp(minute_time)
            fx_rates = self.data_loader._load_fx_data_for_timestamp(minute_time)

            print(f"🔍 Initial data check results:")
            print(f"   🔹 Equity bars: {len(equity_bars) if equity_bars else 0}")
            print(f"   🔹 FX rates: {len(fx_rates) if fx_rates else 0}")
            self.logger.info(
                f"🔍 Initial data check - Equity bars: {len(equity_bars) if equity_bars else 0}, FX rates: {len(fx_rates) if fx_rates else 0}")

            if equity_bars:  # We have equity data (FX is optional)
                print(f"📁 Found bin snap data immediately!")
                self.logger.info(f"📁 Found bin snap data immediately!")
                return self._process_bin_snap_data(equity_bars, fx_rates, minute_time)

            # Wait for data based on whether it's historical or live data
            check_count = 1
            start_wait = time.time()

            while not self.stop_event.is_set():
                # Check if we should exit (only for live bins)
                if max_checks and check_count >= max_checks:
                    elapsed_time = time.time() - start_wait
                    print(f"🎯 Live bin {timestamp_str} not found after {elapsed_time:.1f}s - exiting replay mode")
                    self.logger.info(
                        f"🎯 Live bin {timestamp_str} not found after {elapsed_time:.1f}s - exiting replay mode")
                    return False

                check_count += 1
                elapsed_time = time.time() - start_wait

                print(f"🔍 Data check #{check_count}")
                self.logger.info(f"🔍 Data check #{check_count}")

                # Check for data using environment-aware loader
                equity_bars = self.data_loader._load_equity_data_for_timestamp(minute_time)
                fx_rates = self.data_loader._load_fx_data_for_timestamp(minute_time)

                print(f"   🔹 Equity bars: {len(equity_bars) if equity_bars else 0}")
                print(f"   🔹 FX rates: {len(fx_rates) if fx_rates else 0}")
                self.logger.debug(
                    f"🔍 Data check #{check_count} - Equity bars: {len(equity_bars) if equity_bars else 0}, FX rates: {len(fx_rates) if fx_rates else 0}")

                if equity_bars:  # We have equity data
                    elapsed_time = time.time() - start_wait
                    print(f"📁 Found bin snap data!")
                    print(f"⏱️ Data found after {elapsed_time:.1f} seconds ({check_count} checks)")
                    self.logger.info(f"📁 Found bin snap data after {elapsed_time:.1f} seconds ({check_count} checks)")
                    return self._process_bin_snap_data(equity_bars, fx_rates, minute_time)

                # Log periodic status when waiting
                if check_count % 2 == 0:
                    print(f"🔍 Still looking for bin snap data: {timestamp_str}")
                    print(f"   ⏱️ Elapsed time: {elapsed_time:.1f} seconds")
                    print(f"   🔄 Check count: {check_count}")
                    if max_checks:
                        print(f"   🎯 Live bin - will exit after {max_checks} checks")
                    else:
                        print(f"   📚 Historical bin - waiting indefinitely")

                    self.logger.info(
                        f"🔍 Still looking for bin snap data: {timestamp_str} (elapsed: {elapsed_time:.1f}s)")

                # Sleep before next check
                print(f"⏰ Sleeping for {self.polling_interval} seconds...")
                time.sleep(self.polling_interval)

            if self.stop_event.is_set():
                print(f"🛑 Stop event detected - exiting data wait")
                self.logger.warning("🛑 Stop event detected - exiting data wait")
                return False

            return False

        except Exception as e:
            print(f"❌ Error in _wait_and_process_bin_snap_pair for {minute_time}: {e}")
            self.logger.error(f"❌ Error in _wait_and_process_bin_snap_pair for {minute_time}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False

    def _process_bin_snap_data(self, equity_bars, fx_rates, minute_time: datetime) -> bool:
        """Process the equity and FX bin snap data"""
        try:
            self.logger.info(f"📊 Processing bin snap data for {minute_time}")
            self.logger.debug(f"   📊 Equity bars: {len(equity_bars) if equity_bars else 0}")
            self.logger.debug(f"   💱 FX rates: {len(fx_rates) if fx_rates else 0}")

            if not equity_bars:
                self.logger.error(f"❌ No equity data available for {minute_time}")
                return False

            # Process the data through the unified processor with bypass flag
            books = self.exchange_group_manager.get_all_books()
            if books:
                self.logger.info(f"👥 Processing data for {len(books)} books: {books}")

                # Use bypass flag to avoid circular replay detection
                self.market_data_processor.process_market_data_bin(
                    equity_bars, fx_rates, bypass_replay_detection=True
                )

                # Update the exchange group manager's last snap time
                old_snap_time = self.exchange_group_manager.last_snap_time
                self.exchange_group_manager.last_snap_time = minute_time
                self.logger.info(f"🕒 Updated last snap time: {old_snap_time} -> {minute_time}")

                self.logger.info(f"✅ Successfully processed bin snap data for {minute_time}")
                self.logger.info(f"   📊 Equity bars: {len(equity_bars)}")
                self.logger.info(f"   💱 FX rates: {len(fx_rates) if fx_rates else 0}")
                return True
            else:
                self.logger.error("❌ No books found in exchange group manager")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error processing bin snap data for {minute_time}: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False

    def get_latest_live_info(self) -> Tuple[Optional[datetime], Optional[str]]:
        """Get the latest live timestamp and bin string"""
        try:
            if self.latest_live_timestamp is None:
                self.logger.debug("📡 No latest live timestamp available")
                return None, None

            # Format timestamp as bin string (YYYYMMDD_HHMM)
            latest_live_bin = self.latest_live_timestamp.strftime("%Y%m%d_%H%M")
            self.logger.debug(f"📡 Latest live info: timestamp={self.latest_live_timestamp}, bin={latest_live_bin}")
            return self.latest_live_timestamp, latest_live_bin

        except Exception as e:
            self.logger.error(f"❌ Error getting latest live info: {e}")
            return None, None

    def update_latest_live_timestamp(self, timestamp: datetime) -> None:
        """Update the latest live data timestamp"""
        self.latest_live_timestamp = ensure_utc(timestamp)
        self.logger.debug(f"📡 Updated latest live timestamp: {self.latest_live_timestamp}")

    def stop_replay(self) -> None:
        """Stop replay mode"""
        self.logger.info("🛑 Stopping replay mode")
        self.stop_event.set()

        if self.replay_thread and self.replay_thread.is_alive():
            self.logger.info("🧵 Waiting for replay thread to join...")
            self.replay_thread.join(timeout=10)
            self.logger.info(f"🧵 Thread joined: {not self.replay_thread.is_alive()}")

        self.state = ReplayModeState.LIVE

    def is_in_replay_mode(self) -> bool:
        """Check if currently in replay mode"""
        result = self.state in [ReplayModeState.REPLAY_WAITING, ReplayModeState.REPLAY_PROCESSING]
        self.logger.debug(f"🎬 is_in_replay_mode: {result} (state: {self.state.value})")
        return result

    def get_replay_status(self) -> dict:
        """Get current replay status"""
        status = {
            'state': self.state.value,
            'progress': self.current_progress.__dict__ if self.current_progress else None,
            'is_in_replay': self.state in [ReplayModeState.REPLAY_WAITING, ReplayModeState.REPLAY_PROCESSING],
            'latest_live_timestamp': self.latest_live_timestamp.isoformat() if self.latest_live_timestamp else None,
            'thread_alive': self.replay_thread.is_alive() if self.replay_thread else False
        }
        return status