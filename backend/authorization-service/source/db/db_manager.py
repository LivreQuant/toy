# source/db/database.py
import logging
import asyncpg
import os
import datetime
import json

logger = logging.getLogger('database')

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral')
        }
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
    
    async def connect(self):
        """Create the database connection pool"""
        if self.pool:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                min_size=self.min_connections,
                max_size=self.max_connections,
                **self.db_config
            )
            logger.info("Database connection established")
            
            # Ensure required schema exists
            await self.ensure_schema()
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    async def close(self):
        """Close all database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connections closed")
    
    async def ensure_schema(self):
        """Ensure the auth schema and tables exist"""
        schema_query = """
        -- Create schema if not exists
        CREATE SCHEMA IF NOT EXISTS auth;
        
        -- Create users table if not exists
        CREATE TABLE IF NOT EXISTS auth.users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            role VARCHAR(50) DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP WITH TIME ZONE
        );
        
        -- Create refresh tokens table if not exists
        CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            is_revoked BOOLEAN DEFAULT FALSE,
            CONSTRAINT unique_token UNIQUE (token_hash)
        );
        
        -- Add function for password verification if it doesn't exist
        CREATE OR REPLACE FUNCTION auth.verify_password(
            p_username VARCHAR,
            p_password VARCHAR
        ) RETURNS TABLE(user_id INTEGER, role VARCHAR) AS $$
        DECLARE
            user_record RECORD;
        BEGIN
            -- Get user
            SELECT id, password_hash, role INTO user_record
            FROM auth.users
            WHERE username = p_username AND is_active = TRUE;
            
            -- Simple password check for demo
            -- In production, use proper password hashing with bcrypt
            IF user_record IS NOT NULL AND 
               user_record.password_hash = crypt(p_password, user_record.password_hash) THEN
                -- Return user info
                user_id := user_record.id;
                role := user_record.role;
                RETURN NEXT;
                
                -- Update last login
                UPDATE auth.users SET last_login = NOW() 
                WHERE id = user_record.id;
            END IF;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        
        -- Add cleanup function if it doesn't exist
        CREATE OR REPLACE FUNCTION auth.cleanup_expired_tokens()
        RETURNS void AS $$
        BEGIN
            DELETE FROM auth.refresh_tokens 
            WHERE expires_at < NOW() OR is_revoked = TRUE;
        END;
        $$ LANGUAGE plpgsql;
        
        -- Add extension for password hashing if not exists
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(schema_query)
        
        logger.info("Database schema verification complete")
    
    async def get_user_by_username(self, username):
        """Get user by username"""
        if not self.pool:
            await self.connect()
        
        query = """
            SELECT id, username, password_hash, is_active, role
            FROM auth.users
            WHERE username = $1
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, username)
            return dict(row) if row else None
    
    async def get_user_by_id(self, user_id):
        """Get user by ID"""
        if not self.pool:
            await self.connect()
        
        query = """
            SELECT id, username, email, first_name, last_name, is_active, role
            FROM auth.users
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            return dict(row) if row else None
    
    async def verify_password(self, username, password):
        """Verify user password"""
        if not self.pool:
            await self.connect()
        
        query = """
            SELECT * FROM auth.verify_password($1, $2)
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, username, password)
            return dict(row) if row else None
    
    async def save_refresh_token(self, user_id, token_hash, expires_at):
        """Save a refresh token to the database"""
        if not self.pool:
            await self.connect()
        
        query = """
            INSERT INTO auth.refresh_tokens
            (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (token_hash) 
            DO UPDATE SET expires_at = $3, is_revoked = FALSE
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id, token_hash, expires_at)
    
    async def get_refresh_token(self, token_hash):
        """Get refresh token info"""
        if not self.pool:
            await self.connect()
        
        query = """
            SELECT user_id, expires_at, is_revoked
            FROM auth.refresh_tokens
            WHERE token_hash = $1
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, token_hash)
            return dict(row) if row else None
    
    async def revoke_refresh_token(self, token_hash):
        """Revoke a refresh token"""
        if not self.pool:
            await self.connect()
        
        query = """
            UPDATE auth.refresh_tokens
            SET is_revoked = TRUE
            WHERE token_hash = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, token_hash)
    
    async def revoke_all_user_tokens(self, user_id):
        """Revoke all refresh tokens for a user"""
        if not self.pool:
            await self.connect()
        
        query = """
            UPDATE auth.refresh_tokens
            SET is_revoked = TRUE
            WHERE user_id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id)
    
    async def cleanup_expired_tokens(self):
        """Clean up expired tokens"""
        if not self.pool:
            await self.connect()
        
        query = "SELECT auth.cleanup_expired_tokens()"
        
        async with self.pool.acquire() as conn:
            await conn.execute(query)
            
    async def check_connection(self):
        """Check if database connection is working"""
        if not self.pool:
            try:
                await self.connect()
                return True
            except:
                return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False