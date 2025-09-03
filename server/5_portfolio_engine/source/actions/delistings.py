#!/usr/bin/env python3
"""
Delistings - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, Delisting, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class DelistingsHandler:
    """Complete delistings handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[Delisting] = []

    def load_unified_data(self) -> List[Delisting]:
        """Load unified delistings from CSV"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_delisting.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = Delisting(
                    symbol=row['master_symbol'],
                    action_type='DELISTING',
                    effective_date=self._safe_get_date(row, 'delisting_date'),
                    source=f"unified_{row['source']}",
                    currency='USD',  # Default to USD, manual override if needed
                    account='Credit',
                    value_per_share=Decimal('0')  # Needs manual override for actual value
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified delistings")

        return actions

    def load_manual_data(self) -> List[Delisting]:
        """Load manual delistings overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "delistings.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = Delisting(
                    symbol=row['symbol'],
                    action_type='DELISTING',
                    effective_date='manual',
                    source='manual',
                    currency=row['currency'],
                    account=row['account'],
                    value_per_share=Decimal(str(row['value']))
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual delistings")

        return actions

    def load_all_data(self) -> List[Delisting]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: Delisting, current_date: str) -> List[Position]:
        """Apply delisting to portfolio - remove position"""
        # Portfolio action: Position is completely removed (no new positions)
        logger.info(f"Delisting for {position.symbol}: position removed from portfolio")
        return []

    def apply_account_action(self, position: Position, action: Delisting, current_date: str) -> Dict[str, Decimal]:
        """Apply delisting to account - credit delisting value"""
        # Account action: Credit account with delisting value
        total_value = position.quantity * action.value_per_share

        if total_value > 0:
            logger.info(
                f"Delisting for {position.symbol}: {total_value} {action.currency} credited to {action.account}")
            return {action.currency: total_value}
        else:
            logger.info(f"Delisting for {position.symbol}: no value credited (worthless delisting)")
            return {}

    def apply_action(self, position: Position, action: Delisting, current_date: str) -> PortfolioUpdate:
        """Apply complete delisting action"""
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

        template_path = os.path.join(config.MANUAL_CA_DIR, "delistings.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['BBBY'],
                'currency': ['USD'],
                'account': ['Credit'],
                'value': [0.00]
            }).to_csv(template_path, index=False)

            logger.info(f"Created delistings manual template: {template_path}")