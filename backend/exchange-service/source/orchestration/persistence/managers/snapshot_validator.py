# source/orchestration/persistence/managers/snapshot_validator.py
import logging
from typing import Dict, List

from source.orchestration.coordination.exchange_manager import ExchangeGroupManager


class SnapshotValidator:
    """Validates snapshot completeness and consistency"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_initialization_completeness(self, exchange_group_manager: ExchangeGroupManager) -> bool:
        """Validate that all users have been properly initialized"""
        try:
            if not exchange_group_manager:
                self.logger.error("❌ No exchange group manager provided")
                return False

            if not exchange_group_manager.user_contexts:
                self.logger.error("❌ No user contexts found")
                return False

            users = exchange_group_manager.get_all_users()
            self.logger.info(f"🔍 Validating initialization for {len(users)} users")

            for user_id in users:
                if not self._validate_user_initialization(exchange_group_manager, user_id):
                    return False

            self.logger.info("✅ All users properly initialized")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error validating initialization: {e}")
            return False

    def _validate_user_initialization(self, exchange_group_manager: ExchangeGroupManager, user_id: str) -> bool:
        """Validate that a specific user is properly initialized"""
        try:
            user_context = exchange_group_manager.get_user_context(user_id)
            if not user_context:
                self.logger.error(f"❌ No context found for user {user_id}")
                return False

            app_state = user_context.app_state
            if not app_state:
                self.logger.error(f"❌ No app_state found for user {user_id}")
                return False

            # Check if app_state indicates proper initialization
            if not app_state.is_initialized():
                self.logger.error(f"❌ User {user_id} app_state not initialized")
                return False

            self.logger.debug(f"✅ User {user_id} properly initialized")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error validating user {user_id}: {e}")
            return False

    def get_initialization_summary(self, exchange_group_manager: ExchangeGroupManager) -> Dict:
        """Get a summary of the initialization status"""
        users = []
        snapshot_date = None

        if exchange_group_manager:
            users = exchange_group_manager.get_all_users()
            snapshot_date = exchange_group_manager.last_snap_time

        summary = {
            'group_id': exchange_group_manager.group_id if exchange_group_manager else None,
            'users_count': len(users),
            'users': users,
            'snapshot_date': snapshot_date.isoformat() if snapshot_date else None,
            'initialized': bool(exchange_group_manager and exchange_group_manager.user_contexts)
        }

        return summary

    def validate_data_consistency(self, last_snap_data: Dict) -> List[str]:
        """Validate consistency across loaded data"""
        warnings = []

        # Check universe consistency
        universe_symbols = set(last_snap_data.get('global_data', {}).get('universe', {}).keys())

        # Check if portfolio symbols are in universe
        for user_id, user_data in last_snap_data.get('user_data', {}).items():
            portfolio_symbols = set(user_data.get('portfolio', {}).keys())
            unknown_symbols = portfolio_symbols - universe_symbols

            if unknown_symbols:
                warnings.append(f"User {user_id} has portfolio positions in symbols not in universe: {unknown_symbols}")

            # Check if orders are for valid symbols
            order_symbols = set()
            for order_data in user_data.get('orders', {}).values():
                if isinstance(order_data, dict):
                    order_symbols.add(order_data.get('symbol'))

            unknown_order_symbols = order_symbols - universe_symbols
            if unknown_order_symbols:
                warnings.append(f"User {user_id} has orders for symbols not in universe: {unknown_order_symbols}")

        return warnings
