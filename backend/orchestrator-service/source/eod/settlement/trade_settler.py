# source/eod/settlement/trade_settler.py
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import uuid

logger = logging.getLogger(__name__)

class TradeStatus(Enum):
    PENDING = "pending"
    MATCHED = "matched"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SettlementStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TradeSettler:
    """Handles trade matching and settlement processing"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Settlement configuration
        self.settlement_cycles = {
            'EQUITY': 2,  # T+2 for equities
            'BOND': 1,    # T+1 for bonds
            'FX': 2,      # T+2 for FX
            'COMMODITY': 1 # T+1 for commodities
        }
        
    async def initialize(self):
        """Initialize trade settler"""
        await self._create_settlement_tables()
        logger.info("🔄 Trade Settler initialized")
    
    async def _create_settlement_tables(self):
        """Create settlement-related tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS settlement
            """)
            
            # Trades table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settlement.trades (
                    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,  -- BUY/SELL
                    quantity DECIMAL(20,8) NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    trade_date DATE NOT NULL,
                    settlement_date DATE NOT NULL,
                    trade_value DECIMAL(20,2) NOT NULL,
                    commission DECIMAL(20,2) DEFAULT 0,
                    fees DECIMAL(20,2) DEFAULT 0,
                    net_amount DECIMAL(20,2) NOT NULL,
                    currency VARCHAR(3) DEFAULT 'USD',
                    counterparty VARCHAR(100),
                    trade_status VARCHAR(20) DEFAULT 'PENDING',
                    settlement_status VARCHAR(20) DEFAULT 'PENDING',
                    external_trade_id VARCHAR(100),
                    execution_time TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Trade matching table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settlement.trade_matches (
                    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    buy_trade_id UUID REFERENCES settlement.trades(trade_id),
                    sell_trade_id UUID REFERENCES settlement.trades(trade_id),
                    matched_quantity DECIMAL(20,8) NOT NULL,
                    match_price DECIMAL(20,8) NOT NULL,
                    match_date DATE NOT NULL,
                    match_status VARCHAR(20) DEFAULT 'MATCHED',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Settlement instructions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settlement.settlement_instructions (
                    instruction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    trade_id UUID REFERENCES settlement.trades(trade_id),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    settlement_date DATE NOT NULL,
                    settlement_type VARCHAR(20) NOT NULL, -- CASH/SECURITIES
                    amount DECIMAL(20,2),
                    quantity DECIMAL(20,8),
                    counterparty_account VARCHAR(100),
                    instruction_status VARCHAR(20) DEFAULT 'PENDING',
                    settlement_agent VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    processed_at TIMESTAMP WITH TIME ZONE
                )
            """)
            
            # Settlement failures table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settlement.settlement_failures (
                    failure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    trade_id UUID REFERENCES settlement.trades(trade_id),
                    instruction_id UUID REFERENCES settlement.settlement_instructions(instruction_id),
                    failure_date DATE NOT NULL,
                    failure_reason VARCHAR(200) NOT NULL,
                    failure_type VARCHAR(50) NOT NULL,
                    resolution_status VARCHAR(20) DEFAULT 'PENDING',
                    resolved_date DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indices
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_settlement_date 
                ON settlement.trades (settlement_date, settlement_status)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_account_date 
                ON settlement.trades (account_id, trade_date)
            """)
    
    async def process_trade_settlements(self, settlement_date: date) -> Dict[str, Any]:
        """Process all trade settlements for the given date"""
        logger.info(f"🔄 Processing trade settlements for {settlement_date}")
        
        try:
            results = {
                "trades_to_settle": 0,
                "trades_matched": 0,
                "trades_settled": 0,
                "settlement_failures": 0,
                "total_settlement_value": Decimal('0'),
                "settlement_by_currency": {},
                "failed_settlements": []
            }
            
            # Step 1: Get trades that need settlement
            trades_to_settle = await self._get_trades_for_settlement(settlement_date)
            results["trades_to_settle"] = len(trades_to_settle)
            
            if not trades_to_settle:
                logger.info("No trades to settle")
                return results
            
            logger.info(f"Found {len(trades_to_settle)} trades to settle")
            
            # Step 2: Match trades
            matching_results = await self._match_trades(trades_to_settle, settlement_date)
            results["trades_matched"] = matching_results["matched_trades"]
            
            # Step 3: Generate settlement instructions
            instructions = await self._generate_settlement_instructions(trades_to_settle, settlement_date)
            
            # Step 4: Process settlements
            settlement_results = await self._process_settlements(instructions, settlement_date)
            results.update(settlement_results)
            
            # Step 5: Handle settlement failures
            failure_results = await self._handle_settlement_failures(settlement_date)
            results["settlement_failures"] = failure_results["failure_count"]
            results["failed_settlements"] = failure_results["failed_trades"]
            
            logger.info(f"✅ Trade settlement complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to process trade settlements: {e}", exc_info=True)
            raise
    
    async def _get_trades_for_settlement(self, settlement_date: date) -> List[Dict[str, Any]]:
        """Get all trades that need to be settled on the given date"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM settlement.trades
                WHERE settlement_date = $1 
                  AND settlement_status IN ('PENDING', 'MATCHED')
                ORDER BY trade_id
            """, settlement_date)
            
            return [dict(row) for row in rows]
    
    async def _match_trades(self, trades: List[Dict[str, Any]], settlement_date: date) -> Dict[str, Any]:
        """Match buy and sell trades"""
        logger.info("🤝 Matching trades")
        
        matched_trades = 0
        
        # Group trades by symbol for matching
        trades_by_symbol = {}
        for trade in trades:
            symbol = trade['symbol']
            if symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = {'buys': [], 'sells': []}
            
            if trade['side'] == 'BUY':
                trades_by_symbol[symbol]['buys'].append(trade)
            else:
                trades_by_symbol[symbol]['sells'].append(trade)
        
        async with self.db_manager.pool.acquire() as conn:
            for symbol, symbol_trades in trades_by_symbol.items():
                buys = symbol_trades['buys']
                sells = symbol_trades['sells']
                
                # Simple matching algorithm (FIFO)
                buy_idx = 0
                sell_idx = 0
                
                while buy_idx < len(buys) and sell_idx < len(sells):
                    buy_trade = buys[buy_idx]
                    sell_trade = sells[sell_idx]
                    
                    buy_remaining = Decimal(str(buy_trade['quantity']))
                    sell_remaining = Decimal(str(sell_trade['quantity']))
                    
                    # Match the smaller quantity
                    matched_qty = min(buy_remaining, sell_remaining)
                    match_price = (Decimal(str(buy_trade['price'])) + Decimal(str(sell_trade['price']))) / 2
                    
                    # Create match record
                    await conn.execute("""
                        INSERT INTO settlement.trade_matches
                        (buy_trade_id, sell_trade_id, matched_quantity, match_price, match_date)
                        VALUES ($1, $2, $3, $4, $5)
                    """, buy_trade['trade_id'], sell_trade['trade_id'], 
                    float(matched_qty), float(match_price), settlement_date)
                    
                    # Update trade statuses
                    await conn.execute("""
                        UPDATE settlement.trades 
                        SET trade_status = 'MATCHED', updated_at = NOW()
                        WHERE trade_id IN ($1, $2)
                    """, buy_trade['trade_id'], sell_trade['trade_id'])
                    
                    matched_trades += 2  # Both buy and sell
                    
                    # Move to next trades
                    if buy_remaining <= sell_remaining:
                        buy_idx += 1
                    if sell_remaining <= buy_remaining:
                        sell_idx += 1
        
        return {"matched_trades": matched_trades}
    
    async def _generate_settlement_instructions(self, trades: List[Dict[str, Any]], 
                                              settlement_date: date) -> List[Dict[str, Any]]:
        """Generate settlement instructions for trades"""
        logger.info("📋 Generating settlement instructions")
        
        instructions = []
        
        async with self.db_manager.pool.acquire() as conn:
            for trade in trades:
                trade_id = trade['trade_id']
                account_id = trade['account_id']
                symbol = trade['symbol']
                side = trade['side']
                quantity = Decimal(str(trade['quantity']))
                net_amount = Decimal(str(trade['net_amount']))
                
                # Generate cash instruction
                cash_instruction = {
                    'trade_id': trade_id,
                    'account_id': account_id,
                    'symbol': symbol,
                    'settlement_date': settlement_date,
                    'settlement_type': 'CASH',
                    'amount': float(-net_amount if side == 'BUY' else net_amount),
                    'quantity': None,
                    'counterparty_account': f"CLEARINGHOUSE_{symbol}",
                    'settlement_agent': 'DTC'
                }
                
                # Generate securities instruction
                securities_instruction = {
                    'trade_id': trade_id,
                    'account_id': account_id,
                    'symbol': symbol,
                    'settlement_date': settlement_date,
                    'settlement_type': 'SECURITIES',
                    'amount': None,
                    'quantity': float(quantity if side == 'BUY' else -quantity),
                    'counterparty_account': f"CLEARINGHOUSE_{symbol}",
                    'settlement_agent': 'DTC'
                }
                
                # Insert instructions
                for instruction in [cash_instruction, securities_instruction]:
                    result = await conn.fetchrow("""
                        INSERT INTO settlement.settlement_instructions
                        (trade_id, account_id, symbol, settlement_date, settlement_type,
                         amount, quantity, counterparty_account, settlement_agent)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING instruction_id
                    """, 
                    instruction['trade_id'], instruction['account_id'], instruction['symbol'],
                    instruction['settlement_date'], instruction['settlement_type'],
                    instruction['amount'], instruction['quantity'],
                    instruction['counterparty_account'], instruction['settlement_agent'])
                    
                    instruction['instruction_id'] = result['instruction_id']
                    instructions.append(instruction)
        
        logger.info(f"Generated {len(instructions)} settlement instructions")
        return instructions
    
    async def _process_settlements(self, instructions: List[Dict[str, Any]], 
                                 settlement_date: date) -> Dict[str, Any]:
        """Process settlement instructions"""
        logger.info("💰 Processing settlement instructions")
        
        settled_count = 0
        failed_count = 0
        total_value = Decimal('0')
        settlement_by_currency = {}
        
        async with self.db_manager.pool.acquire() as conn:
            for instruction in instructions:
                try:
                    instruction_id = instruction['instruction_id']
                    settlement_type = instruction['settlement_type']
                    
                    # Simulate settlement processing
                    success = await self._simulate_settlement_processing(instruction)
                    
                    if success:
                        # Mark instruction as completed
                        await conn.execute("""
                            UPDATE settlement.settlement_instructions
                            SET instruction_status = 'COMPLETED', processed_at = NOW()
                            WHERE instruction_id = $1
                        """, instruction_id)
                        
                        # Update trade settlement status
                        await conn.execute("""
                            UPDATE settlement.trades
                            SET settlement_status = 'SETTLED', updated_at = NOW()
                            WHERE trade_id = $1
                        """, instruction['trade_id'])
                        
                        settled_count += 1
                        
                        # Track settlement values
                        if settlement_type == 'CASH' and instruction['amount']:
                            amount = abs(Decimal(str(instruction['amount'])))
                            total_value += amount
                            
                            currency = 'USD'  # Assume USD for now
                            if currency not in settlement_by_currency:
                                settlement_by_currency[currency] = Decimal('0')
                            settlement_by_currency[currency] += amount
                    
                    else:
                        # Handle settlement failure
                        await self._record_settlement_failure(
                            instruction['trade_id'], instruction_id,
                            settlement_date, "Settlement processing failed",
                            "PROCESSING_ERROR"
                        )
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing instruction {instruction['instruction_id']}: {e}")
                    await self._record_settlement_failure(
                        instruction['trade_id'], instruction['instruction_id'],
                        settlement_date, str(e), "SYSTEM_ERROR"
                    )
                    failed_count += 1
        
        return {
            "trades_settled": settled_count,
            "settlement_failures": failed_count,
            "total_settlement_value": total_value,
            "settlement_by_currency": {k: float(v) for k, v in settlement_by_currency.items()}
        }
    
    async def _simulate_settlement_processing(self, instruction: Dict[str, Any]) -> bool:
        """Simulate settlement processing (with occasional failures)"""
        import random
        
        # Simulate processing delay
        await asyncio.sleep(0.01)
        
        # 95% success rate
        return random.random() < 0.95
    
    async def _record_settlement_failure(self, trade_id: str, instruction_id: str,
                                       failure_date: date, failure_reason: str,
                                       failure_type: str):
        """Record a settlement failure"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settlement.settlement_failures
                (trade_id, instruction_id, failure_date, failure_reason, failure_type)
                VALUES ($1, $2, $3, $4, $5)
            """, trade_id, instruction_id, failure_date, failure_reason, failure_type)
            
            # Update instruction status
            await conn.execute("""
                UPDATE settlement.settlement_instructions
                SET instruction_status = 'FAILED', processed_at = NOW()
                WHERE instruction_id = $1
            """, instruction_id)
            
            # Update trade status
            await conn.execute("""
                UPDATE settlement.trades
                SET settlement_status = 'FAILED', updated_at = NOW()
                WHERE trade_id = $1
            """, trade_id)
    
    async def _handle_settlement_failures(self, settlement_date: date) -> Dict[str, Any]:
        """Handle and report settlement failures"""
        logger.info("🚨 Handling settlement failures")
        
        async with self.db_manager.pool.acquire() as conn:
            failures = await conn.fetch("""
                SELECT sf.*, t.symbol, t.account_id, t.trade_value, t.side
                FROM settlement.settlement_failures sf
                JOIN settlement.trades t ON sf.trade_id = t.trade_id
                WHERE sf.failure_date = $1 AND sf.resolution_status = 'PENDING'
                ORDER BY t.trade_value DESC
            """, settlement_date)
            
            failed_trades = []
            for failure in failures:
                failed_trades.append({
                    'trade_id': str(failure['trade_id']),
                    'symbol': failure['symbol'],
                    'account_id': failure['account_id'],
                    'trade_value': float(failure['trade_value']),
                    'side': failure['side'],
                    'failure_reason': failure['failure_reason'],
                    'failure_type': failure['failure_type']
                })
        
        return {
            "failure_count": len(failures),
            "failed_trades": failed_trades
        }
    
    async def create_sample_trades(self, trade_date: date, num_trades: int = 1000) -> Dict[str, Any]:
        """Create sample trades for testing"""
        logger.info(f"🎲 Creating {num_trades} sample trades for {trade_date}")
        
        import random
        import string
        
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA']
        accounts = [f"ACCT_{i:05d}" for i in range(1, 101)]  # 100 test accounts
        
        trades_created = 0
        
        async with self.db_manager.pool.acquire() as conn:
            for i in range(num_trades):
                symbol = random.choice(symbols)
                account_id = random.choice(accounts)
                side = random.choice(['BUY', 'SELL'])
                quantity = Decimal(str(random.randint(100, 10000)))
                price = Decimal(str(round(random.uniform(50, 500), 2)))
                
                # Calculate settlement date based on instrument type
                instrument_type = 'EQUITY'  # Assume all equities for now
                settlement_days = self.settlement_cycles.get(instrument_type, 2)
                settlement_date = trade_date + timedelta(days=settlement_days)
                
                trade_value = quantity * price
                commission = trade_value * Decimal('0.001')  # 0.1% commission
                fees = Decimal('1.00')  # $1 regulatory fee
                
                if side == 'BUY':
                    net_amount = trade_value + commission + fees
                else:
                    net_amount = trade_value - commission - fees
                
                await conn.execute("""
                    INSERT INTO settlement.trades
                    (account_id, symbol, side, quantity, price, trade_date, settlement_date,
                     trade_value, commission, fees, net_amount, external_trade_id, execution_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """, 
                account_id, symbol, side, float(quantity), float(price), 
                trade_date, settlement_date, float(trade_value), float(commission), 
                float(fees), float(net_amount), f"TRADE_{uuid.uuid4().hex[:8].upper()}", 
                datetime.utcnow())
                
                trades_created += 1
        
        logger.info(f"✅ Created {trades_created} sample trades")
        return {"trades_created": trades_created}
    
    async def get_settlement_summary(self, settlement_date: date) -> Dict[str, Any]:
        """Get settlement summary for a specific date"""
        async with self.db_manager.pool.acquire() as conn:
            # Settlement statistics
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN settlement_status = 'SETTLED' THEN 1 END) as settled_trades,
                    COUNT(CASE WHEN settlement_status = 'FAILED' THEN 1 END) as failed_trades,
                    SUM(CASE WHEN settlement_status = 'SETTLED' THEN trade_value ELSE 0 END) as settled_value,
                    SUM(CASE WHEN settlement_status = 'FAILED' THEN trade_value ELSE 0 END) as failed_value
                FROM settlement.trades
                WHERE settlement_date = $1
            """, settlement_date)
            
            # Failures by type
            failure_types = await conn.fetch("""
                SELECT failure_type, COUNT(*) as count
                FROM settlement.settlement_failures
                WHERE failure_date = $1
                GROUP BY failure_type
                ORDER BY count DESC
            """, settlement_date)
            
            return {
                "settlement_date": str(settlement_date),
                "statistics": dict(stats) if stats else {},
                "failure_breakdown": [dict(row) for row in failure_types]
            }