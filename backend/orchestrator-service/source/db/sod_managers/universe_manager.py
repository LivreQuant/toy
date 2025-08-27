# db/managers/universe_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import json
from .base_manager import BaseManager

class UniverseManager(BaseManager):
    """Database manager for trading universe operations"""
    
    # =================================================================
    # UNIVERSE OPERATIONS
    # =================================================================
    
    async def get_eligible_securities(self, target_date: date) -> List[Dict[str, Any]]:
        """Get all potentially eligible securities"""
        return await self.fetch_all("""
            SELECT 
                symbol,
                security_id,
                security_name,
                sector,
                market_cap,
                avg_volume_30d,
                CASE 
                    WHEN bid_price > 0 AND ask_price > 0 
                    THEN ((ask_price - bid_price) / ((ask_price + bid_price) / 2)) * 10000
                    ELSE NULL
                END as spread_bps,
                is_active
            FROM reference_data.securities
            WHERE is_active = TRUE
        """)
    
    async def save_universe_data(self, universe_date: date, securities: List[Dict[str, Any]]):
        """Save universe data to database"""
        # Clear existing universe for the date
        await self.execute("""
            DELETE FROM universe.trading_universe WHERE universe_date = $1
        """, universe_date)
        
        # Insert new universe data
        if securities:
            insert_data = []
            for sec in securities:
                insert_data.append((
                    universe_date,
                    sec['symbol'],
                    sec.get('security_id', sec['symbol']),
                    sec.get('security_name'),
                    sec.get('sector'),
                    int(sec.get('market_cap', 0)) if sec.get('market_cap') else None,
                    int(sec.get('avg_volume_30d', 0)) if sec.get('avg_volume_30d') else None,
                    float(sec.get('spread_bps', 0)) if sec.get('spread_bps') else None,
                    sec.get('is_tradeable', True),
                    sec.get('inclusion_reason'),
                    sec.get('exclusion_reason')
                ))
            
            await self.bulk_insert(
                'universe.trading_universe',
                ['universe_date', 'symbol', 'security_id', 'security_name', 'sector',
                 'market_cap', 'avg_volume_30d', 'avg_spread_bps', 'is_tradeable',
                 'inclusion_reason', 'exclusion_reason'],
                insert_data
            )
    
    async def save_universe_stats(self, universe_date: date, stats: Dict[str, Any]):
        """Save universe statistics"""
        await self.execute("""
            INSERT INTO universe.universe_stats 
            (universe_date, total_securities, tradeable_securities, total_market_cap,
             sectors_included, avg_market_cap, avg_volume, sector_breakdown, criteria_applied)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (universe_date) 
            DO UPDATE SET
                total_securities = EXCLUDED.total_securities,
                tradeable_securities = EXCLUDED.tradeable_securities,
                total_market_cap = EXCLUDED.total_market_cap,
                sectors_included = EXCLUDED.sectors_included,
                avg_market_cap = EXCLUDED.avg_market_cap,
                avg_volume = EXCLUDED.avg_volume,
                sector_breakdown = EXCLUDED.sector_breakdown,
                criteria_applied = EXCLUDED.criteria_applied,
                created_at = NOW()
        """, 
        universe_date, 
        stats['total_securities'],
        stats['tradeable_securities'], 
        stats['total_market_cap'],
        stats['sectors_included'],
        stats.get('avg_market_cap', 0),
        stats.get('avg_volume', 0),
        json.dumps(stats.get('sector_breakdown', {})),
        json.dumps(stats['criteria_applied'])
        )
    
    async def get_universe_for_date(self, universe_date: date, 
                                  tradeable_only: bool = True) -> List[Dict[str, Any]]:
        """Get trading universe for a specific date"""
        query = """
            SELECT * FROM universe.trading_universe 
            WHERE universe_date = $1
        """
        params = [universe_date]
        
        if tradeable_only:
            query += " AND is_tradeable = TRUE"
        
        query += " ORDER BY market_cap DESC NULLS LAST"
        
        return await self.fetch_all(query, *params)
    
    async def get_universe_stats(self, universe_date: date) -> Optional[Dict[str, Any]]:
        """Get universe statistics for a date"""
        return await self.fetch_one("""
            SELECT * FROM universe.universe_stats
            WHERE universe_date = $1
        """, universe_date)
    
    async def get_universe_history(self, symbol: str, start_date: date, 
                                 end_date: date) -> List[Dict[str, Any]]:
        """Get universe inclusion history for a symbol"""
        return await self.fetch_all("""
            SELECT universe_date, is_tradeable, inclusion_reason, exclusion_reason
            FROM universe.trading_universe
            WHERE symbol = $1 AND universe_date BETWEEN $2 AND $3
            ORDER BY universe_date
        """, symbol, start_date, end_date)
    
    async def get_sectors_for_date(self, universe_date: date) -> List[Dict[str, Any]]:
        """Get sector breakdown for a universe date"""
        return await self.fetch_all("""
            SELECT 
                sector,
                COUNT(*) as security_count,
                SUM(market_cap) as total_market_cap,
                AVG(market_cap) as avg_market_cap
            FROM universe.trading_universe
            WHERE universe_date = $1 AND is_tradeable = TRUE AND sector IS NOT NULL
            GROUP BY sector
            ORDER BY total_market_cap DESC NULLS LAST
        """, universe_date)
    
    # =================================================================
    # SYMBOLOGY OPERATIONS
    # =================================================================
    
    async def add_symbol_mapping(self, primary_symbol: str, symbol_type: str,
                               symbol_value: str, data_vendor: str = None,
                               effective_date: date = None) -> Dict[str, Any]:
        """Add or update a symbol mapping"""
        if effective_date is None:
            effective_date = date.today()
        
        # Check for existing mapping
        existing = await self.fetch_one("""
            SELECT primary_symbol FROM symbology.symbol_mappings
            WHERE symbol_value = $1 AND symbol_type = $2 AND is_active = TRUE
        """, symbol_value, symbol_type)
        
        if existing and existing['primary_symbol'] != primary_symbol:
            # Conflict detected - log it
            await self.log_mapping_conflict(
                symbol_value, symbol_type,
                [existing['primary_symbol'], primary_symbol]
            )
            return {
                "success": False,
                "conflict": True,
                "existing_symbol": existing['primary_symbol'],
                "new_symbol": primary_symbol
            }
        
        # Insert or update mapping
        result = await self.execute_returning("""
            INSERT INTO symbology.symbol_mappings 
            (primary_symbol, symbol_type, symbol_value, data_vendor, effective_date, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            ON CONFLICT (primary_symbol, symbol_type, symbol_value, effective_date)
            DO UPDATE SET 
                data_vendor = EXCLUDED.data_vendor,
                is_active = TRUE,
                updated_at = NOW()
            RETURNING (xmax = 0) as inserted
        """, primary_symbol, symbol_type, symbol_value, data_vendor, effective_date)
        
        return {
            "success": True,
            "inserted": result['inserted'] if result else False,
            "conflict": False
        }
    
    async def log_mapping_conflict(self, symbol_value: str, symbol_type: str, 
                                 conflicting_symbols: List[str]):
        """Log a symbol mapping conflict"""
        await self.execute("""
            INSERT INTO symbology.mapping_conflicts
            (symbol_value, symbol_type, conflicting_symbols, conflict_date)
            VALUES ($1, $2, $3, $4)
        """, symbol_value, symbol_type, conflicting_symbols, date.today())
    
    async def get_symbol_mapping(self, symbol_value: str, symbol_type: str) -> Optional[str]:
        """Get primary symbol for a given symbol value and type"""
        result = await self.fetch_one("""
            SELECT primary_symbol FROM symbology.symbol_mappings
            WHERE symbol_value = $1 AND symbol_type = $2 AND is_active = TRUE
            ORDER BY effective_date DESC
            LIMIT 1
        """, symbol_value, symbol_type)
        
        return result['primary_symbol'] if result else None
    
    async def get_all_mappings_for_symbol(self, primary_symbol: str) -> List[Dict[str, Any]]:
        """Get all symbol mappings for a primary symbol"""
        return await self.fetch_all("""
            SELECT symbol_type, symbol_value, data_vendor, effective_date
            FROM symbology.symbol_mappings
            WHERE primary_symbol = $1 AND is_active = TRUE
            ORDER BY symbol_type, effective_date DESC
        """, primary_symbol)
    
    async def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """Get all pending symbol conflicts"""
        return await self.fetch_all("""
            SELECT * FROM symbology.mapping_conflicts
            WHERE resolution_status = 'PENDING'
            ORDER BY conflict_date
        """)
    
    async def resolve_conflict(self, conflict_id: str, resolved_symbol: str, 
                             resolution_reason: str):
        """Resolve a symbol mapping conflict"""
        await self.execute("""
            UPDATE symbology.mapping_conflicts
            SET resolution_status = 'RESOLVED',
                resolved_symbol = $2,
                resolution_reason = $3,
                resolved_date = CURRENT_DATE
            WHERE conflict_id = $1
        """, conflict_id, resolved_symbol, resolution_reason)
    
    async def get_securities_by_exchange(self, exchange: str) -> List[Dict[str, Any]]:
        """Get securities by exchange for conflict resolution"""
        return await self.fetch_all("""
            SELECT symbol, exchange FROM reference_data.securities
            WHERE exchange = $1
        """, exchange)
    
    # =================================================================
    # UNIVERSE RULES MANAGEMENT
    # =================================================================
    
    async def save_universe_rule(self, rule_name: str, rule_type: str, 
                               rule_criteria: Dict[str, Any]) -> str:
        """Save a universe rule"""
        result = await self.execute_returning("""
            INSERT INTO universe.universe_rules (rule_name, rule_type, rule_criteria)
            VALUES ($1, $2, $3)
            ON CONFLICT (rule_name)
            DO UPDATE SET 
                rule_type = EXCLUDED.rule_type,
                rule_criteria = EXCLUDED.rule_criteria,
                updated_at = NOW()
            RETURNING rule_id
        """, rule_name, rule_type, json.dumps(rule_criteria))
        
        return str(result['rule_id']) if result else None
    
    async def get_active_universe_rules(self) -> List[Dict[str, Any]]:
        """Get all active universe rules"""
        return await self.fetch_all("""
            SELECT rule_name, rule_type, rule_criteria
            FROM universe.universe_rules
            WHERE is_active = TRUE
            ORDER BY rule_name
        """)
    
    async def deactivate_universe_rule(self, rule_name: str):
        """Deactivate a universe rule"""
        await self.execute("""
            UPDATE universe.universe_rules
            SET is_active = FALSE, updated_at = NOW()
            WHERE rule_name = $1
        """, rule_name)
    
    # =================================================================
    # CLEANUP AND MAINTENANCE
    # =================================================================
    
    async def cleanup_old_universe_data(self, cutoff_date: date) -> int:
        """Clean up old universe data"""
        result = await self.execute("""
            DELETE FROM universe.trading_universe
            WHERE universe_date < $1
        """, cutoff_date)
        
        deleted_universe = int(result.split()[1]) if result and 'DELETE' in result else 0
        
        # Clean up old stats
        await self.execute("""
            DELETE FROM universe.universe_stats
            WHERE universe_date < $1
        """, cutoff_date)
        
        return deleted_universe
    
    async def get_universe_summary(self, days_back: int = 30) -> Dict[str, Any]:
        """Get universe summary statistics"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        summary = await self.fetch_one("""
            SELECT 
                COUNT(DISTINCT universe_date) as universe_dates,
                AVG(total_securities) as avg_total_securities,
                AVG(tradeable_securities) as avg_tradeable_securities,
                MAX(total_securities) as max_total_securities,
                MIN(total_securities) as min_total_securities
            FROM universe.universe_stats
            WHERE universe_date BETWEEN $1 AND $2
        """, start_date, end_date)
        
        return dict(summary) if summary else {}