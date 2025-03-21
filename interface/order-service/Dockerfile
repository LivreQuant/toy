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
    NEW_USER="true" \
    # Service Ports
    CENTRAL_DESK_INCOMING_PORT="51558" \
    CENTRAL_DESK_OUTGOING_PORT="51559" \
    MARKET_DATA_PORT="51552" \
    ORDER_ENTRY_PORT="51554" \
    HEALTH_CHECK_PORT="8088" \
    # Service URLs
    MARKET_DATA_URL="market-data-service:51552" \
    ORDER_ENTRY_URL="order-entry-service:51554" \
    # Logging and Security
    LOG_LEVEL="INFO" \
    JWT_SECRET="development-secret-key" \
    VERIFY_TOKEN="true" \
    # Application Modes
    USE_DATABASE="true" \
    EVENT_PROCESSING_DELAY="0.1" \
    INITIALIZATION_TIMEOUT="60"

# Expose all necessary ports
EXPOSE 51558 51559 8088

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8088/health || exit 1

# Run the service
CMD ["python", "-m", "source.main"]