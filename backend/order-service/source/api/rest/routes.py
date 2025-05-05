import logging
import aiohttp_cors
from aiohttp import web

from source.api.rest.controllers import OrderController
from source.api.rest.book_controller import BookController
from source.core.order_manager import OrderManager
from source.core.book_manager import BookManager
from source.db.book_repository import BookRepository
from source.core.state_manager import StateManager
from source.config import config

logger = logging.getLogger('rest_routes')


async def setup_app(order_manager: OrderManager, state_manager: StateManager) -> tuple:
    """
    Set up the REST API application with routes and middleware
    """
    # Create application
    app = web.Application()

    # Set up CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        logger.info(f"CORS middleware: {request.method} {request.path}")
        
        # Handle OPTIONS requests explicitly
        if request.method == "OPTIONS":
            logger.info(f"Handling OPTIONS request to {request.path}")
            
            # Set CORS headers
            headers = {
                'Access-Control-Allow-Origin': 'http://localhost:3000',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, DNT, X-CustomHeader, Keep-Alive, User-Agent, If-Modified-Since, Cache-Control, Content-Type, Origin, Accept',
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Max-Age': '86400',
            }
            
            return web.Response(status=204, headers=headers)
        
        # For all other requests, proceed normally
        response = await handler(request)
        return response

    # Add CORS middleware
    app.middlewares.append(cors_middleware)

    # Create controllers
    order_controller = OrderController(order_manager, state_manager)
    
    # Create book repository and manager
    book_repository = BookRepository()
    book_manager = BookManager(book_repository, order_manager.validation_manager)
    book_controller = BookController(book_manager, state_manager)  # Pass state_manager

    # Add order routes
    logger.info("Adding order routes...")
    app.router.add_post('/api/orders/submit', order_controller.submit_orders)
    app.router.add_post('/api/orders/cancel', order_controller.cancel_orders)
    app.router.add_get('/health', order_controller.health_check)
    app.router.add_get('/readiness', order_controller.readiness_check)
    
    # Add book routes with explicit logging
    logger.info("Adding book routes...")
    app.router.add_post('/api/books', book_controller.create_book)
    logger.info("Added POST /api/books route")
    
    app.router.add_get('/api/books', book_controller.get_books)
    logger.info("Added GET /api/books route")
    
    app.router.add_get('/api/books/{book_id}', book_controller.get_book)
    logger.info("Added GET /api/books/{book_id} route")
    
    app.router.add_put('/api/books/{book_id}', book_controller.update_book)
    logger.info("Added PUT /api/books/{book_id} route")
    
    app.router.add_delete('/api/books/{book_id}', book_controller.delete_book)
    logger.info("Added DELETE /api/books/{book_id} route")

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
        logger.info(f"Applied CORS to route: {route}")

    # Start the application
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, config.host, config.rest_port)
    await site.start()

    logger.info(f"REST API started on {config.host}:{config.rest_port}")

    return app, runner, site