# db/managers/reference_data_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class ReferenceDataManager(BaseManager):
    """Manages all reference data database operations"""
    
    async def upsert_security(self, symbol: str, company_name: str = None,
                            sector: str = None, industry: str = None,
                            exchange: str = None, market_cap: Decimal = None,
                            **kwargs) -> str:
        """Insert or update security"""
        query = """
            INSERT INTO reference_data.securities
            (symbol, company_name, sector, industry, exchange, market_cap, 
             country, currency, shares_outstanding, listing_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (symbol)
            DO UPDATE SET
                company_name = COALESCE(EXCLUDED.company_name, securities.company_name),
                sector = COALESCE(EXCLUDED.sector, securities.sector),
                industry = COALESCE(EXCLUDED.industry, securities.industry),
                exchange = COALESCE(EXCLUDED.exchange, securities.exchange),
                market_cap = COALESCE(EXCLUDED.market_cap, securities.market_cap),
                country = COALESCE(EXCLUDED.country, securities.country),
                currency = COALESCE(EXCLUDED.currency, securities.currency),
                shares_outstanding = COALESCE(EXCLUDED.shares_outstanding, securities.shares_outstanding),
                listing_date = COALESCE(EXCLUDED.listing_date, securities.listing_date),
                updated_at = NOW()
            RETURNING security_id
        """
        
        result = await self.execute_returning(
            query, symbol, company_name, sector, industry, exchange,
            float(market_cap) if market_cap else None,
            kwargs.get('country', 'USA'), kwargs.get('currency', 'USD'),
            int(kwargs.get('shares_outstanding', 0)) if kwargs.get('shares_outstanding') else None,
            kwargs.get('listing_date')
        )
        
        return str(result['security_id']) if result else None
    
    async def get_security_by_symbol(self, symbol: str, exchange: str = None) -> Optional[Dict[str, Any]]:
        """Get security by symbol"""
        filters = {'symbol': symbol}
        if exchange:
            filters['exchange'] = exchange
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT * FROM reference_data.securities
            WHERE {where_clause} AND is_active = TRUE
        """
        
        result = await self.fetch_one(query, *params)
        if result:
            decimal_fields = ['market_cap']
            result = self.convert_decimal_fields(result, decimal_fields)
        
        return result
    
    async def get_securities_by_sector(self, sector: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get securities by sector"""
        query = """
            SELECT * FROM reference_data.securities
            WHERE sector = $1 AND is_active = TRUE
            ORDER BY market_cap DESC NULLS LAST
            LIMIT $2
        """
        
        rows = await self.fetch_all(query, sector, limit)
        decimal_fields = ['market_cap']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def get_market_statistics(self) -> Dict[str, Any]:
        """Get market statistics"""
        query = """
            SELECT 
                COUNT(*) as total_securities,
                COUNT(CASE WHEN is_active THEN 1 END) as active_securities,
                COUNT(DISTINCT sector) as unique_sectors,
                COUNT(DISTINCT exchange) as unique_exchanges,
                SUM(market_cap) as total_market_cap,
                AVG(market_cap) as avg_market_cap
            FROM reference_data.securities
            WHERE market_cap IS NOT NULL
        """
        
        result = await self.fetch_one(query)
        
        if result:
            decimal_fields = ['total_market_cap', 'avg_market_cap']
            result = self.convert_decimal_fields(result, decimal_fields)
        
        return result or {}
    
    async def bulk_upsert_securities(self, securities_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert securities"""
        if not securities_data:
            return 0
        
        queries = []
        for security in securities_data:
            query = """
                INSERT INTO reference_data.securities
                (symbol, company_name, sector, industry, exchange, market_cap, 
                 country, currency)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol)
                DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    sector = EXCLUDED.sector,
                    industry = EXCLUDED.industry,
                    exchange = EXCLUDED.exchange,
                    market_cap = EXCLUDED.market_cap,
                    updated_at = NOW()
            """
            
            params = (
                security['symbol'], security.get('company_name'),
                security.get('sector'), security.get('industry'),
                security.get('exchange'), 
                float(security['market_cap']) if security.get('market_cap') else None,
                security.get('country', 'USA'), security.get('currency', 'USD')
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def create_corporate_action(self, symbol: str, action_type: str, 
                                    ex_date: date, amount: Decimal = None,
                                    ratio: Decimal = None, description: str = None,
                                    record_date: date = None, pay_date: date = None) -> str:
        """Create corporate action"""
        query = """
            INSERT INTO reference_data.corporate_actions
            (symbol, action_type, ex_date, record_date, pay_date, amount, ratio, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING action_id
        """
        
        result = await self.execute_returning(
            query, symbol, action_type, ex_date, record_date, pay_date,
            float(amount) if amount else None, float(ratio) if ratio else None, description
        )
        
        return str(result['action_id']) if result else None
    
    async def get_corporate_actions(self, symbol: str = None, action_type: str = None,
                                  ex_date: date = None, status: str = None) -> List[Dict[str, Any]]:
        """Get corporate actions with filters"""
        filters = {}
        if symbol:
            filters['symbol'] = symbol
        if action_type:
            filters['action_type'] = action_type
        if ex_date:
            filters['ex_date'] = ex_date
        if status:
            filters['status'] = status
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT * FROM reference_data.corporate_actions
            WHERE {where_clause}
            ORDER BY ex_date DESC, symbol
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['amount', 'ratio']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]