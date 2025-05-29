# source/db/crypto_repository.py
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
                    wallet_data.get('mnemonic'),
                    wallet_data.get('mnemonic_salt'),
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
        """Save contract information for a user/book combination"""
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Convert app_id to string for database storage
        app_id = contract_data.get('app_id') or contract_data.get('contract_id')
        if app_id is not None:
            app_id = str(app_id)
        
        query = """
        INSERT INTO crypto.contracts (
            user_id, book_id, app_id, app_address, parameters, status, 
            blockchain_status, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    user_id,
                    book_id,
                    app_id,  # Now properly converted to string
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
        """Get contract information for a user/book combination"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT app_id, app_address, parameters, status, 
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
                    contract_data = ensure_json_serializable(dict(row))
                    # Add a synthetic contract_id for backward compatibility if needed
                    contract_data['contract_id'] = contract_data['app_id']
                    track_db_operation("get_contract", True, duration)
                    return contract_data
                else:
                    track_db_operation("get_contract", False, duration)
                    return None
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_contract", False, duration)
            logger.error(f"Error getting contract: {e}")
            return None

    async def get_user_contracts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contracts for a user"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT app_id, book_id, app_address, parameters, 
               status, blockchain_status, active_at, expire_at
        FROM crypto.contracts
        WHERE user_id = $1 AND expire_at > NOW()
        ORDER BY active_at DESC
        """
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                contracts = []
                for row in rows:
                    contract_data = ensure_json_serializable(dict(row))
                    # Add synthetic contract_id for backward compatibility
                    contract_data['contract_id'] = contract_data['app_id']
                    contracts.append(contract_data)
                return contracts
                
        except Exception as e:
            logger.error(f"Error getting user contracts: {e}")
            return []

    async def update_contract_status(self, user_id: str, book_id: str, status: str, blockchain_status: str = None) -> bool:
        """Update contract status"""
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
        
    async def update_contract_parameters(self, user_id: str, book_id: str, parameters: str) -> bool:
        """Update contract parameters using temporal data pattern"""
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 1. Get the current active contract
                    current_contract_query = """
                    SELECT app_id, app_address, status, blockchain_status
                    FROM crypto.contracts
                    WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
                    ORDER BY active_at DESC
                    LIMIT 1
                    """
                    
                    current_contract = await conn.fetchrow(current_contract_query, user_id, book_id)
                    
                    if not current_contract:
                        logger.warning(f"No active contract found to update for user {user_id}, book {book_id}")
                        return False
                    
                    # 2. Expire the current contract
                    expire_query = """
                    UPDATE crypto.contracts
                    SET expire_at = $3
                    WHERE user_id = $1 AND book_id = $2 AND expire_at > NOW()
                    """
                    
                    await conn.execute(expire_query, user_id, book_id, now)
                    
                    # 3. Create new contract row with updated parameters
                    insert_query = """
                    INSERT INTO crypto.contracts (
                        user_id, book_id, app_id, app_address, parameters, status, 
                        blockchain_status, active_at, expire_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9
                    )
                    """
                    
                    await conn.execute(
                        insert_query,
                        user_id,
                        book_id,
                        current_contract['app_id'],  # Already a string from DB
                        current_contract['app_address'],
                        parameters,  # New parameters
                        current_contract['status'],
                        current_contract['blockchain_status'],
                        now,
                        self.future_date
                    )
                    
                    duration = time.time() - start_time
                    track_db_operation("update_contract_parameters", True, duration)
                    logger.info(f"Contract parameters updated with temporal pattern for user {user_id}, book {book_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_contract_parameters", False, duration)
            logger.error(f"Error updating contract parameters with temporal pattern: {e}")
            return False
        
    async def expire_contract(self, user_id: str, book_id: str, deletion_note: str = None) -> bool:
        """Expire a contract (soft delete)"""
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
        """Save transaction to crypto.txs table"""
        start_time = time.time()
        try:
            # Convert app_id to string and handle both old/new field names
            app_id = tx_data.get('app_id') or tx_data.get('contract_id')
            if app_id is not None:
                app_id = str(app_id)
                
            tx_id = tx_data.get('tx_id') or tx_data.get('transaction_id')
            
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO crypto.txs (
                        user_id, book_id, app_id, tx_id, 
                        date, sender, action, g_user_id, g_book_id, g_status, 
                        g_params, l_book_hash, l_research_hash, l_params
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """, 
                tx_data.get('user_id'), 
                tx_data.get('book_id'), 
                app_id,  # Converted to string
                tx_id,   # Handle both field names
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
                
                duration = time.time() - start_time
                track_db_operation("save_transaction", True, duration)
                logger.info(f"Saved transaction to crypto.txs: {tx_id or 'UNKNOWN'}")
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_transaction", False, duration)
            logger.error(f"Error saving transaction to crypto.txs: {e}")
            logger.error(f"Transaction data keys: {list(tx_data.keys()) if tx_data else 'None'}")
            return False

    async def save_supplemental_data(self, supplemental_data: Dict[str, Any]) -> bool:
        """Save supplemental data to crypto.supplemental table"""
        start_time = time.time()
        try:
            # Convert app_id to string and handle both old/new field names
            app_id = supplemental_data.get('app_id') or supplemental_data.get('contract_id')
            if app_id is not None:
                app_id = str(app_id)
                
            tx_id = supplemental_data.get('tx_id') or supplemental_data.get('transaction_id')
            
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO crypto.supplemental (
                        user_id, fund_id, app_id, tx_id, date,
                        conviction_file_path, conviction_file_encoded, research_file_path, 
                        research_file_encoded, notes, notes_encoded
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, 
                supplemental_data.get('user_id'), 
                supplemental_data.get('fund_id'), 
                app_id,  # Converted to string
                tx_id,   # Handle both field names
                supplemental_data.get('date'), 
                supplemental_data.get('conviction_file_path'), 
                supplemental_data.get('conviction_file_encoded'), 
                supplemental_data.get('research_file_path'), 
                supplemental_data.get('research_file_encoded'), 
                supplemental_data.get('notes'), 
                supplemental_data.get('notes_encoded')
                )
                
                duration = time.time() - start_time
                track_db_operation("save_supplemental_data", True, duration)
                logger.info(f"Saved supplemental data: {tx_id or 'UNKNOWN'}")
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_supplemental_data", False, duration)
            logger.error(f"Error saving supplemental data: {e}")
            logger.error(f"Supplemental data keys: {list(supplemental_data.keys()) if supplemental_data else 'None'}")
            return False

    async def get_user_transactions(self, user_id: str, book_id: str = None) -> List[Dict[str, Any]]:
        """Get transactions for a user, optionally filtered by book"""
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

    async def get_supplemental_data(self, user_id: str = None, fund_id: str = None, tx_id: str = None) -> List[Dict[str, Any]]:
        """Get supplemental data with optional filters"""
        pool = await self.db_pool.get_pool()
        
        conditions = []
        params = []
        param_counter = 1
        
        if user_id:
            conditions.append(f"user_id = ${param_counter}")
            params.append(user_id)
            param_counter += 1
            
        if fund_id:
            conditions.append(f"fund_id = ${param_counter}")
            params.append(fund_id)
            param_counter += 1
            
        if tx_id:
            conditions.append(f"tx_id = ${param_counter}")
            params.append(tx_id)
            param_counter += 1
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT * FROM crypto.supplemental
        {where_clause}
        ORDER BY date DESC
        """
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [ensure_json_serializable(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting supplemental data: {e}")
            return []