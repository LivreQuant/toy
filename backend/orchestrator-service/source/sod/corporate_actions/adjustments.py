# source/sod/corporate_actions/adjustments.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class AdjustmentType(Enum):
    PRICE = "price"
    QUANTITY = "quantity"
    CASH = "cash"
    SYMBOL_CHANGE = "symbol_change"

class AdjustmentStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    REVERSED = "reversed"

class CorporateActionAdjustments:
    """Handles price and position adjustments for corporate actions"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize adjustments processor"""
        await self._create_adjustment_tables()
        logger.info("⚖️ Corporate Action Adjustments initialized")
    
    async def _create_adjustment_tables(self):
        """Create adjustment tracking tables"""
        async with self.db_manager.pool.acquire() as conn:
            # Price adjustment history
            await conn.execute("""
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
            
            # Position adjustment audit
            await conn.execute("""
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
                    corporate_action_id UUID,
                    status VARCHAR(20) DEFAULT 'APPLIED',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def apply_dividend_adjustments(self, symbol: str, ex_date: date, 
                                       dividend_amount: Decimal, currency: str = 'USD') -> Dict[str, Any]:
        """Apply dividend adjustments to historical prices and positions"""
        logger.info(f"💰 Applying dividend adjustments for {symbol}: ${dividend_amount}")
        
        results = {
            "symbol": symbol,
            "ex_date": str(ex_date),
            "dividend_amount": float(dividend_amount),
            "price_adjustments": 0,
            "position_adjustments": 0,
            "cash_distributed": Decimal('0')
        }
        
        try:
            # Apply historical price adjustments
            price_result = await self._adjust_historical_prices_dividend(
                symbol, ex_date, dividend_amount
            )
            results["price_adjustments"] = price_result["adjustments_made"]
            
            # Apply position adjustments (dividend payments)
            position_result = await self._apply_dividend_to_positions(
                symbol, ex_date, dividend_amount, currency
            )
            results["position_adjustments"] = position_result["positions_adjusted"]
            results["cash_distributed"] = position_result["total_cash_distributed"]
            
            logger.info(f"✅ Dividend adjustments applied: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply dividend adjustments: {e}", exc_info=True)
            raise
    
    async def apply_split_adjustments(self, symbol: str, ex_date: date, 
                                    split_ratio: Decimal) -> Dict[str, Any]:
        """Apply stock split adjustments"""
        logger.info(f"📊 Applying split adjustments for {symbol}: {split_ratio}:1")
        
        results = {
            "symbol": symbol,
            "ex_date": str(ex_date),
            "split_ratio": float(split_ratio),
            "price_adjustments": 0,
            "position_adjustments": 0
        }
        
        try:
            # Apply historical price adjustments
            price_result = await self._adjust_historical_prices_split(
                symbol, ex_date, split_ratio
            )
            results["price_adjustments"] = price_result["adjustments_made"]
            
            # Apply position adjustments
            position_result = await self._apply_split_to_positions(
                symbol, ex_date, split_ratio
            )
            results["position_adjustments"] = position_result["positions_adjusted"]
            
            logger.info(f"✅ Split adjustments applied: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply split adjustments: {e}", exc_info=True)
            raise
    
    async def apply_spinoff_adjustments(self, parent_symbol: str, new_symbol: str, 
                                      ex_date: date, distribution_ratio: Decimal,
                                      spinoff_price: Decimal) -> Dict[str, Any]:
        """Apply spin-off adjustments"""
        logger.info(f"🔄 Applying spin-off adjustments: {parent_symbol} -> {new_symbol}")
        
        results = {
            "parent_symbol": parent_symbol,
            "new_symbol": new_symbol,
            "ex_date": str(ex_date),
            "distribution_ratio": float(distribution_ratio),
            "position_adjustments": 0,
            "new_positions_created": 0
        }
        
        try:
            # Adjust parent company value
            adjustment_factor = await self._calculate_spinoff_adjustment_factor(
                parent_symbol, new_symbol, spinoff_price, distribution_ratio
            )
            
            # Apply price adjustments to parent
            await self._adjust_historical_prices_spinoff(
                parent_symbol, ex_date, adjustment_factor
            )
            
            # Create new positions for spin-off
            position_result = await self._create_spinoff_positions(
                parent_symbol, new_symbol, ex_date, distribution_ratio, spinoff_price
            )
            
            results["position_adjustments"] = position_result["parent_positions_adjusted"]
            results["new_positions_created"] = position_result["new_positions_created"]
            
            logger.info(f"✅ Spin-off adjustments applied: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply spin-off adjustments: {e}", exc_info=True)
            raise
    
    async def _adjust_historical_prices_dividend(self, symbol: str, ex_date: date, 
                                               dividend_amount: Decimal) -> Dict[str, Any]:
        """Adjust historical prices for dividend"""
        async with self.db_manager.pool.acquire() as conn:
            # Get historical prices before ex-date
            historical_prices = await conn.fetch("""
                SELECT price_date, price FROM positions.eod_prices
                WHERE symbol = $1 AND price_date < $2
                ORDER BY price_date DESC
            """, symbol, ex_date)
            
            adjustments_made = 0
            
            for price_record in historical_prices:
                old_price = Decimal(str(price_record['price']))
                new_price = old_price - dividend_amount
                
                # Update the price
                await conn.execute("""
                    UPDATE positions.eod_prices
                    SET price = $1
                    WHERE symbol = $2 AND price_date = $3
                """, float(new_price), symbol, price_record['price_date'])
                
                # Record the adjustment
                await conn.execute("""
                    INSERT INTO corporate_actions.price_adjustment_history
                    (symbol, adjustment_date, adjustment_type, old_price, new_price,
                     adjustment_factor, dividend_amount, adjustment_reason)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, symbol, ex_date, 'DIVIDEND', float(old_price), float(new_price),
                1.0, float(dividend_amount), f'Dividend adjustment: ${dividend_amount}')
                
                adjustments_made += 1
                
                # Limit to prevent excessive processing
                if adjustments_made >= 1000:
                    break
            
            return {"adjustments_made": adjustments_made}
    
    async def _adjust_historical_prices_split(self, symbol: str, ex_date: date,
                                            split_ratio: Decimal) -> Dict[str, Any]:
        """Adjust historical prices for stock split"""
        async with self.db_manager.pool.acquire() as conn:
            adjustment_factor = Decimal('1') / split_ratio
            
            # Update all historical prices before ex-date
            result = await conn.execute("""
                UPDATE positions.eod_prices
                SET price = price * $1
                WHERE symbol = $2 AND price_date < $3
            """, float(adjustment_factor), symbol, ex_date)
            
            adjustments_made = result.split()[1] if result else 0  # Extract row count
            
            # Record the adjustment
            await conn.execute("""
                INSERT INTO corporate_actions.price_adjustment_history
                (symbol, adjustment_date, adjustment_type, adjustment_factor,
                 split_ratio, adjustment_reason)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, symbol, ex_date, 'STOCK_SPLIT', float(adjustment_factor),
            float(split_ratio), f'Stock split adjustment: {split_ratio}:1')
            
            return {"adjustments_made": int(adjustments_made)}
    
    async def _adjust_historical_prices_spinoff(self, parent_symbol: str, ex_date: date,
                                              adjustment_factor: Decimal) -> Dict[str, Any]:
        """Adjust historical prices for spin-off"""
        async with self.db_manager.pool.acquire() as conn:
            # Update historical prices for parent company
            result = await conn.execute("""
                UPDATE positions.eod_prices
                SET price = price * $1
                WHERE symbol = $2 AND price_date < $3
            """, float(adjustment_factor), parent_symbol, ex_date)
            
            adjustments_made = result.split()[1] if result else 0
            
            # Record the adjustment
            await conn.execute("""
                INSERT INTO corporate_actions.price_adjustment_history
                (symbol, adjustment_date, adjustment_type, adjustment_factor,
                 adjustment_reason)
                VALUES ($1, $2, $3, $4, $5)
            """, parent_symbol, ex_date, 'SPINOFF', float(adjustment_factor),
            f'Spin-off price adjustment: {adjustment_factor}')
            
            return {"adjustments_made": int(adjustments_made)}
    
    async def _apply_dividend_to_positions(self, symbol: str, ex_date: date,
                                         dividend_amount: Decimal, currency: str) -> Dict[str, Any]:
        """Apply dividend payments to all positions"""
        async with self.db_manager.pool.acquire() as conn:
            # Get all long positions in the symbol
            positions = await conn.fetch("""
                SELECT account_id, quantity, avg_cost
                FROM positions.current_positions
                WHERE symbol = $1 AND quantity > 0
            """, symbol)
            
            positions_adjusted = 0
            total_cash_distributed = Decimal('0')
            
            for position in positions:
                account_id = position['account_id']
                quantity = Decimal(str(position['quantity']))
                
                # Calculate dividend payment
                dividend_payment = quantity * dividend_amount
                total_cash_distributed += dividend_payment
                
                # Record the adjustment
                await conn.execute("""
                    INSERT INTO corporate_actions.position_adjustment_audit
                    (account_id, symbol, adjustment_date, adjustment_type,
                     old_quantity, new_quantity, cash_impact, status)
                    VALUES ($1, $2, $3, $4, $5, $5, $6, $7)
                """, account_id, symbol, ex_date, 'DIVIDEND_PAYMENT',
                float(quantity), float(dividend_payment), 'APPLIED')
                
                positions_adjusted += 1
            
            return {
                "positions_adjusted": positions_adjusted,
                "total_cash_distributed": total_cash_distributed
            }
    
    async def _apply_split_to_positions(self, symbol: str, ex_date: date,
                                      split_ratio: Decimal) -> Dict[str, Any]:
        """Apply stock split to all positions"""
        async with self.db_manager.pool.acquire() as conn:
            # Get all positions in the symbol
            positions = await conn.fetch("""
                SELECT account_id, quantity, avg_cost
                FROM positions.current_positions
                WHERE symbol = $1 AND quantity != 0
            """, symbol)
            
            positions_adjusted = 0
            
            for position in positions:
                account_id = position['account_id']
                old_quantity = Decimal(str(position['quantity']))
                old_avg_cost = Decimal(str(position['avg_cost']))
                
                # Calculate new values
                new_quantity = old_quantity * split_ratio
                new_avg_cost = old_avg_cost / split_ratio
                
                # Update the position
                await conn.execute("""
                    UPDATE positions.current_positions
                    SET quantity = $1, avg_cost = $2, updated_at = NOW()
                    WHERE account_id = $3 AND symbol = $4
                """, float(new_quantity), float(new_avg_cost), account_id, symbol)
                
                # Record the adjustment
                await conn.execute("""
                    INSERT INTO corporate_actions.position_adjustment_audit
                    (account_id, symbol, adjustment_date, adjustment_type,
                     old_quantity, new_quantity, old_avg_cost, new_avg_cost, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, account_id, symbol, ex_date, 'STOCK_SPLIT',
                float(old_quantity), float(new_quantity), float(old_avg_cost),
                float(new_avg_cost), 'APPLIED')
                
                positions_adjusted += 1
            
            return {"positions_adjusted": positions_adjusted}
    
    async def _create_spinoff_positions(self, parent_symbol: str, new_symbol: str,
                                      ex_date: date, distribution_ratio: Decimal,
                                      spinoff_price: Decimal) -> Dict[str, Any]:
        """Create new positions for spin-off"""
        async with self.db_manager.pool.acquire() as conn:
            # Get all long positions in parent company
            parent_positions = await conn.fetch("""
                SELECT account_id, quantity
                FROM positions.current_positions
                WHERE symbol = $1 AND quantity > 0
            """, parent_symbol)
            
            parent_positions_adjusted = 0
            new_positions_created = 0
            
            for position in parent_positions:
                account_id = position['account_id']
                parent_quantity = Decimal(str(position['quantity']))
                
                # Calculate spin-off shares
                spinoff_shares = parent_quantity * distribution_ratio
                
                if spinoff_shares > 0:
                    # Create new position for spin-off
                    await conn.execute("""
                        INSERT INTO positions.current_positions
                        (account_id, symbol, quantity, avg_cost, position_date, market_value)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (account_id, symbol, position_date)
                        DO UPDATE SET quantity = positions.current_positions.quantity + $3
                    """, account_id, new_symbol, float(spinoff_shares), float(spinoff_price),
                    ex_date, float(spinoff_shares * spinoff_price))
                    
                    # Record the adjustment
                    await conn.execute("""
                        INSERT INTO corporate_actions.position_adjustment_audit
                        (account_id, symbol, adjustment_date, adjustment_type,
                         old_quantity, new_quantity, new_avg_cost, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, account_id, new_symbol, ex_date, 'SPINOFF_DISTRIBUTION',
                    0, float(spinoff_shares), float(spinoff_price), 'APPLIED')
                    
                    new_positions_created += 1
                
                parent_positions_adjusted += 1
            
            return {
                "parent_positions_adjusted": parent_positions_adjusted,
                "new_positions_created": new_positions_created
            }
    
    async def _calculate_spinoff_adjustment_factor(self, parent_symbol: str, new_symbol: str,
                                                 spinoff_price: Decimal, 
                                                 distribution_ratio: Decimal) -> Decimal:
        """Calculate adjustment factor for parent company after spin-off"""
        # Get recent price of parent company
        async with self.db_manager.pool.acquire() as conn:
            parent_price = await conn.fetchrow("""
                SELECT price FROM positions.eod_prices
                WHERE symbol = $1
                ORDER BY price_date DESC
                LIMIT 1
            """, parent_symbol)
            
            if not parent_price:
                return Decimal('0.95')  # Default 5% haircut
            
            current_price = Decimal(str(parent_price['price']))
            
            # Calculate value per share being spun off
            spinoff_value_per_parent_share = spinoff_price * distribution_ratio
            
            # Adjustment factor = (current_price - spinoff_value) / current_price
            if current_price > 0:
                adjustment_factor = (current_price - spinoff_value_per_parent_share) / current_price
                return max(Decimal('0.1'), adjustment_factor)  # Minimum 10% of original value
            
            return Decimal('0.95')
    
    async def reverse_adjustments(self, symbol: str, adjustment_date: date,
                                adjustment_type: str) -> Dict[str, Any]:
        """Reverse previously applied adjustments"""
        logger.info(f"↩️ Reversing {adjustment_type} adjustments for {symbol} on {adjustment_date}")
        
        results = {
            "symbol": symbol,
            "adjustment_date": str(adjustment_date),
            "adjustment_type": adjustment_type,
            "price_reversals": 0,
            "position_reversals": 0
        }
        
        try:
            async with self.db_manager.pool.acquire() as conn:
                # Get adjustment history
                adjustments = await conn.fetch("""
                    SELECT * FROM corporate_actions.price_adjustment_history
                    WHERE symbol = $1 AND adjustment_date = $2 
                      AND adjustment_type = $3 AND status = 'APPLIED'
                """, symbol, adjustment_date, adjustment_type)
                
                for adjustment in adjustments:
                    if adjustment_type == 'DIVIDEND':
                        # Reverse dividend adjustment
                        dividend_amount = Decimal(str(adjustment['dividend_amount']))
                        await self._reverse_dividend_price_adjustment(symbol, dividend_amount)
                        
                    elif adjustment_type == 'STOCK_SPLIT':
                        # Reverse split adjustment
                        adjustment_factor = Decimal(str(adjustment['adjustment_factor']))
                        reverse_factor = Decimal('1') / adjustment_factor
                        await self._reverse_split_price_adjustment(symbol, reverse_factor)
                    
                    # Mark adjustment as reversed
                    await conn.execute("""
                        UPDATE corporate_actions.price_adjustment_history
                        SET status = 'REVERSED'
                        WHERE adjustment_id = $1
                    """, adjustment['adjustment_id'])
                    
                    results["price_reversals"] += 1
                
                # Reverse position adjustments
                position_adjustments = await conn.fetch("""
                    SELECT * FROM corporate_actions.position_adjustment_audit
                    WHERE symbol = $1 AND adjustment_date = $2 
                      AND adjustment_type = $3 AND status = 'APPLIED'
                """, symbol, adjustment_date, adjustment_type)
                
                for pos_adj in position_adjustments:
                    # Mark as reversed (actual position reversal would need more complex logic)
                    await conn.execute("""
                        UPDATE corporate_actions.position_adjustment_audit
                        SET status = 'REVERSED'
                        WHERE audit_id = $1
                    """, pos_adj['audit_id'])
                    
                    results["position_reversals"] += 1
                
                logger.info(f"✅ Adjustments reversed: {results}")
                return results
                
        except Exception as e:
            logger.error(f"❌ Failed to reverse adjustments: {e}", exc_info=True)
            raise
    
    async def _reverse_dividend_price_adjustment(self, symbol: str, dividend_amount: Decimal):
        """Reverse dividend price adjustment by adding dividend back"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions.eod_prices
                SET price = price + $1
                WHERE symbol = $2
            """, float(dividend_amount), symbol)
    
    async def _reverse_split_price_adjustment(self, symbol: str, reverse_factor: Decimal):
        """Reverse split price adjustment"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions.eod_prices
                SET price = price * $1
                WHERE symbol = $2
            """, float(reverse_factor), symbol)
    
    async def get_adjustment_summary(self, symbol: str = None, 
                                   start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Get summary of adjustments applied"""
        async with self.db_manager.pool.acquire() as conn:
            where_conditions = []
            params = []
            
            if symbol:
                where_conditions.append(f"symbol = ${len(params) + 1}")
                params.append(symbol)
            
            if start_date:
                where_conditions.append(f"adjustment_date >= ${len(params) + 1}")
                params.append(start_date)
            
            if end_date:
                where_conditions.append(f"adjustment_date <= ${len(params) + 1}")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Price adjustments summary
            price_summary = await conn.fetch(f"""
                SELECT 
                    adjustment_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT symbol) as unique_symbols
                FROM corporate_actions.price_adjustment_history
                WHERE {where_clause}
                GROUP BY adjustment_type
                ORDER BY count DESC
            """, *params)
            
            # Position adjustments summary
            position_summary = await conn.fetch(f"""
                SELECT 
                    adjustment_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT account_id) as unique_accounts
                FROM corporate_actions.position_adjustment_audit
                WHERE {where_clause}
                GROUP BY adjustment_type
                ORDER BY count DESC
            """, *params)
            
            return {
                "filter_criteria": {
                    "symbol": symbol,
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None
                },
                "price_adjustments": [dict(row) for row in price_summary],
                "position_adjustments": [dict(row) for row in position_summary]
            }