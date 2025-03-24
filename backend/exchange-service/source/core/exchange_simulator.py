import asyncio
import logging
import time
import uuid
import threading
from typing import Dict, List, Any, Optional, Set

from source.core.market_data import MarketDataGenerator
from source.core.portfolio_manager import PortfolioManager
from source.core.order_manager import OrderManager
from source.utils.config import config
from source.utils.metrics import Metrics

logger = logging.getLogger(__name__)
metrics = Metrics()

class SimulatorStatus:
    """Simulator status constants"""
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    SHUTTING_DOWN = "SHUTTING_DOWN"

class ExchangeSimulator:
    """Exchange simulator main class"""
    
    def __init__(self):
        """Initialize the exchange simulator"""
        self.simulator_id = str(uuid.uuid4())
        self.status = SimulatorStatus.AVAILABLE
        self.running = True

        # Initialize components
        self.market_data = MarketDataGenerator(config.default_symbols)
        self.portfolio_manager = PortfolioManager()
        self.order_manager = OrderManager(self.portfolio_manager, self.market_data)

        # Session management
        self.sessions = {}  # session_id -> session info
        self.session_connections = {}  # session_id -> list of connections

        # Thread safety
        self.lock = threading.RLock()

        # Start background processing threads
        self._start_background_threads()

        # Set up metrics
        metrics.set_gauge("simulator_status", 1, {"status": self.status})
        metrics.increment_counter("simulator_created")
        
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
                time.sleep(config.market_update_interval_seconds)
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
                        if time.time() - session['last_active'] > config.inactivity_timeout_seconds:
                            inactive_sessions.append(session_id)
                            logger.info(f"Session {session_id} inactive for {config.inactivity_timeout_seconds}s")

                    # Remove inactive sessions
                    for session_id in inactive_sessions:
                        self._remove_session(session_id)

                    # Check if simulator should shut down
                    if not self.sessions and config.auto_terminate:
                        logger.info("No active sessions and auto-terminate enabled, shutting down")
                        self.status = SimulatorStatus.SHUTTING_DOWN
                        metrics.set_gauge("simulator_status", 1, {"status": self.status})
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
            for symbol in list(portfolio.positions.keys()):
                price = self.market_data.get_price(symbol)
                self.portfolio_manager.update_position_market_value(session_id, symbol, price)

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
        if not portfolio:
            return {
                'timestamp': int(time.time() * 1000),
                'market_data': [],
                'order_updates': [],
                'portfolio': None
            }

        # Get recent orders
        recent_orders = self.order_manager.get_recent_orders(session_id)

        # Get market data for symbols in portfolio
        symbols = list(portfolio.positions.keys())
        market_data = self.market_data.get_market_data(symbols)

        return {
            'timestamp': int(time.time() * 1000),
            'market_data': market_data,
            'order_updates': recent_orders,
            'portfolio': portfolio.to_proto_format()
        }

    def start_session(self, session_id: str, user_id: str, initial_symbols: Optional[List[str]] = None, initial_cash: Optional[float] = None) -> tuple:
        """
        Start a session
        
        Args:
            session_id: The session ID
            user_id: The user ID
            initial_symbols: Optional list of initial symbols to track
            initial_cash: Optional initial cash amount
            
        Returns:
            Tuple of (success, simulator_id, error_message)
        """
        with self.lock:
            # Check if already active
            if session_id in self.sessions:
                # Update activity time
                self.sessions[session_id]['last_active'] = time.time()
                logger.info(f"Session {session_id} already active, updated activity")
                return True, self.simulator_id, ""

            # Check simulator status
            if self.status != SimulatorStatus.AVAILABLE and len(self.sessions) > 0:
                logger.warning(f"Simulator not available, status: {self.status}")
                return False, "", f"Simulator not available, status: {self.status}"

            # Create session
            self.sessions[session_id] = {
                'user_id': user_id,
                'created_at': time.time(),
                'last_active': time.time(),
                'symbols': initial_symbols or self.market_data.symbols
            }

            # Create portfolio
            self.portfolio_manager.create_portfolio(
                session_id,
                user_id,
                initial_cash or config.default_initial_cash
            )

            # Update simulator status
            self.status = SimulatorStatus.ACTIVE
            metrics.set_gauge("simulator_status", 1, {"status": self.status})
            metrics.increment_counter("session_started")

            logger.info(f"Started session {session_id} for user {user_id}")
            return True, self.simulator_id, ""

    def stop_session(self, session_id: str) -> tuple:
        """
        Stop a session
        
        Args:
            session_id: The session ID
            
        Returns:
            Tuple of (success, error_message)
        """
        with self.lock:
            if session_id not in self.sessions:
                logger.warning(f"Session {session_id} not found")
                return False, "Session not found"

            # Remove session
            self._remove_session(session_id)

            logger.info(f"Stopped session {session_id}")
            metrics.increment_counter("session_stopped")
            return True, ""

    def _remove_session(self, session_id: str):
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
            metrics.set_gauge("simulator_status", 1, {"status": self.status})

    def register_stream(self, session_id: str, client_id: str, context: Any) -> bool:
        """
        Register a new stream connection for a session
        
        Args:
            session_id: The session ID
            client_id: Client identifier
            context: gRPC context for the stream
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Check if session exists
            if session_id not in self.sessions:
                logger.warning(f"Cannot register stream: Session {session_id} not found")
                return False

            # Update session activity
            self.sessions[session_id]['last_active'] = time.time()

            # Create connection info
            connection_info = {
                'client_id': client_id,