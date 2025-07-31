# source/orchestration/coordination/exchange_registry.py
"""
Exchange Registry - Updates existing exchange records with Kubernetes metadata
"""

import os
import logging
import socket
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from source.db.db_manager import db_manager
from source.config import app_config


@dataclass
class KubernetesMetadata:
    """Kubernetes pod metadata for service discovery"""
    pod_name: str
    namespace: str
    endpoint: str
    node_name: Optional[str] = None
    cluster_name: Optional[str] = None


@dataclass
class ExchangeRegistration:
    """Exchange service registration data"""
    exch_id: str
    exchange_type: str
    kubernetes_metadata: KubernetesMetadata


class ExchangeRegistry:
    """
    Updates existing exchange records with Kubernetes metadata for service discovery.
    
    This class:
    1. Reads exch_id and exchange_type from environment variables
    2. Gathers Kubernetes pod metadata  
    3. Updates ONLY the Kubernetes fields in the existing database record
    4. Does NOT create new exchange records (those must be pre-created)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def get_kubernetes_metadata(self) -> KubernetesMetadata:
        """
        Extract Kubernetes metadata from environment variables.
        
        Kubernetes automatically injects these environment variables:
        - HOSTNAME: Pod name
        - POD_NAMESPACE: Namespace (if configured in deployment)
        - NODE_NAME: Node name (if configured)
        
        Returns:
            KubernetesMetadata: Pod metadata for service registration
        """
        try:
            # Get pod name from HOSTNAME (Kubernetes sets this automatically)
            pod_name = os.environ.get('HOSTNAME', socket.gethostname())
            
            # Get namespace from environment (must be set in K8s deployment)
            namespace = os.environ.get('POD_NAMESPACE', 'default')
            
            # Get service endpoint - construct from environment or defaults
            service_name = os.environ.get('SERVICE_NAME', pod_name)
            service_port = os.environ.get('GRPC_SERVICE_PORT', '50055')
            
            # Construct endpoint for service discovery
            # In Kubernetes, services are accessible via: service-name.namespace.svc.cluster.local
            if namespace != 'default':
                endpoint = f"{service_name}.{namespace}.svc.cluster.local:{service_port}"
            else:
                endpoint = f"{service_name}:{service_port}"
            
            # Optional metadata
            node_name = os.environ.get('NODE_NAME')
            cluster_name = os.environ.get('CLUSTER_NAME')
            
            metadata = KubernetesMetadata(
                pod_name=pod_name,
                namespace=namespace,
                endpoint=endpoint,
                node_name=node_name,
                cluster_name=cluster_name
            )
            
            self.logger.info(f"📍 Kubernetes Metadata Collected:")
            self.logger.info(f"   - Pod Name: {metadata.pod_name}")
            self.logger.info(f"   - Namespace: {metadata.namespace}")
            self.logger.info(f"   - Endpoint: {metadata.endpoint}")
            self.logger.info(f"   - Node: {metadata.node_name or 'unknown'}")
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"❌ Failed to collect Kubernetes metadata: {e}")
            raise
    
    def get_exchange_configuration(self) -> tuple[str, str]:
        """
        Get exchange configuration from environment variables.
        
        Required environment variables:
        - EXCH_ID: Unique exchange identifier (UUID format)
        - EXCHANGE_TYPE: Type of exchange (default: 'EXCH_US_EQUITIES')
        
        Returns:
            tuple: (exch_id, exchange_type)
            
        Raises:
            ValueError: If required environment variables are missing
        """
        exch_id = os.environ.get('EXCH_ID')
        if not exch_id:
            raise ValueError("EXCH_ID environment variable is required")
        
        # Validate UUID format
        try:
            uuid.UUID(exch_id)
        except ValueError:
            raise ValueError(f"EXCH_ID must be a valid UUID format, got: {exch_id}")
        
        exchange_type = os.environ.get('EXCHANGE_TYPE', 'EXCH_US_EQUITIES')
        
        self.logger.info(f"🏦 Exchange Configuration:")
        self.logger.info(f"   - Exchange ID: {exch_id}")
        self.logger.info(f"   - Exchange Type: {exchange_type}")
        
        return exch_id, exchange_type
    
    async def update_kubernetes_metadata(self) -> ExchangeRegistration:
        """
        Update existing exchange record with Kubernetes metadata for service discovery.
        
        This method:
        1. Gets exch_id and exchange_type from environment variables
        2. Collects Kubernetes pod metadata
        3. Verifies the exchange record exists in the database
        4. Updates ONLY the Kubernetes metadata fields (endpoint, pod_name, namespace)
        5. Does NOT modify exchange business logic fields
        
        Returns:
            ExchangeRegistration: Updated registration data
            
        Raises:
            ValueError: If exchange record doesn't exist
            Exception: If update fails
        """
        try:
            self.logger.info("=" * 80)
            self.logger.info("🔧 UPDATING EXCHANGE KUBERNETES METADATA")
            self.logger.info("=" * 80)
            
            # Step 1: Get exchange configuration from environment
            exch_id, exchange_type = self.get_exchange_configuration()
            
            # Step 2: Get Kubernetes metadata
            kubernetes_metadata = self.get_kubernetes_metadata()
            
            # Step 3: Verify exchange record exists and get current data
            existing_record = await self._get_existing_exchange_record(exch_id, exchange_type)
            
            # Step 4: Update only Kubernetes metadata fields
            await self._update_kubernetes_fields_only(exch_id, kubernetes_metadata)
            
            # Step 5: Create registration object
            registration = ExchangeRegistration(
                exch_id=exch_id,
                exchange_type=exchange_type,
                kubernetes_metadata=kubernetes_metadata
            )
            
            self.logger.info("=" * 80)
            self.logger.info("✅ KUBERNETES METADATA UPDATE COMPLETE")
            self.logger.info("=" * 80)
            self.logger.info(f"🆔 Exchange ID: {exch_id}")
            self.logger.info(f"🏷️  Exchange Type: {exchange_type}")
            self.logger.info(f"📍 Updated Endpoint: {kubernetes_metadata.endpoint}")
            self.logger.info(f"🚀 Updated Pod: {kubernetes_metadata.pod_name}")
            self.logger.info(f"🏢 Updated Namespace: {kubernetes_metadata.namespace}")
            self.logger.info("=" * 80)
            
            return registration
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update Kubernetes metadata: {e}")
            raise
    
    async def _get_existing_exchange_record(self, exch_id: str, exchange_type: str) -> Dict[str, Any]:
        """
        Verify that the exchange record exists and get its current data.
        
        Args:
            exch_id: Exchange ID to verify
            exchange_type: Expected exchange type
            
        Returns:
            Dict: Existing exchange record data
            
        Raises:
            ValueError: If record doesn't exist or exchange_type doesn't match
        """
        try:
            await db_manager.initialize()
            
            async with db_manager.pool.acquire() as conn:
                query = """
                    SELECT exch_id, exchange_type, timezone, exchanges,
                           last_snap, pre_market_open, market_open, market_close, 
                           post_market_close, endpoint, pod_name, namespace, updated_time
                    FROM exch_us_equity.metadata 
                    WHERE exch_id = $1
                """
                
                record = await conn.fetchrow(query, exch_id)
                
                if not record:
                    raise ValueError(
                        f"Exchange record not found for exch_id: {exch_id}. "
                        f"Exchange records must be pre-created before starting the service."
                    )
                
                # Verify exchange type matches
                if record['exchange_type'] != exchange_type:
                    raise ValueError(
                        f"Exchange type mismatch for exch_id {exch_id}. "
                        f"Expected: {exchange_type}, Found: {record['exchange_type']}"
                    )
                
                self.logger.info(f"✅ Found existing exchange record:")
                self.logger.info(f"   - Exchange ID: {record['exch_id']}")
                self.logger.info(f"   - Exchange Type: {record['exchange_type']}")
                self.logger.info(f"   - Last Snap: {record['last_snap']}")
                self.logger.info(f"   - Current Endpoint: {record['endpoint'] or 'None'}")
                self.logger.info(f"   - Current Pod: {record['pod_name'] or 'None'}")
                
                return dict(record)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get existing exchange record: {e}")
            raise
    
    async def _update_kubernetes_fields_only(self, exch_id: str, kubernetes_metadata: KubernetesMetadata):
        """
        Update ONLY the Kubernetes metadata fields, preserving all exchange business logic.
        
        Updates only:
        - endpoint
        - pod_name  
        - namespace
        - updated_time
        
        Does NOT modify:
        - exchange_type, timezone, exchanges
        - last_snap, market hours (pre_market_open, market_open, etc.)
        """
        try:
            await db_manager.initialize()
            
            async with db_manager.pool.acquire() as conn:
                query = """
                    UPDATE exch_us_equity.metadata 
                    SET 
                        endpoint = $2,
                        pod_name = $3,
                        namespace = $4,
                        updated_time = CURRENT_TIMESTAMP
                    WHERE exch_id = $1
                    RETURNING exch_id, endpoint, pod_name, namespace, updated_time;
                """
                
                result = await conn.fetchrow(
                    query,
                    exch_id,  # $1
                    kubernetes_metadata.endpoint,  # $2
                    kubernetes_metadata.pod_name,  # $3
                    kubernetes_metadata.namespace  # $4
                )
                
                if result:
                    self.logger.info(f"✅ Kubernetes metadata updated successfully:")
                    self.logger.info(f"   - Exchange ID: {result['exch_id']}")
                    self.logger.info(f"   - New Endpoint: {result['endpoint']}")
                    self.logger.info(f"   - New Pod Name: {result['pod_name']}")
                    self.logger.info(f"   - New Namespace: {result['namespace']}")
                    self.logger.info(f"   - Updated At: {result['updated_time']}")
                else:
                    raise RuntimeError("Database update returned no result")
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to update Kubernetes fields: {e}")
            raise

    async def clear_kubernetes_metadata(self, exch_id: str):
        """
        Clear Kubernetes metadata during graceful shutdown.
        
        This marks the exchange service as offline by clearing the Kubernetes fields
        while preserving all exchange business logic data.
        """
        try:
            self.logger.info(f"🧹 Clearing Kubernetes metadata for exchange: {exch_id}")
            
            await db_manager.initialize()
            
            async with db_manager.pool.acquire() as conn:
                query = """
                    UPDATE exch_us_equity.metadata 
                    SET 
                        endpoint = NULL,
                        pod_name = NULL,
                        namespace = NULL,
                        updated_time = CURRENT_TIMESTAMP
                    WHERE exch_id = $1
                    RETURNING exch_id, updated_time;
                """
                
                result = await conn.fetchrow(query, exch_id)
                
                if result:
                    self.logger.info(f"✅ Kubernetes metadata cleared: {result['exch_id']} at {result['updated_time']}")
                else:
                    self.logger.warning(f"⚠️ No record found to clear: {exch_id}")
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to clear Kubernetes metadata: {e}")
            # Don't re-raise during shutdown - this is cleanup


# Global registry instance
exchange_registry = ExchangeRegistry()