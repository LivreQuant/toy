# source/orchestration/servers/market_data/enhanced_market_data_server_impl.py
import grpc
import os
import logging
import threading
import time
from datetime import datetime
from typing import List
from decimal import Decimal

from source.simulation.managers.equity import EquityBar
from source.simulation.managers.fx import FXRate

from source.orchestration.replay.replay_manager import ReplayManager, ReplayModeState
from source.orchestration.processors.market_data_processor import MarketDataProcessor

from source.api.grpc.market_data_interface_pb2 import SubscriptionRequest, MarketDataStream
from source.api.grpc.market_data_interface_pb2_grpc import MarketDataServiceStub

from source.utils.timezone_utils import ensure_utc

# Retry configuration
RETRY_INTERVAL_SECONDS = 10
CONNECTION_TIMEOUT_SECONDS = 5


class EnhancedMultiUserMarketDataClient:
    """Enhanced client with unified replay mode support for handling missing minute bars"""

    def __init__(self, exchange_group_manager, host: str = "localhost", port: int = 50051):
        self.exchange_group_manager = exchange_group_manager
        self.host = host
        self.port = port

        # Initialize unified replay manager
        self.replay_manager = ReplayManager(
            exchange_group_manager=exchange_group_manager,
            market_data_client=self,
            polling_interval=5
        )

        # Set up replay callbacks
        self.replay_manager.on_replay_complete = self._on_replay_complete
        self.replay_manager.on_replay_progress = self._on_replay_progress

        # Initialize market data processor
        self.market_data_processor = MarketDataProcessor(exchange_group_manager)

        # Queue for live data during replay
        self.live_data_queue = []

        # Connection state
        self.channel = None
        self.stub = None
        self.stream = None
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False

        # Statistics
        self.batches_received = 0
        self.total_bars_received = 0
        self.total_fx_received = 0
        self.processing_errors = 0
        self.last_received_time = None
        self.connection_attempts = 0
        self.replay_sessions = 0

        # Setup logging
        self.logger = logging.getLogger('ENHANCED_MULTI_USER_MARKET_DATA_CLIENT')
        self._setup_logging()
        self._log_initialization_header()

    def _setup_logging(self):
        """Setup dedicated logging for market data client"""
        # FIXED: Get project root directory correctly
        # Current file: source/orchestration/servers/market_data/market_data_server_impl.py
        # Need to go up 5 levels to reach project root
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))

        # Double-check we have the right directory by looking for the source folder
        if not os.path.exists(os.path.join(project_root, "source")):
            # Fallback: find project root by locating the parent of "source" directory
            path_parts = current_file.split(os.sep)
            try:
                source_index = path_parts.index("source")
                project_root = os.sep.join(path_parts[:source_index])
            except ValueError:
                # Last resort: use current working directory
                project_root = os.getcwd()

        # FIXED: This will write to /logs/ not /source/logs/
        logs_dir = os.path.join(project_root, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Create timestamped log file name based on MARKET TIME
        market_time = self.exchange_group_manager.last_snap_time
        if market_time:
            timestamp = market_time.strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log_file_path = os.path.join(logs_dir, f"enhanced_multi_user_market_data_feed_{timestamp}.log")

        # IMPORTANT: Don't create a separate file handler here - use the exchange logging system
        # The logger should already be configured by the exchange_logging system
        # Just make sure we're using the right logger name that's configured in exchange_logging

        # The logger name 'ENHANCED_MULTI_USER_MARKET_DATA_CLIENT' is already configured
        # in the exchange_logging config to inherit from the exchange logger

        # Log the file path for reference, but the actual logging will go to exchange log
        print(f"📁 Market data client would log to: {self.log_file_path}")
        print(f"📁 But using exchange logging system instead")

        # Set logging level
        self.logger.setLevel(logging.DEBUG)

    def _log_initialization_header(self):
        """Log initialization header with market time"""
        market_time = self.exchange_group_manager.last_snap_time
        users = self.exchange_group_manager.get_all_users()

        self.logger.info("█" * 120)
        self.logger.info("█" + " " * 30 + "ENHANCED MULTI-USER MARKET DATA CLIENT WITH UNIFIED REPLAY" + " " * 30 + "█")
        self.logger.info("█" * 120)
        self.logger.info("")
        self.logger.info(f"📁 LOG FILE: {self.log_file_path}")
        self.logger.info(f"🎯 TARGET HOST: {self.host}")
        self.logger.info(f"🔌 TARGET PORT: {self.port}")
        self.logger.info(f"👥 USERS: {len(users)} users ({', '.join(str(user) for user in users)})")
        self.logger.info(f"🏛️ EXCHANGE ID: {self.exchange_group_manager.exch_id}")
        self.logger.info(f"📍 MARKET TIME (FROZEN): {market_time}")
        self.logger.info(f"🎬 REPLAY MODE: Available (Unified)")
        self.logger.info(f"🚫 COMPUTER TIME: IGNORED")
        self.logger.info("")
        self.logger.info("█" * 120)

    def start(self):
        """Start the enhanced market data client"""
        try:
            self.logger.info("")
            self.logger.info("🚀 STARTING ENHANCED MULTI-USER MARKET DATA CLIENT WITH UNIFIED REPLAY")
            self.logger.info("=" * 120)

            users = self.exchange_group_manager.get_all_users()
            print(f"🚀 Enhanced multi-user market data client starting for {len(users)} users")
            print(f"📍 Market time frozen at: {self.exchange_group_manager.last_snap_time}")
            print(f"🎬 Replay mode: Available (Unified)")
            print(f"📁 Detailed logs: {self.log_file_path}")

            # Set running flag
            self.running = True
            self.stop_event.clear()

            # Start connection thread
            self.thread = threading.Thread(target=self._run_client, daemon=True)
            self.thread.start()

        except Exception as e:
            self.logger.error(f"❌ Error starting enhanced market data client: {e}")
            raise

    def stop(self):
        """Stop the enhanced market data client"""
        try:
            self.logger.info("🛑 Stopping enhanced multi-user market data client")
            self.running = False
            self.stop_event.set()

            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)

            if self.channel:
                self.channel.close()

            # Stop replay manager
            self.replay_manager.stop_replay()

            self.logger.info("✅ Enhanced multi-user market data client stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping market data client: {e}")

    def _run_client(self):
        """Main client loop"""
        while self.running and not self.stop_event.is_set():
            try:
                if self._connect_to_service():
                    self._stream_market_data()

                if self.running and not self.stop_event.is_set():
                    self.logger.info(f"⏳ Retrying connection in {RETRY_INTERVAL_SECONDS} seconds...")
                    time.sleep(RETRY_INTERVAL_SECONDS)

            except Exception as e:
                self.logger.error(f"❌ Error in client loop: {e}")
                import traceback
                self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                if self.running:
                    time.sleep(RETRY_INTERVAL_SECONDS)

    def _connect_to_service(self) -> bool:
        """Connect to market data service"""
        try:
            self.connection_attempts += 1

            self.logger.info("")
            self.logger.info("🔌 CONNECTION ATTEMPT")
            self.logger.info("=" * 60)
            self.logger.info(f"📊 Attempt #{self.connection_attempts}")
            self.logger.info(f"🎯 Target: {self.host}:{self.port}")

            # Create channel
            self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            self.stub = MarketDataServiceStub(self.channel)

            # Test connection
            self.logger.debug("🔍 Testing channel connectivity...")
            grpc.channel_ready_future(self.channel).result(timeout=CONNECTION_TIMEOUT_SECONDS)

            self.logger.info("✅ CONNECTION SUCCESSFUL!")
            self.logger.info(f"🎉 Connected after {self.connection_attempts} attempt(s)")
            self.logger.info("=" * 60)

            print(
                f"✅ Connected to market data service for {len(self.exchange_group_manager.get_all_users())} users (attempt #{self.connection_attempts})")
            return True

        except grpc.FutureTimeoutError:
            self.logger.warning(f"⏰ Connection timeout after {CONNECTION_TIMEOUT_SECONDS} seconds")
            self.logger.info("=" * 60)
            return False
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.logger.info("=" * 60)
            return False

    def _stream_market_data(self):
        """Stream market data from service"""
        try:
            self.logger.info("")
            self.logger.info("🔄 STARTING ENHANCED MULTI-USER MARKET DATA STREAM")
            self.logger.info("=" * 120)

            # Create subscription request
            request = SubscriptionRequest()
            request.subscriber_id = f"enhanced_multi_user_exchange_{id(self)}"
            request.include_history = True

            self.logger.info(f"📨 Subscription ID: {request.subscriber_id}")
            self.logger.info(f"📚 Include history: {request.include_history}")
            self.logger.info("🎧 Listening for data...")
            self.logger.info("=" * 120)

            print(
                f"🔄 Enhanced multi-user market data stream started for {len(self.exchange_group_manager.get_all_users())} users - receiving data...")

            # Use the correct method name
            self.stream = self.stub.SubscribeToMarketData(request)
            self.logger.debug("🔄 Stream created successfully, starting to iterate...")

            for stream_data in self.stream:
                if self.stop_event.is_set() or not self.running:
                    self.logger.info("🛑 Stopping stream due to shutdown signal")
                    break

                self.logger.debug(f"📥 Received stream data: {type(stream_data)}")
                self._process_market_data_for_all_users(stream_data)

            self.logger.info("🔄 Stream iteration completed")

        except grpc.RpcError as e:
            self.logger.error(f"❌ gRPC error in stream: {e}")
            self.logger.error(f"❌ gRPC error code: {e.code()}")
            self.logger.error(f"❌ gRPC error details: {e.details()}")
        except Exception as e:
            self.logger.error(f"❌ Error in market data stream: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            self.processing_errors += 1

    def _process_market_data_for_all_users(self, stream_data: MarketDataStream):
        """Process incoming market data with unified replay mode detection and live mode transition"""
        try:
            self.logger.debug("🔄 Starting _process_market_data_for_all_users")

            start_time = time.time()
            self.batches_received += 1

            # Parse incoming timestamp and ensure it's timezone-aware
            incoming_timestamp = datetime.fromtimestamp(stream_data.timestamp / 1000)
            incoming_timestamp = ensure_utc(incoming_timestamp)

            # Update the replay manager with the latest live timestamp
            self.logger.info(f"📡 Updating replay manager with latest live timestamp: {incoming_timestamp}")
            self.replay_manager.update_latest_live_timestamp(incoming_timestamp)

            users = self.exchange_group_manager.get_all_users()

            # Header logging
            self.logger.info("")
            self.logger.info("█" * 120)
            self.logger.info(f"📦 BATCH #{stream_data.batch_number:04d} RECEIVED FOR {len(users)} USERS")
            self.logger.info("█" * 120)
            self.logger.info(f"⏰ Market Timestamp: {incoming_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            self.logger.info(f"🕒 Bin Time: {stream_data.bin_time}")
            self.logger.info(f"👥 Users: {', '.join(str(user) for user in users)}")
            self.logger.info(f"🔄 Total Batches: {self.batches_received}")
            self.logger.info(f"🎬 Replay Mode: {self.replay_manager.state.value}")

            # Check replay state first
            current_state = self.replay_manager.state
            self.logger.info(f"🎬 Current replay state: {current_state.value}")

            # Handle replay completion and transition to live mode
            if current_state == ReplayModeState.REPLAY_COMPLETE:
                self.logger.info("🎯 REPLAY COMPLETED - TRANSITIONING TO LIVE MODE")
                print("🎯 REPLAY COMPLETED - TRANSITIONING TO LIVE MODE")

                # Mark as live
                self.replay_manager.state = ReplayModeState.LIVE
                self.logger.info("✅ State transitioned to LIVE mode")
                print("✅ State transitioned to LIVE mode")

                # Process any queued live data first
                if self.live_data_queue:
                    self.logger.info(f"🔄 Processing {len(self.live_data_queue)} queued live data items")
                    print(f"🔄 Processing {len(self.live_data_queue)} queued live data items")
                    self._process_queued_live_data()

                # Now process current data
                self.logger.info("🔄 Processing current live data after replay completion")
                print("🔄 Processing current live data after replay completion")
                self._process_normal_market_data(stream_data, users, incoming_timestamp)
                return

            # If in replay mode, queue for later processing
            if current_state in [ReplayModeState.REPLAY_WAITING, ReplayModeState.REPLAY_PROCESSING]:
                self.logger.info(f"🎬 In replay mode ({current_state.value}) - queuing live data")
                print(f"🎬 In replay mode ({current_state.value}) - queuing live data")
                self.live_data_queue.append(stream_data)
                return

            # If in live mode, check for gaps
            if current_state == ReplayModeState.LIVE:
                # Detailed debugging for gap detection
                last_snap_time = self.exchange_group_manager.last_snap_time
                time_diff = incoming_timestamp - last_snap_time

                self.logger.info("🔍 DETAILED DEBUG GAP DETECTION:")
                self.logger.info(f"   Last snap: {last_snap_time}")
                self.logger.info(f"   Incoming: {incoming_timestamp}")
                self.logger.info(f"   Time diff: {time_diff}")
                self.logger.info(f"   Time diff seconds: {time_diff.total_seconds()}")

                self.logger.info("🔍 Not in replay mode - checking for gap...")

            try:
                # Call detect_gap directly
                gap_info = self.replay_manager.detect_gap(last_snap_time, incoming_timestamp)
                self.logger.info(f"🔍 Gap detection returned: {gap_info}")
                self.logger.info(f"🔍 Gap detection type: {type(gap_info)}")

                if gap_info:
                    self.logger.warning("🚨 GAP DETECTED - ENTERING REPLAY MODE!")
                    print("🚨 GAP DETECTED - ENTERING REPLAY MODE!")

                    self.replay_manager.enter_replay_mode(
                        last_snap_time=last_snap_time,
                        target_live_time=incoming_timestamp
                    )

                    # Queue this data for after replay
                    self.logger.info("📦 Queuing current live data for after replay")
                    print("📦 Queuing current live data for after replay")
                    self.live_data_queue.append(stream_data)
                    return
                else:
                    self.logger.info("✅ No gap detected - processing normally")

            except Exception as e:
                self.logger.error(f"❌ Error in gap detection: {e}")
                import traceback
                self.logger.error(f"❌ Traceback: {traceback.format_exc()}")

                # Normal processing for live data
            self.logger.info("🔄 Processing market data in live mode")
            print("🔄 Processing market data in live mode")
            self._process_normal_market_data(stream_data, incoming_timestamp)

            # Log timing
            processing_time = (time.time() - start_time) * 1000
            self.logger.info(f"✅ Batch processing completed in {processing_time:.2f}ms")

        except Exception as e:
            self.logger.error(f"❌ Error processing market data: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            self.processing_errors += 1

    def _process_normal_market_data(self, stream_data: MarketDataStream, incoming_timestamp: datetime):
        """Process market data normally (not in replay mode)"""
        try:
            self.logger.info("🔄 Starting normal market data processing")

            # Convert protobuf to internal format
            equity_bars = self._convert_equity_data(stream_data.equity, incoming_timestamp)
            fx_rates = self._convert_fx_data(stream_data.fx) if stream_data.fx else None

            # Log data summary
            self.logger.info(f"📊 Data Summary:")
            self.logger.info(f"   Equity bars: {len(equity_bars)}")
            self.logger.info(f"   FX rates: {len(fx_rates) if fx_rates else 0}")

            # Process through the unified market data processor
            if equity_bars:
                self.logger.info("🔄 Processing through unified market data processor")
                self.market_data_processor.process_market_data_bin(equity_bars, fx_rates)
                self.logger.info("✅ Market data processor completed")

                # Update last snap time
                self.exchange_group_manager.last_snap_time = incoming_timestamp
                self.logger.info(f"📍 Updated last snap time to: {incoming_timestamp}")
                print(f"📍 Updated last snap time to: {incoming_timestamp}")
            else:
                self.logger.warning("⚠️ No equity bars to process")

            # Update stats
            self.total_bars_received += len(equity_bars)
            self.total_fx_received += len(fx_rates) if fx_rates else 0
            self.last_received_time = datetime.now()

        except Exception as e:
            self.logger.error(f"❌ Error in normal market data processing: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            raise

    def _convert_equity_data(self, equity_data, market_timestamp: datetime) -> List[EquityBar]:
        """Convert protobuf equity data to internal format"""
        try:
            self.logger.debug(f"🔄 Converting {len(equity_data)} equity bars")
            bars = []

            for bar in equity_data:
                timestamp = market_timestamp.isoformat()
                equity_bar = EquityBar(
                    symbol=bar.symbol,
                    timestamp=timestamp,
                    currency=getattr(bar, 'currency', 'USD'),
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    count=getattr(bar, 'trade_count', 0),
                    vwap=getattr(bar, 'vwap', 0.0),
                    vwas=getattr(bar, 'vwas', 0.0),
                    vwav=getattr(bar, 'vwav', 0.0)
                )
                bars.append(equity_bar)

            self.logger.debug(f"✅ Converted {len(bars)} equity bars successfully")
            return bars

        except Exception as e:
            self.logger.error(f"❌ Error converting equity data: {e}")
            return []

    def _convert_fx_data(self, fx_data) -> List[FXRate]:
        """Convert protobuf FX data to internal format"""
        try:
            self.logger.debug(f"🔄 Converting {len(fx_data)} FX rates")
            rates = []

            for rate in fx_data:
                fx_rate = FXRate(
                    from_currency=rate.from_currency,
                    to_currency=rate.to_currency,
                    rate=Decimal(str(rate.rate))
                )
                rates.append(fx_rate)

            self.logger.debug(f"✅ Converted {len(rates)} FX rates successfully")
            return rates

        except Exception as e:
            self.logger.error(f"❌ Error converting FX data: {e}")
            return []

    def _on_replay_complete(self):
        """Called when replay mode is complete"""
        self.logger.info("✅ REPLAY MODE COMPLETE - TRANSITIONING TO LIVE DATA PROCESSING")
        print("✅ REPLAY MODE COMPLETE - TRANSITIONING TO LIVE DATA PROCESSING")
        self.replay_sessions += 1

        # Mark the state as complete so the next live data batch will transition to live mode
        self.replay_manager.state = ReplayModeState.REPLAY_COMPLETE
        self.logger.info("🎬 Replay state set to REPLAY_COMPLETE")
        print("🎬 Replay state set to REPLAY_COMPLETE")

    def _process_queued_live_data(self):
        """Process queued live data after replay completion"""
        try:
            self.logger.info(f"🔄 Processing {len(self.live_data_queue)} queued live data items")
            print(f"🔄 Processing {len(self.live_data_queue)} queued live data items")

            for i, stream_data in enumerate(self.live_data_queue):
                # users = self.exchange_group_manager.get_all_users()
                incoming_timestamp = datetime.fromtimestamp(stream_data.timestamp / 1000)
                incoming_timestamp = ensure_utc(incoming_timestamp)

                self.logger.info(
                    f"📊 Processing queued data {i + 1}/{len(self.live_data_queue)} for timestamp: {incoming_timestamp}")
                print(
                    f"📊 Processing queued data {i + 1}/{len(self.live_data_queue)} for timestamp: {incoming_timestamp}")

                self._process_normal_market_data(stream_data, incoming_timestamp)

            # Clear the queue
            queue_count = len(self.live_data_queue)
            self.live_data_queue.clear()
            self.logger.info(f"✅ All {queue_count} queued live data items processed and queue cleared")
            print(f"✅ All {queue_count} queued live data items processed and queue cleared")

        except Exception as e:
            self.logger.error(f"❌ Error processing queued live data: {e}")
            print(f"❌ Error processing queued live data: {e}")

    def _on_replay_progress(self, progress):
        """Called when replay progress updates"""
        progress_msg = f"🎬 Replay progress: {progress.progress_percentage:.1f}% ({progress.completed_minutes}/{progress.total_minutes} minutes)"
        self.logger.info(progress_msg)

        # Log progress to console every 10% or every 5 minutes
        if progress.completed_minutes % 5 == 0 or progress.progress_percentage % 10 == 0:
            print(progress_msg)

    def get_stats(self) -> dict:
        """Get service statistics"""
        return {
            'batches_received': self.batches_received,
            'total_bars_received': self.total_bars_received,
            'total_fx_received': self.total_fx_received,
            'processing_errors': self.processing_errors,
            'connection_attempts': self.connection_attempts,
            'replay_sessions': self.replay_sessions,
            'last_received_time': self.last_received_time.isoformat() if self.last_received_time else None,
            'replay_state': self.replay_manager.state.value if self.replay_manager else 'not_available',
            'queued_live_data': len(self.live_data_queue)
        }
