import os
import logging
import logging.handlers
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class ExchangeLoggingConfig:
    session_id: str
    enable_detailed_logging: bool
    logs_dir: str
    exchange_log_file: str

    @staticmethod
    def setup_exchange_logging(enable_detailed_logging: bool = True) -> 'ExchangeLoggingConfig':
        """
        Setup exchange logging with individual component logs only.
        """

        # Generate session ID
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create logs directory - FIXED: Ensure we write to /logs/ not /source/logs/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # From source/exchange_logging/config.py, go up 2 levels to project root
        project_root = os.path.dirname(os.path.dirname(current_dir))
        logs_dir = os.path.join(project_root, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Define log files - ONLY exchange log
        exchange_log_file = os.path.join(logs_dir, f"exchange_{session_id}.log")

        # Clear any existing handlers from root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create exchange-specific logger with file handler
        exchange_logger = logging.getLogger("exchange")
        exchange_logger.setLevel(logging.DEBUG if enable_detailed_logging else logging.INFO)

        # Remove any existing handlers
        for handler in exchange_logger.handlers[:]:
            exchange_logger.removeHandler(handler)

        # Create file handler for exchange
        exchange_file_handler = logging.FileHandler(exchange_log_file, mode='w', encoding='utf-8')
        exchange_file_handler.setLevel(logging.DEBUG)

        # FIXED: Create formatter without broken %f - use custom formatter for microseconds
        class MicrosecondFormatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                if datefmt:
                    dt = datetime.fromtimestamp(record.created)
                    # Use %(msecs)03d which actually works instead of %f
                    return dt.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(record.msecs):03d}'
                return super().formatTime(record, datefmt)

        detailed_formatter = MicrosecondFormatter(
            '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s'
        )
        exchange_file_handler.setFormatter(detailed_formatter)

        # Add handler to exchange logger
        exchange_logger.addHandler(exchange_file_handler)

        # Prevent propagation to root logger
        exchange_logger.propagate = False

        # Setup console handler for important messages only
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = MicrosecondFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # Add console handler only to exchange logger
        exchange_logger.addHandler(console_handler)

        # Configure specific component loggers to use exchange logger as parent
        component_loggers = [
            "source.app",
            "source.managers",
            "source.exchange",
            "source.servers",
            "source.sod",
            "AppState",
            "AccountManager",
            "PortfolioManager",
            "EquityManager",
            "OrderManager",
            "TradeManager",
            "ConvictionManager",
            "FXManager",
            "RiskManager",
            "ReturnsManager",
            "ImpactManager",
            "OrderViewManager",
            "UniverseManager",
            "CashFlowManager",
            "SessionServiceImpl",
            "MarketDataClient",
            "ConvictionServiceImpl",
            # Add gap detection and market data specific loggers
            "GapDetection",
            "ENHANCED_MULTI_USER_MARKET_DATA_CLIENT"
        ]

        for logger_name in component_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG if enable_detailed_logging else logging.INFO)
            # Clear any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            # Set parent to exchange logger (which has the file handler)
            logger.parent = exchange_logger
            logger.propagate = True

        print(f"🚀 Exchange logging configured:")
        print(f"   📁 Session ID: {session_id}")
        print(f"   📁 Exchange log: {exchange_log_file}")
        print(f"   🔧 Detailed logging: {enable_detailed_logging}")

        # FIXED: Add gap detection logger with proper formatter and comprehensive logging
        gap_logger = logging.getLogger('GapDetection')
        gap_logger.setLevel(logging.DEBUG)  # Changed to DEBUG for comprehensive logging

        # Clear any existing handlers
        for handler in gap_logger.handlers[:]:
            gap_logger.removeHandler(handler)

        gap_handler = logging.FileHandler(
            os.path.join(logs_dir, f"gap_detection_{session_id}.log"),
            mode='w', encoding='utf-8'
        )
        gap_handler.setFormatter(detailed_formatter)  # Use the fixed formatter
        gap_logger.addHandler(gap_handler)
        gap_logger.propagate = False

        # Make sure gap logger actually logs by adding an initial test message
        gap_logger.info("🔍 Gap detection logging initialized")
        gap_logger.info(f"📁 Gap detection log file: gap_detection_{session_id}.log")

        return ExchangeLoggingConfig(
            session_id=session_id,
            enable_detailed_logging=enable_detailed_logging,
            logs_dir=logs_dir,
            exchange_log_file=exchange_log_file
        )


def get_exchange_logger(name: str) -> logging.Logger:
    """
    Get a logger for exchange components.
    All logs will go to the exchange log file only.
    """
    # Create logger under exchange hierarchy
    if not name.startswith("exchange."):
        name = f"exchange.{name}"

    logger = logging.getLogger(name)

    # Ensure it inherits from exchange logger
    exchange_logger = logging.getLogger("exchange")
    if logger.parent != exchange_logger:
        logger.parent = exchange_logger

    return logger