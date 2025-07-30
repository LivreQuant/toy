# source/core/exchange/adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any

from source.models.exchange_data import ExchangeDataUpdate

class ExchangeAdapter(ABC):
    """Abstract base class for exchange adapters."""
    
    @abstractmethod
    async def convert_from_protobuf(self, protobuf_data) -> ExchangeDataUpdate:
        """
        Convert exchange-specific protobuf data directly to standardized format
        
        Args:
            protobuf_data: Raw protobuf data from the exchange
            
        Returns:
            Standardized ExchangeDataUpdate object
        """
        pass
    