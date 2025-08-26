# db/managers/reconciliation_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class ReconciliationManager(BaseManager):
    """Manages reconciliation database operations"""
    
    async def initialize_tables(self):
        """Create reconciliation tables"""
        await self.create_schema_if_not_exists('reconciliation')
        
        # Position reconciliation
        await self.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation.position_recon (
                recon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                recon_date DATE NOT NULL,
                account_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                source_system VARCHAR(50) NOT NULL,
                target_system VARCHAR(50) NOT NULL,
                source_quantity DECIMAL(20,8),
                target_quantity DECIMAL(20,8),
                quantity_difference DECIMAL(20,8),
                source_market_value DECIMAL(20,2),
                target_market_value DECIMAL(20,2),
                value_difference DECIMAL(20,2),
                reconciliation_status VARCHAR(20) NOT NULL,
                tolerance_breached BOOLEAN DEFAULT FALSE,
                comments TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Cash reconciliation
        await self.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation.cash_recon (
                recon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                recon_date DATE NOT NULL,
                account_id VARCHAR(50) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                balance_type VARCHAR(50) NOT NULL,
                source_balance DECIMAL(20,2),
                target_balance DECIMAL(20,2),
                balance_difference DECIMAL(20,2),
                reconciliation_status VARCHAR(20) NOT NULL,
                tolerance_breached BOOLEAN DEFAULT FALSE,
                comments TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Reconciliation breaks
        await self.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation.recon_breaks (
                break_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                recon_date DATE NOT NULL,
                account_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20),
                break_type VARCHAR(50) NOT NULL,
                break_description TEXT NOT NULL,
                impact_amount DECIMAL(20,2),
                resolution_status VARCHAR(20) DEFAULT 'OPEN',
                assigned_to VARCHAR(100),
                resolution_notes TEXT,
                resolved_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
    
    async def store_position_reconciliation_results(self, recon_results: List[Dict[str, Any]],
                                                   recon_date: date) -> int:
        """Store position reconciliation results"""
        if not recon_results:
            return 0
        
        # Clear existing results for this date
        await self.execute("""
            DELETE FROM reconciliation.position_recon WHERE recon_date = $1
        """, recon_date)
        
        # Insert new results
        queries = []
        for result in recon_results:
            query = """
                INSERT INTO reconciliation.position_recon
                (recon_date, account_id, symbol, source_system, target_system,
                 source_quantity, target_quantity, quantity_difference,
                 source_market_value, target_market_value, value_difference,
                 reconciliation_status, tolerance_breached, comments)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """
            
            params = (
                recon_date, result['account_id'], result['symbol'],
                result['source_system'], result['target_system'],
                float(result['source_quantity']), float(result['target_quantity']),
                float(result['quantity_difference']), float(result['source_market_value']),
                float(result['target_market_value']), float(result['value_difference']),
                result['reconciliation_status'], result['tolerance_breached'],
                result.get('comments')
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_reconciliation_breaks(self, recon_date: date = None,
                                      status: str = 'OPEN') -> List[Dict[str, Any]]:
        """Get reconciliation breaks"""
        filters = {}
        if recon_date:
            filters['recon_date'] = recon_date
        if status:
            filters['resolution_status'] = status
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT * FROM reconciliation.recon_breaks
            WHERE {where_clause}
            ORDER BY impact_amount DESC NULLS LAST, created_at DESC
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['impact_amount']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]