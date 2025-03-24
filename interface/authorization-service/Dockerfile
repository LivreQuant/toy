# Dockerfile
FROM python:3.11-slim

WORKDIR /app

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
    # Database Configuration
    DB_HOST="postgres" \
    DB_PORT="5432" \
    DB_NAME="opentp" \
    DB_USER="opentp" \
    DB_PASSWORD="samaral" \
    DB_MIN_CONNECTIONS="1" \
    DB_MAX_CONNECTIONS="10" \
    # Service Port
    REST_PORT="8000" \
    # Logging and Security
    LOG_LEVEL="INFO" \
    JWT_SECRET="development-secret-key" \
    JWT_REFRESH_SECRET="development-refresh-secret-key" \
    ACCESS_TOKEN_EXPIRY="3600" \
    REFRESH_TOKEN_EXPIRY="2592000"

# Expose REST port
EXPOSE 8000

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the service
CMD ["python", "main.py"]