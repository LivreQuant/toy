# Add a network policy to temporarily block traffic
kubectl apply -f - << EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-service
spec:
  podSelector:
    matchLabels:
      app: session-manager
  policyTypes:
  - Ingress
  - Egress
EOF

# Remove the policy to restore traffic
kubectl delete networkpolicy block-service