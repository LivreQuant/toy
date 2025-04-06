FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy the source code (which already includes compiled proto files)
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    ENVIRONMENT="development" \
    PYTHONPATH=/app \
    # Database Configuration
    DB_HOST="postgres" \
    DB_PORT="5432" \
    DB_NAME="opentp" \
    DB_USER="opentp" \
    DB_PASSWORD="samaral" \
    DB_MIN_CONNECTIONS="2" \
    DB_MAX_CONNECTIONS="20" \
    # Service Configuration
    REST_PORT="8001" \
    AUTH_SERVICE_URL="http://auth-service:8000" \
    SESSION_SERVICE_URL="http://session-service:8080" \
    # Tracing Configuration
    ENABLE_TRACING="true" \
    METRICS_PORT="9091" \
    OTEL_SERVICE_NAME="order-service" \
    OTEL_EXPORTER_JAEGER_ENDPOINT="http://jaeger-collector:14268/api/traces" \
    # Logging and Security
    LOG_LEVEL="INFO"

# Expose REST port
EXPOSE 8001

# Expose metrics port
EXPOSE 9091

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the service
CMD ["python", "source/main.py"]