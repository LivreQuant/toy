import logging
import time
import json
import asyncio
from aiohttp import web

from source.utils.metrics import Metrics

logger = logging.getLogger(__name__)
metrics = Metrics()

async def health_check(request):
    """
    Simple health check endpoint
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with health status
    """
    return web.json_response({
        'status': 'UP',
        'timestamp': int(time.time() * 1000)
    })

async def readiness_check(request):
    """
    Readiness check endpoint with deeper health checks
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with readiness status
    """
    # Get simulator from application context
    simulator = request.app['simulator']
    
    # Check simulator status
    simulator_ok = simulator.status != simulator.SimulatorStatus.SHUTTING_DOWN
    
    if simulator_ok:
        return web.json_response({
            'status': 'READY',
            'simulator': 'UP',
            'timestamp': int(time.time() * 1000)
        })
    else:
        return web.json_response({
            'status': 'NOT_READY',
            'simulator': 'DOWN',
            'timestamp': int(time.time() * 1000)
        }, status=503)

async def metrics_endpoint(request):
    """
    Metrics endpoint for monitoring
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response with metrics data
    """
    # Get metrics
    metrics_data = Metrics().get_metrics()
    
    # Add system stats
    metrics_data['system'] = {
        'uptime_seconds': time.time() - request.app['start_time'],
        'active_sessions': len(request.app['simulator'].sessions)
    }
    
    return web.json_response(metrics_data)