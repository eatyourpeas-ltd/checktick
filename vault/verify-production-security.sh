#!/bin/bash
# Production Security Verification Script for HashiCorp Vault
# Run this after initial setup to verify security configuration

set -e

echo "═══════════════════════════════════════════════════════"
echo "  Vault Production Security Verification"
echo "═══════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILURES=0
WARNINGS=0

# Check if VAULT_ADDR is set
if [ -z "$VAULT_ADDR" ]; then
    echo -e "${RED}✗ VAULT_ADDR not set${NC}"
    echo "  export VAULT_ADDR=https://your-vault-url:8200"
    exit 1
fi

echo "Vault: $VAULT_ADDR"
echo ""

# Test 1: Verify root token is revoked
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Root Token Revocation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "$VAULT_TOKEN" ]; then
    # Check if current token is root
    TOKEN_INFO=$(vault token lookup -format=json 2>/dev/null || echo '{}')
    IS_ROOT=$(echo "$TOKEN_INFO" | jq -r '.data.policies[]' | grep -c "^root$" || true)

    if [ "$IS_ROOT" -gt 0 ]; then
        echo -e "${RED}✗ Current VAULT_TOKEN has root policy!${NC}"
        echo "  Root token should be revoked after setup."
        echo "  Run: vault token revoke \$VAULT_TOKEN"
        ((FAILURES++))
    else
        echo -e "${GREEN}✓ Current token is not root${NC}"
    fi
else
    echo -e "${YELLOW}⚠ VAULT_TOKEN not set (expected for AppRole auth)${NC}"
fi

# Test 2: Verify AppRole configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. AppRole Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
APPROLE_CONFIG=$(vault read -format=json auth/approle/role/checktick-app 2>/dev/null || echo '{}')

TOKEN_TTL=$(echo "$APPROLE_CONFIG" | jq -r '.data.token_ttl')
TOKEN_MAX_TTL=$(echo "$APPROLE_CONFIG" | jq -r '.data.token_max_ttl')
SECRET_ID_TTL=$(echo "$APPROLE_CONFIG" | jq -r '.data.secret_id_ttl')

if [ "$TOKEN_TTL" = "3600" ]; then
    echo -e "${GREEN}✓ Token TTL: 1 hour${NC}"
else
    echo -e "${YELLOW}⚠ Token TTL: ${TOKEN_TTL}s (expected: 3600)${NC}"
    ((WARNINGS++))
fi

if [ "$TOKEN_MAX_TTL" = "28800" ]; then
    echo -e "${GREEN}✓ Token Max TTL: 8 hours${NC}"
else
    echo -e "${RED}✗ Token Max TTL: ${TOKEN_MAX_TTL}s (expected: 28800)${NC}"
    ((FAILURES++))
fi

if [ "$SECRET_ID_TTL" = "7776000" ]; then
    echo -e "${GREEN}✓ Secret ID TTL: 90 days${NC}"
elif [ "$SECRET_ID_TTL" = "0" ]; then
    echo -e "${RED}✗ Secret ID TTL: Never expires (security risk!)${NC}"
    echo "  Update with: vault write auth/approle/role/checktick-app secret_id_ttl=90d"
    ((FAILURES++))
else
    echo -e "${YELLOW}⚠ Secret ID TTL: ${SECRET_ID_TTL}s${NC}"
    ((WARNINGS++))
fi

# Test 3: Audit logging
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Audit Logging"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
AUDIT_DEVICES=$(vault audit list -format=json 2>/dev/null || echo '{}')
FILE_AUDIT=$(echo "$AUDIT_DEVICES" | jq -r '.["file/"]')

if [ "$FILE_AUDIT" != "null" ]; then
    echo -e "${GREEN}✓ File audit logging enabled${NC}"
    echo "  Path: $(echo "$AUDIT_DEVICES" | jq -r '.["file/"].options.file_path')"
else
    echo -e "${RED}✗ File audit logging not enabled${NC}"
    echo "  Enable with: vault audit enable file file_path=/vault/logs/audit.log"
    ((FAILURES++))
fi

# Test 4: TLS Configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. TLS Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ "$VAULT_ADDR" == https://* ]]; then
    echo -e "${GREEN}✓ HTTPS enabled${NC}"

    # Test TLS connection
    if timeout 5 openssl s_client -connect ${VAULT_ADDR#https://} </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
        echo -e "${GREEN}✓ Valid TLS certificate${NC}"
    else
        echo -e "${YELLOW}⚠ TLS certificate validation failed (may be self-signed)${NC}"
        echo "  Ensure VAULT_TLS_VERIFY is properly configured in application"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}✗ HTTP only (no TLS)${NC}"
    echo "  Production deployments must use HTTPS"
    ((FAILURES++))
fi

# Test 5: Platform master key exists
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Platform Master Key"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PLATFORM_KEY=$(vault kv get -format=json secret/platform/master-key 2>/dev/null || echo '{}')

if [ "$(echo "$PLATFORM_KEY" | jq -r '.data.data.vault_component')" != "null" ]; then
    echo -e "${GREEN}✓ Platform master key configured${NC}"
    CREATED=$(echo "$PLATFORM_KEY" | jq -r '.data.data.created_at')
    echo "  Created: $CREATED"
else
    echo -e "${RED}✗ Platform master key not found${NC}"
    echo "  Run: python vault/setup_vault.py"
    ((FAILURES++))
fi

# Test 6: Sealed status
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Vault Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HEALTH=$(curl -sk ${VAULT_ADDR}/v1/sys/health || echo '{"sealed":true}')
SEALED=$(echo "$HEALTH" | jq -r '.sealed')
INITIALIZED=$(echo "$HEALTH" | jq -r '.initialized')

if [ "$INITIALIZED" = "true" ]; then
    echo -e "${GREEN}✓ Vault initialized${NC}"
else
    echo -e "${RED}✗ Vault not initialized${NC}"
    ((FAILURES++))
fi

if [ "$SEALED" = "false" ]; then
    echo -e "${GREEN}✓ Vault unsealed${NC}"
else
    echo -e "${RED}✗ Vault is sealed${NC}"
    echo "  Unseal with: vault operator unseal"
    ((FAILURES++))
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════════════════"

if [ $FAILURES -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Vault is ready for production."
    exit 0
elif [ $FAILURES -eq 0 ]; then
    echo -e "${YELLOW}⚠ ${WARNINGS} warning(s)${NC}"
    echo ""
    echo "Review warnings above before production deployment."
    exit 0
else
    echo -e "${RED}✗ ${FAILURES} failure(s), ${WARNINGS} warning(s)${NC}"
    echo ""
    echo "Fix critical issues before production deployment."
    exit 1
fi
