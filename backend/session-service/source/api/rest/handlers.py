"""
REST API request handlers.
Implements the handlers for the REST API endpoints.
"""
import logging
import json
import time
from aiohttp import web

logger = logging.getLogger('rest_handlers')


async def get_token_from_request(request):
    """
    Extract token from request headers or query parameters

    Args:
        request: HTTP request

    Returns:
        Token string or None
    """
    # Try Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]

    # Try query parameter
    token = request.query.get('token')
    if token:
        return token

    # Try POST body (for JSON requests)
    content_type = request.headers.get('Content-Type', '')
    if 'application/json' in content_type and request.body_exists:
        try:
            data = await request.json()
            if data and 'token' in data:
                return data['token']
        except:
            pass

    return None

async def handle_create_session(request):
    """
    Handle session creation request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    try:
        # Parse request body
        data = await request.json()
        
        # Extract parameters
        user_id = data.get('userId')
        token = data.get('token')
        
        if not user_id or not token:
            return web.json_response({
                'success': False,
                'error': 'Missing userId or token'
            }, status=400)
        
        # Get client IP
        client_ip = request.remote
        
        # Create session
        session_id, is_new = await session_manager.create_session(user_id, token, client_ip)
        
        if not session_id:
            return web.json_response({
                'success': False,
                'error': 'Failed to create session'
            }, status=500)
        
        return web.json_response({
            'success': True,
            'sessionId': session_id,
            'isNew': is_new
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return web.json_response({
            'success': False,
            'error': 'Server error'
        }, status=500)

async def handle_get_session(request):
    """
    Handle session retrieval request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing authentication token'
        }, status=401)
    
    # Validate session
    user_id = await session_manager.validate_session(session_id, token)
    if not user_id:
        return web.json_response({
            'success': False,
            'error': 'Invalid session or token'
        }, status=401)
    
    # Get session details
    session = await session_manager.get_session(session_id)
    
    if not session:
        return web.json_response({
            'success': False,
            'error': 'Session not found'
        }, status=404)
    
    # Return session details
    return web.json_response({
        'success': True,
        'session': session
    })

async def handle_end_session(request):
    """
    Handle session termination request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    # Get token
    token = await get_token_from_request(request)
    if not token:
        return web.json_response({
            'success': False,
            'error': 'Missing authentication token'
        }, status=401)
    
    # End session
    success, error = await session_manager.end_session(session_id, token)
    
    if not success:
        return web.json_response({
            'success': False,
            'error': error
        }, status=400)
    
    return web.json_response({
        'success': True
    })

async def handle_start_simulator(request):
    """
    Handle simulator start request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    try:
        # Parse request body
        data = await request.json()
        
        # Extract parameters
        session_id = data.get('sessionId')
        token = data.get('token')
        
        if not session_id or not token:
            return web.json_response({
                'success': False,
                'error': 'Missing sessionId or token'
            }, status=400)
        
        # Start simulator
        simulator_id, endpoint, error = await session_manager.start_simulator(session_id, token)
        
        if error:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400)
        
        return web.json_response({
            'success': True,
            'simulatorId': simulator_id,
            'endpoint': endpoint
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error starting simulator: {e}")
        return web.json_response({
            'success': False,
            'error': 'Server error'
        }, status=500)

async def handle_stop_simulator(request):
    """
    Handle simulator stop request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    # Get simulator ID from URL
    simulator_id = request.match_info['simulator_id']
    
    try:
        # Parse request body
        data = await request.json()
        
        # Extract parameters
        session_id = data.get('sessionId')
        token = data.get('token')
        
        if not session_id or not token:
            return web.json_response({
                'success': False,
                'error': 'Missing sessionId or token'
            }, status=400)
            
        # Check if this is the simulator for the session
        session = await session_manager.get_session(session_id)
        if not session or session.get('simulator_id') != simulator_id:
            return web.json_response({
                'success': False,
                'error': 'Simulator does not belong to this session'
            }, status=400)
        
        # Stop simulator
        success, error = await session_manager.stop_simulator(session_id, token)
        
        if not success:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400)
        
        return web.json_response({
            'success': True
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error stopping simulator: {e}")
        return web.json_response({
            'success': False,
            'error': 'Server error'
        }, status=500)

async def handle_get_simulator_status(request):
    """
    Handle simulator status request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    # Get simulator ID from URL
    simulator_id = request.match_info['simulator_id']
    
    # Get token and session ID
    token = request.query.get('token')
    session_id = request.query.get('sessionId')
    
    if not token or not session_id:
        return web.json_response({
            'success': False,
            'error': 'Missing token or sessionId'
        }, status=400)
    
    # Validate session
    user_id = await session_manager.validate_session(session_id, token)
    if not user_id:
        return web.json_response({
            'success': False,
            'error': 'Invalid session or token'
        }, status=401)
    
    # Get simulator status
    status = await session_manager.simulator_manager.get_simulator_status(simulator_id)
    
    # Check if simulator belongs to session
    session = await session_manager.get_session(session_id)
    if not session or session.get('simulator_id') != simulator_id:
        return web.json_response({
            'success': False,
            'error': 'Simulator does not belong to this session'
        }, status=400)
    
    return web.json_response({
        'success': True,
        'status': status
    })

async def handle_reconnect_session(request):
    """
    Handle session reconnection request
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    session_manager = request.app['session_manager']
    
    # Get session ID from URL
    session_id = request.match_info['session_id']
    
    try:
        # Parse request body
        data = await request.json()
        
        # Extract parameters
        token = data.get('token')
        attempt = data.get('attempt', 1)
        
        if not token:
            return web.json_response({
                'success': False,
                'error': 'Missing token'
            }, status=400)
        
        # Reconnect to session
        session_data, error = await session_manager.reconnect_session(session_id, token, attempt)
        
        if error:
            return web.json_response({
                'success': False,
                'error': error
            }, status=400)
        
        return web.json_response({
            'success': True,
            'session': session_data
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error reconnecting session: {e}")
        return web.json_response({
            'success': False,
            'error': 'Server error'
        }, status=500)