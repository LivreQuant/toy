# db/database.py (Updated with schema manager)
from .schemas import SchemaManager

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.schema_manager: Optional[SchemaManager] = None
        # ... other managers ...
    
    async def init(self):
        """Initialize database connection pool and managers"""
        logger.info("🔗 Initializing database connection pool...")
        
        # Create connection pool
        # Continuing db/database.py

        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'opentp'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        logger.info("✅ Database connection pool created")
        
        # Initialize schema manager first
        self.schema_manager = SchemaManager(self)
        
        # Initialize all data managers
        await self._initialize_managers()
        
        # Create schemas and tables using schema manager
        await self.schema_manager.create_all_schemas()
        
        logger.info("🗃️ Database manager fully initialized")
    
    async def get_schema_status(self) -> Dict[str, Any]:
        """Get comprehensive schema status"""
        if not self.schema_manager:
            return {"error": "Schema manager not initialized"}
        
        schema_info = await self.schema_manager.get_schema_info()
        integrity_check = await self.schema_manager.validate_schema_integrity()
        
        return {
            "schema_info": schema_info,
            "integrity_check": integrity_check,
            "timestamp": datetime.utcnow().isoformat()
        }