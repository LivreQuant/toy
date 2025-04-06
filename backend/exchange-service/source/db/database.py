# In exchange-service/source/db/database.py
import asyncpg
import logging
import os
import asyncio

logger = logging.getLogger('database')

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_host = os.environ.get('DB_HOST', 'postgres')
        self.db_port = int(os.environ.get('DB_PORT', '5432'))
        self.db_name = os.environ.get('DB_NAME', 'opentp')
        self.db_user = os.environ.get('DB_USER', 'opentp')
        self.db_password = os.environ.get('DB_PASSWORD', 'samaral')
        self._conn_lock = asyncio.Lock()

    async def connect(self):
        """Connect to the database"""
        async with self._conn_lock:
            if self.pool is not None:
                return

            try:
                self.pool = await asyncpg.create_pool(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name,
                    min_size=1,
                    max_size=5
                )
                logger.info("Connected to database")
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")

    async def update_simulator_stopped(self, session_id: str, simulator_id: str, reason: str = "Self-terminated"):
        """
        Update simulator status to STOPPED and clear from session
        
        Args:
            session_id: Session ID
            simulator_id: Simulator ID
            reason: Reason for stopping
        """
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                # Update simulator status
                await conn.execute('''
                    UPDATE simulator.instances
                    SET status = 'STOPPED'
                    WHERE simulator_id = $1
                ''', simulator_id)
                
                # Update session metadata
                await conn.execute('''
                    UPDATE session.session_metadata
                    SET metadata = jsonb_set(
                        jsonb_set(
                            metadata,
                            '{simulator_status}',
                            '"STOPPED"'
                        ),
                        '{termination_reason}',
                        $1
                    )
                    WHERE session_id = $2
                ''', f'"{reason}"', session_id)
                
                logger.info(f"Updated database: Marked simulator {simulator_id} as STOPPED")
                return True
        except Exception as e:
            logger.error(f"Error updating simulator status: {e}")
            return False