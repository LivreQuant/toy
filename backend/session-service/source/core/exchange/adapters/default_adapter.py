# source/core/exchange/adapters/default_adapter.py
from typing import Dict, Any

from source.core.exchange.adapter import ExchangeAdapter
from source.models.exchange_data import (
    ExchangeDataUpdate, ExchangeType, MarketDataItem, 
    OrderItem, PositionItem, PortfolioItem
)
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate as GrpcExchangeDataUpdate

class DefaultExchangeAdapter(ExchangeAdapter):
    """Adapter for the default exchange simulator"""
    
    async def convert_from_protobuf(self, protobuf_data: GrpcExchangeDataUpdate) -> ExchangeDataUpdate:
        """Convert protobuf message directly to standardized format in one step"""
        
        # Create the base exchange data update
        exchange_data = ExchangeDataUpdate(
            timestamp=protobuf_data.timestamp,
            exchange_type=ExchangeType.EQUITIES,  # Default to equities for existing simulator
        )
        
        # Convert market data
        for item in protobuf_data.market_data:
            exchange_data.market_data.append(
                MarketDataItem(
                    symbol=item.symbol,
                    open=item.open,
                    high=item.high,
                    low=item.low,
                    close=item.close,
                    volume=item.volume,
                    trade_count=item.trade_count,
                    vwap=item.vwap,
                )
            )
        
        # Convert order updates
        for item in protobuf_data.orders_data:
            exchange_data.orders.append(
                OrderItem(
                    order_id=item.order_id,
                    symbol=item.symbol,
                    status=item.status,
                    filled_quantity=item.filled_quantity,
                    average_price=item.average_price,
                )
            )
        
        # Convert portfolio if present
        if protobuf_data.HasField('portfolio'):
            portfolio = protobuf_data.portfolio
            positions = []
            for pos in portfolio.positions:
                positions.append(
                    PositionItem(
                        symbol=pos.symbol,
                        quantity=pos.quantity,
                        average_cost=pos.average_cost,
                        market_value=pos.market_value,
                    )
                )
            
            exchange_data.portfolio = PortfolioItem(
                positions=positions,
                cash_balance=portfolio.cash_balance,
                total_value=portfolio.total_value,
            )
            
        return exchange_data
    