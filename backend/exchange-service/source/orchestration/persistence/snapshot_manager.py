# source/orchestration/persistence/snapshot_manager.py
import logging
from datetime import datetime
from typing import Dict, List, Optional

from source.orchestration.coordination.exchange_manager import ExchangeGroupManager

from source.orchestration.persistence.snapshot_loader import LastSnapLoader

from source.orchestration.persistence.managers.manager_initializer import ManagerInitializer
from source.orchestration.persistence.managers.book_context_manager import BookContextManager
from source.orchestration.persistence.managers.shared_data_manager import SharedDataManager
from source.orchestration.persistence.managers.snapshot_validator import SnapshotValidator


class SnapshotManager:
    """Unified snapshot management for multi-book scenarios"""

    def __init__(self, exch_id: str = ""):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exch_id = exch_id

        # Build paths
        # self.data_dir = os.path.join(self._get_project_root(), "data")
        # self.metadata_file = os.path.join(self.data_dir, f"exchange_group_metadata.json")

        self.logger.info(f"📁 SnapshotManager initialized")
        self.logger.info(f"   Group ID: {exch_id}")

        # Initialize components
        self.exchange_group_manager = None
        self.last_snap_loader = LastSnapLoader(exch_id)

        # Initialize specialized modules (will be set up when exchange_group_manager is available)
        self.manager_initializer = ManagerInitializer()
        self.book_context_manager = None
        self.shared_data_manager = None
        self.snapshot_validator = SnapshotValidator()

    async def initialize_multi_book_from_snapshot(self) -> bool:
        """Initialize multi-book exchange from last snapshot - NOW ASYNC"""
        try:
            self.logger.info("=" * 80)
            self.logger.info("=== MULTI-book SNAPSHOT INITIALIZATION ===")
            self.logger.info("=" * 80)

            # Step 1: Initialize exchange group manager
            self.exchange_group_manager = ExchangeGroupManager(self.exch_id)

            if not await self.exchange_group_manager.initialize():
                self.logger.error("❌ Failed to initialize exchange group manager")
                return False

            # Step 2: Initialize specialized modules now that we have exchange_group_manager
            self.book_context_manager = BookContextManager(self.exchange_group_manager)
            self.shared_data_manager = SharedDataManager(self.book_context_manager)

            # Step 3: Load snapshot data - NOW ASYNC
            snapshot_date = self.exchange_group_manager.last_snap_time
            last_snap_data = await self.last_snap_loader.load_all_last_snap_data(
                snapshot_date, self.exchange_group_manager
            )

            # Step 4: Initialize shared data across all books
            if not self.shared_data_manager.initialize_shared_data(last_snap_data['global_data']):
                return False

            # Step 5: Initialize each book's managers
            if not self._initialize_all_books(last_snap_data):
                return False

            # Step 6: Validate initialization
            if not self.snapshot_validator.validate_initialization_completeness(self.exchange_group_manager):
                return False

            self.logger.info("=== MULTI-book SNAPSHOT INITIALIZATION COMPLETE ===")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error during multi-book snapshot initialization: {e}")
            return False

    def _initialize_all_books(self, last_snap_data: Dict) -> bool:
        """Initialize all books with their specific data"""
        try:
            self.logger.info("👥 INITIALIZING ALL bookS")
            self.logger.info("=" * 60)

            books = self.exchange_group_manager.get_all_books()
            global_data = last_snap_data['global_data']

            for book_id in books:
                self.logger.info(f"🔄 Initializing book {book_id}")

                book_data = last_snap_data['book_data'].get(book_id, {})
                if not book_data:
                    self.logger.warning(f"⚠️ No data found for book {book_id}, using empty data")
                    book_data = {
                        'portfolio': {},
                        'accounts': {},
                        'impact': {},
                        'orders': {},
                        'returns': {}
                    }

                success = self.book_context_manager.initialize_book_managers(
                    book_id, book_data, global_data, self.manager_initializer
                )

                if not success:
                    self.logger.error(f"❌ Failed to initialize book {book_id}")
                    return False

                self.logger.info(f"✅ book {book_id} initialized successfully")

            self.logger.info("✅ All books initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing books: {e}")
            return False

    def get_exchange_group_manager(self) -> Optional[ExchangeGroupManager]:
        """Get the exchange group manager"""
        return self.exchange_group_manager

    def get_initialization_summary(self) -> Dict:
        """Get a summary of the initialization status"""
        return self.snapshot_validator.get_initialization_summary(self.exchange_group_manager)

    def _initialize_universe(self, universe_data: Dict) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_universe(universe_data)

    def _initialize_fx(self, fx_data: List, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_fx(fx_data, date)

    def _initialize_portfolio(self, portfolio_data: Dict, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_portfolio(portfolio_data, date)

    def _initialize_accounts(self, accounts_data: Dict, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_accounts(accounts_data, date)

    def _initialize_equity(self, equity_data: List, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_equity(equity_data, date)

    def _initialize_impact(self, impact_data: Dict, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_impact(impact_data, date)

    def _initialize_orders(self, orders_data: Dict, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_orders(orders_data, date)

    def _initialize_returns(self, returns_data: Dict, date: datetime) -> bool:
        """Backward compatibility method"""
        return self.manager_initializer.initialize_returns(returns_data, date)

