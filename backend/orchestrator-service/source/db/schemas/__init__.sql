# db/schemas/__init__.py
import os
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class SchemaManager:
    """Manages database schema files and deployment"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.schema_dir = Path(__file__).parent
    
    async def create_all_schemas(self):
        """Create all schemas from SQL files"""
        logger.info("🏗️ Creating all database schemas...")
        
        # Execute master schema creation script
        master_script = self.schema_dir / "create_all_schemas.sql"
        
        if master_script.exists():
            await self._execute_sql_file(master_script)
            logger.info("✅ All schemas created successfully")
        else:
            # Fall back to individual schema creation
            await self._create_schemas_individually()
    
    async def _create_schemas_individually(self):
        """Create schemas by executing individual SQL files in dependency order"""
        schema_order = [
            "core/positions.sql",
            "core/trades.sql", 
            "core/pnl.sql",
            "core/workflows.sql",
            "risk/risk_model.sql",
            "risk/risk_metrics.sql", 
            "risk/attribution.sql",
            "reference/securities.sql",
            "reference/exchanges.sql",
            "reference/corporate_actions.sql",
            "reference/universe.sql",
            "reconciliation/position_recon.sql",
            "reconciliation/cash_recon.sql",
            "reconciliation/breaks.sql",
            "reporting/reports.sql",
            "reporting/archival.sql",
            "operations/exchanges.sql",
            "operations/system.sql",
            "views/portfolio_views.sql",
            "views/risk_views.sql",
            "views/reporting_views.sql"
        ]
        
        for schema_file in schema_order:
            file_path = self.schema_dir / schema_file
            if file_path.exists():
                logger.info(f"📄 Executing {schema_file}")
                await self._execute_sql_file(file_path)
            else:
                logger.warning(f"⚠️ Schema file not found: {schema_file}")
    
    async def _execute_sql_file(self, file_path: Path):
        """Execute a SQL file"""
        try:
            with open(file_path, 'r') as f:
                sql_content = f.read()
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            async with self.db_manager.pool.acquire() as conn:
                for statement in statements:
                    if statement and not statement.startswith('--'):
                        await conn.execute(statement)
                        
        except Exception as e:
            logger.error(f"❌ Failed to execute {file_path}: {e}")
            raise
    
    async def get_schema_info(self) -> Dict[str, Any]:
        """Get information about database schemas"""
        async with self.db_manager.pool.acquire() as conn:
            # Get all schemas
            schemas = await conn.fetch("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                ORDER BY schema_name
            """)
            
            # Get table counts per schema
            schema_info = {}
            for schema in schemas:
                schema_name = schema['schema_name']
                
                tables = await conn.fetch("""
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = $1
                    ORDER BY table_name
                """, schema_name)
                
                schema_info[schema_name] = {
                    'table_count': len(tables),
                    'tables': [{'name': t['table_name'], 'type': t['table_type']} 
                              for t in tables]
                }
            
            return {
                'total_schemas': len(schemas),
                'schemas': schema_info
            }
    
    async def validate_schema_integrity(self) -> Dict[str, Any]:
        """Validate schema integrity and relationships"""
        async with self.db_manager.pool.acquire() as conn:
            # Check for missing foreign key references
            broken_fks = await conn.fetch("""
                SELECT 
                    tc.constraint_name,
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_schema AS foreign_table_schema,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND NOT EXISTS (
                      SELECT 1 FROM information_schema.tables t
                      WHERE t.table_schema = ccu.table_schema
                        AND t.table_name = ccu.table_name
                  )
            """)
            
            # Check for tables without primary keys
            tables_without_pks = await conn.fetch("""
                SELECT table_schema, table_name
                FROM information_schema.tables t
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('information_schema', 'pg_catalog')
                  AND NOT EXISTS (
                      SELECT 1 FROM information_schema.table_constraints tc
                      WHERE tc.table_schema = t.table_schema
                        AND tc.table_name = t.table_name
                        AND tc.constraint_type = 'PRIMARY KEY'
                  )
                ORDER BY table_schema, table_name
            """)
            
            return {
                'broken_foreign_keys': [dict(row) for row in broken_fks],
                'tables_without_primary_keys': [dict(row) for row in tables_without_pks],
                'integrity_status': 'GOOD' if not broken_fks and not tables_without_pks else 'ISSUES_FOUND'
            }