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

# Install gRPC tools for protobuf compilation
RUN pip install --no-cache-dir grpcio-tools

# Copy protos and compile them
COPY ./protos /app/protos
RUN mkdir -p /app/source/api && \
    python -m grpc_tools.protoc -I./protos \
    --python_out=./source/api \
    --grpc_python_out=./source/api \
    ./protos/exchange_simulator.proto

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
    DB_MIN_CONNECTIONS="2" \
    DB_MAX_CONNECTIONS="20" \
    # Redis Configuration
    REDIS_HOST="redis" \
    REDIS_PORT="6379" \
    REDIS_DB="0" \
    # Service Configuration
    REST_PORT="8001" \
    AUTH_SERVICE_URL="http://auth-service:8000" \
    # Logging and Security
    LOG_LEVEL="INFO"

# Expose REST port
EXPOSE 8001

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the service
CMD ["python", "main.py"]