# source/simulation/managers/account.py
from typing import Dict, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal

from source.simulation.core.enums.side import Side
from source.utils.timezone_utils import to_iso_string
from source.simulation.managers.utils import TrackingManager


@dataclass
class AccountBalance:
    currency: str
    amount: Decimal

    def to_dict(self) -> Dict:
        return {
            'currency': self.currency,
            'amount': str(self.amount),
        }


class AccountManager(TrackingManager):
    VALID_TYPES = {'CREDIT', 'SHORT_CREDIT', 'DEBIT', 'INVESTOR', 'NAV', 'PORTFOLIO'}

    def __init__(self, tracking: bool = True):
        headers = [
            'timestamp', 'type', 'currency', 'amount', 'previous_amount', 'change'
        ]

        super().__init__(
            manager_name="AccountManager",
            table_name="account_data",
            headers=headers,
            tracking=tracking
        )

        # Nested dictionary: type -> currency -> balance
        self.balances: Dict[str, Dict[str, AccountBalance]] = {
            balance_type: {} for balance_type in self.VALID_TYPES
        }
        # Add previous balances storage
        self.previous_balances: Dict[str, Dict[str, AccountBalance]] = {
            balance_type: {} for balance_type in self.VALID_TYPES
        }

        self.extra_balance_factor = Decimal('1.1')

    def _prepare_balance_data(self, timestamp: datetime, balance_type: str, currency: str,
                              old_amount: Decimal, new_amount: Decimal) -> List[Dict]:
        """Prepare balance data for storage"""

        return [{
            'timestamp': to_iso_string(timestamp),
            'type': balance_type,
            'currency': currency,
            'amount': str(new_amount),
            'previous_amount': str(old_amount),
            'change': str(new_amount - old_amount)
        }]

    def _prepare_all_balances_data(self, timestamp: datetime) -> List[Dict]:
        """Prepare all balances data for storage"""

        all_balance_data = []
        for balance_type, currencies in self.balances.items():
            for currency, balance in currencies.items():
                all_balance_data.append({
                    'timestamp': to_iso_string(timestamp),
                    'type': balance_type,
                    'currency': currency,
                    'amount': str(balance.amount),
                    'previous_amount': '0',
                    'change': '0'
                })
        return all_balance_data

    def save_current_as_previous(self) -> None:
        """Save current balances as previous balances before updating with new data"""
        with self._lock:
            self.logger.info("💾 SAVING CURRENT BALANCES AS PREVIOUS")

            self.previous_balances = {
                balance_type: {
                    currency: AccountBalance(
                        currency=balance.currency,
                        amount=Decimal(str(balance.amount))
                    )
                    for currency, balance in currencies.items()
                }
                for balance_type, currencies in self.balances.items()
            }

            self.logger.info("✅ Current balances saved as previous")

    def initialize_account(self, balances: Dict[str, Dict[str, AccountBalance]], timestamp: datetime) -> None:
        """Initialize account with last snapshot balances"""
        with self._lock:
            self.logger.info("🏦 INITIALIZING ACCOUNT BALANCES")
            self.logger.info(f"📊 Input balances: {balances}")

            # Initialize provided balances
            for balance_type in self.VALID_TYPES:
                self.balances[balance_type] = balances.get(balance_type, {}).copy()
                self.logger.info(f"   {balance_type}: {len(self.balances[balance_type])} currencies")

            from source.orchestration.app_state.state_manager import app_state
            if not app_state.portfolio_manager:
                raise ValueError("No portfolio manager available")

            # Calculate and set PORTFOLIO balances
            self.logger.info("🔄 Computing portfolio balances...")
            portfolio_balances = app_state.portfolio_manager.compute_portfolio_balances()
            self.logger.info(f"📊 Portfolio balances: {portfolio_balances}")

            self.balances['PORTFOLIO'] = {
                currency: AccountBalance(currency=currency, amount=amount)
                for currency, amount in portfolio_balances.items()
            }

            # Calculate and set NAV
            self.logger.info("🔄 Computing NAV...")
            nav = self.compute_nav()
            self.logger.info(f"💰 Computed NAV: {nav}")

            if 'USD' not in self.balances['NAV']:
                self.balances['NAV']['USD'] = AccountBalance(
                    currency='USD',
                    amount=Decimal('0')
                )
            self.balances['NAV']['USD'].amount = nav

            self.save_current_as_previous()
            self.logger.info("✅ Account initialization complete")

    def update_balance(self, balance_type: str, currency: str, amount_change: Decimal, timestamp: datetime) -> None:
        """Update account balance for a currency and type"""
        if balance_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid balance type: {balance_type}")

        with self._lock:
            self.logger.info(f"🔄 UPDATING BALANCE: {balance_type} {currency}")
            self.logger.info(f"   Change: {amount_change}")

            if currency not in self.balances[balance_type]:
                self.balances[balance_type][currency] = AccountBalance(
                    currency=currency,
                    amount=Decimal('0'),
                )

            balance = self.balances[balance_type][currency]
            old_amount = balance.amount

            if not isinstance(balance.amount, Decimal):
                balance.amount = Decimal(str(balance.amount))
            balance.amount = round(balance.amount + amount_change, 2)

            self.logger.info(f"   Balance updated: {old_amount} -> {balance.amount}")

            # Write balance change to storage
            #if self.tracking:
            #    from source.orchestration.app_state.state_manager import app_state
            #    market_timestamp = app_state.get_next_timestamp() or timestamp
            #    data = self._prepare_balance_data(market_timestamp, balance_type, currency, old_amount, balance.amount)
            #    self.write_to_storage(data, timestamp=market_timestamp)

    def write_balances(self):
        """Write immediate update"""
        with self._lock:
            self.logger.info("🏦 ACCOUNT WRITE_BALANCES CALLED")

            from source.orchestration.app_state.state_manager import app_state
            if not app_state.portfolio_manager:
                self.logger.error("❌ No portfolio manager available")
                raise ValueError("No portfolio manager available")

            # Get market timestamp
            market_timestamp = app_state.get_next_timestamp()
            if not market_timestamp:
                self.logger.warning("⚠️ No market timestamp available, using current time")
                market_timestamp = datetime.now(timezone.utc)

            self.logger.info("🔄 Computing portfolio balances...")
            # First update portfolio balances
            portfolio_balances = app_state.portfolio_manager.compute_portfolio_balances()
            self.logger.info(f"📊 Portfolio balances computed: {portfolio_balances}")

            self.balances['PORTFOLIO'] = {
                currency: AccountBalance(currency=currency, amount=amount)
                for currency, amount in portfolio_balances.items()
            }
            self.logger.info(f"📦 Updated PORTFOLIO balances: {self.balances['PORTFOLIO']}")

            # Then compute and update NAV
            self.logger.info("🔄 Computing NAV...")
            old_nav = self.get_balance('NAV', 'USD', current=True)
            nav = self.compute_nav()
            self.logger.info(f"💰 NAV computed: {old_nav} -> {nav}")

            if 'USD' not in self.balances['NAV']:
                self.balances['NAV']['USD'] = AccountBalance(
                    currency='USD',
                    amount=Decimal('0')
                )
            self.balances['NAV']['USD'].amount = nav
            self.logger.info(f"✅ NAV updated in balances")

            # Write updated balances to storage
            if self.tracking:
                data = self._prepare_all_balances_data(market_timestamp)
                self.write_to_storage(data, timestamp=market_timestamp)

    def compute_nav(self) -> Decimal:
        """Compute NAV using account balances and portfolio unrealized PNL"""
        self.logger.info("🔄 COMPUTE_NAV called")

        from source.orchestration.app_state.state_manager import app_state
        if not app_state.portfolio_manager:
            raise ValueError("No portfolio manager available")
        if not app_state.fx_manager:
            raise ValueError("No FX manager available")

        base_currency = app_state.get_base_currency()
        fx_manager = app_state.fx_manager
        nav = Decimal('0')

        self.logger.info(f"📊 Computing NAV in base currency: {base_currency}")

        # First compute portfolio balances by currency
        portfolio_balances = app_state.portfolio_manager.compute_portfolio_balances()
        self.logger.info(f"📊 Portfolio balances for NAV: {portfolio_balances}")

        # Update PORTFOLIO type balances
        with self._lock:
            self.balances['PORTFOLIO'] = {
                currency: AccountBalance(currency=currency, amount=amount)
                for currency, amount in portfolio_balances.items()
            }

        # Sum all account balances converted to base currency
        account_types = ['CREDIT', 'SHORT_CREDIT', 'DEBIT', 'PORTFOLIO']
        for account_type in account_types:
            balances = self.get_type_balances(account_type)
            type_total = Decimal('0')
            for balance in balances.values():
                converted = fx_manager.convert_amount(balance.amount, balance.currency, base_currency, current=True)
                type_total += converted
            nav += type_total
            self.logger.info(f"📊 {account_type} contribution to NAV: {type_total} (total nav so far: {nav})")

        self.logger.info(f"✅ Final computed NAV: {nav}")
        return nav

    def get_balance(self, balance_type: str, currency: str, current: bool = True) -> Decimal:
        """Get balance for a currency and type, either current or previous based on flag"""
        if balance_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid balance type: {balance_type}")

        with self._lock:
            balances_dict = self.balances if current else self.previous_balances
            balance = balances_dict[balance_type].get(
                currency,
                AccountBalance(currency=currency, amount=Decimal('0'))
            )
            if not isinstance(balance.amount, Decimal):
                balance.amount = Decimal(str(balance.amount))
            return balance.amount

    def get_type_balances(self, balance_type: str, current: bool = True) -> Dict[str, AccountBalance]:
        """Get all balances for a specific type"""
        if balance_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid balance type: {balance_type}")

        with self._lock:
            balances_dict = self.balances if current else self.previous_balances
            balances = balances_dict[balance_type].copy()
            # Ensure all amounts are Decimal
            for balance in balances.values():
                if not isinstance(balance.amount, Decimal):
                    balance.amount = Decimal(str(balance.amount))
            return balances

    def get_all_balances(self) -> Dict[str, Dict[str, AccountBalance]]:
        """Get all current balances - used by session service polling"""
        with self._lock:
            return {
                balance_type: currencies.copy()
                for balance_type, currencies in self.balances.items()
            }

    def _convert_debit_to_credit(self, required_amount: Decimal, currency: str, timestamp: datetime,
                                 trade_id: Optional[str] = None, instrument: Optional[str] = None):
        """Convert debit balance to credit balance if needed"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.account_manager:
            raise ValueError("No account manager available")
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")
        if not app_state.fx_manager:
            raise ValueError("No cash flow manager available")

        base_currency = app_state.get_base_currency()
        base_required_amount = app_state.fx_manager.convert_amount(amount=required_amount,
                                                                   from_currency=currency,
                                                                   to_currency=base_currency)
        base_fx = app_state.fx_manager.get_rate(from_currency=base_currency, to_currency=base_currency)
        fx = app_state.fx_manager.get_rate(from_currency=currency, to_currency=base_currency)

        app_state.account_manager.update_balance("DEBIT", base_currency, -base_required_amount, timestamp)
        app_state.account_manager.update_balance("CREDIT", currency, required_amount, timestamp)
        app_state.cash_flow_manager.record_account_transfer(
            from_account="DEBIT",
            from_currency=base_currency,
            from_fx=base_fx,
            from_amount=-base_required_amount,
            to_account="CREDIT",
            to_currency=currency,
            to_fx=fx,
            to_amount=required_amount,
            timestamp=timestamp,
            trade_id=trade_id,
            instrument=instrument,
            description=""
        )

    def _convert_debit_to_short_credit(self, required_amount: Decimal, currency: str, timestamp: datetime,
                                       trade_id: Optional[str] = None, instrument: Optional[str] = None):
        """Convert debit balance to credit balance if needed"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.account_manager:
            raise ValueError("No account manager available")
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")
        if not app_state.fx_manager:
            raise ValueError("No cash flow manager available")

        base_currency = app_state.get_base_currency()
        base_required_amount = app_state.fx_manager.convert_amount(amount=required_amount,
                                                                   from_currency=currency,
                                                                   to_currency=base_currency)
        base_fx = app_state.fx_manager.get_rate(from_currency=base_currency, to_currency=base_currency)
        fx = app_state.fx_manager.get_rate(from_currency=currency, to_currency=base_currency)

        app_state.account_manager.update_balance("DEBIT", base_currency, -base_required_amount, timestamp)
        app_state.account_manager.update_balance("SHORT_CREDIT", currency, required_amount, timestamp)
        app_state.cash_flow_manager.record_account_transfer(
            from_account="DEBIT",
            from_currency=base_currency,
            from_fx=base_fx,
            from_amount=-base_required_amount,
            to_account="SHORT_CREDIT",
            to_currency=currency,
            to_fx=fx,
            to_amount=required_amount,
            timestamp=timestamp,
            trade_id=trade_id,
            instrument=instrument,
            description=""
        )

    def check_account_balance_before_fill(self, account: str, currency: str, required_amount: Decimal,
                                          timestamp: datetime):
        """Check if account has sufficient balance for trade"""
        try:
            from source.orchestration.app_state.state_manager import app_state
            if not app_state.account_manager:
                raise ValueError("No account manager available")
            if not app_state.cash_flow_manager:
                raise ValueError("No cash flow manager available")

            if account == "CREDIT":
                credit_balance = app_state.account_manager.get_balance(account, currency)

                if credit_balance > required_amount:
                    pass
                else:
                    # TAKE DEBIT TO SUPPLY CREDIT
                    transfer_funds = round(self.extra_balance_factor * abs(required_amount) - abs(credit_balance), 2)
                    self._convert_debit_to_credit(transfer_funds, currency, timestamp)

            elif account == "SHORT_CREDIT":
                short_credit_balance = app_state.account_manager.get_balance(account, currency)

                if short_credit_balance > required_amount:
                    pass
                else:
                    # TAKE DEBIT TO SUPPLY SHORT_CREDIT
                    transfer_funds = round(self.extra_balance_factor * abs(required_amount) - abs(short_credit_balance),
                                           2)
                    self._convert_debit_to_short_credit(transfer_funds, currency, timestamp)

            else:
                raise ValueError(f"Unknown account {account} in check_account_balance_before_fill")

        except Exception as e:
            raise ValueError(f"Error checking balance: {e}")

    def adjust_account_balance_after_fill(self, account: str, withdraw: bool, currency: str, amount: Decimal,
                                          timestamp: datetime, trade_id: Optional[str] = None,
                                          instrument: Optional[str] = None) -> None:
        """Adjust account balance after trade execution"""
        try:
            from source.orchestration.app_state.state_manager import app_state
            if not app_state.account_manager:
                raise ValueError("No account manager available")
            if not app_state.cash_flow_manager:
                raise ValueError("No cash flow manager available")
            if not app_state.fx_manager:
                raise ValueError("No cash flow manager available")

            base_currency = app_state.get_base_currency()
            fx = app_state.fx_manager.get_rate(from_currency=currency, to_currency=base_currency)

            if withdraw:
                # REMOVE FUNDS FROM ACCOUNT
                app_state.account_manager.update_balance(account, currency, -amount, timestamp)
                app_state.cash_flow_manager.record_portfolio_transfer(account_type=account,
                                                                      is_inflow=False,
                                                                      from_currency=currency,
                                                                      from_fx=fx,
                                                                      from_amount=-amount,
                                                                      to_currency=currency,
                                                                      to_fx=fx,
                                                                      to_amount=amount,
                                                                      timestamp=timestamp,
                                                                      trade_id=trade_id,
                                                                      instrument=instrument,
                                                                      description="")

            else:
                # ADD FUNDS TO ACCOUNT
                app_state.account_manager.update_balance(account, currency, amount, timestamp)
                app_state.cash_flow_manager.record_portfolio_transfer(account_type=account,
                                                                      is_inflow=True,
                                                                      from_currency=currency,
                                                                      from_fx=fx,
                                                                      from_amount=amount,
                                                                      to_currency=currency,
                                                                      to_fx=fx,
                                                                      to_amount=-amount,
                                                                      timestamp=timestamp,
                                                                      trade_id=trade_id,
                                                                      instrument=instrument,
                                                                      description="")

        except Exception as e:
            raise ValueError(f"Error adjusting balance: {e}")

    def check_balance_before_fill(self, order, start_timestamp: datetime, end_timestamp: datetime,
                                  impacted_price: Decimal,
                                  commissions: Decimal, fill_qty: Decimal, is_risk_off: bool, initial_side):

        if not is_risk_off:
            # RISK ON
            if initial_side.name == 'Long':
                # CREDIT
                # - USE DEBIT TO SUPPLY CREDIT
                self.check_account_balance_before_fill(
                    account="CREDIT",
                    currency=order.get_currency(),
                    required_amount=fill_qty * impacted_price,
                    timestamp=start_timestamp
                )
            elif initial_side.name == 'Short':
                # SHORT_CREDIT
                # - SUPPLY SHORT CREDIT
                pass
            else:
                if order.get_side() == Side.Buy:
                    # CREDIT
                    # - USE DEBIT TO SUPPLY CREDIT
                    self.check_account_balance_before_fill(
                        account="CREDIT",
                        currency=order.get_currency(),
                        required_amount=fill_qty * impacted_price,
                        timestamp=start_timestamp
                    )
                else:
                    # SHORT_CREDIT
                    # - SUPPLY SHORT CREDIT
                    pass
        else:
            # RISK OFF
            if initial_side.name == 'Long':
                # CREDIT
                # - SUPPLY CREDIT
                pass
            elif initial_side.name == 'Short':
                # SHORT_CREDIT
                # - USE DEBIT TO SUPPLY SHORT_CREDIT
                self.check_account_balance_before_fill(
                    account="SHORT_CREDIT",
                    currency=order.get_currency(),
                    required_amount=fill_qty * impacted_price,
                    timestamp=start_timestamp
                )
            else:
                raise ValueError(f"Cannot have risk off without initial position being long or short.")

    def adjust_balance_after_fill(self, order, start_timestamp: datetime, end_timestamp: datetime,
                                  impacted_price: Decimal,
                                  commissions: Decimal, fill_qty: Decimal, is_risk_off: bool, initial_side,
                                  trade_id: Optional[str] = None, instrument: Optional[str] = None):

        if not is_risk_off:
            # RISK ON
            if initial_side.name == 'Long':
                # CREDIT
                # - WITHDRAW CREDIT
                self.adjust_account_balance_after_fill(
                    account="CREDIT",
                    withdraw=True,
                    currency=order.get_currency(),
                    amount=round(fill_qty * impacted_price, 2),
                    timestamp=start_timestamp,
                    instrument=instrument,
                    trade_id=trade_id
                )
            elif initial_side.name == 'Short':
                # SHORT_CREDIT
                # - DEPOSIT SHORT CREDIT
                self.adjust_account_balance_after_fill(
                    account="SHORT_CREDIT",
                    withdraw=False,  # deposit
                    currency=order.get_currency(),
                    amount=round(fill_qty * impacted_price, 2),
                    timestamp=end_timestamp,
                    instrument=instrument,
                    trade_id=trade_id
                )
            else:
                if order.get_side() == Side.Buy:
                    # CREDIT
                    # - WITHDRAW CREDIT
                    self.adjust_account_balance_after_fill(
                        account="CREDIT",
                        withdraw=True,
                        currency=order.get_currency(),
                        amount=round(fill_qty * impacted_price, 2),
                        timestamp=start_timestamp,
                        instrument=instrument,
                        trade_id=trade_id
                    )
                else:
                    # SHORT_CREDIT
                    # - DEPOSIT SHORT CREDIT
                    self.adjust_account_balance_after_fill(
                        account="SHORT_CREDIT",
                        withdraw=False,
                        currency=order.get_currency(),
                        amount=round(fill_qty * impacted_price, 2),
                        timestamp=end_timestamp,
                        instrument=instrument,
                        trade_id=trade_id
                    )
        else:
            # RISK OFF
            if initial_side.name == 'Long':
                # CREDIT
                # - DEPOSIT CREDIT
                self.adjust_account_balance_after_fill(
                    account="CREDIT",
                    withdraw=False,
                    currency=order.get_currency(),
                    amount=round(fill_qty * impacted_price, 2),
                    timestamp=end_timestamp,
                    instrument=instrument,
                    trade_id=trade_id
                )
            elif initial_side.name == 'Short':
                # SHORT_CREDIT
                # - WITHDRAW SHORT CREDIT
                self.adjust_account_balance_after_fill(
                    account="SHORT_CREDIT",
                    withdraw=True,
                    currency=order.get_currency(),
                    amount=round(fill_qty * impacted_price, 2),
                    timestamp=start_timestamp,
                    instrument=instrument,
                    trade_id=trade_id
                )
            else:
                raise ValueError(f"Cannot have risk off without initial position being long or short.")

            # If this is a risk off trade, compute and update realized PNL
            if is_risk_off and instrument:
                from source.orchestration.app_state.state_manager import app_state
                if not app_state.portfolio_manager:
                    raise ValueError("No portfolio manager available")

                position = app_state.portfolio_manager.get_position(instrument)
                if position:
                    realized_pnl = (impacted_price - position.avg_price) * fill_qty
                    position.itd_realized_pnl += realized_pnl
                else:
                    raise ValueError(f"Closing a position that does not exist {instrument}")

    def _convert_debit_to_investor(self, base_required_amount: Decimal, timestamp: datetime,
                                   trade_id: Optional[str] = None, instrument: Optional[str] = None):
        """Convert debit balance to credit balance if needed"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.account_manager:
            raise ValueError("No account manager available")
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")
        if not app_state.fx_manager:
            raise ValueError("No cash flow manager available")

        base_currency = app_state.get_base_currency()

        app_state.account_manager.update_balance("DEBIT", base_currency, -base_required_amount, timestamp)
        app_state.account_manager.update_balance("INVESTOR", base_currency, base_required_amount, timestamp)
        app_state.cash_flow_manager.record_account_transfer(
            from_account="DEBIT",
            from_currency=base_currency,
            from_fx=1,
            from_amount=-base_required_amount,
            to_account="INVESTOR",
            to_currency=base_currency,
            to_fx=1,
            to_amount=base_required_amount,
            timestamp=timestamp,
            trade_id=trade_id,
            instrument=instrument,
            description=""
        )

    def rebalance_capital(self, book_context: Dict[str, int], timestamp: datetime):
        """
        Mode 1: Constant AUM (Strategy Testing) - REBALANCE
        Mode 2: Compound Growth (Real-world Simulation) - DO NOT REBALANCE

        At the SOD we check NAV,
        - if NAV > Constant AUM, we transfer Credit TO Investor; until new NAV = Constant AUM
        - if NAV < Constant AUM, we transfer Investor TO Credit; until new NAV = Constant AUM
        """
        from source.orchestration.app_state.state_manager import app_state

        base_currency = app_state.get_base_currency()
        operation_id = app_state.get_operation_id()
        initial_nav = app_state.get_initial_nav()

        if operation_id == 1:
            # USE ALL OF NAV; NO INVESTOR ACCOUNT REQUIRED
            return

        investor_account = app_state.account_manager.get_balance('INVESTOR', base_currency)

        current_nav = self.compute_nav()

        if current_nav > initial_nav:
            # Portfolio gained - move excess cash to investor account
            excess_cash = current_nav - initial_nav
            self._convert_debit_to_investor(excess_cash, timestamp)

        elif current_nav < initial_nav and investor_account > 0:
            # Portfolio lost - inject cash from investor account
            needed_cash = initial_nav - current_nav
            available = min(needed_cash, investor_account)
            self._convert_debit_to_investor(available, timestamp)
