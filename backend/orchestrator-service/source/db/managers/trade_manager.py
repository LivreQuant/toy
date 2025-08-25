# db/managers/trade_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class TradeManager(BaseManager):
    """Manages all trade and settlement database operations"""
    
    async def initialize_tables(self):
        """Create trade and settlement tables"""
        await self.create_schema_if_not_exists('settlement')
        
        # Trades table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS settlement.trades (
                trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
                quantity DECIMAL(20,8) NOT NULL,
                price DECIMAL(20,8) NOT NULL,
                trade_value DECIMAL(20,2) NOT NULL,
                commission DECIMAL(20,2) NOT NULL DEFAULT 0,
                fees DECIMAL(20,2) NOT NULL DEFAULT 0,
                net_amount DECIMAL(20,2) NOT NULL,
                trade_date DATE NOT NULL,
                settlement_date DATE,
                settlement_status VARCHAR(20) DEFAULT 'PENDING' 
                    CHECK (settlement_status IN ('PENDING', 'MATCHED', 'SETTLED', 'FAILED')),
                execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Settlement instructions table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS settlement.settlement_instructions (
                instruction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                trade_id UUID REFERENCES settlement.trades(trade_id),
                instruction_type VARCHAR(50) NOT NULL,
                counterparty VARCHAR(100),
                settlement_account VARCHAR(100),
                delivery_instructions TEXT,
                status VARCHAR(20) DEFAULT 'PENDING',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Create indexes
        await self.execute("CREATE INDEX IF NOT EXISTS idx_trades_account_date ON settlement.trades(account_id, trade_date)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_trades_settlement ON settlement.trades(settlement_date, settlement_status)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON settlement.trades(symbol, trade_date)")
    
    async def create_trade(self, account_id: str, symbol: str, side: str,
                         quantity: Decimal, price: Decimal, trade_date: date,
                         commission: Decimal = None, fees: Decimal = None,
                         execution_time: datetime = None) -> str:
        """Create new trade record"""
        trade_value = abs(quantity * price)
        commission = commission or Decimal('5.00')
        fees = fees or Decimal('1.00')
        
        if side.upper() == 'BUY':
            net_amount = -(trade_value + commission + fees)
        else:  # SELL
            net_amount = trade_value - commission - fees
        
        query = """
            INSERT INTO settlement.trades
            (account_id, symbol, side, quantity, price, trade_value, 
             commission, fees, net_amount, trade_date, execution_time, settlement_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'PENDING')
            RETURNING trade_id
        """
        
        result = await self.execute_returning(
            query, account_id, symbol, side.upper(), float(quantity), float(price), 
            float(trade_value), float(commission), float(fees), float(net_amount), 
            trade_date, execution_time or datetime.utcnow()
        )
        
        return str(result['trade_id']) if result else None
    
    async def get_trades(self, account_id: str = None, trade_date: date = None,
                        settlement_status: str = None, symbol: str = None,
                        start_date: date = None, end_date: date = None) -> List[Dict[str, Any]]:
        """Get trades with optional filters"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        if trade_date:
            filters['trade_date'] = trade_date
        if settlement_status:
            filters['settlement_status'] = settlement_status
        if symbol:
            filters['symbol'] = symbol
        
        where_clause, params = self.build_where_clause(filters)
        
        if start_date:
            where_clause += f" AND trade_date >= ${len(params) + 1}"
            params.append(start_date)
        
        if end_date:
            where_clause += f" AND trade_date <= ${len(params) + 1}"
            params.append(end_date)
        
        query = f"""
            SELECT 
                trade_id, account_id, symbol, side, quantity, price,
                trade_value, commission, fees, net_amount, trade_date,
                settlement_date, settlement_status, execution_time, created_at
            FROM settlement.trades
            WHERE {where_clause}
            ORDER BY execution_time DESC
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['quantity', 'price', 'trade_value', 'commission', 'fees', 'net_amount']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def update_settlement_status(self, trade_id: str, status: str,
                                     settlement_date: date = None) -> bool:
        """Update trade settlement status"""
        if settlement_date:
            query = """
                UPDATE settlement.trades
                SET settlement_status = $2, settlement_date = $3, updated_at = NOW()
                WHERE trade_id = $1
            """
            await self.execute(query, trade_id, status, settlement_date)
        else:
            query = """
                UPDATE settlement.trades
                SET settlement_status = $2, updated_at = NOW()
                WHERE trade_id = $1
            """
            await self.execute(query, trade_id, status)
        
        return True
    
    async def bulk_update_settlement_status(self, trade_updates: List[Dict[str, Any]]) -> int:
        """Bulk update settlement statuses"""
        if not trade_updates:
            return 0
        
        queries = []
        for update in trade_updates:
            if 'settlement_date' in update:
                query = """
                    UPDATE settlement.trades
                    SET settlement_status = $2, settlement_date = $3, updated_at = NOW()
                    WHERE trade_id = $1
                """
                params = (update['trade_id'], update['status'], update['settlement_date'])
            else:
                query = """
                    UPDATE settlement.trades
                    SET settlement_status = $2, updated_at = NOW()
                    WHERE trade_id = $1
                """
                params = (update['trade_id'], update['status'])
            
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_settlement_summary(self, settlement_date: date) -> Dict[str, Any]:
        """Get settlement summary for a date"""
        # By status summary
        status_query = """
            SELECT 
                settlement_status,
                COUNT(*) as trade_count,
                SUM(ABS(trade_value)) as total_value,
                SUM(commission + fees) as total_costs
            FROM settlement.trades
            WHERE settlement_date = $1
            GROUP BY settlement_status
        """
        
        status_rows = await self.fetch_all(status_query, settlement_date)
        
        # Overall summary
        overall_query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(ABS(trade_value)) as total_value,
                SUM(commission + fees) as total_costs,
                COUNT(CASE WHEN settlement_status = 'SETTLED' THEN 1 END) as settled_trades,
                COUNT(CASE WHEN settlement_status = 'FAILED' THEN 1 END) as failed_trades,
                COUNT(CASE WHEN settlement_status = 'PENDING' THEN 1 END) as pending_trades,
                COUNT(DISTINCT account_id) as unique_accounts,
                COUNT(DISTINCT symbol) as unique_symbols
            FROM settlement.trades
            WHERE settlement_date = $1
        """
        
        overall = await self.fetch_one(overall_query, settlement_date)
        
        # Convert decimal fields
        if overall:
            decimal_fields = ['total_value', 'total_costs']
            overall = self.convert_decimal_fields(overall, decimal_fields)
        
        for row in status_rows:
            decimal_fields = ['total_value', 'total_costs']
            row = self.convert_decimal_fields(row, decimal_fields)
        
        return {
            "settlement_date": str(settlement_date),
            "by_status": status_rows,
            "overall": overall or {}
        }
    
    async def get_trades_for_settlement(self, settlement_date: date) -> List[Dict[str, Any]]:
        """Get trades that need settlement on a specific date"""
        query = """
            SELECT * FROM settlement.trades
            WHERE trade_date <= $1 
              AND settlement_status IN ('PENDING', 'MATCHED')
              AND (settlement_date IS NULL OR settlement_date = $1)
            ORDER BY trade_date, execution_time
        """
        
        rows = await self.fetch_all(query, settlement_date)
        decimal_fields = ['quantity', 'price', 'trade_value', 'commission', 'fees', 'net_amount']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def create_sample_trades(self, trade_date: date, count: int = 100) -> Dict[str, Any]:
        """Create sample trades for testing"""
        import random
        random.seed(int(trade_date.strftime("%Y%m%d")))
        
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA']
        accounts = ['ACC001', 'ACC002', 'ACC003']
        
        trades_created = []
        
        for i in range(count):
            account_id = random.choice(accounts)
            symbol = random.choice(symbols)
            side = random.choice(['BUY', 'SELL'])
            quantity = Decimal(str(random.randint(100, 1000)))
            price = Decimal(str(round(random.uniform(50, 300), 2)))
            
            trade_id = await self.create_trade(
                account_id, symbol, side, quantity, price, trade_date
            )
            
            if trade_id:
                trades_created.append(trade_id)
        
        return {
            "trades_created": len(trades_created),
            "trade_date": str(trade_date),
            "sample_trade_ids": trades_created[:10]  # Return first 10 for reference
        }
    
    async def create_settlement_instruction(self, trade_id: str, instruction_type: str,
                                          counterparty: str = None, 
                                          settlement_account: str = None,
                                          delivery_instructions: str = None) -> str:
        """Create settlement instruction for a trade"""
        query = """
            INSERT INTO settlement.settlement_instructions
            (trade_id, instruction_type, counterparty, settlement_account,
                delivery_instructions, status)
            VALUES ($1, $2, $3, $4, $5, 'PENDING')
            RETURNING instruction_id
        """
        
        result = await self.execute_returning(
            query, trade_id, instruction_type, counterparty, 
            settlement_account, delivery_instructions
        )
        
        return str(result['instruction_id']) if result else None
    
    async def get_trade_statistics(self, start_date: date, end_date: date,
                                    account_id: str = None) -> Dict[str, Any]:
        """Get trade statistics for a period"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        
        where_clause, params = self.build_where_clause(filters)
        where_clause += f" AND trade_date BETWEEN ${len(params) + 1} AND ${len(params) + 2}"
        params.extend([start_date, end_date])
        
        query = f"""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN side = 'BUY' THEN 1 END) as buy_trades,
                COUNT(CASE WHEN side = 'SELL' THEN 1 END) as sell_trades,
                SUM(ABS(trade_value)) as total_volume,
                SUM(commission + fees) as total_costs,
                AVG(ABS(trade_value)) as avg_trade_size,
                COUNT(DISTINCT symbol) as unique_symbols,
                COUNT(DISTINCT account_id) as unique_accounts
            FROM settlement.trades
            WHERE {where_clause}
        """
        
        result = await self.fetch_one(query, *params)
        
        if result:
            decimal_fields = ['total_volume', 'total_costs', 'avg_trade_size']
            result = self.convert_decimal_fields(result, decimal_fields)
        
        return result or {}