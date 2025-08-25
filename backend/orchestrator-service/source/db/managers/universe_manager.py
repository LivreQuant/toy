# db/managers/universe_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class UniverseManager(BaseManager):
    """Manages trading universe database operations"""
    
    async def initialize_tables(self):
        """Create universe tables"""
        await self.create_schema_if_not_exists('universe')
        
        # Trading universe table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS universe.trading_universe (
                universe_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                symbol VARCHAR(20) NOT NULL,
                universe_date DATE NOT NULL,
                is_tradeable BOOLEAN DEFAULT TRUE,
                market_cap DECIMAL(20,2),
                sector VARCHAR(100),
                liquidity_score DECIMAL(5,2),
                inclusion_reason VARCHAR(200),
                exclusion_reason VARCHAR(200),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(symbol, universe_date)
            )
        """)
        
        # Universe rules table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS universe.universe_rules (
                rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                rule_name VARCHAR(100) NOT NULL UNIQUE,
                rule_type VARCHAR(50) NOT NULL,
                rule_criteria JSONB NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
    
    async def build_trading_universe(self, universe_date: date) -> Dict[str, Any]:
        """Build trading universe for a specific date"""
        # Get all active securities
        securities = await self.fetch_all("""
            SELECT symbol, market_cap, sector, is_active
            FROM reference_data.securities
            WHERE is_active = TRUE
        """)
        
        universe_records = []
        included_count = 0
        
        for security in securities:
            # Apply universe rules (simplified)
            is_tradeable = True
            inclusion_reason = "Meets basic criteria"
            exclusion_reason = None
            
            # Market cap filter
            if security['market_cap'] and Decimal(str(security['market_cap'])) < Decimal('1000000000'):  # $1B min
                is_tradeable = False
                exclusion_reason = "Market cap below minimum threshold"
            
            # Sector filter (exclude certain sectors)
            excluded_sectors = ['UTILITIES', 'REAL_ESTATE']
            if security['sector'] in excluded_sectors:
                is_tradeable = False
                exclusion_reason = f"Sector {security['sector']} excluded"
            
            if is_tradeable:
                included_count += 1
            
            universe_records.append({
                'symbol': security['symbol'],
                'universe_date': universe_date,
                'is_tradeable': is_tradeable,
                'market_cap': security['market_cap'],
                'sector': security['sector'],
                'liquidity_score': 85.0,  # Simplified
                'inclusion_reason': inclusion_reason if is_tradeable else None,
                'exclusion_reason': exclusion_reason
            })
        
        # Store universe
        await self.upsert_universe_records(universe_records)
        
        return {
            "universe_date": str(universe_date),
            "total_securities_evaluated": len(securities),
            "securities_included": included_count,
            "securities_excluded": len(securities) - included_count
        }
    
    async def upsert_universe_records(self, universe_records: List[Dict[str, Any]]) -> int:
        """Insert or update universe records"""
        if not universe_records:
            return 0
        
        queries = []
        for record in universe_records:
            query = """
                INSERT INTO universe.trading_universe
                (symbol, universe_date, is_tradeable, market_cap, sector, 
                 liquidity_score, inclusion_reason, exclusion_reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, universe_date)
                DO UPDATE SET
                    is_tradeable = EXCLUDED.is_tradeable,
                    market_cap = EXCLUDED.market_cap,
                    sector = EXCLUDED.sector,
                    liquidity_score = EXCLUDED.liquidity_score,
                    inclusion_reason = EXCLUDED.inclusion_reason,
                    exclusion_reason = EXCLUDED.exclusion_reason
            """
            
            params = (
                record['symbol'], record['universe_date'], record['is_tradeable'],
                float(record['market_cap']) if record['market_cap'] else None,
                record['sector'], float(record.get('liquidity_score', 0)),
                record.get('inclusion_reason'), record.get('exclusion_reason')
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_universe_for_date(self, universe_date: date, 
                                  tradeable_only: bool = True) -> List[Dict[str, Any]]:
        """Get trading universe for a specific date"""
        query = """
            SELECT * FROM universe.trading_universe
            WHERE universe_date = $1
        """
        params = [universe_date]
        
        if tradeable_only:
            query += " AND is_tradeable = TRUE"
        
        query += " ORDER BY market_cap DESC NULLS LAST"
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['market_cap', 'liquidity_score']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]