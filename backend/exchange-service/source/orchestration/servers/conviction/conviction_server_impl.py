# source/orchestration/servers/conviction/conviction_server_impl.py
import logging
import traceback
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from grpc import aio

from source.api.grpc.conviction_exchange_interface_pb2 import (
    BatchConvictionRequest,
    BatchConvictionResponse,
    ConvictionResponse
)
from source.api.grpc.conviction_exchange_interface_pb2_grpc import (
    ConvictionExchangeSimulatorServicer,
    add_ConvictionExchangeSimulatorServicer_to_server
)
from source.engines.engine_factory import EngineFactory
from source.orchestration.coordination.exchange_manager import ExchangeGroupManager
from source.api.grpc.conviction_exchange_interface_pb2 import BatchCancelResponse


class ConvictionServiceImpl(ConvictionExchangeSimulatorServicer):
    """Implementation of the ConvictionExchange gRPC service"""

    def __init__(self, exchange_group_manager: ExchangeGroupManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.exchange_group_manager = exchange_group_manager
        self.server: Optional[aio.Server] = None

    async def SubmitConvictions(self, request: BatchConvictionRequest, context) -> BatchConvictionResponse:
        """Submit convictions and convert them to orders"""

        self.logger.info("=" * 80)
        self.logger.info("📥 CONVICTION SERVICE: SubmitConvictions called")
        self.logger.info(f"📥 Request type: {type(request)}")
        self.logger.info(f"📥 Request has book_id: {hasattr(request, 'book_id')}")
        self.logger.info(f"📥 Request.book_id: {request.book_id}")
        self.logger.info(f"📥 Request.book_id type: {type(request.book_id)}")
        self.logger.info(f"📥 Request.convictions count: {len(request.convictions)}")
        self.logger.info(f"📥 Request attributes: {[attr for attr in dir(request) if not attr.startswith('_')]}")

        try:
            result = await self._async_submit_convictions(request, context)
            self.logger.info("✅ Async execution completed")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error in async execution: {e}")
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"Execution error: {e}"
            )

    async def _async_submit_convictions(self, request: BatchConvictionRequest, context) -> BatchConvictionResponse:
        """Async implementation of submit_convictions with proper book context switching"""
        self.logger.info("🔄 Inside async submit_convictions")

        # Extract book_id from request
        try:
            self.logger.info("🔄 Attempting to get book_id from request...")
            book_id_str = request.book_id
            self.logger.info(f"✅ Got book_id_str: {book_id_str}")
        except AttributeError as e:
            self.logger.error(f"❌ Request does not have book_id attribute: {e}")
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"Request missing book_id: {e}"
            )
        except Exception as e:
            self.logger.error(f"❌ Unexpected error getting book_id: {e}")
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"Error accessing book_id: {e}"
            )

        self.logger.info(f"📊 Received {len(request.convictions)} convictions from book {book_id_str}")

        # Convert string to UUID
        book_id = self._convert_book_id(book_id_str)
        if book_id is None:
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"Invalid book ID or book not found: {book_id_str}"
            )

        # Get book context
        try:
            book_context = self.exchange_group_manager.book_contexts[book_id]
            self.logger.info(f"✅ Got book context for {book_id}")

            # CRITICAL FIX: Switch global app_state to book's app_state
            import source.orchestration.app_state.state_manager as app_state_module
            original_app_state = app_state_module.app_state

            try:
                # Set book's app_state as current (like book_processor.py does)
                app_state_module.app_state = book_context.app_state
                self.logger.info(f"✅ Switched global app_state to book {book_id}'s app_state")

                # Verify exchange is available
                if app_state_module.app_state.exchange:
                    self.logger.info(
                        f"✅ Exchange available in book app_state: {id(app_state_module.app_state.exchange)}")
                else:
                    self.logger.error(f"❌ No exchange in book app_state for {book_id}")
                    return BatchConvictionResponse(
                        success=False,
                        results=[],
                        error_message=f"No exchange available for book {book_id_str}"
                    )

                # Set the book_id in the app_state for this book_context
                book_context.app_state.set_book_id(str(book_id))
                self.logger.info(f"✅ Set book_id {book_id} in app_state for this context")

                # CRITICAL FIX: Set book context in OrderManager
                if book_context.app_state.order_manager:
                    book_context.app_state.order_manager.set_book_context(str(book_id))
                    self.logger.info(f"✅ Set book context in OrderManager for {book_id}")
                else:
                    self.logger.warning(f"⚠️ No OrderManager found in book context for {book_id}")

                # Also set book context in component managers
                if hasattr(book_context.app_state, 'components'):
                    book_context.app_state.components.set_book_context(str(book_id))
                    self.logger.info(f"✅ Set book context in ComponentManagers for {book_id}")

                results = []
                current_time = datetime.now()

                try:
                    # Get book's engine type from database
                    self.logger.info("🔄 Getting engine ID...")
                    engine_id = book_context.app_state.get_engine_id()
                    self.logger.info(f"✅ Engine ID: {engine_id}")

                    if engine_id is None:
                        error_msg = f"Could not determine engine for book {book_id}"
                        self.logger.error(f"❌ {error_msg}")
                        return BatchConvictionResponse(
                            success=False,
                            results=[],
                            error_message=error_msg
                        )

                    # Create engine instance
                    self.logger.info(f"🔄 Creating engine instance for engine_id: {engine_id}")
                    engine = EngineFactory.create_engine(engine_id)

                    if engine is None:
                        error_msg = f"Failed to create engine for ID {engine_id}"
                        self.logger.error(f"❌ {error_msg}")
                        return BatchConvictionResponse(
                            success=False,
                            results=[],
                            error_message=error_msg
                        )

                    self.logger.info(f"✅ Engine created: {type(engine)}")

                    # Process all convictions at once (more efficient)
                    try:
                        # Convert all protobuf convictions to dict format
                        conviction_dicts = []
                        for conviction in request.convictions:
                            # Generate unique conviction ID if not provided
                            conviction_id = conviction.conviction_id if conviction.conviction_id else f"CONV_{uuid.uuid4().hex[:6].upper()}"

                            # Convert protobuf to dict
                            conviction_dict = self._protobuf_to_dict(conviction)
                            conviction_dict['conviction_id'] = conviction_id

                            conviction_dicts.append(conviction_dict)
                            self.logger.info(f"CONVICTION: {conviction_dict}")

                        # FIXED: Use correct engine method name and await it
                        all_orders = await engine.convert_convictions_to_orders(
                            book_id=str(book_id),
                            convictions=conviction_dicts,
                            book_context=book_context
                        )

                        self.logger.info(
                            f"✅ Engine generated {len(all_orders)} total orders from {len(conviction_dicts)} convictions")

                        # Create response results for each conviction
                        for i, conviction in enumerate(request.convictions):
                            conviction_id = conviction.conviction_id if conviction.conviction_id else f"CONV_{uuid.uuid4().hex[:6].upper()}"

                            # FIXED: Use correct protobuf field name (broker_id instead of conviction_id)
                            broker_id = f"BROKER_{conviction_id}_{uuid.uuid4().hex[:8]}"

                            results.append(ConvictionResponse(
                                success=True,
                                broker_id=broker_id,
                                error_message=""
                            ))

                    except Exception as e:
                        self.logger.error(f"❌ Error processing convictions through engine: {e}")
                        self.logger.error(f"   Traceback: {traceback.format_exc()}")

                        # Create error results for all convictions
                        for conviction in request.convictions:
                            results.append(ConvictionResponse(
                                success=False,
                                broker_id="",
                                error_message=f"Engine processing error: {e}"
                            ))

                        return BatchConvictionResponse(
                            success=False,
                            results=results,
                            error_message=f"Engine processing failed: {e}"
                        )

                    # Submit all orders to OrderManager (which now has proper exchange access)
                    if all_orders:
                        self.logger.info(f"🔄 Converting {len(all_orders)} orders to OrderManager format...")

                        orders_submitted = 0
                        for order in all_orders:
                            try:
                                # Convert order dict to the format expected by OrderManager
                                order_data = {
                                    'order_id': order['order_id'],
                                    'cl_order_id': order['cl_order_id'],
                                    'symbol': order['symbol'],
                                    'side': order['side'],
                                    'original_qty': float(order['original_qty']),
                                    'remaining_qty': float(order['remaining_qty']),
                                    'completed_qty': float(order['completed_qty']),
                                    'currency': order['currency'],
                                    'price': float(order['price']),
                                    'order_type': order['order_type'],
                                    'participation_rate': float(order['participation_rate']),
                                    'submit_timestamp': order['submit_timestamp'],
                                }

                                # Add order to OrderManager (which will now have proper exchange access)
                                success = book_context.app_state.order_manager.add_order(order_data)
                                if success:
                                    orders_submitted += 1
                                    self.logger.info(f"✅ Added order {order['order_id']} to OrderManager")
                                else:
                                    self.logger.error(f"❌ Failed to add order {order['order_id']} to OrderManager")

                            except Exception as e:
                                self.logger.error(
                                    f"❌ Error adding order {order.get('order_id', 'unknown')} to OrderManager: {e}")

                        self.logger.info(
                            f"✅ Successfully submitted {orders_submitted}/{len(all_orders)} orders to exchange")
                    else:
                        self.logger.warning("⚠️ No orders generated from convictions")

                    return BatchConvictionResponse(
                        success=True,
                        results=results,
                        error_message=""
                    )

                except Exception as e:
                    self.logger.error(f"❌ Error in conviction processing: {e}")
                    self.logger.error(f"   Traceback: {traceback.format_exc()}")
                    return BatchConvictionResponse(
                        success=False,
                        results=results,
                        error_message=f"Processing error: {e}"
                    )

            finally:
                # CRITICAL: Always restore original app_state
                app_state_module.app_state = original_app_state
                self.logger.info("✅ Restored original app_state")

        except KeyError:
            self.logger.error(f"❌ book {book_id} not found in exchange contexts")
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"book {book_id_str} not found in exchange"
            )
        except Exception as e:
            self.logger.error(f"❌ Unexpected error in conviction processing: {e}")
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
            return BatchConvictionResponse(
                success=False,
                results=[],
                error_message=f"Unexpected error: {e}"
            )

    async def CancelConvictions(self, request, context):
        """Cancel convictions - placeholder implementation"""
        self.logger.info("📥 CONVICTION SERVICE: CancelConvictions called")

        # Return empty response for now
        return BatchCancelResponse(
            success=True,
            results=[],
            error_message=""
        )

    def _convert_book_id(self, book_id_str: str) -> Optional[uuid.UUID]:
        """Convert book_id string to UUID and validate it exists"""
        self.logger.info(f"🔄 Converting book_id: {book_id_str} (type: {type(book_id_str)})")

        try:
            book_id = uuid.UUID(book_id_str)
            self.logger.info(f"✅ Converted to UUID: {book_id} (type: {type(book_id)})")

            if book_id in self.exchange_group_manager.book_contexts:
                self.logger.info(f"✅ book {book_id} found in exchange contexts")
                return book_id
            else:
                self.logger.error(f"❌ book {book_id} not found in exchange contexts")
                return None

        except ValueError as e:
            self.logger.error(f"❌ Invalid UUID format: {book_id_str}: {e}")
            return None

    def _protobuf_to_dict(self, conviction) -> Dict[str, Any]:
        """Convert protobuf conviction to dictionary"""
        conviction_dict = {
            'instrument_id': conviction.instrument_id,
            'conviction_id': conviction.conviction_id,
            'tag': conviction.tag,
            'score': conviction.score,
            'quantity': conviction.quantity,
            'zscore': conviction.zscore,
            'target_percentage': conviction.target_percentage,
            'target_notional': conviction.target_notional,
            'horizon_zscore': conviction.horizon_zscore,
        }

        # Handle enum fields
        if hasattr(conviction, 'participation_rate'):
            conviction_dict['participation_rate'] = conviction.participation_rate

        if hasattr(conviction, 'side'):
            conviction_dict['side'] = conviction.side

        # Handle optional fields
        if hasattr(conviction, 'min_position_size_pct') and conviction.HasField('min_position_size_pct'):
            conviction_dict['min_position_size_pct'] = conviction.min_position_size_pct

        if hasattr(conviction, 'max_position_size_pct') and conviction.HasField('max_position_size_pct'):
            conviction_dict['max_position_size_pct'] = conviction.max_position_size_pct

        if hasattr(conviction, 'max_days_to_liquidate') and conviction.HasField('max_days_to_liquidate'):
            conviction_dict['max_days_to_liquidate'] = conviction.max_days_to_liquidate

        return conviction_dict

    async def _cancel_existing_orders(self, book_id: uuid.UUID, conviction_id: str) -> bool:
        """Cancel all orders where cl_order_id matches conviction_id"""
        try:
            if book_id not in self.exchange_group_manager.book_contexts:
                self.logger.error(f"❌ No exchange context found for book {book_id}")
                return False

            book_context = self.exchange_group_manager.book_contexts[book_id]

            # Cancel orders using cl_order_id = conviction_id
            if hasattr(book_context.app_state, 'order_manager') and book_context.app_state.order_manager:
                cancel_result = book_context.app_state.order_manager.cancel_orders_by_cl_order_id(conviction_id)
                if cancel_result:
                    self.logger.info(f"✅ Cancelled orders with cl_order_id={conviction_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ No active orders found with cl_order_id={conviction_id}")
                    return True  # No orders to cancel is considered success
            else:
                self.logger.warning(f"⚠️ No order_manager found in book context")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error cancelling orders for conviction {conviction_id}: {e}")
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
            return False

    async def _submit_orders_to_exchange(self, book_id: uuid.UUID, orders: List[Dict[str, Any]]):
        """Submit generated orders to the exchange simulator"""
        try:
            if book_id not in self.exchange_group_manager.book_contexts:
                raise Exception(f"No exchange context found for book {book_id}")

            book_context = self.exchange_group_manager.book_contexts[book_id]

            for order in orders:
                print(f"WTF: {order}")
                # Submit order to book's exchange simulator through OrderManager
                if book_context.app_state.order_manager:
                    book_context.app_state.order_manager.add_order(order)
                    self.logger.info(f"✅ Added order {order.get('order_id', 'unknown')} to OrderManager")
                elif hasattr(book_context.app_state, 'components') and book_context.app_state.components.order_manager:
                    book_context.app_state.components.order_manager.add_order(order)
                    self.logger.info(
                        f"✅ Added order {order.get('order_id', 'unknown')} to ComponentManager OrderManager")
                else:
                    self.logger.error(f"❌ No order_manager found in book context")
                    raise Exception("No order_manager found in book context")

        except Exception as e:
            self.logger.error(f"❌ Failed to submit orders to exchange: {e}")
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
            raise

    async def start_server(self, port: int = 50052):
        """Start the gRPC server"""
        self.server = aio.server()
        add_ConvictionExchangeSimulatorServicer_to_server(self, self.server)

        listen_addr = f'[::]:{port}'
        self.server.add_insecure_port(listen_addr)

        self.logger.info(f"Starting ConvictionExchange server on {listen_addr}")
        await self.server.start()

        # Keep server running
        try:
            await self.server.wait_for_termination()
        except KeyboardInterrupt:
            self.logger.info("Server interrupted")
        finally:
            await self.server.stop(grace=5)

    async def stop_server(self):
        """Stop the gRPC server"""
        if self.server:
            await self.server.stop(grace=5)
            self.logger.info("ConvictionExchange server stopped")