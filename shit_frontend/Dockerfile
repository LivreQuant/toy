FROM node:18-alpine as build

WORKDIR /app

# Add build-time environment variable
ARG REACT_APP_AUTH_API_ENDPOINT=http://auth-service:50551
ENV REACT_APP_AUTH_API_ENDPOINT=$REACT_APP_AUTH_API_ENDPOINT

# Install dependencies
COPY package*.json .npmrc ./
RUN npm ci

# Copy source files (use .dockerignore to exclude node_modules, etc.)
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create a basic health check endpoint
RUN mkdir -p /usr/share/nginx/html/health && \
    echo "OK" > /usr/share/nginx/html/health/index.html

# Add a healthcheck directive
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O - http://localhost/health/ || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]