# utils/wallet.py (updated with proper config integration)

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from algosdk import account, mnemonic

from source.config import config
from source.services.utils.encryption import (
    encrypt_string, 
    decrypt_string
)
from source.services.utils.algorand import (
    get_algod_client, 
    check_balance,
    fund_account,
    get_account_from_mnemonic
)

# Configure logging
logger = logging.getLogger("wallet_utils")


def generate_algorand_wallet(name: str = "wallet") -> Dict[str, Any]:
    """
    Generate a new Algorand wallet - ALWAYS encrypted for security.
    
    Args:
        name: A name to identify this wallet (e.g. "admin" or "user")
        
    Returns:
        Dictionary with encrypted wallet information
    """
    # Verify we have encryption capability
    if not config.secret_pass_phrase:
        raise ValueError("SECRET_PASS_PHRASE is required for wallet security")
    
    logger.info(f"Generating encrypted wallet: {name}")
    
    # Generate a new private key and address
    private_key, address = account.generate_account()
    wallet_mnemonic = mnemonic.from_private_key(private_key)

    # Always encrypt sensitive data
    mnemonic_encrypted, salt1 = encrypt_string(wallet_mnemonic, config.secret_pass_phrase)
    private_key_hex = private_key.hex() if isinstance(private_key, bytes) else private_key
    private_key_encrypted, salt2 = encrypt_string(private_key_hex, config.secret_pass_phrase)

    # Always return encrypted wallet info
    wallet_info = {
        "name": name,
        "address": address,
        "mnemonic": mnemonic_encrypted,
        "mnemonic_salt": salt1,
        "private_key_str": private_key_encrypted,
        "private_key_salt": salt2,
    }
    
    logger.info(f"Generated encrypted wallet for {name} with address {address}")
    return wallet_info


def get_wallet_credentials(
    wallet_info: Dict[str, Any], passphrase: str = None
) -> Tuple[str, str]:
    """
    Get private key and address from wallet info - assumes always encrypted.

    Args:
        wallet_info: The encrypted wallet information dictionary
        passphrase: The passphrase for decryption (uses config.secret_pass_phrase if None)

    Returns:
        Tuple of (private_key, address)
    """
    address = wallet_info["address"]

    # Use provided passphrase or the environment variable
    if passphrase is None:
        passphrase = config.secret_pass_phrase

    if not passphrase:
        raise ValueError("Passphrase is required for decrypting wallet")

    # Always decrypt - we assume all wallets are encrypted
    try:
        # Try mnemonic first
        if "mnemonic" in wallet_info and "mnemonic_salt" in wallet_info:
            wallet_mnemonic = decrypt_string(
                wallet_info["mnemonic"], passphrase, wallet_info["mnemonic_salt"]
            )
            private_key = mnemonic.to_private_key(wallet_mnemonic)
            return private_key, address
    except Exception as e:
        logger.error(f"Failed to decrypt mnemonic: {e}")

    # Try private key as fallback
    try:
        if "private_key_str" in wallet_info and "private_key_salt" in wallet_info:
            private_key_hex = decrypt_string(
                wallet_info["private_key_str"],
                passphrase,
                wallet_info["private_key_salt"],
            )
            # Convert hex string back to bytes
            private_key = bytes.fromhex(private_key_hex)
            return private_key, address
    except Exception as e2:
        logger.error(f"Failed to decrypt private key: {e2}")
        raise ValueError("Could not decrypt wallet credentials")

    raise ValueError("No valid encrypted credentials found in wallet info")


def get_admin_credentials() -> Tuple[str, str]:
    """
    Get admin wallet private key and address from environment configuration.
    
    Returns:
        Tuple of (private_key, address)
        
    Raises:
        ValueError: If admin mnemonic is not configured
    """
    if not config.admin_mnemonic:
        raise ValueError("ADMIN_MNEMONIC not found in environment variables")
    
    try:
        # Check if the mnemonic is encrypted (contains colon separator)
        if ":" in config.admin_mnemonic:
            # Encrypted mnemonic format: "encrypted_data:salt"
            encrypted_mnemonic, salt = config.admin_mnemonic.split(":", 1)
            
            if not config.secret_pass_phrase:
                raise ValueError("SECRET_PASS_PHRASE is required to decrypt admin mnemonic")
            
            # Decrypt the mnemonic
            decrypted_mnemonic = decrypt_string(encrypted_mnemonic, config.secret_pass_phrase, salt)
            return get_account_from_mnemonic(decrypted_mnemonic)
        else:
            # Plain text mnemonic
            return get_account_from_mnemonic(config.admin_mnemonic)
            
    except Exception as e:
        logger.error(f"Error getting admin credentials: {e}")
        raise ValueError(f"Could not retrieve admin credentials: {str(e)}")


def decrypt_admin_mnemonic() -> str:
    """
    Decrypt the admin mnemonic from environment variables.
    
    Returns:
        Decrypted admin mnemonic
        
    Raises:
        ValueError: If admin mnemonic is not configured or cannot be decrypted
    """
    if not config.admin_mnemonic:
        raise ValueError("ADMIN_MNEMONIC not found in environment variables")

    # Check if encrypted (contains a colon separator)
    if ":" in config.admin_mnemonic:
        encrypted_mnemonic, salt = config.admin_mnemonic.split(":", 1)

        if not config.secret_pass_phrase:
            raise ValueError("SECRET_PASS_PHRASE is required to decrypt admin mnemonic")

        return decrypt_string(encrypted_mnemonic, config.secret_pass_phrase, salt)
    else:
        # Not encrypted
        return config.admin_mnemonic


def ensure_wallet_funded(address: str, min_balance: float = 1.0) -> bool:
    """
    Ensure wallet has sufficient funds, fund if necessary.
    
    Args:
        address: Wallet address to check/fund
        min_balance: Minimum balance in Algos
        
    Returns:
        True if wallet is funded, False if funding failed
    """
    # Get the algod client
    algod_client = get_algod_client()

    # Check current balance
    current_balance = check_balance(algod_client, address)

    # If wallet has sufficient balance, return True
    if current_balance >= min_balance:
        logger.info(f"Wallet {address} already has sufficient funds ({current_balance} Algos)")
        return True

    # Get admin credentials for funding
    try:
        admin_private_key, admin_address = get_admin_credentials()
    except Exception as e:
        logger.error(f"Cannot get admin credentials for funding: {e}")
        return False

    # Check admin balance
    admin_balance = check_balance(algod_client, admin_address)

    # Fund wallet if admin has sufficient balance
    if admin_balance < min_balance + 1:
        logger.warning(f"Admin wallet doesn't have enough funds to transfer ({admin_balance} Algos)")
        return False

    # Fund the wallet
    amount_to_fund = min_balance + 1  # Add extra for transaction fees
    try:
        result = fund_account(
            algod_client, admin_private_key, admin_address, address, amount_to_fund
        )
        if result:
            logger.info(f"Funded wallet {address} with {amount_to_fund} Algos")
            return True
        else:
            logger.error(f"Failed to fund wallet {address}")
            return False
    except Exception as e:
        logger.error(f"Error funding wallet: {e}")
        return False


def validate_mnemonic(mnemonic_phrase: str) -> bool:
    """
    Validate if a mnemonic phrase is valid.
    
    Args:
        mnemonic_phrase: The mnemonic phrase to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Try to convert mnemonic to private key
        mnemonic.to_private_key(mnemonic_phrase)
        return True
    except Exception:
        return False


def get_address_from_mnemonic(mnemonic_phrase: str) -> str:
    """
    Get address from a mnemonic phrase.
    
    Args:
        mnemonic_phrase: The mnemonic phrase
        
    Returns:
        The wallet address
        
    Raises:
        ValueError: If mnemonic is invalid
    """
    try:
        private_key = mnemonic.to_private_key(mnemonic_phrase)
        return account.address_from_private_key(private_key)
    except Exception as e:
        raise ValueError(f"Invalid mnemonic phrase: {str(e)}")