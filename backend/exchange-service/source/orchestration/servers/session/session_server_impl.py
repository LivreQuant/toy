# source/orchestration/servers/session/session_server_impl.py
"""
COMPLETE Session Server Implementation - FIXED BATCHING
"""

import logging
import queue
import grpc
import uuid
from datetime import datetime, timedelta
from typing import Dict, List
from concurrent import futures

from source.orchestration.servers.utils import BaseServiceImpl
from source.api.grpc.session_exchange_interface_pb2 import (
    ExchangeDataUpdate, StreamRequest, HeartbeatRequest, HeartbeatResponse,
    HealthRequest, HealthResponse, ServiceMetrics, SimulatorStatus,
    EquityData, OrderData, Trade, PortfolioStatus, Position,
    AccountStatus, AccountBalance, FXStatus, FXRate,
    ImpactStatus, ImpactData, ReturnsStatus, ReturnData,
    RiskStatus, EquityRiskData, PortfolioRiskData, RiskExposures, RiskMetrics,
    UniverseStatus, UniverseData, OrderStateEnum
)
from source.api.grpc.session_exchange_interface_pb2_grpc import SessionExchangeSimulatorServicer, \
    add_SessionExchangeSimulatorServicer_to_server

# Import the new state managers
from .state_managers import CompositeStateManager


class MultiUserSessionServiceImpl(SessionExchangeSimulatorServicer, BaseServiceImpl):
    def __init__(self, exchange_group_manager, snapshot_manager=None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("🔧 SESSION SERVICE INITIALIZATION STARTING")

        self.exchange_group_manager = exchange_group_manager
        self.snapshot_manager = snapshot_manager
        self._sequence_counter = 0

        # Initialize composite state manager
        try:
            self.state_manager = CompositeStateManager()
            self._composite_state_manager = CompositeStateManager()
            print(f"🔥🔥🔥 SESSION SERVICE: Composite state manager initialized")
            self.logger.info("🔧 SESSION SERVICE: Composite state manager initialized successfully")
        except Exception as e:
            self.state_manager = None
            self._composite_state_manager = None
            print(f"🔥🔥🔥 SESSION SERVICE: Composite state manager not available: {e}")
            self.logger.warning(f"🔧 SESSION SERVICE: Composite state manager not available: {e}")

        # Per-user stream queues
        self._user_stream_queues: Dict[str, queue.Queue] = {}
        self._active_streams: Dict[str, grpc.ServicerContext] = {}

        # gRPC Server components
        self.server = None
        self.port = 50050
        self.running = False
        self._callback_registered = False

        # Track replay mode statistics
        self.replay_updates_sent = 0
        self.live_updates_sent = 0

        # Setup master callback
        self._setup_master_callback()
        self.logger.info("🔧 SESSION SERVICE INITIALIZATION COMPLETE")

    def start_sync_server(self, port: int = 50050):
        """Start the session service gRPC server synchronously"""
        self.logger.info("🚀 SESSION SERVICE: Starting gRPC server")
        try:
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            add_SessionExchangeSimulatorServicer_to_server(self, self.server)
            self.server.add_insecure_port(f'[::]:{port}')
            self.server.start()

            self.port = port
            self.running = True

            users = self.exchange_group_manager.get_all_users()
            self.logger.info(f"✅ Session Service: STARTED on port {port}")
            self.logger.info(f"🔗 Session Service: Ready for up to {len(users)} concurrent user connections")

        except Exception as e:
            self.logger.error(f"❌ SESSION SERVICE: Failed to start server: {e}")
            raise

    def GetSessionStatus(self, request, context):
        """Get session connection status for a user"""
        try:
            from source.api.grpc.session_exchange_interface_pb2 import SessionStatusResponse
            
            response = SessionStatusResponse()
            response.user_id = request.user_id
            response.is_connected = request.user_id in self._active_streams
            response.connection_count = 1 if response.is_connected else 0
            response.last_update_timestamp = int(datetime.now().timestamp() * 1000)
            response.next_sequence_number = 0
            
            if response.is_connected:
                response.active_session_instances.append(request.session_instance_id)
            
            self.logger.info(f"📊 SESSION_STATUS: User {request.user_id} - connected: {response.is_connected}")
            return response
            
        except Exception as e:
            self.logger.error(f"❌ SESSION_STATUS: Error getting session status: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Internal error: {e}')
            
            # Return empty response on error
            from source.api.grpc.session_exchange_interface_pb2 import SessionStatusResponse
            return SessionStatusResponse()
        
    def GetHealth(self, request: HealthRequest, context: grpc.ServicerContext):
        """Get server health status"""
        try:
            response = HealthResponse()
            user_id_str = request.user_id

            import uuid
            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                response.status = "error"
                response.market_state = f"Invalid user ID format"
                response.timestamp = int(datetime.now().timestamp() * 1000)
                return response

            if self.exchange_group_manager and hasattr(self.exchange_group_manager, 'user_contexts'):
                user_context = self.exchange_group_manager.user_contexts.get(user_id)
                if user_context and user_context.app_state:
                    app_state_status = user_context.app_state.get_app_state()
                    response.status = "healthy" if app_state_status == "ACTIVE" else "error"
                    response.market_state = f"User {user_id}: {app_state_status}"
                else:
                    response.status = "error"
                    response.market_state = f"User {user_id} not found"
            else:
                response.status = "initializing"
                response.market_state = "No exchange group manager"

            response.timestamp = int(datetime.now().timestamp() * 1000)
            return response

        except Exception as e:
            response = HealthResponse()
            response.status = "error"
            response.market_state = f"Health check error: {str(e)}"
            response.timestamp = int(datetime.now().timestamp() * 1000)
            return response

    def StreamExchangeData(self, request: StreamRequest, context: grpc.ServicerContext):
        """Stream exchange data to client"""
        user_id_str = request.user_id

        import uuid
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid user ID format: {user_id_str}")
            return

        self.logger.info(f"🌊 STREAM REQUEST: New stream request from user: {user_id}")

        if not self.exchange_group_manager or not hasattr(self.exchange_group_manager, 'user_contexts'):
            context.abort(grpc.StatusCode.INTERNAL, "No user contexts available")
            return

        if user_id not in self.exchange_group_manager.user_contexts:
            context.abort(grpc.StatusCode.NOT_FOUND, f"User {user_id} not found")
            return

        # Track this stream
        self._active_streams[user_id] = context
        user_queue = self._get_or_create_user_queue(user_id)

        try:
            self.logger.info(f"🌊 STREAM REQUEST: Starting stream for user {user_id}")
            self._send_initial_state_for_user(user_id)

            # Stream updates
            while context.is_active():
                try:
                    update = user_queue.get(timeout=1.0)
                    yield update
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Error sending update to user {user_id}: {e}")
                    break

        except grpc.RpcError as e:
            self.logger.info(f"🔌 Stream disconnected for user {user_id}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Unexpected error in stream for user {user_id}: {e}")
        finally:
            if user_id in self._active_streams:
                del self._active_streams[user_id]
            if user_id in self._user_stream_queues:
                del self._user_stream_queues[user_id]
            self.logger.info(f"🧹 Cleaned up stream for user {user_id}")

    def _setup_master_callback(self):
        """Register with first user's equity manager as master trigger"""
        print(f"🔥🔥🔥 SESSION SERVICE: _setup_master_callback CALLED")

        if self._callback_registered:
            return

        if not self.exchange_group_manager or not hasattr(self.exchange_group_manager, 'user_contexts'):
            return

        users = self.exchange_group_manager.get_all_users()
        if not users:
            return

        master_user = users[0]
        print(f"🔥🔥🔥 SESSION SERVICE: Using master user: {master_user}")

        try:
            user_context = self.exchange_group_manager.user_contexts.get(master_user)
            if user_context and hasattr(user_context, 'app_state') and user_context.app_state:
                if hasattr(user_context.app_state, 'equity_manager') and user_context.app_state.equity_manager:
                    equity_manager = user_context.app_state.equity_manager
                    if hasattr(equity_manager, 'register_update_callback'):
                        equity_manager.register_update_callback(self._on_market_data_update)
                        self._callback_registered = True
                        print(f"🔥🔥🔥 SESSION SERVICE: CALLBACK REGISTERED SUCCESSFULLY!")
        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: EXCEPTION in callback setup: {e}")

    def _get_next_sequence(self) -> int:
        """Get next sequence number for messages"""
        self._sequence_counter += 1
        return self._sequence_counter

    def _get_or_create_user_queue(self, user_id: str) -> queue.Queue:
        """Get or create queue for user"""
        if user_id not in self._user_stream_queues:
            self._user_stream_queues[user_id] = queue.Queue()
        return self._user_stream_queues[user_id]

    def _send_initial_state_for_user(self, user_id: str):
        """Send initial state to user"""
        self.logger.info(f"📤 INITIAL STATE: Sending to user {user_id}")

    def _on_market_data_update(self, update_data):
        """Handle market data updates - MAIN CALLBACK - FIXED FOR BATCHING"""
        print(f"🔥🔥🔥 SESSION SERVICE: _on_market_data_update CALLED!")
        print(f"🔥🔥🔥 SESSION SERVICE: Received {len(update_data) if update_data else 0} updates")

        try:
            if not update_data:
                return

            # FIXED: Create a SINGLE batched exchange update with ALL equity data
            batched_exchange_update = self._create_batched_exchange_update(update_data)

            # Queue the SINGLE batched update for all active users
            for user_id in self._active_streams:
                user_exchange_update = ExchangeDataUpdate()
                user_exchange_update.CopyFrom(batched_exchange_update)
                user_exchange_update.user_id = str(user_id)  # Convert UUID to string

                if user_id in self._user_stream_queues:
                    self._user_stream_queues[user_id].put(user_exchange_update)

            self.logger.info(
                f"✅ SESSION SERVICE: Queued 1 BATCHED update (containing {len(update_data)} equity updates) for {len(self._active_streams)} active streams")

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: EXCEPTION in _on_market_data_update: {e}")
            import traceback
            print(f"🔥🔥🔥 SESSION SERVICE: Traceback:\n{traceback.format_exc()}")

    def _create_batched_exchange_update(self, update_data_list: List) -> ExchangeDataUpdate:
        """FIXED: Create a SINGLE ExchangeDataUpdate with ALL equity data batched together"""
        print(f"🔥🔥🔥 SESSION SERVICE: Creating BATCHED exchange update from {len(update_data_list)} market data items")

        try:
            update = ExchangeDataUpdate()

            # Set common fields from first update item
            first_update = update_data_list[0] if update_data_list else {}
            
            # Set timestamp from first market data item
            if 'timestamp' in first_update:
                timestamp_str = first_update['timestamp']
                try:
                    if isinstance(timestamp_str, str):
                        from dateutil.parser import parse
                        market_dt = parse(timestamp_str)
                        update.timestamp = int(market_dt.timestamp() * 1000)
                    else:
                        update.timestamp = int(timestamp_str)
                except:
                    update.timestamp = int(datetime.now().timestamp() * 1000)
            else:
                update.timestamp = int(datetime.now().timestamp() * 1000)

            # Set sequence number
            update.sequence_number = self._get_next_sequence()

            # Generate unique broadcast ID
            import uuid
            update.broadcast_id = str(uuid.uuid4())

            # FIXED: Add ALL equity data to the SAME message
            for market_data in update_data_list:
                if 'symbol' in market_data:
                    equity = update.equity_data.add()  # Add to repeated field
                    equity.symbol = market_data.get('symbol', '')
                    equity.open = float(market_data.get('open', 0))
                    equity.high = float(market_data.get('high', 0))
                    equity.low = float(market_data.get('low', 0))
                    equity.close = float(market_data.get('close', 0))
                    equity.volume = int(market_data.get('volume', 0))
                    equity.vwap = float(market_data.get('vwap', 0))
                    equity.currency = market_data.get('currency', 'USD')
                    
                    print(f"🔥🔥🔥 SESSION SERVICE: Added equity data for {equity.symbol}")

            print(f"🔥🔥🔥 SESSION SERVICE: BATCHED update contains {len(update.equity_data)} equity entries")

            # FIXED: Add complete exchange state for all users
            users = self.exchange_group_manager.get_all_users()

            for user_id in users:
                user_context = self.exchange_group_manager.user_contexts.get(user_id)
                if user_context and user_context.app_state:
                    # Use composite state manager if available
                    if self._composite_state_manager:
                        self._composite_state_manager.add_user_state(update, user_context)
                    else:
                        # Fallback to manual collection
                        self._add_complete_user_state_FIXED(update, user_context)

            print(f"🔥🔥🔥 SESSION SERVICE: COMPLETE exchange update created with seq#{update.sequence_number}")
            return update

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: EXCEPTION creating batched exchange update: {e}")
            import traceback
            print(f"🔥🔥🔥 SESSION SERVICE: Traceback:\n{traceback.format_exc()}")
            raise

    def _create_exchange_update_FIXED(self, market_data):
        """LEGACY METHOD - REPLACED BY _create_batched_exchange_update"""
        # This method is kept for compatibility but should no longer be used
        # The new batching approach is in _create_batched_exchange_update
        return self._create_batched_exchange_update([market_data])

    def _add_complete_user_state_FIXED(self, update, user_context):
        """FIXED: Add complete user state to the exchange update"""
        print(f"🔥🔥🔥 SESSION SERVICE: Adding COMPLETE state for user {user_context.user_id}")

        import source.orchestration.app_state.state_manager as app_state_module
        original_app_state = app_state_module.app_state

        try:
            app_state_module.app_state = user_context.app_state

            # Add all state components
            self._add_portfolio_state_FIXED(update, user_context.app_state)
            self._add_account_state_FIXED(update, user_context.app_state)
            self._add_order_state_FIXED(update, user_context.app_state)
            self._add_trade_state_FIXED(update, user_context.app_state)
            self._add_fx_state_FIXED(update, user_context.app_state)

        finally:
            app_state_module.app_state = original_app_state

    def _add_portfolio_state_FIXED(self, update, app_state):
        """FIXED: Add current portfolio state"""
        try:
            portfolio_manager = app_state.portfolio_manager
            if not portfolio_manager:
                return

            positions = portfolio_manager.get_all_positions()
            print(f"🔥🔥🔥 SESSION SERVICE: Found {len(positions)} portfolio positions")

            if positions:
                portfolio = update.portfolio
                portfolio.total_value = 0.0
                portfolio.cash_balance = 0.0
                portfolio.total_pnl = 0.0
                portfolio.unrealized_pnl = 0.0

                for symbol, position in positions.items():
                    # DEBUG: Print all available attributes
                    print(
                        f"🔥🔥🔥 SESSION SERVICE: Position {symbol} attributes: {[attr for attr in dir(position) if not attr.startswith('_')]}")

                    pos = portfolio.positions.add()
                    pos.symbol = symbol
                    pos.quantity = float(position.quantity)

                    # Handle average price/cost
                    avg_price = 0.0
                    for field_name in ['avg_price', 'average_price', 'price']:
                        if hasattr(position, field_name):
                            avg_price = float(getattr(position, field_name))
                            print(f"🔥🔥🔥 SESSION SERVICE: Found avg_price in '{field_name}': {avg_price}")
                            break
                    pos.average_cost = avg_price

                    # CRITICAL: Handle market value - check all possible field names
                    market_value = 0.0
                    for field_name in ['mtm_value', 'market_value', 'notional_value', 'current_value']:
                        if hasattr(position, field_name):
                            market_value = float(getattr(position, field_name))
                            print(f"🔥🔥🔥 SESSION SERVICE: Found market_value in '{field_name}': {market_value}")
                            break

                    if market_value == 0.0:
                        # Calculate market value if not found
                        market_value = float(position.quantity) * avg_price
                        print(f"🔥🔥🔥 SESSION SERVICE: Calculated market_value: {market_value}")

                    pos.market_value = market_value
                    pos.unrealized_pnl = float(getattr(position, 'unrealized_pnl', 0.0))
                    pos.realized_pnl = float(getattr(position, 'realized_pnl', 0.0))
                    pos.currency = getattr(position, 'currency', 'USD')

                    # Update portfolio totals
                    portfolio.total_value += market_value
                    portfolio.unrealized_pnl += pos.unrealized_pnl
                    portfolio.total_pnl += (pos.unrealized_pnl + pos.realized_pnl)

                print(f"🔥🔥🔥 SESSION SERVICE: Portfolio FINAL - total_value=${portfolio.total_value}")

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: Error adding portfolio state: {e}")
            import traceback
            print(f"🔥🔥🔥 SESSION SERVICE: Portfolio traceback: {traceback.format_exc()}")

    def _add_order_state_FIXED(self, update, app_state):
        """FIXED: Add current order state"""
        try:
            order_manager = app_state.order_manager
            if not order_manager:
                return

            orders = order_manager.get_all_orders()
            print(f"🔥🔥🔥 SESSION SERVICE: Found {len(orders)} orders")

            for order_id, order in orders.items():
                print(
                    f"🔥🔥🔥 SESSION SERVICE: Order {order_id} attributes: {[attr for attr in dir(order) if not attr.startswith('_')]}")

                order_msg = update.orders_data.add()
                order_msg.order_id = order_id
                order_msg.symbol = order.symbol
                order_msg.side = str(order.side.name if hasattr(order.side, 'name') else order.side)
                order_msg.quantity = float(order.remaining_qty)
                order_msg.price = float(order.price) if order.price else 0.0
                order_msg.order_type = str(
                    order.order_type.name if hasattr(order.order_type, 'name') else order.order_type)

                # FIXED: Get order status correctly
                if hasattr(order, 'status'):
                    order_msg.status = str(order.status.name if hasattr(order.status, 'name') else order.status)
                elif float(order.remaining_qty) <= 0:
                    order_msg.status = "COMPLETED"
                else:
                    order_msg.status = "WORKING"

                order_msg.timestamp = int(order.submit_timestamp.timestamp() * 1000)

                # Add additional fields
                if hasattr(order, 'cl_order_id'):
                    order_msg.cl_order_id = order.cl_order_id
                if hasattr(order, 'currency'):
                    order_msg.currency = order.currency
                if hasattr(order, 'original_qty'):
                    order_msg.original_qty = float(order.original_qty)
                if hasattr(order, 'remaining_qty'):
                    order_msg.remaining_qty = float(order.remaining_qty)

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: Error adding order state: {e}")

    def _add_trade_state_FIXED(self, update, app_state):
        """FIXED: Add recent trade state"""
        try:
            trade_manager = getattr(app_state, 'trade_manager', None)
            order_manager = getattr(app_state, 'order_manager', None)

            trades = []

            if trade_manager and hasattr(trade_manager, 'get_all_trades'):
                trades = trade_manager.get_all_trades()
            elif order_manager and hasattr(order_manager, 'get_all_trades'):
                trades = order_manager.get_all_trades()
            elif order_manager and hasattr(order_manager, 'trades'):
                trades = order_manager.trades

            print(f"🔥🔥🔥 SESSION SERVICE: Found {len(trades)} trades")

            for trade in trades:
                trade_msg = update.trades.add()
                trade_msg.trade_id = getattr(trade, 'trade_id', '')
                trade_msg.order_id = getattr(trade, 'order_id', '')
                trade_msg.symbol = getattr(trade, 'symbol', '')
                trade_msg.side = str(getattr(trade, 'side', ''))
                trade_msg.quantity = float(getattr(trade, 'quantity', 0.0))
                trade_msg.price = float(getattr(trade, 'price', 0.0))
                trade_msg.currency = getattr(trade, 'currency', 'USD')

                timestamp = getattr(trade, 'timestamp', None)
                if timestamp:
                    trade_msg.timestamp = int(timestamp.timestamp() * 1000)

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: Error adding trade state: {e}")

    def _add_account_state_FIXED(self, update, app_state):
        """FIXED: Add current account state"""
        try:
            account_manager = app_state.account_manager
            if not account_manager:
                return

            balances = account_manager.get_all_balances()
            accounts = update.accounts
            accounts.base_currency = "USD"

            if hasattr(account_manager, 'get_nav'):
                nav = account_manager.get_nav()
                accounts.nav = float(nav) if nav else 0.0

            for account_type, currency_balances in balances.items():
                for currency, balance in currency_balances.items():
                    bal = accounts.balances.add()
                    bal.type = account_type
                    bal.currency = currency
                    bal.amount = float(balance.amount)

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: Error adding account state: {e}")

    def _add_fx_state_FIXED(self, update, app_state):
        """FIXED: Add current FX state"""
        try:
            fx_manager = app_state.fx_manager
            if not fx_manager:
                return

            fx_rates = fx_manager.get_all_rates()
            for rate_key, rate_value in fx_rates.items():
                fx_rate = update.fx_rates.rates.add()
                if '/' in str(rate_key):
                    from_curr, to_curr = str(rate_key).split('/')
                    fx_rate.from_currency = from_curr
                    fx_rate.to_currency = to_curr
                fx_rate.rate = float(rate_value)

        except Exception as e:
            print(f"🔥🔥🔥 SESSION SERVICE: Error adding FX state: {e}")

    def Heartbeat(self, request: HeartbeatRequest, context: grpc.ServicerContext) -> HeartbeatResponse:
        """Enhanced heartbeat with session status information"""
        try:
            self.logger.info(f"🏥 HEARTBEAT: Received heartbeat request from user {request.user_id}")
            
            response = HeartbeatResponse()
            response.status = "OK"
            response.timestamp = int(datetime.now().timestamp() * 1000)
            response.current_bin = "live"  # or get from your state manager
            response.next_bin = "next"
            response.market_state = "OPEN"
            
            # Optional: Add connection info
            if hasattr(response, 'connection_info') and response.connection_info:
                response.connection_info.active_connections = 1
                response.connection_info.next_expected_sequence = 0
                response.connection_info.last_sent_timestamp = response.timestamp
                response.connection_info.is_primary_connection = True
            
            self.logger.info(f"🏥 HEARTBEAT: Responding with status {response.status} for user {request.user_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"❌ HEARTBEAT: Error processing heartbeat for user {request.user_id}: {e}")
            
            response = HeartbeatResponse()
            response.status = "ERROR"
            response.timestamp = int(datetime.now().timestamp() * 1000)
            response.current_bin = "unknown"
            response.next_bin = "unknown"
            response.market_state = "UNKNOWN"
            
            return response

    def stop(self):
        """Stop the session service"""
        if self.server and self.running:
            self.logger.info("🛑 SESSION SERVICE: Stopping gRPC server")
            self.server.stop(grace=5)
            self.running = False
            self.logger.info("✅ SESSION SERVICE: Stopped")