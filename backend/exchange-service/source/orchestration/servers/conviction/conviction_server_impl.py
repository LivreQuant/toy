# source/servers/convictionserver/conviction_entry_service_impl.py
import logging
import uuid
import grpc
from datetime import datetime
from typing import Dict

from source.orchestration.servers.utils import BaseServiceImpl
from source.orchestration.app_state.state_manager import app_state

from source.proto.conviction_exchange_interface_pb2 import (
    BatchConvictionRequest, BatchConvictionResponse, ConvictionResponse,
    BatchCancelRequest, BatchCancelResponse, CancelResult,
    Side as ConvictionSide, ParticipationRate
)
from source.proto.conviction_exchange_interface_pb2_grpc import ConvictionExchangeSimulatorServicer

class ConvictionServiceImpl(ConvictionExchangeSimulatorServicer, BaseServiceImpl):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Track active convictions
        self.active_convictions: Dict[str, Dict] = {}

    def SubmitConvictions(self, request: BatchConvictionRequest,
                          context: grpc.ServicerContext) -> BatchConvictionResponse:
        """Receive and process conviction submissions from external service"""

        def submit_convictions():
            self.logger.info(f"Received {len(request.convictions)} convictions")

            results = []
            current_time = datetime.now()

            for conviction in request.convictions:
                try:
                    # Validate conviction
                    validation_error = self._validate_conviction(conviction)
                    if validation_error:
                        results.append(ConvictionResponse(
                            success=False,
                            broker_id="",
                            error_message=validation_error
                        ))
                        self.logger.warning(f"Conviction validation failed: {validation_error}")
                        continue

                    # Generate broker ID
                    broker_id = f"CONV_{conviction.conviction_id}_{uuid.uuid4().hex[:8]}"

                    # Store conviction data
                    conviction_data = self._process_conviction(conviction, broker_id, current_time)
                    self.active_convictions[conviction.conviction_id] = conviction_data

                    # TODO: Later we'll convert to orders and submit to exchange
                    # For now, just store and track

                    results.append(ConvictionResponse(
                        success=True,
                        broker_id=broker_id,
                        error_message=""
                    ))

                    self.logger.info(f"Accepted conviction {conviction.conviction_id} for {conviction.instrument_id} "
                                     f"({conviction.quantity} shares, {conviction.side.name})")

                except Exception as e:
                    self.logger.error(f"Error processing conviction {conviction.conviction_id}: {e}")
                    results.append(ConvictionResponse(
                        success=False,
                        broker_id="",
                        error_message=f"Processing error: {str(e)}"
                    ))

            success_count = len([r for r in results if r.success])

            return BatchConvictionResponse(
                success=success_count > 0,
                results=results,
                error_message=f"Processed {success_count}/{len(request.convictions)} convictions"
            )

        return self._handle_request(context, submit_convictions)

    def CancelConvictions(self, request: BatchCancelRequest, context: grpc.ServicerContext) -> BatchCancelResponse:
        """Cancel convictions"""

        def cancel_convictions():
            self.logger.info(f"Received cancellation request for {len(request.conviction_id)} convictions")

            results = []
            current_time = datetime.now()

            for conviction_id in request.conviction_id:
                try:
                    # Check if conviction exists
                    if conviction_id not in self.active_convictions:
                        results.append(CancelResult(
                            broker_id=conviction_id,
                            success=False,
                            error_message="Conviction not found or already processed"
                        ))
                        continue

                    # Get conviction data
                    conviction_data = self.active_convictions[conviction_id]

                    # Mark as cancelled
                    conviction_data['status'] = 'CANCELLED'
                    conviction_data['cancel_time'] = current_time

                    # TODO: Later we'll cancel any associated orders

                    results.append(CancelResult(
                        broker_id=conviction_data['broker_id'],
                        success=True,
                        error_message=""
                    ))

                    self.logger.info(f"Cancelled conviction {conviction_id}")

                except Exception as e:
                    self.logger.error(f"Error cancelling conviction {conviction_id}: {e}")
                    results.append(CancelResult(
                        broker_id=conviction_id,
                        success=False,
                        error_message=f"Cancellation error: {str(e)}"
                    ))

            success_count = len([r for r in results if r.success])

            return BatchCancelResponse(
                success=success_count > 0,
                results=results,
                error_message=f"Cancelled {success_count}/{len(request.conviction_id)} convictions"
            )

        return self._handle_request(context, cancel_convictions)

    def _validate_conviction(self, conviction) -> str:
        """Validate conviction parameters"""
        if not conviction.instrument_id:
            return "Missing instrument_id"

        if not conviction.conviction_id:
            return "Missing conviction_id"

        if conviction.quantity <= 0:
            return "Quantity must be positive"

        # Check if instrument exists in universe
        if app_state.universe_manager:
            if not app_state.universe_manager.is_valid_symbol(conviction.instrument_id):
                return f"Invalid instrument: {conviction.instrument_id}"

        # Check for duplicate conviction ID
        if conviction.conviction_id in self.active_convictions:
            return f"Conviction ID already exists: {conviction.conviction_id}"

        return ""

    def _process_conviction(self, conviction, broker_id: str, submit_time: datetime) -> Dict:
        """Process and store conviction data"""

        # Convert participation rate enum to float
        participation_map = {
            ParticipationRate.LOW: 0.01,  # 1%
            ParticipationRate.MEDIUM: 0.03,  # 3%
            ParticipationRate.HIGH: 0.05  # 5%
        }
        participation_rate = participation_map.get(conviction.participation_rate, 0.03)

        # Get currency from universe
        currency = "USD"  # Default
        if app_state.universe_manager:
            symbol_data = app_state.universe_manager.get_symbol_metadata(conviction.instrument_id)
            if symbol_data:
                currency = symbol_data.get('currency', 'USD')

        # Store conviction data
        conviction_data = {
            'conviction_id': conviction.conviction_id,
            'broker_id': broker_id,
            'instrument_id': conviction.instrument_id,
            'side': 'BUY' if conviction.side == ConvictionSide.BUY else 'SELL',
            'quantity': float(conviction.quantity),
            'currency': currency,
            'participation_rate': participation_rate,
            'tag': conviction.tag,
            'score': float(conviction.score),
            'zscore': float(conviction.zscore),
            'target_percentage': float(conviction.target_percentage),
            'target_notional': float(conviction.target_notional),
            'horizon_zscore': conviction.horizon_zscore,
            'status': 'ACTIVE',
            'submit_time': submit_time,
            'cancel_time': None
        }

        return conviction_data

    def get_active_convictions(self) -> Dict[str, Dict]:
        """Get all active convictions"""
        return {k: v for k, v in self.active_convictions.items() if v['status'] == 'ACTIVE'}

    def get_all_convictions(self) -> Dict[str, Dict]:
        """Get all convictions (active and cancelled)"""
        return self.active_convictions.copy()