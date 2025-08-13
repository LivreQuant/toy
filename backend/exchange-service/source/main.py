# source/main.py - Complete orchestration with health service integration

import asyncio
import os
import sys
import signal
import traceback
from typing import Optional, Set

# Core dependencies
from source.db.db_manager import DatabaseManager
from source.exchange_logging.config import ExchangeLoggingConfig
from source.exchange_logging.utils import get_exchange_logger

# Orchestration components
from source.orchestration.coordination.exchange_manager import EnhancedExchangeGroupManager
from source.orchestration.coordination.exchange_registry import ExchangeRegistration, exchange_registry
from source.orchestration.persistence.snapshot_manager import SnapshotManager

# Server implementations
from source.orchestration.servers.market_data.market_data_server_impl import EnhancedMultiUserMarketDataClient
from source.orchestration.servers.session.session_server_impl import MultiUserSessionServiceImpl
from source.orchestration.servers.conviction.conviction_server_impl import ConvictionServiceImpl

# Health service integration
from source.api.rest.health import OrchestrationHealthService

# Setup detailed logging
logging_config = ExchangeLoggingConfig.setup_exchange_logging()
logger = get_exchange_logger(__name__)


class CoreExchangeServiceManager:
    """
    Core exchange service manager with comprehensive health monitoring.
    
    This class orchestrates all exchange services and provides health monitoring
    for Kubernetes integration. It manages:
    
    1. Core exchange simulation
    2. Market data connections
    3. Optional gRPC services (session, conviction)
    4. Health monitoring HTTP server
    5. Graceful shutdown handling
    """

    def __init__(self, exchange_group_manager):
        self.exchange_group_manager = exchange_group_manager
        self.logger = get_exchange_logger(__name__)
        self.running = False

        # Market data connection management
        self.market_data_client: Optional[EnhancedMultiUserMarketDataClient] = None
        self.market_data_connected = False
        self.market_data_connection_task: Optional[asyncio.Task] = None

        # Optional gRPC services
        self.session_service: Optional[MultiUserSessionServiceImpl] = None
        self.conviction_service: Optional[ConvictionServiceImpl] = None

        # Track which services are enabled and running
        self.enabled_services: Set[str] = set()

        # Database manager
        self.db_manager = DatabaseManager

        # Exchange registration tracking
        self.exchange_registration: Optional[ExchangeRegistration] = None

        # Health service integration - CRITICAL for Kubernetes
        self.health_service: Optional[OrchestrationHealthService] = None

        # Shutdown coordination
        self.shutdown_requested = False

        # Market data connection settings from environment
        self.market_data_host = os.environ.get("MARKET_DATA_HOST", "localhost")
        self.market_data_port = int(os.environ.get("MARKET_DATA_PORT", "50051"))
        self.market_data_retry_interval = int(os.environ.get("MARKET_DATA_RETRY_SECONDS", "5"))

    async def register_exchange_service(self):
        """Register exchange service with Kubernetes metadata - OPTIONAL"""
        try:
            self.logger.info("🔧 Registering exchange service in database...")

            # Update Kubernetes metadata for service discovery
            self.exchange_registration = await exchange_registry.update_kubernetes_metadata()

            # Mark as ready in health service
            if self.health_service:
                self.health_service.mark_service_ready('exchange_registration', True)

            self.logger.info("✅ Exchange service registration completed")

        except Exception as e:
            self.logger.warning(f"⚠️ Exchange service registration failed (non-critical): {e}")
            # Mark as failed but don't stop startup - this is for service discovery only
            if self.health_service:
                self.health_service.mark_service_ready('exchange_registration', False)
            # DO NOT raise - continue without registry (development mode)
            self.logger.info("🏦 Core exchange continues without service registry")

    async def start_health_service(self):
        """
        Start health monitoring HTTP server - MUST BE FIRST SERVICE STARTED
        
        This service provides Kubernetes-compatible health check endpoints:
        - /health (liveness probe) - basic service availability
        - /readiness (readiness probe) - all components ready
        - /metrics (monitoring) - operational metrics
        - /status (debugging) - detailed status information
        
        The health service runs on a separate HTTP port (50056) from gRPC services.
        """
        try:
            self.logger.info("🏥 Starting Health Service")

            # Get health service port from environment
            health_port = int(os.environ.get("HEALTH_SERVICE_PORT", "50056"))

            # Create health service with references to manager components
            self.health_service = OrchestrationHealthService(
                exchange_group_manager=self.exchange_group_manager,
                service_manager=self,  # Pass self for service status monitoring
                http_port=health_port
            )

            # Start the aiohttp server for health endpoints
            await self.health_service.setup()

            self.logger.info(f"✅ Health Service: STARTED on port {health_port}")
            self.logger.info("🏥 Health endpoints available:")
            self.logger.info(f"   - Liveness:  http://0.0.0.0:{health_port}/health")
            self.logger.info(f"   - Readiness: http://0.0.0.0:{health_port}/readiness")
            self.logger.info(f"   - Metrics:   http://0.0.0.0:{health_port}/metrics")
            self.logger.info(f"   - Status:    http://0.0.0.0:{health_port}/status")

        except Exception as e:
            self.logger.error(f"❌ Health Service failed to start: {e}")
            # Health service failure is critical - cannot monitor without it
            raise

    async def start_core_exchange(self):
        """
        Start the core exchange simulation - THE FOUNDATION OF ALL SERVICES
        
        This initializes the core exchange simulation that all other services depend on.
        It validates that user contexts are loaded and exchange state is ready.
        
        Core exchange must be running before any gRPC services can operate.
        """
        try:
            self.logger.info("🏦 Starting CORE EXCHANGE SERVICE")

            # Validate exchange group manager is properly initialized
            if not self.exchange_group_manager:
                raise RuntimeError("Exchange group manager not initialized")

            # Get user contexts to validate initialization
            users = self.exchange_group_manager.get_all_users()
            if not users:
                raise RuntimeError("No users found in exchange group manager")

            # Validate last snap time is set (required for market timing)
            if not self.exchange_group_manager.last_snap_time:
                raise RuntimeError("Last snap time not set in exchange group manager")

            self.logger.info(f"👥 Core exchange initialized for {len(users)} users: {[str(user) for user in users]}")
            self.logger.info(f"📅 Market time: {self.exchange_group_manager.last_snap_time}")

            # Mark core exchange as ready in health service
            if self.health_service:
                self.health_service.mark_service_ready('core_exchange', True)

            return True

        except Exception as e:
            self.logger.error(f"❌ Core exchange failed to start: {e}")
            # Mark as failed in health service
            if self.health_service:
                self.health_service.mark_service_ready('core_exchange', False)
            raise

    async def start_persistent_market_data_connection(self):
        """
        Start persistent market data connection with automatic retry logic.
        
        This creates a persistent connection to the external market data service.
        Key features:
        - Automatic reconnection on failure
        - Health status tracking for readiness probes
        - Non-blocking startup (core exchange continues if market data is unavailable)
        - Configurable retry intervals
        """
        try:
            self.logger.info("📡 Starting Market Data Client")
            self.logger.info(f"📍 Target: {self.market_data_host}:{self.market_data_port}")

            # Create market data client
            self.market_data_client = EnhancedMultiUserMarketDataClient(
                self.exchange_group_manager,
                host=self.market_data_host,
                port=self.market_data_port
            )

            # Start persistent connection monitoring task
            # This task runs continuously and handles reconnections
            self.market_data_connection_task = asyncio.create_task(
                self._monitor_market_data_connection()
            )

            self.logger.info(f"📡 Market Data Client: Connection monitoring started")
            self.logger.info(f"⏱️  Retry interval: {self.market_data_retry_interval} seconds")

        except Exception as e:
            self.logger.error(f"❌ Market Data Client failed to start: {e}")
            # Mark as failed in health service
            if self.health_service:
                self.health_service.mark_service_ready('market_data_client', False)
            # Don't re-raise - market data is optional for core functionality

    async def _monitor_market_data_connection(self):
        """
        Continuous monitoring task for market data connection.
        """
        retry_count = 0

        while not self.shutdown_requested:
            try:
                if not self.market_data_connected:
                    self.logger.info(f"📡 Attempting market data connection (attempt {retry_count + 1})")

                    # FIXED: Call start() instead of connect_and_run()
                    self.market_data_client.start()

                    # Give it a moment to establish connection
                    await asyncio.sleep(2)

                    # Check if connection was established
                    if self.market_data_client.running:
                        self.market_data_connected = True
                        retry_count = 0

                        # Update health service
                        if self.health_service:
                            self.health_service.mark_service_ready('market_data_client', True)

                        self.logger.info("✅ Market Data: STARTED")
                    else:
                        raise Exception("Market data client failed to start")

                else:
                    # Connection is active, just wait
                    await asyncio.sleep(1)

            except Exception as e:
                # Connection failed or lost
                if self.market_data_connected:
                    self.logger.warning(f"📡 Market Data connection lost: {e}")
                else:
                    self.logger.debug(f"📡 Market Data connection attempt {retry_count + 1} failed: {e}")

                # Update state
                self.market_data_connected = False
                retry_count += 1

                # Update health service
                if self.health_service:
                    self.health_service.mark_service_ready('market_data_client', False)

                # Wait before retry
                self.logger.info(f"⏳ Retrying market data connection in {self.market_data_retry_interval} seconds...")
                await asyncio.sleep(self.market_data_retry_interval)

    async def start_optional_session_service(self):
        """
        Start session gRPC service for client connections with EXTENSIVE debugging.
        """
        try:
            self.logger.info("🔗 SESSION SERVICE STARTUP: Beginning")
            self.logger.info(f"🔗 SESSION SERVICE STARTUP: exchange_group_manager: {self.exchange_group_manager}")
            self.logger.info(
                f"🔗 SESSION SERVICE STARTUP: exchange_group_manager type: {type(self.exchange_group_manager)}")

            if self.exchange_group_manager:
                users = self.exchange_group_manager.get_all_users()
                self.logger.info(f"🔗 SESSION SERVICE STARTUP: Found {len(users)} users")
                for user in users:
                    self.logger.info(f"🔗 SESSION SERVICE STARTUP: User: {user} (type: {type(user)})")
            else:
                self.logger.error("🔗 SESSION SERVICE STARTUP: exchange_group_manager is None!")

            self.logger.info("🔗 Starting Session Service")

            # Create session service implementation
            self.logger.info("🔗 SESSION SERVICE STARTUP: Creating MultiUserSessionServiceImpl")
            self.session_service = MultiUserSessionServiceImpl(self.exchange_group_manager)
            self.logger.info("🔗 SESSION SERVICE STARTUP: MultiUserSessionServiceImpl created")

            # Get port from environment
            session_port = int(os.environ.get("SESSION_SERVICE_PORT", "50050"))
            self.logger.info(f"🔗 SESSION SERVICE STARTUP: Using port {session_port}")

            # Start gRPC server
            self.logger.info("🔗 SESSION SERVICE STARTUP: Starting gRPC server")
            self.session_service.start_sync_server(port=session_port)
            self.logger.info("🔗 SESSION SERVICE STARTUP: gRPC server start_sync_server completed")

            # Track service state
            users = self.exchange_group_manager.get_all_users()
            self.enabled_services.add("session")

            # Update health service
            if self.health_service:
                self.health_service.mark_service_ready('session_service', True)
                self.logger.info("🔗 SESSION SERVICE STARTUP: Health service updated")

            self.logger.info(f"✅ Session Service: STARTED on port {session_port}")
            self.logger.info(f"🔗 Session Service: Ready for up to {len(users)} concurrent user connections")

        except Exception as e:
            self.logger.error(f"❌ Session Service failed to start: {e}")
            import traceback
            self.logger.error(f"❌ Session Service traceback: {traceback.format_exc()}")
            # Mark as failed in health service
            if self.health_service:
                self.health_service.mark_service_ready('session_service', False)
            # Continue without session service - it's optional
            self.logger.info("🏦 Core exchange continues without session service")

    async def start_optional_conviction_service(self):
        """
        Start conviction gRPC service for order processing.
        
        The conviction service handles order submission and conviction processing.
        This is optional and controlled by ENABLE_CONVICTION_SERVICE environment variable.
        
        Service features:
        - Batch order processing
        - Conviction management
        - Health monitoring integration
        """
        try:
            self.logger.info("⚖️ Starting Conviction Service")

            # Create conviction service implementation
            self.conviction_service = ConvictionServiceImpl(self.exchange_group_manager)

            # Get port from environment
            conviction_port = int(os.environ.get("CONVICTION_SERVICE_PORT", "50052"))

            # Start gRPC server
            await self.conviction_service.start_server(port=conviction_port)

            # Track service state
            users = self.exchange_group_manager.get_all_users()
            self.enabled_services.add("conviction")

            # Update health service
            if self.health_service:
                self.health_service.mark_service_ready('conviction_service', True)

            self.logger.info(f"✅ Conviction Service: STARTED on port {conviction_port}")
            self.logger.info(f"⚖️ Conviction Service: Ready for up to {len(users)} concurrent user connections")

        except Exception as e:
            self.logger.error(f"❌ Conviction Service failed to start: {e}")
            # Mark as failed in health service
            if self.health_service:
                self.health_service.mark_service_ready('conviction_service', False)
            # Continue without conviction service - it's optional
            self.logger.info("🏦 Core exchange continues without conviction service")

    async def start_all_services(self):
        """
        Orchestrated startup of all services in the correct order.
        
        Startup sequence (ORDER IS CRITICAL):
        1. Health service (must be first for Kubernetes monitoring)
        2. Core exchange (foundation for all other services)
        3. Market data connection (background task)
        4. Optional services based on environment variables
        
        This method ensures proper dependency ordering and error handling.
        """
        try:
            # STEP 1: Start health service FIRST
            # This is critical - Kubernetes needs health endpoints during startup
            await self.start_health_service()

            # STEP 2: Start core exchange (required foundation)
            await self.start_core_exchange()

            # Register exchange service for service discovery (FOR PROD: SESSION TO FIND EXCHANGE)
            await self.register_exchange_service()

            # STEP 3: Start market data connection (background task)
            await self.start_persistent_market_data_connection()

            # STEP 4: Start optional services based on environment configuration

            # Session service (for client streaming)
            if os.environ.get("ENABLE_SESSION_SERVICE", "true").lower() in ['true', '1', 'yes']:
                await self.start_optional_session_service()
            else:
                self.logger.info("🔗 Session Service: DISABLED by environment variable")

            # Conviction service (for order processing)
            if os.environ.get("ENABLE_CONVICTION_SERVICE", "false").lower() in ['true', '1', 'yes']:
                await self.start_optional_conviction_service()
            else:
                self.logger.info("⚖️ Conviction Service: DISABLED by environment variable")

            # Log startup completion summary
            self._log_startup_summary()

        except Exception as e:
            self.logger.error(f"❌ Failed to start services: {e}")
            raise

    def _log_startup_summary(self):
        """Log comprehensive startup summary for operations visibility."""
        users = self.exchange_group_manager.get_all_users()

        self.logger.info("=" * 80)
        self.logger.info("🎯 EXCHANGE SERVICE STARTUP COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"🏦 Core Exchange: RUNNING ({len(users)} users)")
        self.logger.info(f"👥 Users: {', '.join(str(user) for user in users)}")
        self.logger.info(f"📅 Market Time: {self.exchange_group_manager.last_snap_time}")
        self.logger.info(f"📡 Market Data: {'CONNECTING' if not self.market_data_connected else 'CONNECTED'}")
        self.logger.info(f"   - Host: {self.market_data_host}:{self.market_data_port}")
        self.logger.info(f"   - Retry: {self.market_data_retry_interval}s intervals")
        self.logger.info(f"🔗 Session Service: {'ENABLED' if 'session' in self.enabled_services else 'DISABLED'}")
        self.logger.info(f"⚖️ Conviction Service: {'ENABLED' if 'conviction' in self.enabled_services else 'DISABLED'}")
        self.logger.info(f"🏥 Health Service: RUNNING on port {self.health_service.http_port}")
        self.logger.info("   Health Endpoints:")
        self.logger.info(f"   - Liveness:  http://0.0.0.0:{self.health_service.http_port}/health")
        self.logger.info(f"   - Readiness: http://0.0.0.0:{self.health_service.http_port}/readiness")
        self.logger.info(f"   - Metrics:   http://0.0.0.0:{self.health_service.http_port}/metrics")
        self.logger.info("=" * 80)

    async def stop_all_services(self):
        """
        Graceful shutdown of all services in reverse dependency order.
        
        Shutdown sequence:
        1. Optional services (conviction, session)
        2. Market data connection
        3. Core exchange components
        4. Health service (last, so monitoring works during shutdown)
        
        This ensures clean shutdown without service interdependency issues.
        """
        self.logger.info("=" * 80)
        self.logger.info("🛑 STOPPING ALL SERVICES")
        self.logger.info("=" * 80)

        # Stop optional services first (reverse order of startup)
        services_to_stop = [
            ("conviction", self.conviction_service),
            ("session", self.session_service),
        ]

        for service_name, service in services_to_stop:
            if service:
                try:
                    self.logger.info(f"🛑 Stopping {service_name} service...")
                    if hasattr(service, 'stop_server'):
                        await service.stop_server()
                    elif hasattr(service, 'shutdown'):
                        await service.shutdown()
                    self.logger.info(f"✅ {service_name} service stopped")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping {service_name} service: {e}")

        # Stop market data connection task
        if self.market_data_connection_task:
            try:
                self.logger.info("🛑 Stopping market data connection...")
                self.market_data_connection_task.cancel()
                try:
                    await self.market_data_connection_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
                self.logger.info("✅ Market data connection stopped")
            except Exception as e:
                self.logger.error(f"❌ Error stopping market data task: {e}")

        # Stop market data client
        if self.market_data_client:
            try:
                if hasattr(self.market_data_client, 'shutdown'):
                    await self.market_data_client.shutdown()
            except Exception as e:
                self.logger.error(f"❌ Error stopping market data client: {e}")

        # Stop health service LAST (so monitoring works during shutdown)
        if self.health_service:
            try:
                self.logger.info("🛑 Stopping health service...")
                await self.health_service.shutdown()
                self.logger.info("✅ Health service stopped")
            except Exception as e:
                self.logger.error(f"❌ Error stopping health service: {e}")

        # Clear Kubernetes metadata during shutdown
        if self.exchange_registration:
            try:
                await exchange_registry.clear_kubernetes_metadata(
                    self.exchange_registration.exch_id
                )
            except Exception as e:
                self.logger.error(f"❌ Failed to clear registration: {e}")

        self.logger.info("✅ All services stopped gracefully")

    async def run_forever(self):
        """
        Main service run loop - keeps services running until shutdown.
        
        This method:
        - Keeps the main thread alive
        - Monitors for shutdown signals
        - Handles graceful shutdown coordination
        - Provides operational logging
        """
        self.running = True

        try:
            self.logger.info("🚀 Exchange service running - waiting for shutdown signal")

            # Main service loop
            while not self.shutdown_requested and self.running:
                # Perform any periodic maintenance here if needed
                await asyncio.sleep(1)

            self.logger.info("🛑 Shutdown signal received, initiating graceful shutdown")

        except KeyboardInterrupt:
            self.logger.info("🛑 Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"❌ Error in service run loop: {e}")
        finally:
            self.running = False


async def initialize_core_exchange(exch_id: str) -> EnhancedExchangeGroupManager:
    """
    Initialize core exchange simulation from snapshot data.
    
    This function handles the complex initialization process:
    1. Create snapshot manager
    2. Load last snap data from files/database
    3. Initialize all user contexts and managers
    4. Create enhanced exchange group manager
    5. Validate initialization completeness
    
    Args:
        exch_id: Exchange group identifier (e.g., "ABC")
        
    Returns:
        EnhancedExchangeGroupManager: Fully initialized exchange manager
        
    Raises:
        Exception: If initialization fails at any step
    """
    try:
        logger.info("=" * 80)
        logger.info("🏗️  INITIALIZING CORE EXCHANGE")
        logger.info("=" * 80)

        # Step 1: Create snapshot manager
        logger.info("🔄 Step 1: Creating snapshot manager...")
        snapshot_manager = SnapshotManager(exch_id)

        # Step 2: Initialize from snapshot data
        logger.info("📊 Step 2: Initializing from snapshot data...")
        snapshot_initialized = await snapshot_manager.initialize_multi_user_from_snapshot()

        if not snapshot_initialized:
            raise RuntimeError("Failed to initialize from snapshot data")

        logger.info("✅ Snapshot data loaded successfully")

        # Step 3: Get initialized exchange group manager
        logger.info("🔄 Step 3: Retrieving exchange group manager...")
        regular_exchange_group_manager = snapshot_manager.exchange_group_manager

        if not regular_exchange_group_manager:
            raise RuntimeError("Exchange group manager not created by snapshot initialization")

        logger.info("✅ Exchange group manager retrieved successfully")

        # Step 4: Create enhanced exchange group manager with orchestration features
        logger.info("🚀 Step 4: Creating enhanced exchange group manager...")
        enhanced_exchange_group_manager = EnhancedExchangeGroupManager(
            exch_id=regular_exchange_group_manager.exch_id,
        )

        # Step 5: Copy all initialized state to enhanced manager
        logger.info("📋 Step 5: Copying initialized state...")
        enhanced_exchange_group_manager.metadata = regular_exchange_group_manager.metadata
        enhanced_exchange_group_manager.user_contexts = regular_exchange_group_manager.user_contexts
        enhanced_exchange_group_manager.last_snap_time = regular_exchange_group_manager.last_snap_time
        enhanced_exchange_group_manager.exchange_timezone = regular_exchange_group_manager.exchange_timezone
        enhanced_exchange_group_manager.exchanges = regular_exchange_group_manager.exchanges
        enhanced_exchange_group_manager.market_hours_utc = regular_exchange_group_manager.market_hours_utc
        enhanced_exchange_group_manager.replay_manager = regular_exchange_group_manager.replay_manager
        enhanced_exchange_group_manager._original_last_snap_str = regular_exchange_group_manager._original_last_snap_str

        # Copy additional attributes if they exist
        for attr in ['timezone', 'market_hours']:
            if hasattr(regular_exchange_group_manager, attr):
                setattr(enhanced_exchange_group_manager, attr,
                        getattr(regular_exchange_group_manager, attr))

        logger.info("✅ State copying completed")

        # Step 6: Final validation and logging
        logger.info("✅ Step 6: Final validation...")
        users = enhanced_exchange_group_manager.get_all_users()
        market_time = enhanced_exchange_group_manager.last_snap_time

        if not users:
            raise RuntimeError("No users found after initialization")

        if not market_time:
            raise RuntimeError("Market time not set after initialization")

        # Log successful initialization
        logger.info("=" * 80)
        logger.info("🎉 CORE EXCHANGE INITIALIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"✅ CORE EXCHANGE initialized for {len(users)} users")
        logger.info(f"👥 Users: {', '.join(str(user) for user in users)}")
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

        # Add specific debugging hints for common issues
        if "timeout" in str(e).lower():
            logger.error("🔧 DEBUGGING HINT: Timeout error")
            logger.error("🔧 Check if database is running and accessible")
            logger.error("🔧 Verify database credentials and connectivity")

        if "connection" in str(e).lower():
            logger.error("🔧 DEBUGGING HINT: Connection error")
            logger.error("🔧 Check environment variables for database connection")
            logger.error("🔧 Ensure DB_NAME, DB_USER, DB_PASSWORD are correct")

        if "snapshot" in str(e).lower():
            logger.error("🔧 DEBUGGING HINT: Snapshot data issue")
            logger.error("🔧 Check if snapshot files exist in data directory")
            logger.error("🔧 Verify data file permissions and format")

        raise


async def main():
    """
    Main application entry point with comprehensive error handling.
    
    This function:
    1. Sets up logging and configuration
    2. Initializes core exchange from snapshot data
    3. Creates service manager
    4. Sets up signal handlers for graceful shutdown
    5. Starts all services
    6. Runs until shutdown signal
    7. Performs graceful cleanup
    """
    service_manager = None

    try:
        logger.info("=" * 80)
        logger.info("🏦 STARTING CORE EXCHANGE SERVICE")
        logger.info(f"📋 Session ID: {logging_config.session_id}")
        logger.info(f"🐍 Python: {sys.version}")
        logger.info(f"📁 Working Directory: {os.getcwd()}")
        logger.info("=" * 80)

        # Get configuration from environment
        exch_id = os.environ.get("EXCH_ID", "ABC")
        logger.info(f"🔄 Exchange Group ID: {exch_id}")

        # Log environment configuration
        logger.info("🌍 Environment Configuration:")
        logger.info(f"   - ENABLE_SESSION_SERVICE: {os.environ.get('ENABLE_SESSION_SERVICE', 'true')}")
        logger.info(f"   - ENABLE_CONVICTION_SERVICE: {os.environ.get('ENABLE_CONVICTION_SERVICE', 'false')}")
        logger.info(f"   - MARKET_DATA_HOST: {os.environ.get('MARKET_DATA_HOST', 'localhost')}")
        logger.info(f"   - MARKET_DATA_PORT: {os.environ.get('MARKET_DATA_PORT', '50051')}")
        logger.info(f"   - HEALTH_SERVICE_PORT: {os.environ.get('HEALTH_SERVICE_PORT', '50056')}")

        # Initialize core exchange simulation
        logger.info("🏗️  Initializing core exchange...")
        exchange_group_manager = await initialize_core_exchange(exch_id)

        # Create service manager
        logger.info("🎛️  Creating service manager...")
        service_manager = CoreExchangeServiceManager(exchange_group_manager)

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"📡 Received {signal_name} signal, initiating graceful shutdown...")
            service_manager.shutdown_requested = True

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Docker/Kubernetes termination

        logger.info("📡 Signal handlers registered")

        # Start all services in orchestrated manner
        logger.info("🚀 Starting all services...")
        await service_manager.start_all_services()

        # Run main service loop until shutdown
        logger.info("🎯 All services started - entering main run loop")
        await service_manager.run_forever()

    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error in main: {e}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Always attempt graceful shutdown
        if service_manager:
            try:
                logger.info("🧹 Performing graceful shutdown...")
                await service_manager.stop_all_services()
            except Exception as e:
                logger.error(f"❌ Error during shutdown: {e}")

        logger.info("🏁 Exchange service shutdown complete")


if __name__ == "__main__":
    """
    Application entry point with top-level exception handling.
    """
    try:
        # Run the main exchange service
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt, exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error at top level: {e}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        sys.exit(1)
