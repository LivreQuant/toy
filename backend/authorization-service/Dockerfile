FROM python:3.11-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system appuser && \
    adduser --system --ingroup appuser appuser

# Install system dependencies
RUN apt-get -o Acquire::Check-Valid-Until=false \
    -o Acquire::Check-Date=false update \
    && apt-get -y --no-install-recommends install \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy source code
COPY . .

# Set only essential environment variables, others will come from .env files
ENV PYTHONPATH=/app

# Create log directory and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Expose REST & METRIC port
EXPOSE 8001 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "source/main.py"]