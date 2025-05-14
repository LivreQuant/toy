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
