FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy protobuf files (from your exchange simulator)
COPY exchange_simulator.proto .

# Generate Python code from the proto file
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. exchange_simulator.proto

# Copy source code
COPY main.py .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    SYMBOLS="AAPL,GOOGL,MSFT,AMZN,TSLA,FB" \
    UPDATE_INTERVAL="60" \
    API_HOST="0.0.0.0" \
    API_PORT="50060"

# Run the service
CMD ["python", "main.py"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-50060}/health || exit 1