# Add these new methods to the ExchangeSimulatorService class

async def SubmitOrder(self, request, context):
    """Handle SubmitOrder gRPC request"""
    session_id = request.session_id
    symbol = request.symbol
    side = "BUY" if request.side == 0 else "SELL"
    quantity = float(request.quantity)
    price = float(request.price) if request.price > 0 else None
    order_type = "MARKET" if request.type == 0 else "LIMIT"
    request_id = request.request_id
    
    logger.info(f"SubmitOrder request for session {session_id}: {quantity} {symbol} {side}")
    
    # First check if session is active
    if session_id not in self.simulator.sessions:
        return exchange_simulator_pb2.SubmitOrderResponse(
            success=False,
            error_message="Session not active"
        )
    
    # Update session activity
    self.simulator.update_session_activity(session_id)
    
    # Submit the order
    result = self.simulator.order_manager.submit_order(
        session_id, symbol, side, quantity, price, order_type, request_id
    )
    
    return exchange_simulator_pb2.SubmitOrderResponse(
        success=result.get('success', False),
        order_id=result.get('order_id', ''),
        error_message=result.get('error_message', '')
    )

async def CancelOrder(self, request, context):
    """Handle CancelOrder gRPC request"""
    session_id = request.session_id
    order_id = request.order_id
    
    logger.info(f"CancelOrder request for session {session_id}, order {order_id}")
    
    # First check if session is active
    if session_id not in self.simulator.sessions:
        return exchange_simulator_pb2.CancelOrderResponse(
            success=False,
            error_message="Session not active"
        )
    
    # Update session activity
    self.simulator.update_session_activity(session_id)
    
    # Cancel the order
    result = self.simulator.order_manager.cancel_order(session_id, order_id)
    
    return exchange_simulator_pb2.CancelOrderResponse(
        success=result.get('success', False),
        error_message=result.get('error_message', '')
    )

async def GetOrderStatus(self, request, context):
    """Handle GetOrderStatus gRPC request"""
    session_id = request.session_id
    order_id = request.order_id
    
    logger.info(f"GetOrderStatus request for session {session_id}, order {order_id}")
    
    # First check if session is active
    if session_id not in self.simulator.sessions:
        return exchange_simulator_pb2.GetOrderStatusResponse(
            status=0,  # UNKNOWN
            error_message="Session not active"
        )
    
    # Update session activity
    self.simulator.update_session_activity(session_id)
    
    # Get order status
    result = self.simulator.order_manager.get_order_status(session_id, order_id)
    
    if not result.get('success'):
        return exchange_simulator_pb2.GetOrderStatusResponse(
            status=0,  # UNKNOWN
            error_message=result.get('error_message', '')
        )
    
    return exchange_simulator_pb2.GetOrderStatusResponse(
        status=result.get('status', 0),
        filled_quantity=result.get('filled_quantity', 0),
        avg_price=result.get('avg_price', 0),
        error_message=result.get('error_message', '')
    )