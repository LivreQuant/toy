import os

class Config:
    # Service configuration
    PORT = int(os.getenv('PORT', '50055'))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Simulator settings
    INACTIVITY_TIMEOUT_SECONDS = int(os.getenv('INACTIVITY_TIMEOUT_SECONDS', '300'))
    AUTO_TERMINATE = os.getenv('AUTO_TERMINATE', 'true').lower() == 'true'
    
    # Market data settings
    DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    DEFAULT_INITIAL_CASH = float(os.getenv('DEFAULT_INITIAL_CASH', '100000.0'))
    MARKET_UPDATE_INTERVAL_SECONDS = float(os.getenv('MARKET_UPDATE_INTERVAL_SECONDS', '1.0'))
    
    # Performance settings
    MAX_WORKER_THREADS = int(os.getenv('MAX_WORKER_THREADS', '10'))