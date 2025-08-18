# orchestrator/templates.py

class DeploymentTemplate:
    """Template for creating exchange service deployments"""
    
    def create(self, exchange, name: str) -> dict:
        """Create deployment manifest for exchange"""
        # Convert UUID objects to strings for Kubernetes compatibility
        exch_id_str = str(exchange['exch_id'])
        
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "labels": {
                    "app": name,
                    "managed-by": "orchestrator",
                    "exch-id": exch_id_str
                }
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {"app": name}
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name,
                            "exch-id": exch_id_str
                        },
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": "9090",
                            "prometheus.io/path": "/metrics"
                        }
                    },
                    "spec": {
                        "initContainers": [{
                            "name": "wait-for-db",
                            "image": "postgres:13",
                            "command": [
                                "sh", "-c",
                                "until pg_isready -h pgbouncer -p 5432; do echo waiting for database; sleep 2; done;"
                            ]
                        }],
                        "containers": [{
                            "name": "exchange-service",
                            "image": "opentp/exchange-service:latest",
                            "imagePullPolicy": "Never",
                            "ports": [
                                {"containerPort": 50050},  # Session service port
                                {"containerPort": 50055},  # gRPC service port
                                {"containerPort": 50056},  # HTTP health check port
                                {"containerPort": 9090}    # Metrics port
                            ],
                            "env": [
                                # Database configuration
                                {"name": "DB_HOST", "value": "pgbouncer"},
                                {"name": "DB_PORT", "value": "5432"},
                                {"name": "DB_NAME", "value": "opentp"},
                                {"name": "DB_USER", "valueFrom": {"secretKeyRef": {"name": "db-credentials", "key": "username"}}},
                                {"name": "DB_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "db-credentials", "key": "password"}}},
                                
                                # Service configuration
                                {"name": "ENVIRONMENT", "value": "production"},
                                {"name": "LOG_LEVEL", "value": "INFO"},
                                
                                # Exchange configuration - ONLY EXCH_ID and EXCHANGE_TYPE
                                {"name": "EXCHANGE_TYPE", "value": str(exchange.get('exchange_type', 'US_EQUITIES'))},
                                {"name": "EXCH_ID", "value": exch_id_str},
                                
                                # Service ports
                                {"name": "GRPC_SERVICE_PORT", "value": "50050"},
                                {"name": "SESSION_SERVICE_PORT", "value": "50050"},
                                {"name": "HEALTH_SERVICE_PORT", "value": "50056"},
                                {"name": "HOST", "value": "0.0.0.0"},
                                
                                # Pod info for service discovery
                                {"name": "POD_IP", "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}}},
                                {"name": "POD_NAME", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
                                {"name": "POD_NAMESPACE", "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}}},
                                
                                # Feature flags
                                {"name": "ENABLE_METRICS", "value": "true"},
                                {"name": "ENABLE_TRACING", "value": "true"},
                                {"name": "ENABLE_SESSION_SERVICE", "value": "true"},
                                {"name": "ENABLE_CONVICTION_SERVICE", "value": "false"},
                                
                                # Service URLs
                                {"name": "AUTH_SERVICE_URL", "value": "http://auth-service:8000"},
                                {"name": "MARKET_DATA_HOST", "value": "exch-us-equities-market-data-service"},
                                {"name": "MARKET_DATA_PORT", "value": "50060"},
                                {"name": "MARKET_DATA_RETRY_SECONDS", "value": "5"}
                            ],
                            "resources": {
                                "requests": {"memory": "256Mi", "cpu": "200m"},
                                "limits": {"memory": "1Gi", "cpu": "500m"}
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/ready", "port": 50056},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 10,
                                "timeoutSeconds": 5,
                                "failureThreshold": 3
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": 50056},
                                "initialDelaySeconds": 30,
                                "periodSeconds": 30,
                                "timeoutSeconds": 10,
                                "failureThreshold": 3
                            }
                        }]
                    }
                }
            }
        }


class ServiceTemplate:
    """Template for creating exchange services"""
    
    def create(self, exchange, name: str) -> dict:
        """Create service manifest for exchange"""
        # Convert UUID objects to strings for Kubernetes compatibility
        exch_id_str = str(exchange['exch_id'])
        
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "labels": {
                    "app": name,
                    "managed-by": "orchestrator",
                    "exch-id": exch_id_str
                }
            },
            "spec": {
                "selector": {"app": name},
                "ports": [
                    {"port": 50055, "targetPort": 50055, "name": "grpc"},
                    {"port": 50056, "targetPort": 50056, "name": "http"}, 
                    {"port": 9090, "targetPort": 9090, "name": "metrics"}
                ],
                "type": "ClusterIP"
            }
        }