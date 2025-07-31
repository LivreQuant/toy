from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Dict
from datetime import datetime

from source.simulation.core.enums.side import Side
from source.simulation.core.interfaces.order import Order_ABC
from source.simulation.core.interfaces.order_state import OrderState_ABC


class Market_ABC(ABC):
    """Abstract base class for VWAP-based market implementations"""

    @abstractmethod
    def add_order(self,
                  side: Side,
                  qty: int,
                  price: Optional[Decimal],  # Optional for pure VWAP orders
                  cl_order_id: str,
                  participation_rate: float = 0.1,
                  start_time: Optional[datetime] = None,
                  end_time: Optional[datetime] = None
                  ) -> str:
        """
        Add a new VWAP order to the market

        Args:
            side: Buy or Sell
            qty: Total quantity to execute
            price: Optional limit price (None for pure VWAP)
            cl_order_id: Client order ID
            participation_rate: Target participation rate (0.0-1.0)
            start_time: Optional order start time (default: immediate)
            end_time: Optional order end time (default: market close)

        Returns:
            str: Order ID
        """
        pass

    @abstractmethod
    def delete_order(self, order_id: str) -> OrderState_ABC:
        """Delete an order and return its final state"""
        pass

    @abstractmethod
    def get_buy_orders(self) -> List[Order_ABC]:
        """Get all active buy orders"""
        pass

    @abstractmethod
    def get_sell_orders(self) -> List[Order_ABC]:
        """Get all active sell orders"""
        pass

    @abstractmethod
    def get_instrument(self) -> str:
        """Get the market instrument symbol"""
        pass

    @abstractmethod
    def update_market_state(self, minute_bar: Dict) -> None:
        """
        Update market state with new minute bar data

        Args:
            minute_bar: Dictionary containing minute bar data with fields:
                - timestamp: Bar timestamp
                - open: Opening price
                - high: High price
                - low: Low price
                - close: Closing price
                - vwap: Volume-weighted average price
                - volume: Bar volume
        """
        pass
