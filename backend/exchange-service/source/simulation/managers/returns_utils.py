# returns_utils.py
from decimal import Decimal
from typing import Dict, List


class ReturnsCalculator:
    """Mixin class providing returns calculation utilities for ReturnsManager"""

    def compute_periodic_book_return(self) -> tuple[str, List[Dict[str, Dict[str, Decimal]]]]:
        """Compute portfolio NAV return for the given timestamp"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.equity_manager:
            raise ValueError("No equity data manager available")

        base_currency = app_state.get_base_currency()

        emv_book = app_state.account_manager.get_balance('NAV', base_currency, current=True)
        bmv_book = app_state.account_manager.get_balance('NAV', base_currency, current=False)
        cf = Decimal('0')  # NO TRANSFERS

        rets = [{"NAV": {"emv": emv_book,
                         "bmv": bmv_book,
                         "bmv_book": bmv_book,
                         "cf": cf}
                 }]

        return "BOOK", rets

    def compute_periodic_cash_equity_return(self) -> tuple[str, List[Dict[str, Dict[str, Decimal]]]]:
        """Compute portfolio NAV return for the given timestamp"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.fx_manager:
            raise ValueError("No fx manager available")
        if not app_state.account_manager:
            raise ValueError("No account manager available")
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")
        if not app_state.portfolio_manager:
            raise ValueError("No portfolio manager available")

        base_currency = app_state.get_base_currency()

        # account (cash) balances
        account_types = ['CREDIT', 'SHORT_CREDIT', 'DEBIT']

        emv_cash = Decimal('0')
        for account_type in account_types:
            current_balances = app_state.account_manager.get_type_balances(account_type, current=True)
            for balance in current_balances.values():
                emv_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                current=True)

        bmv_cash = Decimal('0')
        for account_type in account_types:
            previous_balances = app_state.account_manager.get_type_balances(account_type, current=False)
            for balance in previous_balances.values():
                bmv_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                current=False)

        # equity (portfolio) balances
        emv_equity = Decimal('0')
        portfolio_current_balances = app_state.portfolio_manager.compute_portfolio_balances(current=True)
        for currency, amount in portfolio_current_balances.items():
            emv_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=True)

        bmv_equity = Decimal('0')
        portfolio_previous_balances = app_state.portfolio_manager.compute_portfolio_balances(current=False)
        for currency, amount in portfolio_previous_balances.items():
            bmv_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=False)

        # cash flows
        cf_from_cash_to_equity = Decimal('0')
        cash_flows = app_state.cash_flow_manager.get_current_flows()
        for flow in cash_flows:
            if flow['flow_type'] == "PORTFOLIO_TRANSFER":
                if flow['to_account'] == "PORTFOLIO":
                    cf_from_cash_to_equity += app_state.fx_manager.convert_amount(Decimal(flow['from_amount']),
                                                                                  flow['from_currency'], base_currency,
                                                                                  current=False)
                if flow['from_account'] == "PORTFOLIO":
                    cf_from_cash_to_equity -= app_state.fx_manager.convert_amount(Decimal(flow['from_amount']),
                                                                                  flow['from_currency'], base_currency,
                                                                                  current=False)

        bmv_book = bmv_cash + bmv_equity

        rets = [{"CASH": {"emv": emv_cash,
                          "bmv": bmv_cash,
                          "bmv_book": bmv_book,
                          "cf": cf_from_cash_to_equity}
                 },
                {"EQUITY": {"emv": emv_equity,
                            "bmv": bmv_equity,
                            "bmv_book": bmv_book,
                            "cf": -cf_from_cash_to_equity}
                 },
                ]

        print(f"CASH EQUITY RETURNS: {rets}")

        return "CASH_EQUITY", rets

    def compute_periodic_long_short_return(self) -> tuple[str, List[Dict[str, Dict[str, Decimal]]]]:
        """Compute portfolio NAV return for the given timestamp"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.fx_manager:
            raise ValueError("No fx manager available")
        if not app_state.account_manager:
            raise ValueError("No account manager available")
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")
        if not app_state.portfolio_manager:
            raise ValueError("No portfolio manager available")

        base_currency = app_state.get_base_currency()

        # long account (cash) balances
        account_types = ['CREDIT', 'DEBIT']

        emv_long_cash = Decimal('0')
        for account_type in account_types:
            current_balances = app_state.account_manager.get_type_balances(account_type, current=True)
            for balance in current_balances.values():
                emv_long_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                     current=True)

        bmv_long_cash = Decimal('0')
        for account_type in account_types:
            previous_balances = app_state.account_manager.get_type_balances(account_type, current=False)
            for balance in previous_balances.values():
                bmv_long_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                     current=False)

        # long equity (portfolio) balances
        emv_long_equity = Decimal('0')
        portfolio_current_balances = app_state.portfolio_manager.compute_portfolio_balances(current=True)
        for currency, amount in portfolio_current_balances.items():
            emv_long_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=True)

        bmv_long_equity = Decimal('0')
        portfolio_previous_balances = app_state.portfolio_manager.compute_portfolio_balances(current=False)
        for currency, amount in portfolio_previous_balances.items():
            bmv_long_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=False)

        # short account (cash) balances
        account_types = ['SHORT_CREDIT']

        emv_short_cash = Decimal('0')
        for account_type in account_types:
            current_balances = app_state.account_manager.get_type_balances(account_type, current=True)
            for balance in current_balances.values():
                emv_short_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                      current=True)

        bmv_short_cash = Decimal('0')
        for account_type in account_types:
            previous_balances = app_state.account_manager.get_type_balances(account_type, current=False)
            for balance in previous_balances.values():
                bmv_short_cash += app_state.fx_manager.convert_amount(balance.amount, balance.currency, base_currency,
                                                                      current=False)

        # short equity (portfolio) balances
        emv_short_equity = Decimal('0')
        portfolio_current_balances = app_state.portfolio_manager.compute_portfolio_balances(current=True)
        for currency, amount in portfolio_current_balances.items():
            emv_short_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=True)

        bmv_short_equity = Decimal('0')
        portfolio_previous_balances = app_state.portfolio_manager.compute_portfolio_balances(current=False)
        for currency, amount in portfolio_previous_balances.items():
            bmv_short_equity += app_state.fx_manager.convert_amount(amount, currency, base_currency, current=False)

        # cash flows
        cf_from_long_to_short = Decimal('0')
        cash_flows = app_state.cash_flow_manager.get_current_flows()
        for flow in cash_flows:
            if flow['flow_type'] == "PORTFOLIO_TRANSFER":
                if flow['to_account'] == "PORTFOLIO":
                    cf_from_long_to_short += app_state.fx_manager.convert_amount(Decimal(flow['from_amount']),
                                                                                 flow['from_currency'], base_currency,
                                                                                 current=False)
                if flow['from_account'] == "PORTFOLIO":
                    cf_from_long_to_short -= app_state.fx_manager.convert_amount(Decimal(flow['from_amount']),
                                                                                 flow['from_currency'], base_currency,
                                                                                 current=False)

        bmv_book = bmv_long_cash + bmv_long_equity + bmv_short_cash + bmv_short_equity

        rets = [{"LONG": {"emv": emv_long_cash + emv_long_equity,
                          "bmv": bmv_long_cash + emv_long_equity,
                          "bmv_book": bmv_book,
                          "cf": cf_from_long_to_short}
                 },
                {"SHORT": {"emv": emv_short_cash + bmv_short_equity,
                           "bmv": bmv_short_cash + bmv_short_equity,
                           "bmv_book": bmv_book,
                           "cf": -cf_from_long_to_short}
                 },
                ]

        print(f"LONG SHORT RETURNS: {rets}")

        return "LONG_SHORT", rets
