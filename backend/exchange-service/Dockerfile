FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gRPC tools
RUN pip install --no-cache-dir grpcio-tools==1.54.0

# Copy protos
COPY proto/ ./proto/

# Generate gRPC code from proto
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/exchange_simulator.proto

# Copy source code
COPY source/ ./source/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=50055 \
    HOST=0.0.0.0 \
    INACTIVITY_TIMEOUT_SECONDS=300 \
    AUTO_TERMINATE=true \
    LOG_LEVEL=INFO

# Expose the port
EXPOSE 50055
EXPOSE 50056

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:50056/health || exit 1

# Run the application
ENTRYPOINT ["python", "-m", "source.main"]