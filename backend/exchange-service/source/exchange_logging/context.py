# source/logging/context.py
import logging
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any
from datetime import datetime
import threading


class TransactionContext:
    """Thread-local context for tracking related operations"""

    def __init__(self):
        self._local = threading.local()

    def start_transaction(self, transaction_type: str, **kwargs) -> str:
        """Start a new transaction context"""
        transaction_id = str(uuid.uuid4())[:8]

        if not hasattr(self._local, 'stack'):
            self._local.stack = []

        transaction_info = {
            'id': transaction_id,
            'type': transaction_type,
            'start_time': datetime.now(),
            'data': kwargs
        }

        self._local.stack.append(transaction_info)
        return transaction_id

    def end_transaction(self):
        """End the current transaction context"""
        if hasattr(self._local, 'stack') and self._local.stack:
            self._local.stack.pop()

    def get_current_transaction(self) -> Optional[Dict[str, Any]]:
        """Get the current transaction info"""
        if hasattr(self._local, 'stack') and self._local.stack:
            return self._local.stack[-1]
        return None

    def get_transaction_id(self) -> Optional[str]:
        """Get the current transaction ID"""
        current = self.get_current_transaction()
        return current['id'] if current else None


# Global transaction context
_transaction_context = TransactionContext()


@contextmanager
def transaction_scope(transaction_type: str, logger: logging.Logger, **kwargs):
    """Context manager for transaction logging"""
    transaction_id = _transaction_context.start_transaction(transaction_type, **kwargs)

    logger.info(f"TXN_START [{transaction_id}] {transaction_type}")
    for key, value in kwargs.items():
        logger.debug(f"TXN_PARAM [{transaction_id}] {key}: {value}")

    start_time = datetime.now()
    try:
        yield transaction_id
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"TXN_SUCCESS [{transaction_id}] {transaction_type} completed in {duration:.2f}ms")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"TXN_FAILED [{transaction_id}] {transaction_type} failed after {duration:.2f}ms: {str(e)}")
        raise
    finally:
        _transaction_context.end_transaction()


def get_current_transaction_id() -> Optional[str]:
    """Get the current transaction ID for correlation"""
    return _transaction_context.get_transaction_id()