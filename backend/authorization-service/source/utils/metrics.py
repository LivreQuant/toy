# source/utils/metrics.py
import logging
import os
import threading
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Authentication Metrics
LOGIN_ATTEMPTS = Counter(
    'auth_login_attempts_total', 
    'Total number of login attempts',
    ['result', 'username']
)

LOGIN_DURATION = Histogram(
    'auth_login_duration_seconds', 
    'Duration of login process',
    ['result']
)

TOKEN_ISSUED = Counter(
    'auth_tokens_issued_total', 
    'Total number of tokens issued',
    ['type', 'user_role']
)

TOKEN_VALIDATION = Counter(
    'auth_token_validations_total', 
    'Total number of token validations',
    ['result']
)

DB_CONNECTION_ATTEMPTS = Counter(
    'auth_db_connection_attempts_total', 
    'Total database connection attempts',
    ['result']
)

def setup_metrics():
    """Start Prometheus metrics server"""
    logger = logging.getLogger('metrics')
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
def track_login_attempt(username, success):
    """Track login attempt metrics"""
    result = 'success' if success else 'failure'
    LOGIN_ATTEMPTS.labels(result=result, username=username).inc()

def track_login_duration(start_time, success):
    """Track login duration"""
    result = 'success' if success else 'failure'
    LOGIN_DURATION.labels(result=result).observe(time.time() - start_time)

def track_token_issued(token_type, user_role):
    """Track token issuance"""
    TOKEN_ISSUED.labels(type=token_type, user_role=user_role).inc()

def track_token_validation(is_valid):
    """Track token validation"""
    result = 'valid' if is_valid else 'invalid'
    TOKEN_VALIDATION.labels(result=result).inc()

def track_db_connection(success):
    """Track database connection attempts"""
    result = 'success' if success else 'failure'
    DB_CONNECTION_ATTEMPTS.labels(result=result).inc()