#!/usr/bin/env python3
"""
Cash dividends - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, CashDividend, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class CashDividendsHandler:
    """Complete cash dividends handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[CashDividend] = []

    def load_unified_data(self) -> List[CashDividend]:
        """Load unified cash dividends from CSV"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_cash_dividends.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                try:
                    dividend_amount = Decimal(str(row['rate']))
                except (ValueError, TypeError, KeyError):
                    dividend_amount = Decimal('0')
                    logger.warning(f"Invalid dividend rate for {row.get('master_symbol')}: {row.get('rate')}")

                action = CashDividend(
                    symbol=row['master_symbol'],
                    action_type='CASH_DIVIDEND',
                    effective_date=self._safe_get_date(row, 'ex_date'),
                    source=f"unified_{row['source']}",
                    dividend_per_share=dividend_amount,
                    currency=row.get('currency', 'USD'),
                    account='Credit',
                    payable_date=self._safe_get_date(row, 'payable_date')
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified cash dividends")

        return actions

    def load_manual_data(self) -> List[CashDividend]:
        """Load manual cash dividends overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "cash_dividends.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = CashDividend(
                    symbol=row['symbol'],
                    action_type='CASH_DIVIDEND',
                    effective_date='manual',
                    source='manual',
                    dividend_per_share=Decimal(str(row['dividend_per_share'])),
                    currency=row['currency'],
                    account=row['account'],
                    payable_date=row.get('payable_date', '')
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual cash dividends")

        return actions

    def load_all_data(self) -> List[CashDividend]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: CashDividend, current_date: str) -> List[Position]:
        """Apply cash dividend to portfolio - keep original position"""
        if not self._is_payable_date(action, current_date):
            logger.info(f"Cash dividend for {position.symbol} not payable yet (payable: {action.payable_date})")

        # Portfolio action: Keep original position unchanged
        return [position]

    def apply_account_action(self, position: Position, action: CashDividend, current_date: str) -> Dict[str, Decimal]:
        """Apply cash dividend to account - credit dividend amount"""
        if not self._is_payable_date(action, current_date):
            return {}

        # Account action: Credit dividend to account
        dividend_amount = position.quantity * action.dividend_per_share

        logger.info(
            f"Cash dividend for {position.symbol}: {dividend_amount} {action.currency} credited to {action.account}")

        return {action.currency: dividend_amount}

    def apply_action(self, position: Position, action: CashDividend, current_date: str) -> PortfolioUpdate:
        """Apply complete cash dividend action"""
        new_positions = self.apply_portfolio_action(position, action, current_date)
        cash_adjustments = self.apply_account_action(position, action, current_date)

        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )

    def _is_payable_date(self, action: CashDividend, current_date: str) -> bool:
        """Check if current date is the payable date"""
        try:
            if not action.payable_date:
                return True

            payable_date = datetime.strptime(action.payable_date, '%Y-%m-%d').date()
            current = datetime.strptime(current_date, '%Y-%m-%d').date()

            return current >= payable_date
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse payable date for {action.symbol}, assuming payable")
            return True

    def _safe_get_date(self, row, date_field: str) -> str:
        """Safely extract date field"""
        try:
            date_value = row.get(date_field)
            if pd.notna(date_value):
                if isinstance(date_value, str) and date_value.strip():
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
                        try:
                            parsed_date = datetime.strptime(date_value.strip(), fmt)
                            return parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
                    return str(date_value).strip()
            return ''
        except Exception as e:
            logger.warning(f"Error processing date field {date_field}: {e}")
            return ''

    def create_manual_template(self):
        """Create manual template CSV"""
        os.makedirs(config.MANUAL_CA_DIR, exist_ok=True)

        template_path = os.path.join(config.MANUAL_CA_DIR, "cash_dividends.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['AAPL'],
                'dividend_per_share': [0.25],
                'currency': ['USD'],
                'account': ['Credit'],
                'payable_date': ['2025-02-15']
            }).to_csv(template_path, index=False)

            logger.info(f"Created cash dividends manual template: {template_path}")