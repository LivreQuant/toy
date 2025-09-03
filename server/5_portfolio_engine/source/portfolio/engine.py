#!/usr/bin/env python3
"""
Portfolio corporate actions engine for multiple users
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from collections import defaultdict
from source.portfolio.models import (Position, CorporateAction, PortfolioUpdate, UnexplainedPosition,
                                     UserPortfolio, UserUpdate)
from source.actions.cash_dividends import CashDividendsHandler
from source.actions.delistings import DelistingsHandler
from source.actions.mergers import MergersHandler
from source.actions.stock_splits import StockSplitsHandler
from source.actions.stock_dividends import StockDividendsHandler
from source.actions.symbol_changes import SymbolChangesHandler
import logging

logger = logging.getLogger(__name__)


class MultiUserPortfolioEngine:
    """Applies corporate actions to multiple user portfolios"""

    def __init__(self, current_ymd: str = None):
        self.current_ymd = current_ymd
        self.corporate_actions: List[CorporateAction] = []
        self.user_portfolios: Dict[str, UserPortfolio] = {}
        self.user_updates: Dict[str, UserUpdate] = {}
        self.unexplained_positions: List[UnexplainedPosition] = []

        # Initialize action handlers
        self.handlers = [
            CashDividendsHandler(),
            DelistingsHandler(),
            MergersHandler(),
            StockSplitsHandler(),
            StockDividendsHandler(),
            SymbolChangesHandler()
        ]

    def load_corporate_actions(self) -> List[CorporateAction]:
        """Load all corporate actions for the day"""
        logger.info("Loading corporate actions for all action types...")

        all_actions = []

        # Load from each handler
        for handler in self.handlers:
            actions = handler.load_all_data()
            all_actions.extend(actions)
            logger.info(f"Loaded {len(actions)} actions from {handler.__class__.__name__}")

        self.corporate_actions = all_actions
        logger.info(f"Total corporate actions loaded: {len(self.corporate_actions)}")

        return self.corporate_actions

    def load_users(self, sod_dir: str) -> Dict[str, UserPortfolio]:
        """Load portfolios and accounts for all users"""
        logger.info(f"Loading user sod data from {sod_dir}")

        self.user_portfolios = {}

        # Look for portfolio files in the directory
        if not os.path.exists(sod_dir):
            raise ValueError(f"SOD directory does not exist: {sod_dir}")

        # Find all portfolio CSV files (assuming format: user_id_portfolio.csv and user_id_accounts.csv)
        users_dirs = [u for u in os.listdir(sod_dir)]

        for user_dir in users_dirs:
            user_id = os.path.basename(user_dir)

            # Load portfolio positions
            portfolio_path = os.path.join(user_dir, 'portfolio.csv')
            positions = self._load_user_positions(portfolio_path)

            # Load account balances
            accounts_path = os.path.join(user_dir, "accounts.csv")
            accounts = self._load_user_accounts(accounts_path)

            # Create user portfolio
            user_portfolio = UserPortfolio(
                user_id=user_id,
                positions=positions,
                accounts=accounts
            )

            self.user_portfolios[user_id] = user_portfolio
            logger.info(f"Loaded portfolio for user {user_id}: {len(positions)} positions, {len(accounts)} accounts")

        logger.info(f"Total users loaded: {len(self.user_portfolios)}")
        return self.user_portfolios

    def _load_user_positions(self, portfolio_path: str) -> List[Position]:
        """Load positions for a single user"""
        positions = []

        if os.path.exists(portfolio_path):
            df = pd.read_csv(portfolio_path)
            for _, row in df.iterrows():
                position = Position(
                    symbol=row['symbol'],
                    quantity=Decimal(str(row['quantity']))
                )
                positions.append(position)

        return positions

    def _load_user_accounts(self, accounts_path: str) -> Dict[str, Decimal]:
        """Load account balances for a single user"""
        accounts = {}

        if os.path.exists(accounts_path):
            df = pd.read_csv(accounts_path)
            for _, row in df.iterrows():
                accounts[row['currency']] = Decimal(str(row['balance']))
        else:
            # Default account if no accounts file
            accounts['USD'] = Decimal('0')
            logger.info(f"No accounts file found at {accounts_path}, created default USD account")

        return accounts

    def process_all_users(self) -> Dict[str, UserUpdate]:
        """Process corporate actions for all users"""
        logger.info("Processing corporate actions for all users...")

        # Load corporate actions if not already loaded
        if not self.corporate_actions:
            self.load_corporate_actions()

        # Process each user
        for user_id, user_portfolio in self.user_portfolios.items():
            logger.info(f"Processing user: {user_id}")
            user_update = self._process_user_portfolio(user_portfolio)
            self.user_updates[user_id] = user_update

        # Check for unexplained positions across all users
        if self.unexplained_positions:
            self._handle_unexplained_positions()

        return self.user_updates

    def _process_user_portfolio(self, user_portfolio: UserPortfolio) -> UserUpdate:
        """Process corporate actions for a single user"""
        user_updates = []
        final_positions = defaultdict(Decimal)
        final_accounts = user_portfolio.accounts.copy()

        # Group corporate actions by symbol
        ca_lookup = defaultdict(list)
        for action in self.corporate_actions:
            ca_lookup[action.symbol].append(action)

        # Process each position
        for position in user_portfolio.positions:
            if position.symbol in ca_lookup:
                # Apply all corporate actions for this symbol
                current_positions = [position]

                for action in ca_lookup[position.symbol]:
                    new_current_positions = []
                    for current_pos in current_positions:
                        update = self._apply_corporate_action(current_pos, action)
                        if update:
                            user_updates.append(update)
                            new_current_positions.extend(update.new_positions)

                            # Update account balances
                            for currency, amount in update.cash_adjustments.items():
                                if currency in final_accounts:
                                    final_accounts[currency] += amount
                                else:
                                    final_accounts[currency] = amount
                        else:
                            new_current_positions.append(current_pos)
                    current_positions = new_current_positions

                # Add final positions for this symbol
                for pos in current_positions:
                    final_positions[pos.symbol] += pos.quantity
            else:
                # No corporate action found - keep original position
                final_positions[position.symbol] += position.quantity

                # Log as unexplained if position shouldn't exist
                unexplained = UnexplainedPosition(
                    position=position,
                    reason=f"User {user_portfolio.user_id}: No corporate action found to explain position"
                )
                self.unexplained_positions.append(unexplained)

        return UserUpdate(
            user_id=user_portfolio.user_id,
            original_portfolio=user_portfolio,
            updates=user_updates,
            final_positions=dict(final_positions),
            final_accounts=dict(final_accounts)
        )

    def _apply_corporate_action(self, position: Position, action: CorporateAction) -> PortfolioUpdate:
        """Apply corporate action to a position using appropriate handler"""

        # Find appropriate handler
        handler = None
        for h in self.handlers:
            if h.can_handle(action):
                handler = h
                break

        if not handler:
            logger.warning(f"No handler found for action type: {action.action_type}")
            return None

        # Apply the action
        try:
            update = handler.apply_action(position, action, self.current_ymd)
            return update

        except Exception as e:
            logger.error(f"Error applying {action.action_type} to {position.symbol}: {e}")
            raise

    def _handle_unexplained_positions(self):
        """Handle unexplained positions - log warnings instead of errors for multi-user"""
        logger.warning(f"Found {len(self.unexplained_positions)} unexplained positions across all users:")
        for unexplained in self.unexplained_positions:
            logger.warning(
                f"  - {unexplained.reason}: {unexplained.position.symbol} ({unexplained.position.quantity} shares)")

        # For multi-user processing, we don't want to stop execution for unexplained positions
        # Instead, we log them and continue

    def save_results(self, output_dir: str):
        """Save results for all users"""
        logger.info(f"Saving results to {output_dir}")

        os.makedirs(output_dir, exist_ok=True)

        for user_id, user_update in self.user_updates.items():
            # Save final portfolio
            portfolio_df = pd.DataFrame([
                {'symbol': symbol, 'quantity': float(quantity)}
                for symbol, quantity in user_update.final_positions.items()
                if quantity != 0  # Only save non-zero positions
            ])
            portfolio_path = os.path.join(output_dir, f"{user_id}_final_portfolio.csv")
            portfolio_df.to_csv(portfolio_path, index=False)

            # Save final accounts
            accounts_df = pd.DataFrame([
                {'currency': currency, 'balance': float(balance)}
                for currency, balance in user_update.final_accounts.items()
            ])
            accounts_path = os.path.join(output_dir, f"{user_id}_final_accounts.csv")
            accounts_df.to_csv(accounts_path, index=False)

            logger.info(f"Saved results for user {user_id}")

        # Save summary
        self._save_summary(output_dir)

    def _save_summary(self, output_dir: str):
        """Save processing summary"""
        summary_data = []

        for user_id, user_update in self.user_updates.items():
            summary_data.append({
                'user_id': user_id,
                'original_positions': len(user_update.original_portfolio.positions),
                'final_positions': len([q for q in user_update.final_positions.values() if q != 0]),
                'corporate_actions_applied': len(user_update.updates),
                'original_accounts': len(user_update.original_portfolio.accounts),
                'final_accounts': len(user_update.final_accounts)
            })

        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(output_dir, "processing_summary.csv")
        summary_df.to_csv(summary_path, index=False)

        logger.info(f"Saved processing summary: {summary_path}")

    def can_handle(self, action: CorporateAction) -> bool:
        """Check if any handler can process the given action (for backward compatibility)"""
        for handler in self.handlers:
            if hasattr(handler, 'can_handle') and handler.can_handle(action):
                return True
        return False