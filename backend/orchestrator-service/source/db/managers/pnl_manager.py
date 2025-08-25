# db/managers/pnl_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class PnLManager(BaseManager):
    """Manages all P&L related database operations"""
    
    async def initialize_tables(self):
        """Create P&L tables"""
        await self.create_schema_if_not_exists('pnl')
        
        # Daily P&L table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS pnl.daily_pnl (
                pnl_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20),
                pnl_date DATE NOT NULL,
                realized_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
                unrealized_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
                total_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
                market_value_start DECIMAL(20,2) NOT NULL DEFAULT 0,
                market_value_end DECIMAL(20,2) NOT NULL DEFAULT 0,
                quantity_start DECIMAL(20,8) NOT NULL DEFAULT 0,
                quantity_end DECIMAL(20,8) NOT NULL DEFAULT 0,
                trading_pnl DECIMAL(20,2) NOT NULL DEFAULT 0,
                dividends DECIMAL(20,2) NOT NULL DEFAULT 0,
                fees DECIMAL(20,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(account_id, symbol, pnl_date)
            )
        """)
        
        # Portfolio performance table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS pnl.portfolio_performance (
                performance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(50) NOT NULL,
                performance_date DATE NOT NULL,
                total_return_pct DECIMAL(12,6) NOT NULL,
                benchmark_return_pct DECIMAL(12,6),
                excess_return_pct DECIMAL(12,6),
                volatility_pct DECIMAL(12,6),
                sharpe_ratio DECIMAL(12,6),
                max_drawdown_pct DECIMAL(12,6),
                portfolio_value DECIMAL(20,2) NOT NULL,
                cash_balance DECIMAL(20,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(account_id, performance_date)
            )
        """)
        
        # Create indexes
        await self.execute("CREATE INDEX IF NOT EXISTS idx_daily_pnl_account_date ON pnl.daily_pnl(account_id, pnl_date)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON pnl.daily_pnl(pnl_date)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_perf_account ON pnl.portfolio_performance(account_id, performance_date)")
    
    async def calculate_daily_pnl(self, account_id: str, pnl_date: date) -> Dict[str, Any]:
        """Calculate and store daily P&L for an account"""
        # Get current positions
        positions_query = """
            SELECT symbol, quantity, avg_cost, market_value, unrealized_pnl
            FROM positions.current_positions
            WHERE account_id = $1 AND position_date = $2 AND quantity != 0
        """
        positions = await self.fetch_all(positions_query, account_id, pnl_date)
        
        # Get previous day positions for comparison
        prev_date_query = """
            SELECT position_date FROM positions.position_history
            WHERE account_id = $1 AND position_date < $2
            ORDER BY position_date DESC LIMIT 1
        """
        prev_date_result = await self.fetch_one(prev_date_query, account_id, pnl_date)
        
        pnl_records = []
        total_pnl = Decimal('0')
        
        if prev_date_result:
            prev_date = prev_date_result['position_date']
            
            # Get previous positions
            prev_positions_query = """
                SELECT symbol, quantity, market_value
                FROM positions.position_history
                WHERE account_id = $1 AND position_date = $2
            """
            prev_positions = await self.fetch_all(prev_positions_query, account_id, prev_date)
            prev_positions_dict = {p['symbol']: p for p in prev_positions}
        else:
            prev_positions_dict = {}
        
        # Get trades for the day
        trades_query = """
            SELECT symbol, side, quantity, price, net_amount, commission + fees as costs
            FROM settlement.trades
            WHERE account_id = $1 AND trade_date = $2
        """
        trades = await self.fetch_all(trades_query, account_id, pnl_date)
        trades_by_symbol = {}
        for trade in trades:
            symbol = trade['symbol']
            if symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = {'realized_pnl': Decimal('0'), 'costs': Decimal('0')}
            
            # Simplified realized P&L calculation
            if trade['side'] == 'SELL':
                trades_by_symbol[symbol]['realized_pnl'] += Decimal(str(trade['net_amount']))
            trades_by_symbol[symbol]['costs'] += Decimal(str(trade['costs']))
        
        # Calculate P&L for each position
        for position in positions:
            symbol = position['symbol']
            current_quantity = Decimal(str(position['quantity']))
            current_market_value = Decimal(str(position['market_value']))
            current_unrealized_pnl = Decimal(str(position['unrealized_pnl']))
            
            prev_position = prev_positions_dict.get(symbol, {})
            prev_market_value = Decimal(str(prev_position.get('market_value', 0)))
            prev_quantity = Decimal(str(prev_position.get('quantity', 0)))
            
            # Get trade data for this symbol
            trade_data = trades_by_symbol.get(symbol, {'realized_pnl': Decimal('0'), 'costs': Decimal('0')})
            realized_pnl = trade_data['realized_pnl']
            fees = trade_data['costs']
            
            total_pnl_symbol = current_unrealized_pnl + realized_pnl - fees
            
            pnl_record = {
                'account_id': account_id,
                'symbol': symbol,
                'pnl_date': pnl_date,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': current_unrealized_pnl,
                'total_pnl': total_pnl_symbol,
                'market_value_start': prev_market_value,
                'market_value_end': current_market_value,
                'quantity_start': prev_quantity,
                'quantity_end': current_quantity,
                'trading_pnl': realized_pnl,
                'fees': fees
            }
            
            pnl_records.append(pnl_record)
            total_pnl += total_pnl_symbol
        
        # Store P&L records
        await self.upsert_daily_pnl_records(pnl_records)
        
        # Also create portfolio-level P&L
        await self.upsert_daily_pnl_records([{
            'account_id': account_id,
            'symbol': None,  # Portfolio level
            'pnl_date': pnl_date,
            'realized_pnl': sum(r['realized_pnl'] for r in pnl_records),
            'unrealized_pnl': sum(r['unrealized_pnl'] for r in pnl_records),
            'total_pnl': total_pnl,
            'market_value_start': sum(r['market_value_start'] for r in pnl_records),
            'market_value_end': sum(r['market_value_end'] for r in pnl_records),
            'quantity_start': Decimal('0'),
            'quantity_end': Decimal('0'),
            'trading_pnl': sum(r['trading_pnl'] for r in pnl_records),
            'fees': sum(r['fees'] for r in pnl_records)
        }])
        
        return {
            'account_id': account_id,
            'pnl_date': str(pnl_date),
            'total_pnl': float(total_pnl),
            'positions_calculated': len(pnl_records)
        }
    
    async def upsert_daily_pnl_records(self, pnl_records: List[Dict[str, Any]]) -> int:
        """Insert or update daily P&L records"""
        if not pnl_records:
            return 0
        
        queries = []
        for record in pnl_records:
            query = """
                INSERT INTO pnl.daily_pnl
                (account_id, symbol, pnl_date, realized_pnl, unrealized_pnl, total_pnl,
                 market_value_start, market_value_end, quantity_start, quantity_end,
                 trading_pnl, dividends, fees)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (account_id, symbol, pnl_date)
                DO UPDATE SET
                    realized_pnl = EXCLUDED.realized_pnl,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    total_pnl = EXCLUDED.total_pnl,
                    market_value_start = EXCLUDED.market_value_start,
                    market_value_end = EXCLUDED.market_value_end,
                    quantity_start = EXCLUDED.quantity_start,
                    quantity_end = EXCLUDED.quantity_end,
                    trading_pnl = EXCLUDED.trading_pnl,
                    dividends = EXCLUDED.dividends,
                    fees = EXCLUDED.fees
            """
            
            params = (
                record['account_id'], record['symbol'], record['pnl_date'],
                float(record['realized_pnl']), float(record['unrealized_pnl']), 
                float(record['total_pnl']), float(record['market_value_start']),
                float(record['market_value_end']), float(record['quantity_start']),
                float(record['quantity_end']), float(record['trading_pnl']),
                float(record.get('dividends', 0)), float(record['fees'])
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_daily_pnl(self, account_id: str = None, pnl_date: date = None,
                          symbol: str = None, start_date: date = None,
                          end_date: date = None) -> List[Dict[str, Any]]:
        """Get daily P&L records with filters"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        if pnl_date:
            filters['pnl_date'] = pnl_date
        if symbol:
            filters['symbol'] = symbol
        
        where_clause, params = self.build_where_clause(filters)
        
        if start_date:
            where_clause += f" AND pnl_date >= ${len(params) + 1}"
            params.append(start_date)
        
        if end_date:
            where_clause += f" AND pnl_date <= ${len(params) + 1}"
            params.append(end_date)
        
        query = f"""
            SELECT * FROM pnl.daily_pnl
            WHERE {where_clause}
            ORDER BY pnl_date DESC, account_id, symbol NULLS FIRST
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = [
            'realized_pnl', 'unrealized_pnl', 'total_pnl', 'market_value_start',
            'market_value_end', 'quantity_start', 'quantity_end', 'trading_pnl',
            'dividends', 'fees'
        ]
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def get_pnl_summary(self, pnl_date: date, account_id: str = None) -> Dict[str, Any]:
        """Get P&L summary for a date"""
        filters = {'pnl_date': pnl_date}
        if account_id:
            filters['account_id'] = account_id
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT 
                COUNT(*) as total_positions,
                SUM(realized_pnl) as total_realized_pnl,
                SUM(unrealized_pnl) as total_unrealized_pnl,
                SUM(total_pnl) as total_pnl,
                SUM(market_value_end) as total_market_value,
                SUM(trading_pnl) as total_trading_pnl,
                SUM(dividends) as total_dividends,
                SUM(fees) as total_fees,
                COUNT(CASE WHEN total_pnl > 0 THEN 1 END) as winning_positions,
                COUNT(CASE WHEN total_pnl < 0 THEN 1 END) as losing_positions,
                AVG(total_pnl) as avg_pnl_per_position
            FROM pnl.daily_pnl
            WHERE {where_clause} AND symbol IS NOT NULL
        """
        
        result = await self.fetch_one(query, *params)
        
        if result:
            decimal_fields = [
                'total_realized_pnl', 'total_unrealized_pnl', 'total_pnl',
                'total_market_value', 'total_trading_pnl', 'total_dividends',
                'total_fees', 'avg_pnl_per_position'
            ]
            result = self.convert_decimal_fields(result, decimal_fields)
        
        return result or {}
    
    async def calculate_portfolio_performance(self, account_id: str, 
                                            performance_date: date) -> Dict[str, Any]:
        """Calculate and store portfolio performance metrics"""
        # Get historical P&L data for calculations
        historical_pnl = await self.get_daily_pnl(
            account_id=account_id,
            end_date=performance_date
        )
        
        if not historical_pnl:
            return {"error": "No P&L data found"}
        
        # Filter portfolio-level records (symbol is NULL)
        portfolio_pnl = [p for p in historical_pnl if p['symbol'] is None]
        
        if len(portfolio_pnl) < 2:
            # Need at least 2 data points for performance calculation
            return {"error": "Insufficient data for performance calculation"}
        
        # Calculate metrics (simplified)
        current_value = portfolio_pnl[0]['market_value_end']  # Most recent
        prev_value = portfolio_pnl[1]['market_value_end'] if len(portfolio_pnl) > 1 else current_value
        
        if prev_value > 0:
            daily_return = (current_value - prev_value) / prev_value * 100
        else:
            daily_return = Decimal('0')
        
        # Calculate other metrics (simplified for demo)
        returns = [p['total_pnl'] / p['market_value_start'] * 100 
                  for p in portfolio_pnl[:30] if p['market_value_start'] > 0]  # Last 30 days
        
        if returns:
            import statistics
            returns_float = [float(r) for r in returns]
            volatility = Decimal(str(statistics.stdev(returns_float))) if len(returns_float) > 1 else Decimal('0')
            avg_return = Decimal(str(statistics.mean(returns_float)))
            
            # Sharpe ratio (simplified, assuming 5% risk-free rate)
            risk_free_rate = Decimal('0.05') / 252  # Daily risk-free rate
            sharpe_ratio = (avg_return - risk_free_rate) / volatility if volatility > 0 else Decimal('0')
            
            # Max drawdown (simplified)
            cumulative_returns = []
            running_total = Decimal('100')
            for ret in returns:
                running_total *= (1 + ret / 100)
                cumulative_returns.append(running_total)
            
            peak = max(cumulative_returns)
            trough = min(cumulative_returns)
            max_drawdown = (peak - trough) / peak * 100 if peak > 0 else Decimal('0')
        else:
            volatility = Decimal('0')
            sharpe_ratio = Decimal('0')
            max_drawdown = Decimal('0')
        
        # Store performance record
        performance_record = {
            'account_id': account_id,
            'performance_date': performance_date,
            'total_return_pct': daily_return,
            'benchmark_return_pct': Decimal('0.08'),  # Simulate 8% benchmark return
            'excess_return_pct': daily_return - Decimal('0.08'),
            'volatility_pct': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown,
            'portfolio_value': current_value,
            'cash_balance': Decimal('10000')  # Simulate cash balance
        }
        
        await self.upsert_portfolio_performance([performance_record])
        
        return {
            'account_id': account_id,
            'performance_date': str(performance_date),
            'total_return_pct': float(daily_return),
            'volatility_pct': float(volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown_pct': float(max_drawdown),
            'portfolio_value': float(current_value)
        }
    
    async def upsert_portfolio_performance(self, performance_records: List[Dict[str, Any]]) -> int:
        """Insert or update portfolio performance records"""
        if not performance_records:
            return 0
        
        queries = []
        for record in performance_records:
            query = """
                INSERT INTO pnl.portfolio_performance
                (account_id, performance_date, total_return_pct, benchmark_return_pct,
                 excess_return_pct, volatility_pct, sharpe_ratio, max_drawdown_pct,
                 portfolio_value, cash_balance)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (account_id, performance_date)
                DO UPDATE SET
                    total_return_pct = EXCLUDED.total_return_pct,
                    benchmark_return_pct = EXCLUDED.benchmark_return_pct,
                    excess_return_pct = EXCLUDED.excess_return_pct,
                    volatility_pct = EXCLUDED.volatility_pct,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    portfolio_value = EXCLUDED.portfolio_value,
                    cash_balance = EXCLUDED.cash_balance
            """
            
            params = (
                record['account_id'], record['performance_date'],
                float(record['total_return_pct']), float(record['benchmark_return_pct']),
                float(record['excess_return_pct']), float(record['volatility_pct']),
                float(record['sharpe_ratio']), float(record['max_drawdown_pct']),
                float(record['portfolio_value']), float(record['cash_balance'])
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_portfolio_performance_metrics(self, account_id: str, 
                                              start_date: date, end_date: date) -> Dict[str, Any]:
        """Get portfolio performance metrics over a period"""
        query = """
            SELECT 
                performance_date,
                total_return_pct,
                benchmark_return_pct,
                excess_return_pct,
                volatility_pct,
                sharpe_ratio,
                max_drawdown_pct,
                portfolio_value
            FROM pnl.portfolio_performance
            WHERE account_id = $1 AND performance_date BETWEEN $2 AND $3
            ORDER BY performance_date
        """
        
        rows = await self.fetch_all(query, account_id, start_date, end_date)
        
        if not rows:
            return {"error": "No performance data found"}
        
        # Convert decimal fields
        decimal_fields = [
            'total_return_pct', 'benchmark_return_pct', 'excess_return_pct',
            'volatility_pct', 'sharpe_ratio', 'max_drawdown_pct', 'portfolio_value'
        ]
        performance_data = [self.convert_decimal_fields(row, decimal_fields) for row in rows]
        
        # Calculate period statistics
        returns = [float(row['total_return_pct']) for row in performance_data]
        
        if returns:
            import statistics
            period_stats = {
                'total_return': sum(returns),
                'avg_daily_return': statistics.mean(returns),
                'volatility': statistics.stdev(returns) if len(returns) > 1 else 0,
                'best_day': max(returns),
                'worst_day': min(returns),
                'positive_days': len([r for r in returns if r > 0]),
                'negative_days': len([r for r in returns if r < 0]),
                'final_portfolio_value': float(performance_data[-1]['portfolio_value'])
            }
        else:
            period_stats = {}
        
        return {
            'account_id': account_id,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'daily_performance': performance_data,
            'period_statistics': period_stats
        }