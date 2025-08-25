# source/sod/universe/symbology_manager.py
import logging
from typing import Dict, List, Any, Set, Tuple
from datetime import date
import asyncio

logger = logging.getLogger(__name__)

class SymbologyManager:
    """Manages symbol mappings and cross-references"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize symbology manager"""
        await self._create_symbology_tables()
        logger.info("🔤 Symbology Manager initialized")
    
    async def _create_symbology_tables(self):
        """Create symbology tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS symbology
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS symbology.symbol_mappings (
                    primary_symbol VARCHAR(20) NOT NULL,
                    symbol_type VARCHAR(20) NOT NULL,
                    symbol_value VARCHAR(50) NOT NULL,
                    data_vendor VARCHAR(50),
                    is_active BOOLEAN DEFAULT TRUE,
                    effective_date DATE NOT NULL,
                    expiry_date DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (primary_symbol, symbol_type, symbol_value, effective_date)
                )
            """)
            
            # Index for fast lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_mappings_lookup 
                ON symbology.symbol_mappings (symbol_value, symbol_type, is_active)
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS symbology.mapping_conflicts (
                    conflict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol_value VARCHAR(50) NOT NULL,
                    symbol_type VARCHAR(20) NOT NULL,
                    conflicting_symbols TEXT[],
                    resolution_status VARCHAR(20) DEFAULT 'PENDING',
                    resolved_symbol VARCHAR(20),
                    conflict_date DATE NOT NULL,
                    resolved_date DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def update_symbol_mappings(self, mapping_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update symbol mappings from various data sources"""
        logger.info(f"🔤 Updating symbol mappings for {len(mapping_data)} symbols")
        
        try:
            conflicts_detected = []
            mappings_updated = 0
            mappings_added = 0
            
            async with self.db_manager.pool.acquire() as conn:
                for mapping in mapping_data:
                    primary_symbol = mapping['primary_symbol']
                    symbol_type = mapping['symbol_type']  # CUSIP, ISIN, SEDOL, etc.
                    symbol_value = mapping['symbol_value']
                    data_vendor = mapping.get('data_vendor', 'INTERNAL')
                    effective_date = mapping.get('effective_date', date.today())
                    
                    # Check for existing mapping
                    existing = await conn.fetchrow("""
                        SELECT primary_symbol FROM symbology.symbol_mappings
                        WHERE symbol_value = $1 AND symbol_type = $2 AND is_active = TRUE
                    """, symbol_value, symbol_type)
                    
                    if existing and existing['primary_symbol'] != primary_symbol:
                        # Conflict detected
                        conflicts_detected.append({
                            'symbol_value': symbol_value,
                            'symbol_type': symbol_type,
                            'existing_symbol': existing['primary_symbol'],
                            'new_symbol': primary_symbol
                        })
                        
                        # Log conflict
                        await self._log_mapping_conflict(
                            symbol_value, symbol_type,
                            [existing['primary_symbol'], primary_symbol]
                        )
                        continue
                    
                    # Insert or update mapping
                    result = await conn.fetchrow("""
                        INSERT INTO symbology.symbol_mappings 
                        (primary_symbol, symbol_type, symbol_value, data_vendor, effective_date, is_active)
                        VALUES ($1, $2, $3, $4, $5, TRUE)
                        ON CONFLICT (primary_symbol, symbol_type, symbol_value, effective_date)
                        DO UPDATE SET 
                            data_vendor = $4,
                            is_active = TRUE,
                            updated_at = NOW()
                        RETURNING (xmax = 0) as inserted
                    """, primary_symbol, symbol_type, symbol_value, data_vendor, effective_date)
                    
                    if result['inserted']:
                        mappings_added += 1
                    else:
                        mappings_updated += 1
            
            logger.info(f"✅ Symbol mappings updated: {mappings_added} added, {mappings_updated} updated, {len(conflicts_detected)} conflicts")
            
            return {
                "mappings_added": mappings_added,
                "mappings_updated": mappings_updated,
                "conflicts_detected": len(conflicts_detected),
                "conflicts": conflicts_detected
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update symbol mappings: {e}", exc_info=True)
            raise
    
    async def _log_mapping_conflict(self, symbol_value: str, symbol_type: str, conflicting_symbols: List[str]):
        """Log a symbol mapping conflict"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO symbology.mapping_conflicts
                (symbol_value, symbol_type, conflicting_symbols, conflict_date)
                VALUES ($1, $2, $3, $4)
            """, symbol_value, symbol_type, conflicting_symbols, date.today())
    
    async def resolve_symbol_conflicts(self) -> Dict[str, Any]:
        """Resolve pending symbol conflicts using business rules"""
        logger.info("🔧 Resolving symbol mapping conflicts")
        
        try:
            async with self.db_manager.pool.acquire() as conn:
                conflicts = await conn.fetch("""
                    SELECT * FROM symbology.mapping_conflicts
                    WHERE resolution_status = 'PENDING'
                    ORDER BY conflict_date
                """)
                
                resolved_count = 0
                for conflict in conflicts:
                    resolution = await self._resolve_conflict_logic(dict(conflict))
                    
                    if resolution:
                        await conn.execute("""
                            UPDATE symbology.mapping_conflicts
                            SET resolution_status = 'RESOLVED',
                                resolved_symbol = $1,
                                resolved_date = $2
                            WHERE conflict_id = $3
                        """, resolution['resolved_symbol'], date.today(), conflict['conflict_id'])
                        
                        # Update the mapping table
                        await conn.execute("""
                            UPDATE symbology.symbol_mappings
                            SET is_active = FALSE
                            WHERE symbol_value = $1 AND symbol_type = $2 
                              AND primary_symbol != $3
                        """, conflict['symbol_value'], conflict['symbol_type'], resolution['resolved_symbol'])
                        
                        resolved_count += 1
                
                logger.info(f"✅ Resolved {resolved_count} symbol conflicts")
                
                return {
                    "total_conflicts": len(conflicts),
                    "resolved_conflicts": resolved_count,
                    "pending_conflicts": len(conflicts) - resolved_count
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to resolve symbol conflicts: {e}", exc_info=True)
            raise
    
    async def _resolve_conflict_logic(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply business logic to resolve conflicts"""
        # This is where you'd implement your business rules
        # For now, we'll use simple rules
        
        conflicting_symbols = conflict['conflicting_symbols']
        
        # Rule 1: Prefer symbols from primary exchanges
        primary_exchanges = ['NYSE', 'NASDAQ']
        
        async with self.db_manager.pool.acquire() as conn:
            for symbol in conflicting_symbols:
                exchange = await conn.fetchrow("""
                    SELECT exchange FROM reference_data.securities
                    WHERE symbol = $1
                """, symbol)
                
                if exchange and exchange['exchange'] in primary_exchanges:
                    return {
                        'resolved_symbol': symbol,
                        'resolution_reason': f'Primary exchange: {exchange["exchange"]}'
                    }
        
        # Rule 2: Prefer the first symbol alphabetically (fallback)
        resolved_symbol = min(conflicting_symbols)
        
        return {
            'resolved_symbol': resolved_symbol,
            'resolution_reason': 'Alphabetical fallback'
        }
    
    async def get_symbol_mapping(self, symbol_value: str, symbol_type: str) -> str:
        """Get primary symbol for a given symbol value and type"""
        async with self.db_manager.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT primary_symbol FROM symbology.symbol_mappings
                WHERE symbol_value = $1 AND symbol_type = $2 AND is_active = TRUE
                ORDER BY effective_date DESC
                LIMIT 1
            """, symbol_value, symbol_type)
            
            return result['primary_symbol'] if result else None
    
    async def get_all_mappings_for_symbol(self, primary_symbol: str) -> List[Dict[str, Any]]:
        """Get all symbol mappings for a primary symbol"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol_type, symbol_value, data_vendor, effective_date
                FROM symbology.symbol_mappings
                WHERE primary_symbol = $1 AND is_active = TRUE
                ORDER BY symbol_type, effective_date DESC
            """, primary_symbol)
            
            return [dict(row) for row in rows]