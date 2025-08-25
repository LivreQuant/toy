# source/main.py
import asyncio
import logging
from datetime import datetime
import uvicorn
from core.orchestrator import TradingOrchestrator
from api import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Enhanced main entry point for Trading Orchestrator"""
    logger.info("🚀 Starting Enhanced Trading Orchestrator Service")
    
    # Initialize the main orchestrator
    orchestrator = TradingOrchestrator()
    
    # Initialize all components
    await orchestrator.initialize()
    
    # Create FastAPI app with orchestrator
    app = create_app(orchestrator)
    
    # Start orchestrator background tasks
    asyncio.create_task(orchestrator.run())
    
    # Start web server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    
    logger.info("🌐 Starting web server on port 8080")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())