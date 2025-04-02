# In backend/exchange-service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies - add libpq-dev for PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Generate gRPC stubs
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/exchange_simulator.proto

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    DB_HOST=postgres \
    DB_PORT=5432 \
    DB_NAME=opentp \
    DB_USER=opentp

# Note: DB_PASSWORD will be passed at runtime

# Expose ports
EXPOSE 50055 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import grpc; grpc.insecure_channel('localhost:50055')" || exit 1

# Run the application
CMD ["python", "-m", "source.main"]