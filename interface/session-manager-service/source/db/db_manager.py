# db_manager.py
import os
import logging
import time
import threading
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
            'host': os.getenv('DB_HOST', 'pgbouncer.postgresql'),
            'port': os.getenv('DB_PORT', '5432'),
            'dbname': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral'),
            'application_name': os.getenv('SERVICE_NAME', 'session-manager'),
            'connect_timeout': 3,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
        
        # Connection pool settings
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.pool = {}  # Simple connection tracking
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.conn_lock = threading.RLock()
        self.connection_lifetime = int(os.getenv('DB_CONNECTION_LIFETIME', '3600'))  # 1 hour default
        
        # Initialize connection pool
        self._init_pool()
        
        # Start background thread for connection management
        self.pool_maintenance_thread = threading.Thread(target=self._maintain_pool, daemon=True)
        self.pool_maintenance_thread.start()
    
    def _init_pool(self):
        """Initialize minimum number of connections"""
        try:
            with self.conn_lock:
                for i in range(self.min_connections):
                    conn = self._create_connection()
                    self.pool[id(conn)] = {
                        'connection': conn,
                        'in_use': False,
                        'created_at': time.time(),
                        'last_used': time.time()
                    }
                logger.info(f"Initialized database connection pool with {self.min_connections} connections")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            # If we can't establish the minimum connections, we should fail fast
            raise
    
    def _create_connection(self):
        """Create a new database connection with retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                logger.info(f"Creating new database connection to {self.db_config['host']}:{self.db_config['port']}")
                conn = psycopg2.connect(**self.db_config)
                conn.autocommit = True
                return conn
            except Exception as e:
                retries += 1
                logger.error(f"Database connection attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    logger.critical("Failed to connect to database after maximum retries")
                    raise
    
    def _maintain_pool(self):
        """Background thread to maintain the connection pool"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                
                with self.conn_lock:
                    current_time = time.time()
                    
                    # Check for expired connections
                    expired_conns = []
                    for conn_id, data in list(self.pool.items()):
                        # Skip connections that are in use
                        if data['in_use']:
                            continue
                        
                        conn = data['connection']
                        conn_age = current_time - data['created_at']
                        time_since_used = current_time - data['last_used']
                        
                        # Close connections that are too old or haven't been used in a while
                        # but maintain min_connections
                        if (conn_age > self.connection_lifetime or 
                            (time_since_used > 300 and len(self.pool) > self.min_connections)):
                            try:
                                logger.info(f"Closing expired connection (age: {conn_age:.1f}s, idle: {time_since_used:.1f}s)")
                                conn.close()
                                expired_conns.append(conn_id)
                            except Exception as e:
                                logger.error(f"Error closing expired connection: {e}")
                                expired_conns.append(conn_id)
                    
                    # Remove expired connections from the pool
                    for conn_id in expired_conns:
                        del self.pool[conn_id]
                    
                    # Ensure minimum connections
                    if len([c for c_id, c in self.pool.items() if not c['in_use']]) < self.min_connections:
                        for i in range(len(self.pool), self.min_connections):
                            try:
                                conn = self._create_connection()
                                self.pool[id(conn)] = {
                                    'connection': conn,
                                    'in_use': False,
                                    'created_at': time.time(),
                                    'last_used': time.time()
                                }
                                logger.info("Added new connection to maintain minimum pool size")
                            except Exception as e:
                                logger.error(f"Failed to add new connection to pool: {e}")
                                # If we can't create a new connection, wait until next cycle
                                break
                    
                    # Log pool statistics
                    in_use = sum(1 for c in self.pool.values() if c['in_use'])
                    logger.info(f"Connection pool status: {len(self.pool)} total, {in_use} in use")
                    
            except Exception as e:
                logger.error(f"Error in connection pool maintenance: {e}")
    
    def get_connection(self):
        """Get a connection from the pool or create a new one if needed"""
        with self.conn_lock:
            # First, try to find an available connection
            for conn_id, data in list(self.pool.items()):
                if not data['in_use']:
                    # Check if connection is still valid
                    conn = data['connection']
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT 1")
                            data['in_use'] = True
                            data['last_used'] = time.time()
                            return conn
                    except (psycopg2.OperationalError, psycopg2.InterfaceError):
                        # Connection is stale, close it and remove from pool
                        try:
                            conn.close()
                        except:
                            pass
                        del self.pool[conn_id]
            
            # If we have capacity to create a new connection
            if len(self.pool) < self.max_connections:
                try:
                    new_conn = self._create_connection()
                    self.pool[id(new_conn)] = {
                        'connection': new_conn,
                        'in_use': True,
                        'created_at': time.time(),
                        'last_used': time.time()
                    }
                    return new_conn
                except Exception as e:
                    logger.error(f"Failed to create new connection: {e}")
                    # Fall through to wait for an available connection
            
            # Otherwise, wait for a connection to become available
            logger.warning("Connection pool exhausted, waiting for an available connection")
            wait_start = time.time()
            max_wait = 30  # seconds
            
            while time.time() - wait_start < max_wait:
                # Yield control to other threads
                self.conn_lock.release()
                time.sleep(0.1)
                self.conn_lock.acquire()
                
                # Check for available connections again
                for conn_id, data in list(self.pool.items()):
                    if not data['in_use']:
                        try:
                            with data['connection'].cursor() as cursor:
                                cursor.execute("SELECT 1")
                                data['in_use'] = True
                                data['last_used'] = time.time()
                                return data['connection']
                        except:
                            # Try to clean up bad connection
                            try:
                                data['connection'].close()
                            except:
                                pass
                            del self.pool[conn_id]
            
            # If we still can't get a connection after waiting
            raise Exception("Could not acquire database connection after waiting")
    
    def release_connection(self, conn):
        """Release a connection back to the pool"""
        with self.conn_lock:
            if id(conn) in self.pool:
                self.pool[id(conn)]['in_use'] = False
                self.pool[id(conn)]['last_used'] = time.time()
    
    def execute(self, query, params=None, fetch=False):
        """Execute a query using a connection from the pool"""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # Connection error, try once more with a new connection
            logger.warning(f"Database error, retrying with new connection: {e}")
            
            # Remove the failed connection from pool if it exists
            if conn and id(conn) in self.pool:
                try:
                    conn.close()
                except:
                    pass
                with self.conn_lock:
                    del self.pool[id(conn)]
            
            # Try again with a new connection
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
        finally:
            if conn and id(conn) in self.pool:
                self.release_connection(conn)
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.conn_lock:
            for conn_id, data in list(self.pool.items()):
                try:
                    data['connection'].close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
                del self.pool[conn_id]
            logger.info("Closed all database connections")

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