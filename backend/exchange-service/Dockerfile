# Dockerfile - Optimized for Kubernetes deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy source code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# Expose ports
EXPOSE 50055 50056 50052 9090

# 50055: gRPC service port
# 50056: Health check port
# 50052: Conviction service port (for order processing)
# 9090: Metrics port

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:50056/health || exit 1

# Run the application
CMD ["python", "source/main.py"]