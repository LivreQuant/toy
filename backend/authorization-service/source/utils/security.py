# source/utils/security.py
import os
import re
import secrets
import hashlib
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def generate_strong_password(length=12):
    """Generate a cryptographically strong random password"""
    if length < 8:
        length = 8  # Minimum secure length

    # Generate random bytes and convert to URL-safe base64
    random_bytes = secrets.token_bytes(length)
    return base64.urlsafe_b64encode(random_bytes).decode('utf-8')[:length]


def is_strong_password(password):
    """Check if a password meets minimum security requirements"""
    # Minimum length of 8 characters
    if len(password) < 8:
        return False

    # At least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False

    # At least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False

    # At least one digit
    if not re.search(r'\d', password):
        return False

    # At least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False

    return True


def hash_password(password, salt=None):
    """Hash a password using PBKDF2 with HMAC-SHA256"""
    if salt is None:
        salt = os.urandom(16)  # Generate a random 16-byte salt

    # Use PBKDF2 with 100,000 iterations
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    # Derive a key from the password
    key = kdf.derive(password.encode())

    # Encode the salt and key for storage
    salt_b64 = base64.b64encode(salt).decode()
    key_b64 = base64.b64encode(key).decode()

    # Format: iterations$salt$key
    return f"pbkdf2:sha256:100000${salt_b64}${key_b64}"


def verify_password(stored_hash, password):
    """Verify a password against a stored hash"""
    # Parse the stored hash
    try:
        # Format: pbkdf2:sha256:iterations$salt$key
        algorithm, iterations, salt_b64, key_b64 = stored_hash.split('$')

        # Extract algorithm and iterations
        algo_parts = algorithm.split(':')
        if len(algo_parts) != 3 or algo_parts[0] != 'pbkdf2' or algo_parts[1] != 'sha256':
            return False

        # Decode the salt and stored key
        salt = base64.b64decode(salt_b64)
        stored_key = base64.b64decode(key_b64)

        # Use the same KDF parameters to derive a key from the input password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=int(algo_parts[2]),
        )

        # Derive a key from the input password
        key = kdf.derive(password.encode())

        # Compare the derived key with the stored key
        return secrets.compare_digest(key, stored_key)
    except Exception:
        return False


def sanitize_input(input_string):
    """Basic input sanitization to prevent SQL injection and XSS"""
    if input_string is None:
        return None

    # Remove potentially dangerous characters
    sanitized = re.sub(r'[\'";:<>&]', '', input_string)

    # Limit length
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]

    return sanitized
