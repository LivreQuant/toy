FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# Added options to ignore validation date issues sometimes seen in build environments
RUN apt-get -o Acquire::Check-Valid-Until=false \
    -o Acquire::Check-Date=false update \
    && apt-get -y --no-install-recommends install \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Added Step ---
# Upgrade pip and install wheel/setuptools BEFORE installing requirements
# This fixes build issues for packages like 'thrift' that need build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
# --- End Added Step ---

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PYTHONPATH=/app

# Expose ports
EXPOSE 50055 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import grpc; grpc.insecure_channel('localhost:50055')" || exit 1

# Run the application
CMD ["python", "source/main.py"]