# source/utils/metrics.py
import logging
import threading
import time
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server

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

SESSION_LIFETIME = Histogram(
    'session_lifetime_seconds',
    'Session lifetime in seconds',
    ['status']  # 'completed', 'expired', 'error'
)

SESSION_OPERATIONS = Counter(
    'session_operations_total',
    'Number of session operations',
    ['operation']  # 'create', 'reconnect', 'end', etc.
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
    ['direction', 'type']  # direction: 'received', 'sent'; type: message type
)

WEBSOCKET_ERRORS = Counter(
    'session_websocket_errors_total',
    'Number of WebSocket errors',
    ['error_type']
)

# SSE Metrics
SSE_CONNECTIONS = Gauge(
    'session_sse_connections',
    'Number of active SSE connections',
    ['pod_name']
)

SSE_MESSAGES = Counter(
    'session_sse_messages_total',
    'Number of SSE messages sent',
    ['event_type']
)

# Simulator Metrics
ACTIVE_SIMULATORS = Gauge(
    'session_active_simulators',
    'Number of active simulators',
    ['pod_name']
)

SIMULATOR_OPERATIONS = Counter(
    'session_simulator_operations_total',
    'Number of simulator operations',
    ['operation', 'status']  # operation: 'create', 'stop', etc.; status: 'success', 'failure'
)

SIMULATOR_CREATION_DURATION = Histogram(
    'session_simulator_creation_duration_seconds',
    'Time taken to create a simulator',
    []
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

# Client Metrics
CLIENT_RECONNECTIONS = Counter(
    'session_client_reconnections_total',
    'Number of client reconnections',
    ['reconnect_count']
)

CLIENT_CONNECTION_QUALITY = Gauge(
    'session_client_connection_quality',
    'Client connection quality (0:Poor, 1:Degraded, 2:Good)',
    ['pod_name']
)

# System Metrics
CLEANUP_OPERATIONS = Counter(
    'session_cleanup_operations_total',
    'Number of cleanup operations performed',
    ['operation', 'items_cleaned']
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


# Helper functions to track metrics

def track_rest_request(method, endpoint, status_code, duration):
    """Track REST API request"""
    REST_API_REQUESTS.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
    REST_API_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def track_session_count(count, pod_name=None):
    """Track active session count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    ACTIVE_SESSIONS.labels(pod_name=pod_name).set(count)


def track_session_operation(operation):
    """Track session operation"""
    SESSION_OPERATIONS.labels(operation=operation).inc()


def track_session_ended(duration_seconds, status='completed'):
    """Track session end/expiry"""
    SESSION_LIFETIME.labels(status=status).observe(duration_seconds)


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


def track_sse_connection_count(count, pod_name=None):
    """Track SSE connection count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    SSE_CONNECTIONS.labels(pod_name=pod_name).set(count)


def track_sse_message(event_type):
    """Track SSE message"""
    SSE_MESSAGES.labels(event_type=event_type).inc()


def track_simulator_count(count, pod_name=None):
    """Track active simulator count"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name
    ACTIVE_SIMULATORS.labels(pod_name=pod_name).set(count)


def track_simulator_operation(operation, status='success'):
    """Track simulator operation"""
    SIMULATOR_OPERATIONS.labels(operation=operation, status=status).inc()


def track_simulator_creation_time(duration_seconds):
    """Track simulator creation time"""
    SIMULATOR_CREATION_DURATION.observe(duration_seconds)


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
    # Convert state to number: CLOSED=0, OPEN=1, HALF_OPEN=2
    state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
    state_num = state_map.get(state, 0)
    CIRCUIT_BREAKER_STATE.labels(service=service).set(state_num)


def track_circuit_breaker_failure(service):
    """Track circuit breaker failure"""
    CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()


def track_client_reconnection(reconnect_count):
    """Track client reconnection"""
    # Bucket higher reconnect counts
    if reconnect_count > 5:
        reconnect_count = "5+"
    CLIENT_RECONNECTIONS.labels(reconnect_count=str(reconnect_count)).inc()


def track_connection_quality(quality, pod_name=None):
    """Track connection quality"""
    if pod_name is None:
        pod_name = config.kubernetes.pod_name

    # Convert quality to number: poor=0, degraded=1, good=2
    quality_map = {"poor": 0, "degraded": 1, "good": 2}
    quality_num = quality_map.get(quality, 0)
    CLIENT_CONNECTION_QUALITY.labels(pod_name=pod_name).set(quality_num)


def track_cleanup_operation(operation, items_cleaned=0):
    """Track cleanup operation"""
    CLEANUP_OPERATIONS.labels(operation=operation, items_cleaned=str(items_cleaned)).inc()


# Context manager for timing operations and recording metrics
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