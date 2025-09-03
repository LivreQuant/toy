#!/usr/bin/env python3
"""
Symbol changes - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, SymbolChange, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class SymbolChangesHandler:
    """Complete symbol changes handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[SymbolChange] = []

    def load_unified_data(self) -> List[SymbolChange]:
        """Load unified symbol changes from CSV"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_symbol_changes.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = SymbolChange(
                    symbol=row['old_symbol'],
                    action_type='SYMBOL_CHANGE',
                    effective_date=self._safe_get_date(row, 'change_date'),
                    source=f"unified_{row['source']}",
                    old_symbol=row['old_symbol'],
                    new_symbol=row['new_symbol']
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified symbol changes")

        return actions

    def load_manual_data(self) -> List[SymbolChange]:
        """Load manual symbol changes overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "symbol_changes.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = SymbolChange(
                    symbol=row['symbol'],
                    action_type='SYMBOL_CHANGE',
                    effective_date='manual',
                    source='manual',
                    old_symbol=row['symbol'],
                    new_symbol=row['new_symbol']
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual symbol changes")

        return actions

    def load_all_data(self) -> List[SymbolChange]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: SymbolChange, current_date: str) -> List[Position]:
        """Apply symbol change to portfolio - update symbol"""
        new_position = Position(
            symbol=action.new_symbol,
            quantity=position.quantity
        )

        logger.info(
            f"Symbol change for {position.symbol}: changed to {action.new_symbol}, quantity unchanged: {position.quantity}")

        return [new_position]

    def apply_account_action(self, position: Position, action: SymbolChange, current_date: str) -> Dict[str, Decimal]:
        """Apply symbol change to account - no cash impact"""
        # Symbol changes don't generate cash
        return {}

    def apply_action(self, position: Position, action: SymbolChange, current_date: str) -> PortfolioUpdate:
        """Apply complete symbol change action"""
        new_positions = self.apply_portfolio_action(position, action, current_date)
        cash_adjustments = self.apply_account_action(position, action, current_date)

        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )

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

        template_path = os.path.join(config.MANUAL_CA_DIR, "symbol_changes.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['GE'],
                'new_symbol': ['GEW']
            }).to_csv(template_path, index=False)

            logger.info(f"Created symbol changes manual template: {template_path}")