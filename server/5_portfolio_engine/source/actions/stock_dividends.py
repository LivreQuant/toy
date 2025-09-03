#!/usr/bin/env python3
"""
Stock dividends - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, StockDividend, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class StockDividendsHandler:
    """Complete stock dividends handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[StockDividend] = []

    def load_unified_data(self) -> List[StockDividend]:
        """Load unified stock dividends from CSV"""
        # Note: No unified_stock_dividends.csv in your schema, but keeping for completeness
        file_path = os.path.join(config.CA_DATA_DIR, "unified_stock_dividends.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                try:
                    dividend_ratio = Decimal(str(row.get('dividend_ratio', 0)))
                except (ValueError, TypeError):
                    dividend_ratio = Decimal('0')
                    logger.warning(
                        f"Invalid dividend_ratio for {row.get('master_symbol')}: {row.get('dividend_ratio')}")

                action = StockDividend(
                    symbol=row['master_symbol'],
                    action_type='STOCK_DIVIDEND',
                    effective_date=self._safe_get_date(row, 'ex_date'),
                    source=f"unified_{row['source']}",
                    dividend_ratio=dividend_ratio,
                    payable_date=self._safe_get_date(row, 'payable_date')
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified stock dividends")

        return actions

    def load_manual_data(self) -> List[StockDividend]:
        """Load manual stock dividends overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "stock_dividends.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = StockDividend(
                    symbol=row['symbol'],
                    action_type='STOCK_DIVIDEND',
                    effective_date='manual',
                    source='manual',
                    dividend_ratio=Decimal(str(row['dividend_ratio'])),
                    payable_date=row.get('payable_date', '')
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual stock dividends")

        return actions

    def load_all_data(self) -> List[StockDividend]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: StockDividend, current_date: str) -> List[Position]:
        """Apply stock dividend to portfolio - add dividend shares or keep position"""
        if not self._is_payable_date(action, current_date):
            logger.info(f"Stock dividend for {position.symbol} not payable yet (payable: {action.payable_date})")
            return [position]

        if position.quantity >= 0:
            # Long position: Add dividend shares
            dividend_shares = position.quantity * action.dividend_ratio
            new_quantity = position.quantity + dividend_shares

            new_position = Position(
                symbol=position.symbol,
                quantity=new_quantity
            )

            logger.info(
                f"Stock dividend for {position.symbol}: {dividend_shares} shares added, new quantity: {new_quantity}")
            return [new_position]
        else:
            # Short position: Keep original position (will handle cash credit separately)
            logger.info(
                f"Stock dividend for short position {position.symbol}: position unchanged, cash credit required")
            return [position]

    def apply_account_action(self, position: Position, action: StockDividend, current_date: str) -> Dict[str, Decimal]:
        """Apply stock dividend to account - credit cash for short positions"""
        if not self._is_payable_date(action, current_date):
            return {}

        if position.quantity < 0:
            # Short position: Credit account for dividend equivalent
            # Note: This requires stock price data to calculate proper amount
            # For now, we'll log the requirement for manual calculation
            dividend_shares = abs(position.quantity) * action.dividend_ratio

            logger.warning(f"Stock dividend for short position {position.symbol}: "
                           f"{dividend_shares} shares equivalent needs manual cash credit calculation")

            # TODO: Implement proper cash calculation with price data
            # For now, return empty dict and rely on manual override
            return {}

        # Long positions don't generate cash for stock dividends
        return {}

    def apply_action(self, position: Position, action: StockDividend, current_date: str) -> PortfolioUpdate:
        """Apply complete stock dividend action"""
        new_positions = self.apply_portfolio_action(position, action, current_date)
        cash_adjustments = self.apply_account_action(position, action, current_date)

        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )

    def _is_payable_date(self, action: StockDividend, current_date: str) -> bool:
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

        template_path = os.path.join(config.MANUAL_CA_DIR, "stock_dividends.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['MSFT'],
                'dividend_ratio': [0.05],
                'payable_date': ['2025-01-15']
            }).to_csv(template_path, index=False)

            logger.info(f"Created stock dividends manual template: {template_path}")