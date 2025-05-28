# source/db/crypto_repository.py
import logging
import time
import uuid
import json
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('crypto_repository')

class CryptoRepository:
    """Data access layer for crypto-related operations"""

    def __init__(self):
        """Initialize the crypto repository"""
        self.db_pool = DatabasePool()
