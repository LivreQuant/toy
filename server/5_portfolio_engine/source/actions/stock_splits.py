#!/usr/bin/env python3
"""
Stock splits - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, StockSplit, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class StockSplitsHandler:
    """Complete stock splits handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[StockSplit] = []

    def load_unified_data(self) -> List[StockSplit]:
        """Load unified stock splits from CSV"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_stock_splits.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                split_ratio = self._calculate_split_ratio(row)

                action = StockSplit(
                    symbol=row['master_symbol'],
                    action_type='STOCK_SPLIT',
                    effective_date=self._safe_get_date(row, 'ex_date'),
                    source=f"unified_{row['source']}",
                    split_ratio=split_ratio
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified stock splits")

        return actions

    def load_manual_data(self) -> List[StockSplit]:
        """Load manual stock splits overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "stock_splits.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = StockSplit(
                    symbol=row['symbol'],
                    action_type='STOCK_SPLIT',
                    effective_date='manual',
                    source='manual',
                    split_ratio=Decimal(str(row['split_ratio']))
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual stock splits")

        return actions

    def load_all_data(self) -> List[StockSplit]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: StockSplit, current_date: str) -> List[Position]:
        """Apply stock split to portfolio - adjust quantity"""
        new_quantity = position.quantity * action.split_ratio

        new_position = Position(
            symbol=position.symbol,
            quantity=new_quantity
        )

        logger.info(f"Stock split for {position.symbol}: {action.split_ratio}:1, new quantity: {new_quantity}")

        return [new_position]

    def apply_account_action(self, position: Position, action: StockSplit, current_date: str) -> Dict[str, Decimal]:
        """Apply stock split to account - no cash impact"""
        # Stock splits don't generate cash
        return {}

    def apply_action(self, position: Position, action: StockSplit, current_date: str) -> PortfolioUpdate:
        """Apply complete stock split action"""
        new_positions = self.apply_portfolio_action(position, action, current_date)
        cash_adjustments = self.apply_account_action(position, action, current_date)

        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )

    def _calculate_split_ratio(self, row) -> Decimal:
        """Calculate split ratio from various possible fields"""
        # Try direct split_ratio field first
        if pd.notna(row.get('split_ratio')):
            try:
                return Decimal(str(row['split_ratio']))
            except (ValueError, TypeError):
                pass

        # Try old_rate/new_rate calculation
        if pd.notna(row.get('old_rate')) and pd.notna(row.get('new_rate')):
            try:
                old_rate = float(row['old_rate'])
                new_rate = float(row['new_rate'])
                if new_rate > 0:
                    return Decimal(str(old_rate / new_rate))
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # Default to 1:1 (no split)
        logger.warning(f"Could not determine split ratio for {row.get('master_symbol')}, defaulting to 1.0")
        return Decimal('1.0')

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

        template_path = os.path.join(config.MANUAL_CA_DIR, "stock_splits.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['AAPL'],
                'split_ratio': [2.0]
            }).to_csv(template_path, index=False)

            logger.info(f"Created stock splits manual template: {template_path}")