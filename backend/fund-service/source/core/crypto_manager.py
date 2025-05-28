# source/core/conviction_manager_crypto.py
import logging
import hashlib
import json
import time
from typing import Dict, Any, Optional, List

from source.db.crypto_repository import CryptoRepository

from source.services.wallet_service import wallet_service
from source.services.contract_service import contract_service
from source.services.user_contract_service import user_contract_service
from source.services.file_integrity_service import FileIntegrityService

logger = logging.getLogger('crypto_manager')

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file for debugging."""
    hash_obj = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def save_debug_info(file_path, hash_value):
    """Save debugging information about a file."""
    debug_info = {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "file_size": file_path.stat().st_size,
        "hash_value": hash_value,
        "timestamp": time.time(),
    }

    # Save to debug file
    debug_path = Path(f"file_debug_{file_path.name}.json")
    with open(debug_path, "w") as f:
        json.dump(debug_info, f, indent=2)

    logger.info(f"Debug information saved to {debug_path}")

class CryptoManager:
    """Manager for blockchain and cryptographic operations"""

    def __init__(self, crypto_repository: CryptoRepository):
        """Initialize the crypto manager with dependencies"""
        self.crypto_repository = crypto_repository

        self.wallet_service = wallet_service
        self.contract_service = contract_service
        self.user_contract_service = user_contract_service

    #####################
    # WALLET OPERATIONS #
    #####################


    async def create_wallet(self, user_id: str):

        logger.info("STEP 1: Get or create user wallet")
        step1_start = time.time()
        user_wallet = await self.wallet_service.get_or_create_user_wallet(user_id)
        logger.info(f"User wallet address: {user_wallet['address']}")
        logger.info(f"Step 1 completed in {time.time() - step1_start:.2f} seconds")

        success = await self.crypto_repository.save_wallet(user_wallet)

        return success


    async def get_wallet(self, user_id: str):

        result = await self.crypto_repository.get_wallet(user_id)

        return result
    

    async def check_wallet_fund(self, user_id: str, funding_amount: int = 10):

        user_wallet = self.get_wallet(user_id)

        logger.info("STEP 2: Ensure user wallet is funded")
        step2_start = time.time()
        if await self.wallet_service.ensure_user_wallet_funded(user_id, funding_amount):
            logger.info("User wallet funding successful or already sufficient")
        else:
            logger.error(
                f"Failed to fund user wallet with {funding_amount} Algos, aborting workflow"
            )
            logger.info(
                "You may need to manually fund the admin account or reduce the funding amount"
            )
            logger.info(
                f"Try running: 'goal clerk send -a {int(funding_amount * 1000000)} -f ADMIN_ADDRESS -t {user_wallet['address']}'"
            )
            return
        logger.info(f"Step 2 completed in {time.time() - step2_start:.2f} seconds")

        
    #######################
    # CONTRACT OPERATIONS #
    #######################
    
    async def create_contract(self, user_id: str, book_id: str):

        logger.info("STEP 3: Deploy contract or get existing contract")
        step3_start = time.time()
        contract_info = self.contract_service.get_contract_for_user_book(user_id, book_id)
        if contract_info:
            app_id = contract_info["app_id"]
            logger.info(f"Using existing contract: {app_id}")
        else:
            logger.info("Deploying new contract")
            contract_info = self.contract_service.deploy_contract_for_user_book(user_id, book_id)
            if contract_info:
                app_id = contract_info["app_id"]
                logger.info(f"Contract deployed with app ID: {app_id}")
            else:
                logger.error("Contract deployment failed, aborting workflow")
                return
        logger.info(f"Step 3 completed in {time.time() - step3_start:.2f} seconds")

    async def get_contract(self, user_id: str, book_id: str):

        result = await self.crypto_repository.get_contract(user_id, book_id)

        return result

    async def get_contracts(self, user_id: str):

        result = await self.crypto_repository.get_contracts(user_id)

        return result

    async def update_contract(self, user_id: str, book_id: str, params_str: str):

        result = await self.contract_service.update_global_state(user_id, book_id, params_str)

        return result

    async def delete_contract(self, user_id: str, book_id: str):

        result = await self.contract_service.remove_contract(user_id, book_id)

        return result

    ###################
    # USER OPERATIONS #
    ###################

    async def opt_in(self, user_id: str, book_id: str):

        # Step 4: User opt-in to contract
        logger.info("STEP 4: User opt-in to contract")
        step4_start = time.time()
        if await self.user_contract_service.user_opt_in_to_contract(user_id, book_id):
            logger.info("User opt-in successful")
        else:
            logger.error("User opt-in failed, aborting workflow")
            return
        logger.info(f"Step 4 completed in {time.time() - step4_start:.2f} seconds")


    async def opt_out(self, user_id: str, book_id: str):
        # Step 7: User closes out from contract
        logger.info("STEP 7: User closes out from contract")
        step7_start = time.time()
        if await self.user_contract_service.user_close_out_from_contract(user_id, book_id):
            logger.info("User close-out successful")
        else:
            logger.error(
                "User close-out failed, admin may need to force-delete the contract"
            )
        logger.info(f"Step 7 completed in {time.time() - step7_start:.2f} seconds")


    async def update_local_state(self, user_id: str, book_id: str, use_encrypt: bool):

        # Step 5: Update local state with only book hash
        logger.info("STEP 5: Update local state with book hash only")
        step5_start = time.time()

        # Initialize the file integrity service
        file_service = FileIntegrityService()

        # Define path to your book file
        book_file = Path("files/market_stream_20250505T195600.csv")

        # Check if file exists
        if book_file.exists():
            # Calculate and log hash for debugging
            file_hash = calculate_file_hash(book_file)
            logger.info(f"WORKFLOW DEBUG - Book file hash: {file_hash}")
            logger.info(
                f"WORKFLOW DEBUG - Book file size: {book_file.stat().st_size} bytes"
            )

            # Choose the appropriate update method based on use_encrypt flag
            if use_encrypt:
                # Use secure cryptographic signing
                logger.info("Using secure cryptographic signing for book file")

                success = file_service.update_contract_with_signed_hashes(
                    user_id=user_id,
                    book_id=book_id,
                    book_file_path=book_file,
                    passphrase=config.SECRET_PASS_PHRASE,
                )

            else:
                # Update contract with book file hash only (no research file, no params)
                logger.info("Using regular hash for book file")

                success = file_service.update_contract_with_file_hashes(
                    user_id=user_id,
                    book_id=book_id,
                    book_file_path=book_file,
                )

                # Save debug info
                save_debug_info(book_file, file_hash)

            if success:
                logger.info("Local state update with book hash successful")
            else:
                logger.error("Local state update with book hash failed")
        else:
            # Fallback to dummy values if files don't exist
            logger.warning("Book file not found, using dummy hash")
            book_hash = f"book_hash_{user_id}_{book_id}"

            if update_user_local_state(user_id, book_id, book_hash, "", ""):
                logger.info("Local state update with dummy book hash successful")
            else:
                logger.error("Local state update with dummy book hash failed")

        logger.info(f"Step 5 completed in {time.time() - step5_start:.2f} seconds")



    async def get_or_create_contract(self, user_id: str, book_id: str) -> str:
        """Get or create contract for user/book combination"""
        try:
            contract_id = await self.crypto_repository.get_or_create_contract(
                user_id=user_id,
                book_id=book_id,
            )
            logger.info(f"Contract ID for user {user_id}, book {book_id}: {contract_id}")
            return contract_id
        except Exception as e:
            logger.error(f"Error getting/creating contract: {e}")
            raise

    async def create_crypto_transaction(self, user_id: str, book_id: str, contract_id: str,
                                         app_id: str, action: str, notes: str = None,
                                         conviction_fingerprint: str = None,
                                         file_fingerprints: Dict[str, str] = None) -> str:
        """
        Create crypto transaction with fingerprints
        
        Args:
            user_id: User ID
            book_id: Book ID
            contract_id: Contract ID
            app_id: Application ID
            action: Action type (SUBMIT/CANCEL)
            notes: Optional notes
            conviction_fingerprint: Hash of conviction data
            file_fingerprints: Dictionary of file_path -> fingerprint
            
        Returns:
            Transaction ID
        """
        try:
            # Create supplemental data with fingerprints
            supplemental_data = {}
            if conviction_fingerprint:
                supplemental_data['conviction_fingerprint'] = conviction_fingerprint
            if file_fingerprints:
                supplemental_data['file_fingerprints'] = file_fingerprints
            
            tx_id = await self.crypto_repository.create_crypto_transaction(
                user_id=user_id,
                book_id=book_id,
                contract_id=contract_id,
                app_id=app_id,
                action=action,
                notes=notes
            )
            
            # Store fingerprints in supplemental data if provided
            if supplemental_data:
                await self.crypto_repository.update_transaction_status(
                    tx_id, 
                    'FINGERPRINTS_RECORDED',
                    json.dumps(supplemental_data)
                )
            
            logger.info(f"Created crypto transaction {tx_id} for {action} operation")
            return tx_id
            
        except Exception as e:
            logger.error(f"Error creating crypto transaction: {e}")
            raise

    async def create_file_fingerprint(self, file_path: str, file_data: bytes) -> str:
        """
        Create a cryptographic fingerprint of a file
        
        Args:
            file_path: Path where file is stored
            file_data: Raw file data bytes
            
        Returns:
            Hex string of SHA-256 hash
        """
        try:
            # Create SHA-256 hash of file data
            hash_obj = hashlib.sha256()
            hash_obj.update(file_data)
            fingerprint = hash_obj.hexdigest()
            
            logger.info(f"Created fingerprint for {file_path}: {fingerprint[:16]}...")
            return fingerprint
            
        except Exception as e:
            logger.error(f"Error creating fingerprint for {file_path}: {e}")
            raise

    async def create_conviction_fingerprint(self, convictions_data: List[Dict[str, Any]]) -> str:
        """
        Create a cryptographic fingerprint of conviction data
        
        Args:
            convictions_data: List of conviction dictionaries
            
        Returns:
            Hex string of SHA-256 hash
        """
        try:
            # Convert convictions to canonical JSON for consistent hashing
            canonical_json = json.dumps(convictions_data, sort_keys=True, separators=(',', ':'))
            
            # Create SHA-256 hash
            hash_obj = hashlib.sha256()
            hash_obj.update(canonical_json.encode('utf-8'))
            fingerprint = hash_obj.hexdigest()
            
            logger.info(f"Created conviction fingerprint: {fingerprint[:16]}...")
            return fingerprint
            
        except Exception as e:
            logger.error(f"Error creating conviction fingerprint: {e}")
            raise

    async def store_transaction_on_blockchain(self, tx_id: str, contract_id: str, 
                                            conviction_fingerprint: str,
                                            file_fingerprints: Dict[str, str]) -> Dict[str, Any]:
        """
        Store transaction fingerprints on blockchain
        
        Args:
            tx_id: Transaction ID
            contract_id: Smart contract ID
            conviction_fingerprint: Hash of conviction data
            file_fingerprints: Dictionary of file_path -> fingerprint
            
        Returns:
            Result dictionary with blockchain transaction details
        """
        try:
            logger.info(f"Storing transaction {tx_id} on blockchain")
            logger.info(f"Contract: {contract_id}")
            logger.info(f"Conviction fingerprint: {conviction_fingerprint[:16]}...")
            logger.info(f"File fingerprints: {len(file_fingerprints)} files")
            
            # TODO: Implement actual blockchain interaction
            # This would typically involve:
            # 1. Creating a blockchain transaction
            # 2. Including all fingerprints in the transaction data
            # 3. Signing the transaction
            # 4. Submitting to blockchain network
            # 5. Waiting for confirmation
            
            # For now, simulate blockchain storage
            blockchain_tx_id = f"blockchain_tx_{tx_id[:8]}"
            block_height = 12345  # Mock block height
            
            # Store blockchain reference in our database
            blockchain_data = {
                'blockchain_tx_id': blockchain_tx_id,
                'block_height': block_height,
                'conviction_fingerprint': conviction_fingerprint,
                'file_fingerprints': file_fingerprints,
                'status': 'CONFIRMED'
            }
            
            # Update crypto transaction with blockchain data
            await self.crypto_repository.update_transaction_status(
                tx_id, 
                'BLOCKCHAIN_CONFIRMED',
                json.dumps(blockchain_data)
            )
            
            logger.info(f"Transaction {tx_id} confirmed on blockchain: {blockchain_tx_id}")
            
            return {
                'success': True,
                'blockchain_tx_id': blockchain_tx_id,
                'block_height': block_height,
                'conviction_fingerprint': conviction_fingerprint,
                'file_fingerprints': file_fingerprints
            }
            
        except Exception as e:
            logger.error(f"Error storing transaction on blockchain: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def verify_transaction_integrity(self, tx_id: str, 
                                         convictions_data: List[Dict[str, Any]],
                                         file_data_map: Dict[str, bytes]) -> Dict[str, Any]:
        """
        Verify the integrity of a transaction by comparing fingerprints
        
        Args:
            tx_id: Transaction ID to verify
            convictions_data: Current conviction data
            file_data_map: Map of file_path -> file_data for verification
            
        Returns:
            Verification result dictionary
        """
        try:
            logger.info(f"Verifying integrity of transaction {tx_id}")
            
            # Get blockchain data for this transaction
            tx_details = await self.crypto_repository.get_transaction_details(tx_id)
            
            if not tx_details or not tx_details.get('g_params'):
                return {
                    'verified': False,
                    'error': 'No blockchain data found for transaction'
                }
            
            blockchain_data = json.loads(tx_details['g_params'])
            stored_conviction_fingerprint = blockchain_data.get('conviction_fingerprint')
            stored_file_fingerprints = blockchain_data.get('file_fingerprints', {})
            
            # Verify conviction data fingerprint
            current_conviction_fingerprint = await self.create_conviction_fingerprint(convictions_data)
            conviction_verified = (current_conviction_fingerprint == stored_conviction_fingerprint)
            
            # Verify file fingerprints
            file_verification = {}
            for file_path, file_data in file_data_map.items():
                current_fingerprint = await self.create_file_fingerprint(file_path, file_data)
                stored_fingerprint = stored_file_fingerprints.get(file_path)
                file_verification[file_path] = (current_fingerprint == stored_fingerprint)
            
            all_files_verified = all(file_verification.values())
            
            result = {
                'verified': conviction_verified and all_files_verified,
                'conviction_verified': conviction_verified,
                'files_verified': file_verification,
                'blockchain_tx_id': blockchain_data.get('blockchain_tx_id'),
                'block_height': blockchain_data.get('block_height')
            }
            
            if result['verified']:
                logger.info(f"Transaction {tx_id} integrity verified successfully")
            else:
                logger.warning(f"Transaction {tx_id} integrity verification failed")
                
            return result
            
        except Exception as e:
            logger.error(f"Error verifying transaction integrity: {e}")
            return {
                'verified': False,
                'error': str(e)
            }

    async def get_transaction_proof(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cryptographic proof for a transaction
        
        Args:
            tx_id: Transaction ID
            
        Returns:
            Proof dictionary or None if not found
        """
        try:
            tx_details = await self.crypto_repository.get_transaction_details(tx_id)
            
            if not tx_details or not tx_details.get('g_params'):
                return None
            
            blockchain_data = json.loads(tx_details['g_params'])
            
            return {
                'tx_id': tx_id,
                'blockchain_tx_id': blockchain_data.get('blockchain_tx_id'),
                'block_height': blockchain_data.get('block_height'),
                'conviction_fingerprint': blockchain_data.get('conviction_fingerprint'),
                'file_fingerprints': blockchain_data.get('file_fingerprints', {}),
                'timestamp': tx_details.get('created_at'),
                'status': blockchain_data.get('status')
            }
            
        except Exception as e:
            logger.error(f"Error getting transaction proof: {e}")
            return None

    async def encode_conviction_data(self, convictions_data: List[Dict[str, Any]]) -> str:
        """
        Encode conviction data for privacy/security
        
        Args:
            convictions_data: List of conviction dictionaries
            
        Returns:
            Encoded string
        """
        try:
            # TODO: Implement actual encoding/encryption
            # This could involve:
            # 1. Encryption with user's private key
            # 2. Base64 encoding
            # 3. Other privacy-preserving techniques
            
            # For now, just base64 encode the JSON
            import base64
            json_str = json.dumps(convictions_data, sort_keys=True)
            encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
            
            logger.info(f"Encoded {len(convictions_data)} convictions")
            return encoded
            
        except Exception as e:
            logger.error(f"Error encoding conviction data: {e}")
            raise

    async def decode_conviction_data(self, encoded_data: str) -> List[Dict[str, Any]]:
        """
        Decode encoded conviction data
        
        Args:
            encoded_data: Encoded conviction data string
            
        Returns:
            List of conviction dictionaries
        """
        try:
            # TODO: Implement actual decoding/decryption
            # This should reverse the encoding process
            
            # For now, just base64 decode
            import base64
            json_str = base64.b64decode(encoded_data.encode('utf-8')).decode('utf-8')
            convictions_data = json.loads(json_str)
            
            logger.info(f"Decoded {len(convictions_data)} convictions")
            return convictions_data
            
        except Exception as e:
            logger.error(f"Error decoding conviction data: {e}")
            raise