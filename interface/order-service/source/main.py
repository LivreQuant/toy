# main.py
import asyncio
import logging
import os
import signal
from aiohttp import web
import redis.asyncio as redis

from source.api.rest_routes import setup_rest_app
from source.core.order_manager import OrderManager
from source.api.auth_client import AuthClient
from source.core.exchange_client import ExchangeClient
from source.db.order_store import OrderStore

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('order_service')

async def init_redis():
    """Initialize Redis connection"""
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    
    try:
        # Create Redis client
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("Connected to Redis successfully")
        return redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

async def serve():
    try:
        # Initialize Redis
        redis_client = await init_redis()
        
        # Initialize order database
        order_store = OrderStore()
        await order_store.connect()
        
        # Initialize auth client
        auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')
        auth_client = AuthClient(auth_service_url)
        
        # Initialize exchange client
        exchange_client = ExchangeClient(redis_client)
        
        # Initialize order manager
        order_manager = OrderManager(order_store, auth_client, exchange_client, redis_client)
        
        # Set up REST API server
        app = setup_rest_app(order_manager)
        rest_port = int(os.getenv('REST_PORT', '8001'))
        
        # Configure signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(shutdown(runner, order_store, redis_client))
            )
        
        # Start REST server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', rest_port)
        await site.start()
        
        logger.info(f"Order service started on port {rest_port}")
        
        # Keep running until signaled to stop
        while True:
            await asyncio.sleep(3600)  # Just to keep the event loop running
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

async def shutdown(runner, order_store, redis_client):
    logger.info("Shutting down server...")
    
    # Shutdown REST server
    await runner.cleanup()
    
    # Close database connections
    await order_store.close()
    
    # Close Redis connection
    await redis_client.close()
    
    logger.info("Server shutdown complete")
    asyncio.get_event_loop().stop()

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")