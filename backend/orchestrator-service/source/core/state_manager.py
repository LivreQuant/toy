# source/core/state_manager.py
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum
import json
import pytz

logger = logging.getLogger(__name__)

class StateManager:
    """Manages system state persistence and recovery with proper UTC handling"""
    
    def __init__(self):
        self.db_manager = None
        self.market_tz = pytz.timezone('America/New_York')
        
        # State tracking (all in UTC)
        self.last_sod_time: Optional[datetime] = None
        self.last_eod_time: Optional[datetime] = None
        self.current_state_data: Dict[str, Any] = {}
        
    async def initialize(self, db_manager):
        """Initialize state manager with database connection"""
        self.db_manager = db_manager
        await self._create_state_tables()
        logger.info("🗄️ State manager initialized")
    
    async def _create_state_tables(self):
        """Create state management tables if they don't exist"""
        async with self.db_manager.pool.acquire() as conn:
            # Create schema if it doesn't exist
            await conn.execute("CREATE SCHEMA IF NOT EXISTS orchestrator")
            
            # System state table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator.system_state (
                    id SERIAL PRIMARY KEY,
                    state_key VARCHAR(50) NOT NULL UNIQUE,
                    state_value JSONB,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Operations log table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator.operations_log (
                    id SERIAL PRIMARY KEY,
                    operation_type VARCHAR(50) NOT NULL,
                    operation_date DATE NOT NULL,
                    start_time TIMESTAMP WITH TIME ZONE,
                    end_time TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(20) NOT NULL,
                    details JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
        logger.info("✅ State tables created/verified")
    
    async def load_current_state(self) -> Dict[str, Any]:
        """Load current system state from database and return recovery info"""
        try:
            async with self.db_manager.pool.acquire() as conn:
                # Load last SOD/EOD times (stored in UTC)
                sod_result = await conn.fetchrow("""
                    SELECT state_value->>'timestamp' as timestamp
                    FROM orchestrator.system_state 
                    WHERE state_key = 'last_sod'
                """)
                
                eod_result = await conn.fetchrow("""
                    SELECT state_value->>'timestamp' as timestamp
                    FROM orchestrator.system_state 
                    WHERE state_key = 'last_eod'
                """)
                
                if sod_result and sod_result['timestamp']:
                    self.last_sod_time = datetime.fromisoformat(sod_result['timestamp'])
                    
                if eod_result and eod_result['timestamp']:
                    self.last_eod_time = datetime.fromisoformat(eod_result['timestamp'])
                    
                # Determine current state based on what happened today (in ET business date)
                now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
                now_et = now_utc.astimezone(self.market_tz)
                today_et = now_et.date()
                
                recovery_info = self._determine_recovery_state(today_et, now_utc)
                
                logger.info(f"📊 State loaded - Last SOD: {self.last_sod_time}, Last EOD: {self.last_eod_time}")
                logger.info(f"🔄 Recovery info: {recovery_info}")
                
                return recovery_info
                
        except Exception as e:
            logger.error(f"❌ Failed to load current state: {e}", exc_info=True)
            return {"sod_complete": False, "eod_complete": False}
    
    def _determine_recovery_state(self, today_et: date, now_utc: datetime) -> Dict[str, Any]:
        """Determine what state we should be in based on completed operations"""
        recovery_info = {
            "sod_complete": False,
            "eod_complete": False,
            "should_be_trading": False,
            "should_be_idle": False
        }
        
        # Check if SOD ran today
        if (self.last_sod_time and 
            self.last_sod_time.astimezone(self.market_tz).date() == today_et):
            recovery_info["sod_complete"] = True
            recovery_info["should_be_trading"] = True
            logger.info(f"✅ SOD completed today at {self.last_sod_time}")
        
        # Check if EOD ran today  
        if (self.last_eod_time and 
            self.last_eod_time.astimezone(self.market_tz).date() == today_et):
            recovery_info["eod_complete"] = True
            recovery_info["should_be_idle"] = True
            recovery_info["should_be_trading"] = False  # EOD overrides SOD
            logger.info(f"✅ EOD completed today at {self.last_eod_time}")
            
        return recovery_info
    
    async def save_current_state(self, current_state):
        """Save current system state (in UTC)"""
        try:
            state_data = {
                "state": current_state.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestrator.system_state (state_key, state_value, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (state_key) 
                    DO UPDATE SET state_value = $2, updated_at = NOW()
                """, "current_state", json.dumps(state_data))
                
            logger.debug(f"💾 Current state saved: {current_state.value}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save current state: {e}", exc_info=True)
    
    async def save_operation_log(self, operation_type: str, status: str, 
                               start_time: datetime, end_time: datetime = None,
                               details: Dict[str, Any] = None):
        """Log operation execution (all times in UTC, but use ET business date)"""
        try:
            # Use ET business date for operation_date
            et_date = start_time.astimezone(self.market_tz).date()
            
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestrator.operations_log 
                    (operation_type, operation_date, start_time, end_time, status, details)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, operation_type, et_date, start_time, end_time, status, 
                json.dumps(details) if details else None)
                
            logger.debug(f"📝 Operation logged: {operation_type} - {status} (ET date: {et_date})")
            
        except Exception as e:
            logger.error(f"❌ Failed to save operation log: {e}", exc_info=True)
    
    async def save_sod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save SOD completion timestamp (in UTC)"""
        try:
            self.last_sod_time = completion_time
            
            state_data = {
                "timestamp": completion_time.isoformat(),
                "details": details
            }
            
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestrator.system_state (state_key, state_value, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (state_key) 
                    DO UPDATE SET state_value = $2, updated_at = NOW()
                """, "last_sod", json.dumps(state_data))
                
            et_time = completion_time.astimezone(self.market_tz)
            logger.info(f"✅ SOD completion saved: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save SOD completion: {e}", exc_info=True)
    
    async def save_eod_completion(self, completion_time: datetime, details: Dict[str, Any] = None):
        """Save EOD completion timestamp (in UTC)"""
        try:
            self.last_eod_time = completion_time
            
            state_data = {
                "timestamp": completion_time.isoformat(),
                "details": details
            }
            
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestrator.system_state (state_key, state_value, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (state_key) 
                    DO UPDATE SET state_value = $2, updated_at = NOW()
                """, "last_eod", json.dumps(state_data))
                
            et_time = completion_time.astimezone(self.market_tz)
            logger.info(f"✅ EOD completion saved: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save EOD completion: {e}", exc_info=True)
    
    async def get_recent_operations(self, operation_type: str = None, limit: int = 10):
        """Get recent operation history"""
        try:
            async with self.db_manager.pool.acquire() as conn:
                if operation_type:
                    rows = await conn.fetch("""
                        SELECT * FROM orchestrator.operations_log
                        WHERE operation_type = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, operation_type, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM orchestrator.operations_log
                        ORDER BY created_at DESC
                        LIMIT $1
                    """, limit)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get recent operations: {e}", exc_info=True)
            return []
    
    async def save_error_state(self, error_message: str):
        """Save error state information"""
        try:
            error_data = {
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.db_manager.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestrator.system_state (state_key, state_value, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (state_key) 
                    DO UPDATE SET state_value = $2, updated_at = NOW()
                """, "last_error", json.dumps(error_data))
                
            logger.error(f"💾 Error state saved: {error_message}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save error state: {e}", exc_info=True)