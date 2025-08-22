import logging
import datetime
from threading import RLock
from decimal import Decimal
from typing import Optional

from source.simulation.core.enums.side import Side, LS
from source.simulation.exchange.order_impl import Order
from source.utils.timezone_utils import ensure_utc


class Account:
    """Manages account balance checks and updates"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = RLock()

        self.extra_balance_factor = Decimal('1.1')

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

            # ✅ FIX: Use current market timestamp instead of the passed timestamp
            cash_flow_timestamp = ensure_utc(timestamp)

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
                                                                      timestamp=cash_flow_timestamp,
                                                                      # ✅ USE MARKET TIME
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
                                                                      timestamp=cash_flow_timestamp,
                                                                      # ✅ USE MARKET TIME
                                                                      trade_id=trade_id,
                                                                      instrument=instrument,
                                                                      description="")

        except Exception as e:
            raise ValueError(f"Error adjusting balance: {e}")

    def check_balance_before_fill(self, order: Order, start_timestamp: datetime, end_timestamp: datetime,
                                  impacted_price: Decimal,
                                  commissions: Decimal, fill_qty: Decimal, is_risk_off: bool, initial_side: bool):

        if not is_risk_off:
            # RISK ON
            if initial_side == LS.Long:
                # CREDIT
                # - USE DEBIT TO SUPPLY CREDIT
                self.check_account_balance_before_fill(
                    account="CREDIT",
                    currency=order.get_currency(),
                    required_amount=fill_qty * impacted_price,
                    timestamp=start_timestamp
                )
            elif initial_side == LS.Short:
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
            if initial_side == LS.Long:
                # CREDIT
                # - SUPPLY CREDIT
                pass
            elif initial_side == LS.Short:
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

    def adjust_balance_after_fill(self, order: Order, start_timestamp: datetime, end_timestamp: datetime,
                                  impacted_price: Decimal,
                                  commissions: Decimal, fill_qty: Decimal, is_risk_off: bool, initial_side: bool,
                                  trade_id: Optional[str] = None, instrument: Optional[str] = None):

        if not is_risk_off:
            # RISK ON
            if initial_side == LS.Long:
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
            elif initial_side == LS.Short:
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
            if initial_side == LS.Long:
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
            elif initial_side == LS.Short:
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
