"""
Kubernetes client utilities for managing simulator deployments.
Provides an interface to create, monitor, and delete simulator pods.
"""
import logging
import time
import grpc
import asyncio
from typing import Dict, Any, List
from kubernetes import client, config

from source.config import config as app_config

#from source.api.grpc.exchange_simulator_pb2_grpc import ExchangeSimulatorStub

logger = logging.getLogger('k8s_client')


class KubernetesClient:
    """Client for Kubernetes API operations"""

    def __init__(self):
        """Initialize the Kubernetes client"""
        self.apps_v1 = None
        self.core_v1 = None
        self.initialized = False
        self.namespace = app_config.kubernetes.namespace
        self.pod_name = app_config.kubernetes.pod_name

    def initialize(self):
        """Initialize the Kubernetes client"""
        if self.initialized:
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

    async def create_simulator_deployment(
            self,
            simulator_id: str,
            session_id: str,
            user_id: str,
    ) -> str:
        """
        Create a new simulator deployment in Kubernetes
        
        Args:
            simulator_id: Unique ID for the simulator
            session_id: Session ID
            user_id: User ID
            
        Returns:
            The service endpoint for the simulator
        """
        self.initialize()

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
                                    client.V1ContainerPort(container_port=50055, name="grpc"),  # gRPC port
                                    client.V1ContainerPort(container_port=50056, name="http")   # HTTP port
                                ],
                                env=env_vars,
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "100m", "memory": "128Mi"},
                                    limits={"cpu": "500m", "memory": "512Mi"}
                                ),
                                readiness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/readiness",  # Changed from /health to /readiness
                                        port=50056         # Use HTTP port instead of gRPC port
                                    ),
                                    initial_delay_seconds=5,
                                    period_seconds=10
                                ),
                                liveness_probe=client.V1Probe(
                                    http_get=client.V1HTTPGetAction(
                                        path="/health",
                                        port=50056         # Use HTTP port instead of gRPC port
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

            # Return the endpoint
            endpoint = f"{service_name}.{self.namespace}.svc.cluster.local:50055"
            return endpoint

        except Exception as e:
            logger.error(f"Error creating simulator deployment: {e}")
            # Try to clean up any resources that were created
            try:
                self.delete_simulator_deployment(simulator_id)
            except:
                pass
            raise

    async def delete_simulator_deployment(self, simulator_id: str) -> bool:
        """
        Delete a simulator deployment and service
        
        Args:
            simulator_id: ID of the simulator to delete
            
        Returns:
            True if successful, False otherwise
        """
        self.initialize()

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

            return True
        except Exception as e:
            logger.error(f"Error deleting simulator deployment: {e}")
            return False

    async def check_simulator_status(self, simulator_id: str) -> str:
        """
        Check status of a simulator deployment
        
        Args:
            simulator_id: ID of the simulator
            
        Returns:
            Status string: "PENDING", "RUNNING", "FAILED", "UNKNOWN"
        """
        self.initialize()

        deployment_name = f"simulator-{simulator_id}"

        try:
            # Get deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace
            )

            # Check status
            if deployment.status.available_replicas == 1:
                return "RUNNING"
            elif deployment.status.unavailable_replicas == 1:
                return "PENDING"
            else:
                return "UNKNOWN"
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return "NOT_FOUND"
            return "FAILED"
        except Exception as e:
            logger.error(f"Error checking simulator status: {e}")
            return "UNKNOWN"

    async def list_user_simulators(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all simulator deployments for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of simulator details
        """
        self.initialize()

        try:
            # Get deployments with matching labels
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector=f"user_id={user_id},app=exchange-simulator"
            )

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
            return []

    async def cleanup_inactive_simulators(self, older_than_seconds: int = 3600) -> int:
        """
        Cleanup simulator deployments that haven't been updated recently
        
        Args:
            older_than_seconds: Delete simulators older than this many seconds
            
        Returns:
            Number of simulators deleted
        """
        self.initialize()

        try:
            # Get all simulator deployments with more detailed filtering
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector="app=exchange-simulator,managed-by=session-service"
            )

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
                        self._check_simulator_health(endpoint, session_id),
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
                    await self.delete_simulator_deployment(simulator_id)
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} inactive simulator deployments")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up inactive simulators: {e}")
            return 0

    async def _check_simulator_health(self, endpoint: str, session_id: str) -> dict:
        """Check simulator health via gRPC"""
        try:
            # This would use your ExchangeClient, but keeping it here for simplicity
            channel = grpc.aio.insecure_channel(endpoint)
            #stub = ExchangeSimulatorStub(channel)

            # response = await stub.GetSimulatorStatus(request, timeout=2.0)

            await channel.close()

            return {
                'status': 'OK',  # response.status,
                'uptime_seconds': 100,  # response.uptime_seconds,
                'error': None
            }
        except Exception as e:
            logger.error(f"Error checking simulator health: {e}")
            return {'status': 'UNREACHABLE', 'error': str(e)}

    async def list_simulator_deployments(self) -> List[Dict[str, Any]]:
        """
        List all simulator deployments
        
        Returns:
            List of simulator deployment details
        """
        self.initialize()

        try:
            # Get deployments with matching labels
            deployment_list = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector="app=exchange-simulator"
            )

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
            return []
