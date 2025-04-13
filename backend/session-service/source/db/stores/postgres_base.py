# data_access/stores/postgres/postgres_base.py
"""
Base PostgreSQL connection management and generic repository implementation.
"""
import logging
import asyncio
import asyncpg
from typing import Optional, Dict, Any, List, TypeVar, Generic, Type

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_db_error, track_db_operation, TimedOperation

logger = logging.getLogger(__name__)

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

                max_retries = self.db_config.max_retries
                retry_count = 0
                retry_delay = self.db_config.retry_delay

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
    """Generic PostgreSQL repository with improved CRUD operations"""

    def __init__(self,
                 entity_class: Type[T],
                 schema_name: str,
                 table_name: str,
                 id_field: str = None,
                 tracer_name: str = None,
                 db_config=None):
        """Initialize a generic repository"""
        super().__init__(db_config)
        self.entity_class = entity_class
        self.schema_name = schema_name
        self.table_name = table_name
        self.id_field = id_field or f"{self.table_name[:-1]}_id"  # Default: singular + _id
        self.full_table_name = f"{schema_name}.{table_name}"
        self.tracer = trace.get_tracer(tracer_name or f"postgres_{table_name}_store")
        logger.info(f"Initialized repository for {self.full_table_name} with entity {entity_class.__name__}")

    # Core CRUD operations

    async def create(self, entity: T) -> bool:
        """
        Create a new entity in the database

        Args:
            entity: The entity to create

        Returns:
            True if creation was successful, False otherwise
        """
        operation_name = f"pg_create_{self.table_name[:-1]}"
        with optional_trace_span(self.tracer, operation_name) as span:
            # Extract primary key for span attribute
            id_value = getattr(entity, self.id_field)
            span.set_attribute(self.id_field, id_value)

            # Convert entity to dict
            entity_dict = self._entity_to_dict(entity)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Dynamically generate insert SQL using dict keys/values
                        fields = list(entity_dict.keys())
                        placeholders = [f'${i + 1}' for i in range(len(fields))]
                        values = [entity_dict[field] for field in fields]

                        query = f"""
                            INSERT INTO {self.full_table_name}
                            ({', '.join(fields)})
                            VALUES ({', '.join(placeholders)})
                        """

                        await conn.execute(query, *values)
                        return True
            except Exception as e:
                logger.error(f"Error creating {self.entity_class.__name__}: {e}")
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def get_by_id(self, id_value: str) -> Optional[T]:
        """
        Generic get entity by ID

        Args:
            id_value: The ID value to look up

        Returns:
            Entity object if found, None otherwise
        """
        operation_name = f"pg_get_{self.table_name[:-1]}"
        with optional_trace_span(self.tracer, operation_name) as span:
            span.set_attribute(self.id_field, id_value)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        query = f"SELECT * FROM {self.full_table_name} WHERE {self.id_field} = $1"
                        row = await conn.fetchrow(query, id_value)

                        if not row:
                            logger.debug(f"{self.entity_class.__name__} with {self.id_field}={id_value} not found.")
                            return None

                        return self._row_to_entity(row)
            except Exception as e:
                logger.error(f"Error getting {self.entity_class.__name__} {id_value}: {e}")
                span.record_exception(e)
                track_db_error(operation_name)
                return None

    async def update(self, id_value: str, updates: Dict[str, Any]) -> bool:
        """
        Update an entity with the given values

        Args:
            id_value: The ID of the entity to update
            updates: Dictionary of field/value pairs to update

        Returns:
            True if update was successful, False otherwise
        """
        operation_name = f"pg_update_{self.table_name[:-1]}"
        with optional_trace_span(self.tracer, operation_name) as span:
            span.set_attribute(self.id_field, id_value)

            if not updates:
                logger.warning(f"No updates provided for {self.entity_class.__name__} {id_value}")
                return False

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        # Build update statement dynamically
                        set_clauses = []
                        values = []

                        for i, (field, value) in enumerate(updates.items(), 1):
                            set_clauses.append(f"{field} = ${i}")
                            values.append(value)

                        # Add ID as the last parameter
                        values.append(id_value)

                        query = f"""
                            UPDATE {self.full_table_name}
                            SET {', '.join(set_clauses)}
                            WHERE {self.id_field} = ${len(values)}
                        """

                        result = await conn.execute(query, *values)
                        updated = 'UPDATE 1' in result
                        span.set_attribute("updated", updated)
                        return updated
            except Exception as e:
                logger.error(f"Error updating {self.entity_class.__name__} {id_value}: {e}")
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def delete(self, id_value: str) -> bool:
        """
        Delete an entity by ID

        Args:
            id_value: The ID of the entity to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        operation_name = f"pg_delete_{self.table_name[:-1]}"
        with optional_trace_span(self.tracer, operation_name) as span:
            span.set_attribute(self.id_field, id_value)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        query = f"DELETE FROM {self.full_table_name} WHERE {self.id_field} = $1"
                        result = await conn.execute(query, id_value)
                        deleted = 'DELETE 1' in result
                        span.set_attribute("deleted", deleted)
                        return deleted
            except Exception as e:
                logger.error(f"Error deleting {self.entity_class.__name__} {id_value}: {e}")
                span.record_exception(e)
                track_db_error(operation_name)
                return False

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all entities with pagination

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of entity objects
        """
        operation_name = f"pg_get_all_{self.table_name}"
        with optional_trace_span(self.tracer, operation_name) as span:
            span.set_attribute("limit", limit)
            span.set_attribute("offset", offset)

            pool = await self._get_pool()
            entities = []
            try:
                with TimedOperation(track_db_operation, operation_name):
                    async with pool.acquire() as conn:
                        query = f"""
                            SELECT * FROM {self.full_table_name}
                            ORDER BY created_at DESC
                            LIMIT $1 OFFSET $2
                        """
                        rows = await conn.fetch(query, limit, offset)

                        for row in rows:
                            entity = self._row_to_entity(row)
                            if entity:
                                entities.append(entity)

                        return entities
            except Exception as e:
                logger.error(f"Error getting all {self.entity_class.__name__} entities: {e}")
                span.record_exception(e)
                track_db_error(operation_name)
                return []

    # Helper methods

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

    def _entity_to_dict(self, entity: T) -> Dict[str, Any]:
        """
        Convert entity to dictionary for database operations

        Args:
            entity: The entity object

        Returns:
            Dictionary of field/value pairs
        """
        try:
            # Use the entity's .dict() method if available (for Pydantic models)
            if hasattr(entity, 'dict'):
                return entity.dict()
            # Otherwise use the entity's __dict__ attribute
            return entity.__dict__
        except Exception as e:
            logger.error(f"Error converting {self.entity_class.__name__} to dict: {e}")
            return {}
