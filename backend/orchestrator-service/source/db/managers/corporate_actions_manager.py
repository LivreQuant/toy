# db/managers/corporate_actions_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class CorporateActionsManager(BaseManager):
    """Manages corporate actions database operations"""
    
    async def initialize_tables(self):
        """Create corporate actions tables"""
        await self.create_schema_if_not_exists('corporate_actions')
        
        # Corporate actions table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS corporate_actions.actions (
                action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                symbol VARCHAR(20) NOT NULL,
                action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('DIVIDEND', 'STOCK_SPLIT', 'STOCK_DIVIDEND', 'SPINOFF', 'MERGER', 'RIGHTS')),
                ex_date DATE NOT NULL,
                record_date DATE,
                pay_date DATE,
                amount DECIMAL(20,8),
                ratio DECIMAL(20,8),
                new_symbol VARCHAR(20),
                description TEXT,
                status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSED', 'CANCELLED')),
                source VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                processed_at TIMESTAMP WITH TIME ZONE
            )
        """)
        
        # Price adjustments history
        await self.execute("""
            CREATE TABLE IF NOT EXISTS corporate_actions.price_adjustment_history (
                adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                symbol VARCHAR(20) NOT NULL,
                adjustment_date DATE NOT NULL,
                adjustment_type VARCHAR(50) NOT NULL,
                old_price DECIMAL(20,8),
                new_price DECIMAL(20,8),
                adjustment_factor DECIMAL(20,8),
                dividend_amount DECIMAL(20,8) DEFAULT 0,
                split_ratio DECIMAL(20,8) DEFAULT 1,
                adjustment_reason TEXT,
                status VARCHAR(20) DEFAULT 'APPLIED',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Position adjustments audit
        await self.execute("""
            CREATE TABLE IF NOT EXISTS corporate_actions.position_adjustment_audit (
                audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                adjustment_date DATE NOT NULL,
                adjustment_type VARCHAR(50) NOT NULL,
                old_quantity DECIMAL(20,8),
                new_quantity DECIMAL(20,8),
                old_avg_cost DECIMAL(20,8),
                new_avg_cost DECIMAL(20,8),
                cash_impact DECIMAL(20,2) DEFAULT 0,
                corporate_action_id UUID REFERENCES corporate_actions.actions(action_id),
                status VARCHAR(20) DEFAULT 'APPLIED',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
    
    async def create_corporate_action(self, symbol: str, action_type: str, ex_date: date,
                                    amount: Decimal = None, ratio: Decimal = None,
                                    description: str = None, **kwargs) -> str:
        """Create a new corporate action"""
        query = """
            INSERT INTO corporate_actions.actions
            (symbol, action_type, ex_date, record_date, pay_date, amount, ratio, 
             new_symbol, description, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING action_id
        """
        
        result = await self.execute_returning(
            query, symbol, action_type, ex_date,
            kwargs.get('record_date'), kwargs.get('pay_date'),
            float(amount) if amount else None, float(ratio) if ratio else None,
            kwargs.get('new_symbol'), description, kwargs.get('source', 'MANUAL')
        )
        
        return str(result['action_id']) if result else None
    
    async def get_pending_actions(self, symbol: str = None, 
                                ex_date: date = None) -> List[Dict[str, Any]]:
        """Get pending corporate actions"""
        filters = {'status': 'PENDING'}
        if symbol:
            filters['symbol'] = symbol
        if ex_date:
            filters['ex_date'] = ex_date
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT * FROM corporate_actions.actions
            WHERE {where_clause}
            ORDER BY ex_date, symbol
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['amount', 'ratio']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def process_corporate_action(self, action_id: str) -> Dict[str, Any]:
        """Mark corporate action as processed"""
        query = """
            UPDATE corporate_actions.actions
            SET status = 'PROCESSED', processed_at = NOW()
            WHERE action_id = $1
            RETURNING *
        """
        
        result = await self.execute_returning(query, action_id)
        
        if result:
            decimal_fields = ['amount', 'ratio']
            return self.convert_decimal_fields(dict(result), decimal_fields)
        
        return {}