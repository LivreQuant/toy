# backend/fund-service/source/db/crypto_repository.py
import logging
import time
import uuid
import json
import datetime
from typing import Dict, Any, Optional, List

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('crypto_repository')

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, datetime.datetime):
        return data.timestamp()
    elif isinstance(data, uuid.UUID):
        return str(data)
    return data

class CryptoRepository:
    """Data access layer for crypto-related operations"""

    def __init__(self):
        """Initialize the crypto repository"""
        self.db_pool = DatabasePool()
        # Far future date used for active records
        self.future_date = datetime.datetime(2999, 1, 1, tzinfo=datetime.timezone.utc)

    ######################
    # WALLET OPERATIONS  #
    ######################

    async def save_wallet(self, user_id: str, fund_id: str, wallet_data: Dict[str, Any]) -> bool:
        """Save wallet information for a user/fund combination - always encrypted"""
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Security validation - ensure we have encrypted data and salt
        if not wallet_data.get('mnemonic') or not wallet_data.get('mnemonic_salt'):
            logger.error(f"Missing encrypted mnemonic or salt for user {user_id}")
            return False
        
        query = """
        INSERT INTO crypto.wallets (
            user_id, fund_id, address, mnemonic, mnemonic_salt, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        ) ON CONFLICT (user_id, fund_id) 
        DO UPDATE SET 
            address = EXCLUDED.address,
            mnemonic = EXCLUDED.mnemonic,
            mnemonic_salt = EXCLUDED.mnemonic_salt,
            active_at = EXCLUDED.active_at,
            expire_at = EXCLUDED.expire_at
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    user_id,
                    fund_id,
                    wallet_data.get('address'),
                    wallet_data.get('mnemonic'),  # Always encrypted
                    wallet_data.get('mnemonic_salt'),  # Salt for decryption
                    now,
                    self.future_date
                )
                
                duration = time.time() - start_time
                track_db_operation("save_wallet", True, duration)
                logger.info(f"Encrypted wallet saved for user {user_id}, fund {fund_id}")
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_wallet", False, duration)
            logger.error(f"Error saving encrypted wallet: {e}")
            return False

    async def get_wallet(self, user_id: str, fund_id: str) -> Optional[Dict[str, Any]]:
        """Get wallet information for a user/fund combination - always encrypted"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT address, mnemonic, mnemonic_salt, active_at, expire_at
        FROM crypto.wallets
        WHERE user_id = $1 AND fund_id = $2 AND expire_at > NOW()
        ORDER BY active_at DESC
        LIMIT 1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id, fund_id)
                
                duration = time.time() - start_time
                if row:
                    wallet_data = ensure_json_serializable(dict(row))
                    
                    # Security validation - ensure we have salt (indicates proper encryption)
                    if not wallet_data.get('mnemonic_salt'):
                        logger.error(f"Wallet missing encryption salt for user {user_id} - possible corruption")
                        track_db_operation("get_wallet", False, duration)
                        return None
                    
                    track_db_operation("get_wallet", True, duration)
                    return wallet_data
                else:
                    track_db_operation("get_wallet", False, duration)
                    return None
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_wallet", False, duration)
            logger.error(f"Error getting wallet: {e}")
            return None

    #########################
    # CONTRACT OPERATIONS   #
    #########################

    async def save_contract(self, user_id: str, book_id: str, contract_data: Dict[str, Any]) -> bool:
        """
        Save contract information for a user/book combination
        
        Args:
            user_id: User ID
            book_id: Book ID
            contract_data: Contract information
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        query = """
        INSERT INTO crypto.contracts (
            user_id, book_id, app_id, app_address, parameters, status, 
            blockchain_status, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9
        ) RETURNING contract_id
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                contract_id = await conn.fetchval(
                    query,
                    user_id,
                    book_id,
                    contract_data.get('app_id'),
                    contract_data.get('app_address'),
                    contract_data.get('parameters'),
                    contract_data.get('status', 'ACTIVE'),
                    contract_data.get('blockchain_status', 'Active'),
                    now,
                    self.future_date
                )
                
                duration = time.time() - start_time
                track_db_operation("save_contract", True, duration)
                logger.info(f"Contract saved for user {user_id}, book {book_id}")
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_contract", False, duration)
            logger.error(f"Error saving contract: {e}")
            return False

    async def get_contract(self, user_id: str, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get contract information for a user/book combination
        
        Args:
            user_id: User ID
            book_id: Book ID
            
        Returns:
            Contract data if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT contract_id, app_id, app_address, parameters, status, 
               blockchain_status, active_at, expire_at
        FROM crypto.contracts
        WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
        ORDER BY active_at DESC
        LIMIT 1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id, book_id)
                
                duration = time.time() - start_time
                if row:
                    track_db_operation("get_contract", True, duration)
                    return ensure_json_serializable(dict(row))
                else:
                    track_db_operation("get_contract", False, duration)
                    return None
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_contract", False, duration)
            logger.error(f"Error getting contract: {e}")
            return None

    async def get_user_contracts(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all contracts for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of contract data
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT contract_id, book_id, app_id, app_address, parameters, 
               status, blockchain_status, active_at, expire_at
        FROM crypto.contracts
        WHERE user_id = $1 AND expire_at > NOW()
        ORDER BY active_at DESC
        """
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                return [ensure_json_serializable(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting user contracts: {e}")
            return []

    async def update_contract_status(self, user_id: str, book_id: str, status: str, blockchain_status: str = None) -> bool:
        """
        Update contract status
        
        Args:
            user_id: User ID
            book_id: Book ID
            status: New status
            blockchain_status: New blockchain status
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        if blockchain_status:
            query = """
            UPDATE crypto.contracts
            SET status = $3, blockchain_status = $4, active_at = $5
            WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
            """
            params = (user_id, book_id, status, blockchain_status, now)
        else:
            query = """
            UPDATE crypto.contracts
            SET status = $3, active_at = $4
            WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
            """
            params = (user_id, book_id, status, now)
        
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(query, *params)
                
                # Check if any rows were affected
                if result.split()[-1] == '0':
                    logger.warning(f"No contract found to update for user {user_id}, book {book_id}")
                    return False
                    
                logger.info(f"Contract status updated for user {user_id}, book {book_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating contract status: {e}")
            return False

    async def expire_contract(self, user_id: str, book_id: str, deletion_note: str = None) -> bool:
        """
        Expire a contract (soft delete)
        
        Args:
            user_id: User ID
            book_id: Book ID
            deletion_note: Optional note about deletion
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        query = """
        UPDATE crypto.contracts
        SET expire_at = $3, deleted_at = $3, deletion_note = $4
        WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
        """
        
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(query, user_id, book_id, now, deletion_note)
                
                # Check if any rows were affected
                if result.split()[-1] == '0':
                    logger.warning(f"No contract found to expire for user {user_id}, book {book_id}")
                    return False
                    
                logger.info(f"Contract expired for user {user_id}, book {book_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error expiring contract: {e}")
            return False

    #########################
    # TRANSACTION OPERATIONS #
    #########################

    async def save_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """
        Save transaction information
        
        Args:
            tx_data: Transaction data
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO crypto.txs (
            user_id, book_id, contract_id, app_id, transaction_id, date,
            sender, action, g_user_id, g_book_id, g_status, g_params,
            l_book_hash, l_research_hash, l_params
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
        ) ON CONFLICT (transaction_id) DO NOTHING
        """
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    tx_data.get('user_id'),
                    tx_data.get('book_id'),
                    tx_data.get('contract_id'),
                    tx_data.get('app_id'),
                    tx_data.get('transaction_id'),
                    tx_data.get('date'),
                    tx_data.get('sender'),
                    tx_data.get('action'),
                    tx_data.get('g_user_id'),
                    tx_data.get('g_book_id'),
                    tx_data.get('g_status'),
                    tx_data.get('g_params'),
                    tx_data.get('l_book_hash'),
                    tx_data.get('l_research_hash'),
                    tx_data.get('l_params')
                )
                
                logger.info(f"Transaction saved: {tx_data.get('transaction_id')}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving transaction: {e}")
            return False

    async def get_user_transactions(self, user_id: str, book_id: str = None) -> List[Dict[str, Any]]:
        """
        Get transactions for a user, optionally filtered by book
        
        Args:
            user_id: User ID
            book_id: Optional book ID filter
            
        Returns:
            List of transaction data
        """
        pool = await self.db_pool.get_pool()
        
        if book_id:
            query = """
            SELECT * FROM crypto.txs
            WHERE user_id = $1 AND book_id = $2
            ORDER BY date DESC
            """
            params = (user_id, book_id)
        else:
            query = """
            SELECT * FROM crypto.txs
            WHERE user_id = $1
            ORDER BY date DESC
            """
            params = (user_id,)
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [ensure_json_serializable(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []