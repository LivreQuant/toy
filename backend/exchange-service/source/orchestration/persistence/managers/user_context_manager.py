# source/orchestration/persistence/managers/user_context_manager.py
import logging
from typing import Callable, Any

from source.orchestration.app_state import state_manager as app_state_module
from source.orchestration.coordination.exchange_manager import ExchangeGroupManager


class UserContextManager:
    """Manages user context switching for multi-user operations"""

    def __init__(self, exchange_group_manager: ExchangeGroupManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager

    def execute_with_user_context(self, user_id: str, func: Callable) -> Any:
        """Execute a function within a specific user's context"""
        try:
            # Get user context
            user_context = self.exchange_group_manager.get_user_context(user_id)
            if not user_context:
                self.logger.error(f"❌ User context not found for {user_id}")
                return False

            # Store original app_state
            original_app_state = app_state_module.app_state

            # Switch global app_state to this user's state
            app_state_module.app_state = user_context.app_state
            return func()

        except Exception as e:
            self.logger.error(f"❌ Error in user context execution: {e}")
            return False
        finally:
            # Restore original app_state
            app_state_module.app_state = original_app_state

    def initialize_user_managers(self, user_id: str, user_data: dict, global_data: dict, manager_initializer) -> bool:
        """Initialize all managers for a specific user"""
        try:
            self.logger.debug(f"🔄 Initializing managers for user {user_id}")

            def _init_user():
                # Initialize in correct order (portfolio before accounts for NAV calculation)
                initialization_steps = [
                    ("FX rates", lambda: manager_initializer.initialize_fx(global_data['fx'], None)),
                    ("Portfolio",
                     lambda: manager_initializer.initialize_portfolio(user_data.get('portfolio', {}), None)),
                    ("Accounts", lambda: manager_initializer.initialize_accounts(user_data.get('accounts', {}), None)),
                    ("Equity data", lambda: manager_initializer.initialize_equity(global_data['equity'], None)),
                    ("Impact states", lambda: manager_initializer.initialize_impact(user_data.get('impact', {}), None)),
                    ("Orders", lambda: manager_initializer.initialize_orders(user_data.get('orders', {}), None)),
                    ("Returns", lambda: manager_initializer.initialize_returns(user_data.get('returns', {}), None))
                ]

                for step_name, step_func in initialization_steps:
                    try:
                        self.logger.debug(f"   🔄 Initializing {step_name} for {user_id}...")
                        success = step_func()
                        if success:
                            self.logger.debug(f"   ✅ {step_name} initialized for {user_id}")
                        else:
                            self.logger.error(f"   ❌ {step_name} initialization failed for {user_id}")
                            return False
                    except Exception as e:
                        self.logger.error(f"   ❌ Error initializing {step_name} for {user_id}: {e}")
                        return False

                # CRITICAL FIX: Mark initialization as complete after all steps succeed
                from source.orchestration.app_state.state_manager import app_state
                app_state.mark_initialization_complete()
                self.logger.info(f"✅ User {user_id} initialization marked complete")

                return True

            return self.execute_with_user_context(user_id, _init_user)

        except Exception as e:
            self.logger.error(f"❌ Error initializing user managers for {user_id}: {e}")
            return False

    def get_all_user_contexts(self) -> dict:
        """Get all available user contexts"""
        if not self.exchange_group_manager:
            return {}
        return self.exchange_group_manager.user_contexts

    def validate_user_context(self, user_id: str) -> bool:
        """Validate that a user context exists and is properly initialized"""
        user_context = self.exchange_group_manager.get_user_context(user_id)
        if not user_context:
            return False

        # Check if app_state exists and has required managers
        app_state = user_context.app_state
        required_managers = ['portfolio_manager', 'account_manager', 'order_manager', 'fx_manager']

        for manager_name in required_managers:
            if not hasattr(app_state, manager_name):
                self.logger.error(f"❌ User {user_id} missing required manager: {manager_name}")
                return False

        return True