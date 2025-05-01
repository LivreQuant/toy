# source/utils/metrics.py
import logging
import os
import threading
from prometheus_client import Counter, Histogram, Gauge, start_http_server

logger = logging.getLogger('metrics')

# Order Lifecycle Metrics
ORDER_CREATED = Counter(
    'order_created_total',
    'Total number of orders created',
    ['order_type', 'symbol', 'side']
)

ORDER_SUBMITTED = Counter(
    'order_submitted_total',
    'Total number of orders submitted to exchange',
    ['order_type', 'symbol', 'side']
)

ORDER_SUBMISSION_LATENCY = Histogram(
    'order_submission_latency_seconds',
    'Latency of order submission process',
    ['order_type', 'success']
)

ORDER_STATUS_CHANGES = Counter(
    'order_status_changes_total',
    'Total number of order status changes',
    ['from_status', 'to_status']
)

# User Activity Metrics
USER_ORDER_COUNT = Counter(
    'user_order_count_total',
    'Total number of orders per user',
    ['user_id']
)

# External Service Metrics
AUTH_REQUEST_LATENCY = Histogram(
    'auth_request_latency_seconds',
    'Latency of authentication service requests',
    ['endpoint', 'success']
)

SESSION_REQUEST_LATENCY = Histogram(
    'session_request_latency_seconds',
    'Latency of session service requests',
    ['endpoint', 'success']
)

EXCHANGE_REQUEST_LATENCY = Histogram(
    'exchange_request_latency_seconds',
    'Latency of exchange service requests',
    ['operation', 'success']
)

# Database Metrics
DB_OPERATION_LATENCY = Histogram(
    'db_operation_latency_seconds',
    'Latency of database operations',
    ['operation', 'success']
)

DB_CONNECTION_COUNT = Gauge(
    'db_connection_count',
    'Number of open database connections'
)

# Circuit Breaker Metrics
CIRCUIT_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['service']
)

CIRCUIT_FAILURE_COUNT = Counter(
    'circuit_breaker_failures_total',
    'Total number of circuit breaker failures',
    ['service']
)


def setup_metrics():
    """Start Prometheus metrics server"""
    enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    if not enable_metrics:
        logger.info("Metrics are disabled")
        return

    metrics_port = int(os.getenv('METRICS_PORT', '9090'))
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
def track_order_created(order_type, symbol, side):
    """Track order creation"""
    ORDER_CREATED.labels(order_type=order_type, symbol=symbol, side=side).inc()


def track_order_submitted(order_type, symbol, side):
    """Track order submission to exchange"""
    ORDER_SUBMITTED.labels(order_type=order_type, symbol=symbol, side=side).inc()


def track_order_submission_latency(order_type, success, duration_seconds):
    """Track order submission latency"""
    ORDER_SUBMISSION_LATENCY.labels(order_type=order_type, success=str(success).lower()).observe(duration_seconds)


def track_order_status_change(from_status, to_status):
    """Track order status changes"""
    ORDER_STATUS_CHANGES.labels(from_status=from_status, to_status=to_status).inc()


def track_user_order(user_id):
    """Track orders per user"""
    USER_ORDER_COUNT.labels(user_id=user_id).inc()


def track_auth_request(endpoint, success, duration_seconds):
    """Track auth service request latency"""
    AUTH_REQUEST_LATENCY.labels(endpoint=endpoint, success=str(success).lower()).observe(duration_seconds)


def track_session_request(endpoint, success, duration_seconds):
    """Track session service request latency"""
    SESSION_REQUEST_LATENCY.labels(endpoint=endpoint, success=str(success).lower()).observe(duration_seconds)


def track_exchange_request(operation, success, duration_seconds):
    """Track exchange service request latency"""
    EXCHANGE_REQUEST_LATENCY.labels(operation=operation, success=str(success).lower()).observe(duration_seconds)


def track_db_operation(operation, success, duration_seconds):
    """Track database operation latency"""
    DB_OPERATION_LATENCY.labels(operation=operation, success=str(success).lower()).observe(duration_seconds)


def set_db_connection_count(count):
    """Set the current database connection count"""
    DB_CONNECTION_COUNT.set(count)


def set_circuit_state(service, state):
    """Set circuit breaker state (0=closed, 1=open, 2=half-open)"""
    state_value = {
        'CLOSED': 0,
        'OPEN': 1,
        'HALF_OPEN': 2
    }.get(state, -1)
    CIRCUIT_STATE.labels(service=service).set(state_value)


def track_circuit_failure(service):
    """Track circuit breaker failures"""
    CIRCUIT_FAILURE_COUNT.labels(service=service).inc()