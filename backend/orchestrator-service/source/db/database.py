# db/database.py (Add state manager import and initialization)
from typing import Optional
from source.db.base_managers.state_manager import StateManager

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
        # Initialize all managers including state manager
        self.workflows: Optional[WorkflowManager] = None
        self.state: Optional[StateManager] = None 

        self.reporting: Optional[ReportingManager] = None

        self.positions: Optional[PositionManager] = None
        self.reference_data: Optional[ReferenceDataManager] = None
        self.universe: Optional[UniverseManager] = None
        self.corporate_actions: Optional[CorporateActionsManager] = None
        self.reconciliation: Optional[ReconciliationManager] = None
    
    async def _initialize_managers(self):
        """Initialize all data managers"""
        logger.info("📋 Initializing data managers...")
        
        self.workflows = WorkflowManager(self)
        self.state = StateManager(self)

        self.reporting = ReportingManager(self)

        self.positions = PositionManager(self)
        self.reference_data = ReferenceDataManager(self)
        self.universe = UniverseManager(self)
        self.corporate_actions = CorporateActionsManager(self)
        self.reconciliation = ReconciliationManager(self)
        
        logger.info("✅ All data managers initialized")
    
    async def _initialize_tables(self):
        """Initialize all database tables"""
        logger.info("🏗️ Creating database tables...")
        
        managers_to_init = [
            ("Workflows", self.workflows),
            ("State Management", self.state),

            ("Reporting", self.reporting),

            ("Positions", self.positions),
            ("Reference Data", self.reference_data),
            ("Universe", self.universe),
            ("Corporate Actions", self.corporate_actions),
            ("Reconciliation", self.reconciliation),
        ]
        
        for name, manager in managers_to_init:
            try:
                logger.info(f"🔨 Initializing {name} tables...")
                await manager.initialize_tables()
                logger.info(f"✅ {name} tables created")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {name} tables: {e}")
                raise
        
        logger.info("🎉 All database tables created successfully")