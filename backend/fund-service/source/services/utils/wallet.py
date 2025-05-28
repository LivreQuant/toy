# utils/wallet.py (updated with encryption)

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from dotenv import load_dotenv
from algosdk import account, mnemonic

from source.services.utils.encryption import (
    encrypt_string, 
    decrypt_string
)
from source.services.utils.algorand import (
    get_algod_client, 
    check_balance,
    fund_account
)

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("wallet_utils")

# Get secret passphrase from environment
SECRET_PASS_PHRASE = os.getenv("SECRET_PASS_PHRASE")


def generate_algorand_wallet(
    name: str = "wallet", encrypt: bool = True
) -> Dict[str, Any]:
    """
    Generate a new Algorand wallet including private key, address, and mnemonic.

    Args:
        name: A name to identify this wallet (e.g. "admin" or "user")
        encrypt: Whether to encrypt sensitive data

    Returns:
        Dictionary with wallet information
    """
    # Generate a new private key and address
    private_key, address = account.generate_account()

    # Generate the mnemonic for the private key
    wallet_mnemonic = mnemonic.from_private_key(private_key)

    # Encrypt sensitive data if requested
    if encrypt and SECRET_PASS_PHRASE:
        mnemonic_encrypted, salt1 = encrypt_string(wallet_mnemonic, SECRET_PASS_PHRASE)
        private_key_encrypted, salt2 = encrypt_string(
            private_key.hex(), SECRET_PASS_PHRASE
        )

        # Create wallet info object with encrypted data
        wallet_info = {
            "name": name,
            "address": address,
            "mnemonic": mnemonic_encrypted,
            "mnemonic_salt": salt1,
            "private_key_str": private_key_encrypted,
            "private_key_salt": salt2,
            "encrypted": True,
        }
    else:
        # Create wallet info object with plaintext data
        wallet_info = {
            "name": name,
            "address": address,
            "private_key": private_key,
            "mnemonic": wallet_mnemonic,
            "encrypted": False,
        }

    return wallet_info


def get_wallet_credentials(
    wallet_info: Dict[str, Any], passphrase: str = None
) -> Tuple[str, str]:
    """
    Get private key and address from wallet info, decrypting if necessary.

    Args:
        wallet_info: The wallet information dictionary
        passphrase: The passphrase for decryption (uses SECRET_PASS_PHRASE if None)

    Returns:
        Tuple of (private_key, address)
    """
    address = wallet_info["address"]

    if wallet_info.get("encrypted", False):
        # Use provided passphrase or the environment variable
        if passphrase is None:
            passphrase = SECRET_PASS_PHRASE

        if not passphrase:
            raise ValueError("Passphrase is required for decrypting wallet")

        # Decrypt mnemonic and get private key
        try:
            wallet_mnemonic = decrypt_string(
                wallet_info["mnemonic"], passphrase, wallet_info["mnemonic_salt"]
            )
            private_key = mnemonic.to_private_key(wallet_mnemonic)
            return private_key, address
        except Exception as e:
            logger.error(f"Failed to decrypt mnemonic: {e}")

            # Try with private key if available
            try:
                if (
                    "private_key_str" in wallet_info
                    and "private_key_salt" in wallet_info
                ):
                    private_key_hex = decrypt_string(
                        wallet_info["private_key_str"],
                        passphrase,
                        wallet_info["private_key_salt"],
                    )
                    return bytes.fromhex(private_key_hex), address
            except Exception as e2:
                logger.error(f"Failed to decrypt private key: {e2}")
                raise ValueError("Could not decrypt wallet credentials")
    else:
        # Handle unencrypted wallet info
        if "private_key" in wallet_info:
            return wallet_info["private_key"], address
        elif "private_key_hex" in wallet_info:
            return bytes.fromhex(wallet_info["private_key_hex"]), address
        elif "mnemonic" in wallet_info:
            return mnemonic.to_private_key(wallet_info["mnemonic"]), address
        else:
            raise ValueError("No private key or mnemonic found in wallet info")


def decrypt_admin_mnemonic() -> str:
    """
    Decrypt the admin mnemonic from environment variables.

    Returns:
        Decrypted admin mnemonic
    """
    admin_mnemonic_env = os.getenv("ADMIN_MNEMONIC")

    if not admin_mnemonic_env:
        raise ValueError("ADMIN_MNEMONIC not found in environment variables")

    # Check if encrypted (contains a colon separator)
    if ":" in admin_mnemonic_env:
        encrypted_mnemonic, salt = admin_mnemonic_env.split(":", 1)

        if not SECRET_PASS_PHRASE:
            raise ValueError("SECRET_PASS_PHRASE is required to decrypt admin mnemonic")

        return decrypt_string(encrypted_mnemonic, SECRET_PASS_PHRASE, salt)
    else:
        # Not encrypted
        return admin_mnemonic_env
