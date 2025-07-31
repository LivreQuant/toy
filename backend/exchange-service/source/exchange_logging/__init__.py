"""
Exchange Service Detailed Logging System

This module provides comprehensive logging capabilities for the exchange service
with focus on traceability, debugging, and performance monitoring.

Usage:
    # In exchange.py or main startup
    from source.exchange_logging.config import ExchangeLoggingConfig
    logging_config = ExchangeLoggingConfig.setup_exchange_logging()

    # In individual modules
    from source.exchange_logging.utils import get_exchange_logger
    logger = get_exchange_logger(__name__)

    # For transaction tracing
    from source.exchange_logging.context import transaction_scope
    with transaction_scope("operation_name", logger, param1=value1):
        # ... your code ...

Environment Variables:
    EXCHANGE_DETAILED_LOGS: Set to 'true' to enable detailed logging (default: true)
    EXCHANGE_LOG_LEVEL: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
"""

from .config import ExchangeLoggingConfig
from .utils import get_exchange_logger, trace_execution
from .context import transaction_scope, get_current_transaction_id

__all__ = [
    'ExchangeLoggingConfig',
    'get_exchange_logger',
    'trace_execution',
    'transaction_scope',
    'get_current_transaction_id'
]

# Version info
__version__ = "1.0.0"