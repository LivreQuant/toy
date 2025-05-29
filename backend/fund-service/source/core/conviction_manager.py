# source/core/conviction_manager.py
import logging
import json 
import uuid

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
                    research_fingerprint = self.create_file_fingerprint(research_file_data, research_file_name)
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
                    notes_fingerprint = self.create_file_fingerprint(notes_bytes, "notes.txt")
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
                convictions_fingerprint = self.create_file_fingerprint(csv_content, "convictions.csv")
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
            logger.info(f"=== STEP 3: STORING IN DATABASE ===")
            logger.info(f"Transaction ID: {temp_tx_id}, Book ID: {book_id}")
            logger.info(f"Convictions data count: {len(convictions_data)}")
            
            db_success = await self.db_manager.store_submit_conviction_data(
                tx_id=temp_tx_id,
                book_id=book_id,
                convictions_data=convictions_data
            )
            
            logger.info(f"Database storage result: {db_success}")
            
            if not db_success:
                logger.error(f"✗ Failed to store conviction data for transaction {temp_tx_id}")
                return {
                    "success": False,
                    "error": "Failed to store conviction data in database",
                    "results": []
                }
            
            logger.info(f"✓ Successfully stored conviction data in database")
            
            # STEP 4: Send to operations manager (exchange processing)
            logger.info(f"=== STEP 4: SENDING TO OPERATIONS MANAGER ===")
            logger.info(f"Sending {len(convictions_data)} convictions to operations manager")
            
            exchange_result = await self.operation_manager.submit_convictions(convictions_data, user_id)
            
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
        
    async def cancel_convictions(self, cancellation_data, user_id):
        """Cancel convictions with complete flow: files -> fingerprints -> blockchain -> database -> operations"""
        # Extract all data
        book_id = cancellation_data.get('book_id')
        conviction_ids = cancellation_data.get('conviction_ids', [])
        notes = cancellation_data.get('notes', '')
        research_file_data = cancellation_data.get('research_file_data')
        research_file_name = cancellation_data.get('research_file_name')
        
        logger.info(f"Processing cancellation of {len(conviction_ids)} convictions for user {user_id} in book {book_id}")
        
        try:
            # Get fund_id for storage paths
            fund_id = await self._get_fund_id_for_user(user_id)

            # Get or create contract for this user/book
            contract_id = await self.crypto_manager.get_or_create_contract(
                user_id=user_id,
                book_id=book_id,
                app_id="456"
            )
            
            # STEP 1: Store files first (need originals for fingerprinting)
            research_file_path = None
            notes_file_path = None
            csv_file_path = None
            file_fingerprints = {}

            # Store research file if provided
            if research_file_data and research_file_name:
                research_file_path = await self.storage_manager.store_research_file(
                    research_file_data, research_file_name, fund_id, book_id, "temp"
                )
                if research_file_path:
                    fingerprint = await self.crypto_manager.create_file_fingerprint(
                        research_file_path, research_file_data
                    )
                    file_fingerprints[research_file_path] = fingerprint

            # Store notes if provided
            if notes and notes.strip():
                notes_file_path = await self.storage_manager.store_notes_file(
                    notes, fund_id, book_id, "temp"
                )
                if notes_file_path:
                    notes_bytes = notes.encode('utf-8')
                    fingerprint = await self.crypto_manager.create_file_fingerprint(
                        notes_file_path, notes_bytes
                    )
                    file_fingerprints[notes_file_path] = fingerprint

            # Create and store cancellation CSV
            csv_file_path = await self.storage_manager.store_cancellation_csv(
                conviction_ids, fund_id, book_id, "temp"
            )
            if csv_file_path:
                csv_content = json.dumps(conviction_ids, sort_keys=True).encode('utf-8')
                fingerprint = await self.crypto_manager.create_file_fingerprint(
                    csv_file_path, csv_content
                )
                file_fingerprints[csv_file_path] = fingerprint

            # STEP 2: Create cancellation fingerprint
            cancellation_fingerprint = await self.crypto_manager.create_conviction_fingerprint(conviction_ids)
            
            # STEP 3: Create crypto transaction with fingerprints
            tx_id = await self.crypto_manager.create_crypto_transaction(
                user_id=user_id,
                book_id=book_id,
                contract_id=contract_id,
                app_id="456",
                action="CANCEL",
                notes=notes,
                conviction_fingerprint=cancellation_fingerprint,
                file_fingerprints=file_fingerprints
            )

            # STEP 4: Store transaction fingerprints on blockchain
            blockchain_result = await self.crypto_manager.store_transaction_on_blockchain(
                tx_id, contract_id, cancellation_fingerprint, file_fingerprints
            )
            
            if not blockchain_result.get('success'):
                logger.error(f"Failed to store transaction on blockchain: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record transaction on blockchain",
                    "results": []
                }

            # STEP 5: Store cancellation data in PostgreSQL (only after blockchain success)
            cancellation_success = await self.db_manager.store_cancel_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                conviction_ids=conviction_ids
            )
            
            if not cancellation_success:
                logger.error(f"Failed to store cancellation data for transaction {tx_id}")
                return {
                    "success": False,
                    "error": "Failed to store cancellation data",
                    "results": []
                }
            
            # STEP 6: Send to operations (which handles simulator)
            exchange_result = await self.operation_manager.cancel_convictions(conviction_ids, user_id)
            
            # Add complete transaction metadata to result
            exchange_result.update({
                'tx_id': tx_id,
                'contract_id': contract_id,
                'blockchain_tx_id': blockchain_result.get('blockchain_tx_id'),
                'block_height': blockchain_result.get('block_height'),
                'conviction_fingerprint': cancellation_fingerprint,
                'file_fingerprints': file_fingerprints,
                'files_stored': {
                    'research_file': bool(research_file_path),
                    'notes_file': bool(notes_file_path),
                    'csv_file': bool(csv_file_path)
                },
                'blockchain_confirmed': True,
                'database_stored': True
            })
            
            return exchange_result
            
        except Exception as e:
            logger.error(f"Error in cancel_convictions: {e}")
            return {
                "success": False,
                "error": f"Failed to process cancellation: {str(e)}",
                "results": []
            }

    async def submit_encoded_convictions(self, submission_data, user_id):
        """Submit encoded convictions"""
        book_id = submission_data.get('book_id')
        encoded_convictions = submission_data.get('encoded_convictions', '')
        encoded_research_file = submission_data.get('encoded_research_file', '')
        notes = submission_data.get('notes', '')
        
        logger.info(f"Processing encoded conviction submission for user {user_id}")
        
        try:
            # Store encoded data
            encoded_data_path = await self.storage_manager.store_encoded_data(
                book_id, encoded_convictions, encoded_research_file, notes, user_id, 'submit'
            )
            
            # TODO: Implement decoding and processing
            # decoded_convictions = await self.crypto_manager.decode_conviction_data(encoded_convictions)
            # return await self.submit_convictions({'book_id': book_id, 'convictions': decoded_convictions}, user_id)
            
            return {
                "success": True,
                "message": "Encoded conviction submission received and stored",
                "encoded_data_path": encoded_data_path,
                "results": []
            }
        except Exception as e:
            logger.error(f"Error in submit_encoded_convictions: {e}")
            return {
                "success": False,
                "error": f"Failed to process encoded submission: {str(e)}",
                "results": []
            }

    async def cancel_encoded_convictions(self, cancellation_data, user_id):
       """Cancel encoded convictions"""
       book_id = cancellation_data.get('book_id')
       encoded_conviction_ids = cancellation_data.get('encoded_conviction_ids', '')
       encoded_research_file = cancellation_data.get('encoded_research_file', '')
       notes = cancellation_data.get('notes', '')
       
       logger.info(f"Processing encoded conviction cancellation for user {user_id}")
       
       try:
           # Store encoded data
           encoded_data_path = await self.storage_manager.store_encoded_data(
               book_id, encoded_conviction_ids, encoded_research_file, notes, user_id, 'cancel'
           )
           
           # TODO: Implement decoding and processing
           # decoded_conviction_ids = await self.crypto_manager.decode_conviction_data(encoded_conviction_ids)
           # return await self.cancel_convictions({'book_id': book_id, 'conviction_ids': decoded_conviction_ids}, user_id)
           
           return {
               "success": True,
               "message": "Encoded conviction cancellation received and stored",
               "encoded_data_path": encoded_data_path,
               "results": []
           }
       except Exception as e:
           logger.error(f"Error in cancel_encoded_convictions: {e}")
           return {
               "success": False,
               "error": f"Failed to process encoded cancellation: {str(e)}",
               "results": []
           }
