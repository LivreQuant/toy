# source/orchestration/persistence/managers/snapshot_validator.py
import logging
from typing import Dict, List

from source.orchestration.coordination.exchange_manager import ExchangeGroupManager


class SnapshotValidator:
    """Validates snapshot completeness and consistency"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_initialization_completeness(self, exchange_group_manager: ExchangeGroupManager) -> bool:
        """Validate that all books have been properly initialized"""
        try:
            if not exchange_group_manager:
                self.logger.error("❌ No exchange group manager provided")
                return False

            if not exchange_group_manager.book_contexts:
                self.logger.error("❌ No book contexts found")
                return False

            books = exchange_group_manager.get_all_books()
            self.logger.info(f"🔍 Validating initialization for {len(books)} books")

            for book_id in books:
                if not self._validate_book_initialization(exchange_group_manager, book_id):
                    return False

            self.logger.info("✅ All books properly initialized")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error validating initialization: {e}")
            return False

    def _validate_book_initialization(self, exchange_group_manager: ExchangeGroupManager, book_id: str) -> bool:
        """Validate that a specific book is properly initialized"""
        try:
            book_context = exchange_group_manager.get_book_context(book_id)
            if not book_context:
                self.logger.error(f"❌ No context found for book {book_id}")
                return False

            app_state = book_context.app_state
            if not app_state:
                self.logger.error(f"❌ No app_state found for book {book_id}")
                return False

            # Check if app_state indicates proper initialization
            if not app_state.is_initialized():
                self.logger.error(f"❌ book {book_id} app_state not initialized")
                return False

            self.logger.debug(f"✅ book {book_id} properly initialized")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error validating book {book_id}: {e}")
            return False

    def get_initialization_summary(self, exchange_group_manager: ExchangeGroupManager) -> Dict:
        """Get a summary of the initialization status"""
        books = []
        snapshot_date = None

        if exchange_group_manager:
            books = exchange_group_manager.get_all_books()
            snapshot_date = exchange_group_manager.last_snap_time

        summary = {
            'exch_id': exchange_group_manager.exch_id if exchange_group_manager else None,
            'books_count': len(books),
            'books': books,
            'snapshot_date': snapshot_date.isoformat() if snapshot_date else None,
            'initialized': bool(exchange_group_manager and exchange_group_manager.book_contexts)
        }

        return summary

    def validate_data_consistency(self, last_snap_data: Dict) -> List[str]:
        """Validate consistency across loaded data"""
        warnings = []

        # Check universe consistency
        universe_symbols = set(last_snap_data.get('global_data', {}).get('universe', {}).keys())

        # Check if portfolio symbols are in universe
        for book_id, book_data in last_snap_data.get('book_data', {}).items():
            portfolio_symbols = set(book_data.get('portfolio', {}).keys())
            unknown_symbols = portfolio_symbols - universe_symbols

            if unknown_symbols:
                warnings.append(f"book {book_id} has portfolio positions in symbols not in universe: {unknown_symbols}")

            # Check if orders are for valid symbols
            order_symbols = set()
            for order_data in book_data.get('orders', {}).values():
                if isinstance(order_data, dict):
                    order_symbols.add(order_data.get('symbol'))

            unknown_order_symbols = order_symbols - universe_symbols
            if unknown_order_symbols:
                warnings.append(f"book {book_id} has orders for symbols not in universe: {unknown_order_symbols}")

        return warnings
