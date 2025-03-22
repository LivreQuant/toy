# Create a directory for certificates
mkdir -p certs

# Generate CA key and certificate
openssl genrsa -out certs/ca.key 4096
openssl req -new -x509 -key certs/ca.key -sha256 -subj "/CN=Trading CA" -out certs/ca.crt -days 365

# Generate server key and CSR (Certificate Signing Request)
openssl genrsa -out certs/server.key 4096
openssl req -new -key certs/server.key -sha256 \
    -subj "/CN=*.trading-service.svc.cluster.local" \
    -reqexts SAN \
    -config <(cat /etc/ssl/openssl.cnf \
        <(printf "\n[SAN]\nsubjectAltName=DNS:auth-service,DNS:session-manager,DNS:*.trading-service.svc.cluster.local,DNS:localhost")) \
    -out certs/server.csr

# Sign the server certificate with our CA
openssl x509 -req -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key \
    -CAcreateserial -out certs/server.crt -days 365 \
    -extfile <(cat /etc/ssl/openssl.cnf \
        <(printf "\n[SAN]\nsubjectAltName=DNS:auth-service,DNS:session-manager,DNS:*.trading-service.svc.cluster.local,DNS:localhost")) \
    -extensions SAN

# Generate client key and certificate (for mutual TLS)
openssl genrsa -out certs/client.key 4096
openssl req -new -key certs/client.key -out certs/client.csr \
    -subj "/CN=trading-client" -config <(cat /etc/ssl/openssl.cnf)

openssl x509 -req -in certs/client.csr -CA certs/ca.crt -CAkey certs/ca.key \
    -CAcreateserial -out certs/client.crt -days 365