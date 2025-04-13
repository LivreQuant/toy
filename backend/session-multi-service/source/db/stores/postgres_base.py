# data_access/stores/postgres/postgres_base.py
"""
Base PostgreSQL connection management and generic repository implementation.
"""
import logging
import asyncio
import asyncpg
import json
import time
from typing import Optional, Dict, Any, List, TypeVar, Generic, Tuple, Type

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_db_error, track_db_operation, TimedOperation

logger = logging.getLogger(__name__)

# Generic type for entity models
T = TypeVar('T')


class PostgresBase:
    """Base PostgreSQL connection handler"""

    def __init__(self, db_config=None):
        """Initialize PostgreSQL base connection"""
        self.pool: Optional[asyncpg.Pool] = None
        self.db_config = db_config or config.db
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("postgres_base")

    async def connect(self):
        """Connect to the PostgreSQL database"""
        with optional_trace_span(self.tracer, "pg_connect") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.name", self.db_config.database)
            span.set_attribute("db.host", self.db_config.host)

            async with self._conn_lock:
                if self.pool is not None:
                    return

                max_retries = 5
                retry_count = 0
                retry_delay = 1.0

                while retry_count < max_retries:
                    try:
                        self.pool = await asyncpg.create_pool(
                            host=self.db_config.host,
                            port=self.db_config.port,
                            user=self.db_config.user,
                            password=self.db_config.password,
                            database=self.db_config.database,
                            min_size=self.db_config.min_connections,
                            max_size=self.db_config.max_connections
                        )

                        logger.info("Successfully connected to PostgreSQL database")
                        span.set_attribute("success", True)
                        return

                    except Exception as e:
                        retry_count += 1
                        logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}")
                        span.record_exception(e)
                        span.set_attribute("retry_count", retry_count)

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error("Maximum PostgreSQL connection retries reached")
                            span.set_attribute("success", False)
                            track_db_error("pg_connect")
                            raise ConnectionError("Failed to connect to PostgreSQL after multiple retries.") from e

    async def close(self):
        """Close PostgreSQL database connections"""
        async with self._conn_lock:
            if self.pool:
                logger.info("Closing PostgreSQL database connection pool...")
                await self.pool.close()
                self.pool = None
                logger.info("Closed PostgreSQL database connection pool.")
            else:
                logger.info("PostgreSQL connection pool already closed.")

    async def check_connection(self) -> bool:
        """Check PostgreSQL database connection health"""
        if not self.pool:
            logger.warning("Checking connection status: Pool does not exist.")
            return False

        try:
            async with self.pool.acquire() as conn:
                result = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5.0)
                is_healthy = (result == 1)
                logger.debug(f"PostgreSQL connection check result: {is_healthy}")
                return is_healthy
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"PostgreSQL connection check failed: {e}", exc_info=True)
            return False

    async def _get_pool(self) -> asyncpg.Pool:
        """Internal helper to get the pool, ensuring it's connected"""
        if self.pool is None:
            logger.warning("Accessing pool before explicit connect(). Attempting connection...")
            await self.connect()
        if self.pool is None:
            raise ConnectionError("PostgreSQL pool is not initialized.")
        return self.pool


class PostgresRepository(PostgresBase, Generic[T]):
    """Generic PostgreSQL repository for entity type T"""
    
    def __init__(self, 
                 entity_class: Type[T], 
                 schema_name: str,
                 table_name: str, 
                 id_field: str = None,
                 tracer_name: str = None,
                 db_config=None):
        """
        Initialize a generic repository

        Args:
            entity_class: The entity model class (e.g., Session, Simulator)
            schema_name: Database schema name (e.g., "session", "simulator")
            table_name: Database table name (e.g., "active_sessions", "instances")
            id_field: Primary key field name (e.g., "session_id", "simulator_id")
            tracer_name: Name for the tracer
            db_config: Optional database configuration
        """
        super().__init__(db_config)
        self.entity_class = entity_class
        self.schema_name = schema_name
        self.table_name = table_name
        self.id_field = id_field or f"{self.table_name[:-1]}_id"  # Default: singular + _id
        self.full_table_name = f"{schema_name}.{table_name}"
        self.tracer = trace.get_tracer(tracer_name or f"postgres_{table_name}_store")
        logger.info(f"Initialized repository for {self.full_table_name} with entity {entity_class.__name__}")
    
    async def get_by_id(self, id_value: str, skip_status_check: bool = False) -> Optional[T]:
        """
        Generic get entity by ID

        Args:
            id_value: The ID value to look up
            skip_status_check: If True, don't filter by status (get all records)

        Returns:
            Entity object if found, None otherwise
        """
        operation_name = f"pg_get_{self.table_name[:-1]}"
        with optional_trace_span(self.tracer, f"pg_store_{operation_name}") as span:
            span.set_attribute(self.id_field, id_value)
            span.set_attribute("skip_status_check", skip_status_check)
            
            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Base query - override in subclasses to customize
                        query = f"SELECT * FROM {self.full_table_name} WHERE {self.id_field} = $1"
                        params = [id_value]
                        
                        # Check result
                        row = await conn.fetchrow(query, *params)
                        if not row:
                            logger.debug(f"{self.entity_class.__name__} with {self.id_field}={id_value} not found.")
                            return None
                        
                        # Process result - override in subclasses to customize
                        return self._row_to_entity(row)
                        
            except Exception as e:
                logger.error(f"Error getting {self.entity_class.__name__} {id_value} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error(operation_name)
                return None

    async def update_status(self, id_value: str, status: Any) -> bool:
        """
        Generic status update method
        
        Args:
            id_value: ID of the entity to update
            status: Status value (string or enum)
            
        Returns:
            True if update succeeded, False otherwise
        """
        operation_name = f"pg_update_{self.table_name[:-1]}_status"
        with optional_trace_span(self.tracer, f"pg_store_{operation_name}") as span:
            span.set_attribute(self.id_field, id_value)
            
            # Handle enum status values
            status_value = status.value if hasattr(status, 'value') else status
            span.set_attribute("status", status_value)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Simple update query - override in subclasses for more complex logic
                        query = f"""
                            UPDATE {self.full_table_name}
                            SET status = $1
                            WHERE {self.id_field} = $2
                        """
                        result = await conn.execute(query, status_value, id_value)
                        updated = 'UPDATE 1' in result
                        span.set_attribute("updated", updated)
                        return updated
                        
            except Exception as e:
                logger.error(f"Error updating status for {self.entity_class.__name__} {id_value} to {status_value}: {e}", 
                             exc_info=True)
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def update_activity(self, id_value: str) -> bool:
        """
        Generic method to update last_active timestamp
        
        Args:
            id_value: ID of the entity to update
            
        Returns:
            True if update succeeded, False otherwise
        """
        operation_name = f"pg_update_{self.table_name[:-1]}_activity"
        with optional_trace_span(self.tracer, f"pg_store_{operation_name}") as span:
            span.set_attribute(self.id_field, id_value)
            
            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        current_time = time.time()
                        query = f"""
                            UPDATE {self.full_table_name}
                            SET last_active = to_timestamp($1)
                            WHERE {self.id_field} = $2
                        """
                        result = await conn.execute(query, current_time, id_value)
                        updated = 'UPDATE 1' in result
                        span.set_attribute("updated", updated)
                        return updated
                        
            except Exception as e:
                logger.error(f"Error updating activity for {self.entity_class.__name__} {id_value}: {e}", 
                             exc_info=True)
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def update_json_metadata(self, id_value: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Generic method to update JSONB metadata using merge operation
        
        Args:
            id_value: ID of the entity to update
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            True if update succeeded, False otherwise
        """
        operation_name = f"pg_update_{self.table_name[:-1]}_metadata"
        with optional_trace_span(self.tracer, f"pg_store_{operation_name}") as span:
            span.set_attribute(self.id_field, id_value)
            
            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Add updated_at timestamp
                        metadata_updates['updated_at'] = time.time()
                        update_json = json.dumps(metadata_updates)
                        
                        # UPSERT with JSONB concatenation
                        query = f"""
                            INSERT INTO {self.schema_name}.{self.table_name}_metadata ({self.id_field}, metadata)
                            VALUES ($1, $2::jsonb)
                            ON CONFLICT ({self.id_field})
                            DO UPDATE SET metadata = {self.schema_name}.{self.table_name}_metadata.metadata || $2::jsonb
                        """
                        result = await conn.execute(query, id_value, update_json)
                        
                        updated = 'INSERT 1' in result or 'UPDATE 1' in result
                        span.set_attribute("updated", updated)
                        return updated
                        
            except Exception as e:
                logger.error(f"Error updating metadata for {self.entity_class.__name__} {id_value}: {e}", 
                             exc_info=True)
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def get_with_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """
        Generic method to get entities matching criteria
        
        Args:
            criteria: Dictionary of field/value pairs to match
            
        Returns:
            List of matching entities
        """
        operation_name = f"pg_get_{self.table_name}_with_criteria"
        with optional_trace_span(self.tracer, f"pg_store_{operation_name}") as span:
            span.set_attribute("criteria", json.dumps(criteria))
            
            pool = await self._get_pool()
            entities = []
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Base query - subclasses should override to include metadata joins if needed
                        query_parts = [f"SELECT * FROM {self.full_table_name}"]
                        conditions = []
                        params = []
                        param_idx = 1
                        
                        # Build simple exact-match conditions
                        for key, value in criteria.items():
                            conditions.append(f"{key} = ${param_idx}")
                            params.append(value)
                            param_idx += 1
                        
                        if conditions:
                            query_parts.append("WHERE " + " AND ".join(conditions))
                        
                        query = " ".join(query_parts)
                        span.set_attribute("db.statement", query)
                        
                        rows = await conn.fetch(query, *params)
                        
                        logger.info(f"Query returned {len(rows)} matches.")
                        span.set_attribute("result_count", len(rows))
                        
                        for row in rows:
                            try:
                                entity = self._row_to_entity(row)
                                if entity:
                                    entities.append(entity)
                            except Exception as e:
                                logger.error(f"Error converting row to entity: {e}", exc_info=True)
                                
                        return entities
                        
            except Exception as e:
                logger.error(f"Error getting entities with criteria {criteria}: {e}", 
                             exc_info=True)
                span.record_exception(e)
                track_db_error(operation_name)
                return []
    
    def _row_to_entity(self, row: asyncpg.Record) -> Optional[T]:
        """
        Convert database row to entity object.
        Subclasses should override this to handle specific entity conversion.
        
        Args:
            row: Database row from query
            
        Returns:
            Entity object or None on error
        """
        try:
            # Basic implementation - subclasses should override
            return self.entity_class(**dict(row))
        except Exception as e:
            logger.error(f"Error converting row to {self.entity_class.__name__}: {e}")
            return None