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

# Install gRPC tools for protobuf compilation
RUN pip install --no-cache-dir grpcio-tools

# Copy protos and compile them
COPY ./protos /app/protos
RUN mkdir -p /app/source/api/grpc && \
    python -m grpc_tools.protoc -I./protos \
    --python_out=./source/api/grpc \
    --grpc_python_out=./source/api/grpc \
    ./protos/exchange_simulator.proto \
    && sed -i 's/import main_dot_exchange__simulator__pb2/import source.api.grpc.exchange_simulator_pb2 as main_dot_exchange__simulator__pb2/g' \
    ./source/api/grpc/exchange_simulator_pb2_grpc.py

# Copy the source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    ENVIRONMENT="development" \
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
    # Logging and Security
    LOG_LEVEL="INFO"

# Expose REST port
EXPOSE 8001

# Health check using our HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the service
CMD ["python", "source/main.py"]