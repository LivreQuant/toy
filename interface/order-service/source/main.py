# order_service.py
import grpc
import json
import uuid
import logging
import time
from concurrent import futures
import order_service_pb2
import order_service_pb2_grpc
import auth_pb2
import auth_pb2_grpc
import session_manager_pb2
import session_manager_pb2_grpc
from redis import Redis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('order_service')

class OrderServicer(order_service_pb2_grpc.OrderServiceServicer):
    def __init__(self, auth_channel, session_manager_channel, redis_client):
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
        self.session_manager_stub = session_manager_pb2_grpc.SessionManagerServiceStub(session_manager_channel)
        self.redis = redis_client
        
        # Track order requests to detect duplicates if client retries
        self.recently_processed = {}
    
    def SubmitOrder(self, request, context):
        # 1. Validate authentication
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during SubmitOrder")
            return order_service_pb2.SubmitOrderResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        session_id = request.session_id
        
        # 2. Validate session
        try:
            session_response = self.session_manager_stub.GetSession(
                session_manager_pb2.GetSessionRequest(
                    session_id=session_id,
                    token=request.token
                )
            )
            
            if not session_response.session_active:
                logger.warning(f"Inactive session {session_id} during SubmitOrder")
                return order_service_pb2.SubmitOrderResponse(
                    success=False,
                    error_message="Session is not active"
                )
        except grpc.RpcError as e:
            logger.error(f"Error validating session: {e}")
            return order_service_pb2.SubmitOrderResponse(
                success=False,
                error_message="Failed to validate session"
            )
        
        # 3. Check for request ID duplication (idempotency) - optional client feature
        if request.request_id:
            # If client sent a request ID, check if we've seen it recently
            request_key = f"{user_id}:{request.request_id}"
            if request_key in self.recently_processed:
                stored_response = self.recently_processed[request_key]
                logger.info(f"Returning cached response for duplicate request {request.request_id}")
                return stored_response
            
            # Clean up old request IDs (keep for 5 minutes)
            self._cleanup_old_request_ids()
        
        # 4. Check connection quality via Redis (client info is stored in Redis by connection manager)
        connection_quality = self._check_connection_quality(user_id, session_id)
        if connection_quality == "poor":
            logger.warning(f"Rejecting order for user {user_id} due to poor connection quality")
            return order_service_pb2.SubmitOrderResponse(
                success=False,
                error_message="Order rejected: Connection quality is too poor for order submission"
            )
        
        # 5. Get simulator routing information
        simulator_info = self._get_simulator_info(session_id)
        if not simulator_info:
            logger.warning(f"No simulator found for session {session_id}")
            return order_service_pb2.SubmitOrderResponse(
                success=False,
                error_message="No active simulator found for this session"
            )
        
        # 6. Process the order (in production, forward to the appropriate simulator pod)
        order_id = str(uuid.uuid4())
        logger.info(f"Creating order {order_id} for user {user_id} on simulator {simulator_info.get('simulator_id')}")
        
        # Simulate order processing delay
        time.sleep(0.2)
        
        # 7. Store order in Redis for tracking
        order_data = {
            "id": order_id,
            "user_id": user_id,
            "session_id": session_id,
            "symbol": request.symbol,
            "side": self._side_to_string(request.side),
            "price": request.price,
            "quantity": request.quantity,
            "status": "NEW",
            "filled_quantity": 0,
            "avg_price": 0,
            "timestamp": time.time()
        }
        
        self.redis.set(f"order:{order_id}", json.dumps(order_data))
        self.redis.expire(f"order:{order_id}", 86400)  # Expire after 24 hours
        
        # Add to user's order list
        self.redis.lpush(f"user:{user_id}:orders", order_id)
        self.redis.ltrim(f"user:{user_id}:orders", 0, 99)  # Keep last 100 orders
        
        # Create response
        response = order_service_pb2.SubmitOrderResponse(
            success=True,
            order_id=order_id
        )
        
        # Store response for idempotency if request_id provided
        if request.request_id:
            self.recently_processed[f"{user_id}:{request.request_id}"] = response
        
        return response
    
    def CancelOrder(self, request, context):
        # Similar flow to SubmitOrder with connection validation
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during CancelOrder")
            return order_service_pb2.CancelOrderResponse(
                success=False,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        session_id = request.session_id
        order_id = request.order_id
        
        # Get order data
        order_data = self._get_order_data(order_id)
        if not order_data:
            logger.warning(f"Order {order_id} not found")
            return order_service_pb2.CancelOrderResponse(
                success=False,
                error_message="Order not found"
            )
        
        # Verify order belongs to user
        if order_data.get("user_id") != user_id:
            logger.warning(f"Order {order_id} does not belong to user {user_id}")
            return order_service_pb2.CancelOrderResponse(
                success=False,
                error_message="Order does not belong to user"
            )
        
        # Check if order is in a state that can be canceled
        if order_data.get("status") not in ["NEW", "PARTIALLY_FILLED"]:
            logger.warning(f"Cannot cancel order {order_id} in state {order_data.get('status')}")
            return order_service_pb2.CancelOrderResponse(
                success=False,
                error_message=f"Cannot cancel order in state {order_data.get('status')}"
            )
        
        # Process cancellation (in production, forward to the appropriate simulator pod)
        order_data["status"] = "CANCELED"
        
        # Save updated order
        self.redis.set(f"order:{order_id}", json.dumps(order_data))
        
        return order_service_pb2.CancelOrderResponse(success=True)
    
    def GetOrderStatus(self, request, context):
        validate_response = self.auth_stub.ValidateToken(
            auth_pb2.ValidateTokenRequest(token=request.token)
        )
        
        if not validate_response.valid:
            logger.warning(f"Invalid token during GetOrderStatus")
            return order_service_pb2.GetOrderStatusResponse(
                status=order_service_pb2.GetOrderStatusResponse.Status.UNKNOWN,
                error_message="Invalid authentication token"
            )
        
        user_id = validate_response.user_id
        order_id = request.order_id
        
        # Get order data
        order_data = self._get_order_data(order_id)
        if not order_data:
            logger.warning(f"Order {order_id} not found")
            return order_service_pb2.GetOrderStatusResponse(
                status=order_service_pb2.GetOrderStatusResponse.Status.UNKNOWN,
                error_message="Order not found"
            )
        
        # Verify order belongs to user
        if order_data.get("user_id") != user_id:
            logger.warning(f"Order {order_id} does not belong to user {user_id}")
            return order_service_pb2.GetOrderStatusResponse(
                status=order_service_pb2.GetOrderStatusResponse.Status.UNKNOWN,
                error_message="Order does not belong to user"
            )
        
        # Map status string to enum
        status_map = {
            "NEW": order_service_pb2.GetOrderStatusResponse.Status.NEW,
            "PARTIALLY_FILLED": order_service_pb2.GetOrderStatusResponse.Status.PARTIALLY_FILLED,
            "FILLED": order_service_pb2.GetOrderStatusResponse.Status.FILLED,
            "CANCELED": order_service_pb2.GetOrderStatusResponse.Status.CANCELED,
            "REJECTED": order_service_pb2.GetOrderStatusResponse.Status.REJECTED
        }
        
        status_enum = status_map.get(
            order_data.get("status"), 
            order_service_pb2.GetOrderStatusResponse.Status.UNKNOWN
        )
        
        return order_service_pb2.GetOrderStatusResponse(
            status=status_enum,
            filled_quantity=order_data.get("filled_quantity", 0),
            avg_price=order_data.get("avg_price", 0)
        )
    
    def _get_order_data(self, order_id):
        order_json = self.redis.get(f"order:{order_id}")
        if not order_json:
            return None
        
        try:
            return json.loads(order_json.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error decoding order data for {order_id}: {e}")
            return None
    
    def _cleanup_old_request_ids(self):
        # Remove request IDs older than 5 minutes
        current_time = time.time()
        to_remove = []
        
        for key, (timestamp, _) in self.recently_processed.items():
            if current_time - timestamp > 300:  # 5 minutes
                to_remove.append(key)
        
        for key in to_remove:
            del self.recently_processed[key]
    
    def _check_connection_quality(self, user_id, session_id):
        # In production, this would check connection metrics in Redis
        # For now, return "good" as default
        connection_quality_key = f"connection:{user_id}:{session_id}:quality"
        quality = self.redis.get(connection_quality_key)
        
        if quality:
            return quality.decode()
        
        return "good"  # Default to good if no data
    
    def _get_simulator_info(self, session_id):
        # Get simulator info from Redis
        simulator_id = self.redis.get(f"session:{session_id}:simulator")
        
        if not simulator_id:
            return None
        
        simulator_endpoint = self.redis.get(f"simulator:{simulator_id.decode()}:endpoint")
        
        if not simulator_endpoint:
            return None
        
        return {
            "simulator_id": simulator_id.decode(),
            "endpoint": simulator_endpoint.decode()
        }
    
    def _side_to_string(self, side_enum):
        if side_enum == order_service_pb2.SubmitOrderRequest.Side.BUY:
            return "BUY"
        elif side_enum == order_service_pb2.SubmitOrderRequest.Side.SELL:
            return "SELL"
        return "UNKNOWN"

def serve():
    auth_channel = grpc.insecure_channel('auth:50051')
    session_manager_channel = grpc.insecure_channel('session-manager:50052')
    redis_client = Redis(host='redis', port=6379, db=0)
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_service_pb2_grpc.add_OrderServiceServicer_to_server(
        OrderServicer(auth_channel, session_manager_channel, redis_client), server
    )
    server.add_insecure_port('[::]:50054')
    server.start()
    logger.info("Order Service started on port 50054")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()