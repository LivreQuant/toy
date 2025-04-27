# source/utils/logging_utils.py
import logging
import sys
from datetime import datetime
import json

from source.config import config


def setup_logging():
    """Configure logging for the application"""
    
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Determine if we're in a Kubernetes environment
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        # Use structured JSON logging for Kubernetes
        formatter = JsonFormatter()
    else:
        # Use more readable format for local development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set log levels for noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    return root_logger


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)
    