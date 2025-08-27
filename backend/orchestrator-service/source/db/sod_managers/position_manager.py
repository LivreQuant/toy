# db/managers/position_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class PositionManager(BaseManager):
    """Manages all position-related database operations"""
    
    async def get_current_positions(self, account_id: str = None, 
                                  position_date: date = None,
                                  symbol: str = None) -> List[Dict[str, Any]]:
        """Get current positions with optional filters"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        if position_date:
            filters['position_date'] = position_date
        if symbol:
            filters['symbol'] = symbol
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT 
                position_id, account_id, symbol, quantity, avg_cost, 
                market_value, unrealized_pnl, last_price, position_date,
                created_at, updated_at
            FROM positions.current_positions
            WHERE {where_clause}
            ORDER BY account_id, symbol
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['quantity', 'avg_cost', 'market_value', 'unrealized_pnl', 'last_price']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def upsert_position(self, account_id: str, symbol: str, quantity: Decimal,
                            avg_cost: Decimal, position_date: date,
                            market_value: Decimal = None, last_price: Decimal = None) -> str:
        """Insert or update position"""
        market_value = market_value or (quantity * avg_cost)
        unrealized_pnl = market_value - (quantity * avg_cost) if last_price else Decimal('0')
        
        query = """
            INSERT INTO positions.current_positions
            (account_id, symbol, quantity, avg_cost, market_value, unrealized_pnl, 
             last_price, position_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (account_id, symbol, position_date)
            DO UPDATE SET
                quantity = EXCLUDED.quantity,
                avg_cost = EXCLUDED.avg_cost,
                market_value = EXCLUDED.market_value,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                last_price = EXCLUDED.last_price,
                updated_at = NOW()
            RETURNING position_id
        """
        
        result = await self.execute_returning(
            query, account_id, symbol, float(quantity), float(avg_cost),
            float(market_value), float(unrealized_pnl), 
            float(last_price) if last_price else None, position_date
        )
        
        return str(result['position_id']) if result else None
    
    async def update_market_values(self, position_date: date, 
                                 price_updates: List[Dict[str, Any]]) -> int:
        """Bulk update market values from price data"""
        if not price_updates:
            return 0
        
        # Build update queries
        queries = []
        for update in price_updates:
            symbol = update['symbol']
            price = Decimal(str(update['price']))
            
            query = """
                UPDATE positions.current_positions
                SET last_price = $1,
                    market_value = quantity * $1,
                    unrealized_pnl = (quantity * $1) - (quantity * avg_cost),
                    updated_at = NOW()
                WHERE symbol = $2 AND position_date = $3 AND quantity != 0
            """
            queries.append((query, (float(price), symbol, position_date)))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def create_position_snapshot(self, position_date: date) -> int:
        """Create position snapshot for EOD"""
        query = """
            INSERT INTO positions.position_history
            (account_id, symbol, quantity, avg_cost, market_value, unrealized_pnl, 
             last_price, position_date, snapshot_time)
            SELECT 
                account_id, symbol, quantity, avg_cost, market_value, unrealized_pnl,
                last_price, position_date, NOW()
            FROM positions.current_positions
            WHERE position_date = $1 AND quantity != 0
            ON CONFLICT (account_id, symbol, position_date) 
            DO UPDATE SET
                quantity = EXCLUDED.quantity,
                avg_cost = EXCLUDED.avg_cost,
                market_value = EXCLUDED.market_value,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                last_price = EXCLUDED.last_price,
                snapshot_time = NOW()
        """
        
        result = await self.execute(query, position_date)
        return int(result.split()[-1]) if result and 'INSERT' in result else 0
    
    async def get_position_history(self, account_id: str = None, symbol: str = None,
                                 start_date: date = None, end_date: date = None) -> List[Dict[str, Any]]:
        """Get position history with filters"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        if symbol:
            filters['symbol'] = symbol
        
        where_clause, params = self.build_where_clause(filters)
        
        if start_date:
            where_clause += f" AND position_date >= ${len(params) + 1}"
            params.append(start_date)
        
        if end_date:
            where_clause += f" AND position_date <= ${len(params) + 1}"
            params.append(end_date)
        
        query = f"""
            SELECT * FROM positions.position_history
            WHERE {where_clause}
            ORDER BY position_date DESC, account_id, symbol
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['quantity', 'avg_cost', 'market_value', 'unrealized_pnl', 'last_price']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def get_eod_prices(self, symbols: List[str] = None, 
                           price_date: date = None,
                           pricing_source: str = None) -> List[Dict[str, Any]]:
        """Get EOD prices"""
        query = """
            SELECT symbol, price, price_date, pricing_source, currency, created_at
            FROM positions.eod_prices
            WHERE 1=1
        """
        
        params = []
        if symbols:
            placeholders = ','.join(f'${i}' for i in range(len(params) + 1, len(params) + len(symbols) + 1))
            query += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        
        if price_date:
            query += f" AND price_date = ${len(params) + 1}"
            params.append(price_date)
        
        if pricing_source:
            query += f" AND pricing_source = ${len(params) + 1}"
            params.append(pricing_source)
        
        query += " ORDER BY symbol, price_date DESC"
        
        rows = await self.fetch_all(query, *params)
        return [self.convert_decimal_fields(row, ['price']) for row in rows]
    
    async def upsert_eod_price(self, symbol: str, price: Decimal, 
                             price_date: date, pricing_source: str = 'MARKET',
                             currency: str = 'USD') -> bool:
        """Insert or update EOD price"""
        query = """
            INSERT INTO positions.eod_prices (symbol, price, price_date, pricing_source, currency)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (symbol, price_date, pricing_source)
            DO UPDATE SET 
                price = EXCLUDED.price, 
                currency = EXCLUDED.currency,
                updated_at = NOW()
        """
        
        await self.execute(query, symbol, float(price), price_date, pricing_source, currency)
        return True
    
    async def bulk_upsert_eod_prices(self, price_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert EOD prices"""
        if not price_data:
            return 0
        
        # Use execute_transaction for bulk operations
        queries = []
        for price_info in price_data:
            query = """
                INSERT INTO positions.eod_prices (symbol, price, price_date, pricing_source, currency)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (symbol, price_date, pricing_source)
                DO UPDATE SET price = EXCLUDED.price, updated_at = NOW()
            """
            
            params = (
                price_info['symbol'],
                float(price_info['price']),
                price_info['price_date'],
                price_info.get('pricing_source', 'MARKET'),
                price_info.get('currency', 'USD')
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_position_summary(self, position_date: date, 
                                 account_id: str = None) -> Dict[str, Any]:
        """Get position summary statistics"""
        filters = {'position_date': position_date}
        if account_id:
            filters['account_id'] = account_id
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT 
                COUNT(*) as total_positions,
                COUNT(CASE WHEN quantity > 0 THEN 1 END) as long_positions,
                COUNT(CASE WHEN quantity < 0 THEN 1 END) as short_positions,
                SUM(market_value) as total_market_value,
                SUM(unrealized_pnl) as total_unrealized_pnl,
                AVG(market_value) as avg_position_size,
                COUNT(DISTINCT account_id) as unique_accounts
            FROM positions.current_positions
            WHERE {where_clause} AND quantity != 0
        """
        
        result = await self.fetch_one(query, *params)
        
        if result:
            decimal_fields = ['total_market_value', 'total_unrealized_pnl', 'avg_position_size']
            result = self.convert_decimal_fields(result, decimal_fields)
        
        return result or {}