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

    ############################
    # WALLET OPERATIONS - FUND #
    ############################

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

        
    ##############################
    # CONTRACT OPERATIONS - BOOK #
    ##############################
    
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

    ####################################################
    # USER OPERATIONS - USER SUBMIT/CANCEL CONVICTIONS #
    ####################################################

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


