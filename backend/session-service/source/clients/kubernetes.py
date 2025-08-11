# source/clients/kubernetes.py
"""
Simple Kubernetes client - just find pods by name.
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.rest import ApiException

from source.clients.base import BaseClient
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('kubernetes_client')


class KubernetesClient(BaseClient):
    """Simple Kubernetes client for finding pods by name"""

    def __init__(self):
        super().__init__(service_name="kubernetes_api")
        self.v1_api = None
        self._config_loaded = False

    async def _ensure_config(self):
        """Load Kubernetes config"""
        if not self._config_loaded:
            try:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except config.ConfigException:
                await config.load_kube_config()
                logger.info("Loaded kubeconfig")
            
            self.v1_api = client.CoreV1Api()
            self._config_loaded = True

    async def get_pod_endpoint(self, pod_name: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get pod IP and port for connection
        """
        with optional_trace_span(self.tracer, "k8s_get_pod_endpoint") as span:
            span.set_attribute("pod_name", pod_name)
            span.set_attribute("namespace", namespace)

            await self._ensure_config()
            
            try:
                pod = await self.v1_api.read_namespaced_pod(name=pod_name, namespace=namespace)
                
                if pod.status.phase != "Running":
                    logger.warning(f"Pod {pod_name} is not running (status: {pod.status.phase})")
                    return None
                
                # Use port 50060 (the API_PORT from the exchange service)
                grpc_port = 50060
                
                # Log all available ports for debugging
                all_ports = []
                if pod.spec.containers and pod.spec.containers[0].ports:
                    for port in pod.spec.containers[0].ports:
                        all_ports.append(f"{port.name}:{port.container_port}")
                        # Confirm 50060 is available
                        if port.container_port == 50060:
                            grpc_port = port.container_port
                            logger.info(f"Found gRPC port 50060 in pod spec")
                            
                logger.info(f"Pod {pod_name} has ports: {all_ports}, using gRPC port: {grpc_port}")

                result = {
                    'pod_name': pod.metadata.name,
                    'endpoint': f"{pod.status.pod_ip}:{grpc_port}",
                    'ip': pod.status.pod_ip,
                    'port': grpc_port,
                    'status': 'RUNNING'
                }
                
                logger.info(f"Final endpoint: {result['endpoint']}")
                return result
                
            except ApiException as e:
                if e.status == 404:
                    logger.warning(f"Pod {pod_name} not found")
                else:
                    logger.error(f"Error getting pod {pod_name}: {e}")
                return None
            

    async def close(self):
        """Close client"""
        if self.v1_api:
            await self.v1_api.api_client.close()