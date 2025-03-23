import logging
import grpc
import asyncio
from typing import Dict, List, Optional, Any

import source.api.exchange_simulator_pb2
import source.api.exchange_simulator_pb2_grpc

logger = logging.getLogger('exchange_client')

class ExchangeServiceClient:
    """Client for communicating with exchange simulator service"""
    
    def __init__(self):
        self.channels = {}  # endpoint -> channel
        self.stubs = {}     # endpoint -> stub
    
    async def check_service(self):
        """Check if exchange service is available"""
        # This would check a known exchange service
        # In real implementation, might check service registry
        return True
    
    async def get_channel(self, endpoint):
        """Get or create a gRPC channel to the endpoint"""
        if endpoint in self.channels:
            return self.channels[endpoint], self.stubs[endpoint]
        
        # Create channel options
        options = [
            ('grpc.keepalive_time_ms', 10000),        # 10 seconds
            ('grpc.keepalive_timeout_ms', 5000),      # 5 seconds
            ('grpc.keepalive_permit_without_calls', 1),
            ('grpc.http2.max_pings_without_data', 0), 
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 5000)
        ]
        
        # Create channel
        channel = grpc.aio.insecure_channel(endpoint, options=options)
        stub = exchange_simulator_pb2_grpc.ExchangeSimulatorStub(channel)
        
        # Store for reuse
        self.channels[endpoint] = channel
        self.stubs[endpoint] = stub
        
        return channel, stub
    
    async def start_simulator(self, session_id, user_id):
        """Start a new simulator instance"""
        # In a real implementation, this would call a simulator manager
        # service to provision a new simulator instance
        
        # Simulate a successful response for now
        simulator_id = f"simulator-{session_id}"
        simulator_endpoint = f"exchange-{session_id}.exchangesvc:50053"
        
        return {
            'success': True,
            'simulator_id': simulator_id,
            'simulator_endpoint': simulator_endpoint
        }
    
    async def stop_simulator(self, simulator_id):
        """Stop a simulator instance"""
        # In a real implementation, call simulator manager
        # Simulate success
        return {
            'success': True
        }
    
    async def get_simulator_status(self, simulator_id):
        """Get the status of a simulator instance"""
        # In real implementation, call simulator manager
        # Simulate a running simulator
        return "RUNNING"
    
    async def stream_exchange_data(self, session_id, user_id, simulator_id, symbols=None):
        """Stream exchange data from a simulator"""
        # Get simulator endpoint
        # In a real implementation, would look up endpoint from registry
        # Mock endpoint for now
        endpoint = f"exchange-{simulator_id}.exchangesvc:50053"
        
        # Get or create channel
        _, stub = await self.get_channel(endpoint)
        
        # Create request
        request = exchange_simulator_pb2.StreamRequest(
            session_id=session_id,
            client_id=f"session_service_{user_id}",
            symbols=symbols or []
        )
        
        # Start stream
        stream = stub.StreamExchangeData(request)
        return stream
    
    async def send_heartbeat(self, session_id, simulator_id):
        """Send heartbeat to exchange simulator"""
        # Get simulator endpoint
        endpoint = f"exchange-{simulator_id}.exchangesvc:50053"
        
        # Get or create channel
        _, stub = await self.get_channel(endpoint)
        
        # Create request
        request = exchange_simulator_pb2.HeartbeatRequest(
            session_id=session_id,
            client_id="session_service",
            client_timestamp=int(time.time() * 1000)
        )
        
        # Send heartbeat
        try:
            response = await stub.Heartbeat(request, timeout=5)
            return response.success
        except Exception as e:
            logger.error(f"Error sending heartbeat to exchange {simulator_id}: {e}")
            return False
    
    async def close(self):
        """Close all channels"""
        for endpoint, channel in self.channels.items():
            try:
                await channel.close()
            except Exception as e:
                logger.error(f"Error closing channel to {endpoint}: {e}")
        
        self.channels.clear()
        self.stubs.clear()