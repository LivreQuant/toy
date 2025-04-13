# source/utils/metrics.py

import logging
import threading
import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from source.config import config

logger = logging.getLogger('metrics')

# Primary metrics - focus on the most important measurements
API_REQUESTS = Counter(
    'session_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

API_LATENCY = Histogram(
    'session_api_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'session_active_connections',
    'Number of active WebSocket connections',
    ['pod_name']
)

DATABASE_OPERATIONS = Counter(
    'session_db_operations_total',
    'Number of database operations',
    ['operation', 'status']
)

SIMULATOR_STATUS = Gauge(
    'session_simulator_status',
    'Simulator status (0:None, 1:Creating, 2:Starting, 3:Running, 4:Stopping, 5:Stopped, 6:Error)',
    ['pod_name']
)

ERROR_COUNT = Counter(
    'session_errors_total',
    'Number of errors by category',
    ['category', 'error_code']
)


def status_code_to_text(status_code: int) -> str:
    """Convert HTTP status code to text category"""
    if status_code < 200:
        return "informational"
    elif status_code < 300:
        return "success"
    elif status_code < 400:
        return "redirect"
    elif status_code < 500:
        return "client_error"
    else:
        return "server_error"


def setup_metrics(metrics_port=None):
    """Start Prometheus metrics server"""
    if metrics_port is None:
        metrics_port = config.metrics.port

    try:
        def _start_metrics_server():
            start_http_server(metrics_port)

        metrics_thread = threading.Thread(
            target=_start_metrics_server,
            daemon=True
        )
        metrics_thread.start()
        logger.info(f"Prometheus metrics server started on port {metrics_port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


def track_request(method: str, endpoint: str, status_code: int, duration: float):
    """Track an API request"""
    status_text = status_code_to_text(status_code)
    API_REQUESTS.labels(method=method, endpoint=endpoint, status=status_text).inc()
    API_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def track_connection_count(count: int, pod_name: str = None):
    """Track WebSocket connection count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    ACTIVE_CONNECTIONS.labels(pod_name=pod_name).set(count)


def track_db_operation(operation: str, success: bool = True):
    """Track database operation"""
    status = "success" if success else "error"
    DATABASE_OPERATIONS.labels(operation=operation, status=status).inc()


def track_simulator_state(state_value: int, pod_name: str = None):
    """Track simulator state"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    SIMULATOR_STATUS.labels(pod_name=pod_name).set(state_value)


def track_error(category: str, error_code: str):
    """Track an error"""
    ERROR_COUNT.labels(category=category, error_code=error_code).inc()


class TimedOperation:
    """Context manager for timing operations"""
    def __init__(self, operation_name: str, metric_func=None):
        self.operation_name = operation_name
        self.metric_func = metric_func or track_request
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        if hasattr(self, 'method') and hasattr(self, 'endpoint'):
            # For HTTP requests
            status = 500 if exc_type else 200
            self.metric_func(self.method, self.endpoint, status, duration)
        else:
            # For database operations
            track_db_operation(self.operation_name, success)
