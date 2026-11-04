#!/bin/bash
# Generate self-signed TLS certificates for Vault
# For production, use proper CA-signed certificates

set -e

NAMESPACE="checktick"
SECRET_NAME="vault-tls"
DOMAIN="vault.checktick.internal"
DAYS_VALID=3650  # 10 years

echo "Generating TLS certificates for Vault..."

# Generate private key
openssl genrsa -out vault-key.pem 4096

# Generate certificate signing request
openssl req -new -key vault-key.pem -out vault-csr.pem \
  -subj "/C=GB/ST=England/L=London/O=CheckTick/OU=IT/CN=${DOMAIN}"

# Generate self-signed certificate
openssl x509 -req -days ${DAYS_VALID} \
  -in vault-csr.pem \
  -signkey vault-key.pem \
  -out vault-cert.pem \
  -extfile <(printf "subjectAltName=DNS:${DOMAIN},DNS:vault,DNS:vault-0.vault-internal,DNS:vault-1.vault-internal,DNS:vault-2.vault-internal,DNS:localhost,IP:127.0.0.1")

echo "✅ Certificates generated"

# Create Kubernetes secret (if kubectl available and cluster accessible)
if command -v kubectl &> /dev/null; then
    echo ""
    echo "Checking Kubernetes cluster connection..."
    if kubectl cluster-info &> /dev/null; then
        echo "Creating Kubernetes secret..."
        kubectl create secret generic ${SECRET_NAME} \
          --from-file=tls.crt=vault-cert.pem \
          --from-file=tls.key=vault-key.pem \
          --namespace=${NAMESPACE} \
          --dry-run=client -o yaml | kubectl apply -f -
        echo "✅ Secret ${SECRET_NAME} created in namespace ${NAMESPACE}"
    else
        echo "⚠️  kubectl not connected to cluster"
        echo ""
        echo "To create the secret once connected:"
        echo "  1. Set KUBECONFIG to your cluster's kubeconfig"
        echo "  2. Create the secret:"
        echo "     kubectl create secret generic ${SECRET_NAME} \\"
        echo "       --from-file=tls.crt=vault-cert.pem \\"
        echo "       --from-file=tls.key=vault-key.pem \\"
        echo "       --namespace=${NAMESPACE}"
    fi
else
    echo ""
    echo "⚠️  kubectl not found - create the secret manually:"
    echo "  1. Install kubectl and connect to your cluster"
    echo "  2. kubectl create secret generic ${SECRET_NAME} \\"
    echo "       --from-file=tls.crt=vault-cert.pem \\"
    echo "       --from-file=tls.key=vault-key.pem \\"
    echo "       --namespace=${NAMESPACE}"
fi

# Clean up
rm vault-csr.pem

echo ""
echo "Certificate files:"
echo "  vault-cert.pem - Public certificate"
echo "  vault-key.pem  - Private key"
echo ""
echo "⚠️  For production, use proper CA-signed certificates!"
