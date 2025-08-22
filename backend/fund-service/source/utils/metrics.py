# source/utils/metrics.py
import logging
import os
import threading
from prometheus_client import Counter, Histogram, Gauge, start_http_server

logger = logging.getLogger('metrics')

# Conviction Lifecycle Metrics
CONVICTION_CREATED = Counter(
    'conviction_created_total',
    'Total number of convictions created',
    ['conviction_type', 'symbol', 'side']
)

BOOK_CREATED = Counter(
    'book_created_total',
    'Total number of books created',
    ['user_id']
)

CONVICTION_SUBMITTED = Counter(
    'conviction_submitted_total',
    'Total number of convictions submitted to exchange',
    ['conviction_type', 'symbol', 'side']
)

CONVICTION_SUBMISSION_LATENCY = Histogram(
    'conviction_submission_latency_seconds',
    'Latency of conviction submission process',
    ['conviction_type', 'success']
)

CONVICTION_STATUS_CHANGES = Counter(
    'conviction_status_changes_total',
    'Total number of conviction status changes',
    ['from_status', 'to_status']
)

# User Activity Metrics
USER_CONVICTION_COUNT = Counter(
    'book_conviction_count_total',
    'Total number of conviction per book',
    ['book_id']
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

FUND_CREATED = Counter(
    'fund_created_total',
    'Total number of funds created',
    ['user_id']
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
def track_conviction_created(conviction_type, symbol, side):
    """Track conviction creation"""
    CONVICTION_CREATED.labels(conviction_type=conviction_type, symbol=symbol, side=side).inc()


def track_conviction_submitted(conviction_type, symbol, side):
    """Track conviction submission to exchange"""
    CONVICTION_SUBMITTED.labels(conviction_type=conviction_type, symbol=symbol, side=side).inc()


def track_conviction_submission_latency(conviction_type, success, duration_seconds):
    """Track conviction submission latency"""
    CONVICTION_SUBMISSION_LATENCY.labels(conviction_type=conviction_type, success=str(success).lower()).observe(duration_seconds)


def track_conviction_status_change(from_status, to_status):
    """Track conviction status changes"""
    CONVICTION_STATUS_CHANGES.labels(from_status=from_status, to_status=to_status).inc()


def track_book_conviction(book_id):
    """Track conviction per user"""
    USER_CONVICTION_COUNT.labels(book_id=book_id).inc()


def track_book_created(user_id):
    """Track book creation"""
    BOOK_CREATED.labels(user_id=user_id).inc()

    
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

def track_fund_created(user_id):
    """Track fund creation"""
    FUND_CREATED.labels(user_id=user_id).inc()
    