# kubernetes_manager.py
import logging
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from templates import DeploymentTemplate, ServiceTemplate

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
    
    def _get_resource_name(self, exch_id) -> str:
        """Get standardized resource name for exchange"""
        # Convert UUID to string and make it lowercase
        exch_id_str = str(exch_id).lower()
        # Replace hyphens with dashes to make it valid for Kubernetes resource names
        return f"exchange-service-{exch_id_str}"
    
    async def start_exchange(self, exchange):
        """Start exchange deployment and service"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        
        logger.info(f"Starting exchange with exch_id: {exch_id} (type: {type(exch_id)})")
        logger.info(f"Generated resource name: {name}")
        
        try:
            # Create deployment
            deployment = self.deployment_template.create(exchange, name)
            await self._create_deployment(deployment)
            
            # Create service
            service = self.service_template.create(exchange, name)
            await self._create_service(service)
            
            # Use string representation for tracking
            self.running_exchanges.add(str(exch_id))
            logger.info(f"Started exchange: {exchange.get('exchange_name', 'Unknown')} ({name})")
            
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.error(f"Failed to start {exchange.get('exchange_name', 'Unknown')}: {e}")
                raise
            else:
                # Already running, add to tracking
                self.running_exchanges.add(str(exch_id))
                logger.info(f"Exchange {exchange.get('exchange_name', 'Unknown')} already running")
    
    async def stop_exchange(self, exchange):
        """Stop exchange deployment and service"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        
        try:
            # Delete deployment
            await self._delete_deployment(name)
            
            # Delete service
            await self._delete_service(name)
            
            self.running_exchanges.discard(str(exch_id))
            logger.info(f"Stopped exchange: {exchange.get('exchange_name', 'Unknown')} ({name})")
            
        except Exception as e:
            if "not found" not in str(e).lower():
                logger.error(f"Failed to stop {exchange.get('exchange_name', 'Unknown')}: {e}")
                raise
    
    async def check_exchange_health(self, exchange):
        """Check health of a specific exchange pod"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        exchange_name = exchange.get('exchange_name', 'Unknown')
        
        try:
            # Check deployment status
            deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)
            
            # Check if deployment is ready
            replicas = deployment.spec.replicas or 0
            ready_replicas = deployment.status.ready_replicas or 0
            unavailable_replicas = deployment.status.unavailable_replicas or 0
            
            if ready_replicas < replicas:
                logger.error(f"HEALTH CHECK FAILED: {exchange_name} - {ready_replicas}/{replicas} replicas ready")
                return False
            
            if unavailable_replicas > 0:
                logger.error(f"HEALTH CHECK FAILED: {exchange_name} - {unavailable_replicas} replicas unavailable")
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
                    logger.error(f"HEALTH CHECK FAILED: {exchange_name} pod {pod_name} in phase: {pod_phase}")
                    return False
                
                # Check container statuses
                if pod.status.container_statuses:
                    for container in pod.status.container_statuses:
                        if not container.ready:
                            logger.error(f"HEALTH CHECK FAILED: {exchange_name} pod {pod_name} container {container.name} not ready")
                            return False
                        
                        if container.restart_count > 0:
                            logger.warning(f"HEALTH CHECK WARNING: {exchange_name} pod {pod_name} container {container.name} has {container.restart_count} restarts")
            
            # If we get here, everything is healthy
            logger.debug(f"HEALTH CHECK PASSED: {exchange_name} is healthy")
            return True
            
        except ApiException as e:
            if e.status == 404:
                logger.error(f"HEALTH CHECK FAILED: {exchange_name} deployment not found")
                return False
            else:
                logger.error(f"HEALTH CHECK ERROR: {exchange_name} - {e}")
                return False
        except Exception as e:
            logger.error(f"HEALTH CHECK ERROR: {exchange_name} - {e}")
            return False
    
    async def check_all_running_exchanges_health(self):
        """Check health of all running exchanges"""
        if not self.running_exchanges:
            logger.debug("No running exchanges to check")
            return
        
        logger.debug(f"Checking health of {len(self.running_exchanges)} running exchanges")
        
        healthy_count = 0
        unhealthy_count = 0
        
        for exch_id_str in list(self.running_exchanges):  # Use list() to avoid modification during iteration
            try:
                # Check if deployment exists
                name = self._get_resource_name(exch_id_str)
                deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)
                
                ready_replicas = deployment.status.ready_replicas or 0
                if ready_replicas > 0:
                    healthy_count += 1
                    logger.debug(f"Exchange {exch_id_str} is healthy")
                else:
                    unhealthy_count += 1
                    logger.error(f"HEALTH CHECK FAILED: Exchange {exch_id_str} has no ready replicas")
                    
            except ApiException as e:
                if e.status == 404:
                    # Exchange pod doesn't exist but we think it's running
                    logger.error(f"HEALTH CHECK FAILED: Exchange {exch_id_str} deployment not found but marked as running")
                    self.running_exchanges.discard(exch_id_str)  # Remove from tracking
                    unhealthy_count += 1
                else:
                    logger.error(f"HEALTH CHECK ERROR: Exchange {exch_id_str} - {e}")
                    unhealthy_count += 1
        
        if unhealthy_count > 0:
            logger.warning(f"Health check summary: {healthy_count} healthy, {unhealthy_count} unhealthy exchanges")
        else:
            logger.info(f"Health check summary: All {healthy_count} exchanges are healthy")
    
    async def is_exchange_running(self, exch_id) -> bool:
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