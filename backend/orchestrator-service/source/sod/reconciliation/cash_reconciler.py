# source/sod/reconciliation/cash_reconciler.py
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class CashReconciler:
    """Reconciles cash balances across different systems"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Cash reconciliation tolerances
        self.cash_tolerance = Decimal('0.01')  # $0.01 tolerance
        
    async def initialize(self):
        """Initialize cash reconciler"""
        await self._create_cash_tables()
        logger.info("💰 Cash Reconciler initialized")
    
    async def _create_cash_tables(self):
        """Create cash reconciliation tables"""
        async with self.db_manager.pool.acquire() as conn:
            # Cash balances table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.cash_balances (
                    balance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    balance_date DATE NOT NULL,
                    account_id VARCHAR(50) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    balance_type VARCHAR(50) NOT NULL, -- SETTLED, PENDING, AVAILABLE
                    balance_amount DECIMAL(20,2) NOT NULL,
                    source_system VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(balance_date, account_id, currency, balance_type, source_system)
                )
            """)
            
            # Cash movements table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.cash_movements (
                    movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    movement_date DATE NOT NULL,
                    account_id VARCHAR(50) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    movement_type VARCHAR(50) NOT NULL, -- TRADE, DIVIDEND, FEE, TRANSFER, etc.
                    movement_amount DECIMAL(20,2) NOT NULL,
                    reference_id VARCHAR(100),
                    description TEXT,
                    source_system VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Cash reconciliation results
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation.cash_recon (
                    recon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    recon_date DATE NOT NULL,
                    account_id VARCHAR(50) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    balance_type VARCHAR(50) NOT NULL,
                    source_balance DECIMAL(20,2),
                    target_balance DECIMAL(20,2),
                    balance_difference DECIMAL(20,2),
                    reconciliation_status VARCHAR(20) NOT NULL,
                    tolerance_breached BOOLEAN DEFAULT FALSE,
                    comments TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def reconcile_cash_balances(self, recon_date: date) -> Dict[str, Any]:
        """Reconcile cash balances for all accounts"""
        logger.info(f"💰 Reconciling cash balances for {recon_date}")
        
        try:
            results = {
                "recon_date": str(recon_date),
                "accounts_reconciled": 0,
                "balances_matched": 0,
                "balances_discrepancy": 0,
                "total_cash_discrepancy": Decimal('0'),
                "by_currency": {}
            }
            
            # Step 1: Calculate internal cash balances
            internal_balances = await self._calculate_internal_cash_balances(recon_date)
            logger.info(f"Calculated {len(internal_balances)} internal cash balances")
            
            # Step 2: Get external cash balances (from custodians, banks, etc.)
            external_balances = await self._get_external_cash_balances(recon_date)
            logger.info(f"Retrieved {len(external_balances)} external cash balances")
            
            # Step 3: Store balances
            await self._store_cash_balances(internal_balances, 'INTERNAL', recon_date)
            await self._store_cash_balances(external_balances, 'EXTERNAL', recon_date)
            
            # Step 4: Perform reconciliation
            recon_results = await self._perform_cash_reconciliation(
                internal_balances, external_balances, recon_date
            )
            
            # Step 5: Store reconciliation results
            await self._store_cash_reconciliation_results(recon_results, recon_date)
            
            # Step 6: Generate summary
            summary = await self._generate_cash_reconciliation_summary(recon_results)
            results.update(summary)
            
            logger.info(f"✅ Cash reconciliation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Cash reconciliation failed: {e}", exc_info=True)
            raise
    
    async def _calculate_internal_cash_balances(self, balance_date: date) -> List[Dict[str, Any]]:
        """Calculate cash balances from internal trade and position data"""
        balances = []
        
        # Get all unique accounts
        async with self.db_manager.pool.acquire() as conn:
            accounts = await conn.fetch("""
                SELECT DISTINCT account_id FROM positions.current_positions
                WHERE position_date = $1
            """, balance_date)
            
            for account in accounts:
                account_id = account['account_id']
                
                # Calculate settled cash balance
                settled_balance = await self._calculate_settled_cash(account_id, balance_date)
                
                # Calculate pending cash (unsettled trades)
                pending_balance = await self._calculate_pending_cash(account_id, balance_date)
                
                # Available cash = settled - pending commitments
                available_balance = settled_balance - abs(pending_balance) if pending_balance < 0 else settled_balance + pending_balance
                
                # Add balances for different types
                for balance_type, amount in [
                    ('SETTLED', settled_balance),
                    ('PENDING', pending_balance),
                    ('AVAILABLE', available_balance)
                ]:
                    balances.append({
                        'account_id': account_id,
                        'currency': 'USD',  # Assume USD for now
                        'balance_type': balance_type,
                        'balance_amount': amount,
                        'balance_date': balance_date
                    })
        
        return balances
    
    async def _calculate_settled_cash(self, account_id: str, balance_date: date) -> Decimal:
        """Calculate settled cash balance from trades and dividends"""
        async with self.db_manager.pool.acquire() as conn:
            # Start with beginning balance (simulated)
            beginning_balance = Decimal('100000')  # $100k starting cash
            
            # Add cash from settled sells
            sell_proceeds = await conn.fetchrow("""
                SELECT COALESCE(SUM(net_amount), 0) as total
                FROM settlement.trades
                WHERE account_id = $1 
                  AND settlement_date <= $2
                  AND side = 'SELL'
                  AND settlement_status = 'SETTLED'
            """, account_id, balance_date)
            
            # Subtract cash from settled buys
            buy_costs = await conn.fetchrow("""
                SELECT COALESCE(SUM(net_amount), 0) as total
                FROM settlement.trades
                WHERE account_id = $1 
                  AND settlement_date <= $2
                  AND side = 'BUY'
                  AND settlement_status = 'SETTLED'
            """, account_id, balance_date)
            
            # Add dividend payments (simulate)
            dividend_payments = Decimal('1000')  # Simulated dividend income
            
            # Subtract fees and expenses (simulate)
            fees_expenses = Decimal('50')  # Simulated fees
            
            settled_cash = (beginning_balance + 
                          Decimal(str(sell_proceeds['total'])) - 
                          Decimal(str(buy_costs['total'])) + 
                          dividend_payments - 
                          fees_expenses)
            
            return settled_cash
    
    async def _calculate_pending_cash(self, account_id: str, balance_date: date) -> Decimal:
        """Calculate pending cash from unsettled trades"""
        async with self.db_manager.pool.acquire() as conn:
            # Pending settlements (trades executed but not settled)
            pending_sells = await conn.fetchrow("""
                SELECT COALESCE(SUM(net_amount), 0) as total
                FROM settlement.trades
                WHERE account_id = $1 
                  AND trade_date <= $2
                  AND settlement_status IN ('PENDING', 'MATCHED')
                  AND side = 'SELL'
            """, account_id, balance_date)
            
            pending_buys = await conn.fetchrow("""
                SELECT COALESCE(SUM(net_amount), 0) as total
                FROM settlement.trades
                WHERE account_id = $1 
                  AND trade_date <= $2
                  AND settlement_status IN ('PENDING', 'MATCHED')
                  AND side = 'BUY'
            """, account_id, balance_date)
            
            # Net pending = pending sells - pending buys
            pending_cash = (Decimal(str(pending_sells['total'])) - 
                           Decimal(str(pending_buys['total'])))
            
            return pending_cash
    
    async def _get_external_cash_balances(self, balance_date: date) -> List[Dict[str, Any]]:
        """Get cash balances from external systems (simulated)"""
        # In practice, this would connect to custodian APIs, bank APIs, etc.
        # For demo, we'll simulate external balances with slight differences
        
        internal_balances = await self._calculate_internal_cash_balances(balance_date)
        external_balances = []
        
        import random
        random.seed(int(balance_date.strftime("%Y%m%d")))
        
        for balance in internal_balances:
            external_balance = balance.copy()
            
            # 95% chance of exact match
            if random.random() < 0.95:
                external_balances.append(external_balance)
            else:
                # Introduce small discrepancy
                discrepancy = Decimal(str(round(random.uniform(-100, 100), 2)))
                external_balance['balance_amount'] += discrepancy
                external_balances.append(external_balance)
        
        # Add some balances that might exist only externally (money market, etc.)
        for account_id in set(b['account_id'] for b in internal_balances):
            if random.random() < 0.1:  # 10% chance
                external_balances.append({
                    'account_id': account_id,
                    'currency': 'USD',
                    'balance_type': 'MONEY_MARKET',
                    'balance_amount': Decimal(str(round(random.uniform(1000, 10000), 2))),
                    'balance_date': balance_date
                })
        
        return external_balances
    
    async def _store_cash_balances(self, balances: List[Dict], source_system: str, balance_date: date):
        """Store cash balances in database"""
        async with self.db_manager.pool.acquire() as conn:
            # Clear existing balances for this date and source
            await conn.execute("""
                DELETE FROM reconciliation.cash_balances 
                WHERE balance_date = $1 AND source_system = $2
            """, balance_date, source_system)
            
            # Insert new balances
            for balance in balances:
                await conn.execute("""
                    INSERT INTO reconciliation.cash_balances
                    (balance_date, account_id, currency, balance_type, balance_amount, source_system)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, balance_date, balance['account_id'], balance['currency'],
                balance['balance_type'], float(balance['balance_amount']), source_system)
    
    async def _perform_cash_reconciliation(self, internal_balances: List[Dict],
                                         external_balances: List[Dict],
                                         recon_date: date) -> List[Dict[str, Any]]:
        """Perform cash balance reconciliation"""
        logger.info("💸 Performing cash reconciliation")
        
        recon_results = []
        
        # Create lookup dictionaries
        internal_lookup = {}
        external_lookup = {}
        
        for balance in internal_balances:
            key = (balance['account_id'], balance['currency'], balance['balance_type'])
            internal_lookup[key] = balance
        
        # Continuing cash_reconciler.py
        for balance in external_balances:
            key = (balance['account_id'], balance['currency'], balance['balance_type'])
            external_lookup[key] = balance
        
        # Get all unique keys
        all_keys = set(internal_lookup.keys()) | set(external_lookup.keys())
        
        for key in all_keys:
            account_id, currency, balance_type = key
            internal_balance = internal_lookup.get(key)
            external_balance = external_lookup.get(key)
            
            recon_result = {
                'account_id': account_id,
                'currency': currency,
                'balance_type': balance_type,
                'recon_date': recon_date
            }
            
            if internal_balance and external_balance:
                # Both balances exist - compare them
                internal_amount = internal_balance['balance_amount']
                external_amount = external_balance['balance_amount']
                difference = internal_amount - external_amount
                
                recon_result.update({
                    'source_balance': internal_amount,
                    'target_balance': external_amount,
                    'balance_difference': difference
                })
                
                # Check tolerance
                if abs(difference) <= self.cash_tolerance:
                    recon_result['reconciliation_status'] = 'MATCHED'
                    recon_result['tolerance_breached'] = False
                else:
                    recon_result['reconciliation_status'] = 'DISCREPANCY'
                    recon_result['tolerance_breached'] = True
                    recon_result['comments'] = f'Balance difference of ${difference}'
                    
            elif internal_balance:
                # Balance exists internally but missing externally
                recon_result.update({
                    'source_balance': internal_balance['balance_amount'],
                    'target_balance': Decimal('0'),
                    'balance_difference': internal_balance['balance_amount'],
                    'reconciliation_status': 'MISSING_EXTERNAL',
                    'tolerance_breached': True,
                    'comments': 'Balance missing in external system'
                })
                
            else:
                # Balance exists externally but missing internally
                recon_result.update({
                    'source_balance': Decimal('0'),
                    'target_balance': external_balance['balance_amount'],
                    'balance_difference': -external_balance['balance_amount'],
                    'reconciliation_status': 'MISSING_INTERNAL',
                    'tolerance_breached': True,
                    'comments': 'Balance missing in internal system'
                })
            
            recon_results.append(recon_result)
        
        return recon_results
    
    async def _store_cash_reconciliation_results(self, recon_results: List[Dict], recon_date: date):
        """Store cash reconciliation results"""
        async with self.db_manager.pool.acquire() as conn:
            # Clear existing results
            await conn.execute("""
                DELETE FROM reconciliation.cash_recon WHERE recon_date = $1
            """, recon_date)
            
            # Insert new results
            for result in recon_results:
                await conn.execute("""
                    INSERT INTO reconciliation.cash_recon
                    (recon_date, account_id, currency, balance_type, source_balance,
                        target_balance, balance_difference, reconciliation_status,
                        tolerance_breached, comments)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, recon_date, result['account_id'], result['currency'],
                result['balance_type'], float(result['source_balance']),
                float(result['target_balance']), float(result['balance_difference']),
                result['reconciliation_status'], result['tolerance_breached'],
                result.get('comments'))
    
    async def _generate_cash_reconciliation_summary(self, recon_results: List[Dict]) -> Dict[str, Any]:
        """Generate cash reconciliation summary"""
        total_balances = len(recon_results)
        matched_balances = len([r for r in recon_results if r['reconciliation_status'] == 'MATCHED'])
        discrepancy_balances = len([r for r in recon_results if r['tolerance_breached']])
        
        total_discrepancy = sum(abs(r['balance_difference']) for r in recon_results if r['tolerance_breached'])
        
        # By currency breakdown
        by_currency = {}
        for result in recon_results:
            currency = result['currency']
            if currency not in by_currency:
                by_currency[currency] = {
                    'total_balances': 0,
                    'matched_balances': 0,
                    'total_discrepancy': Decimal('0')
                }
            
            by_currency[currency]['total_balances'] += 1
            if result['reconciliation_status'] == 'MATCHED':
                by_currency[currency]['matched_balances'] += 1
            if result['tolerance_breached']:
                by_currency[currency]['total_discrepancy'] += abs(result['balance_difference'])
        
        return {
            'accounts_reconciled': len(set(r['account_id'] for r in recon_results)),
            'balances_matched': matched_balances,
            'balances_discrepancy': discrepancy_balances,
            'total_cash_discrepancy': float(total_discrepancy),
            'by_currency': {k: {
                'total_balances': v['total_balances'],
                'matched_balances': v['matched_balances'],
                'total_discrepancy': float(v['total_discrepancy'])
            } for k, v in by_currency.items()}
        }
    
    async def record_cash_movement(self, account_id: str, movement_date: date,
                                    currency: str, movement_type: str, amount: Decimal,
                                    reference_id: str = None, description: str = None) -> str:
        """Record a cash movement"""
        async with self.db_manager.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO reconciliation.cash_movements
                (movement_date, account_id, currency, movement_type, movement_amount,
                    reference_id, description, source_system)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING movement_id
            """, movement_date, account_id, currency, movement_type, float(amount),
            reference_id, description, 'INTERNAL')
            
            return str(result['movement_id'])
    
    async def get_cash_reconciliation_summary(self, recon_date: date) -> Dict[str, Any]:
        """Get cash reconciliation summary for a date"""
        async with self.db_manager.pool.acquire() as conn:
            # Overall statistics
            overall = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_reconciliations,
                    COUNT(CASE WHEN reconciliation_status = 'MATCHED' THEN 1 END) as matched,
                    COUNT(CASE WHEN tolerance_breached THEN 1 END) as discrepancies,
                    SUM(ABS(balance_difference)) as total_discrepancy_amount
                FROM reconciliation.cash_recon
                WHERE recon_date = $1
            """, recon_date)
            
            # By account breakdown
            by_account = await conn.fetch("""
                SELECT 
                    account_id,
                    currency,
                    COUNT(*) as balance_types,
                    SUM(ABS(balance_difference)) as account_discrepancy
                FROM reconciliation.cash_recon
                WHERE recon_date = $1
                GROUP BY account_id, currency
                ORDER BY account_discrepancy DESC
            """, recon_date)
            
            # Largest discrepancies
            top_discrepancies = await conn.fetch("""
                SELECT 
                    account_id,
                    currency,
                    balance_type,
                    source_balance,
                    target_balance,
                    balance_difference,
                    comments
                FROM reconciliation.cash_recon
                WHERE recon_date = $1 AND tolerance_breached = TRUE
                ORDER BY ABS(balance_difference) DESC
                LIMIT 10
            """, recon_date)
            
            return {
                "recon_date": str(recon_date),
                "overall_statistics": dict(overall) if overall else {},
                "by_account": [dict(row) for row in by_account],
                "top_discrepancies": [dict(row) for row in top_discrepancies]
            }
    
    async def get_cash_movements(self, account_id: str = None, start_date: date = None,
                                end_date: date = None, movement_type: str = None) -> List[Dict[str, Any]]:
        """Get cash movements with optional filters"""
        async with self.db_manager.pool.acquire() as conn:
            where_conditions = []
            params = []
            
            if account_id:
                where_conditions.append(f"account_id = ${len(params) + 1}")
                params.append(account_id)
            
            if start_date:
                where_conditions.append(f"movement_date >= ${len(params) + 1}")
                params.append(start_date)
            
            if end_date:
                where_conditions.append(f"movement_date <= ${len(params) + 1}")
                params.append(end_date)
            
            if movement_type:
                where_conditions.append(f"movement_type = ${len(params) + 1}")
                params.append(movement_type)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            movements = await conn.fetch(f"""
                SELECT * FROM reconciliation.cash_movements
                WHERE {where_clause}
                ORDER BY movement_date DESC, created_at DESC
                LIMIT 1000
            """, *params)
            
            return [dict(row) for row in movements]