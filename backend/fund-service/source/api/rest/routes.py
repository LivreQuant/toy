# source/rest/routes.py
import logging
from aiohttp import web

from source.api.rest.state_controller import StateController
from source.api.rest.fund_controller import FundController
from source.api.rest.book_controller import BookController
from source.api.rest.conviction_controller import ConvictionController


from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager

from source.core.fund_manager import FundManager
from source.core.book_manager import BookManager
from source.core.conviction_manager import ConvictionManager

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

async def setup_app( 
    state_manager: StateManager,
    session_manager: SessionManager,
    fund_manager: FundManager,
    book_manager: BookManager,
    conviction_manager: ConvictionManager,
    ) -> tuple:
    """
    Set up the REST API application with routes and middleware
    """
    # Create application with CORS middleware
    app = web.Application(middlewares=[cors_middleware])

    # Add session routes
    state_controller = StateController(state_manager)
    app.router.add_get('/health', state_controller.health_check)
    app.router.add_get('/readiness', state_controller.readiness_check)

    # Add fund routes
    fund_controller = FundController(state_manager, session_manager, fund_manager)
    app.router.add_post('/api/funds', fund_controller.create_fund)
    app.router.add_get('/api/funds', fund_controller.get_fund)
    app.router.add_put('/api/funds', fund_controller.update_fund)

    # Add book routes
    book_controller = BookController(state_manager, session_manager, book_manager)
    app.router.add_get('/api/books', book_controller.get_books)
    app.router.add_post('/api/books', book_controller.create_book)
    app.router.add_get('/api/books/{id}', book_controller.get_book)
    app.router.add_put('/api/books/{id}', book_controller.update_book)
    
    # Add client config routes
    app.router.add_get('/api/books/{id}/config', book_controller.get_client_config)
    app.router.add_put('/api/books/{id}/config', book_controller.update_client_config)

    # Add conviction routes
    conviction_controller = ConvictionController(state_manager, session_manager, conviction_manager)
    app.router.add_post('/api/convictions/submit', conviction_controller.submit_convictions)
    app.router.add_post('/api/convictions/cancel', conviction_controller.cancel_convictions)
    app.router.add_post('/api/convictions/encoded_submit', conviction_controller.submit_convictions_encoded)
    app.router.add_post('/api/convictions/encoded_cancel', conviction_controller.cancel_convictions_encoded)

    # Start the application
    runner = web.AppRunner(app)
    await runner.setup()

    logger.info(f"REST API started on {config.host}:{config.rest_port}")

    return app, runner