FROM python:3.11-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system appuser && \
    adduser --system --ingroup appuser appuser

# Install system dependencies
RUN apt-get -o Acquire::Check-Valid-Until=false \
    -o Acquire::Check-Date=false update \
    && apt-get -y --no-install-recommends install \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy the source code
COPY . .

# Set comprehensive default environment variables
ENV ENVIRONMENT="development" \
    PYTHONPATH=/app \
    # Database Configuration
    DB_HOST="postgres" \
    DB_PORT="5432" \
    DB_NAME="opentp" \
    DB_USER="opentp" \
    DB_PASSWORD="samaral" \
    DB_MIN_CONNECTIONS="1" \
    DB_MAX_CONNECTIONS="10" \
    # Tracing Configuration
    ENABLE_TRACING="true" \
    METRICS_PORT="9090" \
    # Service Configuration
    REST_PORT="8001" \
    AUTH_SERVICE_URL="http://auth-service:8000" \
    # Logging and Security
    LOG_LEVEL="DEBUG"

# Create log directory and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Expose REST port
EXPOSE 8001

# Expose METRIC port
EXPOSE 9090

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the service
CMD ["python", "source/main.py"]