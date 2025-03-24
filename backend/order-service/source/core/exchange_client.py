# source/core/exchange_client.py
import logging
import grpc
import asyncio
import time
from typing import Dict, Any, Optional, List
import json

from source.api.exchange_pb2 import (
    SubmitOrderRequest, CancelOrderRequest, GetOrderStatusRequest
)
from source.api.exchange_pb2_grpc import ExchangeServiceStub
from source.models.order import Order, OrderStatus, OrderSide, OrderType

logger = logging.getLogger('exchange_client')

class ExchangeClient:
    """Client for communicating with exchange simulator via gRPC"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.channels = {}  # endpoint -> channel
        self.stubs = {}     # endpoint -> stub
    
    async def get_channel(self, endpoint: str):
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
        stub = ExchangeServiceStub(channel)
        
        # Store for reuse
        self.channels[endpoint] = channel
        self.stubs[endpoint] = stub
        
        return channel, stub
    
    async def get_simulator_info(self, session_id: str) -> Optional[Dict[str, str]]:
        """Get simulator info from Redis"""
        try:
            # Get simulator ID for this session
            simulator_id = await self.redis.get(f"session:{session_id}:simulator")
            
            if not simulator_id:
                logger.warning(f"No simulator found for session {session_id}")
                return None
            
            # Get simulator endpoint
            simulator_endpoint = await self.redis.get(f"simulator:{simulator_id}:endpoint")
            
            if not simulator_endpoint:
                logger.warning(f"No endpoint found for simulator {simulator_id}")
                return None
            
            return {
                "simulator_id": simulator_id,
                "endpoint": simulator_endpoint
            }
        except Exception as e:
            logger.error(f"Error getting simulator info: {e}")
            return None
    
    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """Submit an order to the exchange simulator"""
        # Get simulator info
        simulator_info = await self.get_simulator_info(order.session_id)
        
        if not simulator_info:
            logger.warning(f"Cannot submit order: No simulator for session {order.session_id}")
            return {
                "success": False,
                "error": "No active simulator found for this session"
            }
        
        try:
            # Get gRPC connection
            _, stub = await self.get_channel(simulator_info["endpoint"])
            
            # Convert order side and type to gRPC enum values
            side_enum = self._string_to_side_enum(order.side)
            type_enum = self._string_to_type_enum(order.order_type)
            
            # Create gRPC request
            request = SubmitOrderRequest(
                session_id=order.session_id,
                symbol=order.symbol,
                side=side_enum,
                quantity=float(order.quantity),
                price=float(order.price) if order.price is not None else 0,
                type=type_enum,
                request_id=order.request_id or f"order-{int(time.time())}-{order.order_id}"
            )
            
            # Call gRPC service
            response = await stub.SubmitOrder(request, timeout=5)
            
            # Update order with simulator ID
            order.simulator_id = simulator_info["simulator_id"]
            
            if not response.success:
                logger.warning(f"Order submission failed: {response.error_message}")
                return {
                    "success": False,
                    "error": response.error_message,
                    "order_id": order.order_id
                }
            
            return {
                "success": True,
                "order_id": response.order_id or order.order_id
            }
            
        except Exception as e:
            logger.error(f"Error submitting order to exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}",
                "order_id": order.order_id
            }
    
    async def cancel_order(self, order: Order) -> Dict[str, Any]:
        """Cancel an order on the exchange simulator"""
        # Get simulator info
        simulator_info = await self.get_simulator_info(order.session_id)
        
        if not simulator_info:
            logger.warning(f"Cannot cancel order: No simulator for session {order.session_id}")
            return {
                "success": False,
                "error": "No active simulator found for this session"
            }
        
        try:
            # Get gRPC connection
            _, stub = await self.get_channel(simulator_info["endpoint"])
            
            # Create gRPC request
            request = CancelOrderRequest(
                session_id=order.session_id,
                order_id=order.order_id
            )
            
            # Call gRPC service
            response = await stub.CancelOrder(request, timeout=5)
            
            if not response.success:
                logger.warning(f"Order cancellation failed: {getattr(response, 'error_message', 'Unknown error')}")
                return {
                    "success": False,
                    "error": getattr(response, "error_message", "Cancellation failed")
                }
            
            return {
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error cancelling order on exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}"
            }
    
    async def get_order_status(self, order: Order) -> Dict[str, Any]:
        """Get order status from the exchange simulator"""
        # Get simulator info
        simulator_info = await self.get_simulator_info(order.session_id)
        
        if not simulator_info:
            logger.warning(f"Cannot get order status: No simulator for session {order.session_id}")
            return {
                "success": False,
                "error": "No active simulator found for this session"
            }
        
        try:
            # Get gRPC connection
            _, stub = await self.get_channel(simulator_info["endpoint"])
            
            # Create gRPC request
            request = GetOrderStatusRequest(
                session_id=order.session_id,
                order_id=order.order_id
            )
            
            # Call gRPC service
            response = await stub.GetOrderStatus(request, timeout=5)
            
            # Map gRPC enum status to string
            status = self._status_enum_to_string(response.status)
            
            # source/core/exchange_client.py (continued)
            return {
                "success": True,
                "status": status,
                "filled_quantity": float(response.filled_quantity),
                "avg_price": float(response.avg_price),
                "error_message": getattr(response, "error_message", None)
            }
            
        except Exception as e:
            logger.error(f"Error getting order status from exchange: {e}")
            return {
                "success": False,
                "error": f"Exchange communication error: {str(e)}"
            }
    
    def _string_to_side_enum(self, side):
        """Convert string order side to gRPC enum value"""
        side_str = side.value if isinstance(side, OrderSide) else side
        if side_str == "BUY":
            return SubmitOrderRequest.Side.BUY
        elif side_str == "SELL":
            return SubmitOrderRequest.Side.SELL
        else:
            raise ValueError(f"Invalid order side: {side}")
    
    def _string_to_type_enum(self, order_type):
        """Convert string order type to gRPC enum value"""
        type_str = order_type.value if isinstance(order_type, OrderType) else order_type
        if type_str == "MARKET":
            return SubmitOrderRequest.Type.MARKET
        elif type_str == "LIMIT":
            return SubmitOrderRequest.Type.LIMIT
        else:
            raise ValueError(f"Invalid order type: {order_type}")
    
    def _status_enum_to_string(self, status_enum):
        """Convert gRPC enum status to string status"""
        status_map = {
            GetOrderStatusResponse.Status.NEW: OrderStatus.NEW,
            GetOrderStatusResponse.Status.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
            GetOrderStatusResponse.Status.FILLED: OrderStatus.FILLED,
            GetOrderStatusResponse.Status.CANCELED: OrderStatus.CANCELED,
            GetOrderStatusResponse.Status.REJECTED: OrderStatus.REJECTED,
            GetOrderStatusResponse.Status.UNKNOWN: OrderStatus.REJECTED  # Map unknown to rejected
        }
        return status_map.get(status_enum, OrderStatus.REJECTED)
    
    async def close(self):
        """Close all gRPC channels"""
        for endpoint, channel in self.channels.items():
            try:
                await channel.close()
            except Exception as e:
                logger.error(f"Error closing channel to {endpoint}: {e}")
        
        self.channels.clear()
        self.stubs.clear()