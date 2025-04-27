FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client for health checks
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy protobuf files and generate Python code
COPY main/services/market_exchange_interface.proto .
RUN mkdir -p source/api/grpc && \
    python -m grpc_tools.protoc -I. --python_out=source/api/grpc --grpc_python_out=source/api/grpc market_exchange_interface.proto

# Add wait-for script to ensure database is ready before starting the app
COPY wait-for-postgres.sh .
RUN chmod +x wait-for-postgres.sh

# Copy source code
COPY source/ source/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    SYMBOLS="AAPL,GOOGL,MSFT,AMZN,TSLA,FB" \
    UPDATE_INTERVAL="60" \
    API_HOST="0.0.0.0" \
    API_PORT="50060" \
    DB_HOST="postgres" \
    DB_PORT="5432" \
    DB_NAME="marketdata" \
    DB_USER="postgres" \
    DB_PASSWORD="postgres"

# Wait for PostgreSQL and start the service
CMD ["sh", "-c", "./wait-for-postgres.sh && python -m source.main"]

# Health check using gRPC reflection and database connection
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER && python -c "import grpc; grpc.insecure_channel('localhost:${API_PORT:-50060}')" || exit 1