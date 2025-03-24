#!/bin/bash

# Generate a secure JWT secret
JWT_SECRET=$(openssl rand -hex 32)

# Create database secret from template
cat config/secrets/database.template.yaml | sed "s/REPLACE_ME/password/g" > config/secrets/database.yaml

# Create JWT secret from template
cat config/secrets/auth-jwt-secret.template.yaml | sed "s/REPLACE_ME_WITH_STRONG_SECRET_KEY/$JWT_SECRET/g" > config/secrets/auth-jwt-secret.yaml

# Apply secrets
kubectl apply -f config/secrets/database.yaml
kubectl apply -f config/secrets/auth-jwt-secret.yaml

echo "Environment setup complete!"