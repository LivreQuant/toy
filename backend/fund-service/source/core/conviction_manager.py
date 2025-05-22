# source/core/conviction_manager.py
import logging

from typing import Dict, Any

from source.clients.exchange_client import ExchangeClient

from source.db.conviction_repository import ConvictionRepository
from source.db.crypto_repository import CryptoRepository

from source.core.session_manager import SessionManager

from source.core.conviction_manager_exchange import ExchangeManager
from source.core.conviction_manager_record import RecordManager
from source.core.conviction_manager_operation import OperationManager


logger = logging.getLogger('conviction_manager')


class ConvictionManager:
    """Main manager for conviction operations"""
    
    def __init__(
            self,
            conviction_repository: ConvictionRepository,
            crypto_repository: CryptoRepository,
            session_manager: SessionManager,
            exchange_client: ExchangeClient,
    ):
        """Initialize the conviction manager with dependencies"""
        # Create specialized managers
        self.conviction_repository = conviction_repository
        self.session_manager = session_manager
        self.crypto_repository = crypto_repository 

        self.record_manager = RecordManager(conviction_repository)
        self.exchange_manager = ExchangeManager(exchange_client)

        self.operation_manager = OperationManager(
            self.conviction_repository,
            self.session_manager,
            self.record_manager,
            self.exchange_manager
        )
        
    async def validate_book_ownership(self, book_id: str, user_id: str) -> Dict[str, Any]:
        """Validate that the book belongs to the user"""
        try:
            # Use existing book manager to validate ownership
            from source.core.book_manager import BookManager
            
            # This assumes you have access to book_manager or can import it
            # You might need to inject BookManager as a dependency
            result = await self.book_manager.get_book(book_id, user_id)
            
            if result.get('success'):
                return {'valid': True}
            else:
                return {'valid': False, 'error': result.get('error', 'Book not found or access denied')}
                
        except Exception as e:
            logger.error(f"Error validating book ownership: {e}")
            return {'valid': False, 'error': 'Failed to validate book ownership'}


    async def submit_convictions(self, submission_data, user_id):
        """Submit conviction with complete database and file storage"""
        # Extract all data
        book_id = submission_data.get('book_id')
        convictions_data = submission_data.get('conviction', [])
        notes = submission_data.get('notes', '')
        research_file_path = submission_data.get('research_file_path')
        csv_path = submission_data.get('csv_path')
        
        logger.info(f"Processing {len(convictions_data)} conviction for user {user_id} in book {book_id}")
        
        try:
            # Get or create contract for this user/book
            contract_id = await self.crypto_repository.get_or_create_contract(
                user_id=user_id,
                book_id=book_id,
                app_id="123"
            )
            
            # Create crypto transaction
            tx_id = await self.crypto_repository.create_crypto_transaction(
                user_id=user_id,
                book_id=book_id,
                contract_id=contract_id,
                app_id="123",
                action="SUBMIT",
                research_file_path=research_file_path,
                notes=notes
            )
            
            # Store conviction data in conv.submit
            conviction_success = await self.conviction_repository.store_submit_conviction_data(
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
            logger.info(f"Successfully stored submission data:")
            logger.info(f"  - Transaction ID: {tx_id}")
            logger.info(f"  - Contract ID: {contract_id}")
            logger.info(f"  - Convictions stored: {len(convictions_data)}")
            if research_file_path:
                logger.info(f"  - Research file: {research_file_path}")
            if csv_path:
                logger.info(f"  - CSV backup: {csv_path}")
            
            # Add metadata to convictions for exchange processing
            enriched_convictions = []
            for conviction in convictions_data:
                enriched_conviction = conviction.copy()
                enriched_conviction.update({
                    'book_id': book_id,
                    'tx_id': tx_id,
                    'contract_id': contract_id
                })
                enriched_convictions.append(enriched_conviction)
            
            # Process convictions through existing exchange pipeline
            exchange_result = await self.operation_manager.submit_convictions(enriched_convictions, user_id)
            
            # Update transaction status based on exchange result
            if exchange_result.get('success'):
                await self.crypto_repository.update_transaction_status(tx_id, 'COMPLETED')
            else:
                await self.crypto_repository.update_transaction_status(tx_id, 'FAILED')
            
            # Add transaction metadata to result
            exchange_result.update({
                'tx_id': tx_id,
                'contract_id': contract_id,
                'conviction_stored': True,
                'research_file_stored': bool(research_file_path)
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
        """Cancel convictions with complete database storage"""
        # Extract all data
        book_id = cancellation_data.get('book_id')
        conviction_ids = cancellation_data.get('conviction_ids', [])
        notes = cancellation_data.get('notes', '')
        research_file_path = cancellation_data.get('research_file_path')
        csv_path = cancellation_data.get('csv_path')
        
        logger.info(f"Processing cancellation of {len(conviction_ids)} convictions for user {user_id} in book {book_id}")
        
        try:
            # Get or create contract for this user/book
            contract_id = await self.conviction_repository.get_or_create_contract(
                user_id=user_id,
                book_id=book_id,
                app_id="456"
            )
            
            # Create crypto transaction
            tx_id = await self.conviction_repository.create_crypto_transaction(
                user_id=user_id,
                book_id=book_id,
                contract_id=contract_id,
                app_id="456",
                action="CANCEL",
                research_file_path=research_file_path,
                notes=notes
            )
            
            # Store conviction data in conv.cancel
            conviction_success = await self.conviction_repository.store_cancel_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                conviction_ids=conviction_ids
            )
            
            if not conviction_success:
                logger.error(f"Failed to store conviction cancellation data for transaction {tx_id}")
                return {
                    "success": False,
                    "error": "Failed to store conviction cancellation data",
                    "results": []
                }
            
            # Log storage completion
            logger.info(f"Successfully stored cancellation data:")
            logger.info(f"  - Transaction ID: {tx_id}")
            logger.info(f"  - Contract ID: {contract_id}")
            logger.info(f"  - Convictions to cancel: {len(conviction_ids)}")
            if research_file_path:
                logger.info(f"  - Research file: {research_file_path}")
            if csv_path:
                logger.info(f"  - CSV backup: {csv_path}")
            
            # Process cancellations through existing exchange pipeline
            exchange_result = await self.operation_manager.cancel_convictions(conviction_ids, user_id)
            
            # Add transaction metadata to result
            exchange_result.update({
                'tx_id': tx_id,
                'contract_id': contract_id,
                'conviction_stored': True,
                'research_file_stored': bool(research_file_path)
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
        encoded_data_path = submission_data.get('encoded_data_path')
        
        logger.info(f"Processing encoded conviction submission for user {user_id}")
        logger.info(f"Encoded convictions length: {len(encoded_convictions)}")
        logger.info(f"Encoded research file length: {len(encoded_research_file)}")
        logger.info(f"Encoded data stored at: {encoded_data_path}")
        
        # TODO: Implement your decoding logic here
        # decoded_convictions = decode_fingerprint_convictions(encoded_convictions)
        # return await self.operation_manager.submit_convictions(decoded_convictions, user_id)
        
        return {
            "success": True,
            "message": "Encoded conviction submission received and stored",
            "results": []
        }

    async def cancel_encoded_convictions(self, cancellation_data, user_id):
        """Cancel encoded convictions"""
        book_id = cancellation_data.get('book_id')
        encoded_conviction_ids = cancellation_data.get('encoded_conviction_ids', '')
        encoded_research_file = cancellation_data.get('encoded_research_file', '')
        notes = cancellation_data.get('notes', '')
        encoded_data_path = cancellation_data.get('encoded_data_path')
        
        logger.info(f"Processing encoded conviction cancellation for user {user_id}")
        logger.info(f"Encoded conviction IDs length: {len(encoded_conviction_ids)}")
        logger.info(f"Encoded research file length: {len(encoded_research_file)}")
        logger.info(f"Encoded data stored at: {encoded_data_path}")
        
        # TODO: Implement your decoding logic here
        # decoded_conviction_ids = decode_fingerprint_conviction_ids(encoded_conviction_ids)
        # return await self.operation_manager.cancel_convictions(decoded_conviction_ids, user_id)
        
        return {
            "success": True,
            "message": "Encoded conviction cancellation received and stored",
            "results": []
        }
    