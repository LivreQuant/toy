import logging
import aiohttp_cors
from aiohttp import web

from source.api.rest.controllers import OrderController
from source.core.order_manager import OrderManager
from source.core.state_manager import StateManager
from source.config import config

logger = logging.getLogger('rest_routes')


async def setup_app(order_manager: OrderManager, state_manager: StateManager) -> tuple:
    """
    Set up the REST API application with routes and middleware
    
    Args:
        order_manager: The order manager instance
        state_manager: The state manager instance
        
    Returns:
        Tuple of (app, runner, site)
    """
    # Create application
    app = web.Application()

    # Create controller
    controller = OrderController(order_manager, state_manager)

    # Add routes
    app.router.add_post('/api/orders/submit', controller.submit_order)
    app.router.add_post('/api/orders/cancel', controller.cancel_order)
    app.router.add_get('/health', controller.health_check)
    app.router.add_get('/readiness', controller.readiness_check)

    # Set up CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    # Start the application
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, config.host, config.rest_port)
    await site.start()

    logger.info(f"REST API started on {config.host}:{config.rest_port}")

    return app, runner, site
