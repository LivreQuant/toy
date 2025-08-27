# kubernetes_manager.py
import logging
import yaml
import json
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

    def _dump_yaml_to_logs(self, resource_type: str, resource_dict: dict, exchange_name: str = ""):
        """Dump generated YAML to logs for debugging"""
        try:
            yaml_output = yaml.dump(resource_dict, default_flow_style=False, indent=2)

            logger.info(f"📄 Generated {resource_type} YAML for {exchange_name}:")
            logger.info("=" * 80)
            # Split the YAML into lines and log each line to avoid truncation
            for line in yaml_output.split('\n'):
                logger.info(line)
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Failed to dump {resource_type} YAML to logs: {e}")
            # Fallback to JSON if YAML fails
            try:
                json_output = json.dumps(resource_dict, indent=2, default=str)
                logger.info(f"📄 Generated {resource_type} JSON for {exchange_name}:")
                logger.info("=" * 80)
                for line in json_output.split('\n'):
                    logger.info(line)
                logger.info("=" * 80)
            except Exception as json_e:
                logger.error(f"❌ Failed to dump {resource_type} JSON to logs: {json_e}")

    async def start_exchange(self, exchange):
        """Start exchange deployment and service"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        # exchange_name = exchange.get('exchange_name', f"Exchange-{name}")

        logger.info(f"Starting exchange with exch_id: {exch_id} (type: {type(exch_id)})")
        logger.info(f"Generated resource name: {name}")
        logger.info(f"Exchange data received: {exchange}")

        try:
            # Create deployment manifest
            deployment = self.deployment_template.create(exchange, name)

            # DUMP DEPLOYMENT YAML TO LOGS
            # self._dump_yaml_to_logs("Deployment", deployment, exchange_name)

            # Create deployment
            await self._create_deployment(deployment)
            logger.info(f"✅ Deployment created successfully for {exch_id}")

            # Create service manifest
            service = self.service_template.create(exchange, name)

            # DUMP SERVICE YAML TO LOGS
            # self._dump_yaml_to_logs("Service", service, exchange_name)

            # Create service
            await self._create_service(service)
            logger.info(f"✅ Service created successfully for {exch_id}")

            # Use string representation for tracking
            self.running_exchanges.add(str(exch_id))
            logger.info(f"Started exchange: {exch_id} ({name})")

        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.error(f"Failed to start {exch_id}: {e}")
                logger.error(f"Exchange data was: {exchange}")
                raise
            else:
                # Already running, add to tracking
                self.running_exchanges.add(str(exch_id))
                logger.info(f"Exchange {exch_id} already running")

    async def stop_exchange(self, exchange):
        """Stop exchange deployment and service"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        exchange_name = exchange.get('exchange_name', f"Exchange-{name}")

        logger.info(f"Stopping exchange: {exchange_name} ({name})")

        try:
            # Delete deployment
            await self._delete_deployment(name)
            logger.info(f"✅ Deployment deleted for {exchange_name}")

            # Delete service
            await self._delete_service(name)
            logger.info(f"✅ Service deleted for {exchange_name}")

            self.running_exchanges.discard(str(exch_id))
            logger.info(f"Stopped exchange: {exchange_name} ({name})")

        except Exception as e:
            if "not found" not in str(e).lower():
                logger.error(f"Failed to stop {exchange_name}: {e}")
                raise
            else:
                logger.info(f"Exchange {exchange_name} was not running")

    async def check_exchange_health(self, exchange):
        """Check health of a specific exchange pod"""
        exch_id = exchange['exch_id']
        name = self._get_resource_name(exch_id)
        exchange_name = exchange.get('exchange_name', f"Exchange-{name}")

        try:
            # Check deployment status
            deployment = self.k8s_apps.read_namespaced_deployment(name, self.namespace)

            # Check if deployment is ready
            replicas = deployment.spec.replicas or 0
            ready_replicas = deployment.status.ready_replicas or 0

            if ready_replicas >= replicas and replicas > 0:
                logger.debug(f"✅ {exchange_name} is healthy ({ready_replicas}/{replicas} replicas ready)")
                return True
            else:
                logger.warning(f"⚠️ {exchange_name} is not ready ({ready_replicas}/{replicas} replicas ready)")
                return False

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
                    logger.error(
                        f"HEALTH CHECK FAILED: Exchange {exch_id_str} deployment not found but marked as running")
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
