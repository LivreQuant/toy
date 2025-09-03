#!/usr/bin/env python3
"""
Mergers - complete handler including loading, portfolio actions, and account actions
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
from source.portfolio.models import Position, Merger, MergerComponent, PortfolioUpdate
from source.config import config
import logging

logger = logging.getLogger(__name__)


class MergersHandler:
    """Complete mergers handler - loading, portfolio actions, account actions"""

    def __init__(self):
        self.actions: List[Merger] = []

    def load_unified_data(self) -> List[Merger]:
        """Load unified mergers from CSV"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_mergers.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                components = self._build_merger_components(row)

                action = Merger(
                    symbol=row['acquiree_symbol'],
                    action_type='MERGER',
                    effective_date=self._safe_get_date(row, 'ex_date'),
                    source=f"unified_{row['source']}",
                    components=components
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} unified mergers")

        return actions

    def load_manual_data(self) -> List[Merger]:
        """Load manual mergers overrides"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "mergers.csv")
        actions = []

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            merger_dict = {}

            # Group components by symbol
            for _, row in df.iterrows():
                symbol = row['symbol']
                if symbol not in merger_dict:
                    merger_dict[symbol] = []

                component = MergerComponent(
                    type=row['type'],
                    parent=row['parent'],
                    currency=row.get('currency') if pd.notna(row.get('currency')) else None,
                    value=Decimal(str(row['value']))
                )
                merger_dict[symbol].append(component)

            # Create merger actions
            for symbol, components in merger_dict.items():
                action = Merger(
                    symbol=symbol,
                    action_type='MERGER',
                    effective_date='manual',
                    source='manual',
                    components=components
                )
                actions.append(action)

            logger.info(f"Loaded {len(actions)} manual mergers")

        return actions

    def load_all_data(self) -> List[Merger]:
        """Load unified + manual data with manual overrides"""
        unified = self.load_unified_data()
        manual = self.load_manual_data()

        # Manual overrides unified (by symbol)
        manual_symbols = {action.symbol for action in manual}
        unified_filtered = [action for action in unified if action.symbol not in manual_symbols]

        self.actions = manual + unified_filtered
        return self.actions

    def apply_portfolio_action(self, position: Position, action: Merger, current_date: str) -> List[Position]:
        """Apply merger to portfolio - create new stock positions"""
        new_positions = []

        for component in action.components:
            if component.type == 'stock':
                # Create new stock position
                new_quantity = position.quantity * component.value
                new_position = Position(
                    symbol=component.parent,
                    quantity=new_quantity
                )
                new_positions.append(new_position)
                logger.info(f"Merger for {position.symbol}: created {new_quantity} shares of {component.parent}")

        return new_positions

    def apply_account_action(self, position: Position, action: Merger, current_date: str) -> Dict[str, Decimal]:
        """Apply merger to account - credit cash components"""
        cash_adjustments = {}

        for component in action.components:
            if component.type == 'cash':
                # Add cash adjustment
                cash_amount = position.quantity * component.value
                currency = component.currency or 'USD'

                if currency in cash_adjustments:
                    cash_adjustments[currency] += cash_amount
                else:
                    cash_adjustments[currency] = cash_amount

                logger.info(f"Merger for {position.symbol}: {cash_amount} {currency} credited to account")

        return cash_adjustments

    def apply_action(self, position: Position, action: Merger, current_date: str) -> PortfolioUpdate:
        """Apply complete merger action"""
        new_positions = self.apply_portfolio_action(position, action, current_date)
        cash_adjustments = self.apply_account_action(position, action, current_date)

        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )

    def _build_merger_components(self, row) -> List[MergerComponent]:
        """Build merger components from unified merger row"""
        components = []

        # Add stock component if acquirer info available
        if pd.notna(row.get('acquirer_symbol')) and pd.notna(row.get('acquirer_rate')):
            try:
                acquirer_rate = float(row['acquirer_rate'])
                if acquirer_rate > 0:
                    components.append(MergerComponent(
                        type='stock',
                        parent=row['acquirer_symbol'],
                        currency=None,
                        value=Decimal(str(acquirer_rate))
                    ))
            except (ValueError, TypeError):
                logger.warning(f"Invalid acquirer_rate for {row.get('acquiree_symbol')}: {row.get('acquirer_rate')}")

        # Add cash component if cash rate available
        if pd.notna(row.get('cash_rate')):
            try:
                cash_rate = float(row['cash_rate'])
                if cash_rate > 0:
                    components.append(MergerComponent(
                        type='cash',
                        parent='Credit',
                        currency='USD',  # Default to USD
                        value=Decimal(str(cash_rate))
                    ))
            except (ValueError, TypeError):
                logger.warning(f"Invalid cash_rate for {row.get('acquiree_symbol')}: {row.get('cash_rate')}")

        # If no components found, create a placeholder that needs manual override
        if not components:
            components.append(MergerComponent(
                type='cash',
                parent='Credit',
                currency='USD',
                value=Decimal('0')  # Needs manual override
            ))
            logger.warning(f"No valid merger components found for {row.get('acquiree_symbol')}, added placeholder")

        return components

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

        template_path = os.path.join(config.MANUAL_CA_DIR, "mergers.csv")
        if not os.path.exists(template_path):
            pd.DataFrame({
                'symbol': ['GE', 'GE'],
                'type': ['stock', 'cash'],
                'parent': ['GEW', 'Credit'],
                'currency': [None, 'USD'],
                'value': [0.34, 10.0]
            }).to_csv(template_path, index=False)

            logger.info(f"Created mergers manual template: {template_path}")