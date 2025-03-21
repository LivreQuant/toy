# exchange_simulator.py
import time
import uuid
import random
import threading
import logging
from concurrent import futures
import grpc

import exchange_pb2
import exchange_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('exchange_simulator')

class ExchangeSimulator(exchange_pb2_grpc.ExchangeSimulatorServicer):
    def __init__(self):
        self.active_sessions = {}  # session_id -> client_connections
        self.symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        self.symbol_prices = {
            "AAPL": 175.0,
            "MSFT": 350.0,
            "GOOGL": 140.0,
            "AMZN": 130.0,
            "TSLA": 200.0
        }
        self.orders = {}  # order_id -> order_info
        self.portfolios = {}  # session_id -> portfolio_data
        self.lock = threading.RLock()
        
        # Start data processor
        self.running = True
        self.data_thread = threading.Thread(target=self._process_exchange_data)
        self.data_thread.daemon = True
        self.data_thread.start()
    
    def StreamExchangeData(self, request, context):
        """Stream complete exchange data for a session"""
        session_id = request.session_id
        client_id = request.client_id
        requested_symbols = list(request.symbols) or self.symbols
        
        logger.info(f"Exchange data stream requested for session {session_id}, client {client_id}")
        
        # Create client connection entry
        connection_info = {
            'client_id': client_id,
            'symbols': requested_symbols,
            'context': context,
            'last_update': time.time()
        }
        
        # Register this connection
        with self.lock:
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = []
                
                # Initialize empty portfolio for new session
                if session_id not in self.portfolios:
                    self.portfolios[session_id] = {
                        'cash_balance': 100000.0,
                        'positions': {}
                    }
            
            # Add connection to session
            self.active_sessions[session_id].append(connection_info)
        
        # Setup stream termination handler
        def on_rpc_done():
            with self.lock:
                if session_id in self.active_sessions:
                    # Remove this connection
                    self.active_sessions[session_id] = [
                        conn for conn in self.active_sessions[session_id] 
                        if conn.get('context') != context
                    ]
                    
                    # If no more connections for this session, clean up
                    if not self.active_sessions[session_id]:
                        logger.info(f"No more connections for session {session_id}, removing session")
                        del self.active_sessions[session_id]
                        
                        # In a real system, we might keep the portfolio data for reconnection
                        # For this example, we'll clean it up
                        if session_id in self.portfolios:
                            del self.portfolios[session_id]
        
        context.add_callback(on_rpc_done)
        
        # Keep connection alive and send initial data
        try:
            # Send initial complete update
            self._send_complete_update_to_session(session_id)
            
            # Keep stream open
            while context.is_active() and self.running:
                # In a real implementation, we might have backpressure handling here
                time.sleep(60)  # This is just to keep the stream open
        except Exception as e:
            logger.error(f"Error in exchange data stream for {session_id}/{client_id}: {e}")
        
        return  # Stream ends when client disconnects
    
    def Heartbeat(self, request, context):
        """Process heartbeat request to keep session alive"""
        session_id = request.session_id
        client_id = request.client_id
        client_timestamp = request.client_timestamp
        
        # Update last active timestamp for this session/client
        with self.lock:
            if session_id in self.active_sessions:
                for conn in self.active_sessions[session_id]:
                    if conn.get('client_id') == client_id:
                        conn['last_update'] = time.time()
        
        return exchange_pb2.HeartbeatResponse(
            success=True,
            server_timestamp=int(time.time() * 1000)
        )
    
    def _process_exchange_data(self):
        """Main processing thread for exchange data"""
        data_update_interval = 1.0  # seconds
        last_update_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Only update at specified interval
                if current_time - last_update_time >= data_update_interval:
                    last_update_time = current_time
                    
                    # 1. Update market prices
                    self._update_market_prices()
                    
                    # 2. Process simulated orders
                    self._process_simulated_orders()
                    
                    # 3. Send complete updates to all active sessions
                    self._broadcast_updates_to_all_sessions()
                
                # Sleep a small amount to prevent CPU hogging
                time.sleep(0.01)
            
            except Exception as e:
                logger.error(f"Error in exchange data processing: {e}")
                time.sleep(1.0)  # Sleep longer on error
    
    def _update_market_prices(self):
        """Update market prices for all symbols"""
        with self.lock:
            for symbol in self.symbols:
                # Random price movement
                price = self.symbol_prices[symbol]
                price_change = price * (random.random() * 0.01 - 0.005)  # -0.5% to +0.5%
                new_price = max(0.01, price + price_change)
                self.symbol_prices[symbol] = new_price
                
                # Update portfolio values based on new prices
                for session_id, portfolio in self.portfolios.items():
                    if symbol in portfolio['positions']:
                        position = portfolio['positions'][symbol]
                        position['market_value'] = position['quantity'] * new_price
    
    def _process_simulated_orders(self):
        """Simulate some order activity"""
        # Only simulate for sessions that have been active for a while
        with self.lock:
            for session_id in list(self.active_sessions.keys()):
                # 10% chance of creating a simulated order
                if random.random() < 0.1:
                    symbol = random.choice(self.symbols)
                    is_buy = random.choice([True, False])
                    quantity = random.randint(1, 10) * 10  # 10, 20, ..., 100
                    price = self.symbol_prices[symbol]
                    
                    # Create order update
                    order_id = str(uuid.uuid4())
                    self.orders[order_id] = {
                        'session_id': session_id,
                        'symbol': symbol,
                        'side': 'BUY' if is_buy else 'SELL',
                        'quantity': quantity,
                        'price': price,
                        'status': 'FILLED',  # Simplification - all orders fill immediately
                        'filled_quantity': quantity,
                        'average_price': price,
                        'timestamp': time.time()
                    }
                    
                    # Update portfolio
                    if session_id in self.portfolios:
                        portfolio = self.portfolios[session_id]
                        
                        # Update cash
                        trade_value = quantity * price
                        if is_buy:
                            portfolio['cash_balance'] -= trade_value
                        else:
                            portfolio['cash_balance'] += trade_value
                        
                        # Update position
                        if symbol not in portfolio['positions']:
                            portfolio['positions'][symbol] = {
                                'quantity': 0,
                                'average_cost': 0,
                                'market_value': 0
                            }
                        
                        position = portfolio['positions'][symbol]
                        
                        if is_buy:
                            # Buying - add to position
                            new_quantity = position['quantity'] + quantity
                            new_cost_basis = (
                                (position['quantity'] * position['average_cost']) + 
                                (quantity * price)
                            ) / new_quantity if new_quantity > 0 else 0
                            
                            position['quantity'] = new_quantity
                            position['average_cost'] = new_cost_basis
                            position['market_value'] = new_quantity * price
                        else:
                            # Selling - reduce position
                            position['quantity'] -= quantity
                            position['market_value'] = position['quantity'] * price
                            
                            # Remove if quantity is zero or negative (simplification)
                            if position['quantity'] <= 0:
                                del portfolio['positions'][symbol]
    
    def _broadcast_updates_to_all_sessions(self):
        """Send complete updates to all active sessions"""
        with self.lock:
            for session_id in list(self.active_sessions.keys()):
                self._send_complete_update_to_session(session_id)
    
    def _send_complete_update_to_session(self, session_id):
        """Create and send a complete data update to a specific session"""
        with self.lock:
            if session_id not in self.active_sessions:
                return
            
            # Get connections for this session
            connections = self.active_sessions[session_id]
            if not connections:
                return
            
            # Get all symbols requested by any connection for this session
            requested_symbols = set()
            for conn in connections:
                symbols = conn.get('symbols', [])
                requested_symbols.update(symbols)
            
            # If no specific symbols requested, use all symbols
            if not requested_symbols:
                requested_symbols = set(self.symbols)
            
            # Gather market data
            market_data_list = []
            for symbol in requested_symbols:
                if symbol in self.symbol_prices:
                    price = self.symbol_prices[symbol]
                    bid = price - random.random() * 0.02  # Small random spread
                    ask = price + random.random() * 0.02
                    
                    market_data_list.append(exchange_pb2.MarketData(
                        symbol=symbol,
                        bid=bid,
                        ask=ask,
                        bid_size=random.randint(100, 1000),
                        ask_size=random.randint(100, 1000),
                        last_price=price,
                        last_size=random.randint(10, 100)
                    ))
            
            # Gather recent order updates
            order_updates = []
            for order_id, order in list(self.orders.items()):
                if order.get('session_id') == session_id:
                    # Only include recent orders from the last 10 seconds
                    if time.time() - order.get('timestamp', 0) < 10:
                        order_updates.append(exchange_pb2.OrderUpdate(
                            order_id=order_id,
                            symbol=order['symbol'],
                            status=order['status'],
                            filled_quantity=order['filled_quantity'],
                            average_price=order['average_price']
                        ))
            
            # Get portfolio status
            portfolio_status = None
            if session_id in self.portfolios:
                portfolio = self.portfolios[session_id]
                positions = []
                
                for symbol, pos in portfolio['positions'].items():
                    positions.append(exchange_pb2.Position(
                        symbol=symbol,
                        quantity=pos['quantity'],
                        average_cost=pos['average_cost'],
                        market_value=pos['market_value']
                    ))
                
                total_value = portfolio['cash_balance']
                for pos in portfolio['positions'].values():
                    total_value += pos['market_value']
                
                portfolio_status = exchange_pb2.PortfolioStatus(
                    positions=positions,
                    cash_balance=portfolio['cash_balance'],
                    total_value=total_value
                )
            
            # Create complete update
            update = exchange_pb2.ExchangeDataUpdate(
                timestamp=int(time.time() * 1000),
                market_data=market_data_list,
                order_updates=order_updates,
                portfolio=portfolio_status or exchange_pb2.PortfolioStatus()
            )
            
            # Send update to all connections for this session
            for conn in list(connections):
                try:
                    conn['context'].write(update)
                except Exception as e:
                    logger.error(f"Error sending update to session {session_id}: {e}")
                    # Don't remove the connection here - let the gRPC framework handle disconnects
    
    def shutdown(self):
        """Cleanup when shutting down"""
        self.running = False
        if self.data_thread.is_alive():
            self.data_thread.join(timeout=2)


def serve():
    """Start the exchange simulator server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulator = ExchangeSimulator()
    exchange_pb2_grpc.add_ExchangeSimulatorServicer_to_server(simulator, server)
    
    # Listen on all interfaces
    server.add_insecure_port('[::]:50055')
    server.start()
    
    logger.info("Exchange Simulator started on port 50055")
    
    try:
        while True:
            time.sleep(86400)  # Sleep for a day
    except KeyboardInterrupt:
        logger.info("Shutting down Exchange Simulator")
        simulator.shutdown()
        server.stop(0)


if __name__ == '__main__':
    serve()