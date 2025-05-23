from enum import Enum


class Side(str, Enum):
    """Side enum"""
    BUY = "BUY"
    SELL = "SELL"


class ErrorCode(str, Enum):
    """Error codes for API responses"""
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
