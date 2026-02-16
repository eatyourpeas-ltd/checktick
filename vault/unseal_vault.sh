#!/bin/bash
# unseal_vault.sh - Decrypt Vault unseal keys

set -e

echo "=========================================="
echo "  HashiCorp Vault Unsealing Helper"
echo "=========================================="
echo ""
echo "This script decrypts the Vault unseal keys."
echo "You will need:"
echo "  - YubiKey 1 (Team Member A)"
echo "  - YubiKey 2 (Team Member B)"
echo "  - Share 3 from physical safe"
echo ""
echo "Prerequisites:"
echo "  - vault_unseal_share1.enc and vault_unseal_share1.key.enc (downloaded from Bitwarden)"
echo "  - vault_unseal_share2.enc and vault_unseal_share2.key.enc (downloaded from Bitwarden)"
echo ""
read -p "Press Enter when ready..."

# Detect PKCS11 module location
if [ -f "/usr/local/lib/libykcs11.dylib" ]; then
    PKCS11_MODULE="/usr/local/lib/libykcs11.dylib"
elif [ -f "/opt/homebrew/lib/libykcs11.dylib" ]; then
    PKCS11_MODULE="/opt/homebrew/lib/libykcs11.dylib"
else
    echo "Error: Could not find libykcs11.dylib"
    echo "Install with: brew install opensc"
    exit 1
fi

echo ""
echo "Step 1/3: Decrypting Vault unseal share 1"
echo "-------------------------------------------"
echo "Insert YubiKey 1 and press Enter..."
read

pkcs11-tool --module "$PKCS11_MODULE" \
  --slot 0 --id 03 --decrypt --mechanism RSA-PKCS \
  --input vault_unseal_share1.key.enc \
  --output aes_key1.bin --login

SHARE1=$(openssl enc -d -aes-256-cbc -pbkdf2 \
  -in vault_unseal_share1.enc -pass file:aes_key1.bin)
shred -u aes_key1.bin

echo "✓ Share 1 decrypted"

echo ""
echo "Step 2/3: Decrypting Vault unseal share 2"
echo "-------------------------------------------"
echo "Remove YubiKey 1, insert YubiKey 2, and press Enter..."
read

pkcs11-tool --module "$PKCS11_MODULE" \
  --slot 0 --id 03 --decrypt --mechanism RSA-PKCS \
  --input vault_unseal_share2.key.enc \
  --output aes_key2.bin --login

SHARE2=$(openssl enc -d -aes-256-cbc -pbkdf2 \
  -in vault_unseal_share2.enc -pass file:aes_key2.bin)
shred -u aes_key2.bin

echo "✓ Share 2 decrypted"

echo ""
echo "Step 3/3: Manual input required"
echo "-------------------------------------------"
echo "Retrieve share 3 from the physical safe"
echo ""

echo ""
echo "=========================================="
echo "  DECRYPTED VAULT UNSEAL KEYS"
echo "=========================================="
echo ""
echo "Share 1: $SHARE1"
echo ""
echo "Share 2: $SHARE2"
echo ""
echo "Share 3: [Retrieved from physical safe]"
echo ""
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. SSH to Northflank: ssh your-server"
echo "2. Run: vault operator unseal"
echo "3. Paste Share 1, then Share 2, then Share 3"
echo "4. Vault should unseal after the 3rd key"
echo ""
echo "Press Enter to clear shares from memory and exit..."
read

# Clear sensitive variables
unset SHARE1 SHARE2

echo "✓ Shares cleared from memory"
