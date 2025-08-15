# orchestrator/kubernetes_manager.py
import logging
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from .templates import DeploymentTemplate, ServiceTemplate

logger = logging.getLogger(__name__)

class KubernetesManager:
    def __init__(self, namespace="default"):
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        self.k8s_apps = client.AppsV1Api()
        self.k8s_core = client.CoreV1Api()
        self.namespace = namespace
        
        # Templates
        self.deployment_template = DeploymentTemplate()
        self.service_template = ServiceTemplate()
        
        # Track running exchanges
        self.running_exchanges = set()
        
        logger.info(f"Kubernetes manager initialized for namespace: {namespace}")
    
    def _get_resource_name(self, exch_id: str) -> str:
        """Get standardized resource name for exchange"""
        return f"exchange-service-{exch_id.lower()}"
    
    async def start_exchange(self, exchange):
        """Start exchange deployment and service"""
        name = self._get_resource_name(exchange['exch_id'])
        
        try:
            # Create deployment
            deployment = self.deployment_template.create(exchange, name)
            await self._create_deployment(deployment)
            
            # Create service
            service = self.service_template.create(exchange, name)
            await self._create_service(service)
            
            self.running_exchanges.add(exchange['exch_id'])
            logger.info(f"Started exchange: {exchange['exchange_id']} ({name})")
            
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.error(f"Failed to start {exchange['exchange_id']}: {e}")
                raise
            else:
                # Already running, add to tracking
                self.running_exchanges.add(exchange['exch_id'])
    
    async def stop_exchange(self, exchange):
        """Stop exchange deployment and service"""
        name = self._get_resource_name(exchange['exch_id'])
        
        try:
            # Delete deployment
            await self._delete_deployment(name)
            
            # Delete service
            await self._delete_service(name)
            
            self.running_exchanges.discard(exchange['exch_id'])
            logger.info(f"Stopped exchange: {exchange['exchange_id']} ({name})")
            
        except Exception as e:
            if "not found" not in str(e).lower():
                logger.error(f"Failed to stop {exchange['exchange_id']}: {e}")
                raise
    
    async def check_exchange_health(self, exchange):
        """Check health of a specific exchange pod"""
        name = self._get_resource_name(exchange['exch_id'])
        exchange_id = exchange['exchange_id']
        
        try:
            # Check deployment status
            deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)
            
            # Check if deployment is ready
            replicas = deployment.spec.replicas or 0
            ready_replicas = deployment.status.ready_replicas or 0
            unavailable_replicas = deployment.status.unavailable_replicas or 0
            
            if ready_replicas < replicas:
                logger.error(f"HEALTH CHECK FAILED: {exchange_id} - {ready_replicas}/{replicas} replicas ready")
                return False
            
            if unavailable_replicas > 0:
                logger.error(f"HEALTH CHECK FAILED: {exchange_id} - {unavailable_replicas} replicas unavailable")
                return False
            
            # Check pod status
            pods = self.k8s_core.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app={name}"
            )
            
            for pod in pods.items:
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase
                
                if pod_phase != "Running":
                    logger.error(f"HEALTH CHECK FAILED: {exchange_id} pod {pod_name} in phase: {pod_phase}")
                    return False
                
                # Check container statuses
                if pod.status.container_statuses:
                    for container in pod.status.container_statuses:
                        if not container.ready:
                            logger.error(f"HEALTH CHECK FAILED: {exchange_id} pod {pod_name} container {container.name} not ready")
                            return False
                        
                        if container.restart_count > 0:
                            logger.warning(f"HEALTH CHECK WARNING: {exchange_id} pod {pod_name} container {container.name} has {container.restart_count} restarts")
            
            # If we get here, everything is healthy
            logger.debug(f"HEALTH CHECK PASSED: {exchange_id} is healthy")
            return True
            
        except ApiException as e:
            if e.status == 404:
                logger.error(f"HEALTH CHECK FAILED: {exchange_id} deployment not found")
                return False
            else:
                logger.error(f"HEALTH CHECK ERROR: {exchange_id} - {e}")
                return False
        except Exception as e:
            logger.error(f"HEALTH CHECK ERROR: {exchange_id} - {e}")
            return False
    
    async def check_all_running_exchanges_health(self):
        """Check health of all running exchanges"""
        if not self.running_exchanges:
            logger.debug("No running exchanges to check")
            return
        
        logger.debug(f"Checking health of {len(self.running_exchanges)} running exchanges")
        
        healthy_count = 0
        unhealthy_count = 0
        
        # We need the exchange data to check health, so this method should be called
        # from scheduler with exchange data, or we need to modify this approach
        for exch_id in list(self.running_exchanges):  # Use list() to avoid modification during iteration
            # Note: This is a simplified version. In practice, we'd need exchange metadata
            # to properly check health. This should be called from the scheduler.
            try:
                # Check if deployment exists
                name = self._get_resource_name(exch_id)
                deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)
                
                ready_replicas = deployment.status.ready_replicas or 0
                if ready_replicas > 0:
                    healthy_count += 1
                    logger.debug(f"Exchange {exch_id} is healthy")
                else:
                    unhealthy_count += 1
                    logger.error(f"HEALTH CHECK FAILED: Exchange {exch_id} has no ready replicas")
                    
            except ApiException as e:
                if e.status == 404:
                    # Exchange pod doesn't exist but we think it's running
                    logger.error(f"HEALTH CHECK FAILED: Exchange {exch_id} deployment not found but marked as running")
                    self.running_exchanges.discard(exch_id)  # Remove from tracking
                    unhealthy_count += 1
                else:
                    logger.error(f"HEALTH CHECK ERROR: Exchange {exch_id} - {e}")
                    unhealthy_count += 1
        
        if unhealthy_count > 0:
            logger.warning(f"Health check summary: {healthy_count} healthy, {unhealthy_count} unhealthy exchanges")
        else:
            logger.info(f"Health check summary: All {healthy_count} exchanges are healthy")
    
    async def is_exchange_running(self, exch_id: str) -> bool:
        """Check if exchange is currently running"""
        name = self._get_resource_name(exch_id)
        
        try:
            deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)
            return (deployment.status.ready_replicas and 
                   deployment.status.ready_replicas > 0)
        except ApiException as e:
            if e.status == 404:
                return False
            raise
    
    async def _create_deployment(self, deployment):
        """Create Kubernetes deployment"""
        self.k8s_apps.create_namespaced_deployment(
            namespace=self.namespace,
            body=deployment
        )
    
    async def _create_service(self, service):
        """Create Kubernetes service"""
        self.k8s_core.create_namespaced_service(
            namespace=self.namespace,
            body=service
        )
    
    async def _delete_deployment(self, name):
        """Delete Kubernetes deployment"""
        self.k8s_apps.delete_namespaced_deployment(
            name=name,
            namespace=self.namespace
        )
    
    async def _delete_service(self, name):
        """Delete Kubernetes service"""
        self.k8s_core.delete_namespaced_service(
            name=name,
            namespace=self.namespace
        )
    
    def get_running_exchanges(self):
        """Get set of currently running exchange IDs"""
        return self.running_exchanges.copy()