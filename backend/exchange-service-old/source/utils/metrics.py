import logging
import threading
from prometheus_client import start_http_server, Counter, Histogram, Gauge

from source.config import config

logger = logging.getLogger('metrics')

# gRPC Method Metrics
GRPC_REQUESTS = Counter(
    'exchange_grpc_requests_total', 
    'Total gRPC requests', 
    ['method']
)

GRPC_REQUEST_DURATION = Histogram(
    'exchange_grpc_request_duration_seconds', 
    'gRPC request duration', 
    ['method']
)

# Simulator Metrics
ACTIVE_SIMULATORS = Gauge(
    'exchange_active_simulators', 
    'Number of active simulators'
)

MARKET_DATA_UPDATES = Counter(
    'exchange_market_data_updates_total', 
    'Total market data updates'
)

# Add these metrics
STREAM_CONNECTIONS = Counter(
    'exchange_stream_connections_total', 
    'Total stream connections established', 
    ['client_id']
)

STREAM_UPDATES_SENT = Counter(
    'exchange_stream_updates_sent_total', 
    'Total market data updates sent', 
    ['client_id']
)

def setup_metrics():
    """Start Prometheus metrics server"""
    try:
        def _start_metrics_server():
            start_http_server(config.metrics.port)

        metrics_thread = threading.Thread(
            target=_start_metrics_server,
            daemon=True
        )
        metrics_thread.start()
        logger.info(f"Metrics server started on port {config.metrics.port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")

def track_grpc_request(method):
    """Track gRPC request metrics"""
    GRPC_REQUESTS.labels(method=method).inc()

def track_grpc_request_duration(method, duration):
    """Track gRPC request duration"""
    GRPC_REQUEST_DURATION.labels(method=method).observe(duration)

def track_active_simulators(count):
    """Track number of active simulators"""
    ACTIVE_SIMULATORS.set(count)

def track_market_data_update():
    """Track market data updates"""
    MARKET_DATA_UPDATES.inc()