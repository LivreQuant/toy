import logging
import aiohttp_cors
from aiohttp import web

from source.api.rest.controllers import OrderController
from source.api.rest.book_controller import BookController
from source.core.order_manager import OrderManager
from source.core.state_manager import StateManager
from source.db.book_repository import BookRepository
from source.config import config

logger = logging.getLogger('rest_routes')

@web.middleware
async def cors_middleware(request, handler):
    """Middleware to handle CORS for all requests, including OPTIONS preflight"""
    
    # Set CORS headers for all responses
    cors_headers = {
        'Access-Control-Allow-Origin': '*',  # Or your specific frontend domain
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, X-CSRF-Token',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Max-Age': '86400',  # 24 hours to reduce preflight requests
    }
    
    # Handle OPTIONS request (preflight)
    if request.method == 'OPTIONS':
        response = web.Response()
        response.headers.update(cors_headers)
        return response
    
    # Process the regular request
    response = await handler(request)
    
    # Add CORS headers to the response
    response.headers.update(cors_headers)
    return response

async def setup_app(order_manager: OrderManager, state_manager: StateManager) -> tuple:
    """
    Set up the REST API application with routes and middleware
    """
    # Create application with CORS middleware
    app = web.Application(middlewares=[cors_middleware])

    # Create controllers
    order_controller = OrderController(order_manager, state_manager)
    
    # Create book repository and controller
    book_repository = BookRepository()
    book_controller = BookController(
        book_repository,
        order_manager.auth_client,
        order_manager.validation_manager
    )

    # Add order routes
    app.router.add_post('/api/orders/submit', order_controller.submit_orders)
    app.router.add_post('/api/orders/cancel', order_controller.cancel_orders)
    
    # Add book routes
    app.router.add_get('/api/books', book_controller.get_books)
    app.router.add_post('/api/books', book_controller.create_book)
    app.router.add_get('/api/books/{id}', book_controller.get_book)
    app.router.add_put('/api/books/{id}', book_controller.update_book)
    
    # Add health check routes
    app.router.add_get('/health', order_controller.health_check)
    app.router.add_get('/readiness', order_controller.readiness_check)

    # Start the application
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, config.host, config.rest_port)
    await site.start()

    logger.info(f"REST API started on {config.host}:{config.rest_port}")

    return app, runner, site