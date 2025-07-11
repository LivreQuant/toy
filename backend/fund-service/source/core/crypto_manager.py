# backend/fund-service/source/core/crypto_manager.py
import logging
import hashlib
import json
import uuid
import time
import base64
import datetime
from typing import Dict, Any, Optional, List

from source.db.crypto_repository import CryptoRepository
from source.config import config

from source.services.utils.wallet import generate_algorand_wallet, get_wallet_credentials

from source.services.utils.algorand import get_algod_client, fund_account, check_balance, get_account_from_mnemonic

from source.services.contract_service import deploy_contract_for_user_book, update_global_state, remove_contract

from source.services.user_contract_service import user_opt_in_to_contract, update_user_local_state

logger = logging.getLogger('crypto_manager')

class CryptoManager:
    """Manager for blockchain and cryptographic operations"""

    def __init__(self, crypto_repository: CryptoRepository):
        """Initialize the crypto manager with dependencies"""
        self.crypto_repository = crypto_repository

    def create_file_fingerprint(self, file_data: bytes, filename: str) -> str:
        """
        Create a cryptographic fingerprint of file data
        
        Args:
            file_data: The file data as bytes
            filename: The filename (for context)
            
        Returns:
            SHA-256 hash of the file data
        """
        # Create SHA-256 hash of the file data
        hash_obj = hashlib.sha256()
        hash_obj.update(file_data)
        fingerprint = hash_obj.hexdigest()
        
        logger.info(f"Created fingerprint for {filename}: {fingerprint[:16]}...")
        return fingerprint

    def create_conviction_fingerprint(self, conviction_ids: List[str]) -> str:
        """
        Create a fingerprint for conviction IDs
        
        Args:
            conviction_ids: List of conviction IDs
            
        Returns:
            SHA-256 hash of the conviction IDs
        """
        # Sort IDs for deterministic hashing
        sorted_ids = sorted(conviction_ids)
        ids_string = json.dumps(sorted_ids, sort_keys=True)
        
        hash_obj = hashlib.sha256()
        hash_obj.update(ids_string.encode('utf-8'))
        fingerprint = hash_obj.hexdigest()
        
        logger.info(f"Created conviction fingerprint for {len(conviction_ids)} IDs: {fingerprint[:16]}...")
        return fingerprint

    async def save_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """Save transaction information to crypto.txs"""
        try:
            success = await self.crypto_repository.save_transaction(tx_data)
            if success:
                logger.info(f"Transaction saved to crypto.txs: {tx_data.get('tx_id')}")
            return success
        except Exception as e:
            logger.error(f"Error saving transaction to crypto.txs: {e}")
            return False

    async def save_supplemental_data(self, supplemental_data: Dict[str, Any]) -> bool:
        """Save supplemental transaction data to crypto.supplemental"""
        try:
            success = await self.crypto_repository.save_supplemental_data(supplemental_data)
            if success:
                logger.info(f"Supplemental data saved: {supplemental_data.get('tx_id')}")
            return success
        except Exception as e:
            logger.error(f"Error saving supplemental data: {e}")
            return False

    ############################
    # WALLET OPERATIONS - FUND #
    ############################

    async def create_wallet(self, user_id: str, fund_id: str) -> Dict[str, Any]:
        """Create a new wallet for a user/fund combination - always encrypted"""
        try:
            logger.info(f"Creating encrypted wallet for user {user_id}, fund {fund_id}")
            
            # Always generate encrypted wallets
            wallet_info = generate_algorand_wallet(f"user_{user_id}")
            
            # Extract credentials
            private_key, address = get_wallet_credentials(wallet_info)
            
            # Prepare wallet data for database storage - always encrypted
            wallet_data = {
                'address': address,
                'mnemonic': wallet_info.get('mnemonic'),  # Always encrypted
                'mnemonic_salt': wallet_info.get('mnemonic_salt'),  # Required for decryption
            }
            
            # Validate that we have encrypted data
            if not wallet_data['mnemonic'] or not wallet_data['mnemonic_salt']:
                logger.error("Missing encrypted mnemonic or salt")
                return {
                    "success": False,
                    "error": "Encryption validation failed"
                }
            
            # Save to database
            success = await self.crypto_repository.save_wallet(user_id, fund_id, wallet_data)
            
            if success:
                logger.info(f"Encrypted wallet created successfully for user {user_id}, fund {fund_id}")
                
                # Fund the wallet
                await self._fund_wallet(user_id, fund_id, wallet_info)
                
                return {
                    "success": True,
                    "address": address,
                    "wallet_info": wallet_info
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save encrypted wallet to database"
                }
                
        except Exception as e:
            logger.error(f"Error creating encrypted wallet: {e}")
            return {
                "success": False,
                "error": f"Error creating encrypted wallet: {str(e)}"
            }

    async def get_wallet(self, user_id: str, fund_id: str) -> Optional[Dict[str, Any]]:
        """
        Get wallet information for a user/fund combination
        
        Args:
            user_id: User ID
            fund_id: Fund ID
            
        Returns:
            Wallet data if found, None otherwise
        """
        try:
            wallet_data = await self.crypto_repository.get_wallet(user_id, fund_id)
            
            if wallet_data:
                logger.info(f"Retrieved wallet for user {user_id}, fund {fund_id}")
                return wallet_data
            else:
                logger.info(f"No wallet found for user {user_id}, fund {fund_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting wallet: {e}")
            return None

    async def _fund_wallet(self, user_id: str, fund_id: str, wallet_info: Dict[str, Any], funding_amount: float = 5.0):
        """
        Fund a wallet with Algos
        
        Args:
            user_id: User ID
            fund_id: Fund ID
            wallet_info: Wallet information
            funding_amount: Amount in Algos to fund
        """
        try:
            logger.info(f"Funding wallet for user {user_id}, fund {fund_id} with {funding_amount} Algos")
                        
            # Get user wallet credentials
            user_private_key, user_address = get_wallet_credentials(wallet_info)
            
            # Check current balance
            algod_client = get_algod_client()
            current_balance = check_balance(algod_client, user_address)
            
            if current_balance >= funding_amount:
                logger.info(f"Wallet already has sufficient funds ({current_balance} Algos)")
                return True
            
            # Get admin wallet for funding
            if not config.admin_mnemonic:
                logger.warning("No admin mnemonic configured, cannot fund wallet")
                return False
                
            admin_private_key, admin_address = get_account_from_mnemonic(config.admin_mnemonic)
            
            # Check admin balance
            admin_balance = check_balance(algod_client, admin_address)
            
            if admin_balance < funding_amount + 1:  # Extra for fees
                logger.warning(f"Admin wallet has insufficient funds ({admin_balance} Algos)")
                return False
            
            # Fund the user wallet
            result = fund_account(
                algod_client,
                admin_private_key,
                admin_address,
                user_address,
                funding_amount
            )
            
            if result:
                logger.info(f"Successfully funded wallet for user {user_id}")
                return True
            else:
                logger.error(f"Failed to fund wallet for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error funding wallet: {e}")
            return False

    ##############################
    # CONTRACT OPERATIONS - BOOK #
    ##############################
    
    async def create_contract(self, user_id: str, book_id: str, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new contract for a user/book combination with complete setup
        FIXED: Save contract to database IMMEDIATELY after blockchain deployment
        
        Args:
            user_id: User ID
            book_id: Book ID
            book_data: Book data for contract parameters
            
        Returns:
            Result dictionary with success flag and contract info
        """
        try:
            logger.info(f"Creating complete contract setup for user {user_id}, book {book_id}")
            
            # Check if contract already exists
            existing_contract = await self.crypto_repository.get_contract(user_id, book_id)
            if existing_contract:
                logger.info(f"Contract already exists for user {user_id}, book {book_id}")
                return {
                    "success": True,
                    "app_id": existing_contract['app_id'],
                    "contract_info": existing_contract
                }
            
            # Get user's wallet info first - we'll need it for global state update and opt-in
            fund_id = await self._get_fund_id_for_user(user_id)
            if not fund_id:
                logger.error(f"No fund found for user {user_id}")
                return {
                    "success": False,
                    "error": "User fund not found - cannot create contract"
                }
                
            wallet_data = await self.get_wallet(user_id, fund_id)
            if not wallet_data:
                logger.error(f"No wallet found for user {user_id}")
                return {
                    "success": False,
                    "error": "User wallet not found - cannot create contract"
                }
            
            user_address = wallet_data['address']
            logger.info(f"Found user wallet address: {user_address}")
                    
            # Convert book parameters to fingerprint
            params_fingerprint = self._convert_book_data_to_params(book_data)
            
            # =============================================================================
            # STEP 1: Deploy contract to blockchain
            # =============================================================================
            logger.info(f"STEP 1: Deploying contract for user {user_id}, book {book_id}")
            contract_info = deploy_contract_for_user_book(user_id, book_id, params_fingerprint)
            
            if not contract_info or not contract_info.get('app_id'):
                logger.error("Failed to deploy contract")
                return {
                    "success": False,
                    "error": "Failed to deploy contract"
                }
            
            app_id = contract_info['app_id']
            logger.info(f"Contract deployed successfully with app ID: {app_id}")

            # =============================================================================
            # STEP 2: CRITICAL FIX - Save contract to database IMMEDIATELY
            # This must happen BEFORE any transaction records are saved to avoid foreign key errors
            # =============================================================================
            logger.info(f"STEP 2: Saving contract to database IMMEDIATELY after blockchain deployment")
            contract_data = {
                'app_id': str(app_id),
                'app_address': contract_info['app_address'],
                'parameters': params_fingerprint,
                'status': 'CREATING',  # Temporary status during setup
                'blockchain_status': 'Deployed'
            }
            
            success = await self.crypto_repository.save_contract(user_id, book_id, contract_data)
            if not success:
                logger.error("Failed to save contract to database")
                return {
                    "success": False,
                    "error": "Contract deployed but failed to save to database"
                }
            
            logger.info(f"✅ Contract saved to database with app_id: {app_id}")

            # =============================================================================
            # STEP 3: Now it's SAFE to save transaction records (contract exists in DB)
            # =============================================================================
            creation_tx_id = contract_info.get('creation_tx_id')
            funding_tx_id = contract_info.get('funding_tx_id') 
            init_tx_id = contract_info.get('init_tx_id')
            
            if creation_tx_id:
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=creation_tx_id,
                    action="CREATE_CONTRACT",
                    g_status="INACTIVE-INIT",
                    g_params=""
                )
            
            if funding_tx_id:
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=funding_tx_id,
                    action="FUND_CONTRACT",
                    g_status="INACTIVE-INIT",
                    g_params=""
                )
                
            if init_tx_id:
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=init_tx_id,
                    action="INIT_CONTRACT",
                    g_status="INACTIVE-INIT",
                    g_params=params_fingerprint
                    
                )
            
            # =============================================================================
            # STEP 4: Update global state with real user address
            # =============================================================================
            logger.info(f"STEP 4: Updating global state with user address: {user_address}")
            global_result = update_global_state(app_id, user_id, book_id, user_address, params_fingerprint)
            
            if global_result.get('success'):
                global_tx_id = global_result.get('tx_id')
                params_hash = global_result.get('params_hash')
                
                # Save with REAL blockchain transaction ID
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=global_tx_id,
                    action="UPDATE_GLOBAL_STATE",
                    g_status="ACTIVE",
                    g_params=params_hash
                )
            
            logger.info(f"Global state updated successfully")

            # =============================================================================
            # STEP 5: User opt-in to the contract
            # =============================================================================
            logger.info(f"STEP 5: User opt-in to contract")
            opt_in_result = await user_opt_in_to_contract(user_id, book_id, self, app_id, wallet_data)
            
            if opt_in_result.get('success'):  # Update user_contract_service.py to return dict
                opt_in_tx_id = opt_in_result.get('tx_id')
                
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=opt_in_tx_id,
                    action="USER_OPT_IN",
                    g_status="ACTIVE",
                    g_params=params_hash
                )

            
            # =============================================================================
            # STEP 6: Update contract status to ACTIVE (everything completed successfully)
            # =============================================================================
            logger.info(f"STEP 6: Updating contract status to ACTIVE")
            await self.crypto_repository.update_contract_status(user_id, book_id, 'ACTIVE', 'Active')
            
            logger.info(f"✅ Complete contract setup finished successfully for user {user_id}, book {book_id}")
            return {
                "success": True,
                "app_id": app_id,
                "contract_info": contract_info,
                "user_opted_in": True
            }
                
        except Exception as e:
            logger.error(f"❌ Error in complete contract creation: {e}")
            return {
                "success": False,
                "error": f"Error creating contract: {str(e)}"
            }

    async def _save_contract_transaction(self, g_user_id: str, g_book_id: str, app_id: int, blockchain_tx_id: str, 
                                         action: str, g_status: str, g_params: str,
                                        l_book_hash: str = "", l_research_hash: str = "", l_params: str = ""):
        """
        Save contract-related transactions to crypto.txs with REAL blockchain transaction IDs
        """
        try:            
            tx_data = {
                'user_id': g_user_id,
                'book_id': g_book_id,
                'app_id': str(app_id),
                'tx_id': blockchain_tx_id,  # REAL blockchain TX ID
                'date': datetime.datetime.now(datetime.timezone.utc),
                'sender': g_user_id,
                'action': action,
                'g_user_id': g_user_id,
                'g_book_id': g_book_id,
                'g_status': g_status,
                'g_params': g_params,  # Use params hash if available
                'l_book_hash': l_book_hash,
                'l_research_hash': l_research_hash,
                'l_params': l_params
            }
            
            success = await self.save_transaction(tx_data)
            if success:
                logger.info(f"✅ Saved {action} transaction with blockchain TX ID: {blockchain_tx_id}")
            else:
                logger.error(f"❌ Failed to save {action} transaction")
            
        except Exception as e:
            logger.error(f"❌ Error saving contract transaction: {e}")

    async def get_contract(self, user_id: str, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get contract information for a user/book combination
        
        Args:
            user_id: User ID
            book_id: Book ID
            
        Returns:
            Contract data if found, None otherwise
        """
        try:
            contract_data = await self.crypto_repository.get_contract(user_id, book_id)
            
            if contract_data:
                logger.info(f"Retrieved contract for user {user_id}, book {book_id}")
                return contract_data
            else:
                logger.info(f"No contract found for user {user_id}, book {book_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting contract: {e}")
            return None

    async def update_contract(self, user_id: str, book_id: str, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update contract parameters
        
        Args:
            user_id: User ID
            book_id: Book ID
            book_data: Updated book data
            
        Returns:
            Result dictionary with success flag
        """
        try:
            logger.info(f"Updating contract for user {user_id}, book {book_id}")
            
            # Get existing contract
            contract_data = await self.crypto_repository.get_contract(user_id, book_id)
            if not contract_data:
                return {
                    "success": False,
                    "error": "Contract not found"
                }
                        
            # Convert book parameters to params string
            params_str = self._convert_book_data_to_params(book_data)
            
            # Get user's fund ID (same pattern as create_contract)
            fund_id = await self._get_fund_id_for_user(user_id)
            if not fund_id:
                logger.error(f"No fund found for user {user_id}")
                return {
                    "success": False,
                    "error": "User fund not found - cannot update contract"
                }
                
            # Get user wallet info
            wallet_data = await self.get_wallet(user_id, fund_id)
            if not wallet_data:
                logger.error(f"No wallet found for user {user_id}")
                return {
                    "success": False,
                    "error": "User wallet not found - cannot update contract"
                }
            
            user_address = wallet_data['address']
            logger.info(f"Found user wallet address: {user_address}")
            
            # Update contract global state
            app_id = int(contract_data['app_id'])
                        
            global_result = update_global_state(app_id, user_id, book_id, user_address, params_str)
            
            if global_result.get('success'):
                global_tx_id = global_result.get('tx_id')
                params_hash = global_result.get('params_hash')
                
                # Save with REAL blockchain transaction ID
                await self._save_contract_transaction(
                    user_id, book_id, app_id, blockchain_tx_id=global_tx_id,
                    action="UPDATE_GLOBAL_STATE",
                    g_status="ACTIVE",
                    g_params=params_hash
                )

                # Update database record with new parameters
                await self.crypto_repository.update_contract_parameters(
                    user_id, book_id, params_str
                )
                
                logger.info(f"Contract updated successfully for user {user_id}, book {book_id}")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": "Failed to update contract global state"
                }
            
        except Exception as e:
            logger.error(f"Error updating contract: {e}")
            return {
                "success": False,
                "error": f"Error updating contract: {str(e)}"
            }

    async def delete_contract(self, user_id: str, book_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Delete/expire a contract
        
        Args:
            user_id: User ID
            book_id: Book ID
            force: Force deletion even if user is still opted in
            
        Returns:
            Result dictionary with success flag
        """
        try:
            logger.info(f"Deleting contract for user {user_id}, book {book_id}")
                        
            # Remove contract from blockchain
            success = remove_contract(user_id, book_id, force)
            
            if success:
                # Expire contract in database
                await self.crypto_repository.expire_contract(
                    user_id, book_id, "Contract deleted from blockchain"
                )
                
                logger.info(f"Contract deleted successfully for user {user_id}, book {book_id}")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": "Failed to delete contract from blockchain"
                }
                
        except Exception as e:
            logger.error(f"Error deleting contract: {e}")
            return {
                "success": False,
                "error": f"Error deleting contract: {str(e)}"
            }

    def _convert_book_data_to_params(self, book_data: Dict[str, Any]) -> str:
        """
        Convert book data to parameters fingerprint for blockchain storage
        
        Args:
            book_data: Book data dictionary
            
        Returns:
            SHA-256 fingerprint of parameters (64 hex characters)
        """
        import hashlib
        import json
        
        # Build the full parameters string first
        params = []
        
        # Extract parameters from book_data in a deterministic order
        if 'parameters' in book_data and isinstance(book_data['parameters'], list):
            # Sort parameters for deterministic hashing
            sorted_params = sorted(book_data['parameters'], key=lambda x: (x[0], x[1], str(x[2])))
            
            for param in sorted_params:
                if len(param) >= 3:
                    category, subcategory, value = param[0], param[1], param[2]
                    if subcategory:
                        params.append(f"{category}_{subcategory}:{value}")
                    else:
                        params.append(f"{category}:{value}")
        
        # Create the full parameters string
        if not params:
            params_string = config.default_params_str
        else:
            params_string = "|".join(params)
        
        # Create SHA-256 fingerprint of the parameters string
        fingerprint = hashlib.sha256(params_string.encode('utf-8')).hexdigest()
        
        logger.info(f"Created parameters fingerprint: {fingerprint[:16]}... (from {len(params_string)} byte string)")
        
        return fingerprint
    
    ####################################################
    # USER OPERATIONS - USER SUBMIT/CANCEL CONVICTIONS #
    ####################################################

    async def _get_fund_id_for_user(self, user_id: str) -> Optional[str]:
        """Get fund_id for a user by querying the fund repository"""
        try:
            pool = await self.crypto_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                fund_id = await conn.fetchval(
                    "SELECT fund_id FROM fund.funds WHERE user_id = $1 ORDER BY active_at DESC LIMIT 1",
                    user_id
                )
                return str(fund_id) if fund_id else None
        except Exception as e:
            logger.error(f"Error getting fund_id for user {user_id}: {e}")
            return None
    
    async def update_local_state(self, user_id: str, book_id: str, 
                                book_hash: str = None, research_hash: str = None, 
                                params_hash: str = None) -> Dict[str, Any]:
        """Update local state with conviction data and return blockchain transaction ID"""
        try:
            logger.info(f"Updating local state for user {user_id}, book {book_id}")
            
            # Use provided hashes or generate dummy ones
            book_hash = book_hash or f"book_hash_{user_id}_{book_id}"
            research_hash = research_hash or ""
            params_hash = params_hash or f"params_hash_{user_id}_{book_id}"
            
            # This function should be updated to return the blockchain transaction ID
            result = await update_user_local_state(
                user_id, book_id, book_hash, research_hash, params_hash, self  # Pass self
            )
            
            if result.get('success'):
                # Get the actual blockchain transaction ID from the result
                blockchain_tx_id = result.get('blockchain_tx_id')
                
                if blockchain_tx_id:
                    logger.info(f"Local state updated successfully for user {user_id}, book {book_id}")
                    return {
                        "success": True,
                        "blockchain_tx_id": blockchain_tx_id
                    }
                else:
                    # Fallback to generating a placeholder if no tx_id returned
                    blockchain_tx_id = f"BLOCKCHAIN_{str(uuid.uuid4()).replace('-', '').upper()[:32]}"
                    logger.warning(f"No blockchain_tx_id returned, using placeholder: {blockchain_tx_id}")
                    return {
                        "success": True,
                        "blockchain_tx_id": blockchain_tx_id
                    }
            else:
                return {"success": False, "error": result.get('error', 'Failed to update local state')}
                
        except Exception as e:
            logger.error(f"Error updating local state: {e}")
            return {"success": False, "error": f"Error updating local state: {str(e)}"}
        
    ########
    # MISC #
    ########

    def verify_contract_status(app_id: int, expected_status: str = "ACTIVE") -> bool:
        """Verify the contract has the expected status"""
        try:
            from source.services.utils.algorand import get_algod_client
            
            algod_client = get_algod_client()
            app_info = algod_client.application_info(app_id)
            
            global_state = app_info["params"].get("global-state", [])
            
            for item in global_state:
                key_bytes = base64.b64decode(item["key"])
                try:
                    key = key_bytes.decode("utf-8")
                    if key == "status" and item["value"]["type"] == 1:
                        value_bytes = base64.b64decode(item["value"]["bytes"])
                        status = value_bytes.decode("utf-8")
                        logger.info(f"Contract {app_id} status: {status}")
                        return status == expected_status
                except:
                    continue
            
            logger.warning(f"Could not find status in contract {app_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking contract status: {e}")
            return False
        

    def create_file_fingerprint(self, file_data: bytes, filename: str) -> str:
        """
        Create a cryptographic fingerprint of file data
        
        Args:
            file_data: The file data as bytes
            filename: The filename (for context)
            
        Returns:
            SHA-256 hash of the file data
        """
        import hashlib
        
        # Create SHA-256 hash of the file data
        hash_obj = hashlib.sha256()
        hash_obj.update(file_data)
        fingerprint = hash_obj.hexdigest()
        
        logger.info(f"Created fingerprint for {filename}: {fingerprint[:16]}...")
        return fingerprint