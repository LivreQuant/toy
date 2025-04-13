# source/clients/k8s_client.py
"""
Kubernetes client utilities with circuit breaker protection.
"""
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional
from kubernetes import client, config

from source.config import config as app_config
from source.utils.circuit_breaker import CircuitOpenError
from source.utils.metrics import track_external_request
from source.utils.tracing import optional_trace_span
from source.clients.base import BaseClient

logger = logging.getLogger('k8s_client')


async def _check_simulator_health(endpoint: str, session_id: str) -> dict:
    """
    Check simulator health via gRPC.

    Args:
        endpoint: The service endpoint
        session_id: The session ID

    Returns:
        Dictionary with status information
    """
    try:
        # In a real implementation, use the ExchangeClient to check health
        # For now, simulate a health check without adding a dependency
        import grpc.aio
        channel = grpc.aio.insecure_channel(endpoint)

        # Simulate a quick channel check
        await asyncio.sleep(0.1)

        # Close channel properly
        await channel.close()

        return {
            'status': 'OK',
            'uptime_seconds': 100,
            'error': None
        }
    except Exception as e:
        logger.error(f"Error checking simulator health: {e}")
        return {'status': 'UNREACHABLE', 'error': str(e)}


class KubernetesClient(BaseClient):
    """Client for Kubernetes API operations with circuit breaker protection."""

    def __init__(self):
        """Initialize the Kubernetes client."""
        super().__init__(
            service_name="kubernetes_api",
            failure_threshold=3,
            reset_timeout_ms=60000  # Longer timeout for k8s operations
        )
        self.apps_v1: Optional[client.AppsV1Api] = None
        self.core_v1: Optional[client.CoreV1Api] = None
        self.initialized = False
        self.namespace = app_config.kubernetes.namespace
        self.pod_name = app_config.kubernetes.pod_name
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self):
        """Ensure client is initialized (async-safe)."""
        if self.initialized:
            return

        async with self._init_lock:
            if self.initialized:  # Check again inside lock
                return

            try:
                # Load appropriate configuration
                if app_config.kubernetes.in_cluster:
                    config.load_incluster_config()
                    logger.info("Loaded in-cluster Kubernetes configuration")
                else:
                    config.load_kube_config()
                    logger.info("Loaded local Kubernetes configuration")

                # Initialize API clients
                self.core_v1 = client.CoreV1Api()
                self.apps_v1 = client.AppsV1Api()

                self.initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Kubernetes client: {e}")
                raise

    async def close(self):
        """Clean up any resources."""
        # The Kubernetes client doesn't have a specific close method,
        # but we implement this for consistency with other clients
        logger.debug("Kubernetes client resources cleaned")
        pass

    async def create_simulator_deployment(
            self,
            simulator_id: str,
            session_id: str,
            user_id: str,
    ) -> str:
        """
        Create a new simulator deployment in Kubernetes with circuit breaker protection.
        
        Args:
            simulator_id: Unique ID for the simulator
            session_id: Session ID
            user_id: User ID
            
        Returns:
            The service endpoint for the simulator
            
        Raises:
            CircuitOpenError: If the circuit breaker is open
            Exception: For other errors
        """
        with optional_trace_span(self.tracer, "create_simulator_deployment") as span:
            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)

            try:
                # Use circuit breaker for the kubernetes operation
                return await self.execute_with_cb(
                    self._create_simulator_deployment_impl,
                    simulator_id, session_id, user_id
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                raise
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error creating simulator deployment: {e}")
                raise

    async def _create_simulator_deployment_impl(
            self,
            simulator_id: str,
            session_id: str,
            user_id: str,
    ) -> str:
        """
        Implementation of create_simulator_deployment protected by circuit breaker.
        
        Args:
            simulator_id: Unique ID for the simulator
            session_id: Session ID
            user_id: User ID
            
        Returns:
            The service endpoint for the simulator
        """
        start_time = time.time()

        await self._ensure_initialized()

        # Create unique names
        deployment_name = f"simulator-{simulator_id}"
        service_name = f"simulator-{simulator_id}"

        # Define container env vars
        env_vars = [
            client.V1EnvVar(name="SIMULATOR_ID", value=simulator_id),
            client.V1EnvVar(name="SESSION_ID", value=session_id),
            client.V1EnvVar(name="USER_ID", value=user_id),
            client.V1EnvVar(name="DESK_ID", value="test"),

            # Database connection variables
            client.V1EnvVar(name="DB_HOST", value="postgres"),
            client.V1EnvVar(name="DB_PORT", value="5432"),
            client.V1EnvVar(name="DB_NAME", value="opentp"),
            client.V1EnvVar(
                name="DB_USER",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name="db-credentials",
                        key="username"
                    )
                )
            ),
            client.V1EnvVar(
                name="DB_PASSWORD",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name="db-credentials",
                        key="password"
                    )
                )
            ),
        ]

        # Create deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=deployment_name,
                namespace=self.namespace,
                labels={
                    "app": "exchange-simulator",
                    "simulator_id": simulator_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "managed-by": "session-service"
                }
            ),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels={"simulator_id": simulator_id}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "exchange-simulator",
                            "simulator_id": simulator_id,
                            "session_id": session_id,
                            "user_id": user_id
                        }
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="exchange-simulator",
                                image="opentp/exchange-simulator:latest",
                                image_pull_policy="Never",
                                ports=[
                                    client.V1ContainerPort(container_port=50055, name="grpc"),
                                    client.V1ContainerPort(container_port=50056, name="http")
                                ],
                                env=env_vars,
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "100m", "memory": "128Mi"},
                                    limits={"cpu": "500m", "memory": "512Mi"}
                                ),
                                readiness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/readiness",
                                        port=50056
                                    ),
                                    initial_delay_seconds=5,
                                    period_seconds=10
                                ),
                                liveness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/health",
                                        port=50056
                                    ),
                                    initial_delay_seconds=15,
                                    period_seconds=20
                                )
                            )
                        ],
                        termination_grace_period_seconds=30
                    )
                )
            )
        )

        # Create service for the simulator
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                namespace=self.namespace,
                labels={
                    "app": "exchange-simulator",
                    "simulator_id": simulator_id,
                    "managed-by": "session-service"
                }
            ),
            spec=client.V1ServiceSpec(
                selector={"simulator_id": simulator_id},
                ports=[client.V1ServicePort(port=50055, target_port=50055)],
                type="ClusterIP"
            )
        )

        try:
            # Create deployment
            self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment
            )
            logger.info(f"Created deployment {deployment_name} in namespace {self.namespace}")

            # Create service
            self.core_v1.create_namespaced_service(
                namespace=self.namespace,
                body=service
            )
            logger.info(f"Created service {service_name} in namespace {self.namespace}")

            # Track external request metrics
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "create_simulator", 200, duration)

            # Return the endpoint
            endpoint = f"{service_name}.{self.namespace}.svc.cluster.local:50055"
            return endpoint

        except Exception as e:
            logger.error(f"Error creating simulator deployment: {e}")
            # Track external request metrics for failure
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "create_simulator", 500, duration)

            # Try to clean up any resources that were created
            try:
                await self.delete_simulator_deployment(simulator_id)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup after failed deployment: {cleanup_error}")

            raise

    async def delete_simulator_deployment(self, simulator_id: str) -> bool:
        """
        Delete a simulator deployment and service with circuit breaker protection.
        
        Args:
            simulator_id: ID of the simulator to delete
            
        Returns:
            True if successful, False otherwise
        """
        with optional_trace_span(self.tracer, "delete_simulator_deployment") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                return await self.execute_with_cb(
                    self._delete_simulator_deployment_impl,
                    simulator_id
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API during delete.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                return False
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error deleting simulator deployment: {e}")
                return False

    async def _delete_simulator_deployment_impl(self, simulator_id: str) -> bool:
        """
        Implementation of delete_simulator_deployment protected by circuit breaker.

        Args:
            simulator_id: ID of the simulator to delete

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        await self._ensure_initialized()

        deployment_name = f"simulator-{simulator_id}"
        service_name = f"simulator-{simulator_id}"

        try:
            # Delete deployment
            self.apps_v1.delete_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace
            )
            logger.info(f"Deleted deployment {deployment_name}")

            # Delete service
            self.core_v1.delete_namespaced_service(
                name=service_name,
                namespace=self.namespace
            )
            logger.info(f"Deleted service {service_name}")

            # Track external request metrics
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "delete_simulator", 200, duration)

            return True
        except Exception as e:
            logger.error(f"Error deleting simulator deployment: {e}")
            # Track external request metrics for failure
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "delete_simulator", 500, duration)
            raise

    async def check_simulator_status(self, simulator_id: str) -> str:
        """
        Check status of a simulator deployment with circuit breaker protection.

        Args:
            simulator_id: ID of the simulator

        Returns:
            Status string: "PENDING", "RUNNING", "FAILED", "UNKNOWN"
        """
        with optional_trace_span(self.tracer, "check_simulator_status") as span:
            span.set_attribute("simulator_id", simulator_id)

            try:
                return await self.execute_with_cb(
                    self._check_simulator_status_impl,
                    simulator_id
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API during status check.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                return "UNKNOWN"
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error checking simulator status: {e}")
                return "UNKNOWN"

    async def _check_simulator_status_impl(self, simulator_id: str) -> str:
        """
        Implementation of check_simulator_status protected by circuit breaker.

        Args:
            simulator_id: ID of the simulator

        Returns:
            Status string: "PENDING", "RUNNING", "FAILED", "UNKNOWN", "NOT_FOUND"
        """
        start_time = time.time()
        await self._ensure_initialized()

        deployment_name = f"simulator-{simulator_id}"

        try:
            # Get deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace
            )

            # Track external request metrics
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "check_simulator_status", 200, duration)

            # Check status
            if deployment.status.available_replicas == 1:
                return "RUNNING"
            elif deployment.status.unavailable_replicas == 1:
                return "PENDING"
            else:
                return "UNKNOWN"
        except client.exceptions.ApiException as e:
            # Track external request metrics with proper status code
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "check_simulator_status", e.status, duration)

            if e.status == 404:
                return "NOT_FOUND"
            return "FAILED"
        except Exception as e:
            logger.error(f"Error checking simulator status: {e}")
            # Track external request metrics for other failures
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "check_simulator_status", 500, duration)
            raise

    async def list_user_simulators(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all simulator deployments for a user with circuit breaker protection.

        Args:
            user_id: ID of the user

        Returns:
            List of simulator details
        """
        with optional_trace_span(self.tracer, "list_user_simulators") as span:
            span.set_attribute("user_id", user_id)

            try:
                return await self.execute_with_cb(
                    self._list_user_simulators_impl,
                    user_id
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API during user simulators listing.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                return []
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error listing user simulators: {e}")
                return []

    async def _list_user_simulators_impl(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Implementation of list_user_simulators protected by circuit breaker.

        Args:
            user_id: ID of the user

        Returns:
            List of simulator details
        """
        start_time = time.time()
        await self._ensure_initialized()

        try:
            # Get deployments with matching labels
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector=f"user_id={user_id},app=exchange-simulator"
            )

            # Track external request metrics
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "list_user_simulators", 200, duration)

            simulators = []
            for deployment in deployment_list.items:
                simulator_id = deployment.metadata.labels.get("simulator_id")
                session_id = deployment.metadata.labels.get("session_id")

                simulators.append({
                    "simulator_id": simulator_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "status": "RUNNING" if deployment.status.available_replicas == 1 else "PENDING",
                    "created_at": deployment.metadata.creation_timestamp.timestamp()
                })

            return simulators
        except Exception as e:
            logger.error(f"Error listing user simulators: {e}")
            # Track external request metrics for failure
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "list_user_simulators", 500, duration)
            raise

    async def cleanup_inactive_simulators(self, older_than_seconds: int = 3600) -> int:
        """
        Cleanup simulator deployments that haven't been updated recently with circuit breaker protection.

        Args:
            older_than_seconds: Delete simulators older than this many seconds

        Returns:
            Number of simulators deleted
        """
        with optional_trace_span(self.tracer, "cleanup_inactive_simulators") as span:
            span.set_attribute("older_than_seconds", older_than_seconds)

            try:
                return await self.execute_with_cb(
                    self._cleanup_inactive_simulators_impl,
                    older_than_seconds
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API during cleanup.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                return 0
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error during simulator cleanup: {e}")
                return 0

    async def _cleanup_inactive_simulators_impl(self, older_than_seconds: int = 3600) -> int:
        """
        Implementation of cleanup_inactive_simulators protected by circuit breaker.

        Args:
            older_than_seconds: Delete simulators older than this many seconds

        Returns:
            Number of simulators deleted
        """
        start_time = time.time()
        await self._ensure_initialized()

        try:
            # Get all simulator deployments with detailed filtering
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector="app=exchange-simulator,managed-by=session-service"
            )

            # Track external request metrics for the list operation
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "list_deployments", 200, duration)

            deleted_count = 0
            now = time.time()

            for deployment in deployment_list.items:
                simulator_id = deployment.metadata.labels.get("simulator_id")
                session_id = deployment.metadata.labels.get("session_id")

                if not simulator_id or not session_id:
                    logger.warning(f"Found deployment without proper labels: {deployment.metadata.name}")
                    continue

                # First check simulator status via service endpoint if accessible
                status = "UNKNOWN"
                try:
                    service_name = f"simulator-{simulator_id}"
                    endpoint = f"{service_name}.{self.namespace}.svc.cluster.local:50055"
                    # Try to get status (timeout quickly)
                    status_response = await asyncio.wait_for(
                        _check_simulator_health(endpoint, session_id),
                        timeout=2.0
                    )
                    status = status_response.get('status', 'UNKNOWN')
                except (asyncio.TimeoutError, Exception) as e:
                    logger.info(f"Simulator {simulator_id} health check failed: {e}")
                    # If we can't reach it, assume it's not healthy
                    status = "UNREACHABLE"

                # Check creation time
                created_time = deployment.metadata.creation_timestamp.timestamp()
                age_seconds = now - created_time

                should_delete = False

                # Delete if too old
                if age_seconds > older_than_seconds:
                    logger.info(f"Simulator {simulator_id} is too old (age: {age_seconds:.1f}s)")
                    should_delete = True
                # Delete if unreachable
                elif status == "UNREACHABLE":
                    logger.info(f"Simulator {simulator_id} is unreachable")
                    should_delete = True
                # Delete if pod reports ERROR state
                elif status == "ERROR":
                    logger.info(f"Simulator {simulator_id} reports ERROR state")
                    should_delete = True

                if should_delete:
                    success = await self.delete_simulator_deployment(simulator_id)
                    if success:
                        deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} inactive simulator deployments")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up inactive simulators: {e}")
            # Track external request metrics for failure
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "cleanup_simulators", 500, duration)
            raise

    async def list_simulator_deployments(self) -> List[Dict[str, Any]]:
        """
        List all simulator deployments with circuit breaker protection.

        Returns:
            List of simulator deployment details
        """
        with optional_trace_span(self.tracer, "list_simulator_deployments") as span:
            try:
                return await self.execute_with_cb(
                    self._list_simulator_deployments_impl
                )
            except CircuitOpenError:
                logger.warning(f"Circuit open for Kubernetes API during simulator deployments listing.")
                span.set_attribute("error", "Kubernetes API unavailable (circuit open)")
                return []
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                logger.error(f"Error listing simulator deployments: {e}")
                return []

    async def _list_simulator_deployments_impl(self) -> List[Dict[str, Any]]:
        """
        Implementation of list_simulator_deployments protected by circuit breaker.

        Returns:
            List of simulator deployment details
        """
        start_time = time.time()
        await self._ensure_initialized()

        try:
            # Get deployments with matching labels
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector="app=exchange-simulator"
            )

            # Track external request metrics
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "list_simulator_deployments", 200, duration)

            simulators = []
            for deployment in deployment_list.items:
                simulator_id = deployment.metadata.labels.get("simulator_id")
                session_id = deployment.metadata.labels.get("session_id")
                user_id = deployment.metadata.labels.get("user_id")

                if not simulator_id:
                    continue

                simulators.append({
                    "simulator_id": simulator_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "status": "RUNNING" if deployment.status.available_replicas == 1 else "PENDING",
                    "created_at": deployment.metadata.creation_timestamp.timestamp() if deployment.metadata.creation_timestamp else 0
                })

            return simulators
        except Exception as e:
            logger.error(f"Error listing simulator deployments: {e}")
            # Track external request metrics for failure
            duration = time.time() - start_time
            track_external_request("kubernetes_api", "list_simulator_deployments", 500, duration)
            raise
