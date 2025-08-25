# source/sod/reconciliation/position_reconciler.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class ReconciliationStatus(Enum):
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    MISSING = "missing"
    UNKNOWN = "unknown"

class PositionReconciler:
    """Reconciles positions across different systems and data sources"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Reconciliation tolerances
        self.quantity_tolerance = Decimal('0.0001')  # 0.0001 shares
        self.value_tolerance = Decimal('0.01')       # $0.01
        self.percentage_tolerance = Decimal('0.001') # 0.1%
        
    async def initialize(self):
        """Initialize position reconciler"""
        await self._create_reconciliation_tables()
        logger.info("⚖️ Position Reconciler initialized")
    
    async def _create_reconciliation_tables(self):
        """Create reconciliation tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS reconciliation
            """)
            
            # Position reconciliation results
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.position_recon (
                    recon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    recon_date DATE NOT NULL,
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    source_system VARCHAR(50) NOT NULL,
                    target_system VARCHAR(50) NOT NULL,
                    source_quantity DECIMAL(20,8),
                    target_quantity DECIMAL(20,8),
                    quantity_difference DECIMAL(20,8),
                    source_market_value DECIMAL(20,2),
                    target_market_value DECIMAL(20,2),
                    value_difference DECIMAL(20,2),
                    reconciliation_status VARCHAR(20) NOT NULL,
                    tolerance_breached BOOLEAN DEFAULT FALSE,
                    comments TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Reconciliation breaks (discrepancies)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.recon_breaks (
                    break_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    recon_date DATE NOT NULL,
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    break_type VARCHAR(50) NOT NULL,
                    break_description TEXT NOT NULL,
                    impact_amount DECIMAL(20,2),
                    resolution_status VARCHAR(20) DEFAULT 'OPEN',
                    assigned_to VARCHAR(100),
                    resolution_notes TEXT,
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Reconciliation summary
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.recon_summary (
                    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    recon_date DATE NOT NULL,
                    total_positions INTEGER NOT NULL,
                    matched_positions INTEGER NOT NULL,
                    discrepancy_positions INTEGER NOT NULL,
                    missing_positions INTEGER NOT NULL,
                    total_market_value DECIMAL(20,2),
                    total_discrepancy_value DECIMAL(20,2),
                    reconciliation_rate DECIMAL(8,4),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def reconcile_positions(self, recon_date: date) -> Dict[str, Any]:
        """Perform comprehensive position reconciliation"""
        logger.info(f"⚖️ Starting position reconciliation for {recon_date}")
        
        try:
            results = {
                "recon_date": str(recon_date),
                "total_positions": 0,
                "matched_positions": 0,
                "discrepancy_positions": 0,
                "missing_positions": 0,
                "breaks_identified": 0,
                "total_discrepancy_value": Decimal('0'),
                "reconciliation_rate": 0.0
            }
            
            # Step 1: Get positions from primary system (our database)
            primary_positions = await self._get_primary_positions(recon_date)
            logger.info(f"Retrieved {len(primary_positions)} positions from primary system")
            
            # Step 2: Get positions from external/custodian systems (simulated)
            external_positions = await self._get_external_positions(recon_date)
            logger.info(f"Retrieved {len(external_positions)} positions from external systems")
            
            # Step 3: Perform position matching
            recon_results = await self._perform_position_matching(
                primary_positions, external_positions, recon_date
            )
            
            # Step 4: Identify and categorize breaks
            breaks = await self._identify_reconciliation_breaks(recon_results, recon_date)
            
            # Step 5: Store reconciliation results
            await self._store_reconciliation_results(recon_results, recon_date)
            await self._store_reconciliation_breaks(breaks, recon_date)
            
            # Step 6: Generate summary
            summary = await self._generate_reconciliation_summary(recon_results, breaks, recon_date)
            
            results.update(summary)
            
            logger.info(f"✅ Position reconciliation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Position reconciliation failed: {e}", exc_info=True)
            raise
    
    async def _get_primary_positions(self, recon_date: date) -> List[Dict[str, Any]]:
        """Get positions from primary system (our database)"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    account_id,
                    symbol,
                    quantity,
                    avg_cost,
                    market_value,
                    last_price,
                    position_date
                FROM positions.current_positions
                WHERE position_date = $1 AND quantity != 0
                ORDER BY account_id, symbol
            """, recon_date)
            
            # Continuing position_reconciler.py

               positions.append({
                   'account_id': row['account_id'],
                   'symbol': row['symbol'],
                   'quantity': Decimal(str(row['quantity'])),
                   'avg_cost': Decimal(str(row['avg_cost'] or 0)),
                   'market_value': Decimal(str(row['market_value'] or 0)),
                   'last_price': Decimal(str(row['last_price'] or 0)),
                   'position_date': row['position_date'],
                   'source_system': 'PRIMARY'
               })
           
           return positions
   
   async def _get_external_positions(self, recon_date: date) -> List[Dict[str, Any]]:
       """Get positions from external/custodian systems (simulated)"""
       # In practice, this would connect to custodian APIs, SFTP feeds, etc.
       # For demo purposes, we'll simulate external positions with slight discrepancies
       
       primary_positions = await self._get_primary_positions(recon_date)
       external_positions = []
       
       import random
       random.seed(int(recon_date.strftime("%Y%m%d")))  # Deterministic for testing
       
       for pos in primary_positions:
           # Simulate external position with potential discrepancies
           external_pos = pos.copy()
           external_pos['source_system'] = 'CUSTODIAN'
           
           # 90% chance of exact match
           if random.random() < 0.9:
               external_positions.append(external_pos)
           else:
               # Introduce discrepancy
               discrepancy_type = random.choice(['quantity', 'price', 'missing'])
               
               if discrepancy_type == 'quantity':
                   # Small quantity difference
                   diff = random.uniform(-0.1, 0.1)
                   external_pos['quantity'] += Decimal(str(diff))
                   external_pos['market_value'] = external_pos['quantity'] * external_pos['last_price']
                   external_positions.append(external_pos)
                   
               elif discrepancy_type == 'price':
                   # Price difference (different pricing source)
                   price_diff = random.uniform(-0.02, 0.02)  # 2% max difference
                   new_price = external_pos['last_price'] * (1 + Decimal(str(price_diff)))
                   external_pos['last_price'] = new_price
                   external_pos['market_value'] = external_pos['quantity'] * new_price
                   external_positions.append(external_pos)
                   
               # 'missing' case: don't add to external positions
       
       # Add some positions that exist only in external system
       for _ in range(random.randint(1, 3)):
           fake_symbol = f"FAKE{random.randint(100, 999)}"
           fake_account = random.choice([p['account_id'] for p in primary_positions])
           
           external_positions.append({
               'account_id': fake_account,
               'symbol': fake_symbol,
               'quantity': Decimal(str(random.randint(100, 1000))),
               'avg_cost': Decimal(str(round(random.uniform(50, 200), 2))),
               'market_value': Decimal(str(round(random.uniform(5000, 50000), 2))),
               'last_price': Decimal(str(round(random.uniform(50, 200), 2))),
               'position_date': recon_date,
               'source_system': 'CUSTODIAN'
           })
       
       return external_positions
   
   async def _perform_position_matching(self, primary_positions: List[Dict], 
                                      external_positions: List[Dict],
                                      recon_date: date) -> List[Dict[str, Any]]:
       """Match positions between primary and external systems"""
       logger.info("🔍 Performing position matching")
       
       recon_results = []
       
       # Create lookup dictionaries
       primary_lookup = {}
       external_lookup = {}
       
       for pos in primary_positions:
           key = (pos['account_id'], pos['symbol'])
           primary_lookup[key] = pos
       
       for pos in external_positions:
           key = (pos['account_id'], pos['symbol'])
           external_lookup[key] = pos
       
       # Get all unique position keys
       all_keys = set(primary_lookup.keys()) | set(external_lookup.keys())
       
       for key in all_keys:
           account_id, symbol = key
           primary_pos = primary_lookup.get(key)
           external_pos = external_lookup.get(key)
           
           recon_result = {
               'account_id': account_id,
               'symbol': symbol,
               'recon_date': recon_date,
               'source_system': 'PRIMARY',
               'target_system': 'CUSTODIAN'
           }
           
           if primary_pos and external_pos:
               # Both positions exist - compare them
               recon_result.update({
                   'source_quantity': primary_pos['quantity'],
                   'target_quantity': external_pos['quantity'],
                   'quantity_difference': primary_pos['quantity'] - external_pos['quantity'],
                   'source_market_value': primary_pos['market_value'],
                   'target_market_value': external_pos['market_value'],
                   'value_difference': primary_pos['market_value'] - external_pos['market_value']
               })
               
               # Check if within tolerance
               status = self._determine_reconciliation_status(recon_result)
               recon_result['reconciliation_status'] = status.value
               recon_result['tolerance_breached'] = status != ReconciliationStatus.MATCHED
               
           elif primary_pos:
               # Position exists in primary but missing in external
               recon_result.update({
                   'source_quantity': primary_pos['quantity'],
                   'target_quantity': Decimal('0'),
                   'quantity_difference': primary_pos['quantity'],
                   'source_market_value': primary_pos['market_value'],
                   'target_market_value': Decimal('0'),
                   'value_difference': primary_pos['market_value'],
                   'reconciliation_status': ReconciliationStatus.MISSING.value,
                   'tolerance_breached': True,
                   'comments': 'Position missing in external system'
               })
               
           else:
               # Position exists in external but missing in primary
               recon_result.update({
                   'source_quantity': Decimal('0'),
                   'target_quantity': external_pos['quantity'],
                   'quantity_difference': -external_pos['quantity'],
                   'source_market_value': Decimal('0'),
                   'target_market_value': external_pos['market_value'],
                   'value_difference': -external_pos['market_value'],
                   'reconciliation_status': ReconciliationStatus.MISSING.value,
                   'tolerance_breached': True,
                   'comments': 'Position missing in primary system'
               })
           
           recon_results.append(recon_result)
       
       return recon_results
   
   def _determine_reconciliation_status(self, recon_result: Dict[str, Any]) -> ReconciliationStatus:
       """Determine reconciliation status based on tolerances"""
       qty_diff = abs(recon_result['quantity_difference'])
       value_diff = abs(recon_result['value_difference'])
       
       # Check quantity tolerance
       if qty_diff <= self.quantity_tolerance:
           qty_match = True
       else:
           # Check percentage tolerance
           source_qty = abs(recon_result['source_quantity'])
           if source_qty > 0:
               qty_pct_diff = qty_diff / source_qty
               qty_match = qty_pct_diff <= self.percentage_tolerance
           else:
               qty_match = False
       
       # Check value tolerance
       if value_diff <= self.value_tolerance:
           value_match = True
       else:
           # Check percentage tolerance
           source_value = abs(recon_result['source_market_value'])
           if source_value > 0:
               value_pct_diff = value_diff / source_value
               value_match = value_pct_diff <= self.percentage_tolerance
           else:
               value_match = False
       
       if qty_match and value_match:
           return ReconciliationStatus.MATCHED
       else:
           return ReconciliationStatus.DISCREPANCY
   
   async def _identify_reconciliation_breaks(self, recon_results: List[Dict], 
                                           recon_date: date) -> List[Dict[str, Any]]:
       """Identify and categorize reconciliation breaks"""
       logger.info("🚨 Identifying reconciliation breaks")
       
       breaks = []
       
       for result in recon_results:
           if result['tolerance_breached']:
               break_record = {
                   'recon_date': recon_date,
                   'account_id': result['account_id'],
                   'symbol': result['symbol'],
                   'resolution_status': 'OPEN'
               }
               
               if result['reconciliation_status'] == ReconciliationStatus.MISSING.value:
                   if result['source_quantity'] == 0:
                       # Missing in primary
                       break_record.update({
                           'break_type': 'MISSING_PRIMARY',
                           'break_description': f'Position {result["symbol"]} missing in primary system',
                           'impact_amount': float(abs(result['value_difference']))
                       })
                   else:
                       # Missing in external
                       break_record.update({
                           'break_type': 'MISSING_EXTERNAL',
                           'break_description': f'Position {result["symbol"]} missing in external system',
                           'impact_amount': float(abs(result['value_difference']))
                       })
               else:
                   # Quantity or value discrepancy
                   qty_diff = abs(result['quantity_difference'])
                   value_diff = abs(result['value_difference'])
                   
                   if qty_diff > self.quantity_tolerance:
                       break_record.update({
                           'break_type': 'QUANTITY_DISCREPANCY',
                           'break_description': f'Quantity difference of {qty_diff} shares for {result["symbol"]}',
                           'impact_amount': float(value_diff)
                       })
                   elif value_diff > self.value_tolerance:
                       break_record.update({
                           'break_type': 'VALUE_DISCREPANCY',
                           'break_description': f'Value difference of ${value_diff} for {result["symbol"]}',
                           'impact_amount': float(value_diff)
                       })
               
               breaks.append(break_record)
       
       return breaks
   
   async def _store_reconciliation_results(self, recon_results: List[Dict], recon_date: date):
       """Store reconciliation results in database"""
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing results for this date
           await conn.execute("""
               DELETE FROM reconciliation.position_recon WHERE recon_date = $1
           """, recon_date)
           
           # Insert new results
           for result in recon_results:
               await conn.execute("""
                   INSERT INTO reconciliation.position_recon
                   (recon_date, account_id, symbol, source_system, target_system,
                    source_quantity, target_quantity, quantity_difference,
                    source_market_value, target_market_value, value_difference,
                    reconciliation_status, tolerance_breached, comments)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
               """, 
               recon_date, result['account_id'], result['symbol'],
               result['source_system'], result['target_system'],
               float(result['source_quantity']), float(result['target_quantity']),
               float(result['quantity_difference']), float(result['source_market_value']),
               float(result['target_market_value']), float(result['value_difference']),
               result['reconciliation_status'], result['tolerance_breached'],
               result.get('comments'))
   
   async def _store_reconciliation_breaks(self, breaks: List[Dict], recon_date: date):
       """Store reconciliation breaks in database"""
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing breaks for this date
           await conn.execute("""
               DELETE FROM reconciliation.recon_breaks WHERE recon_date = $1
           """, recon_date)
           
           # Insert new breaks
           for break_record in breaks:
               await conn.execute("""
                   INSERT INTO reconciliation.recon_breaks
                   (recon_date, account_id, symbol, break_type, break_description,
                    impact_amount, resolution_status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """,
               break_record['recon_date'], break_record['account_id'], 
               break_record['symbol'], break_record['break_type'],
               break_record['break_description'], break_record['impact_amount'],
               break_record['resolution_status'])
   
   async def _generate_reconciliation_summary(self, recon_results: List[Dict], 
                                            breaks: List[Dict], recon_date: date) -> Dict[str, Any]:
       """Generate reconciliation summary statistics"""
       total_positions = len(recon_results)
       matched_positions = len([r for r in recon_results if r['reconciliation_status'] == 'matched'])
       discrepancy_positions = len([r for r in recon_results if r['reconciliation_status'] == 'discrepancy'])
       missing_positions = len([r for r in recon_results if r['reconciliation_status'] == 'missing'])
       
       total_market_value = sum(abs(r['source_market_value']) for r in recon_results)
       total_discrepancy_value = sum(abs(r['value_difference']) for r in recon_results if r['tolerance_breached'])
       
       reconciliation_rate = (matched_positions / total_positions * 100) if total_positions > 0 else 0
       
       summary = {
           'total_positions': total_positions,
           'matched_positions': matched_positions,
           'discrepancy_positions': discrepancy_positions,
           'missing_positions': missing_positions,
           'breaks_identified': len(breaks),
           'total_market_value': float(total_market_value),
           'total_discrepancy_value': float(total_discrepancy_value),
           'reconciliation_rate': round(reconciliation_rate, 2)
       }
       
       # Store summary
       async with self.db_manager.pool.acquire() as conn:
           await conn.execute("""
               INSERT INTO reconciliation.recon_summary
               (recon_date, total_positions, matched_positions, discrepancy_positions,
                missing_positions, total_market_value, total_discrepancy_value, reconciliation_rate)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           """, recon_date, total_positions, matched_positions, discrepancy_positions,
           missing_positions, float(total_market_value), float(total_discrepancy_value),
           reconciliation_rate)
       
       return summary
   
   async def get_reconciliation_summary(self, recon_date: date) -> Dict[str, Any]:
       """Get reconciliation summary for a specific date"""
       async with self.db_manager.pool.acquire() as conn:
           # Overall summary
           summary = await conn.fetchrow("""
               SELECT * FROM reconciliation.recon_summary
               WHERE recon_date = $1
           """, recon_date)
           
           # Break details
           breaks = await conn.fetch("""
               SELECT 
                   break_type,
                   COUNT(*) as count,
                   SUM(impact_amount) as total_impact,
                   AVG(impact_amount) as avg_impact
               FROM reconciliation.recon_breaks
               WHERE recon_date = $1
               GROUP BY break_type
               ORDER BY total_impact DESC
           """, recon_date)
           
           # Top discrepancies
           top_discrepancies = await conn.fetch("""
               SELECT 
                   account_id,
                   symbol,
                   quantity_difference,
                   value_difference,
                   reconciliation_status
               FROM reconciliation.position_recon
               WHERE recon_date = $1 AND tolerance_breached = TRUE
               ORDER BY ABS(value_difference) DESC
               LIMIT 10
           """, recon_date)
           
           return {
               "recon_date": str(recon_date),
               "summary": dict(summary) if summary else {},
               "break_analysis": [dict(row) for row in breaks],
               "top_discrepancies": [dict(row) for row in top_discrepancies]
           }
   
   async def resolve_reconciliation_break(self, break_id: str, resolution_notes: str,
                                        assigned_to: str = None) -> Dict[str, Any]:
       """Mark a reconciliation break as resolved"""
       async with self.db_manager.pool.acquire() as conn:
           # Update break record
           result = await conn.fetchrow("""
               UPDATE reconciliation.recon_breaks
               SET resolution_status = 'RESOLVED',
                   resolution_notes = $2,
                   assigned_to = $3,
                   resolved_at = NOW()
               WHERE break_id = $1
               RETURNING *
           """, break_id, resolution_notes, assigned_to)
           
           if result:
               return {
                   "success": True,
                   "break_id": break_id,
                   "resolution_notes": resolution_notes,
                   "resolved_at": result['resolved_at'].isoformat()
               }
           else:
               return {"success": False, "error": "Break not found"}
   
   async def get_open_breaks(self, account_id: str = None) -> List[Dict[str, Any]]:
       """Get all open reconciliation breaks"""
       async with self.db_manager.pool.acquire() as conn:
           where_clause = "WHERE resolution_status = 'OPEN'"
           params = []
           
           if account_id:
               where_clause += " AND account_id = $1"
               params.append(account_id)
           
           breaks = await conn.fetch(f"""
               SELECT * FROM reconciliation.recon_breaks
               {where_clause}
               ORDER BY impact_amount DESC, created_at DESC
           """, *params)
           
           return [dict(row) for row in breaks]