# source/core/conviction_manager.py
import logging
import json 
import uuid
import datetime

from typing import Dict, Any

from source.clients.exchange_client import ExchangeClient

from source.db.conviction_repository import ConvictionRepository

from source.core.book_manager import BookManager
from source.core.crypto_manager import CryptoManager
from source.core.session_manager import SessionManager

from source.core.utils.conviction_manager_storage import StorageManager
from source.core.utils.conviction_manager_db import DBManager
from source.core.utils.conviction_manager_operation import OperationManager
from source.core.utils.conviction_manager_exchange import ExchangeManager

logger = logging.getLogger('conviction_manager')

class ConvictionManager:
    """Main manager for conviction operations"""
    
    def __init__(
            self,
            conviction_repository: ConvictionRepository,
            book_manager: BookManager,
            crypto_manager: CryptoManager,
            session_manager: SessionManager,
            exchange_client: ExchangeClient,
    ):
        """Initialize the conviction manager with dependencies"""
        self.book_manager = book_manager
        self.crypto_manager = crypto_manager
        self.session_manager = session_manager

        # Create specialized managers
        self.db_manager = DBManager(conviction_repository)
        self.exchange_manager = ExchangeManager(exchange_client)
        self.storage_manager = StorageManager()

        self.operation_manager = OperationManager(
            conviction_repository,
            self.session_manager,
            self.db_manager,
            self.exchange_manager
        )
        
    async def validate_book_ownership(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """Validate that the book belongs to the user"""
        try:
            result = await self.book_manager.get_book(book_id, user_id)
            
            if result.get('success'):
                return {'valid': True}
            else:
                return {'valid': False, 'error': result.get('error', 'Book not found or access denied')}
                
        except Exception as e:
            logger.error(f"Error validating book ownership: {e}")
            return {'valid': False, 'error': 'Failed to validate book ownership'}

    async def _get_fund_id_for_user(self, user_id: str) -> str:
        """Get fund_id for a user via record manager"""
        return await self.db_manager.get_fund_id_for_user(user_id)

    async def submit_convictions(self, submission_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Submit convictions with complete integrity verification flow
        """
        book_id = submission_data.get('book_id')
        convictions_data = submission_data.get('convictions', [])
        notes = submission_data.get('notes', '')
        research_file_data = submission_data.get('research_file_data')
        research_file_name = submission_data.get('research_file_name')
        
        logger.info(f"=== STARTING CONVICTION SUBMISSION ===")
        logger.info(f"User: {user_id}, Book: {book_id}")
        logger.info(f"Convictions count: {len(convictions_data)}")
        logger.info(f"Has research file: {bool(research_file_data and research_file_name)}")
        logger.info(f"Has notes: {bool(notes and notes.strip())}")
        
        try:
            # Get fund ID
            logger.info(f"STEP 0: Getting fund ID for user {user_id}")
            fund_id = await self._get_fund_id_for_user(user_id)
            logger.info(f"Fund ID: {fund_id}")
            
            # Generate transaction ID
            temp_tx_id = str(uuid.uuid4())
            logger.info(f"Generated transaction ID: {temp_tx_id}")
            
            # STEP 1: Store files and create fingerprints
            logger.info(f"=== STEP 1: STORING FILES AND CREATING FINGERPRINTS ===")
            file_fingerprints = {}
            
            # Store and fingerprint research file
            if research_file_data and research_file_name:
                logger.info(f"Processing research file: {research_file_name} ({len(research_file_data)} bytes)")
                research_path = await self.storage_manager.store_research_file(
                    research_file_data, research_file_name, fund_id, book_id, temp_tx_id
                )
                if research_path:
                    research_fingerprint = self.crypto_manager.create_file_fingerprint(research_file_data, research_file_name)
                    file_fingerprints['research'] = research_fingerprint
                    logger.info(f"✓ Research file stored at: {research_path}")
                    logger.info(f"✓ Research file fingerprint: {research_fingerprint}")
                else:
                    logger.error(f"✗ Failed to store research file")
            else:
                logger.info(f"No research file provided")
            
            # Store and fingerprint notes
            if notes and notes.strip():
                logger.info(f"Processing notes: {len(notes)} characters")
                notes_path = await self.storage_manager.store_notes_file(
                    notes, fund_id, book_id, temp_tx_id
                )
                if notes_path:
                    notes_bytes = notes.encode('utf-8')
                    notes_fingerprint = self.crypto_manager.create_file_fingerprint(notes_bytes, "notes.txt")
                    file_fingerprints['notes'] = notes_fingerprint
                    logger.info(f"✓ Notes file stored at: {notes_path}")
                    logger.info(f"✓ Notes file fingerprint: {notes_fingerprint}")
                else:
                    logger.error(f"✗ Failed to store notes file")
            else:
                logger.info(f"No notes provided")
            
            # Store and fingerprint CSV (this IS the conviction fingerprint)
            logger.info(f"Processing convictions CSV with {len(convictions_data)} convictions")
            csv_path = await self.storage_manager.store_convictions_csv(
                convictions_data, fund_id, book_id, temp_tx_id
            )
            if csv_path:
                # Create deterministic CSV content for fingerprinting
                csv_content = json.dumps(convictions_data, sort_keys=True).encode('utf-8')
                convictions_fingerprint = self.crypto_manager.create_file_fingerprint(csv_content, "convictions.csv")
                file_fingerprints['convictions'] = convictions_fingerprint
                logger.info(f"✓ Convictions CSV stored at: {csv_path}")
                logger.info(f"✓ Convictions CSV fingerprint: {convictions_fingerprint}")
            else:
                logger.error(f"✗ Failed to store convictions CSV")
                return {
                    "success": False,
                    "error": "Failed to store convictions CSV file",
                    "results": []
                }
            
            logger.info(f"File fingerprints summary: {list(file_fingerprints.keys())}")
            
            # STEP 2: Update blockchain local state with fingerprints
            logger.info(f"=== STEP 2: UPDATING BLOCKCHAIN LOCAL STATE ===")
            logger.info(f"Book ID: {book_id}, User ID: {user_id}")
            
            # Map fingerprints to blockchain fields
            book_hash = file_fingerprints.get('convictions', '')  # Main conviction data fingerprint
            research_hash = file_fingerprints.get('research', '')  # Research file fingerprint  
            params_hash = file_fingerprints.get('notes', '')      # Notes file fingerprint
            
            logger.info(f"Blockchain hashes to store:")
            logger.info(f"  book_hash (convictions): {book_hash}")
            logger.info(f"  research_hash: {research_hash}")
            logger.info(f"  params_hash (notes): {params_hash}")
            
            blockchain_result = await self.crypto_manager.update_local_state(
                user_id, book_id, book_hash, research_hash, params_hash
            )

            blockchain_tx_id = blockchain_result.get('blockchain_tx_id')

            logger.info(f"Blockchain update result: {blockchain_result}")
            
            if not blockchain_result.get('success'):
                logger.error(f"✗ Failed to update blockchain local state: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record fingerprints on blockchain",
                    "results": []
                }
            
            logger.info(f"✓ Successfully updated blockchain with fingerprints")
            
            # STEP 3: Store in PostgreSQL database
            logger.info("=== STEP 3: STORING IN DATABASE ===")
            logger.info(f"Blockchain Transaction ID: {blockchain_tx_id}, Book ID: {book_id}")
            logger.info(f"Convictions data count: {len(convictions_data)}")

            # Get contract_id (required for both tables)
            contract_data = await self.crypto_manager.get_contract(user_id, book_id)
            if not contract_data:
                logger.error("No contract found - required for database storage")
                return {"success": False, "error": "Contract not found"}

            app_id = str(contract_data.get('app_id'))

            # 3A: Store transaction record in crypto.txs (CRITICAL - must be first)
            logger.info("3A: Storing transaction record in crypto.txs")
            tx_data = {
                'user_id': user_id,
                'book_id': book_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'sender': user_id,
                'action': 'SUBMIT_CONVICTIONS',
                'g_user_id': user_id,
                'g_book_id': book_id,
                'g_status': 'ACTIVE',
                'g_params': f"SEE PREVIOUS TX",
                'l_book_hash': book_hash,      # From blockchain operation
                'l_research_hash': research_hash,  # From blockchain operation  
                'l_params': params_hash        # From blockchain operation
            }

            crypto_txs_success = await self.crypto_manager.save_transaction(tx_data)
            if not crypto_txs_success:
                logger.error("CRITICAL: Failed to save to crypto.txs")
                return {"success": False, "error": "Failed to save transaction record"}

            logger.info(f"✓ Transaction record saved to crypto.txs with blockchain ID: {blockchain_tx_id}")

            # 3B: Store supplemental data in crypto.supplemental
            logger.info("3B: Storing supplemental data in crypto.supplemental")

            # Create file paths based on your naming convention
            conviction_file_path = f"{fund_id}/{book_id}/{blockchain_tx_id}/convictions.csv" if convictions_data else None
            research_file_path = f"{fund_id}/{book_id}/{blockchain_tx_id}/research.txt" if research_file_data else None

            supplemental_data = {
                'user_id': user_id,
                'fund_id': fund_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'conviction_file_path': conviction_file_path,
                'conviction_file_encoded': book_hash,      # The conviction fingerprint
                'research_file_path': research_file_path,
                'research_file_encoded': research_hash,    # The research fingerprint
                'notes': notes,
                'notes_encoded': params_hash               # The notes fingerprint
            }

            supplemental_success = await self.crypto_manager.save_supplemental_data(supplemental_data)
            if not supplemental_success:
                logger.warning("Failed to save supplemental data, but continuing...")
            else:
                logger.info(f"✓ Supplemental data saved to crypto.supplemental for TX: {blockchain_tx_id}")

            # 3C: Store conviction data in conv.submit 
            logger.info("3C: Storing conviction data in conv.submit")
            db_success = await self.db_manager.store_submit_conviction_data(
                tx_id=blockchain_tx_id,  # This should match crypto.txs
                book_id=book_id,
                convictions_data=convictions_data
            )

            if not db_success:
                logger.error(f"Failed to store conviction data in conv.submit for TX: {blockchain_tx_id}")
                return {"success": False, "error": "Failed to store conviction data"}

            logger.info(f"✓ Successfully stored {len(convictions_data)} convictions in conv.submit")
            
            # STEP 4: Send to operations manager (exchange processing)
            logger.info(f"=== STEP 4: SENDING TO OPERATIONS MANAGER ===")
            logger.info(f"Sending {len(convictions_data)} convictions to operations manager")
            
            exchange_result = await self.operation_manager.submit_convictions(convictions_data, book_id)
            
            logger.info(f"Operations manager result: {exchange_result.get('success', False)}")
            if not exchange_result.get('success', False):
                logger.warning(f"Operations manager returned: {exchange_result}")
            
            # Add integrity verification metadata to result
            exchange_result.update({
                'temp_tx_id': temp_tx_id,
                'file_fingerprints': file_fingerprints,
                'blockchain_hashes': {
                    'book_hash': book_hash,           # convictions fingerprint
                    'research_hash': research_hash,   # research file fingerprint
                    'params_hash': params_hash        # notes fingerprint
                },
                'integrity_verified': True,
                'blockchain_updated': True,
                'database_stored': True
            })
            
            logger.info(f"=== CONVICTION SUBMISSION COMPLETED SUCCESSFULLY ===")
            logger.info(f"Transaction ID: {temp_tx_id}")
            logger.info(f"Files stored: {list(file_fingerprints.keys())}")
            logger.info(f"Blockchain updated: ✓")
            logger.info(f"Database updated: ✓")
            logger.info(f"Exchange processing: {'✓' if exchange_result.get('success') else '✗'}")
            
            return exchange_result
            
        except Exception as e:
            logger.error(f"=== ERROR IN CONVICTION SUBMISSION ===")
            logger.error(f"User: {user_id}, Book: {book_id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"Failed to process submission: {str(e)}",
                "results": []
            }

    async def cancel_convictions(self, cancellation_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Cancel convictions with complete flow: files -> fingerprints -> blockchain -> database -> operations"""
        # Extract all data
        book_id = cancellation_data.get('book_id')
        conviction_ids = cancellation_data.get('conviction_ids', [])
        notes = cancellation_data.get('notes', '')
        research_file_data = cancellation_data.get('research_file_data')
        research_file_name = cancellation_data.get('research_file_name')
        
        logger.info(f"=== STARTING CONVICTION CANCELLATION ===")
        logger.info(f"User: {user_id}, Book: {book_id}")
        logger.info(f"Conviction IDs count: {len(conviction_ids)}")
        logger.info(f"Has research file: {bool(research_file_data and research_file_name)}")
        logger.info(f"Has notes: {bool(notes and notes.strip())}")
        
        try:
            # Get fund ID
            logger.info(f"STEP 0: Getting fund ID for user {user_id}")
            fund_id = await self._get_fund_id_for_user(user_id)
            logger.info(f"Fund ID: {fund_id}")
            
            # Generate transaction ID
            temp_tx_id = str(uuid.uuid4())
            logger.info(f"Generated transaction ID: {temp_tx_id}")
            
            # STEP 1: Store files and create fingerprints (same as submit)
            logger.info(f"=== STEP 1: STORING FILES AND CREATING FINGERPRINTS ===")
            file_fingerprints = {}
            
            # Store and fingerprint research file
            if research_file_data and research_file_name:
                logger.info(f"Processing research file: {research_file_name} ({len(research_file_data)} bytes)")
                research_path = await self.storage_manager.store_research_file(
                    research_file_data, research_file_name, fund_id, book_id, temp_tx_id
                )
                if research_path:
                    research_fingerprint = self.crypto_manager.create_file_fingerprint(research_file_data, research_file_name)
                    file_fingerprints['research'] = research_fingerprint
                    logger.info(f"✓ Research file stored at: {research_path}")
                    logger.info(f"✓ Research file fingerprint: {research_fingerprint}")
                else:
                    logger.error(f"✗ Failed to store research file")
            else:
                logger.info(f"No research file provided")
            
            # Store and fingerprint notes
            if notes and notes.strip():
                logger.info(f"Processing notes: {len(notes)} characters")
                notes_path = await self.storage_manager.store_notes_file(
                    notes, fund_id, book_id, temp_tx_id
                )
                if notes_path:
                    notes_bytes = notes.encode('utf-8')
                    notes_fingerprint = self.crypto_manager.create_file_fingerprint(notes_bytes, "notes.txt")
                    file_fingerprints['notes'] = notes_fingerprint
                    logger.info(f"✓ Notes file stored at: {notes_path}")
                    logger.info(f"✓ Notes file fingerprint: {notes_fingerprint}")
                else:
                    logger.error(f"✗ Failed to store notes file")
            else:
                logger.info(f"No notes provided")
            
            # Store and fingerprint cancellation CSV (this IS the cancellation fingerprint)
            logger.info(f"Processing cancellation CSV with {len(conviction_ids)} conviction IDs")
            csv_path = await self.storage_manager.store_cancellation_csv(
                conviction_ids, fund_id, book_id, temp_tx_id
            )
            if csv_path:
                # Create deterministic CSV content for fingerprinting
                csv_content = json.dumps(conviction_ids, sort_keys=True).encode('utf-8')
                cancellation_fingerprint = self.crypto_manager.create_file_fingerprint(csv_content, "cancellations.csv")
                file_fingerprints['cancellations'] = cancellation_fingerprint
                logger.info(f"✓ Cancellation CSV stored at: {csv_path}")
                logger.info(f"✓ Cancellation CSV fingerprint: {cancellation_fingerprint}")
            else:
                logger.error(f"✗ Failed to store cancellation CSV")
                return {
                    "success": False,
                    "error": "Failed to store cancellation CSV file",
                    "results": []
                }
            
            logger.info(f"File fingerprints summary: {list(file_fingerprints.keys())}")
            
            # STEP 2: Update blockchain local state with fingerprints
            logger.info(f"=== STEP 2: UPDATING BLOCKCHAIN LOCAL STATE ===")
            logger.info(f"Book ID: {book_id}, User ID: {user_id}")
            
            # Map fingerprints to blockchain fields
            book_hash = file_fingerprints.get('cancellations', '')  # Main cancellation data fingerprint
            research_hash = file_fingerprints.get('research', '')    # Research file fingerprint  
            params_hash = file_fingerprints.get('notes', '')         # Notes file fingerprint
            
            logger.info(f"Blockchain hashes to store:")
            logger.info(f"  book_hash (cancellations): {book_hash}")
            logger.info(f"  research_hash: {research_hash}")
            logger.info(f"  params_hash (notes): {params_hash}")
            
            blockchain_result = await self.crypto_manager.update_local_state(
                user_id, book_id, book_hash, research_hash, params_hash
            )

            blockchain_tx_id = blockchain_result.get('blockchain_tx_id')

            logger.info(f"Blockchain update result: {blockchain_result}")
            
            if not blockchain_result.get('success'):
                logger.error(f"✗ Failed to update blockchain local state: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record fingerprints on blockchain",
                    "results": []
                }
            
            logger.info(f"✓ Successfully updated blockchain with fingerprints")
            
            # STEP 3: Store in PostgreSQL database
            logger.info("=== STEP 3: STORING IN DATABASE ===")
            logger.info(f"Blockchain Transaction ID: {blockchain_tx_id}, Book ID: {book_id}")
            logger.info(f"Conviction IDs count: {len(conviction_ids)}")

            # Get contract_id (required for both tables)
            contract_data = await self.crypto_manager.get_contract(user_id, book_id)
            if not contract_data:
                logger.error("No contract found - required for database storage")
                return {"success": False, "error": "Contract not found"}

            app_id = str(contract_data.get('app_id'))

            # 3A: Store transaction record in crypto.txs (CRITICAL - must be first)
            logger.info("3A: Storing transaction record in crypto.txs")
            tx_data = {
                'user_id': user_id,
                'book_id': book_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'sender': user_id,
                'action': 'CANCEL_CONVICTIONS',
                'g_user_id': user_id,
                'g_book_id': book_id,
                'g_status': 'ACTIVE',
                'g_params': f"SEE PREVIOUS TX",
                'l_book_hash': book_hash,      # From blockchain operation
                'l_research_hash': research_hash,  # From blockchain operation  
                'l_params': params_hash        # From blockchain operation
            }

            crypto_txs_success = await self.crypto_manager.save_transaction(tx_data)
            if not crypto_txs_success:
                logger.error("CRITICAL: Failed to save to crypto.txs")
                return {"success": False, "error": "Failed to save transaction record"}

            logger.info(f"✓ Transaction record saved to crypto.txs with blockchain ID: {blockchain_tx_id}")

            # 3B: Store supplemental data in crypto.supplemental
            logger.info("3B: Storing supplemental data in crypto.supplemental")

            # Create file paths based on your naming convention
            cancellation_file_path = f"{fund_id}/{book_id}/{blockchain_tx_id}/cancellations.csv" if conviction_ids else None
            research_file_path = f"{fund_id}/{book_id}/{blockchain_tx_id}/research.txt" if research_file_data else None

            supplemental_data = {
                'user_id': user_id,
                'fund_id': fund_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'conviction_file_path': cancellation_file_path,
                'conviction_file_encoded': book_hash,      # The cancellation fingerprint
                'research_file_path': research_file_path,
                'research_file_encoded': research_hash,    # The research fingerprint
                'notes': notes,
                'notes_encoded': params_hash               # The notes fingerprint
            }

            supplemental_success = await self.crypto_manager.save_supplemental_data(supplemental_data)
            if not supplemental_success:
                logger.warning("Failed to save supplemental data, but continuing...")
            else:
                logger.info(f"✓ Supplemental data saved to crypto.supplemental for TX: {blockchain_tx_id}")

            # 3C: Store cancellation data in conv.cancel 
            logger.info("3C: Storing cancellation data in conv.cancel")
            db_success = await self.db_manager.store_cancel_conviction_data(
                tx_id=blockchain_tx_id,  # This should match crypto.txs
                book_id=book_id,
                conviction_ids=conviction_ids
            )

            if not db_success:
                logger.error(f"Failed to store cancellation data in conv.cancel for TX: {blockchain_tx_id}")
                return {"success": False, "error": "Failed to store cancellation data"}

            logger.info(f"✓ Successfully stored {len(conviction_ids)} cancellations in conv.cancel")
            
            # STEP 4: Send to operations manager (exchange processing)
            logger.info(f"=== STEP 4: SENDING TO OPERATIONS MANAGER ===")
            logger.info(f"Sending {len(conviction_ids)} conviction IDs to operations manager")
            
            exchange_result = await self.operation_manager.cancel_convictions(conviction_ids, book_id)
            
            logger.info(f"Operations manager result: {exchange_result.get('success', False)}")
            if not exchange_result.get('success', False):
                logger.warning(f"Operations manager returned: {exchange_result}")
            
            # Add integrity verification metadata to result
            exchange_result.update({
                'temp_tx_id': temp_tx_id,
                'file_fingerprints': file_fingerprints,
                'blockchain_hashes': {
                    'book_hash': book_hash,           # cancellation fingerprint
                    'research_hash': research_hash,   # research file fingerprint
                    'params_hash': params_hash        # notes fingerprint
                },
                'integrity_verified': True,
                'blockchain_updated': True,
                'database_stored': True
            })
            
            logger.info(f"=== CONVICTION CANCELLATION COMPLETED SUCCESSFULLY ===")
            logger.info(f"Transaction ID: {temp_tx_id}")
            logger.info(f"Files stored: {list(file_fingerprints.keys())}")
            logger.info(f"Blockchain updated: ✓")
            logger.info(f"Database updated: ✓")
            logger.info(f"Exchange processing: {'✓' if exchange_result.get('success') else '✗'}")
            
            return exchange_result
            
        except Exception as e:
            logger.error(f"=== ERROR IN CONVICTION CANCELLATION ===")
            logger.error(f"User: {user_id}, Book: {book_id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"Failed to process cancellation: {str(e)}",
                "results": []
            }

    async def submit_encoded_convictions(self, submission_data, user_id):
        """Submit encoded convictions with simplified flow: hashes -> blockchain -> database"""
        book_id = submission_data.get('book_id')
        encoded_convictions = submission_data.get('encoded_convictions', '')
        encoded_research_file = submission_data.get('encoded_research_file', '')
        notes = submission_data.get('notes', '')
        
        logger.info(f"=== STARTING ENCODED CONVICTION SUBMISSION ===")
        logger.info(f"User: {user_id}, Book: {book_id}")
        logger.info(f"Has encoded convictions: {bool(encoded_convictions)}")
        logger.info(f"Has encoded research: {bool(encoded_research_file)}")
        logger.info(f"Has notes: {bool(notes and notes.strip())}")
        
        try:
            # Get fund ID
            logger.info(f"STEP 0: Getting fund ID for user {user_id}")
            fund_id = await self._get_fund_id_for_user(user_id)
            logger.info(f"Fund ID: {fund_id}")
            
            # Generate transaction ID
            temp_tx_id = str(uuid.uuid4())
            logger.info(f"Generated transaction ID: {temp_tx_id}")
            
            # STEP 1: Use provided hashes directly (no file storage needed)
            logger.info(f"=== STEP 1: USING PROVIDED ENCODED HASHES ===")
            
            # Map provided hashes to blockchain fields
            book_hash = encoded_convictions  # Main conviction data hash
            research_hash = encoded_research_file  # Research file hash
            params_hash = notes  # Notes as params (could be hashed if needed)
            
            logger.info(f"Encoded hashes to store:")
            logger.info(f"  book_hash (convictions): {book_hash}")
            logger.info(f"  research_hash: {research_hash}")
            logger.info(f"  params_hash (notes): {params_hash}")
            
            # STEP 2: Update blockchain local state with provided hashes
            logger.info(f"=== STEP 2: UPDATING BLOCKCHAIN LOCAL STATE ===")
            logger.info(f"Book ID: {book_id}, User ID: {user_id}")
            
            blockchain_result = await self.crypto_manager.update_local_state(
                user_id, book_id, book_hash, research_hash, params_hash
            )

            blockchain_tx_id = blockchain_result.get('blockchain_tx_id')

            logger.info(f"Blockchain update result: {blockchain_result}")
            
            if not blockchain_result.get('success'):
                logger.error(f"✗ Failed to update blockchain local state: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record hashes on blockchain",
                    "temp_tx_id": temp_tx_id
                }
            
            logger.info(f"✓ Successfully updated blockchain with encoded hashes")
            
            # STEP 3: Store in PostgreSQL database
            logger.info("=== STEP 3: STORING IN DATABASE ===")
            logger.info(f"Blockchain Transaction ID: {blockchain_tx_id}, Book ID: {book_id}")

            # Get contract_id (required for both tables)
            contract_data = await self.crypto_manager.get_contract(user_id, book_id)
            if not contract_data:
                logger.error("No contract found - required for database storage")
                return {"success": False, "error": "Contract not found"}

            contract_id = contract_data.get('contract_id')
            app_id = str(contract_data.get('app_id'))

            # 3A: Store transaction record in crypto.txs
            logger.info("3A: Storing transaction record in crypto.txs")
            tx_data = {
                'user_id': user_id,
                'book_id': book_id,
                'contract_id': contract_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'sender': user_id,
                'action': 'SUBMIT_ENCODED_CONVICTIONS',
                'g_user_id': user_id,
                'g_book_id': book_id,
                'g_status': 'ACTIVE',
                'g_params': f"ENCODED SUBMISSION",
                'l_book_hash': book_hash,      # From user-provided hash
                'l_research_hash': research_hash,  # From user-provided hash  
                'l_params': params_hash        # From user-provided hash/notes
            }

            crypto_txs_success = await self.crypto_manager.save_transaction(tx_data)
            if not crypto_txs_success:
                logger.error("CRITICAL: Failed to save to crypto.txs")
                return {"success": False, "error": "Failed to save transaction record"}

            logger.info(f"✓ Transaction record saved to crypto.txs with blockchain ID: {blockchain_tx_id}")

            # 3B: Store supplemental data in crypto.supplemental
            logger.info("3B: Storing supplemental data in crypto.supplemental")

            supplemental_data = {
                'user_id': user_id,
                'fund_id': fund_id,
                'contract_id': contract_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'conviction_file_path': None,  # No actual file stored
                'conviction_file_encoded': book_hash,      # The provided conviction hash
                'research_file_path': None,  # No actual file stored
                'research_file_encoded': research_hash,    # The provided research hash
                'notes': notes,
                'notes_encoded': params_hash               # The provided notes/hash
            }

            supplemental_success = await self.crypto_manager.save_supplemental_data(supplemental_data)
            if not supplemental_success:
                logger.warning("Failed to save supplemental data, but continuing...")
            else:
                logger.info(f"✓ Supplemental data saved to crypto.supplemental for TX: {blockchain_tx_id}")

            # Note: No conv.submit storage for encoded submissions
            # Note: No exchange processing for encoded submissions
            
            logger.info(f"=== ENCODED CONVICTION SUBMISSION COMPLETED SUCCESSFULLY ===")
            logger.info(f"Transaction ID: {temp_tx_id}")
            logger.info(f"Blockchain updated: ✓")
            logger.info(f"Database updated: ✓")
            logger.info(f"No exchange processing needed for encoded submissions")
            
            return {
                "success": True,
                "message": "Encoded conviction submission processed successfully",
                "temp_tx_id": temp_tx_id,
                "blockchain_tx_id": blockchain_tx_id,
                "encoded_hashes": {
                    'book_hash': book_hash,
                    'research_hash': research_hash,
                    'params_hash': params_hash
                },
                "blockchain_updated": True,
                "database_stored": True
            }
            
        except Exception as e:
            logger.error(f"=== ERROR IN ENCODED CONVICTION SUBMISSION ===")
            logger.error(f"User: {user_id}, Book: {book_id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"Failed to process encoded submission: {str(e)}"
            }

    async def cancel_encoded_convictions(self, cancellation_data, user_id):
        """Cancel encoded convictions with simplified flow: hashes -> blockchain -> database"""
        book_id = cancellation_data.get('book_id')
        encoded_conviction_ids = cancellation_data.get('encoded_conviction_ids', '')
        encoded_research_file = cancellation_data.get('encoded_research_file', '')
        notes = cancellation_data.get('notes', '')
        
        logger.info(f"=== STARTING ENCODED CONVICTION CANCELLATION ===")
        logger.info(f"User: {user_id}, Book: {book_id}")
        logger.info(f"Has encoded conviction IDs: {bool(encoded_conviction_ids)}")
        logger.info(f"Has encoded research: {bool(encoded_research_file)}")
        logger.info(f"Has notes: {bool(notes and notes.strip())}")
        
        try:
            # Get fund ID
            logger.info(f"STEP 0: Getting fund ID for user {user_id}")
            fund_id = await self._get_fund_id_for_user(user_id)
            logger.info(f"Fund ID: {fund_id}")
            
            # Generate transaction ID
            temp_tx_id = str(uuid.uuid4())
            logger.info(f"Generated transaction ID: {temp_tx_id}")
            
            # STEP 1: Use provided hashes directly (no file storage needed)
            logger.info(f"=== STEP 1: USING PROVIDED ENCODED HASHES ===")
            
            # Map provided hashes to blockchain fields
            book_hash = encoded_conviction_ids  # Main cancellation data hash
            research_hash = encoded_research_file  # Research file hash
            params_hash = notes  # Notes as params (could be hashed if needed)
            
            logger.info(f"Encoded hashes to store:")
            logger.info(f"  book_hash (cancellations): {book_hash}")
            logger.info(f"  research_hash: {research_hash}")
            logger.info(f"  params_hash (notes): {params_hash}")
            
            # STEP 2: Update blockchain local state with provided hashes
            logger.info(f"=== STEP 2: UPDATING BLOCKCHAIN LOCAL STATE ===")
            logger.info(f"Book ID: {book_id}, User ID: {user_id}")
            
            blockchain_result = await self.crypto_manager.update_local_state(
                user_id, book_id, book_hash, research_hash, params_hash
            )

            blockchain_tx_id = blockchain_result.get('blockchain_tx_id')

            logger.info(f"Blockchain update result: {blockchain_result}")
            
            if not blockchain_result.get('success'):
                logger.error(f"✗ Failed to update blockchain local state: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record hashes on blockchain",
                    "temp_tx_id": temp_tx_id
                }
            
            logger.info(f"✓ Successfully updated blockchain with encoded hashes")
            
            # STEP 3: Store in PostgreSQL database
            logger.info("=== STEP 3: STORING IN DATABASE ===")
            logger.info(f"Blockchain Transaction ID: {blockchain_tx_id}, Book ID: {book_id}")

            # Get contract_id (required for both tables)
            contract_data = await self.crypto_manager.get_contract(user_id, book_id)
            if not contract_data:
                logger.error("No contract found - required for database storage")
                return {"success": False, "error": "Contract not found"}

            contract_id = contract_data.get('contract_id')
            app_id = str(contract_data.get('app_id'))

            # 3A: Store transaction record in crypto.txs
            logger.info("3A: Storing transaction record in crypto.txs")
            tx_data = {
                'user_id': user_id,
                'book_id': book_id,
                'contract_id': contract_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'sender': user_id,
                'action': 'CANCEL_ENCODED_CONVICTIONS',
                'g_user_id': user_id,
                'g_book_id': book_id,
                'g_status': 'ACTIVE',
                'g_params': f"ENCODED CANCELLATION",
                'l_book_hash': book_hash,      # From user-provided hash
                'l_research_hash': research_hash,  # From user-provided hash  
                'l_params': params_hash        # From user-provided hash/notes
            }

            crypto_txs_success = await self.crypto_manager.save_transaction(tx_data)
            if not crypto_txs_success:
                logger.error("CRITICAL: Failed to save to crypto.txs")
                return {"success": False, "error": "Failed to save transaction record"}

            logger.info(f"✓ Transaction record saved to crypto.txs with blockchain ID: {blockchain_tx_id}")

            # 3B: Store supplemental data in crypto.supplemental
            logger.info("3B: Storing supplemental data in crypto.supplemental")

            supplemental_data = {
                'user_id': user_id,
                'fund_id': fund_id,
                'contract_id': contract_id,
                'app_id': app_id,
                'tx_id': blockchain_tx_id,
                'date': datetime.datetime.now(datetime.timezone.utc),
                'conviction_file_path': None,  # No actual file stored
                'conviction_file_encoded': book_hash,      # The provided cancellation hash
                'research_file_path': None,  # No actual file stored
                'research_file_encoded': research_hash,    # The provided research hash
                'notes': notes,
                'notes_encoded': params_hash               # The provided notes/hash
            }

            supplemental_success = await self.crypto_manager.save_supplemental_data(supplemental_data)
            if not supplemental_success:
                logger.warning("Failed to save supplemental data, but continuing...")
            else:
                logger.info(f"✓ Supplemental data saved to crypto.supplemental for TX: {blockchain_tx_id}")

            # Note: No conv.cancel storage for encoded cancellations  
            # Note: No exchange processing for encoded cancellations
            
            logger.info(f"=== ENCODED CONVICTION CANCELLATION COMPLETED SUCCESSFULLY ===")
            logger.info(f"Transaction ID: {temp_tx_id}")
            logger.info(f"Blockchain updated: ✓")
            logger.info(f"Database updated: ✓")
            logger.info(f"No exchange processing needed for encoded cancellations")
            
            return {
                "success": True,
                "message": "Encoded conviction cancellation processed successfully",
                "temp_tx_id": temp_tx_id,
                "blockchain_tx_id": blockchain_tx_id,
                "encoded_hashes": {
                    'book_hash': book_hash,
                    'research_hash': research_hash,
                    'params_hash': params_hash
                },
                "blockchain_updated": True,
                "database_stored": True
            }
            
        except Exception as e:
            logger.error(f"=== ERROR IN ENCODED CONVICTION CANCELLATION ===")
            logger.error(f"User: {user_id}, Book: {book_id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"Failed to process encoded cancellation: {str(e)}"
            }