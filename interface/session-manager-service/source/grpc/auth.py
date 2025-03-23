import logging
import grpc
import asyncio
import os

import source.api.auth_pb2
import source.api.auth_pb2_grpc

logger = logging.getLogger('auth_client')

class AuthServiceClient:
    """Client for communicating with auth service"""
    
    def __init__(self):
        self.auth_service = os.getenv('AUTH_SERVICE', 'auth-service:50051')
        self.channel = None
        self.stub = None
    
    async def connect(self):
        """Connect to auth service"""
        if self.channel:
            return
        
        options = [
            ('grpc.enable_retries', 1),
            ('grpc.max_reconnect_backoff_ms', 10000),
            ('grpc.initial_reconnect_backoff_ms', 1000),
            ('grpc.min_reconnect_backoff_ms', 1000),
            ('grpc.max_send_message_length', 10 * 1024 * 1024),
            ('grpc.max_receive_message_length', 10 * 1024 * 1024)
        ]
        
        # In production, this would use TLS
        self.channel = grpc.aio.insecure_channel(self.auth_service, options=options)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)
    
    async def check_service(self):
        """Check if auth service is available"""
        await self.connect()
        try:
            # Use a quick request to check if service is responsive
            await self.stub.ValidateToken(
                auth_pb2.ValidateTokenRequest(token="health-check"),
                timeout=2
            )
            return True
        except Exception as e:
            logger.error(f"Auth service check failed: {e}")
            # Try to reconnect
            self.channel = None
            return False
    
    async def validate_token(self, token):
        """Validate a JWT token"""
        await self.connect()
        
        try:
            response = await self.stub.ValidateToken(
                auth_pb2.ValidateTokenRequest(token=token)
            )
            
            return {
                'valid': response.valid,
                'user_id': response.user_id if response.valid else None
            }
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return {
                'valid': False,
                'user_id': None
            }
    
    async def close(self):
        """Close the connection"""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None