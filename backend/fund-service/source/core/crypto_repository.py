# source/db/crypto_repository.py
import logging
import time
import uuid
import json
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('crypto_repository')

class CryptoRepository:
    """Data access layer for crypto-related operations"""

    def __init__(self):
        """Initialize the crypto repository"""
        self.db_pool = DatabasePool()

    async def get_or_create_contract(self, user_id: str, book_id: str, app_id: str = "conviction_app") -> str:
        """
        Get existing contract or create a new one for the user/book combination
        
        Args:
            user_id: User ID
            book_id: Book ID  
            app_id: Application ID
            
        Returns:
            Contract ID
        """
        pool = await self.db_pool.get_pool()
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Try to find existing active contract
                existing_query = """
                SELECT contract_id FROM crypto.contracts 
                WHERE user_id = $1 AND book_id = $2 AND app_id = $3 AND status = 'ACTIVE'
                ORDER BY active_at DESC
                LIMIT 1
                """
                
                existing = await conn.fetchval(existing_query, user_id, book_id, app_id)
                
                if existing:
                    duration = time.time() - start_time
                    track_db_operation("get_contract", True, duration)
                    logger.info(f"Found existing contract {existing} for user {user_id} book {book_id}")
                    return str(existing)
                
                # Create new contract
                contract_id = str(uuid.uuid4())
                app_address = f"contract_{app_id}_{contract_id[:8]}"
                
                create_query = """
                INSERT INTO crypto.contracts (
                    contract_id, user_id, book_id, app_id, app_address, 
                    parameters, status, blockchain_status, active_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, 'ACTIVE', 'Active', NOW()
                ) RETURNING contract_id
                """
                
                created_contract_id = await conn.fetchval(
                    create_query,
                    contract_id, user_id, book_id, app_id, app_address,
                    json.dumps({"created_for": "conviction_orders", "created_at": time.time()})
                )
                
                duration = time.time() - start_time
                track_db_operation("create_contract", True, duration)
                logger.info(f"Created new contract {created_contract_id} for user {user_id} book {book_id}")
                return str(created_contract_id)
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_or_create_contract", False, duration)
            logger.error(f"Error getting/creating contract: {e}")
            raise

    async def create_crypto_transaction(self, user_id: str, book_id: str, contract_id: str, 
                                      app_id: str, action: str, research_file_path: str = None,
                                      research_file_encoded: str = None, notes: str = None,
                                      notes_encoded: str = None) -> str:
        """
        Create transaction records in both crypto.txs and crypto.supplemental
        
        Args:
            user_id: User ID
            book_id: Book ID
            contract_id: Contract ID
            app_id: Application ID
            action: Action type (SUBMIT/CANCEL)
            research_file_path: Path to research file
            research_file_encoded: Encoded research file data
            notes: Notes text
            notes_encoded: Encoded notes
            
        Returns:
            Transaction ID
        """
        pool = await self.db_pool.get_pool()
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Generate transaction ID and other required fields
                    tx_id = str(uuid.uuid4())
                    transaction_id = f"tx_{int(time.time())}_{tx_id[:8]}"
                    
                    # Insert into crypto.txs
                    txs_query = """
                    INSERT INTO crypto.txs (
                        tx_id, user_id, book_id, contract_id, app_id, transaction_id, 
                        date, sender, action, g_user_id, g_book_id, g_status, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9, $10, 'PENDING', NOW()
                    ) RETURNING tx_id
                    """
                    
                    created_tx_id = await conn.fetchval(
                        txs_query,
                        tx_id, user_id, book_id, contract_id, app_id, transaction_id,
                        user_id,  # sender
                        action,   # action (SUBMIT/CANCEL)
                        user_id,  # g_user_id
                        book_id   # g_book_id
                    )
                    
                    # Insert into crypto.supplemental if we have additional data
                    if research_file_path or research_file_encoded or notes or notes_encoded:
                        # Get fund_id - we need to find which fund this book belongs to
                        fund_query = """
                        SELECT f.fund_id 
                        FROM fund.funds f
                        JOIN fund.books b ON f.user_id = b.user_id
                        WHERE b.book_id = $1
                        LIMIT 1
                        """
                        fund_result = await conn.fetchrow(fund_query, book_id)
                        
                        if fund_result:
                            fund_id = fund_result['fund_id']
                            
                            supplemental_query = """
                            INSERT INTO crypto.supplemental (
                                tx_id, user_id, fund_id, contract_id, app_id, transaction_id, date,
                                research_file_path, research_file_encoded, notes, notes_encoded
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9, $10
                            )
                            """
                            
                            await conn.execute(
                                supplemental_query,
                                tx_id, user_id, fund_id, contract_id, app_id, transaction_id,
                                research_file_path, research_file_encoded, notes, notes_encoded
                            )
                            
                            logger.info(f"Created supplemental data for transaction {tx_id}")
                        else:
                            logger.warning(f"Could not find fund for book {book_id}, skipping supplemental data")
                    
                    duration = time.time() - start_time
                    track_db_operation("create_crypto_transaction", True, duration)
                    logger.info(f"Created crypto transaction {tx_id} for {action} operation")
                    return str(created_tx_id)
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_crypto_transaction", False, duration)
            logger.error(f"Error creating crypto transaction: {e}")
            raise

    async def get_contract_by_id(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Get contract details by ID"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM crypto.contracts 
        WHERE contract_id = $1 AND status = 'ACTIVE'
        """
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, contract_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting contract {contract_id}: {e}")
            return None

    async def get_user_contracts(self, user_id: str, book_id: str = None) -> list:
        """Get all contracts for a user, optionally filtered by book"""
        pool = await self.db_pool.get_pool()
        
        if book_id:
            query = """
            SELECT * FROM crypto.contracts 
            WHERE user_id = $1 AND book_id = $2 AND status = 'ACTIVE'
            ORDER BY active_at DESC
            """
            params = [user_id, book_id]
        else:
            query = """
            SELECT * FROM crypto.contracts 
            WHERE user_id = $1 AND status = 'ACTIVE'
            ORDER BY active_at DESC
            """
            params = [user_id]
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting user contracts: {e}")
            return []

    async def get_transaction_details(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """Get complete transaction details including supplemental data"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 
            t.*,
            s.research_file_path, s.research_file_encoded,
            s.notes, s.notes_encoded
        FROM crypto.txs t
        LEFT JOIN crypto.supplemental s ON t.tx_id = s.tx_id
        WHERE t.tx_id = $1
        """
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, tx_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting transaction details {tx_id}: {e}")
            return None

    async def update_transaction_status(self, tx_id: str, status: str, 
                                      g_params: str = None) -> bool:
        """Update transaction status"""
        pool = await self.db_pool.get_pool()
        
        query = """
        UPDATE crypto.txs 
        SET g_status = $2, g_params = COALESCE($3, g_params)
        WHERE tx_id = $1
        """
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(query, tx_id, status, g_params)
                logger.info(f"Updated transaction {tx_id} status to {status}")
                return True
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            return False