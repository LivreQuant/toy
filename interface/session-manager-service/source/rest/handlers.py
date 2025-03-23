import logging
from aiohttp import web
import json

logger = logging.getLogger('api_handlers')

async def get_token_from_request(request):
    """Extract JWT token from request headers or query parameters"""
    # Try Authorization header first
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Try query parameter
    token = request.query.get('token')
    if token:
        return token
    
    # Try POST body if this is a POST request
    if request.method == 'POST':
        try:
            body = await request.json()
            if 'token' in body:
                return body['token']
        except:
            pass
    
    return None

async def handle_create_session(request):
    """Handle session creation request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    try:
        # Parse request body
        body = await request.json()
        token = body.get('token')
        
        if not token:
            return web.json_response({
                'success': False,
                'error': 'Missing token'
            }, status=400)
        
        # Validate token
        auth_client = request.app['auth_client']
        validate_result = await auth_client.validate_token(token)
        
        if not validate_result['valid']:
            return web.json_response({
                'success': False,
                'error': 'Invalid token'
            }, status=401)
        
        user_id = validate_result['user_id']
        
        # Get client IP
        client_ip = request.remote
        
        # Create session
        session_id, is_new = await session_manager.create_session(
            user_id, token, client_ip)
        
        if not session_id:
            return web.json_response({
                'success': False,
                'error': 'Failed to create session'
            }, status=500)
        
        return web.json_response({
            'success': True,
            'sessionId': session_id,
            'isNew': is_new,
            'podName': session_manager.pod_name
        })
    
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def handle_get_session(request):
    """Handle session retrieval request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing token'
        }, status=400)
    
    # Validate session
    user_id = await session_manager.validate_session(session_id, token)
    if not user_id:
        return web.json_response({
            'success': False,
            'error': 'Invalid session or token'
        }, status=401)
    
    # Get session data
    session = await session_manager.get_session(session_id)
    
    # Format response
    response = {
        'success': True,
        'sessionId': session_id,
        'userId': user_id,
        'sessionActive': True,
        'simulatorId': session.get('simulator_id'),
        'simulatorEndpoint': session.get('simulator_endpoint'),
        'simulatorStatus': session.get('simulator_status', 'UNKNOWN'),
        'podName': session_manager.pod_name
    }
    
    return web.json_response(response)

async def handle_end_session(request):
    """Handle session termination request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing token'
        }, status=400)
    
    # End session
    success, error = await session_manager.end_session(session_id, token)
    
    if not success:
        return web.json_response({
            'success': False,
            'error': error
        }, status=400 if "Invalid" in error else 500)
    
    return web.json_response({
        'success': True
    })

async def handle_keep_alive(request):
    """Handle session keep-alive request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing token'
        }, status=400)
    
    # Validate session
    user_id = await session_manager.validate_session(session_id, token)
    if not user_id:
        return web.json_response({
            'success': False,
            'error': 'Invalid session or token'
        }, status=401)
    
    # Session is valid, return success
    return web.json_response({
        'success': True,
        'timestamp': int(time.time() * 1000)
    })

async def handle_start_simulator(request):
    """Handle simulator start request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    try:
        # Parse request body
        body = await request.json()
        session_id = body.get('sessionId')
        token = body.get('token')
        
        if not session_id or not token:
            return web.json_response({
                'success': False,
                'error': 'Missing sessionId or token'
            }, status=400)
        
        # Start simulator
        simulator_id, simulator_endpoint, error = await session_manager.start_simulator(
            session_id, token)
        
        if not simulator_id:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400 if "Invalid" in error else 500)
        
        return web.json_response({
            'success': True,
            'simulatorId': simulator_id,
            'simulatorEndpoint': simulator_endpoint,
            'status': 'STARTING'
        })
    
    except Exception as e:
        logger.error(f"Error starting simulator: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def handle_stop_simulator(request):
    """Handle simulator stop request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get simulator ID from URL
    simulator_id = request.match_info['simulator_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing token'
        }, status=400)
    
    try:
        # Parse request body to get session ID
        body = await request.json()
        session_id = body.get('sessionId')
        
        if not session_id:
            return web.json_response({
                'success': False,
                'error': 'Missing sessionId'
            }, status=400)
        
        # Stop simulator
        success, error = await session_manager.stop_simulator(session_id, token)
        
        if not success:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400 if "Invalid" in error else 500)
        
        return web.json_response({
            'success': True,
            'status': 'STOPPING'
        })
    
    except Exception as e:
        logger.error(f"Error stopping simulator: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def handle_get_simulator_status(request):
    """Handle simulator status request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get simulator ID from URL
    simulator_id = request.match_info['simulator_id']
    
    # Get token and session ID from query
    token = request.query.get('token')
    session_id = request.query.get('sessionId')
    
    if not token or not session_id:
        return web.json_response({
            'success': False,
            'error': 'Missing token or sessionId'
        }, status=400)
    
    # Get simulator status
    status, error = await session_manager.get_simulator_status(session_id, token)
    
    if not status:
        return web.json_response({
            'success': False,
            'error': error
        }, status=400 if "Invalid" in error else 500)
    
    return web.json_response({
        'success': True,
        'status': status['status'],
        'simulatorId': status['simulator_id'] if 'simulator_id' in status else simulator_id
    })

async def handle_reconnect_session(request):
    """Handle session reconnection request"""
    # Get session manager
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    try:
        # Parse request body
        body = await request.json()
        token = body.get('token')
        attempt = body.get('reconnectAttempt', 1)
        
        if not token:
            return web.json_response({
                'success': False,
                'error': 'Missing token'
            }, status=400)
        
        # Reconnect session
        result, error = await session_manager.reconnect_session(session_id, token, attempt)
        
        if not result:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400 if "Invalid" in error else 500)
        
        return web.json_response(result)
    
    except Exception as e:
        logger.error(f"Error reconnecting session: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)