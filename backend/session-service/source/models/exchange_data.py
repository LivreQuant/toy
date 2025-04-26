# source/models/exchange_data.py
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import uuid


class ExchangeType(str, Enum):
    """Type of exchange"""
    EQUITIES = "EQUITIES"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITIES = "COMMODITIES"
    GENERIC = "GENERIC"


class OrderSide(str, Enum):
    """Order side enum"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enum"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    """Order status enum"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class MarketDataItem(BaseModel):
    """Standardized market data item"""
    symbol: str
    bid: float
    ask: float
    bid_size: int = 0
    ask_size: int = 0
    last_price: Optional[float] = None
    last_size: Optional[int] = None
    exchange_type: ExchangeType = ExchangeType.GENERIC
    
    # Additional fields for different exchange types
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderItem(BaseModel):
    """Standardized order item"""
    order_id: str
    symbol: str
    status: str
    filled_quantity: int = 0
    average_price: float = 0
    exchange_type: ExchangeType = ExchangeType.GENERIC
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionItem(BaseModel):
    """Standardized position item"""
    symbol: str
    quantity: int = 0
    average_cost: float = 0
    market_value: float = 0
    exchange_type: ExchangeType = ExchangeType.GENERIC
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioItem(BaseModel):
    """Standardized portfolio status"""
    positions: List[PositionItem] = Field(default_factory=list)
    cash_balance: float = 0
    total_value: float = 0
    exchange_type: ExchangeType = ExchangeType.GENERIC
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExchangeDataUpdate(BaseModel):
    """Standardized exchange data update"""
    update_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    exchange_type: ExchangeType = ExchangeType.GENERIC
    
    market_data: List[MarketDataItem] = Field(default_factory=list)
    orders: List[OrderItem] = Field(default_factory=list)
    portfolio: Optional[PortfolioItem] = None
    
    # Allow for exchange-specific extensions
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization to clients"""
        return {
            "updateId": self.update_id,
            "timestamp": self.timestamp,
            "exchangeType": self.exchange_type,
            "marketData": [item.dict() for item in self.market_data],
            "orders": [order.dict() for order in self.orders],
            "portfolio": self.portfolio.dict() if self.portfolio else None,
            "metadata": self.metadata
        }