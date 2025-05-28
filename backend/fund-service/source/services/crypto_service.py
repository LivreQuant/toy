# services/crypto_service.py
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes as crypto_hashes
from cryptography.hazmat.primitives import serialization


def verify_signature(
    hash_value: str, signature_hex: str, public_key_pem: bytes
) -> bool:
    """
    Verify a signature against a hash value using the public key.

    Args:
        hash_value: Original hash that was signed
        signature_hex: Hex-encoded signature to verify
        public_key_pem: PEM-encoded public key

    Returns:
        True if signature is valid, False otherwise
    """
    public_key = serialization.load_pem_public_key(public_key_pem)

    try:
        public_key.verify(
            bytes.fromhex(signature_hex),
            hash_value.encode(),
            padding.PSS(
                mgf=padding.MGF1(crypto_hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            crypto_hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def sign_hash_deterministic(hash_value: str, secret_passphrase: str) -> str:
    """
    Create a deterministic signature using HMAC with the secret passphrase.

    Args:
        hash_value: The hash to sign
        secret_passphrase: Secret passphrase

    Returns:
        Deterministic signature as a hex string
    """
    import hmac
    import hashlib

    # Use HMAC with the passphrase as the key - this is deterministic
    signature = hmac.new(
        key=secret_passphrase.encode(),
        msg=hash_value.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return signature
