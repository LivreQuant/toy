# backend/fund-service/source/core/crypto_manager.py
import logging
import hashlib
import json
import time
from typing import Dict, Any, Optional, List

from source.db.crypto_repository import CryptoRepository
from source.config import config

from source.services.utils.wallet import generate_algorand_wallet, get_wallet_credentials

from source.services.utils.algorand import get_algod_client, fund_account, check_balance, get_account_from_mnemonic

from source.services.contract_service import deploy_contract_for_user_book, update_global_state, remove_contract

from source.services.user_contract_service import user_opt_in_to_contract, user_close_out_from_contract, update_user_local_state

logger = logging.getLogger('crypto_manager')

class CryptoManager:
    """Manager for blockchain and cryptographic operations"""

    def __init__(self, crypto_repository: CryptoRepository):
        """Initialize the crypto manager with dependencies"""
        self.crypto_repository = crypto_repository

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
        Create a new contract for a user/book combination
        
        Args:
            user_id: User ID
            book_id: Book ID
            book_data: Book data for contract parameters
            
        Returns:
            Result dictionary with success flag and contract info
        """
        try:
            logger.info(f"Creating contract for user {user_id}, book {book_id}")
            
            # Check if contract already exists
            existing_contract = await self.crypto_repository.get_contract(user_id, book_id)
            if existing_contract:
                logger.info(f"Contract already exists for user {user_id}, book {book_id}")
                return {
                    "success": True,
                    "app_id": existing_contract['app_id'],
                    "contract_info": existing_contract
                }
                        
            # Convert book parameters to params string
            params_str = self._convert_book_data_to_params(book_data)
            
            # Deploy contract
            contract_info = deploy_contract_for_user_book(user_id, book_id, params_str)
            
            if contract_info and contract_info.get('app_id'):
                # Save to database
                contract_data = {
                    'app_id': str(contract_info['app_id']),
                    'app_address': contract_info['app_address'],
                    'parameters': params_str,
                    'status': 'ACTIVE',
                    'blockchain_status': 'Active'
                }
                
                success = await self.crypto_repository.save_contract(user_id, book_id, contract_data)
                
                if success:
                    logger.info(f"Contract created successfully for user {user_id}, book {book_id}")
                    return {
                        "success": True,
                        "app_id": contract_info['app_id'],
                        "contract_info": contract_info
                    }
                else:
                    logger.error("Failed to save contract to database")
                    return {
                        "success": False,
                        "error": "Failed to save contract to database"
                    }
            else:
                logger.error("Failed to deploy contract")
                return {
                    "success": False,
                    "error": "Failed to deploy contract"
                }
                
        except Exception as e:
            logger.error(f"Error creating contract: {e}")
            return {
                "success": False,
                "error": f"Error creating contract: {str(e)}"
            }

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

    async def get_contracts(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all contracts for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of contract data
        """
        try:
            contracts = await self.crypto_repository.get_user_contracts(user_id)
            logger.info(f"Retrieved {len(contracts)} contracts for user {user_id}")
            return contracts
            
        except Exception as e:
            logger.error(f"Error getting contracts: {e}")
            return []

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
            
            # Update contract global state
            app_id = int(contract_data['app_id'])
            
            # Get user wallet info for the address
            fund_id = book_data.get('fund_id')  # We'll need to pass this or derive it
            wallet_data = await self.get_wallet(user_id, fund_id) if fund_id else None
            user_address = wallet_data['address'] if wallet_data else None
            
            if not user_address:
                logger.error("User address not found for contract update")
                return {
                    "success": False,
                    "error": "User address not found"
                }
            
            success = update_global_state(app_id, user_id, book_id, user_address, params_str)
            
            if success:
                # Update database record
                await self.crypto_repository.update_contract_status(
                    user_id, book_id, 'ACTIVE', 'Active'
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
        Convert book data to parameters string format
        
        Args:
            book_data: Book data dictionary
            
        Returns:
            Parameters string
        """
        params = []
        
        # Extract parameters from book_data
        if 'parameters' in book_data and isinstance(book_data['parameters'], list):
            for param in book_data['parameters']:
                if len(param) >= 3:
                    category, subcategory, value = param[0], param[1], param[2]
                    if subcategory:
                        params.append(f"{category}_{subcategory}:{value}")
                    else:
                        params.append(f"{category}:{value}")
        
        # If no parameters, use default
        if not params:
            return config.default_params_str
            
        return "|".join(params)

    ####################################################
    # USER OPERATIONS - USER SUBMIT/CANCEL CONVICTIONS #
    ####################################################

    async def _get_fund_id_for_user(self, user_id: str) -> Optional[str]:
        """Get fund_id for a user by querying the fund repository"""
        # This is a helper method - you might need to add fund_repository to crypto_manager
        # For now, we can make a database query directly or add fund_repository as a dependency
        
        # Quick solution - query database directly
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
    
    async def opt_in(self, user_id: str, book_id: str) -> Dict[str, Any]:
        """User opt-in to contract"""
        try:
            logger.info(f"User {user_id} opting in to contract for book {book_id}")
            
            success = await user_opt_in_to_contract(user_id, book_id, self)  # Pass self
            
            if success:
                logger.info(f"User {user_id} opted in successfully to book {book_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "Failed to opt in to contract"}
                
        except Exception as e:
            logger.error(f"Error in opt-in: {e}")
            return {"success": False, "error": f"Error in opt-in: {str(e)}"}

    async def update_local_state(self, user_id: str, book_id: str, 
                                book_hash: str = None, research_hash: str = None, 
                                params_hash: str = None) -> Dict[str, Any]:
        """Update local state with conviction data"""
        try:
            logger.info(f"Updating local state for user {user_id}, book {book_id}")
            
            # Use provided hashes or generate dummy ones
            book_hash = book_hash or f"book_hash_{user_id}_{book_id}"
            research_hash = research_hash or ""
            params_hash = params_hash or f"params_hash_{user_id}_{book_id}"
            
            success = await update_user_local_state(
                user_id, book_id, book_hash, research_hash, params_hash, self  # Pass self
            )
            
            if success:
                logger.info(f"Local state updated successfully for user {user_id}, book {book_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "Failed to update local state"}
                
        except Exception as e:
            logger.error(f"Error updating local state: {e}")
            return {"success": False, "error": f"Error updating local state: {str(e)}"}

    async def opt_out(self, user_id: str, book_id: str) -> Dict[str, Any]:
        """User opt-out from contract"""
        try:
            logger.info(f"User {user_id} opting out from contract for book {book_id}")
            
            success = await user_close_out_from_contract(user_id, book_id, self)  # Pass self
            
            if success:
                logger.info(f"User {user_id} opted out successfully from book {book_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "Failed to opt out from contract"}
                
        except Exception as e:
            logger.error(f"Error in opt-out: {e}")
            return {"success": False, "error": f"Error in opt-out: {str(e)}"}