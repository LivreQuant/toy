from enum import Enum, auto

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