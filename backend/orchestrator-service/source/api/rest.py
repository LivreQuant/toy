# api.py
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)


def create_app(orchestrator) -> FastAPI:
    """Create FastAPI application with all routes"""

    app = FastAPI(title="Exchange Orchestrator", version="1.0.0")

    # Get components from orchestrator
    db_manager = orchestrator.db_manager
    k8s_manager = orchestrator.k8s_manager
    scheduler = orchestrator.scheduler

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "timestamp": datetime.utcnow()}

    @app.get("/ready")
    async def ready_check():
        """Readiness check endpoint for Kubernetes"""
        try:
            # Check if database is accessible
            if db_manager.pool is None:
                raise HTTPException(status_code=503, detail="Database not initialized")

            # Try a simple database query
            exchanges = await db_manager.get_active_exchanges()
            return {
                "status": "ready",
                "timestamp": datetime.utcnow(),
                "exchanges_count": len(exchanges)
            }
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

    @app.get("/status")
    async def get_status():
        """Get overall system status"""
        try:
            exchanges = await db_manager.get_active_exchanges()
            running = k8s_manager.get_running_exchanges()

            return {
                "total_exchanges": len(exchanges),
                "running_exchanges": len(running),
                "running_exchange_ids": list(running),
                "scheduler_running": scheduler.running,
                "exchanges_detail": [
                    {
                        "exch_id": ex['exch_id'],
                        "exchange_name": ex['exchange_name'],
                        "exchange_type": ex['exchange_type'],
                        "is_running": ex['exch_id'] in running
                    } for ex in exchanges
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/exchanges")
    async def list_exchanges():
        """List all exchanges with their status"""
        try:
            exchanges = await db_manager.get_active_exchanges()
            running = k8s_manager.get_running_exchanges()

            result = []
            for exchange in exchanges:
                result.append({
                    "exch_id": exchange['exch_id'],
                    "exchange_id": exchange['exchange_id'],
                    "exchange_name": exchange['exchange_name'],
                    "exchange_type": exchange['exchange_type'],
                    "timezone": exchange['timezone'],
                    "market_hours": {
                        "pre_open": str(exchange['pre_open_time']),
                        "open": str(exchange['open_time']),
                        "close": str(exchange['close_time']),
                        "post_close": str(exchange['post_close_time'])
                    },
                    "is_running": exchange['exch_id'] in running,
                    "should_be_running": scheduler.should_exchange_be_running(exchange)
                })

            return {"exchanges": result}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/exchanges/{exch_id}/start")
    async def start_exchange(exch_id: str):
        """Manually start an exchange"""
        try:
            exchange = await db_manager.get_exchange_by_id(exch_id)
            if not exchange:
                raise HTTPException(status_code=404, detail="Exchange not found")

            await k8s_manager.start_exchange(exchange)

            return {
                "message": f"Started exchange {exchange['exchange_name']}",
                "exch_id": exch_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to start exchange {exch_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/exchanges/{exch_id}/stop")
    async def stop_exchange(exch_id: str):
        """Manually stop an exchange"""
        try:
            exchange = await db_manager.get_exchange_by_id(exch_id)
            if not exchange:
                raise HTTPException(status_code=404, detail="Exchange not found")

            await k8s_manager.stop_exchange(exchange)

            return {
                "message": f"Stopped exchange {exchange['exchange_name']}",
                "exch_id": exch_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to stop exchange {exch_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/exchanges/{exch_id}")
    async def get_exchange_info(exch_id: str):
        """Get detailed info about specific exchange"""
        try:
            exchange = await db_manager.get_exchange_by_id(exch_id)
            if not exchange:
                raise HTTPException(status_code=404, detail="Exchange not found")

            is_running = exchange['exch_id'] in k8s_manager.get_running_exchanges()
            should_be_running = scheduler.should_exchange_be_running(exchange)

            return {
                "exch_id": exchange['exch_id'],
                "exchange_id": exchange['exchange_id'],
                "exchange_name": exchange['exchange_name'],
                "exchange_type": exchange['exchange_type'],
                "timezone": exchange['timezone'],
                "is_running": is_running,
                "should_be_running": should_be_running,
                "market_hours": {
                    "pre_open": str(exchange['pre_open_time']),
                    "open": str(exchange['open_time']),
                    "close": str(exchange['close_time']),
                    "post_close": str(exchange['post_close_time'])
                },
                "exchanges_list": exchange.get('exchanges', [])
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app
