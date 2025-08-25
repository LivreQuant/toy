# source/sod/corporate_actions/ca_processor.py
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class ActionType(Enum):
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    STOCK_DIVIDEND = "stock_dividend"
    SPIN_OFF = "spin_off"
    MERGER = "merger"
    RIGHTS_OFFERING = "rights_offering"
    SPECIAL_DIVIDEND = "special_dividend"

class ActionStatus(Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CorporateActionsProcessor:
    """Processes corporate actions and applies adjustments"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize corporate actions processor"""
        await self._create_ca_tables()
        logger.info("🏢 Corporate Actions Processor initialized")
    
    async def _create_ca_tables(self):
        """Create corporate actions tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS corporate_actions
            """)
            
            # Main corporate actions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_actions.actions (
                    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    announcement_date DATE NOT NULL,
                    ex_date DATE NOT NULL,
                    record_date DATE,
                    payment_date DATE,
                    effective_date DATE,
                    action_details JSONB NOT NULL,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    processed_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Position adjustments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_actions.position_adjustments (
                    adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_id UUID REFERENCES corporate_actions.actions(action_id),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    adjustment_date DATE NOT NULL,
                    old_quantity DECIMAL(20,8),
                    new_quantity DECIMAL(20,8),
                    old_price DECIMAL(20,8),
                    new_price DECIMAL(20,8),
                    cash_adjustment DECIMAL(20,2) DEFAULT 0,
                    adjustment_reason TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Price adjustments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS corporate_actions.price_adjustments (
                    adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_id UUID REFERENCES corporate_actions.actions(action_id),
                    symbol VARCHAR(20) NOT NULL,
                    adjustment_date DATE NOT NULL,
                    adjustment_factor DECIMAL(20,8) NOT NULL,
                    dividend_amount DECIMAL(20,8) DEFAULT 0,
                    adjustment_type VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indices
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_actions_ex_date 
                ON corporate_actions.actions (ex_date, status)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_actions_symbol 
                ON corporate_actions.actions (symbol, ex_date)
            """)
    
    async def process_pending_corporate_actions(self, processing_date: date) -> Dict[str, Any]:
        """Process all pending corporate actions for the given date"""
        logger.info(f"🏢 Processing corporate actions for {processing_date}")
        
        try:
            # Get all pending actions with ex_date <= processing_date
            pending_actions = await self._get_pending_actions(processing_date)
            
            if not pending_actions:
                logger.info("No pending corporate actions to process")
                return {
                    "total_actions": 0,
                    "processed_actions": 0,
                    "failed_actions": 0,
                    "by_type": {}
                }
            
            logger.info(f"Found {len(pending_actions)} pending corporate actions")
            
            results = {
                "total_actions": len(pending_actions),
                "processed_actions": 0,
                "failed_actions": 0,
                "by_type": {}
            }
            
            for action in pending_actions:
                try:
                    action_type = ActionType(action['action_type'])
                    
                    if action_type not in results['by_type']:
                        results['by_type'][action_type.value] = {'processed': 0, 'failed': 0}
                    
                    # Process based on action type
                    success = await self._process_action_by_type(action, action_type, processing_date)
                    
                    if success:
                        results['processed_actions'] += 1
                        results['by_type'][action_type.value]['processed'] += 1
                        
                        # Mark as processed
                        await self._mark_action_processed(action['action_id'])
                        
                        logger.info(f"✅ Processed {action_type.value} for {action['symbol']}")
                        
                    else:
                        results['failed_actions'] += 1
                        results['by_type'][action_type.value]['failed'] += 1
                        
                        # Mark as failed
                        await self._mark_action_failed(action['action_id'], "Processing failed")
                        
                        logger.error(f"❌ Failed to process {action_type.value} for {action['symbol']}")
                        
                except Exception as e:
                    results['failed_actions'] += 1
                    logger.error(f"❌ Error processing action {action['action_id']}: {e}", exc_info=True)
                    
                    await self._mark_action_failed(action['action_id'], str(e))
            
            logger.info(f"🏢 Corporate actions processing complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to process corporate actions: {e}", exc_info=True)
            raise
    
    async def _get_pending_actions(self, processing_date: date) -> List[Dict[str, Any]]:
        """Get all pending corporate actions"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM corporate_actions.actions
                WHERE status = 'PENDING' 
                  AND ex_date <= $1
                ORDER BY ex_date, symbol
            """, processing_date)
            
            return [dict(row) for row in rows]
    
    async def _process_action_by_type(self, action: Dict[str, Any], action_type: ActionType, processing_date: date) -> bool:
        """Process action based on its type"""
        try:
            if action_type == ActionType.DIVIDEND:
                return await self._process_dividend(action, processing_date)
            elif action_type == ActionType.STOCK_SPLIT:
                return await self._process_stock_split(action, processing_date)
            elif action_type == ActionType.STOCK_DIVIDEND:
                return await self._process_stock_dividend(action, processing_date)
            elif action_type == ActionType.SPIN_OFF:
                return await self._process_spin_off(action, processing_date)
            elif action_type == ActionType.MERGER:
                return await self._process_merger(action, processing_date)
            elif action_type == ActionType.RIGHTS_OFFERING:
                return await self._process_rights_offering(action, processing_date)
            elif action_type == ActionType.SPECIAL_DIVIDEND:
                return await self._process_special_dividend(action, processing_date)
            else:
                logger.error(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {action_type.value}: {e}", exc_info=True)
            return False
    
    async def _process_dividend(self, action: Dict[str, Any], processing_date: date) -> bool:
        """Process regular dividend"""
        logger.info(f"💰 Processing dividend for {action['symbol']}")
        
        details = action['action_details']
        dividend_amount = Decimal(str(details['dividend_amount']))
        currency = details.get('currency', 'USD')
        
        # Apply dividend to all positions
        await self._apply_dividend_to_positions(
            action['action_id'],
            action['symbol'],
            processing_date,
            dividend_amount,
            currency
        )
        
        # Record price adjustment (for historical price series)
        await self._record_price_adjustment(
            action['action_id'],
            action['symbol'],
            processing_date,
            adjustment_factor=Decimal('1.0'),  # No split adjustment for dividends
            dividend_amount=dividend_amount,
            adjustment_type='DIVIDEND'
        )
        
        return True
    
    async def _process_stock_split(self, action: Dict[str, Any], processing_date: date) -> bool:
        """Process stock split"""
        logger.info(f"📊 Processing stock split for {action['symbol']}")
        
        details = action['action_details']
        split_ratio = Decimal(str(details['split_ratio']))  # e.g., 2.0 for 2:1 split
        
        # Apply split to all positions
        await self._apply_split_to_positions(
            action['action_id'],
            action['symbol'],
            processing_date,
            split_ratio
        )
        
        # Record price adjustment
        adjustment_factor = Decimal('1.0') / split_ratio
        await self._record_price_adjustment(
            action['action_id'],
            action['symbol'],
            processing_date,
            adjustment_factor=adjustment_factor,
            dividend_amount=Decimal('0'),
            adjustment_type='STOCK_SPLIT'
        )
        
        return True
    
    async def _process_stock_dividend(self, action: Dict[str, Any], processing_date: date) -> bool:
        """Process stock dividend"""
        logger.info(f"📈 Processing stock dividend for {action['symbol']}")
        
        details = action['action_details']
        dividend_ratio = Decimal(str(details['dividend_ratio']))  # e.g., 0.05 for 5% stock dividend
        
        # Apply stock dividend to positions
        await self._apply_stock_dividend_to_positions(
            action['action_id'],
            action['symbol'],
            processing_date,
            dividend_ratio
        )
        
        # Record price adjustment
        adjustment_factor = Decimal('1.0') / (Decimal('1.0') + dividend_ratio)
        await self._record_price_adjustment(
            action['action_id'],
            action['symbol'],
            processing_date,
            adjustment_factor=adjustment_factor,
            dividend_amount=Decimal('0'),
            adjustment_type='STOCK_DIVIDEND'
        )
        
        return True
    
    # Continuing corporate_actions/ca_processor.py

   async def _process_spin_off(self, action: Dict[str, Any], processing_date: date) -> bool:
       """Process spin-off"""
       logger.info(f"🔄 Processing spin-off for {action['symbol']}")
       
       details = action['action_details']
       new_symbol = details['new_symbol']
       distribution_ratio = Decimal(str(details['distribution_ratio']))
       new_security_price = Decimal(str(details.get('new_security_price', '0')))
       
       # Apply spin-off to positions
       await self._apply_spinoff_to_positions(
           action['action_id'],
           action['symbol'],
           new_symbol,
           processing_date,
           distribution_ratio,
           new_security_price
       )
       
       # No price adjustment for the original security in spin-offs typically
       # The market will adjust the price naturally
       
       return True
   
   async def _process_merger(self, action: Dict[str, Any], processing_date: date) -> bool:
       """Process merger/acquisition"""
       logger.info(f"🤝 Processing merger for {action['symbol']}")
       
       details = action['action_details']
       acquiring_symbol = details.get('acquiring_symbol')
       cash_amount = Decimal(str(details.get('cash_amount', '0')))
       stock_ratio = Decimal(str(details.get('stock_ratio', '0')))
       
       # Apply merger to positions
       await self._apply_merger_to_positions(
           action['action_id'],
           action['symbol'],
           acquiring_symbol,
           processing_date,
           cash_amount,
           stock_ratio
       )
       
       return True
   
   async def _process_rights_offering(self, action: Dict[str, Any], processing_date: date) -> bool:
       """Process rights offering"""
       logger.info(f"📜 Processing rights offering for {action['symbol']}")
       
       details = action['action_details']
       rights_ratio = Decimal(str(details['rights_ratio']))  # Rights per share
       subscription_price = Decimal(str(details['subscription_price']))
       
       # Create rights positions for existing shareholders
       await self._create_rights_positions(
           action['action_id'],
           action['symbol'],
           processing_date,
           rights_ratio,
           subscription_price
       )
       
       return True
   
   async def _process_special_dividend(self, action: Dict[str, Any], processing_date: date) -> bool:
       """Process special dividend"""
       logger.info(f"💎 Processing special dividend for {action['symbol']}")
       
       # Special dividends are processed similar to regular dividends
       # but may have different tax implications
       return await self._process_dividend(action, processing_date)
   
   async def _apply_dividend_to_positions(self, action_id: str, symbol: str, 
                                        processing_date: date, dividend_amount: Decimal, 
                                        currency: str):
       """Apply dividend payments to all positions"""
       async with self.db_manager.pool.acquire() as conn:
           # Get all positions for this symbol
           positions = await conn.fetch("""
               SELECT account_id, quantity, avg_cost
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity != 0
           """, symbol)
           
           for position in positions:
               account_id = position['account_id']
               quantity = Decimal(str(position['quantity']))
               
               if quantity > 0:  # Only long positions receive dividends
                   cash_amount = quantity * dividend_amount
                   
                   # Record the dividend payment
                   await conn.execute("""
                       INSERT INTO corporate_actions.position_adjustments
                       (action_id, account_id, symbol, adjustment_date, old_quantity, 
                        new_quantity, cash_adjustment, adjustment_reason)
                       VALUES ($1, $2, $3, $4, $5, $5, $6, $7)
                   """, action_id, account_id, symbol, processing_date, 
                   float(quantity), float(cash_amount), 
                   f"Dividend payment: {dividend_amount} per share")
                   
                   # Update cash balance (in practice, this would update actual positions table)
                   logger.debug(f"💰 Dividend payment: {account_id} receives {cash_amount} {currency} for {symbol}")
   
   async def _apply_split_to_positions(self, action_id: str, symbol: str, 
                                     processing_date: date, split_ratio: Decimal):
       """Apply stock split to all positions"""
       async with self.db_manager.pool.acquire() as conn:
           positions = await conn.fetch("""
               SELECT account_id, quantity, avg_cost
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity != 0
           """, symbol)
           
           for position in positions:
               account_id = position['account_id']
               old_quantity = Decimal(str(position['quantity']))
               old_avg_cost = Decimal(str(position['avg_cost']))
               
               new_quantity = old_quantity * split_ratio
               new_avg_cost = old_avg_cost / split_ratio
               
               # Record the split adjustment
               await conn.execute("""
                   INSERT INTO corporate_actions.position_adjustments
                   (action_id, account_id, symbol, adjustment_date, 
                    old_quantity, new_quantity, old_price, new_price, adjustment_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               """, action_id, account_id, symbol, processing_date,
               float(old_quantity), float(new_quantity), 
               float(old_avg_cost), float(new_avg_cost),
               f"Stock split {split_ratio}:1")
               
               # Update position (in practice, this would update actual positions table)
               logger.debug(f"📊 Split adjustment: {account_id} {symbol} {old_quantity} -> {new_quantity} shares")
   
   async def _apply_stock_dividend_to_positions(self, action_id: str, symbol: str,
                                              processing_date: date, dividend_ratio: Decimal):
       """Apply stock dividend to positions"""
       async with self.db_manager.pool.acquire() as conn:
           positions = await conn.fetch("""
               SELECT account_id, quantity, avg_cost
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity != 0
           """, symbol)
           
           for position in positions:
               account_id = position['account_id']
               old_quantity = Decimal(str(position['quantity']))
               old_avg_cost = Decimal(str(position['avg_cost']))
               
               additional_shares = old_quantity * dividend_ratio
               new_quantity = old_quantity + additional_shares
               new_avg_cost = old_avg_cost * old_quantity / new_quantity
               
               # Record the stock dividend
               await conn.execute("""
                   INSERT INTO corporate_actions.position_adjustments
                   (action_id, account_id, symbol, adjustment_date,
                    old_quantity, new_quantity, old_price, new_price, adjustment_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               """, action_id, account_id, symbol, processing_date,
               float(old_quantity), float(new_quantity),
               float(old_avg_cost), float(new_avg_cost),
               f"Stock dividend {dividend_ratio * 100}%")
   
   async def _apply_spinoff_to_positions(self, action_id: str, original_symbol: str,
                                       new_symbol: str, processing_date: date,
                                       distribution_ratio: Decimal, new_security_price: Decimal):
       """Apply spin-off to positions"""
       async with self.db_manager.pool.acquire() as conn:
           positions = await conn.fetch("""
               SELECT account_id, quantity
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity > 0
           """, original_symbol)
           
           for position in positions:
               account_id = position['account_id']
               old_quantity = Decimal(str(position['quantity']))
               
               new_shares = old_quantity * distribution_ratio
               
               # Record the spin-off
               await conn.execute("""
                   INSERT INTO corporate_actions.position_adjustments
                   (action_id, account_id, symbol, adjustment_date,
                    old_quantity, new_quantity, adjustment_reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, action_id, account_id, new_symbol, processing_date,
               0, float(new_shares),
               f"Spin-off from {original_symbol}: {distribution_ratio} shares per original share")
               
               logger.debug(f"🔄 Spin-off: {account_id} receives {new_shares} {new_symbol} from {original_symbol}")
   
   async def _apply_merger_to_positions(self, action_id: str, target_symbol: str,
                                      acquiring_symbol: str, processing_date: date,
                                      cash_amount: Decimal, stock_ratio: Decimal):
       """Apply merger to positions"""
       async with self.db_manager.pool.acquire() as conn:
           positions = await conn.fetch("""
               SELECT account_id, quantity
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity != 0
           """, target_symbol)
           
           for position in positions:
               account_id = position['account_id']
               old_quantity = Decimal(str(position['quantity']))
               
               if old_quantity > 0:  # Long position
                   total_cash = old_quantity * cash_amount
                   new_shares = old_quantity * stock_ratio if acquiring_symbol else Decimal('0')
                   
                   # Record merger adjustment
                   await conn.execute("""
                       INSERT INTO corporate_actions.position_adjustments
                       (action_id, account_id, symbol, adjustment_date,
                        old_quantity, new_quantity, cash_adjustment, adjustment_reason)
                       VALUES ($1, $2, $3, $4, $5, 0, $6, $7)
                   """, action_id, account_id, target_symbol, processing_date,
                   float(old_quantity), float(total_cash),
                   f"Merger with {acquiring_symbol or 'cash'}: {cash_amount} cash + {stock_ratio} stock ratio")
                   
                   # If stock component, create new position
                   if acquiring_symbol and new_shares > 0:
                       await conn.execute("""
                           INSERT INTO corporate_actions.position_adjustments
                           (action_id, account_id, symbol, adjustment_date,
                            old_quantity, new_quantity, adjustment_reason)
                           VALUES ($1, $2, $3, $4, 0, $5, $6)
                       """, action_id, account_id, acquiring_symbol, processing_date,
                       float(new_shares),
                       f"Merger: received from {target_symbol}")
   
   async def _create_rights_positions(self, action_id: str, symbol: str,
                                    processing_date: date, rights_ratio: Decimal,
                                    subscription_price: Decimal):
       """Create rights positions for rights offering"""
       async with self.db_manager.pool.acquire() as conn:
           positions = await conn.fetch("""
               SELECT account_id, quantity
               FROM positions.current_positions 
               WHERE symbol = $1 AND quantity > 0
           """, symbol)
           
           rights_symbol = f"{symbol}_RIGHTS"
           
           for position in positions:
               account_id = position['account_id']
               share_quantity = Decimal(str(position['quantity']))
               
               rights_quantity = share_quantity * rights_ratio
               
               # Record rights creation
               await conn.execute("""
                   INSERT INTO corporate_actions.position_adjustments
                   (action_id, account_id, symbol, adjustment_date,
                    old_quantity, new_quantity, adjustment_reason)
                   VALUES ($1, $2, $3, $4, 0, $5, $6)
               """, action_id, account_id, rights_symbol, processing_date,
               float(rights_quantity),
               f"Rights offering: {rights_ratio} rights per share, subscription price {subscription_price}")
   
   async def _record_price_adjustment(self, action_id: str, symbol: str, 
                                    adjustment_date: date, adjustment_factor: Decimal,
                                    dividend_amount: Decimal, adjustment_type: str):
       """Record price adjustment for historical data"""
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               INSERT INTO corporate_actions.price_adjustments
               (action_id, symbol, adjustment_date, adjustment_factor, 
                dividend_amount, adjustment_type)
               VALUES ($1, $2, $3, $4, $5, $6)
           """, action_id, symbol, adjustment_date, float(adjustment_factor),
           float(dividend_amount), adjustment_type)
   
   async def _mark_action_processed(self, action_id: str):
       """Mark action as successfully processed"""
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               UPDATE corporate_actions.actions 
               SET status = 'PROCESSED', processed_at = NOW(), updated_at = NOW()
               WHERE action_id = $1
           """, action_id)
   
   async def _mark_action_failed(self, action_id: str, error_message: str):
       """Mark action as failed"""
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               UPDATE corporate_actions.actions 
               SET status = 'FAILED', 
                   action_details = action_details || jsonb_build_object('error', $2),
                   updated_at = NOW()
               WHERE action_id = $1
           """, action_id, error_message)
   
   async def add_corporate_action(self, symbol: str, action_type: ActionType,
                                announcement_date: date, ex_date: date,
                                action_details: Dict[str, Any],
                                record_date: date = None, payment_date: date = None,
                                effective_date: date = None) -> str:
       """Add a new corporate action"""
       async with self.db_manager.pool.acquire() as conn:
           result = await conn.fetchrow("""
               INSERT INTO corporate_actions.actions
               (symbol, action_type, announcement_date, ex_date, record_date,
                payment_date, effective_date, action_details, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDING')
               RETURNING action_id
           """, symbol, action_type.value, announcement_date, ex_date,
           record_date, payment_date, effective_date, action_details)
           
           action_id = result['action_id']
           logger.info(f"➕ Added corporate action: {action_type.value} for {symbol} (ID: {action_id})")
           
           return str(action_id)
   
   async def get_pending_actions_summary(self) -> Dict[str, Any]:
       """Get summary of pending corporate actions"""
       async with self.db_manager.pool.acquire() as conn:
           summary = await conn.fetch("""
               SELECT 
                   action_type,
                   COUNT(*) as count,
                   MIN(ex_date) as earliest_ex_date,
                   MAX(ex_date) as latest_ex_date
               FROM corporate_actions.actions
               WHERE status = 'PENDING'
               GROUP BY action_type
               ORDER BY action_type
           """)
           
           return {
               'by_type': [dict(row) for row in summary],
               'total_pending': sum(row['count'] for row in summary)
           }


# Create some sample corporate actions for testing
async def create_sample_corporate_actions(ca_processor: CorporateActionsProcessor):
   """Create sample corporate actions for testing"""
   from datetime import date, timedelta
   
   today = date.today()
   tomorrow = today + timedelta(days=1)
   
   # Sample dividend
   await ca_processor.add_corporate_action(
       symbol="AAPL",
       action_type=ActionType.DIVIDEND,
       announcement_date=today - timedelta(days=30),
       ex_date=tomorrow,
       record_date=tomorrow + timedelta(days=2),
       payment_date=tomorrow + timedelta(days=14),
       action_details={
           "dividend_amount": "0.23",
           "currency": "USD",
           "dividend_type": "REGULAR"
       }
   )
   
   # Sample stock split
   await ca_processor.add_corporate_action(
       symbol="TSLA",
       action_type=ActionType.STOCK_SPLIT,
       announcement_date=today - timedelta(days=15),
       ex_date=tomorrow,
       action_details={
           "split_ratio": "3.0",
           "old_shares": 1,
           "new_shares": 3
       }
   )
   
   # Sample spin-off
   await ca_processor.add_corporate_action(
       symbol="IBM",
       action_type=ActionType.SPIN_OFF,
       announcement_date=today - timedelta(days=60),
       ex_date=tomorrow,
       action_details={
           "new_symbol": "KYNDRYL",
           "distribution_ratio": "1.0",
           "new_security_price": "25.50",
           "description": "Kyndryl spin-off"
       }
   )