FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install psutil for health checks
RUN pip install --no-cache-dir psutil

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code with proper directory structure
COPY source/ ./source/

# Expose ports (update these to match your config)
EXPOSE 8080 8088

# Set health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the service
CMD ["python", "-m", "source.server"]