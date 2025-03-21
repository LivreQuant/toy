# db_manager.py
import os
import logging
import time
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import DictCursor
import json
import uuid

logger = logging.getLogger('db_manager')

class DatabaseManager:
    """Handles all database operations for the session service"""
    
    def __init__(self):
        # Get database configuration from environment
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': os.getenv('DB_PORT', '5432'),
            'dbname': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral')
        }
        
        # Connection pool settings
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        
        # Establish initial connection
        self.conn = self._connect()
    
    def _connect(self):
        """Create a new database connection with retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                logger.info(f"Connecting to database at {self.db_config['host']}:{self.db_config['port']}")
                conn = psycopg2.connect(**self.db_config)
                conn.autocommit = True
                logger.info("Database connection established")
                return conn
            except Exception as e:
                retries += 1
                logger.error(f"Database connection attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.critical("Failed to connect to database after maximum retries")
                    raise
    
    def execute(self, query, params=None, fetch=False):
        """Execute a query with error handling and connection reset"""
        try:
            with self.conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # Connection may have timed out, try to reconnect
            logger.warning(f"Database connection error, attempting to reconnect: {e}")
            self.conn = self._connect()
            
            # Retry once with new connection
            with self.conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    # Session management methods
    def get_session(self, session_id):
        """Get session data by ID"""
        query = """
            SELECT 
                session_id, user_id, created_at, last_active, expires_at, ip_address
            FROM 
                session.active_sessions 
            WHERE 
                session_id = %s
        """
        results = self.execute(query, (session_id,), fetch=True)
        
        if not results:
            return None
            
        # Get additional session metadata
        metadata_query = """
            SELECT 
                metadata
            FROM 
                session.session_metadata 
            WHERE 
                session_id = %s
        """
        metadata_results = self.execute(metadata_query, (session_id,), fetch=True)
        
        session = dict(results[0])
        
        # Add metadata if available
        if metadata_results and metadata_results[0]['metadata']:
            try:
                session.update(json.loads(metadata_results[0]['metadata']))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON metadata for session {session_id}")
        
        return session
    
    def get_user_session(self, user_id):
        """Get active session for a user"""
        query = """
            SELECT 
                session_id
            FROM 
                session.active_sessions 
            WHERE 
                user_id = %s AND expires_at > NOW()
        """
        results = self.execute(query, (user_id,), fetch=True)
        return results[0]['session_id'] if results else None
    
    def create_session(self, session_id, user_id, client_ip=None):
        """Create a new session"""
        token = str(uuid.uuid4())  # Generate session token
        
        # Insert session record
        query = """
            INSERT INTO session.active_sessions 
            (session_id, user_id, token, created_at, last_active, expires_at, ip_address) 
            VALUES (%s, %s, %s, NOW(), NOW(), NOW() + INTERVAL '1 hour', %s)
        """
        self.execute(query, (session_id, user_id, token, client_ip))
        
        # Initialize empty metadata
        metadata_query = """
            INSERT INTO session.session_metadata
            (session_id, metadata)
            VALUES (%s, %s)
        """
        initial_metadata = json.dumps({
            "frontend_connections": 0,
            "simulator_id": None,
            "simulator_endpoint": None
        })
        self.execute(metadata_query, (session_id, initial_metadata))
        
        return True
    
    def update_session_activity(self, session_id):
        """Update last_active timestamp for a session"""
        query = """
            UPDATE session.active_sessions 
            SET last_active = NOW() 
            WHERE session_id = %s
            RETURNING TRUE
        """
        result = self.execute(query, (session_id,), fetch=True)
        return result and result[0][0]
    
    def update_session_metadata(self, session_id, updates):
        """Update session metadata fields"""
        # First get current metadata
        query = """
            SELECT metadata FROM session.session_metadata 
            WHERE session_id = %s
        """
        results = self.execute(query, (session_id,), fetch=True)
        
        if not results:
            # Create metadata record if it doesn't exist
            metadata = updates
            insert_query = """
                INSERT INTO session.session_metadata (session_id, metadata)
                VALUES (%s, %s)
            """
            self.execute(insert_query, (session_id, json.dumps(metadata)))
        else:
            # Update existing metadata
            try:
                metadata = json.loads(results[0]['metadata']) if results[0]['metadata'] else {}
            except json.JSONDecodeError:
                metadata = {}
            
            # Apply updates
            metadata.update(updates)
            
            # Save back to database
            update_query = """
                UPDATE session.session_metadata
                SET metadata = %s
                WHERE session_id = %s
            """
            self.execute(update_query, (json.dumps(metadata), session_id))
        
        return True
    
    def end_session(self, session_id):
        """Delete a session and return the user_id"""
        query = """
            DELETE FROM session.active_sessions 
            WHERE session_id = %s
            RETURNING user_id
        """
        result = self.execute(query, (session_id,), fetch=True)
        
        # Also clean up metadata
        metadata_query = """
            DELETE FROM session.session_metadata
            WHERE session_id = %s
        """
        self.execute(metadata_query, (session_id,))
        
        return result[0][0] if result else None
    
    def cleanup_expired_sessions(self):
        """Run the cleanup function for expired sessions"""
        self.execute("SELECT session.cleanup_expired_sessions()")
        return True
        
    # Exchange service methods
    def register_exchange_service(self, session_id, exchange_id, endpoint, inactivity_timeout_seconds=300):
        """Register a new exchange service for a session"""
        query = """
            INSERT INTO session.exchange_services
            (exchange_id, session_id, endpoint, created_at, last_active, inactivity_timeout_seconds)
            VALUES (%s, %s, %s, NOW(), NOW(), %s)
            ON CONFLICT (session_id) DO UPDATE
            SET exchange_id = EXCLUDED.exchange_id,
                endpoint = EXCLUDED.endpoint,
                last_active = NOW(),
                inactivity_timeout_seconds = EXCLUDED.inactivity_timeout_seconds
        """
        self.execute(query, (exchange_id, session_id, endpoint, inactivity_timeout_seconds))
        return True
    
    def update_exchange_last_active(self, session_id):
        """Update last_active timestamp for exchange service attached to session"""
        query = """
            UPDATE session.exchange_services
            SET last_active = NOW()
            WHERE session_id = %s
        """
        self.execute(query, (session_id,))
        return True
    
    def get_exchange_for_session(self, session_id):
        """Get exchange service info for a session"""
        query = """
            SELECT 
                exchange_id, endpoint, last_active, inactivity_timeout_seconds
            FROM 
                session.exchange_services
            WHERE 
                session_id = %s
        """
        results = self.execute(query, (session_id,), fetch=True)
        return dict(results[0]) if results else None
    
    def get_all_exchange_services(self):
        """Get all exchange services for cleanup check"""
        query = """
            SELECT 
                exchange_id, session_id, endpoint, last_active, inactivity_timeout_seconds
            FROM 
                session.exchange_services
        """
        results = self.execute(query, fetch=True)
        return [dict(row) for row in results] if results else []
    
    def deactivate_exchange_service(self, exchange_id):
        """Deactivate an exchange service"""
        query = """
            DELETE FROM session.exchange_services
            WHERE exchange_id = %s
            RETURNING session_id
        """
        result = self.execute(query, (exchange_id,), fetch=True)
        
        # Clear simulator info from session metadata if exists
        if result:
            session_id = result[0]['session_id']
            self.update_session_metadata(session_id, {
                "simulator_id": None,
                "simulator_endpoint": None
            })
        
        return True