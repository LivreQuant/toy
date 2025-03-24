import time
import threading
import uuid
import logging
from typing import Dict, List, Any, Optional, Set
import asyncio

from source.config import Config
from source.models.session import SessionInfo, SessionStatus
from source.simulator.market_data import MarketDataGenerator
from source.simulator.portfolio_manager import PortfolioManager
from source.simulator.order_manager import OrderManager

logger = logging.getLogger(__name__)


class SimulatorStatus:
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class ExchangeSimulator:
    def __init__(self):
        self.simulator_id = str(uuid.uuid4())
        self.status = SimulatorStatus.AVAILABLE
        self.running = True

        # Initialize components
        self.market_data = MarketDataGenerator(Config.DEFAULT_SYMBOLS)
        self.portfolio_manager = PortfolioManager()
        self.order_manager = OrderManager(self.portfolio_manager, self.market_data)

        # Session management
        self.sessions = {}  # session_id -> SessionInfo
        self.session_connections = {}  # session_id -> list of connections

        # Thread safety
        self.lock = threading.RLock()

        # Start background processing threads
        self._start_background_threads()

        logger.info(f"Exchange simulator {self.simulator_id} initialized")

    def _start_background_threads(self):
        """Start background processing threads"""
        # Market data processing thread
        self.market_thread = threading.Thread(
            target=self._run_market_updates,
            daemon=True
        )
        self.market_thread.start()

        # Cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._run_cleanup,
            daemon=True
        )
        self.cleanup_thread.start()

    def _run_market_updates(self):
        """Run market data updates"""
        while self.running:
            try:
                # Update market prices
                self.market_data.update_prices()

                # Update portfolio market values
                self._update_portfolio_values()

                # Generate random orders
                self._generate_random_orders()

                # Send updates to connected clients
                self._send_updates_to_clients()

                # Sleep until next update
                time.sleep(Config.MARKET_UPDATE_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Error in market update: {e}")
                time.sleep(1.0)  # Sleep longer on error

    def _run_cleanup(self):
        """Run cleanup of inactive sessions"""
        while self.running:
            try:
                # Sleep first to avoid immediate cleanup
                time.sleep(30)

                with self.lock:
                    # Find inactive sessions
                    inactive_sessions = []
                    for session_id, session in self.sessions.items():
                        if session.is_inactive(Config.INACTIVITY_TIMEOUT_SECONDS):
                            inactive_sessions.append(session_id)
                            logger.info(f"Session {session_id} inactive for {Config.INACTIVITY_TIMEOUT_SECONDS}s")

                    # Remove inactive sessions
                    for session_id in inactive_sessions:
                        self._remove_session(session_id)

                    # Check if simulator should shut down
                    if not self.sessions and Config.AUTO_TERMINATE:
                        logger.info("No active sessions and auto-terminate enabled, shutting down")
                        self.status = SimulatorStatus.SHUTTING_DOWN
                        self.running = False
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")

    def _update_portfolio_values(self):
        """Update portfolio values based on current prices"""
        for session_id in self.sessions:
            portfolio = self.portfolio_manager.get_portfolio(session_id)
            if not portfolio:
                continue

            # Update market value for each position
            for symbol, position in list(portfolio['positions'].items()):
                price = self.market_data.get_price(symbol)
                self.portfolio_manager.update_position_market_value(
                    session_id, symbol, price)

    def _generate_random_orders(self):
        """Generate random orders for active sessions"""
        for session_id in list(self.sessions.keys()):
            self.order_manager.create_random_order(session_id)

    def _send_updates_to_clients(self):
        """Send updates to all connected clients"""
        for session_id, connections in list(self.session_connections.items()):
            if not connections:
                continue

            # Create update data
            update_data = self._create_update_data(session_id)

            # Send to each connection
            for conn in list(connections):
                try:
                    # In a real implementation, this would send the data via gRPC
                    context = conn.get('context')
                    if context and hasattr(context, 'write') and context.is_active():
                        # This is a placeholder for the actual gRPC write
                        pass
                except Exception as e:
                    logger.error(f"Error sending update to client: {e}")

    def _create_update_data(self, session_id):
        """Create update data for a session"""
        # Get portfolio
        portfolio = self.portfolio_manager.get_portfolio(session_id)

        # Get recent orders
        recent_orders = self.order_manager.get_recent_orders(session_id)

        # Get market data
        market_data = self.market_data.get_market_data()

        return {
            'timestamp': int(time.time() * 1000),
            'market_data': market_data,
            'order_updates': recent_orders,
            'portfolio': portfolio
        }

    def start_session(self, session_id, user_id, symbols=None, initial_cash=None):
        """Start a session"""
        with self.lock:
            # Check if already active
            if session_id in self.sessions:
                # Update activity time
                self.sessions[session_id].update_activity()
                logger.info(f"Session {session_id} already active, updated activity")
                return True, self.simulator_id, ""

            # Check simulator status
            if self.status != SimulatorStatus.AVAILABLE and len(self.sessions) > 0:
                logger.warning(f"Simulator not available, status: {self.status}")
                return False, "", f"Simulator not available, status: {self.status}"

            # Create session
            self.sessions[session_id] = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                symbols=symbols or self.market_data.symbols
            )

            # Create portfolio
            initial_cash = initial_cash or Config.DEFAULT_INITIAL_CASH
            self.portfolio_manager.create_portfolio(session_id, initial_cash)

            # Update simulator status
            self.status = SimulatorStatus.ACTIVE

            logger.info(f"Started session {session_id} for user {user_id}")
            return True, self.simulator_id, ""

    def stop_session(self, session_id):
        """Stop a session"""
        with self.lock:
            if session_id not in self.sessions:
                logger.warning(f"Session {session_id} not found")
                return False, "Session not found"

            # Remove session
            self._remove_session(session_id)

            logger.info(f"Stopped session {session_id}")
            return True, ""

    def _remove_session(self, session_id):
        """Remove a session and its data"""
        # Remove session
        if session_id in self.sessions:
            del self.sessions[session_id]

        # Remove portfolio
        self.portfolio_manager.remove_portfolio(session_id)

        # Clear orders
        self.order_manager.clear_session_orders(session_id)

        # Remove connections
        if session_id in self.session_connections:
            del self.session_connections[session_id]

        # Update status if no more sessions
        if not self.sessions:
            self.status = SimulatorStatus.AVAILABLE

    def register_connection(self, session_id, client_id, context, symbols=None):
        """Register a new client connection for a session"""
        with self.lock:
            # Check if session exists
            if session_id not in self.sessions:
                logger.warning(f"Cannot register connection: Session {session_id} not found")
                return False

            # Update session activity
            self.sessions[session_id].update_activity()

            # Create connection info
            connection_info = {
                'client_id': client_id,
                'context': context,
                'symbols': symbols,
                'connected_at': time.time(),
                'last_update': time.time()
            }

            # Add to connections
            if session_id not in self.session_connections:
                self.session_connections[session_id] = []

            self.session_connections[session_id].append(connection_info)

            logger.info(f"Registered connection for session {session_id}, client {client_id}")
            return True

    def unregister_connection(self, session_id, context):
        """Unregister a client connection for a session"""
        with self.lock:
            if session_id not in self.session_connections:
                return

            # Remove connection
            self.session_connections[session_id] = [
                conn for conn in self.session_connections[session_id]
                if conn.get('context') != context
            ]

            # Update session activity time
            if session_id in self.sessions:
                self.sessions[session_id].update_activity()

    def update_session_activity(self, session_id):
        """Update the activity time for a session"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].update_activity()
                return True
            return False

    def shutdown(self):
        """Shutdown the simulator"""
        logger.info("Shutting down exchange simulator")
        self.running = False
        self.status = SimulatorStatus.SHUTTING_DOWN
