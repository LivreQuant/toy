"""
Logging configuration for the Session Service.
Provides structured JSON logging for production and human-readable logs for development.
"""
import logging
import sys
import json
from datetime import datetime

from source.config import config

def setup_logging():
    """Set up logging with appropriate format based on environment"""
    log_level_name = config.log_level
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    
    # Determine if we're in a production environment
    is_production = config.environment == 'production'
    
    if is_production:
        # In production, use JSON format for structured logging
        setup_json_logging(log_level)
    else:
        # In development, use a more readable format
        setup_dev_logging(log_level)
    
    # Set log levels for some noisy libraries
    logging.getLogger('grpc').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)

def setup_json_logging(log_level):
    """Set up JSON structured logging for production"""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    
    # Add stdout JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

def setup_dev_logging(log_level):
    """Set up developer-friendly logging"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
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
        
        # Add any extra attributes
        for key, value in record.__dict__.items():
            if key not in ['args', 'asctime', 'created', 'exc_info', 'exc_text', 
                           'filename', 'funcName', 'id', 'levelname', 'levelno', 
                           'lineno', 'module', 'msecs', 'message', 'msg', 
                           'name', 'pathname', 'process', 'processName', 
                           'relativeCreated', 'stack_info', 'thread', 'threadName']:
                log_data[key] = value
        
        return json.dumps(log_data)