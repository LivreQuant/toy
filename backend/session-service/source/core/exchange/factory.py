# source/core/exchange/factory.py
from typing import Dict, Type

from source.core.exchange.adapter import ExchangeAdapter
from source.core.exchange.adapters.default_adapter import DefaultExchangeAdapter
from source.models.exchange_data import ExchangeType


class ExchangeAdapterFactory:
    """Factory for creating exchange adapters"""
    
    # Registry of exchange adapters
    _adapters: Dict[ExchangeType, Type[ExchangeAdapter]] = {
        ExchangeType.EQUITIES: DefaultExchangeAdapter,
        # Add more exchange types here as they're implemented
        # ExchangeType.CRYPTO: CryptoExchangeAdapter,
        # ExchangeType.FX: FXExchangeAdapter,
    }
    
    @classmethod
    def get_adapter(cls, exchange_type: ExchangeType) -> ExchangeAdapter:
        """
        Get the appropriate adapter for the exchange type
        
        Args:
            exchange_type: The type of exchange
            
        Returns:
            An instance of the appropriate exchange adapter
        """
        adapter_class = cls._adapters.get(exchange_type, DefaultExchangeAdapter)
        return adapter_class()
    
    @classmethod
    def register_adapter(cls, exchange_type: ExchangeType, adapter_class: Type[ExchangeAdapter]):
        """
        Register a new adapter for an exchange type
        
        Args:
            exchange_type: The type of exchange
            adapter_class: The adapter class to use for this exchange type
        """
        cls._adapters[exchange_type] = adapter_class