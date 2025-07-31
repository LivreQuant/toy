"""
Metrics for session service - connection-focused, no creation metrics.
"""
import logging
import threading
import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from source.config import config

logger = logging.getLogger('metrics')

# REST API Metrics
REST_API_REQUESTS = Counter(
    'session_rest_requests_total',
    'Total number of REST API requests',
    ['method', 'endpoint', 'status']
)

REST_API_LATENCY = Histogram(
    'session_rest_request_duration_seconds',
    'REST API request duration in seconds',
    ['method', 'endpoint']
)

# Session Metrics
ACTIVE_SESSIONS = Gauge(
    'session_active_sessions',
    'Number of active sessions',
    ['pod_name']
)

SESSION_OPERATIONS = Counter(
    'session_operations_total',
    'Number of session operations',
    ['operation']
)

# WebSocket Metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'session_websocket_connections',
    'Number of active WebSocket connections',
    ['pod_name']
)

WEBSOCKET_MESSAGES = Counter(
    'session_websocket_messages_total',
    'Number of WebSocket messages',
    ['direction', 'type']
)

WEBSOCKET_ERRORS = Counter(
    'session_websocket_errors_total',
    'Number of WebSocket errors',
    ['error_type']
)

# Simulator Connection Metrics (updated - no creation, just connection)
SIMULATOR_CONNECTIONS = Gauge(
    'session_simulator_connections',
    'Number of active simulator connections',
    ['pod_name']
)

SIMULATOR_CONNECTION_ATTEMPTS = Counter(
    'session_simulator_connection_attempts_total',
    'Number of simulator connection attempts',
    ['status']
)

SIMULATOR_CONNECTION_DURATION = Histogram(
    'session_simulator_connection_duration_seconds',
    'Time taken to establish simulator connection',
    ['status']
)

# Database Metrics
DB_OPERATION_LATENCY = Histogram(
    'session_db_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation']
)

DB_ERRORS = Counter(
    'session_db_errors_total',
    'Number of database errors',
    ['operation']
)

# External Service Metrics
EXTERNAL_SERVICE_REQUESTS = Counter(
    'session_external_service_requests_total',
    'Number of requests to external services',
    ['service', 'endpoint', 'status']
)

EXTERNAL_SERVICE_LATENCY = Histogram(
    'session_external_service_duration_seconds',
    'External service request duration in seconds',
    ['service', 'endpoint']
)

# Circuit Breaker Metrics
CIRCUIT_BREAKER_STATE = Gauge(
    'session_circuit_breaker_state',
    'Circuit breaker state (0:Closed, 1:Open, 2:Half-Open)',
    ['service']
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'session_circuit_breaker_failures_total',
    'Number of circuit breaker failures',
    ['service']
)


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


def track_rest_request(method, endpoint, status_code, duration):
    """Track REST API request"""
    REST_API_REQUESTS.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
    REST_API_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def track_session_count(count, pod_name=None):
    """Track active session count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    ACTIVE_SESSIONS.labels(pod_name=pod_name).set(count)


def track_session_operation(operation, status="success"):
    """Track session operation"""
    SESSION_OPERATIONS.labels(operation=operation).inc()


def track_websocket_connection_count(count, pod_name=None):
    """Track WebSocket connection count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    WEBSOCKET_CONNECTIONS.labels(pod_name=pod_name).set(count)


def track_websocket_message(direction, message_type):
    """Track WebSocket message"""
    WEBSOCKET_MESSAGES.labels(direction=direction, type=message_type).inc()


def track_websocket_error(error_type):
    """Track WebSocket error"""
    WEBSOCKET_ERRORS.labels(error_type=error_type).inc()


def track_simulator_connection_count(count, pod_name=None):
    """Track active simulator connection count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    SIMULATOR_CONNECTIONS.labels(pod_name=pod_name).set(count)


def track_simulator_connection_attempt(status='success'):
    """Track simulator connection attempt"""
    SIMULATOR_CONNECTION_ATTEMPTS.labels(status=status).inc()


def track_simulator_connection_time(duration_seconds, status='success'):
    """Track simulator connection time"""
    SIMULATOR_CONNECTION_DURATION.labels(status=status).observe(duration_seconds)


def track_db_operation(operation, duration_seconds):
    """Track database operation"""
    DB_OPERATION_LATENCY.labels(operation=operation).observe(duration_seconds)


def track_db_error(operation):
    """Track database error"""
    DB_ERRORS.labels(operation=operation).inc()


def track_external_request(service, endpoint, status, duration_seconds):
    """Track external service request"""
    EXTERNAL_SERVICE_REQUESTS.labels(service=service, endpoint=endpoint, status=status).inc()
    EXTERNAL_SERVICE_LATENCY.labels(service=service, endpoint=endpoint).observe(duration_seconds)


def track_circuit_breaker_state(service, state):
    """Track circuit breaker state change"""
    state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
    state_num = state_map.get(state, 0)
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state_num)


def track_circuit_breaker_failure(service):
    """Track circuit breaker failure"""
    CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()


def track_client_reconnection(reconnect_count):
    """Track client reconnection"""
    CIRCUIT_BREAKER_FAILURES.labels(service=f"reconnect_{reconnect_count}").inc()


def track_connection_quality(quality, pod_name=None):
    """Track connection quality"""
    pass  # Simplified implementation


def track_cleanup_operation(operation, items_cleaned=0):
    """Track cleanup operation"""
    SESSION_OPERATIONS.labels(operation=f"cleanup_{operation}").inc()


class TimedOperation:
    def __init__(self, metric_func, *args, **kwargs):
        self.metric_func = metric_func
        self.args = args
        self.kwargs = kwargs
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is None:
            self.metric_func(*self.args, duration, **self.kwargs)