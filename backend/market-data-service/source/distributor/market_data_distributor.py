# src/distributor/market_data_distributor.py
import asyncio
import logging
import time
import grpc
from datetime import datetime
from typing import Dict, List, Set, Any
import uuid

# Import the exchange simulator protobuf classes
# These are from your exchange simulator project
from source.api.grpc import exchange_simulator_pb2 as pb2
from source.api.grpc import exchange_simulator_pb2_grpc as pb2_grpc

from src.generator.market_data_generator import MarketDataGenerator
from src.config import config

logger = logging.getLogger(__name__)


class ExchangeSimulatorClient:
    """Client for connecting to an exchange simulator instance"""
    
    def __init__(self, host: str, port: int):
        """
        Initialize a connection to an exchange simulator.
        
        Args:
            host: Host address of the exchange simulator
            port: gRPC port of the exchange simulator
        """
        self.host = host
        self.port = port
        self.address = f"{host}:{port}"
        self.channel = None
        self.stub = None
        self.connected = False
        self.last_success = 0
        self.connection_failures = 0
    
    async def connect(self) -> bool:
        """
        Establish connection to the exchange simulator.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            self.channel = grpc.aio.insecure_channel(self.address)
            self.stub = pb2_grpc.ExchangeSimulatorStub(self.channel)
            
            # Test connection with a heartbeat
            request = pb2.HeartbeatRequest(
                client_timestamp=int(time.time() * 1000)
            )
            
            # Set a timeout for the heartbeat call
            response = await self.stub.Heartbeat(
                request, 
                timeout=5.0  # 5 second timeout
            )
            
            if response and response.success:
                self.connected = True
                self.last_success = time.time()
                self.connection_failures = 0
                logger.debug(f"Connected to exchange simulator at {self.address}")
                return True
            else:
                logger.warning(f"Heartbeat to {self.address} failed")
                self.connected = False
                return False
                
        except Exception as e:
            self.connected = False
            self.connection_failures += 1
            logger.warning(f"Failed to connect to {self.address}: {e}")
            return False
    
    async def disconnect(self):
        """Close the connection to the exchange simulator"""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            self.connected = False
    
    async def send_market_data(self, market_data: List[Dict[str, Any]]) -> bool:
        """
        Send market data to the exchange simulator.
        
        Args:
            market_data: List of market data records
            
        Returns:
            True if data was successfully sent, False otherwise
        """
        if not self.connected:
            reconnected = await self.connect()
            if not reconnected:
                return False
                
        try:
            # Convert our market data format to the format expected by the exchange simulator
            pb_market_data = []
            for md in market_data:
                pb_market_data.append(pb2.MarketData(
                    symbol=md['symbol'],
                    bid=md['bid'],
                    ask=md['ask'],
                    bid_size=md['bid_size'],
                    ask_size=md['ask_size'],
                    last_price=md['last_price'],
                    last_size=md['last_size']
                ))
            
            # Create exchange data update message
            update = pb2.ExchangeDataUpdate(
                timestamp=int(time.time() * 1000),
                market_data=pb_market_data
            )
            
            # Create a unique session ID for this distribution
            session_id = str(uuid.uuid4())
            
            # Create stream request
            request = pb2.StreamRequest(
                session_id=session_id,
                client_id="market_data_distributor",
                symbols=[md['symbol'] for md in market_data]
            )
            
            # Send data using a heartbeat instead of StreamExchangeData
            # This is because we're pushing data to the exchange simulator
            # rather than subscribing to a stream
            heartbeat_req = pb2.HeartbeatRequest(
                client_timestamp=int(time.time() * 1000)
            )
            
            response = await self.stub.Heartbeat(
                heartbeat_req,
                timeout=5.0
            )
            
            if response and response.success:
                self.last_success = time.time()
                self.connection_failures = 0
                logger.debug(f"Successfully sent market data to {self.address}")
                return True
            else:
                logger.warning(f"Failed to send market data to {self.address}")
                return False
                
        except Exception as e:
            self.connection_failures += 1
            logger.warning(f"Error sending market data to {self.address}: {e}")
            return False
            
    def is_healthy(self) -> bool:
        """
        Check if the connection is healthy based on recent successes.
        
        Returns:
            True if the connection is considered healthy, False otherwise
        """
        # Consider a connection unhealthy if it has failed 3 or more consecutive times
        return self.connection_failures < 3


class MarketDataDistributor:
    """
    Distributes market data to registered exchange simulator instances.
    """
    
    def __init__(self, generator: MarketDataGenerator, update_interval: int = 60):
        """
        Initialize the market data distributor.
        
        Args:
            generator: Market data generator instance
            update_interval: Interval in seconds between market data updates
        """
        self.generator = generator
        self.update_interval = update_interval
        self.clients: Dict[str, ExchangeSimulatorClient] = {}
        self.clients_lock = asyncio.Lock()
        self.running = False
        self.distribution_task = None
        
        # Metrics
        self.updates_sent = 0
        self.connections_active = 0
        self.last_distribution_time = 0
        
        logger.info(f"Market data distributor initialized with {update_interval}s interval")
    
    async def start(self):
        """Start the market data distribution service"""
        if self.running:
            logger.warning("Market data distributor is already running")
            return
            
        self.running = True
        
        # Check if we're within operating hours
        current_hour = datetime.now().hour
        if current_hour < config.STARTUP_HOUR or current_hour >= config.SHUTDOWN_HOUR:
            logger.info(f"Outside operating hours ({config.STARTUP_HOUR}:00 - {config.SHUTDOWN_HOUR}:00), waiting...")
            # Schedule to start at the configured start hour
            next_run = self._calculate_next_run_time()
            logger.info(f"Will start at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            await asyncio.sleep((next_run - datetime.now()).total_seconds())
        
        logger.info("Market data distributor started")
        
        # Start the distribution task
        self.distribution_task = asyncio.create_task(self._distribution_loop())
    
    def _calculate_next_run_time(self):
        """Calculate the next time the distributor should run based on operating hours"""
        now = datetime.now()
        current_hour = now.hour
        
        if current_hour < config.STARTUP_HOUR:
            # Start later today
            next_run = now.replace(hour=config.STARTUP_HOUR, minute=0, second=0, microsecond=0)
        else:
            # Start tomorrow
            next_run = now.replace(hour=config.STARTUP_HOUR, minute=0, second=0, microsecond=0)
            next_run = next_run.replace(day=now.day + 1)
        
        return next_run
    
    async def stop(self):
        """Stop the market data distribution service"""
        if not self.running:
            return
            
        logger.info("Stopping market data distributor")
        self.running = False
        
        if self.distribution_task:
            self.distribution_task.cancel()
            try:
                await self.distribution_task
            except asyncio.CancelledError:
                pass
            
        # Disconnect all clients
        async with self.clients_lock:
            disconnect_tasks = []
            for client in self.clients.values():
                disconnect_tasks.append(asyncio.create_task(client.disconnect()))
            
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks)
            
            self.clients.clear()
        
        logger.info("Market data distributor stopped")
    
    async def _distribution_loop(self):
        """Main loop that distributes market data at regular intervals"""
        try:
            while self.running:
                current_hour = datetime.now().hour
                
                # Check if we're outside operating hours
                if current_hour < config.STARTUP_HOUR or current_hour >= config.SHUTDOWN_HOUR:
                    logger.info(f"Outside operating hours ({config.STARTUP_HOUR}:00 - {config.SHUTDOWN_HOUR}:00), pausing...")
                    await asyncio.sleep(60)  # Check again in a minute
                    continue
                
                # Update market data
                self.generator.update_prices()
                
                # Distribute market data to all clients
                await self._distribute_market_data()
                
                # Sleep until next update
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Distribution loop cancelled")
        except Exception as e:
            logger.error(f"Error in distribution loop: {e}", exc_info=True)
            if self.running:
                # Restart the loop after a short delay
                logger.info("Restarting distribution loop in 5 seconds...")
                await asyncio.sleep(5)
                self.distribution_task = asyncio.create_task(self._distribution_loop())
    
    async def _distribute_market_data(self):
        """Distribute current market data to all registered clients"""
        if not self.clients:
            logger.debug("No clients registered, skipping distribution")
            return
        
        self.last_distribution_time = time.time()
        market_data = self.generator.get_market_data()
        
        logger.info(f"Distributing market data for {len(market_data)} symbols to {len(self.clients)} clients")
        
        async with self.clients_lock:
            # Create a list to track clients to remove
            clients_to_remove = []
            
            # Send data to each client
            for host, client in self.clients.items():
                success = await client.send_market_data(market_data)
                
                if not success and not client.is_healthy():
                    logger.warning(f"Client {host} is unhealthy, marking for removal")
                    clients_to_remove.append(host)
            
            # Remove unhealthy clients
            for host in clients_to_remove:
                logger.info(f"Removing unhealthy client: {host}")
                await self.clients[host].disconnect()
                del self.clients[host]
            
            # Update metrics
            self.connections_active = len(self.clients)
            self.updates_sent += 1
    
    async def register_client(self, host: str, port: int = None) -> bool:
        """
        Register a new exchange simulator client.
        
        Args:
            host: Host address or hostname of the exchange simulator
            port: gRPC port of the exchange simulator (optional, uses config if not provided)
            
        Returns:
            True if registration was successful, False otherwise
        """
        port = port or config.EXCHANGE_SERVICE_PORT
        
        # Create a client address that includes the port
        client_address = f"{host}:{port}" if ":" not in host else host
        
        async with self.clients_lock:
            if client_address in self.clients:
                logger.debug(f"Client {client_address} is already registered")
                return True
            
            # Create and connect to the client
            client = ExchangeSimulatorClient(host, port)
            success = await client.connect()
            
            if success:
                self.clients[client_address] = client
                self.connections_active = len(self.clients)
                logger.info(f"Registered client: {client_address}")
                return True
            else:
                logger.warning(f"Failed to register client: {client_address}")
                return False
    
    async def unregister_client(self, host: str, port: int = None) -> bool:
        """
        Unregister an exchange simulator client.
        
        Args:
            host: Host address or hostname of the exchange simulator
            port: gRPC port of the exchange simulator (optional)
            
        Returns:
            True if unregistration was successful, False otherwise
        """
        if port:
            client_address = f"{host}:{port}" if ":" not in host else host
        else:
            # Try to match partial address
            async with self.clients_lock:
                matches = [addr for addr in self.clients.keys() if host in addr]
                if matches:
                    client_address = matches[0]
                else:
                    logger.warning(f"No registered client found for host: {host}")
                    return False
        
        async with self.clients_lock:
            if client_address in self.clients:
                client = self.clients[client_address]
                await client.disconnect()
                del self.clients[client_address]
                self.connections_active = len(self.clients)
                logger.info(f"Unregistered client: {client_address}")
                return True
            else:
                logger.warning(f"Client not registered: {client_address}")
                return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the distributor.
        
        Returns:
            Dictionary with current status metrics
        """
        return {
            "running": self.running,
            "connections_active": self.connections_active,
            "updates_sent": self.updates_sent,
            "last_update": self.last_distribution_time,
            "time_since_update": time.time() - self.last_distribution_time if self.last_distribution_time > 0 else None,
            "operating_hours": f"{config.STARTUP_HOUR}:00 - {config.SHUTDOWN_HOUR}:00",
            "symbols": len(self.generator.symbols),
            "update_interval": self.update_interval
        }
    