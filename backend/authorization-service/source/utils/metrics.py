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

# Profile Metrics
PROFILE_UPDATES = Counter(
    'auth_profile_updates_total',
    'Total number of profile updates',
    ['result']
)

# User Registration Metrics
SIGNUP_ATTEMPTS = Counter(
    'auth_signup_attempts_total',
    'Total number of signup attempts',
    ['result']
)

EMAIL_VERIFICATION = Counter(
    'auth_email_verifications_total',
    'Total number of email verification attempts',
    ['result']
)

# Password Management Metrics
PASSWORD_RESET_REQUESTS = Counter(
    'auth_password_reset_requests_total',
    'Total number of password reset requests',
    ['result']
)

PASSWORD_RESETS = Counter(
    'auth_password_resets_total',
    'Total number of password reset completions',
    ['result']
)

# Feedback Metrics
FEEDBACK_SUBMISSIONS = Counter(
    'auth_feedback_submissions_total',
    'Total number of feedback submissions',
    ['result', 'feedback_type']
)

# Token Management Metrics
REFRESH_TOKEN_ATTEMPTS = Counter(
    'auth_refresh_token_attempts_total',
    'Total number of token refresh attempts',
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


def track_profile_update(success):
    """Track profile update metrics"""
    result = 'success' if success else 'failure'
    PROFILE_UPDATES.labels(result=result).inc()


def track_signup_attempt(success):
    """Track signup attempt metrics"""
    result = 'success' if success else 'failure'
    SIGNUP_ATTEMPTS.labels(result=result).inc()


def track_email_verification(success):
    """Track email verification metrics"""
    result = 'success' if success else 'failure'
    EMAIL_VERIFICATION.labels(result=result).inc()


def track_password_reset_request(success):
    """Track password reset request metrics"""
    result = 'success' if success else 'failure'
    PASSWORD_RESET_REQUESTS.labels(result=result).inc()


def track_password_reset(success):
    """Track password reset completion metrics"""
    result = 'success' if success else 'failure'
    PASSWORD_RESETS.labels(result=result).inc()


def track_feedback_submission(success, feedback_type='general'):
    """Track feedback submission metrics"""
    result = 'success' if success else 'failure'
    FEEDBACK_SUBMISSIONS.labels(result=result, feedback_type=feedback_type).inc()


def track_refresh_token_attempt(success):
    """Track token refresh attempt metrics"""
    result = 'success' if success else 'failure'
    REFRESH_TOKEN_ATTEMPTS.labels(result=result).inc()
