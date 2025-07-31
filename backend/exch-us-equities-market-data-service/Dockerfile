FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (including pre-generated protobuf files)
COPY source/ source/

# Copy market configuration files
COPY tests/ tests/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Market Data Configuration
    CONFIG_FILE="test_0.json" \
    API_HOST="0.0.0.0" \
    API_PORT="50060" \
    # Database Configuration
    DB_HOST="postgres" \
    DB_PORT="5432" \
    DB_NAME="opentp" \
    DB_USER="opentp" \
    DB_PASSWORD="samaral" \
    # Logging Configuration
    LOG_LEVEL="INFO"

# Expose gRPC port and health check port
EXPOSE 50060 50061

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:50061/health || exit 1

# Run the application
CMD ["python", "-m", "source.main"]