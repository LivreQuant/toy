import logging
import time
import uuid
import grpc
import asyncio
import random
from typing import AsyncGenerator

from source.api.grpc.exchange_simulator_pb2 import (
    StartSimulatorResponse,
    StopSimulatorResponse,
    HeartbeatResponse,
    ExchangeDataUpdate,
    MarketData,
    Position,
    PortfolioStatus
)
from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorServicer

from source.core.market_data import MarketDataGenerator
from source.core.order_manager import OrderManager
from source.core.portfolio_manager import PortfolioManager
from source.models.enums import OrderSide, OrderType, OrderStatus
from source.config import config

logger = logging.getLogger(__name__)

class ExchangeSimulatorService(ExchangeSimulatorServicer):
    def __init__(
        self, 
        market_data: MarketDataGenerator, 
        order_manager: OrderManager,
        portfolio_manager: PortfolioManager
    ):
        self.market_data = market_data
        self.order_manager = order_manager
        self.portfolio_manager = portfolio_manager
        self.active_sessions = {}

    async def StartSimulator(self, request, context):
        """Start a simulator for a specific session"""
        session_id = request.session_id
        user_id = request.user_id
        initial_symbols = list(request.initial_symbols) or config.simulator.default_symbols
        initial_cash = request.initial_cash or config.simulator.initial_cash

        # Create portfolio
        self.portfolio_manager.create_portfolio(session_id, user_id, initial_cash)

        # Track session
        simulator_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'simulator_id': simulator_id,
            'created_at': time.time()
        }

        return StartSimulatorResponse(
            success=True,
            simulator_id=simulator_id
        )

    async def StopSimulator(self, request, context):
        """Stop a simulator"""
        session_id = request.session_id

        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return StopSimulatorResponse(success=True)
        
        return StopSimulatorResponse(
            success=False, 
            error_message="Session not found"
        )
        
    async def Heartbeat(self, request, context):
        """
        Heartbeat to verify connection
        
        Enhanced to track session service connection health
        """
        session_id = request.session_id
        client_id = request.client_id
        client_timestamp = request.client_timestamp
        
        # Update last heartbeat time for TTL checking
        self.last_session_heartbeat = time.time()
        
        # Check if session exists (optional validation)
        if session_id not in self.active_sessions:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Session {session_id} not found")
            return HeartbeatResponse(
                success=False,
                server_timestamp=int(time.time() * 1000)
            )
        
        # Log periodic heartbeats at debug level
        if hasattr(self, 'heartbeat_counter'):
            self.heartbeat_counter += 1
            if self.heartbeat_counter % 10 == 0:  # Log every 10th heartbeat
                logger.debug(f"Received heartbeat #{self.heartbeat_counter} for session {session_id}")
        else:
            self.heartbeat_counter = 1
            logger.info(f"Received first heartbeat for session {session_id}")
        
        return HeartbeatResponse(
            success=True,
            server_timestamp=int(time.time() * 1000)
        )

    async def StreamExchangeData(
        self, 
        request, 
        context
    ) -> AsyncGenerator[ExchangeDataUpdate, None]:
        """Stream market data and portfolio updates"""
        session_id = request.session_id
        symbols = list(request.symbols) or config.simulator.default_symbols

        # Validate session
        if session_id not in self.active_sessions:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Session not found")
            return

        # Periodic market data and portfolio update stream
        try:
            while True:
                # Update market prices
                self.market_data.update_prices()
                market_prices = self.market_data.get_market_data(symbols)

                # Get portfolio
                portfolio = self.portfolio_manager.get_portfolio(session_id)
                
                # Prepare data update
                update = ExchangeDataUpdate(
                    timestamp=int(time.time() * 1000)
                )

                # Add market data
                for market_data in market_prices:
                    pb_market_data = MarketData(
                        symbol=market_data['symbol'],
                        bid=market_data['bid'],
                        ask=market_data['ask'],
                        bid_size=market_data['bid_size'],
                        ask_size=market_data['ask_size'],
                        last_price=market_data['last_price'],
                        last_size=market_data['last_size']
                    )
                    update.market_data.append(pb_market_data)

                # Optional: Periodic random trade generation
                if random.random() < 0.2:  # 20% chance of random trade
                    random_symbol = random.choice(symbols)
                    random_side = random.choice(list(OrderSide))
                    order = self.order_manager.submit_order(
                        session_id=session_id,
                        symbol=random_symbol,
                        side=random_side,
                        quantity=random.uniform(1, 10),
                        order_type=OrderType.MARKET
                    )

                # Add order updates and portfolio
                if portfolio:
                    # Add portfolio data
                    portfolio_pb = PortfolioStatus(
                        cash_balance=portfolio.cash_balance,
                        total_value=portfolio.get_total_value(
                            {md['symbol']: md['last_price'] for md in market_prices}
                        )
                    )

                    # Add positions
                    for symbol, position in portfolio.positions.items():
                        position_pb = Position(
                            symbol=symbol,
                            quantity=int(position['quantity']),
                            average_cost=position['avg_cost'],
                            market_value=position['quantity'] * 
                                next((md['last_price'] for md in market_prices if md['symbol'] == symbol), 0)
                        )
                        portfolio_pb.positions.append(position_pb)

                    update.portfolio.CopyFrom(portfolio_pb)

                yield update
                await asyncio.sleep(1)  # Update interval

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")