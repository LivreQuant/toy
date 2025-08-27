# source/sod/reconciliation/position_reconciler.py
import logging
from typing import Dict, List, Any
from datetime import date
from decimal import Decimal
from enum import Enum
import random

logger = logging.getLogger(__name__)

class ReconciliationStatus(Enum):
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    MISSING = "missing"
    UNKNOWN = "unknown"

class PortfoliosReconciler:
    """Reconciles positions across different systems - NO DATABASE ACCESS"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Reconciliation tolerances
        self.quantity_tolerance = Decimal('0.0001')  # 0.0001 shares
        self.value_tolerance = Decimal('0.01')       # $0.01
        self.percentage_tolerance = Decimal('0.001') # 0.1%
        
    async def initialize(self):
        """Initialize position reconciler"""
        # Initialize tables through database manager ONLY
        if hasattr(self.db_manager, 'reconciliation'):
            await self.db_manager.reconciliation.initialize_tables()
        
        logger.info("⚖️ Position Reconciler initialized")
    
    async def reconcile_positions(self, recon_date: date = None) -> Dict[str, Any]:
        """Perform comprehensive position reconciliation"""
        if recon_date is None:
            recon_date = date.today()
            
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
            
            # Step 1: Get positions from primary system through database manager ONLY
            primary_positions = await self.db_manager.reconciliation.get_primary_positions(recon_date)
            logger.info(f"Retrieved {len(primary_positions)} positions from primary system")
            
            # Step 2: Get positions from external/custodian systems (simulated)
            external_positions = await self._get_external_positions(recon_date, primary_positions)
            logger.info(f"Retrieved {len(external_positions)} positions from external systems")
            
            # Step 3: Perform position matching (pure business logic)
            recon_results = self._perform_position_matching(
                primary_positions, external_positions, recon_date
            )
            
            # Step 4: Identify and categorize breaks (pure business logic)
            breaks = self._identify_reconciliation_breaks(recon_results, recon_date)
            
            # Step 5: Store results through database manager ONLY
            await self.db_manager.reconciliation.save_position_reconciliation_results(recon_results, recon_date)
            await self.db_manager.reconciliation.save_reconciliation_breaks(breaks, recon_date)
            
            # Step 6: Generate summary (pure business logic)
            summary = self._generate_reconciliation_summary(recon_results, breaks, recon_date)
            
            # Step 7: Save summary through database manager ONLY
            await self.db_manager.reconciliation.save_position_recon_summary(summary, recon_date)
            
            results.update(summary)
            
            logger.info(f"✅ Position reconciliation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Position reconciliation failed: {e}", exc_info=True)
            raise
    
    async def _get_external_positions(self, recon_date: date, primary_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get positions from external/custodian systems (simulated)"""
        # In practice, this would connect to custodian APIs, SFTP feeds, etc.
        # For simulation, we'll create positions based on primary positions with some variations
        
        external_positions = []
        
        for primary_pos in primary_positions:
            if random.random() < 0.95:  # 95% chance position exists in external system
                # Add some random variation to simulate real-world discrepancies
                quantity_factor = 1.0 + random.uniform(-0.001, 0.001)  # ±0.1% variation
                price_factor = 1.0 + random.uniform(-0.002, 0.002)     # ±0.2% variation
                
                external_positions.append({
                    'account_id': primary_pos['account_id'],
                    'symbol': primary_pos['symbol'],
                    'quantity': Decimal(str(primary_pos['quantity'])) * Decimal(str(quantity_factor)),
                    'avg_cost': Decimal(str(primary_pos['avg_cost'])) * Decimal(str(price_factor)),
                    'market_value': Decimal(str(primary_pos['market_value'])) * Decimal(str(price_factor)),
                    'last_price': Decimal(str(primary_pos['last_price'])) * Decimal(str(price_factor)),
                    'position_date': recon_date,
                    'source_system': 'CUSTODIAN'
                })
        
        # Add some positions that only exist in external system (rare)
        unique_accounts = list(set(pos['account_id'] for pos in primary_positions))
        for _ in range(random.randint(0, 3)):  # 0-3 external-only positions
            if unique_accounts:
                external_positions.append({
