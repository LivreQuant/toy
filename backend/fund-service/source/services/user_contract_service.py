# source/services/user_contract_service.py
import logging

from typing import Dict, Any

from source.services.utils.algorand import (
    get_algod_client,
    check_if_specific_user_opted_in,
    wait_for_confirmation,
)
from source.services.utils.wallet import (
    get_wallet_credentials,
)
from source.services.contract_service import (
    create_method_signature,
)

from algosdk import transaction

logger = logging.getLogger(__name__)


async def user_opt_in_to_contract(user_id: str, book_id: str, crypto_manager, app_id: int = None, wallet_data: dict = None) -> bool:
    """
    Opt user into a contract.

    Args:
        user_id: User identifier
        book_id: Book identifier
        crypto_manager: CryptoManager instance to get wallet info
        app_id: Optional app_id if we already have it
        wallet_data: Optional wallet_data if we already have it

    Returns:
        True if successful, False otherwise
    """
    
    # If we already have the contract info, use it
    if app_id and wallet_data:
        logger.info(f"Using provided contract info for opt-in: app_id={app_id}")
        user_address = wallet_data['address']
        
        # Create wallet_info dict for get_wallet_credentials  
        wallet_info = {
            'address': wallet_data['address'],
            'mnemonic': wallet_data['mnemonic'],
            'mnemonic_salt': wallet_data['mnemonic_salt']
        }
    else:
        # Fallback to database lookup (existing code)
        contract_data = await crypto_manager.get_contract(user_id, book_id)
        if not contract_data:
            logger.error(f"No contract found for user {user_id} and book {book_id}")
            return False

        app_id = int(contract_data["app_id"])
        
        # Get user wallet from database
        fund_id = await crypto_manager._get_fund_id_for_user(user_id)
        if not fund_id:
            logger.error(f"No fund found for user {user_id}")
            return False
            
        wallet_data = await crypto_manager.get_wallet(user_id, fund_id)
        if not wallet_data:
            logger.error(f"No wallet found for user {user_id}")
            return False

        # Create wallet_info dict for get_wallet_credentials
        wallet_info = {
            'address': wallet_data['address'],
            'mnemonic': wallet_data['mnemonic'], 
            'mnemonic_salt': wallet_data['mnemonic_salt']
        }
    
    user_private_key, user_address = get_wallet_credentials(wallet_info)

    # Check if already opted in
    algod_client = get_algod_client()
    if check_if_specific_user_opted_in(app_id, user_address):
        logger.info(
            f"User {user_id} is already opted in to contract for book {book_id}"
        )
        return True

    logger.info(f"Opting user {user_id} into contract {app_id} for book {book_id}")

    # Create the method selector for opt_in
    opt_in_selector = create_method_signature("opt_in()uint64")

    # Create the transaction
    params = algod_client.suggested_params()
    opt_in_txn = transaction.ApplicationOptInTxn(
        sender=user_address, sp=params, index=app_id, app_args=[opt_in_selector]
    )

    signed_opt_in_txn = opt_in_txn.sign(user_private_key)
    opt_in_txid = algod_client.send_transaction(signed_opt_in_txn)

    logger.info(f"Opt-in transaction sent with ID: {opt_in_txid}")

    # Wait for confirmation
    try:
        wait_for_confirmation(algod_client, opt_in_txid)
        logger.info(f"User {user_id} successfully opted in to contract for book {book_id}")
        
        # RETURN SUCCESS WITH TRANSACTION ID
        return {
            "success": True,
            "tx_id": opt_in_txid
        }
    except Exception as e:
        logger.error(f"Error opting in to contract: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def update_user_local_state(
    user_id: str, book_id: str, book_hash: str, research_hash: str, params_str: str, crypto_manager
) -> Dict[str, Any]:
    """
    Update the local state for a user in a contract and return transaction ID.

    Args:
        user_id: User identifier
        book_id: Book identifier
        book_hash: Book hash value
        research_hash: Research hash value
        params_str: Parameters string
        crypto_manager: CryptoManager instance

    Returns:
        Dictionary with success flag and blockchain_tx_id
    """
    # Get contract info from database
    contract_data = await crypto_manager.get_contract(user_id, book_id)
    if not contract_data:
        logger.error(f"No contract found for user {user_id} and book {book_id}")
        return {"success": False, "error": "Contract not found"}

    app_id = int(contract_data["app_id"])
    
    # Get user wallet from database
    fund_id = await crypto_manager._get_fund_id_for_user(user_id)
    if not fund_id:
        logger.error(f"No fund found for user {user_id}")
        return {"success": False, "error": "Fund not found"}
        
    wallet_data = await crypto_manager.get_wallet(user_id, fund_id)
    if not wallet_data:
        logger.error(f"No wallet found for user {user_id}")
        return {"success": False, "error": "Wallet not found"}

    # Create wallet_info dict for get_wallet_credentials
    wallet_info = {
        'address': wallet_data['address'],
        'mnemonic': wallet_data['mnemonic'],
        'mnemonic_salt': wallet_data['mnemonic_salt']
    }
    
    user_private_key, user_address = get_wallet_credentials(wallet_info)

    # Check if opted in
    algod_client = get_algod_client()
    if not check_if_specific_user_opted_in(app_id, user_address):
        logger.error(f"User {user_id} is not opted in to contract for book {book_id}")
        return {"success": False, "error": "User not opted in to contract"}

    logger.info(f"Updating local state for user {user_id} in contract {app_id}")

    # Add ABI encoding (2-byte length prefix) to match what the contract expects
    book_hash_bytes = len(book_hash).to_bytes(2, byteorder="big") + book_hash.encode()
    research_hash_bytes = (
        len(research_hash).to_bytes(2, byteorder="big") + research_hash.encode()
    )
    params_bytes = len(params_str).to_bytes(2, byteorder="big") + params_str.encode()

    # Create the method selector for update_local
    update_local_selector = create_method_signature(
        "update_local(byte[],byte[],byte[])uint64"
    )

    # Create the transaction
    params = algod_client.suggested_params()
    update_txn = transaction.ApplicationNoOpTxn(
        sender=user_address,
        sp=params,
        index=app_id,
        app_args=[
            update_local_selector,
            book_hash_bytes,
            research_hash_bytes,
            params_bytes,
        ],
    )

    signed_update_txn = update_txn.sign(user_private_key)
    update_txid = algod_client.send_transaction(signed_update_txn)

    logger.info(f"Update local state transaction sent with ID: {update_txid}")

    # Wait for confirmation
    try:
        wait_for_confirmation(algod_client, update_txid)
        logger.info(
            f"Local state updated successfully for user {user_id} in contract for book {book_id}"
        )
        return {
            "success": True,
            "blockchain_tx_id": update_txid
        }
    except Exception as e:
        logger.error(f"Error updating local state: {e}")
        return {"success": False, "error": f"Error updating local state: {str(e)}"}


async def user_close_out_from_contract(user_id: str, book_id: str, crypto_manager) -> bool:
    """
    Close out a user from a contract.

    Args:
        user_id: User identifier
        book_id: Book identifier
        crypto_manager: CryptoManager instance

    Returns:
        True if successful, False otherwise
    """
    # Get contract info from database
    contract_data = await crypto_manager.get_contract(user_id, book_id)
    if not contract_data:
        logger.error(f"No contract found for user {user_id} and book {book_id}")
        return False

    app_id = int(contract_data["app_id"])
    
    # Get user wallet from database
    fund_id = await crypto_manager._get_fund_id_for_user(user_id)
    if not fund_id:
        logger.error(f"No fund found for user {user_id}")
        return False
        
    wallet_data = await crypto_manager.get_wallet(user_id, fund_id)
    if not wallet_data:
        logger.error(f"No wallet found for user {user_id}")
        return False

    # Create wallet_info dict for get_wallet_credentials
    wallet_info = {
        'address': wallet_data['address'],
        'mnemonic': wallet_data['mnemonic'],
        'mnemonic_salt': wallet_data['mnemonic_salt']
    }
    
    user_private_key, user_address = get_wallet_credentials(wallet_info)

    # Check if opted in
    algod_client = get_algod_client()
    if not check_if_specific_user_opted_in(app_id, user_address):
        logger.info(
            f"User {user_id} is not opted in to contract for book {book_id}, nothing to close out from"
        )
        return True

    logger.info(f"Closing out user {user_id} from contract {app_id} for book {book_id}")

    # Create the method selector for close_out
    close_out_selector = create_method_signature("close_out()uint64")

    # Create the transaction
    params = algod_client.suggested_params()
    close_out_txn = transaction.ApplicationCloseOutTxn(
        sender=user_address, sp=params, index=app_id, app_args=[close_out_selector]
    )

    signed_close_out_txn = close_out_txn.sign(user_private_key)
    close_out_txid = algod_client.send_transaction(signed_close_out_txn)

    logger.info(f"Close-out transaction sent with ID: {close_out_txid}")

    # Wait for confirmation
    try:
        wait_for_confirmation(algod_client, close_out_txid)
        logger.info(
            f"User {user_id} successfully closed out from contract for book {book_id}"
        )
        return True
    except Exception as e:
        logger.error(f"Error closing out from contract: {e}")
        return False