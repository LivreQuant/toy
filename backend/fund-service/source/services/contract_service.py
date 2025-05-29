# services/contract_service.py
import json
import time
import logging
import base64
from typing import Dict, Any, Optional

from source.config import config
from source.services.utils.algorand import (
    get_algod_client,
    wait_for_confirmation,
)
from source.services.utils.wallet import (
    get_admin_credentials
)

from algosdk import encoding, logic, transaction

logger = logging.getLogger(__name__)


def create_method_signature(method_signature: str) -> bytes:
    """
    Create a method signature for ARC-4 compatible smart contracts.

    Args:
        method_signature: The method signature string

    Returns:
        The first 4 bytes of the hash
    """
    return encoding.checksum(method_signature.encode())[:4]


def deploy_contract_for_user_book(
    user_id: str, book_id: str, params_str: str = None
) -> Dict[str, Any]:
    """
    Deploy a new contract for a user and book.

    Args:
        user_id: User identifier
        book_id: Book identifier
        params_str: Optional parameters string

    Returns:
        Contract info dictionary
    """
    # Use default params if none provided
    if params_str is None:
        params_str = config.default_params_str

    # Get admin credentials
    admin_private_key, admin_address = get_admin_credentials()

    # Initialize Algorand client
    algod_client = get_algod_client()

    # Load TEAL files from artifacts directory
    approval_program_path = config.contract_approval_path
    clear_program_path = config.contract_clear_path
    
    if not approval_program_path.exists():
        raise FileNotFoundError(f"Approval program not found at: {approval_program_path}")
    
    if not clear_program_path.exists():
        raise FileNotFoundError(f"Clear program not found at: {clear_program_path}")

    # Load and compile the programs
    with open(approval_program_path, "r") as f:
        approval_program_source = f.read()

    with open(clear_program_path, "r") as f:
        clear_program_source = f.read()

    approval_program = algod_client.compile(approval_program_source)["result"]
    clear_program = algod_client.compile(clear_program_source)["result"]

    # Define global schema and local schema
    global_schema = transaction.StateSchema(num_uints=0, num_byte_slices=5)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=3)

    # Define application parameters
    params = algod_client.suggested_params()

    # Create unsigned transaction
    txn = transaction.ApplicationCreateTxn(
        sender=admin_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=base64.b64decode(approval_program),
        clear_program=base64.b64decode(clear_program),
        global_schema=global_schema,
        local_schema=local_schema,
    )

    # Sign transaction
    signed_txn = txn.sign(admin_private_key)

    # Send transaction
    txid = algod_client.send_transaction(signed_txn)
    logger.info(f"Contract creation transaction sent with ID: {txid}")

    # Wait for confirmation
    tx_info = wait_for_confirmation(algod_client, txid)

    # Get the application ID
    app_id = tx_info.get("application-index")
    logger.info(f"Created application with ID: {app_id}")

    # Fund the contract account
    app_address = logic.get_application_address(app_id)
    logger.info(f"Application address: {app_address}")

    # Fund the application with specified amount
    params = algod_client.suggested_params()
    fund_txn = transaction.PaymentTxn(
        sender=admin_address,
        sp=params,
        receiver=app_address,
        amt=config.default_funding_amount,
    )

    signed_fund_txn = fund_txn.sign(admin_private_key)
    fund_txid = algod_client.send_transaction(signed_fund_txn)
    logger.info(f"Funding transaction sent with ID: {fund_txid}")

    # Wait for confirmation
    wait_for_confirmation(algod_client, fund_txid)
    logger.info(
        f"Funded contract with {config.default_funding_amount / 1_000_000} Algo"
    )

    # Convert strings to bytes with ABI encoding
    # Add a 2-byte length prefix to each string
    user_id_bytes = len(user_id).to_bytes(2, byteorder="big") + user_id.encode()
    book_id_bytes = len(book_id).to_bytes(2, byteorder="big") + book_id.encode()
    params_bytes = len(params_str).to_bytes(2, byteorder="big") + params_str.encode()

    # Create application call transaction to initialize contract
    params = algod_client.suggested_params()
    init_app_args = [
        create_method_signature("initialize(byte[],byte[],byte[])uint64"),
        user_id_bytes,
        book_id_bytes,
        params_bytes,
    ]

    initialize_txn = transaction.ApplicationCallTxn(
        sender=admin_address,
        sp=params,
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=init_app_args,
    )

    signed_initialize_txn = initialize_txn.sign(admin_private_key)
    initialize_txid = algod_client.send_transaction(signed_initialize_txn)
    logger.info(f"Initialization transaction sent with ID: {initialize_txid}")

    # Wait for confirmation
    wait_for_confirmation(algod_client, initialize_txid)
    logger.info(f"Contract initialized with initial values")

    # Return contract information (to be stored in PostgreSQL by caller)
    contract_info = {
        "app_id": app_id,
        "app_address": app_address,
        "user_id": user_id,
        "book_id": book_id,
        "parameters": params_str,
        "creation_timestamp": time.time(),
        "status": "ACTIVE",
        "blockchain_status": "Active",
        # ADD THESE TRANSACTION IDs
        "creation_tx_id": txid,           # Contract creation
        "funding_tx_id": fund_txid,       # Contract funding  
        "init_tx_id": initialize_txid,    # Contract initialization
    }

    logger.info(
        f"Contract deployed successfully for user {user_id} and book {book_id} with app ID {app_id}"
    )

    return contract_info


def update_global_state(
    app_id: int, user_id: str, book_id: str, user_address: str, params_str: str
) -> bool:
    """
    Update the global state of a contract.

    Args:
        app_id: Application ID
        user_id: User identifier
        book_id: Book identifier
        user_address: User wallet address
        params_str: Parameters string

    Returns:
        True if successful, False otherwise
    """
    try:
        # Debug logging
        logger.info(f"update_global_state called with:")
        logger.info(f"  app_id: {app_id}")
        logger.info(f"  user_id: {user_id}")
        logger.info(f"  book_id: {book_id}")
        logger.info(f"  user_address: {user_address}")
        logger.info(f"  params_str: {params_str}")
        
        # Get admin credentials
        admin_private_key, admin_address = get_admin_credentials()
        
        # Initialize Algorand client
        algod_client = get_algod_client()

        # Add ABI encoding (2-byte length prefix) to match what the contract expects
        user_id_bytes = len(user_id).to_bytes(2, byteorder="big") + user_id.encode()
        book_id_bytes = len(book_id).to_bytes(2, byteorder="big") + book_id.encode()
        params_bytes = len(params_str).to_bytes(2, byteorder="big") + params_str.encode()

        # Debug logging
        logger.info(f"Updating global parameters for app ID: {app_id}")
        logger.info(f"User_id: {user_id}")
        logger.info(f"Book_id: {book_id}")
        logger.info(f"User address: {user_address}")
        logger.info(f"Parameters: {params_str}")

        # Create application call transaction to update global parameters
        params = algod_client.suggested_params()

        # For the update_global method
        update_app_args = [
            create_method_signature("update_global(byte[],byte[],account,byte[])uint64"),
            user_id_bytes,
            book_id_bytes,
            (1).to_bytes(8, "big"),  # Index 0 in accounts array
            params_bytes,
        ]

        update_txn = transaction.ApplicationCallTxn(
            sender=admin_address,
            sp=params,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=update_app_args,
            accounts=[user_address],  # Pass the user address as the first entry in the accounts array
        )

        signed_update_txn = update_txn.sign(admin_private_key)
        update_txid = algod_client.send_transaction(signed_update_txn)
        logger.info(f"Update global parameters transaction sent with ID: {update_txid}")

        # Wait for confirmation
        wait_for_confirmation(algod_client, update_txid)
        logger.info(f"Contract global parameters updated successfully")
        
        # RETURN THE TRANSACTION ID
        return {
            "success": True,
            "tx_id": update_txid,
            "params_hash": params_str
        }
    except Exception as e:
        logger.error(f"Error updating global state: {e}")
        return {"success": False, "error": str(e)}


def update_contract_status(app_id: int, status: str) -> bool:
    """
    Update the status of a contract.

    Args:
        app_id: Application ID
        status: Status string ('ACTIVE', 'INACTIVE-STOP', or 'INACTIVE-SOLD')

    Returns:
        True if successful, False otherwise
    """
    # Validate status
    valid_statuses = ["ACTIVE", "INACTIVE-STOP", "INACTIVE-SOLD"]
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of {valid_statuses}")

    try:
        # Initialize Algorand client
        algod_client = get_algod_client()

        # Get admin credentials
        admin_private_key, admin_address = get_admin_credentials()

        # Add ABI encoding to status
        status_bytes = len(status).to_bytes(2, byteorder="big") + status.encode()

        # Debug logging
        logger.info(f"Updating status for app ID: {app_id}")
        logger.info(f"New status: {status}")

        # Create application call transaction to update status
        params = algod_client.suggested_params()
        app_args = [create_method_signature("update_status(string)uint64"), status_bytes]

        update_txn = transaction.ApplicationCallTxn(
            sender=admin_address,
            sp=params,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args,
        )

        signed_update_txn = update_txn.sign(admin_private_key)
        update_txid = algod_client.send_transaction(signed_update_txn)
        logger.info(f"Update status transaction sent with ID: {update_txid}")

        # Wait for confirmation
        wait_for_confirmation(algod_client, update_txid)
        logger.info(f"Contract status updated to {status}")
        
        return True
    except Exception as e:
        logger.error(f"Error updating contract status: {e}")
        return False


def remove_contract(user_id: str, book_id: str, force: bool = False) -> bool:
    """
    Remove a contract from the blockchain.
    Note: Contract info should be marked as deleted in PostgreSQL by the caller.

    Args:
        user_id: User identifier
        book_id: Book identifier
        force: Force deletion even if user is still opted in

    Returns:
        True if successful, False otherwise
    """
    try:
        # This function would need to get the app_id from PostgreSQL
        # For now, we'll assume the caller provides the app_id
        # In practice, this should be called from crypto_manager which has access to the database
        
        logger.warning("remove_contract: This function needs app_id from database")
        logger.warning("Should be called from crypto_manager.delete_contract() instead")
        
        return False
    except Exception as e:
        logger.error(f"Error in remove_contract: {e}")
        return False


def delete_contract_from_blockchain(app_id: int, force: bool = False) -> bool:
    """
    Delete a contract from the blockchain.

    Args:
        app_id: Application ID
        force: Force deletion even if user is still opted in

    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize Algorand client
        algod_client = get_algod_client()

        # Check if user is opted in (this would need to be implemented properly)
        # For now, we'll skip this check unless force is False
        
        # Get admin credentials
        admin_private_key, admin_address = get_admin_credentials()

        # Debug logging
        logger.info(f"Deleting contract with app ID: {app_id}")
        if force:
            logger.warning(
                f"CAUTION: Force deleting contract {app_id}. "
                f"This may lead to locked funds if users are still opted in!"
            )

        # Create application call transaction to delete application
        params = algod_client.suggested_params()

        app_args = [create_method_signature("delete_application()uint64")]

        delete_txn = transaction.ApplicationDeleteTxn(
            sender=admin_address, 
            sp=params, 
            index=app_id, 
            app_args=app_args
        )

        signed_delete_txn = delete_txn.sign(admin_private_key)
        delete_txid = algod_client.send_transaction(signed_delete_txn)
        logger.info(f"Delete transaction sent with ID: {delete_txid}")

        # Wait for confirmation
        wait_for_confirmation(algod_client, delete_txid)
        logger.info(f"Contract {app_id} deleted successfully from blockchain")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting contract {app_id}: {e}")
        return False
