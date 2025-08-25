# source/eod/marking/position_marker.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
import asyncio

logger = logging.getLogger(__name__)

class PositionMarker:
    """Marks positions to market using end-of-day prices"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Pricing sources priority order
        self.pricing_sources = ['BLOOMBERG', 'REFINITIV', 'INTERNAL']
        
    async def initialize(self):
        """Initialize position marker"""
        await self._create_marking_tables()
        logger.info("📈 Position Marker initialized")
    
    async def _create_marking_tables(self):
        """Create position marking tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS positions
            """)
            
            # Current positions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS positions.current_positions (
                    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    quantity DECIMAL(20,8) NOT NULL,
                    avg_cost DECIMAL(20,8) NOT NULL,
                    market_value DECIMAL(20,2),
                    unrealized_pnl DECIMAL(20,2),
                    last_price DECIMAL(20,8),
                    price_date DATE,
                    position_date DATE NOT NULL,
                    currency VARCHAR(3) DEFAULT 'USD',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(account_id, symbol, position_date)
                )
            """)
            
            # Position history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS positions.position_history (
                    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    position_date DATE NOT NULL,
                    quantity DECIMAL(20,8) NOT NULL,
                    avg_cost DECIMAL(20,8) NOT NULL,
                    market_price DECIMAL(20,8) NOT NULL,
                    market_value DECIMAL(20,2) NOT NULL,
                    unrealized_pnl DECIMAL(20,2) NOT NULL,
                    daily_pnl DECIMAL(20,2),
                    pricing_source VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Price sources table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS positions.eod_prices (
                    price_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    price_date DATE NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    volume BIGINT,
                    bid_price DECIMAL(20,8),
                    ask_price DECIMAL(20,8),
                    pricing_source VARCHAR(50) NOT NULL,
                    price_type VARCHAR(20) DEFAULT 'CLOSE',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(symbol, price_date, pricing_source, price_type)
                )
            """)
            
            # Fair value adjustments
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS positions.fair_value_adjustments (
                    adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    adjustment_date DATE NOT NULL,
                    market_price DECIMAL(20,8) NOT NULL,
                    fair_value_price DECIMAL(20,8) NOT NULL,
                    adjustment_amount DECIMAL(20,8) NOT NULL,
                    adjustment_reason TEXT,
                    model_used VARCHAR(50),
                    confidence_level DECIMAL(5,2),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indices
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_positions_account 
                ON positions.current_positions (account_id, position_date)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_date 
                ON positions.position_history (position_date, symbol)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_eod_prices_symbol_date 
                ON positions.eod_prices (symbol, price_date)
            """)
    
    async def mark_positions_to_market(self, marking_date: date) -> Dict[str, Any]:
        """Mark all positions to market for the given date"""
        logger.info(f"📈 Marking positions to market for {marking_date}")
        
        try:
            # Continuing position_marker.py

           results = {
               "positions_marked": 0,
               "positions_failed": 0,
               "total_market_value": Decimal('0'),
               "total_unrealized_pnl": Decimal('0'),
               "pricing_sources_used": {},
               "fair_value_adjustments": 0,
               "illiquid_positions": 0,
               "currency_breakdown": {}
           }
           
           # Step 1: Load EOD prices
           eod_prices = await self._load_eod_prices(marking_date)
           logger.info(f"Loaded {len(eod_prices)} EOD prices")
           
           # Step 2: Get all current positions
           positions = await self._get_current_positions(marking_date)
           logger.info(f"Found {len(positions)} positions to mark")
           
           if not positions:
               logger.info("No positions to mark")
               return results
           
           # Step 3: Mark each position
           for position in positions:
               try:
                   marking_result = await self._mark_single_position(
                       position, eod_prices, marking_date
                   )
                   
                   if marking_result['success']:
                       results["positions_marked"] += 1
                       results["total_market_value"] += marking_result['market_value']
                       results["total_unrealized_pnl"] += marking_result['unrealized_pnl']
                       
                       # Track pricing sources
                       source = marking_result['pricing_source']
                       results["pricing_sources_used"][source] = results["pricing_sources_used"].get(source, 0) + 1
                       
                       # Track currency breakdown
                       currency = marking_result.get('currency', 'USD')
                       if currency not in results["currency_breakdown"]:
                           results["currency_breakdown"][currency] = {
                               'positions': 0, 'market_value': Decimal('0'), 'unrealized_pnl': Decimal('0')
                           }
                       results["currency_breakdown"][currency]['positions'] += 1
                       results["currency_breakdown"][currency]['market_value'] += marking_result['market_value']
                       results["currency_breakdown"][currency]['unrealized_pnl'] += marking_result['unrealized_pnl']
                       
                       # Check if fair value adjustment was applied
                       if marking_result.get('fair_value_adjusted'):
                           results["fair_value_adjustments"] += 1
                       
                       # Check if position is illiquid
                       if marking_result.get('is_illiquid'):
                           results["illiquid_positions"] += 1
                   else:
                       results["positions_failed"] += 1
                       logger.error(f"Failed to mark position: {position['symbol']} - {marking_result.get('error')}")
                       
               except Exception as e:
                   results["positions_failed"] += 1
                   logger.error(f"Error marking position {position['symbol']}: {e}", exc_info=True)
           
           # Convert Decimal to float for serialization
           results["total_market_value"] = float(results["total_market_value"])
           results["total_unrealized_pnl"] = float(results["total_unrealized_pnl"])
           
           for currency in results["currency_breakdown"]:
               results["currency_breakdown"][currency]['market_value'] = float(results["currency_breakdown"][currency]['market_value'])
               results["currency_breakdown"][currency]['unrealized_pnl'] = float(results["currency_breakdown"][currency]['unrealized_pnl'])
           
           logger.info(f"✅ Position marking complete: {results}")
           return results
           
       except Exception as e:
           logger.error(f"❌ Failed to mark positions to market: {e}", exc_info=True)
           raise
   
   async def _load_eod_prices(self, price_date: date) -> Dict[str, Dict[str, Any]]:
       """Load end-of-day prices for all securities"""
       logger.info("💰 Loading EOD prices")
       
       # First, simulate loading prices from external sources
       await self._simulate_price_feed_ingestion(price_date)
       
       async with self.db_manager.pool.acquire() as conn:
           rows = await conn.fetch("""
               SELECT symbol, price, pricing_source, bid_price, ask_price, volume
               FROM positions.eod_prices
               WHERE price_date = $1
               ORDER BY symbol, 
                        CASE pricing_source 
                            WHEN 'BLOOMBERG' THEN 1 
                            WHEN 'REFINITIV' THEN 2 
                            WHEN 'INTERNAL' THEN 3 
                            ELSE 4 
                        END
           """, price_date)
           
           prices = {}
           for row in rows:
               symbol = row['symbol']
               if symbol not in prices:  # Use highest priority source
                   prices[symbol] = {
                       'price': Decimal(str(row['price'])),
                       'pricing_source': row['pricing_source'],
                       'bid_price': Decimal(str(row['bid_price'])) if row['bid_price'] else None,
                       'ask_price': Decimal(str(row['ask_price'])) if row['ask_price'] else None,
                       'volume': row['volume']
                   }
           
           return prices
   
   async def _simulate_price_feed_ingestion(self, price_date: date):
       """Simulate ingesting prices from external feeds"""
       import random
       
       # Get all active securities
       async with self.db_manager.pool.acquire() as conn:
           securities = await conn.fetch("""
               SELECT symbol, last_price FROM reference_data.securities
               WHERE is_active = TRUE
               LIMIT 500  -- Limit for demo
           """)
           
           # Clear existing prices for the date
           await conn.execute("""
               DELETE FROM positions.eod_prices WHERE price_date = $1
           """, price_date)
           
           # Generate EOD prices for each security
           for security in securities:
               symbol = security['symbol']
               base_price = float(security['last_price']) if security['last_price'] else 100.0
               
               for source in self.pricing_sources:
                   # Add some noise to simulate different pricing sources
                   noise_factor = random.gauss(1.0, 0.001)  # 0.1% noise
                   price = base_price * noise_factor
                   
                   # Generate bid/ask
                   spread_pct = random.uniform(0.001, 0.01)  # 0.1% to 1% spread
                   bid_price = price * (1 - spread_pct/2)
                   ask_price = price * (1 + spread_pct/2)
                   
                   volume = random.randint(100000, 5000000)
                   
                   await conn.execute("""
                       INSERT INTO positions.eod_prices
                       (symbol, price_date, price, bid_price, ask_price, volume, pricing_source)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (symbol, price_date, pricing_source, price_type) DO NOTHING
                   """, symbol, price_date, price, bid_price, ask_price, volume, source)
   
   async def _get_current_positions(self, position_date: date) -> List[Dict[str, Any]]:
       """Get all current positions that need marking"""
       # First, simulate some positions
       await self._simulate_current_positions(position_date)
       
       async with self.db_manager.pool.acquire() as conn:
           rows = await conn.fetch("""
               SELECT * FROM positions.current_positions
               WHERE position_date = $1 AND quantity != 0
               ORDER BY account_id, symbol
           """, position_date)
           
           return [dict(row) for row in rows]
   
   async def _simulate_current_positions(self, position_date: date):
       """Create sample positions for testing"""
       import random
       
       symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA']
       accounts = [f"ACCT_{i:05d}" for i in range(1, 51)]  # 50 accounts
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing positions for the date
           await conn.execute("""
               DELETE FROM positions.current_positions WHERE position_date = $1
           """, position_date)
           
           # Generate sample positions
           for account in accounts:
               # Each account has 3-8 positions
               num_positions = random.randint(3, 8)
               account_symbols = random.sample(symbols, num_positions)
               
               for symbol in account_symbols:
                   quantity = Decimal(str(random.randint(100, 5000)))
                   avg_cost = Decimal(str(round(random.uniform(50, 500), 2)))
                   
                   await conn.execute("""
                       INSERT INTO positions.current_positions
                       (account_id, symbol, quantity, avg_cost, position_date)
                       VALUES ($1, $2, $3, $4, $5)
                   """, account, symbol, float(quantity), float(avg_cost), position_date)
   
   async def _mark_single_position(self, position: Dict[str, Any], 
                                 eod_prices: Dict[str, Dict[str, Any]], 
                                 marking_date: date) -> Dict[str, Any]:
       """Mark a single position to market"""
       symbol = position['symbol']
       account_id = position['account_id']
       quantity = Decimal(str(position['quantity']))
       avg_cost = Decimal(str(position['avg_cost']))
       
       result = {
           'success': False,
           'symbol': symbol,
           'account_id': account_id,
           'market_value': Decimal('0'),
           'unrealized_pnl': Decimal('0'),
           'pricing_source': None,
           'fair_value_adjusted': False,
           'is_illiquid': False,
           'currency': 'USD'
       }
       
       try:
           # Get price for the symbol
           if symbol in eod_prices:
               price_data = eod_prices[symbol]
               market_price = price_data['price']
               pricing_source = price_data['pricing_source']
               volume = price_data.get('volume', 0)
               
               # Check if position is illiquid (low volume)
               is_illiquid = volume < 50000  # Less than 50k shares traded
               
               # Apply fair value adjustment for illiquid positions
               if is_illiquid:
                   adjusted_price = await self._apply_fair_value_adjustment(
                       symbol, market_price, marking_date
                   )
                   if adjusted_price != market_price:
                       market_price = adjusted_price
                       result['fair_value_adjusted'] = True
               
               # Calculate market value and P&L
               market_value = quantity * market_price
               cost_basis = quantity * avg_cost
               unrealized_pnl = market_value - cost_basis
               
               # Update position in database
               await self._update_position_marking(
                   position, market_price, market_value, unrealized_pnl, 
                   marking_date, pricing_source
               )
               
               # Record in position history
               await self._record_position_history(
                   account_id, symbol, marking_date, quantity, avg_cost,
                   market_price, market_value, unrealized_pnl, pricing_source
               )
               
               result.update({
                   'success': True,
                   'market_value': market_value,
                   'unrealized_pnl': unrealized_pnl,
                   'pricing_source': pricing_source,
                   'is_illiquid': is_illiquid
               })
               
           else:
               # No price available
               logger.warning(f"No EOD price available for {symbol}")
               result['error'] = f"No EOD price available for {symbol}"
               
       except Exception as e:
           result['error'] = str(e)
           logger.error(f"Error marking position {symbol}: {e}", exc_info=True)
       
       return result
   
   async def _apply_fair_value_adjustment(self, symbol: str, market_price: Decimal, 
                                        adjustment_date: date) -> Decimal:
       """Apply fair value adjustment for illiquid securities"""
       # Simple fair value model - apply a liquidity discount
       liquidity_discount = Decimal('0.05')  # 5% discount for illiquid securities
       fair_value_price = market_price * (Decimal('1') - liquidity_discount)
       
       adjustment_amount = market_price - fair_value_price
       
       # Record the adjustment
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               INSERT INTO positions.fair_value_adjustments
               (symbol, adjustment_date, market_price, fair_value_price, 
                adjustment_amount, adjustment_reason, model_used, confidence_level)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           """, symbol, adjustment_date, float(market_price), float(fair_value_price),
           float(adjustment_amount), "Liquidity discount for low volume security",
           "LIQUIDITY_DISCOUNT_MODEL", 85.0)
       
       logger.info(f"Applied fair value adjustment to {symbol}: ${market_price:.2f} -> ${fair_value_price:.2f}")
       return fair_value_price
   
   async def _update_position_marking(self, position: Dict[str, Any], 
                                    market_price: Decimal, market_value: Decimal,
                                    unrealized_pnl: Decimal, marking_date: date,
                                    pricing_source: str):
       """Update position with marking information"""
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               UPDATE positions.current_positions
               SET market_value = $1,
                   unrealized_pnl = $2,
                   last_price = $3,
                   price_date = $4,
                   updated_at = NOW()
               WHERE position_id = $5
           """, float(market_value), float(unrealized_pnl), float(market_price), 
           marking_date, position['position_id'])
   
   async def _record_position_history(self, account_id: str, symbol: str, 
                                    position_date: date, quantity: Decimal,
                                    avg_cost: Decimal, market_price: Decimal,
                                    market_value: Decimal, unrealized_pnl: Decimal,
                                    pricing_source: str):
       """Record position in history table"""
       async with self.db_manager.pool.acquire() as conn:
           # Calculate daily P&L (difference from previous day)
           previous_day_pnl = await conn.fetchrow("""
               SELECT unrealized_pnl FROM positions.position_history
               WHERE account_id = $1 AND symbol = $2 AND position_date = $3 - INTERVAL '1 day'
           """, account_id, symbol, position_date)
           
           daily_pnl = unrealized_pnl
           if previous_day_pnl:
               daily_pnl = unrealized_pnl - Decimal(str(previous_day_pnl['unrealized_pnl']))
           
           await conn.execute("""
               INSERT INTO positions.position_history
               (account_id, symbol, position_date, quantity, avg_cost, market_price,
                market_value, unrealized_pnl, daily_pnl, pricing_source)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
               ON CONFLICT (account_id, symbol, position_date) 
               DO UPDATE SET
                   quantity = $4, avg_cost = $5, market_price = $6,
                   market_value = $7, unrealized_pnl = $8, daily_pnl = $9,
                   pricing_source = $10
           """, account_id, symbol, position_date, float(quantity), float(avg_cost),
           float(market_price), float(market_value), float(unrealized_pnl),
           float(daily_pnl), pricing_source)
   
   async def get_position_summary(self, position_date: date, account_id: str = None) -> Dict[str, Any]:
       """Get position summary for a specific date"""
       async with self.db_manager.pool.acquire() as conn:
           where_clause = "WHERE position_date = $1"
           params = [position_date]
           
           if account_id:
               where_clause += " AND account_id = $2"
               params.append(account_id)
           
           # Overall statistics
           stats = await conn.fetchrow(f"""
               SELECT 
                   COUNT(*) as total_positions,
                   SUM(CASE WHEN quantity > 0 THEN 1 ELSE 0 END) as long_positions,
                   SUM(CASE WHEN quantity < 0 THEN 1 ELSE 0 END) as short_positions,
                   SUM(market_value) as total_market_value,
                   SUM(unrealized_pnl) as total_unrealized_pnl,
                   AVG(unrealized_pnl) as avg_unrealized_pnl
               FROM positions.position_history
               {where_clause}
           """, *params)
           
           # Top winners and losers
           winners = await conn.fetch(f"""
               SELECT account_id, symbol, unrealized_pnl, market_value
               FROM positions.position_history
               {where_clause} AND unrealized_pnl > 0
               ORDER BY unrealized_pnl DESC
               LIMIT 10
           """, *params)
           
           losers = await conn.fetch(f"""
               SELECT account_id, symbol, unrealized_pnl, market_value
               FROM positions.position_history
               {where_clause} AND unrealized_pnl < 0
               ORDER BY unrealized_pnl ASC
               LIMIT 10
           """, *params)
           
           # By symbol breakdown
           by_symbol = await conn.fetch(f"""
               SELECT 
                   symbol,
                   COUNT(*) as position_count,
                   SUM(quantity) as net_quantity,
                   SUM(market_value) as total_market_value,
                   SUM(unrealized_pnl) as total_unrealized_pnl
               FROM positions.position_history
               {where_clause}
               GROUP BY symbol
               ORDER BY total_market_value DESC
               LIMIT 20
           """, *params)
           
           return {
               "position_date": str(position_date),
               "account_filter": account_id,
               "summary_statistics": dict(stats) if stats else {},
               "top_winners": [dict(row) for row in winners],
               "top_losers": [dict(row) for row in losers],
               "by_symbol": [dict(row) for row in by_symbol]
           }
   
   async def get_fair_value_adjustments(self, adjustment_date: date) -> List[Dict[str, Any]]:
       """Get all fair value adjustments for a specific date"""
       async with self.db_manager.pool.acquire() as conn:
           rows = await conn.fetch("""
               SELECT * FROM positions.fair_value_adjustments
               WHERE adjustment_date = $1
               ORDER BY ABS(adjustment_amount) DESC
           """, adjustment_date)
           
           return [dict(row) for row in rows]