# source/main.py - Updated market data connection logic

import asyncio
import os
import sys
import signal
import traceback
from typing import Optional, Set

from source.db.db_manager import DatabaseManager

from source.exchange_logging.config import ExchangeLoggingConfig
from source.exchange_logging.utils import get_exchange_logger

from source.orchestration.coordination.exchange_manager import EnhancedExchangeGroupManager
from source.orchestration.persistence.snapshot_manager import SnapshotManager

from source.orchestration.servers.market_data.market_data_server_impl import EnhancedMultiUserMarketDataClient
from source.orchestration.servers.session.session_server_impl import MultiUserSessionServiceImpl
from source.orchestration.servers.conviction.conviction_server_impl import ConvictionServiceImpl

# Setup detailed logging
logging_config = ExchangeLoggingConfig.setup_exchange_logging()
logger = get_exchange_logger(__name__)


class CoreExchangeServiceManager:
    """Core exchange service manager with persistent market data connection"""

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = get_exchange_logger(__name__)
        self.running = False

        # Market data connection management
        self.market_data_client: Optional[EnhancedMultiUserMarketDataClient] = None
        self.market_data_connected = False
        self.market_data_connection_task: Optional[asyncio.Task] = None

        # Optional services
        self.session_service: Optional[MultiUserSessionServiceImpl] = None
        self.conviction_service: Optional[ConvictionServiceImpl] = None

        # Track which services are enabled
        self.enabled_services: Set[str] = set()

        # database
        self.db_manager = DatabaseManager

        # Shutdown flag
        self.shutdown_requested = False

        # Market data connection settings
        self.market_data_host = os.environ.get("MARKET_DATA_HOST", "localhost")
        self.market_data_port = int(os.environ.get("MARKET_DATA_PORT", "50051"))
        self.market_data_retry_interval = int(os.environ.get("MARKET_DATA_RETRY_SECONDS", "5"))

    async def start_core_exchange(self):
        """Start the core exchange simulation - this always runs"""
        try:
            self.logger.info("🏦 Starting CORE EXCHANGE SERVICE")

            # Initialize all user contexts in exchange group manager
            users = self.exchange_group_manager.get_all_users()
            self.logger.info(f"👥 Core exchange initialized for {len(users)} users: {users}")

            # Set exchange group manager in all user equity managers
            for user_context in self.exchange_group_manager.user_contexts.values():
                user_context.app_state.equity_manager.set_exchange_group_manager(self.exchange_group_manager)

            self.running = True
            self.logger.info("✅ CORE EXCHANGE SERVICE is running independently")

        except Exception as e:
            self.logger.error(f"❌ Failed to start core exchange: {e}")
            raise

    async def start_persistent_market_data_connection(self):
        """Start persistent market data connection with auto-retry"""
        self.logger.info(
            f"📡 Starting PERSISTENT Market Data Connection to {self.market_data_host}:{self.market_data_port}")
        self.logger.info(f"🔄 Will retry every {self.market_data_retry_interval} seconds if connection fails")

        # Start the connection task
        self.market_data_connection_task = asyncio.create_task(self._market_data_connection_loop())

    async def _market_data_connection_loop(self):
        """Continuous loop to maintain market data connection"""
        attempt = 0

        while self.running and not self.shutdown_requested:
            attempt += 1

            try:
                if not self.market_data_connected:
                    self.logger.info(f"📡 Market Data Connection Attempt #{attempt}")

                    # Create new market data client
                    self.market_data_client = EnhancedMultiUserMarketDataClient(
                        exchange_group_manager=self.exchange_group_manager,
                        host=self.market_data_host,
                        port=self.market_data_port
                    )

                    # Try to connect
                    self.market_data_client.start()

                    # Link replay manager
                    self.exchange_group_manager.set_replay_manager(self.market_data_client.replay_manager)

                    self.market_data_connected = True
                    self.enabled_services.add("market_data")

                    self.logger.info(f"✅ Market Data Service: CONNECTED on attempt #{attempt}")
                    self.logger.info(
                        f"📡 Market Data: Receiving live data from {self.market_data_host}:{self.market_data_port}")

                    # Reset attempt counter on successful connection
                    attempt = 0

                # Check if connection is still alive
                if self.market_data_connected and self.market_data_client:
                    if not self._is_market_data_healthy():
                        self.logger.warning("📡 Market Data connection lost, will reconnect...")
                        self._cleanup_market_data_connection()
                        continue

                # Wait before next check/retry
                await asyncio.sleep(self.market_data_retry_interval)

            except Exception as e:
                self.logger.error(f"❌ Market Data Connection Attempt #{attempt} failed: {e}")
                self._cleanup_market_data_connection()

                # Wait before retry
                await asyncio.sleep(self.market_data_retry_interval)

    def _is_market_data_healthy(self) -> bool:
        """Check if market data connection is healthy"""
        try:
            # Add your health check logic here
            # For now, just check if client exists and has required attributes
            return (self.market_data_client is not None and
                    hasattr(self.market_data_client, 'replay_manager'))
        except Exception:
            return False

    def _cleanup_market_data_connection(self):
        """Clean up failed market data connection"""
        try:
            if self.market_data_client and hasattr(self.market_data_client, 'stop'):
                self.market_data_client.stop()
        except Exception as e:
            self.logger.error(f"❌ Error cleaning up market data connection: {e}")

        self.market_data_client = None
        self.market_data_connected = False
        self.enabled_services.discard("market_data")

    async def start_optional_session_service(self):
        """Start optional session service for up to N users"""
        try:
            self.logger.info("🔗 Starting Session Service")

            self.session_service = MultiUserSessionServiceImpl(self.exchange_group_manager)

            session_port = int(os.environ.get("SESSION_SERVICE_PORT", "50050"))
            self.session_service.start_sync_server(port=session_port)

            users = self.exchange_group_manager.get_all_users()
            self.enabled_services.add("session")

            self.logger.info(f"✅ Session Service: STARTED on port {session_port}")
            self.logger.info(f"🔗 Session Service: Ready for up to {len(users)} concurrent user connections")

        except Exception as e:
            self.logger.error(f"❌ Session Service failed to start: {e}")
            self.logger.info("🏦 Core exchange continues without session service")

    async def start_optional_conviction_service(self):
        """Start optional conviction service for up to N users"""
        try:
            self.logger.info("⚖️ Starting Conviction Service")

            self.conviction_service = ConvictionServiceImpl(self.exchange_group_manager)

            conviction_port = int(os.environ.get("CONVICTION_SERVICE_PORT", "50052"))
            await self.conviction_service.start_server(port=conviction_port)

            users = self.exchange_group_manager.get_all_users()
            self.enabled_services.add("conviction")

            self.logger.info(f"✅ Conviction Service: STARTED on port {conviction_port}")
            self.logger.info(f"⚖️ Conviction Service: Ready for up to {len(users)} concurrent user connections")

        except Exception as e:
            self.logger.error(f"❌ Conviction Service failed to start: {e}")
            self.logger.info("🏦 Core exchange continues without conviction service")

    async def start_all_services(self):
        """Start core exchange and all services"""
        try:
            # Always start core exchange first
            await self.start_core_exchange()

            # Start persistent market data connection (always attempt)
            await self.start_persistent_market_data_connection()

            # Start optional services based on environment
            if os.environ.get("ENABLE_SESSION_SERVICE", "true").lower() in ['true', '1', 'yes']:
                await self.start_optional_session_service()
            else:
                self.logger.info("🔗 Session Service: DISABLED by environment variable")

            if os.environ.get("ENABLE_CONVICTION_SERVICE", "false").lower() in ['true', '1', 'yes']:
                await self.start_optional_conviction_service()
            else:
                self.logger.info("⚖️ Conviction Service: DISABLED by environment variable")

            self.logger.info("=" * 80)
            self.logger.info("🎯 EXCHANGE SERVICE STARTUP COMPLETE")
            self.logger.info(f"🏦 Core Exchange: RUNNING ({len(self.exchange_group_manager.get_all_users())} users)")
            self.logger.info(
                f"📡 Market Data: {'CONNECTING' if not self.market_data_connected else 'CONNECTED'} (persistent retry enabled)")
            self.logger.info(f"🔗 Session Service: {'ENABLED' if 'session' in self.enabled_services else 'DISABLED'}")
            self.logger.info(
                f"⚖️ Conviction Service: {'ENABLED' if 'conviction' in self.enabled_services else 'DISABLED'}")
            self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"❌ Failed to start services: {e}")
            raise

    async def stop_all_services(self):
        """Stop all services gracefully"""
        try:
            self.logger.info("🛑 STOPPING ALL SERVICES")
            self.shutdown_requested = True

            # Stop market data connection task
            if self.market_data_connection_task:
                self.market_data_connection_task.cancel()
                try:
                    await self.market_data_connection_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("✅ Market Data Connection Task: STOPPED")

            # Stop session service
            if self.session_service and hasattr(self.session_service, 'stop'):
                try:
                    self.session_service.stop()
                    self.logger.info("✅ Session Service: STOPPED")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping session service: {e}")

            # Stop conviction service
            if self.conviction_service and hasattr(self.conviction_service, 'stop_server'):
                try:
                    await self.conviction_service.stop_server()
                    self.logger.info("✅ Conviction Service: STOPPED")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping conviction service: {e}")

            # Clean up market data connection
            self._cleanup_market_data_connection()
            self.logger.info("✅ Market Data Service: STOPPED")

            # Stop core exchange
            self.running = False
            self.logger.info("✅ Core Exchange: STOPPED")
            self.logger.info("🛑 ALL SERVICES STOPPED")

        except Exception as e:
            self.logger.error(f"❌ Error stopping services: {e}")

    async def run_forever(self):
        """Run the exchange service indefinitely until shutdown"""
        try:
            self.logger.info("🔄 Exchange service running indefinitely...")
            self.logger.info("📡 Market data connection will auto-retry every 10 seconds if disconnected")

            # Main service loop
            while self.running and not self.shutdown_requested:
                await asyncio.sleep(1.0)

                # Optional: Periodic health checks
                if self.running:
                    await self._periodic_health_check()

            self.logger.info("🔄 Exchange service loop ended")

        except Exception as e:
            self.logger.error(f"❌ Error in service loop: {e}")

    async def _periodic_health_check(self):
        """Periodic health check for all services"""
        if hasattr(self, '_health_check_counter'):
            self._health_check_counter += 1
        else:
            self._health_check_counter = 1

        if self._health_check_counter % 60 == 0:  # Every 60 seconds
            active_services = len(self.enabled_services)
            users = len(self.exchange_group_manager.get_all_users())
            market_status = "CONNECTED" if self.market_data_connected else "RETRYING"

            self.logger.info(
                f"💓 Health Check: Core Exchange running for {users} users, {active_services} services active, Market Data: {market_status}")


async def initialize_core_exchange(group_id: str) -> EnhancedExchangeGroupManager:
    """Initialize core exchange simulation with enhanced logging and error handling"""
    try:
        logger.info("=" * 80)
        logger.info(f"🏦 INITIALIZING CORE EXCHANGE for group: {group_id}")
        logger.info("=" * 80)

        # Check environment configuration
        from source.config import app_config
        logger.info(f"🔧 Environment: {app_config.environment}")
        logger.info(f"🔧 Is production: {app_config.is_production}")
        logger.info(f"🔧 Use database storage: {app_config.use_database_storage}")

        # Initialize database connection only if in production mode
        if app_config.is_production:
            logger.info("🔄 Production mode detected - initializing database connection...")

            # Check database configuration
            logger.info(f"🔧 Database host: {app_config.database.host}")
            logger.info(f"🔧 Database port: {app_config.database.port}")
            logger.info(f"🔧 Database name: {app_config.database.database}")
            logger.info(f"🔧 Database user: {app_config.database.user}")
            logger.info(f"🔧 Connection string: {app_config.database.connection_string}")

            # Import and initialize database manager
            from source.db.db_manager import db_manager

            # Test database connection with proper timeout
            async def init_and_test_db():
                try:
                    logger.info("🔄 Initializing database connection...")
                    await db_manager.initialize()
                    logger.info("✅ Database connection initialized")

                    # Test basic query
                    logger.info("🔄 Testing database query...")
                    metadata = await db_manager.load_exchange_metadata(group_id)
                    if metadata:
                        logger.info(f"✅ Database query successful for group: {group_id}")
                        logger.info(f"   Exchange type: {metadata.get('exchange_type')}")
                        logger.info(f"   Timezone: {metadata.get('timezone')}")
                    else:
                        logger.warning(f"⚠️ No metadata found for group: {group_id}")

                    return True
                except Exception as e:
                    logger.error(f"❌ Database test failed: {e}")
                    return False

            # Run database initialization - FIXED THE ASYNC ISSUE
            try:
                logger.info("🔄 Testing database connection with 10 second timeout...")
                db_success = await asyncio.wait_for(init_and_test_db(), timeout=10)
            except asyncio.TimeoutError:
                logger.error("❌ Database connection timeout after 10 seconds")
                logger.error("🔧 Check database connectivity and performance")
                raise RuntimeError("Database connection timeout")

            if not db_success:
                logger.error("❌ Database initialization failed")
                raise RuntimeError("Database initialization failed")

            logger.info("✅ Database connection and testing successful")
        else:
            logger.info("🔄 Development mode - skipping database initialization")

        # Step 1: Initialize snapshot manager
        logger.info("📸 Step 1: Initializing snapshot manager...")
        snapshot_manager = SnapshotManager(group_id=group_id)
        logger.info("✅ Snapshot manager created")

        # Step 2: Load snapshot data
        logger.info("📂 Step 2: Loading snapshot data...")
        logger.info("⏳ Looking for required data files or database records...")

        # Initialize snapshot data
        initialization_success = await snapshot_manager.initialize_multi_user_from_snapshot()

        if not initialization_success:
            logger.error("❌ Failed to initialize exchange snapshot data")
            logger.error("🔧 Check if required data files are present or database has data")
            raise RuntimeError("Failed to initialize exchange snapshot data")

        logger.info("✅ Snapshot initialization successful")

        # Step 3: Get the regular exchange group manager
        logger.info("📊 Step 3: Getting exchange group manager...")
        regular_exchange_group_manager = snapshot_manager.get_exchange_group_manager()

        if not regular_exchange_group_manager:
            logger.error("❌ Exchange group manager is None")
            logger.error("🔧 This usually indicates a problem with metadata loading")
            raise RuntimeError("Exchange group manager is None")

        logger.info("✅ Exchange group manager retrieved successfully")

        # Step 4: Create enhanced exchange group manager
        logger.info("🚀 Step 4: Creating enhanced exchange group manager...")
        enhanced_exchange_group_manager = EnhancedExchangeGroupManager(
            group_id=regular_exchange_group_manager.group_id,
        )

        # Step 5: Copy all initialized state
        logger.info("📋 Step 5: Copying initialized state...")
        enhanced_exchange_group_manager.metadata = regular_exchange_group_manager.metadata
        enhanced_exchange_group_manager.user_contexts = regular_exchange_group_manager.user_contexts
        enhanced_exchange_group_manager.last_snap_time = regular_exchange_group_manager.last_snap_time
        enhanced_exchange_group_manager.exchange_timezone = regular_exchange_group_manager.exchange_timezone
        enhanced_exchange_group_manager.exchanges = regular_exchange_group_manager.exchanges
        enhanced_exchange_group_manager.market_hours_utc = regular_exchange_group_manager.market_hours_utc
        enhanced_exchange_group_manager.replay_manager = regular_exchange_group_manager.replay_manager
        enhanced_exchange_group_manager._original_last_snap_str = regular_exchange_group_manager._original_last_snap_str

        # Copy additional attributes
        if hasattr(regular_exchange_group_manager, 'timezone'):
            enhanced_exchange_group_manager.timezone = regular_exchange_group_manager.timezone
        if hasattr(regular_exchange_group_manager, 'market_hours'):
            enhanced_exchange_group_manager.market_hours = regular_exchange_group_manager.market_hours

        logger.info("✅ State copying completed")

        # Step 6: Final validation and logging
        logger.info("✅ Step 6: Final validation...")
        users = enhanced_exchange_group_manager.get_all_users()
        market_time = enhanced_exchange_group_manager.last_snap_time

        logger.info("=" * 80)
        logger.info("🎉 CORE EXCHANGE INITIALIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"✅ CORE EXCHANGE initialized for {len(users)} users")
        logger.info(f"👥 Users: {', '.join(users)}")
        logger.info(f"📍 Market time: {market_time}")
        logger.info(f"🏦 Exchange simulation ready for services")
        logger.info("=" * 80)

        return enhanced_exchange_group_manager

    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ CORE EXCHANGE INITIALIZATION FAILED")
        logger.error("=" * 80)
        logger.error(f"❌ Core exchange initialization failed: {e}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        logger.error("=" * 80)

        # Add specific debugging hints
        if "timeout" in str(e).lower():
            logger.error("🔧 DEBUGGING HINT: Timeout error")
            logger.error("🔧 Check if database is running and accessible")
            logger.error("🔧 Verify database credentials match your working test script")

        if "connection" in str(e).lower():
            logger.error("🔧 DEBUGGING HINT: Connection error")
            logger.error("🔧 Your test script works, so check environment variables")
            logger.error("🔧 Ensure DB_NAME=opentp, DB_USER=opentp, DB_PASSWORD=samaral")

        raise

async def main():
    """Main function - Core exchange with persistent market data connection"""
    service_manager = None

    try:
        logger.info("=" * 80)
        logger.info("🏦 STARTING CORE EXCHANGE SERVICE")
        logger.info(f"Session ID: {logging_config.session_id}")
        logger.info("=" * 80)

        # Get exchange group ID
        group_id = os.environ.get("EXCHANGE_GROUP_ID", "ABC")
        logger.info(f"🔄 Exchange Group ID: {group_id}")

        # Initialize core exchange
        exchange_group_manager = await initialize_core_exchange(group_id)

        # Create service manager
        service_manager = CoreExchangeServiceManager(exchange_group_manager)

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
            service_manager.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start all services
        await service_manager.start_all_services()

        # Run forever until shutdown
        await service_manager.run_forever()

    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error in main: {e}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
    finally:
        # Always attempt graceful shutdown
        if service_manager:
            await service_manager.stop_all_services()
        logger.info("🏁 Exchange service shutdown complete")


if __name__ == "__main__":
    try:
        # Run the main exchange service
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt, exiting...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)