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
        echo "To create secret via Northflank CLI:"
        echo "  1. Install Northflank CLI: npm install -g @northflank/cli"
        echo "  2. Login: northflank login"
        echo "  3. Get kubeconfig: northflank kubeconfig get --project checktick > ~/.kube/northflank-config"
        echo "  4. Set context: export KUBECONFIG=~/.kube/northflank-config"
        echo "  5. Create secret:"
        echo "     kubectl create secret generic ${SECRET_NAME} \\"
        echo "       --from-file=tls.crt=vault-cert.pem \\"
        echo "       --from-file=tls.key=vault-key.pem \\"
        echo "       --namespace=${NAMESPACE}"
        echo ""
        echo "Or upload manually via Northflank Dashboard:"
        echo "  1. Go to your project → Secrets"
        echo "  2. Click 'Add Secret' → 'TLS Certificate'"
        echo "  3. Name: ${SECRET_NAME}"
        echo "  4. Upload vault-cert.pem as Certificate"
        echo "  5. Upload vault-key.pem as Private Key"
    fi
else
    echo ""
    echo "⚠️  kubectl not found - create secret manually via Northflank Dashboard:"
    echo "  1. Go to your project → Secrets"
    echo "  2. Click 'Add Secret' → 'TLS Certificate'"
    echo "  3. Name: ${SECRET_NAME}"
    echo "  4. Upload vault-cert.pem as Certificate"
    echo "  5. Upload vault-key.pem as Private Key"
fi

# Clean up
rm vault-csr.pem

echo ""
echo "Certificate files:"
echo "  vault-cert.pem - Public certificate"
echo "  vault-key.pem  - Private key"
echo ""
echo "⚠️  For production, use proper CA-signed certificates!"
