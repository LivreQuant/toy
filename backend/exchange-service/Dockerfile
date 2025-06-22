# Updated Dockerfile
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

# Upgrade pip and tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PYTHONPATH=/app \
    MARKET_DATA_SERVICE_URL=market-data-service:50060

# Expose REST & METRIC port
EXPOSE 50055 50056 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:50056/health || exit 1

# Run the application
CMD ["python", "source/main.py"]