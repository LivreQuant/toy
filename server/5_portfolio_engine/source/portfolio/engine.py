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
        all_actions = []

        # Load from each handler - summary logging only
        handler_summary = {}
        for handler in self.handlers:
            actions = handler.load_all_data()
            all_actions.extend(actions)
            handler_name = handler.__class__.__name__.replace('Handler', '')
            handler_summary[handler_name] = len(actions)

        self.corporate_actions = all_actions

        # Log summary
        logger.info("Corporate actions loaded:")
        for handler_name, count in handler_summary.items():
            if count > 0:
                logger.info(f"  {handler_name}: {count}")

        return self.corporate_actions

    def load_users(self, sod_dir: str) -> Dict[str, UserPortfolio]:
        """Load portfolios and accounts for all users"""
        logger.info(f"Loading user data from {sod_dir}")

        self.user_portfolios = {}

        # Look for portfolio files in the directory
        if not os.path.exists(sod_dir):
            raise ValueError(f"SOD directory does not exist: {sod_dir}")

        # Find all user directories
        users_dirs = [u for u in os.listdir(sod_dir) if os.path.isdir(os.path.join(sod_dir, u))]

        for user_dir in users_dirs:
            user_id = os.path.basename(user_dir)
            full_user_dir = os.path.join(sod_dir, user_dir)

            # Load portfolio positions
            portfolio_path = os.path.join(full_user_dir, 'portfolio.csv')
            positions = self._load_user_positions(portfolio_path)

            # Load account balances
            accounts_path = os.path.join(full_user_dir, "accounts.csv")
            accounts = self._load_user_accounts(accounts_path, user_id)

            # Create user portfolio
            user_portfolio = UserPortfolio(
                user_id=user_id,
                positions=positions,
                accounts=accounts
            )

            self.user_portfolios[user_id] = user_portfolio

            # Log what we loaded for this user
            logger.info(f"User {user_id}:")
            logger.info(f"  Positions: {len(positions)}")
            for pos in positions:
                logger.info(f"    {pos.symbol}: {pos.quantity}")
            logger.info(f"  Accounts: {accounts}")

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
        else:
            logger.info(f"No portfolio file found at {portfolio_path}")

        return positions

    def _load_user_accounts(self, accounts_path: str, user_id: str) -> Dict[str, Decimal]:
        """Load account balances for a single user"""
        accounts = {}

        if os.path.exists(accounts_path):
            df = pd.read_csv(accounts_path)
            for _, row in df.iterrows():
                accounts[row['currency']] = Decimal(str(row['balance']))
            logger.info(f"Loaded accounts from {accounts_path}: {accounts}")
        else:
            # Default account if no accounts file
            accounts['USD'] = Decimal('100000')  # Set default to 100000 like you expect
            logger.info(f"No accounts file found at {accounts_path}, created default: {accounts}")

        return accounts

    def process_all_users(self) -> Dict[str, UserUpdate]:
        """Process corporate actions for all users"""
        logger.info("=== STARTING USER PROCESSING ===")

        # Load corporate actions if not already loaded
        if not self.corporate_actions:
            self.load_corporate_actions()

        # Process each user
        total_actions_applied = 0
        for user_id, user_portfolio in self.user_portfolios.items():
            logger.info(f"\n--- Processing user: {user_id} ---")
            logger.info(f"Starting accounts: {user_portfolio.accounts}")
            logger.info(f"Starting positions: {len(user_portfolio.positions)}")

            user_update = self._process_user_portfolio(user_portfolio)
            self.user_updates[user_id] = user_update
            total_actions_applied += len(user_update.updates)

            logger.info(f"Final accounts: {user_update.final_accounts}")
            logger.info(f"Final positions: {len([q for q in user_update.final_positions.values() if q != 0])}")
            logger.info(f"Actions applied: {len(user_update.updates)}")

        logger.info(f"\n=== PROCESSING COMPLETE ===")
        logger.info(f"Total actions applied across all users: {total_actions_applied}")

        # Check for unexplained positions across all users
        if self.unexplained_positions:
            self._handle_unexplained_positions()

        return self.user_updates

    def _process_user_portfolio(self, user_portfolio: UserPortfolio) -> UserUpdate:
        """Process corporate actions for a single user"""
        logger.info(f"Processing portfolio for user {user_portfolio.user_id}")

        user_updates = []
        final_positions = defaultdict(Decimal)
        final_accounts = user_portfolio.accounts.copy()

        logger.info(f"Initial final_accounts (copy): {final_accounts}")

        # Group corporate actions by symbol
        ca_lookup = defaultdict(list)
        for action in self.corporate_actions:
            ca_lookup[action.symbol].append(action)

        logger.info(f"Corporate actions available for {len(ca_lookup)} symbols")

        # Process each position
        actions_applied = 0
        logger.info(f"Processing {len(user_portfolio.positions)} positions")

        for i, position in enumerate(user_portfolio.positions):
            logger.info(f"  Position {i + 1}: {position.symbol} - {position.quantity}")

            if position.symbol in ca_lookup:
                logger.info(f"    Found {len(ca_lookup[position.symbol])} corporate actions for {position.symbol}")

                # Apply all corporate actions for this symbol
                current_positions = [position]

                for action in ca_lookup[position.symbol]:
                    logger.info(f"    Applying {action.action_type} to {position.symbol}")
                    new_current_positions = []
                    for current_pos in current_positions:
                        update = self._apply_corporate_action(current_pos, action)
                        if update:
                            user_updates.append(update)
                            new_current_positions.extend(update.new_positions)
                            actions_applied += 1

                            # Update account balances
                            logger.info(f"    Cash adjustments: {update.cash_adjustments}")
                            for currency, amount in update.cash_adjustments.items():
                                if currency in final_accounts:
                                    old_balance = final_accounts[currency]
                                    final_accounts[currency] += amount
                                    logger.info(
                                        f"    Updated {currency}: {old_balance} + {amount} = {final_accounts[currency]}")
                                else:
                                    final_accounts[currency] = amount
                                    logger.info(f"    Created {currency} account: {amount}")
                        else:
                            new_current_positions.append(current_pos)
                    current_positions = new_current_positions

                # Add final positions for this symbol
                for pos in current_positions:
                    final_positions[pos.symbol] += pos.quantity
                    logger.info(f"    Final position: {pos.symbol} = {final_positions[pos.symbol]}")
            else:
                logger.info(f"    No corporate actions found for {position.symbol}")
                # No corporate action found - keep original position
                final_positions[position.symbol] += position.quantity
                logger.info(f"    Kept original position: {position.symbol} = {final_positions[position.symbol]}")

        logger.info(f"Completed processing. Actions applied: {actions_applied}")
        logger.info(f"Final accounts before return: {final_accounts}")
        logger.info(f"Final positions before return: {dict(final_positions)}")

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
            if hasattr(h, 'can_handle') and h.can_handle(action):
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
        """Handle unexplained positions - log summary only"""
        logger.warning(f"Found {len(self.unexplained_positions)} unexplained positions across all users")

    def save_results(self, output_dir: str):
        """Save results for all users"""
        logger.info(f"=== SAVING RESULTS ===")
        os.makedirs(output_dir, exist_ok=True)

        for user_id, user_update in self.user_updates.items():
            logger.info(f"Saving results for user {user_id}")
            logger.info(f"  Accounts to save: {user_update.final_accounts}")
            logger.info(f"  Positions to save: {user_update.final_positions}")

            # Save final portfolio
            portfolio_df = pd.DataFrame([
                {'symbol': symbol, 'quantity': float(quantity)}
                for symbol, quantity in user_update.final_positions.items()
                if quantity != 0  # Only save non-zero positions
            ])
            portfolio_path = os.path.join(output_dir, f"{user_id}_final_portfolio.csv")
            portfolio_df.to_csv(portfolio_path, index=False)
            logger.info(f"  Saved portfolio: {portfolio_path}")

            # Save final accounts
            accounts_df = pd.DataFrame([
                {'currency': currency, 'balance': float(balance)}
                for currency, balance in user_update.final_accounts.items()
            ])
            accounts_path = os.path.join(output_dir, f"{user_id}_final_accounts.csv")
            accounts_df.to_csv(accounts_path, index=False)
            logger.info(f"  Saved accounts: {accounts_path}")

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

    def can_handle(self, action: CorporateAction) -> bool:
        """Check if any handler can process the given action (for backward compatibility)"""
        for handler in self.handlers:
            if hasattr(handler, 'can_handle') and handler.can_handle(action):
                return True
        return False