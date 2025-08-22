# source/simulation/managers/models.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict
from datetime import datetime


@dataclass
class EquityBar:
    symbol: str
    timestamp: str
    currency: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    count: int
    vwap: Decimal
    vwas: Decimal
    vwav: Decimal

    def __init__(self, symbol: str, timestamp: str, currency: str, open: float, high: float,
                 low: float, close: float, volume: int, count: int, vwap: float, vwas: float, vwav: float):
        self.symbol = symbol
        self.timestamp = timestamp
        self.currency = currency
        self.open = Decimal(str(open))
        self.high = Decimal(str(high))
        self.low = Decimal(str(low))
        self.close = Decimal(str(close))
        self.volume = volume
        self.count = count
        self.vwap = Decimal(str(vwap))
        self.vwas = Decimal(str(vwas))
        self.vwav = Decimal(str(vwav))


@dataclass
class EquityState:
    last_update_time: datetime
    last_currency: str
    last_price: Decimal
    last_volume: int

@dataclass
class FXRate:
    from_currency: str
    to_currency: str
    rate: Decimal

    def __init__(self, from_currency: str, to_currency: str, rate: Decimal):
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.rate = Decimal(str(rate))  # Ensure it's always a Decimal

    def to_dict(self) -> Dict:
        return {
            'from_currency': self.from_currency,
            'to_currency': self.to_currency,
            'rate': str(self.rate),
        }
