#!/usr/bin/env python3
"""
Portfolio corporate actions engine
"""

import pandas as pd
from typing import List, Dict, Set
from decimal import Decimal
from collections import defaultdict
from .models import (Position, CorporateAction, SymbolChange, Delisting, Merger, 
                     StockSplit, StockDividend, CashDividend, PortfolioUpdate, UnexplainedPosition)
from .loaders import CorporateActionsLoader
from .config import config
import logging

logger = logging.getLogger(__name__)

class PortfolioEngine:
    """Applies corporate actions to portfolio positions"""
    
    def __init__(self):
        self.loader = CorporateActionsLoader()
        self.corporate_actions: List[CorporateAction] = []
        self.portfolio_positions: List[Position] = []
        self.updates: List[PortfolioUpdate] = []
        self.unexplained_positions: List[UnexplainedPosition] = []
        self.cash_adjustments: Dict[str, Decimal] = {}
    
    def load_start_of_day_portfolio(self) -> List[Position]:
        """Load start of day portfolio positions"""
        logger.info(f"Loading portfolio from {config.START_OF_DAY_PORTFOLIO}")
        
        df = pd.read_csv(config.START_OF_DAY_PORTFOLIO)
        positions = []
        
        for _, row in df.iterrows():
            position = Position(
                symbol=row['symbol'],
                quantity=Decimal(str(row['quantity']))
            )
            positions.append(position)
        
        logger.info(f"Loaded {len(positions)} portfolio positions")
        return positions
    
    def process_portfolio(self) -> Dict:
        """Main processing function"""
        logger.info("Starting portfolio corporate actions processing...")
        
        # Load data
        self.corporate_actions = self.loader.load_all()
        self.portfolio_positions = self.load_start_of_day_portfolio()
        
        # Group corporate actions by symbol
        ca_lookup = defaultdict(list)
        for action in self.corporate_actions:
            ca_lookup[action.symbol].append(action)
        
        # Process each position
        for position in self.portfolio_positions:
            if position.symbol in ca_lookup:
                # Apply all corporate actions for this symbol
                current_positions = [position]
                
                for action in ca_lookup[position.symbol]:
                    new_current_positions = []
                    for current_pos in current_positions:
                        update = self.apply_corporate_action(current_pos, action)
                        self.updates.append(update)
                        new_current_positions.extend(update.new_positions)
                    current_positions = new_current_positions
            else:
                # Check if this is an unexplained position
                unexplained = UnexplainedPosition(
                    position=position,
                    reason="No corporate action found to explain position"
                )
                self.unexplained_positions.append(unexplained)
        
        # Check for unexplained positions and raise error if any
        if self.unexplained_positions:
            self.handle_unexplained_positions()
        
        return self.generate_results()
    
    def apply_corporate_action(self, position: Position, action: CorporateAction) -> PortfolioUpdate:
        """Apply corporate action to a position"""
        new_positions = []
        cash_adjustments = {}
        
        if isinstance(action, SymbolChange):
            # Simple symbol change
            new_position = Position(
                symbol=action.new_symbol,
                quantity=position.quantity
            )
            new_positions.append(new_position)
            
        elif isinstance(action, Delisting):
            # Convert to cash
            cash_amount = position.quantity * action.value_per_share
            cash_adjustments[action.currency] = cash_adjustments.get(action.currency, Decimal('0')) + cash_amount
            
        elif isinstance(action, Merger):
            # Apply each merger component
            for component in action.components:
                if component.type == 'stock':
                    new_quantity = position.quantity * component.value
                    new_position = Position(
                        symbol=component.parent,
                        quantity=new_quantity
                    )
                    new_positions.append(new_position)
                elif component.type == 'cash':
                    cash_amount = position.quantity * component.value
                    currency = component.currency or 'USD'
                    cash_adjustments[currency] = cash_adjustments.get(currency, Decimal('0')) + cash_amount
        
        elif isinstance(action, StockSplit):
            # Multiply shares by split ratio
            new_quantity = position.quantity * action.split_ratio
            new_position = Position(
                symbol=position.symbol,
                quantity=new_quantity
            )
            new_positions.append(new_position)
            
        elif isinstance(action, StockDividend):
            # Add dividend shares
            dividend_shares = position.quantity * action.dividend_ratio
            new_position = Position(
                symbol=position.symbol,
                quantity=position.quantity + dividend_shares
            )
            new_positions.append(new_position)
            
        elif isinstance(action, CashDividend):
            # Keep original position and add cash
            new_positions.append(position)
            cash_amount = position.quantity * action.dividend_per_share
            cash_adjustments[action.currency] = cash_adjustments.get(action.currency, Decimal('0')) + cash_amount
        
        # Update global cash adjustments
        for currency, amount in cash_adjustments.items():
            self.cash_adjustments[currency] = self.cash_adjustments.get(currency, Decimal('0')) + amount
        
        return PortfolioUpdate(
            original_position=position,
            action=action,
            new_positions=new_positions,
            cash_adjustments=cash_adjustments
        )
    
    def handle_unexplained_positions(self):
        """Handle unexplained positions - raise error"""
        error_msg = f"Found {len(self.unexplained_positions)} unexplained positions:\n"
        for unexplained in self.unexplained_positions:
            error_msg += f"  - {unexplained.position.symbol}: {unexplained.position.quantity} shares\n"
        error_msg += "\nAdd manual corporate actions or investigate these positions."
        
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    def generate_results(self) -> Dict:
        """Generate final results"""
        # Calculate final positions by consolidating all positions with same symbol
        final_positions = defaultdict(Decimal)
        
        for update in self.updates:
            for new_position in update.new_positions:
                final_positions[new_position.symbol] += new_position.quantity
        
        return {
            'original_positions': len(self.portfolio_positions),
            'corporate_actions_applied': len(self.updates),
            'final_positions': dict(final_positions),
            'cash_adjustments': dict(self.cash_adjustments),
            'updates': self.updates
        }