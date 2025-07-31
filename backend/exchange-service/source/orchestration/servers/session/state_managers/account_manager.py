# source/orchestration/servers/session/state_managers/account_state_manager.py
"""
Account State Management Component
Extracted from session_server_impl.py to reduce file size
"""

import logging
from source.api.grpc.session_exchange_interface_pb2 import ExchangeDataUpdate, AccountStatus, AccountBalance


class AccountStateManager:
    """Handles account state operations for session server"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_current_accounts_state(self, update: ExchangeDataUpdate):
        """Poll current accounts state - Fixed for proto"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.account_manager:
            return

        try:
            balances = app_state.account_manager.balances
            update.accounts.CopyFrom(self.build_account_status(balances))
            total_balances = sum(len(currencies) for currencies in balances.values())
            self.logger.debug(f"🏦 Added accounts with {total_balances} balances to update")
        except Exception as e:
            self.logger.error(f"Error adding accounts state: {e}")

    def build_account_status(self, balances) -> AccountStatus:
        """Build account status from balances - Fixed for proto"""
        account_status = AccountStatus()

        for account_id, currencies in balances.items():
            for currency, balance_data in currencies.items():
                balance = AccountBalance()
                # Fix: Use correct field names from proto
                balance.type = account_id  # Changed from account to type
                balance.currency = currency

                # Handle both dict and object balance_data
                if isinstance(balance_data, dict):
                    balance.amount = float(balance_data.get('cash_balance', 0.0))
                else:
                    # Handle object with attributes
                    balance.amount = float(getattr(balance_data, 'amount', 0.0))

                account_status.balances.append(balance)

        # Add additional fields from proto
        account_status.nav = 0.0  # Default NAV
        account_status.base_currency = 'USD'  # Default base currency

        return account_status