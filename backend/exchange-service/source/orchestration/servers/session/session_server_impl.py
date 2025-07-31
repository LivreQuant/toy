# source/orchestration/servers/session/session_server_impl.py
"""
Fixed Session Server Implementation
Fixed timestamp method and using market time instead of system time
"""

import logging
import queue
import grpc
from datetime import datetime
from typing import Dict
from concurrent import futures

from source.orchestration.servers.utils import BaseServiceImpl
from source.proto.session_exchange_interface_pb2 import (
    ExchangeDataUpdate, StreamRequest, HeartbeatRequest, HeartbeatResponse,
    HealthRequest, HealthResponse, ServiceMetrics, SimulatorStatus,
    EquityData, OrderData, Trade, PortfolioStatus, Position,
    AccountStatus, AccountBalance, FXStatus, FXRate,
    ImpactStatus, ImpactData, ReturnsStatus, ReturnData,
    RiskStatus, EquityRiskData, PortfolioRiskData, RiskExposures, RiskMetrics,
    UniverseStatus, UniverseData, OrderStateEnum
)
from source.proto.session_exchange_interface_pb2_grpc import SessionExchangeSimulatorServicer, \
    add_SessionExchangeSimulatorServicer_to_server

# Import the new state managers
from .state_managers import CompositeStateManager


class MultiUserSessionServiceImpl(SessionExchangeSimulatorServicer, BaseServiceImpl):
    def __init__(self, exchange_group_manager, snapshot_manager=None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager
        self.snapshot_manager = snapshot_manager

        # Initialize the composite state manager
        self.state_manager = CompositeStateManager()

        # Per-user stream queues
        self._user_stream_queues: Dict[str, queue.Queue] = {}
        self._active_streams: Dict[str, grpc.ServicerContext] = {}

        # gRPC Server components
        self.server = None
        self.port = 50050  # Default port - make this configurable
        self.running = False

        # Track callback registration to prevent duplicates
        self._callback_registered = False

        # Track replay mode statistics
        self.replay_updates_sent = 0
        self.live_updates_sent = 0

        # Setup master callback - only register with first user's equity manager
        self._setup_master_callback()

    def _setup_master_callback(self):
        """Register with first user's equity manager as master trigger - PREVENT DUPLICATES"""
        # Prevent duplicate registrations
        if self._callback_registered:
            self.logger.info("🔍 CALLBACK ALREADY REGISTERED - SKIPPING DUPLICATE REGISTRATION")
            return

        users = self.exchange_group_manager.get_all_users()
        self.logger.info(f"🔍 SETTING UP SESSION SERVICE CALLBACKS")
        self.logger.info(f"🔍 Found {len(users)} users: {users}")

        if users:
            first_user_id = users[0]
            first_user_context = self.exchange_group_manager.user_contexts[first_user_id]
            self.logger.info(f"🔍 Using first user: {first_user_id}")

            if first_user_context.app_state.equity_manager:
                self.logger.info(f"🔍 Registering callback with equity manager for {first_user_id}")

                # FIXED: Use correct method name 'register_callback' instead of 'register_bin_advancement_callback'
                first_user_context.app_state.equity_manager.register_callback(
                    self._on_equity_data_complete
                )

                self._callback_registered = True
                self.logger.info("✅ SESSION SERVICE CALLBACK REGISTERED SUCCESSFULLY")
            else:
                self.logger.warning(f"⚠️ No equity manager found for user {first_user_id}")

    def _on_equity_data_complete(self, equity_data):
        """Handle equity data updates by sending updates to all active users"""
        try:
            self.logger.info(f"📊 Session Service Equity Callback Triggered!")
            self.logger.info(f"📊 Received equity data: {len(equity_data) if equity_data else 0} records")

            # Extract market timestamp from equity data if available
            market_timestamp = None
            timestamp_source = "unknown"

            # Method 1: Try to get timestamp from equity data (highest priority)
            if equity_data and len(equity_data) > 0:
                try:
                    timestamp_str = equity_data[0].get('timestamp')
                    if timestamp_str:
                        market_timestamp = datetime.fromisoformat(timestamp_str)
                        timestamp_source = "equity_data[0].timestamp"
                        self.logger.info(f"📅 Using market timestamp from equity data: {market_timestamp}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Error parsing equity data timestamp: {e}")

            # Method 2: Fall back to app state current timestamp
            if market_timestamp is None:
                market_timestamp, timestamp_source = self._get_market_timestamp("callback")

            self.logger.info(f"⏰ Final callback timestamp source: {timestamp_source}")

            # Get the latest data for all users and send updates
            for user_id, user_context in self.exchange_group_manager.user_contexts.items():
                if user_id in self._user_stream_queues:
                    self.logger.info(f"📤 Creating live update for user {user_id}")
                    update = ExchangeDataUpdate()

                    # ALWAYS use market timestamp (not computer time)
                    update.timestamp = int(market_timestamp.timestamp() * 1000)
                    update.user_id = user_id

                    self.logger.debug(f"⏰ Update timestamp: {market_timestamp} (source: {timestamp_source})")

                    # Add equity data to the update
                    if equity_data:
                        self._add_equity_data(update, equity_data)

                    # Add user-specific state using the new state manager
                    self.state_manager.add_user_state(update, user_context)

                    # Send to this user's queue
                    self._user_stream_queues[user_id].put(update)
                    self.logger.info(f"✅ Sent live update to user {user_id} queue")

            self.logger.info(f"✅ Sent live updates to {len(self._user_stream_queues)} active user streams")

        except Exception as e:
            self.logger.error(f"❌ Error in equity data callback: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")

    def _get_or_create_user_queue(self, user_id: str) -> queue.Queue:
        """Get or create stream queue for a specific user"""
        if user_id not in self._user_stream_queues:
            self._user_stream_queues[user_id] = queue.Queue()
        return self._user_stream_queues[user_id]

    def _add_equity_data(self, update: ExchangeDataUpdate, equity_data):
        """Add equity data to the update"""
        try:
            for bar_data in equity_data:
                equity_bar = EquityData()
                equity_bar.symbol = bar_data['symbol']
                equity_bar.open = float(bar_data['open'])
                equity_bar.high = float(bar_data['high'])
                equity_bar.low = float(bar_data['low'])
                equity_bar.close = float(bar_data['close'])
                equity_bar.volume = int(bar_data['volume'])
                equity_bar.trade_count = int(bar_data['count'])
                equity_bar.vwap = float(bar_data['vwap'])
                equity_bar.currency = bar_data['currency']
                equity_bar.vwas = float(bar_data['vwas'])

                update.equity_data.append(equity_bar)

            self.logger.debug(f"📊 Added {len(equity_data)} equity bars to update")
        except Exception as e:
            self.logger.error(f"Error adding equity data: {e}")

    def _send_initial_state_for_user(self, user_id: str):
        """Send initial state for a specific user"""
        try:
            self.logger.info(f"📡 Sending initial state to user {user_id}")

            user_context = self.exchange_group_manager.user_contexts[user_id]
            user_queue = self._get_or_create_user_queue(user_id)

            update = ExchangeDataUpdate()

            # Get market timestamp for initial state
            market_timestamp, timestamp_source = self._get_market_timestamp("initial_state")

            # Set the market timestamp
            update.timestamp = int(market_timestamp.timestamp() * 1000)
            update.user_id = user_id

            self.logger.info(f"⏰ Initial state timestamp: {market_timestamp}")
            self.logger.info(f"📍 Timestamp source: {timestamp_source}")

            # Add user-specific state using the new state manager
            self.state_manager.add_user_state(update, user_context)

            user_queue.put(update)
            self.logger.info(f"✅ Sent initial state to user {user_id} with market timestamp")

        except Exception as e:
            self.logger.error(f"❌ Error sending initial state to user {user_id}: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")

    def _get_market_timestamp(self, context: str = "unknown") -> tuple:
        """
        Get the current market timestamp from the best available source.
        Returns tuple of (timestamp, source_description)
        """
        try:
            # Try to get timestamp from first user's app state
            users = self.exchange_group_manager.get_all_users()
            if users:
                first_user_context = self.exchange_group_manager.user_contexts[users[0]]

                # Method 1: Try get_current_timestamp (market bin timestamp)
                if hasattr(first_user_context.app_state, 'get_current_timestamp'):
                    market_time = first_user_context.app_state.get_current_timestamp()
                    if market_time:
                        return market_time, f"app_state.get_current_timestamp()[{users[0]}]"

                # Method 2: Try get_next_timestamp (next market bin timestamp)
                if hasattr(first_user_context.app_state, 'get_next_timestamp'):
                    market_time = first_user_context.app_state.get_next_timestamp()
                    if market_time:
                        return market_time, f"app_state.get_next_timestamp()[{users[0]}]"

                # Method 3: Try base_date as fallback
                if hasattr(first_user_context.app_state, 'base_date') and first_user_context.app_state.base_date:
                    return first_user_context.app_state.base_date, f"app_state.base_date[{users[0]}]"

            # Method 4: Try exchange group manager last_snap_time
            if hasattr(self.exchange_group_manager, 'last_snap_time') and self.exchange_group_manager.last_snap_time:
                return self.exchange_group_manager.last_snap_time, "exchange_group_manager.last_snap_time"

            # Fallback to system time
            return datetime.now(), "system_time"

        except Exception as e:
            self.logger.warning(f"Error getting market timestamp for {context}: {e}")
            return datetime.now(), f"system_time_fallback[{context}]"

    # ========================================
    # gRPC Service Implementation Methods
    # ========================================

    def StreamExchangeData(self, request: StreamRequest, context: grpc.ServicerContext):
        """Stream exchange data to client - Multi-user aware"""
        user_id = request.user_id if request.user_id else "USER_000"  # Default fallback

        self.logger.info(f"🌊 New stream request from user: {user_id}")

        if user_id not in self.exchange_group_manager.user_contexts:
            context.abort(grpc.StatusCode.NOT_FOUND, f"User {user_id} not found")
            return

        # Track this stream
        self._active_streams[user_id] = context
        user_queue = self._get_or_create_user_queue(user_id)

        try:
            # Send initial state
            self._send_initial_state_for_user(user_id)

            # Stream updates
            while context.is_active():
                try:
                    # Get update from queue with timeout
                    update = user_queue.get(timeout=1.0)
                    yield update
                    self.logger.debug(f"📤 Sent update to user {user_id}")
                except queue.Empty:
                    # Send periodic heartbeat or continue
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Error sending update to user {user_id}: {e}")
                    break

        except grpc.RpcError as e:
            self.logger.info(f"🔌 Stream disconnected for user {user_id}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Unexpected error in stream for user {user_id}: {e}")
        finally:
            # Clean up
            if user_id in self._active_streams:
                del self._active_streams[user_id]
            if user_id in self._user_stream_queues:
                del self._user_stream_queues[user_id]
            self.logger.info(f"🧹 Cleaned up stream for user {user_id}")

    def GetHealth(self, request: HealthRequest, context: grpc.ServicerContext):
        """Get server health status"""
        try:
            response = HealthResponse()
            user_id = request.user_id if request.user_id else "USER_000"

            # Check if we have any users and determine health
            if self.exchange_group_manager.user_contexts:
                if user_id in self.exchange_group_manager.user_contexts:
                    user_context = self.exchange_group_manager.user_contexts[user_id]
                    # Map app state to valid status strings
                    app_state_status = user_context.app_state.get_app_state()
                    if app_state_status == "ACTIVE":
                        response.status = "healthy"
                    elif app_state_status == "DEGRADED":
                        response.status = "error"  # Map DEGRADED to error
                    elif app_state_status == "INITIALIZING":
                        response.status = "initializing"
                    else:
                        response.status = "error"

                    response.market_state = f"User {user_id}: {app_state_status}"
                else:
                    response.status = "error"
                    response.market_state = f"User {user_id} not found"
            else:
                response.status = "initializing"
                response.market_state = "No users configured"

            # FIX: Use integer timestamp, not string
            response.timestamp = int(datetime.now().timestamp() * 1000)

            # FIX: Remove this line - user_id field doesn't exist in proto
            # response.user_id = user_id

            # Add service metrics using the correct structure
            if user_id in self.exchange_group_manager.user_contexts:
                user_context = self.exchange_group_manager.user_contexts[user_id]
                # Only add metrics if the user context has service status
                if hasattr(user_context.app_state, '_service_status'):
                    for name, status in user_context.app_state._service_status.items():
                        service_metric = ServiceMetrics()
                        service_metric.running = status.is_running if hasattr(status, 'is_running') else True
                        service_metric.errors = status.error_count if hasattr(status, 'error_count') else 0
                        service_metric.last_heartbeat = status.last_heartbeat.isoformat() if hasattr(status,
                                                                                                     'last_heartbeat') else datetime.now().isoformat()
                        response.services[name].CopyFrom(service_metric)

            return response
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def Heartbeat(self, request: HeartbeatRequest, context: grpc.ServicerContext):
        """Get heartbeat for specific user"""
        try:
            user_id = request.user_id if request.user_id else "USER_000"  # Default fallback

            if user_id not in self.exchange_group_manager.user_contexts:
                context.abort(grpc.StatusCode.NOT_FOUND, f"User {user_id} not found")
                return

            user_context = self.exchange_group_manager.user_contexts[user_id]

            response = HeartbeatResponse()
            response.success = True
            response.server_timestamp = int(datetime.now().timestamp() * 1000)
            response.user_id = user_id  # Add user_id to response

            # Check health for this specific user
            if user_context.app_state.is_healthy():
                response.status = SimulatorStatus.RUNNING
            elif user_context.app_state.is_initialized():
                response.status = SimulatorStatus.ERROR
            else:
                response.status = SimulatorStatus.INITIALIZING

            # Use this user's timing info
            response.current_bin = user_context.app_state.get_current_bin() or ""
            response.next_bin = user_context.app_state.get_next_bin() or ""

            return response
        except Exception as e:
            self.logger.error(f"Error in heartbeat for user {user_id}: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    # ========================================
    # gRPC Server Management Methods
    # ========================================

    def start_sync_server(self, port: int = None):
        """Start the gRPC server synchronously"""
        try:
            if port:
                self.port = port

            self.logger.info(f"🚀 Starting Session Exchange gRPC Server on port {self.port}")

            # Create server
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

            # Add servicer to server
            add_SessionExchangeSimulatorServicer_to_server(self, self.server)

            # Add insecure port
            listen_addr = f'[::]:{self.port}'
            self.server.add_insecure_port(listen_addr)

            # Start server
            self.server.start()
            self.running = True

            self.logger.info(f"✅ Session Exchange gRPC Server started successfully")
            self.logger.info(f"📡 Listening on {listen_addr}")
            self.logger.info(f"👥 Supporting {len(self.exchange_group_manager.user_contexts)} users")

            # Log available users
            for user_id in self.exchange_group_manager.user_contexts.keys():
                self.logger.info(f"   📊 User: {user_id}")

        except Exception as e:
            self.logger.error(f"❌ Failed to start Session Exchange gRPC Server: {e}")
            raise

    def stop(self):
        """Synchronous stop method for compatibility"""
        if self.running and self.server:
            try:
                # For sync server, stop directly
                self.server.stop(grace=5)
                self.running = False
                self._active_streams.clear()
                self._user_stream_queues.clear()
                self.logger.info("✅ Session Exchange gRPC Server stopped")
            except Exception as e:
                self.logger.error(f"❌ Error stopping Session Exchange gRPC Server: {e}")

    def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            self.server.wait_for_termination()