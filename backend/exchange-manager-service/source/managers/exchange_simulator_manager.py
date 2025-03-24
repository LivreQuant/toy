# backend/exchange-manager-service/source/exchange_simulator_manager.py
import logging
import uuid
import time
import asyncio
import grpc
from concurrent import futures
from typing import Dict, Optional

from source.simulator.exchange_simulator import ExchangeSimulator
from source.config import Config
from source.api import exchange_simulator_pb2
from source.api import exchange_simulator_pb2_grpc

logger = logging.getLogger(__name__)


class ExchangeSimulatorManagerService(exchange_simulator_pb2_grpc.ExchangeSimulatorServicer):
    def __init__(self):
        self.simulators: Dict[str, Dict] = {}
        self.max_simulators = Config.MAX_USER_SIMULATORS
        self.simulator_timeout = Config.SIMULATOR_TIMEOUT_SECONDS

    def _cleanup_expired_simulators(self):
        """Remove simulators that have exceeded timeout"""
        current_time = time.time()
        expired = [
            sid for sid, simulator in self.simulators.items()
            if current_time - simulator['last_active'] > self.simulator_timeout
        ]

        for sid in expired:
            logger.info(f"Cleaning up expired simulator: {sid}")
            del self.simulators[sid]

    def StartSimulator(self, request, context):
        """Start a simulator for a specific session"""
        try:
            # Check for existing simulators
            for simulator in self.simulators.values():
                if (simulator['session_id'] == request.session_id and
                        simulator['status'] == 'ACTIVE'):
                    return exchange_simulator_pb2.StartSimulatorResponse(
                        success=True,
                        simulator_id=simulator['id']
                    )

            # Check total simulator count and clean up if needed
            if len(self.simulators) >= self.max_simulators:
                self._cleanup_expired_simulators()

                if len(self.simulators) >= self.max_simulators:
                    return exchange_simulator_pb2.StartSimulatorResponse(
                        success=False,
                        error_message="Maximum simulator limit reached"
                    )

            # Create new simulator
            simulator_id = str(uuid.uuid4())
            initial_symbols = request.initial_symbols or Config.DEFAULT_SYMBOLS
            initial_cash = request.initial_cash or Config.DEFAULT_INITIAL_CASH

            # In a real implementation, you would create a separate 
            # simulator instance for each user
            simulator = {
                'id': simulator_id,
                'session_id': request.session_id,
                'user_id': request.user_id,
                'created_at': time.time(),
                'last_active': time.time(),
                'status': 'ACTIVE',
                'symbols': initial_symbols,
                'initial_cash': initial_cash
            }

            self.simulators[simulator_id] = simulator

            logger.info(f"Created simulator {simulator_id} for session {request.session_id}")

            return exchange_simulator_pb2.StartSimulatorResponse(
                success=True,
                simulator_id=simulator_id
            )

        except Exception as e:
            logger.error(f"Error starting simulator: {e}")
            return exchange_simulator_pb2.StartSimulatorResponse(
                success=False,
                error_message=str(e)
            )

    def StopSimulator(self, request, context):
        """Stop a simulator"""
        try:
            # Find simulator by session ID
            for simulator_id, simulator in list(self.simulators.items()):
                if simulator['session_id'] == request.session_id:
                    del self.simulators[simulator_id]
                    logger.info(f"Stopped simulator {simulator_id} for session {request.session_id}")
                    return exchange_simulator_pb2.StopSimulatorResponse(success=True)

            return exchange_simulator_pb2.StopSimulatorResponse(
                success=False,
                error_message="No simulator found for this session"
            )

        except Exception as e:
            logger.error(f"Error stopping simulator: {e}")
            return exchange_simulator_pb2.StopSimulatorResponse(
                success=False,
                error_message=str(e)
            )

    def Heartbeat(self, request, context):
        """Update last active time for a simulator"""
        for simulator in self.simulators.values():
            if simulator['session_id'] == request.session_id:
                simulator['last_active'] = time.time()
                break

        return exchange_simulator_pb2.HeartbeatResponse(
            success=True,
            server_timestamp=int(time.time() * 1000)
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    exchange_simulator_pb2_grpc.add_ExchangeSimulatorServicer_to_server(
        ExchangeSimulatorManagerService(), server
    )
    server.add_insecure_port(f'[::]:{Config.PORT}')
    server.start()
    logger.info(f"Exchange Simulator Manager started on port {Config.PORT}")
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
