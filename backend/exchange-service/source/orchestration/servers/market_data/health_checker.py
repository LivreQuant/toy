# source/servers/market_data/health_checker.py
import asyncio
import grpc
import logging
import socket
from datetime import datetime
from typing import Callable
from threading import Thread, Event

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceStub


class MarketDataHealthChecker:
    """Monitors external market data service availability"""

    def __init__(self, host: str = "localhost", port: int = 50051, check_interval: int = 10):
        self.host = host
        self.port = port
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)

        # State tracking
        self.is_available = False
        self.last_check_time = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0

        # Threading
        self._stop_event = Event()
        self._health_thread = None

        # Callbacks
        self._on_available_callbacks = []
        self._on_unavailable_callbacks = []

    def register_on_available(self, callback: Callable[[], None]):
        """Register callback for when market data service becomes available"""
        self._on_available_callbacks.append(callback)

    def register_on_unavailable(self, callback: Callable[[], None]):
        """Register callback for when market data service becomes unavailable"""
        self._on_unavailable_callbacks.append(callback)

    def _notify_available(self):
        """Notify all callbacks that service is available"""
        for callback in self._on_available_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in available callback: {e}")

    def _notify_unavailable(self):
        """Notify all callbacks that service is unavailable"""
        for callback in self._on_unavailable_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in unavailable callback: {e}")

    async def _check_port_open(self) -> bool:
        """Check if market data service port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            self.logger.debug(f"Port check failed: {e}")
            return False

    async def _check_grpc_health(self) -> bool:
        """Check if market data service gRPC is responding"""
        try:
            channel = grpc.aio.insecure_channel(f'{self.host}:{self.port}')
            stub = MarketDataServiceStub(channel)

            # Try to create a subscription (don't actually consume data)
            test_request = SubscriptionRequest(
                subscriber_id="health_check",
                include_history=False
            )

            # Set a short timeout for health checks
            try:
                stream = stub.SubscribeToMarketData(test_request)
                # Try to get the first message to confirm service is working
                async for _ in stream:
                    # Got a message, service is healthy
                    break
            except grpc.aio.AioRpcError as e:
                if e.code() in [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED]:
                    return False
                # Other errors might indicate service is up but has issues
                # For health checking purposes, consider it available
                self.logger.debug(f"Service responded with: {e.code()}")
                return True

            await channel.close()
            self.logger.debug("Market data service health check: SUCCESS")
            return True

        except asyncio.TimeoutError:
            self.logger.debug("Market data service health check timed out")
            return False
        except Exception as e:
            self.logger.debug(f"Market data service health check failed: {e}")
            return False

    async def _single_health_check(self) -> bool:
        """Perform a single comprehensive health check"""
        self.last_check_time = datetime.now()

        # First check if port is open (faster)
        if not await self._check_port_open():
            return False

        # Then check gRPC health
        return await self._check_grpc_health()

    async def _health_check_loop(self):
        """Main health check loop"""
        self.logger.info(f"🔍 Starting market data service health monitoring")
        self.logger.info(f"📍 Target: {self.host}:{self.port}")
        self.logger.info(f"⏱️  Check interval: {self.check_interval} seconds")

        while not self._stop_event.is_set():
            try:
                is_healthy = await self._single_health_check()

                # Handle state transitions
                if is_healthy and not self.is_available:
                    self.consecutive_successes += 1
                    self.consecutive_failures = 0

                    if self.consecutive_successes >= 2:
                        self.logger.info(f"✅ External market data service is now AVAILABLE")
                        self.is_available = True
                        self._notify_available()

                elif is_healthy and self.is_available:
                    self.consecutive_successes += 1
                    self.consecutive_failures = 0

                elif not is_healthy and self.is_available:
                    self.consecutive_failures += 1
                    self.consecutive_successes = 0

                    if self.consecutive_failures >= 3:
                        self.logger.warning(f"❌ External market data service is now UNAVAILABLE")
                        self.is_available = False
                        self._notify_unavailable()

                elif not is_healthy and not self.is_available:
                    self.consecutive_failures += 1
                    self.consecutive_successes = 0

                    if self.consecutive_failures % 5 == 0:
                        self.logger.info(
                            f"⏳ Still waiting for external market data service... ({self.consecutive_failures * self.check_interval}s)")

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.check_interval)

    def start(self):
        """Start health monitoring in background thread"""
        if self._health_thread and self._health_thread.is_alive():
            self.logger.warning("Health checker already running")
            return

        self._stop_event.clear()

        def run_health_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._health_check_loop())
            finally:
                loop.close()

        self._health_thread = Thread(target=run_health_check, daemon=True)
        self._health_thread.start()

        self.logger.info("🚀 External market data health checker started")

    def stop(self):
        """Stop health monitoring"""
        if self._stop_event:
            self._stop_event.set()

        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5.0)

        self.logger.info("🛑 Market data health checker stopped")

    def get_status(self) -> dict:
        """Get current health status"""
        return {
            'is_available': self.is_available,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'consecutive_failures': self.consecutive_failures,
            'consecutive_successes': self.consecutive_successes,
            'target_host': self.host,
            'target_port': self.port,
            'check_interval': self.check_interval
        }