# source/core/conviction_manager.py
import logging
import json 

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

    async def submit_convictions(self, submission_data, user_id):
        """Submit conviction with complete flow: files -> fingerprints -> blockchain -> database -> operations"""
        # Extract all data
        book_id = submission_data.get('book_id')
        convictions_data = submission_data.get('convictions', [])
        notes = submission_data.get('notes', '')
        research_file_data = submission_data.get('research_file_data')
        research_file_name = submission_data.get('research_file_name')
        
        logger.info(f"Processing {len(convictions_data)} convictions for user {user_id} in book {book_id}")
        
        try:
            # Get fund_id for storage paths
            fund_id = await self._get_fund_id_for_user(user_id)

            # Get or create contract for this user/book
            contract_id = await self.crypto_manager.get_or_create_contract(
                user_id=user_id,
                book_id=book_id,
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
                    # Create fingerprint of research file
                    fingerprint = await self.crypto_manager.create_file_fingerprint(
                        research_file_path, research_file_data
                    )
                    file_fingerprints[research_file_path] = fingerprint
                    logger.info(f"Stored research file with fingerprint: {research_file_path}")

            # Store notes if provided
            if notes and notes.strip():
                notes_file_path = await self.storage_manager.store_notes_file(
                    notes, fund_id, book_id, "temp"
                )
                if notes_file_path:
                    # Create fingerprint of notes file
                    notes_bytes = notes.encode('utf-8')
                    fingerprint = await self.crypto_manager.create_file_fingerprint(
                        notes_file_path, notes_bytes
                    )
                    file_fingerprints[notes_file_path] = fingerprint
                    logger.info(f"Stored notes file with fingerprint: {notes_file_path}")

            # Create and store CSV file
            csv_file_path = await self.storage_manager.store_convictions_csv(
                convictions_data, fund_id, book_id, "temp"
            )
            if csv_file_path:
                # Create CSV data for fingerprinting
                csv_content = json.dumps(convictions_data, sort_keys=True).encode('utf-8')
                fingerprint = await self.crypto_manager.create_file_fingerprint(
                    csv_file_path, csv_content
                )
                file_fingerprints[csv_file_path] = fingerprint
                logger.info(f"Stored CSV file with fingerprint: {csv_file_path}")

            # STEP 2: Create conviction fingerprint
            conviction_fingerprint = await self.crypto_manager.create_conviction_fingerprint(convictions_data)
            
            # STEP 3: Create crypto transaction with fingerprints
            tx_id = await self.crypto_manager.create_crypto_transaction(
                user_id=user_id,
                book_id=book_id,
                contract_id=contract_id,
                app_id="123",
                action="SUBMIT",
                notes=notes,
                conviction_fingerprint=conviction_fingerprint,
                file_fingerprints=file_fingerprints
            )

            # Update file paths with actual tx_id (move from temp)
            if research_file_path:
                research_file_path = research_file_path.replace("/temp/", f"/{tx_id}/")
            if notes_file_path:
                notes_file_path = notes_file_path.replace("/temp/", f"/{tx_id}/")
            if csv_file_path:
                csv_file_path = csv_file_path.replace("/temp/", f"/{tx_id}/")

            # STEP 4: Store transaction fingerprints on blockchain
            blockchain_result = await self.crypto_manager.store_transaction_on_blockchain(
                tx_id, contract_id, conviction_fingerprint, file_fingerprints
            )
            
            if not blockchain_result.get('success'):
                logger.error(f"Failed to store transaction on blockchain: {blockchain_result.get('error')}")
                return {
                    "success": False,
                    "error": "Failed to record transaction on blockchain",
                    "results": []
                }

            # STEP 5: Store conviction data in PostgreSQL (only after blockchain success)
            conviction_success = await self.db_manager.store_submit_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                convictions_data=convictions_data
            )
            
            if not conviction_success:
                logger.error(f"Failed to store conviction data for transaction {tx_id}")
                return {
                    "success": False,
                    "error": "Failed to store conviction data",
                    "results": []
                }
            
            # Log storage completion
            logger.info(f"Successfully completed all storage operations:")
            logger.info(f"  - Transaction ID: {tx_id}")
            logger.info(f"  - Contract ID: {contract_id}")
            logger.info(f"  - Blockchain TX: {blockchain_result.get('blockchain_tx_id')}")
            logger.info(f"  - Conviction fingerprint: {conviction_fingerprint[:16]}...")
            logger.info(f"  - File fingerprints: {len(file_fingerprints)} files")
            logger.info(f"  - PostgreSQL convictions: {len(convictions_data)} stored")

            # STEP 6: Send to operations (which handles simulator)
            # Add metadata to convictions for exchange processing
            enriched_convictions = []
            for conviction in convictions_data:
                enriched_conviction = conviction.copy()
                enriched_conviction.update({
                    'book_id': book_id,
                    'tx_id': tx_id,
                    'contract_id': contract_id,
                    'blockchain_tx_id': blockchain_result.get('blockchain_tx_id')
                })
                enriched_convictions.append(enriched_conviction)
            
            # Process convictions through operations (simulator interaction)
            exchange_result = await self.operation_manager.submit_convictions(enriched_convictions, user_id)
            
            # Add complete transaction metadata to result
            exchange_result.update({
                'tx_id': tx_id,
                'contract_id': contract_id,
                'blockchain_tx_id': blockchain_result.get('blockchain_tx_id'),
                'block_height': blockchain_result.get('block_height'),
                'conviction_fingerprint': conviction_fingerprint,
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
            logger.error(f"Error in submit_convictions: {e}")
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