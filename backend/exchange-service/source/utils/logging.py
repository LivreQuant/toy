import logging
import sys
import json
import os
from datetime import datetime
from source.config import config

def setup_logging():
    """Set up logging configuration"""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    if config.environment.lower() == 'production':
        setup_json_logging(log_level)
    else:
        setup_dev_logging(log_level)

    # Set log levels for noisy libraries
    logging.getLogger('grpc').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

def setup_dev_logging(log_level):
    """Setup human-readable logging for development"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

def setup_json_logging(log_level):
    """Setup structured JSON logging for production"""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

class JsonFormatter(logging.Formatter):
    """JSON log formatter"""
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)