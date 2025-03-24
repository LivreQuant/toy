FROM docker.io/bitnami/postgresql:11.8.0-debian-10-r19

# Add health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD pg_isready -U opentp -d opentp || exit 1

# Set environment variables for secure defaults
ENV POSTGRESQL_PASSWORD=samaral
ENV POSTGRESQL_DATABASE=opentp
ENV POSTGRESQL_USERNAME=opentp

COPY schemas/sessions.sql /docker-entrypoint-initdb.d/02-sessions-schema.sql
COPY schemas/simulator_sessions.sql /docker-entrypoint-initdb.d/02-simulator-sessions-schema.sql
COPY schemas/connection_monitoring.sql /docker-entrypoint-initdb.d/02-connection-monitoring-schema.sql
COPY schemas/users.sql /docker-entrypoint-initdb.d/01-users-schema.sql

# Copy data files
COPY data/users.sql /docker-entrypoint-initdb.d/05-users-data.sql
COPY data/auth_functions.sql /docker-entrypoint-initdb.d/06-auth-functions.sql
COPY data/sessions_init.sql /docker-entrypoint-initdb.d/06-sessions-init.sql
