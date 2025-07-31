# source/orchestration/persistence/managers/shared_data_manager.py
import logging
from typing import Dict

from source.orchestration.persistence.managers.manager_initializer import ManagerInitializer
from source.orchestration.persistence.managers.user_context_manager import UserContextManager


class SharedDataManager:
    """Manages shared data initialization across all users"""

    def __init__(self, user_context_manager: UserContextManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_context_manager = user_context_manager
        self.manager_initializer = ManagerInitializer()

    def initialize_shared_data(self, global_data: Dict) -> bool:
        """Initialize shared data that's common to all users (universe, equity, fx)"""
        try:
            self.logger.info("🌍 INITIALIZING SHARED DATA")
            self.logger.info("=" * 60)

            # Set universe for all users
            universe_data = global_data.get('universe', {})
            if not universe_data:
                self.logger.warning("⚠️ No universe data found")
                return False

            self.logger.info(f"📊 Initializing universe with {len(universe_data)} symbols")

            user_contexts = self.user_context_manager.get_all_user_contexts()

            for user_id, user_context in user_contexts.items():
                self.logger.debug(f"🔄 Setting universe for user {user_id}")

                def _init_universe():
                    return self.manager_initializer.initialize_universe(universe_data)

                success = self.user_context_manager.execute_with_user_context(user_id, _init_universe)
                if not success:
                    self.logger.error(f"❌ Failed to initialize universe for user {user_id}")
                    return False

            self.logger.info("✅ Shared data (universe) initialized for all users")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing shared data: {e}")
            return False

    def validate_shared_data(self, global_data: Dict) -> bool:
        """Validate that all required shared data is present"""
        errors = []

        if not global_data.get('universe'):
            errors.append("Missing universe data")

        if not global_data.get('fx'):
            errors.append("Missing FX data")

        if not global_data.get('equity'):
            errors.append("Missing equity data")

        if errors:
            error_msg = f"Shared data validation failed: {', '.join(errors)}"
            self.logger.error(f"❌ {error_msg}")
            return False

        return True

    def get_shared_data_summary(self, global_data: Dict) -> Dict:
        """Get summary of shared data"""
        return {
            'universe_symbols': len(global_data.get('universe', {})),
            'fx_rates': len(global_data.get('fx', [])),
            'equity_states': len(global_data.get('equity', []))
        }