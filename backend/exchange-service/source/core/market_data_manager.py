# source/core/market_data_handler.py
import logging
import asyncio
import aiohttp
import socket
import time
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger('market_data_handler')


class MarketDataHandler:
    """
    Handles receiving market data from the distributor
    and registering with the distributor service.
    """
    
    def __init__(self, exchange_manager):
        """
        Initialize the market data handler.
        
        Args:
            exchange_manager: Reference to the exchange manager
        """
        self.exchange_manager = exchange_manager
        self.distributor_url = os.getenv(
            'MARKET_DATA_DISTRIBUTOR_URL', 
            'http://market-data-distributor:50060'
        )
        self.registered = False
        self.registration_task = None
        self.symbols = self.exchange_manager.default_symbols
        
        # Get hostname and namespace for registration
        self.hostname = socket.gethostname()
        self.namespace = os.getenv('POD_NAMESPACE', 'default')
        self.service_name = os.getenv('SERVICE_NAME', 'exchange-simulator')
        self.grpc_port = int(os.getenv('GRPC_PORT', '50055'))
        
        # Construct fully qualified domain name for this pod
        self.fqdn = f"{self.hostname}.{self.service_name}.{self.namespace}.svc.cluster.local"
        
        logger.info(f"Market data handler initialized with distributor: {self.distributor_url}")
    
    async def start(self):
        """Start the market data handler"""
        # Start a background task to register with the distributor
        self.registration_task = asyncio.create_task(self._registration_loop())
        logger.info("Market data handler started")
    
    async def stop(self):
        """Stop the market data handler"""
        if self.registration_task:
            self.registration_task.cancel()
            try:
                await self.registration_task
            except asyncio.CancelledError:
                pass
        
        # Unregister from the distributor
        if self.registered:
            await self._unregister()
        
        logger.info("Market data handler stopped")
    
    async def _registration_loop(self):
        """
        Background task that periodically registers with the distributor
        to ensure continued reception of market data.
        """
        try:
            while True:
                if not self.registered:
                    registered = await self._register()
                    if registered:
                        self.registered = True
                        logger.info("Successfully registered with market data distributor")
                    else:
                        logger.warning("Failed to register with market data distributor, will retry")
                
                # Re-register every 5 minutes to ensure we're still known to the distributor
                await asyncio.sleep(300)  # 5 minutes
                
                # Ping the distributor to check if we're still registered
                health_check = await self._check_distributor_health()
                if not health_check:
                    self.registered = False
                    logger.warning("Lost connection to market data distributor, will re-register")
                    
        except asyncio.CancelledError:
            logger.info("Registration loop cancelled")
        except Exception as e:
            logger.error(f"Error in registration loop: {e}", exc_info=True)
            self.registered = False
            # Restart the loop after a delay
            await asyncio.sleep(10)
            self.registration_task = asyncio.create_task(self._registration_loop())
    
    async def _register(self) -> bool:
        """
        Register this exchange simulator with the market data distributor.
        
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.distributor_url}/register",
                    json={
                        "host": self.fqdn,
                        "port": self.grpc_port
                    },
                    timeout=5.0
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Registered with market data distributor: {data}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Failed to register with distributor: {error}")
                        return False
        except Exception as e:
            logger.error(f"Error registering with distributor: {e}")
            return False
    
    async def _unregister(self) -> bool:
        """
        Unregister this exchange simulator from the market data distributor.
        
        Returns:
            True if unregistration was successful, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.distributor_url}/unregister",
                    json={"host": self.fqdn},
                    timeout=5.0
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Unregistered from market data distributor: {data}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Failed to unregister from distributor: {error}")
                        return False
        except Exception as e:
            logger.error(f"Error unregistering from distributor: {e}")
            return False
    
    async def _check_distributor_health(self) -> bool:
        """
        Check if the market data distributor is healthy.
        
        Returns:
            True if the distributor is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.distributor_url}/health",
                    timeout=5.0
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        return False
        except Exception:
            return False
    
    def process_market_data(self, market_data: List[Dict[str, Any]]):
        """
        Process market data received from the distributor.
        
        Args:
            market_data: List of market data records
        """
        try:
            # Update the market data in the exchange manager
            self.exchange_manager.market_data_generator.update_from_external(market_data)
            logger.debug(f"Processed market data for {len(market_data)} symbols")
        except Exception as e:
            logger.error(f"Error processing market data: {e}")