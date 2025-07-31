# source/main.py
import asyncio
import logging
import signal
import grpc
import sys
import os

from source.config import config
from source.utils.logging_utils import setup_logging
from source.generator.market_data_generator import ControlledMarketDataGenerator
from source.db.database import DatabaseManager
from source.api.grpc.market_exchange_interface_pb2_grpc import add_MarketDataServiceServicer_to_server
from source.service.market_data_service import MarketDataService
from source.service.health import HealthService

async def shutdown(service, server, health_service):
    """Gracefully shut down all services"""
    logging.info("🛑 Shutting down 24/7/365 market data service...")
    
    # Stop the service first
    if service:
        await service.stop()
    
    # Stop the health service
    if health_service:
        await health_service.shutdown()

    # Then stop the server
    if server:
        await server.stop(5)  # 5 seconds grace period
    
    logging.info("✅ Shutdown complete")

async def main():
    """Main entry point for the 24/7/365 market data service"""
    # Setup logging
    logger = setup_logging()
    logger.info("🚀 Starting 24/7/365 market data service for Kubernetes")
    logger.info("🔄 Service runs continuously - data provided based on exchange parameters")
    
    service = None
    server = None
    health_service = None
    
    try:
        # Load market configuration from JSON
        market_config = config.load_market_config()
        logger.info(f"📋 Loaded market config: {market_config['config_name']}")
        logger.info(f"🌍 Market timezone: {market_config.get('timezone', 'UTC')}")
        logger.info(f"📈 Tracking {len(market_config['equity'])} equity symbols")
        logger.info(f"💱 Tracking {len(market_config['fx'])} FX pairs")
        logger.info(f"💾 Storage: PostgreSQL only (exch_us_equity schema)")
        logger.info(f"🕐 Time source: Current UTC time converted to market timezone")
        logger.info(f"⏰ Generation: Automatic minute bars at real-time boundaries")
        logger.info(f"🏗️ Kubernetes: Continuous 24/7/365 operation")
        
        # Log market hours configuration
        market_hours = market_config.get('market_hours', {})
        timezone = market_config.get('timezone', 'UTC')
        logger.info(f"🏪 Market hours configuration ({timezone}):")
        logger.info(f"   Pre-market: {market_hours.get('pre_market_start', 4):02d}:{market_hours.get('pre_market_start_min', 0):02d} - {market_hours.get('market_open', 9):02d}:{market_hours.get('market_open_min', 30):02d}")
        logger.info(f"   Regular:    {market_hours.get('market_open', 9):02d}:{market_hours.get('market_open_min', 30):02d} - {market_hours.get('market_close', 16):02d}:{market_hours.get('market_close_min', 0):02d}")
        logger.info(f"   After-hrs:  {market_hours.get('market_close', 16):02d}:{market_hours.get('market_close_min', 0):02d} - {market_hours.get('after_hours_end', 20):02d}:{market_hours.get('after_hours_end_min', 0):02d}")
        logger.info(f"   Data policy: Live during market hours, last available during weekends/holidays/closed hours")
        
        # Create the controlled market data generator
        generator = ControlledMarketDataGenerator(market_config)
        
        # Create database manager
        db_manager = DatabaseManager()
        
        # Create the service
        service = MarketDataService(
            generator=generator,
            db_manager=db_manager
        )
        
        # Create health service with reference to market data service        
        health_service = HealthService(market_data_service=service, http_port=50061)
        await health_service.setup()

        # Create gRPC server
        server = grpc.aio.server()
        add_MarketDataServiceServicer_to_server(service, server)
        
        # Start server
        server_addr = f"{config.API_HOST}:{config.API_PORT}"
        server.add_insecure_port(server_addr)
        await server.start()
        
        # Log current market status
        is_trading, market_status = generator.get_market_status()
        current_utc = generator.get_current_time()
        current_market = generator.get_current_market_time()
        
        logger.info(f"✅ 24/7/365 market data server started on {server_addr}")
        logger.info(f"🏥 Health check server started on http://0.0.0.0:50061")
        logger.info(f"⏰ Current UTC time: {current_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"🌍 Current market time: {current_market.strftime('%Y-%m-%d %H:%M:%S %Z')} ({current_market.strftime('%A')})")
        logger.info(f"📊 Current market status: {market_status.upper()} {'(LIVE DATA)' if is_trading else '(LAST AVAILABLE DATA)'}")
        logger.info(f"💾 Database: {config.db.host}:{config.db.port}/{config.db.database}")
        logger.info(f"📊 Tables: exch_us_equity.equity_data, exch_us_equity.fx_data")
        
        # Set up shutdown handler
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(service, server, health_service))
            )
        
        # Start the service
        await service.start()
        
        logger.info("🎯 24/7/365 market data service is ready for Kubernetes")
        logger.info("📡 Exchange simulators can now subscribe to receive minute bars")
        logger.info("💾 All minute bar data will be stored in PostgreSQL exch_us_equity schema")
        logger.info("🕐 Service runs continuously - provides live data during market hours, last available data otherwise")
        logger.info("🏗️ Kubernetes pod will restart automatically if needed - no manual intervention required")
        logger.info("⏰ Next minute bar will generate at the next minute boundary")
        
        # Keep the server running
        await server.wait_for_termination()
        
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await shutdown(service, server, health_service)

if __name__ == "__main__":
    asyncio.run(main())