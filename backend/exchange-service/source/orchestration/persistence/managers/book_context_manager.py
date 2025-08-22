# source/orchestration/persistence/managers/book_context_manager.py
import logging
from typing import Callable, Any

from source.orchestration.app_state import state_manager as app_state_module
from source.orchestration.coordination.exchange_manager import ExchangeGroupManager


class BookContextManager:
    """Manages book context switching for multi-book operations"""

    def __init__(self, exchange_group_manager: ExchangeGroupManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager

    def execute_with_book_context(self, book_id: str, func: Callable) -> Any:
        """Execute a function within a specific book's context"""
        try:
            # Get book context
            book_context = self.exchange_group_manager.get_book_context(book_id)
            if not book_context:
                self.logger.error(f"❌ book context not found for {book_id}")
                return False

            # Store original app_state
            original_app_state = app_state_module.app_state

            # Switch global app_state to this book's state
            app_state_module.app_state = book_context.app_state
            return func()

        except Exception as e:
            self.logger.error(f"❌ Error in book context execution: {e}")
            return False
        finally:
            # Restore original app_state
            app_state_module.app_state = original_app_state

    def initialize_book_managers(self, book_id: str, book_data: dict, global_data: dict, manager_initializer) -> bool:
        """Initialize all managers for a specific book"""
        try:
            self.logger.debug(f"🔄 Initializing managers for book {book_id}")

            def _init_book():
                # Initialize in correct order (portfolio before accounts for NAV calculation)
                initialization_steps = [
                    ("FX rates", lambda: manager_initializer.initialize_fx(global_data['fx'], None)),
                    ("Portfolio",
                     lambda: manager_initializer.initialize_portfolio(book_data.get('portfolio', {}), None)),
                    ("Accounts", lambda: manager_initializer.initialize_accounts(book_data.get('accounts', {}), None)),
                    ("Equity data", lambda: manager_initializer.initialize_equity(global_data['equity'], None)),
                    ("Impact states", lambda: manager_initializer.initialize_impact(book_data.get('impact', {}), None)),
                    ("Orders", lambda: manager_initializer.initialize_orders(book_data.get('orders', {}), None)),
                    ("Returns", lambda: manager_initializer.initialize_returns(book_data.get('returns', {}), None))
                ]

                for step_name, step_func in initialization_steps:
                    try:
                        self.logger.debug(f"   🔄 Initializing {step_name} for {book_id}...")
                        success = step_func()
                        if success:
                            self.logger.debug(f"   ✅ {step_name} initialized for {book_id}")
                        else:
                            self.logger.error(f"   ❌ {step_name} initialization failed for {book_id}")
                            return False
                    except Exception as e:
                        self.logger.error(f"   ❌ Error initializing {step_name} for {book_id}: {e}")
                        return False

                # CRITICAL FIX: Mark initialization as complete after all steps succeed
                from source.orchestration.app_state.state_manager import app_state
                app_state.mark_initialization_complete()
                self.logger.info(f"✅ book {book_id} initialization marked complete")

                return True

            return self.execute_with_book_context(book_id, _init_book)

        except Exception as e:
            self.logger.error(f"❌ Error initializing book managers for {book_id}: {e}")
            return False

    def get_all_book_contexts(self) -> dict:
        """Get all available book contexts"""
        if not self.exchange_group_manager:
            return {}
        return self.exchange_group_manager.book_contexts

    def validate_book_context(self, book_id: str) -> bool:
        """Validate that a book context exists and is properly initialized"""
        book_context = self.exchange_group_manager.get_book_context(book_id)
        if not book_context:
            return False

        # Check if app_state exists and has required managers
        app_state = book_context.app_state
        required_managers = ['portfolio_manager', 'account_manager', 'order_manager', 'fx_manager']

        for manager_name in required_managers:
            if not hasattr(app_state, manager_name):
                self.logger.error(f"❌ book {book_id} missing required manager: {manager_name}")
                return False

        return True