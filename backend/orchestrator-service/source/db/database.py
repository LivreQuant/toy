# db/database.py (Add state manager import and initialization)
from .managers.state_manager import StateManager

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
        # Initialize all managers including state manager
        self.positions: Optional[PositionManager] = None
        self.trades: Optional[TradeManager] = None
        self.pnl: Optional[PnLManager] = None
        self.risk: Optional[RiskManager] = None
        self.reference_data: Optional[ReferenceDataManager] = None
        self.universe: Optional[UniverseManager] = None
        self.corporate_actions: Optional[CorporateActionsManager] = None
        self.reconciliation: Optional[ReconciliationManager] = None
        self.reporting: Optional[ReportingManager] = None
        self.archival: Optional[ArchivalManager] = None
        self.workflows: Optional[WorkflowManager] = None
        self.state: Optional[StateManager] = None  # Add state manager
    
    async def _initialize_managers(self):
        """Initialize all data managers"""
        logger.info("📋 Initializing data managers...")
        
        self.positions = PositionManager(self)
        self.trades = TradeManager(self)
        self.pnl = PnLManager(self)
        self.risk = RiskManager(self)
        self.reference_data = ReferenceDataManager(self)
        self.universe = UniverseManager(self)
        self.corporate_actions = CorporateActionsManager(self)
        self.reconciliation = ReconciliationManager(self)
        self.reporting = ReportingManager(self)
        self.archival = ArchivalManager(self)
        self.workflows = WorkflowManager(self)
        self.state = StateManager(self)  # Add state manager
        
        logger.info("✅ All data managers initialized")
    
    async def _initialize_tables(self):
        """Initialize all database tables"""
        logger.info("🏗️ Creating database tables...")
        
        managers_to_init = [
            ("Positions", self.positions),
            ("Trades", self.trades), 
            ("P&L", self.pnl),
            ("Risk", self.risk),
            ("Reference Data", self.reference_data),
            ("Universe", self.universe),
            ("Corporate Actions", self.corporate_actions),
            ("Reconciliation", self.reconciliation),
            ("Reporting", self.reporting),
            ("Archival", self.archival),
            ("Workflows", self.workflows),
            ("State Management", self.state)  # Add state manager
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