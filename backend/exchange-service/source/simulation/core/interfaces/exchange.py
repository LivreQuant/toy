from abc import ABC, abstractmethod
from typing import Dict
from source.simulation.core.interfaces.market import Market_ABC


class Exchange_ABC(ABC):
    @abstractmethod
    def get_market(self, instrument: str) -> Market_ABC:
        """Get the VWAP market for an instrument"""
        pass

    @abstractmethod
    def update_market_data(self, minute_bar: Dict) -> None:
        """Update market data for an instrument with new minute bar"""
        pass

    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Get list of all symbols/instruments currently in the exchange"""
        pass