# main.py
import asyncio
import logging
from datetime import datetime
import uvicorn
from database import DatabaseManager
from kubernetes_manager import KubernetesManager
from scheduler import Scheduler
from api import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point"""
    logger.info("Starting Exchange Orchestrator Service")
    
    # Initialize components
    db_manager = DatabaseManager()
    k8s_manager = KubernetesManager()
    scheduler = Scheduler(db_manager, k8s_manager)
    
    # Initialize database
    await db_manager.init()
    
    # Create FastAPI app with components
    app = create_app(db_manager, k8s_manager, scheduler)
    
    # Start scheduler in background
    asyncio.create_task(scheduler.run())
    
    # Start web server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())