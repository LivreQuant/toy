# source/orchestration/persistence/loaders/data_validator.py
import logging
from typing import Dict


class DataValidator:
    """Validates loaded snapshot data and provides summaries"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_last_snap_data(self, last_snap_data: Dict):
        """Validate that critical last snap data was loaded"""
        errors = []

        # Check exchange metadata
        if not last_snap_data.get('exchange_metadata'):
            errors.append("No exchange metadata loaded")

        # Check global data
        global_data = last_snap_data.get('global_data', {})
        if not global_data.get('universe'):
            errors.append("No universe symbols loaded")

        if not global_data.get('fx'):
            errors.append("No FX rates loaded")

        # Check book data
        if not last_snap_data.get('book_data'):
            errors.append("No book data loaded")
        else:
            for book_id, book_data in last_snap_data['book_data'].items():
                # Check accounts for each book
                if not any(book_data.get('accounts', {}).values()):
                    errors.append(f"No account balances loaded for book {book_id}")

        # Log warnings for optional data
        for book_id, book_data in last_snap_data.get('book_data', {}).items():
            if not book_data.get('portfolio'):
                self.logger.warning(f"⚠️ No portfolio positions loaded for book {book_id} (this may be intentional)")

            if not book_data.get('orders'):
                self.logger.warning(f"⚠️ No orders loaded for book {book_id} (this may be intentional)")

            if not book_data.get('returns'):
                self.logger.warning(f"⚠️ No returns period baselines loaded for book {book_id} (this may be intentional)")

        # Fail if critical data is missing
        if errors:
            error_msg = f"Critical Last Snap data missing: {', '.join(errors)}"
            self.logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

    def log_last_snap_summary(self, last_snap_data: Dict):
        """Log summary of loaded Last Snap data"""
        total_books = len(last_snap_data['book_data'])
        summary = {
            'total_books': total_books,
            'exch_id': last_snap_data['exchange_metadata'].get('exch_id', 'UNKNOWN'),
            'exchange_type': last_snap_data['exchange_metadata'].get('exchange_type', 'UNKNOWN'),
            'universe_symbols': len(last_snap_data['global_data']['universe']),
            'equity': len(last_snap_data['global_data']['equity']),
            'fx': len(last_snap_data['global_data']['fx']),
        }

        # Add per-book summaries
        for book_id, book_data in last_snap_data['book_data'].items():
            summary[f'{book_id}_portfolio_positions'] = len(book_data['portfolio'])
            summary[f'{book_id}_account_balances'] = sum(
                len(accounts) for accounts in book_data['accounts'].values())
            summary[f'{book_id}_orders'] = len(book_data['orders'])

        self.logger.info(f"✅ Last Snap Data loaded successfully: {summary}")

    def get_validation_summary(self, last_snap_data: Dict) -> Dict:
        """Get comprehensive validation summary"""
        summary = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }

        try:
            self.validate_last_snap_data(last_snap_data)
        except ValueError as e:
            summary['is_valid'] = False
            summary['errors'].append(str(e))

        # Collect statistics
        if last_snap_data.get('book_data'):
            summary['statistics'] = {
                'total_books': len(last_snap_data['book_data']),
                'total_positions': sum(len(book_data.get('portfolio', {}))
                                     for book_data in last_snap_data['book_data'].values()),
                'total_orders': sum(len(book_data.get('orders', {}))
                                  for book_data in last_snap_data['book_data'].values()),
                'universe_size': len(last_snap_data.get('global_data', {}).get('universe', {})),
                'fx_rates_count': len(last_snap_data.get('global_data', {}).get('fx', []))
            }

        return summary
