#!/usr/bin/env bash
#
# verify-yubikey-shares.sh
#
# Verifies that the encrypted share files for a given YubiKey decrypt correctly
# and match the original plaintext files in temp_keys/.
#
# Usage:
#   ./vault/verify-yubikey-shares.sh <1|2>
#
# Run from the repository root with the relevant YubiKey inserted.
# You will be prompted for the YubiKey PIN twice (once per share).
#
# Prerequisites:
#   brew install opensc   # provides pkcs11-tool
#   brew install ykman

set -euo pipefail

# ── Arguments ────────────────────────────────────────────────────────────────

if [[ $# -ne 1 ]] || [[ "$1" != "1" && "$1" != "2" ]]; then
  echo "Usage: $0 <1|2>"
  echo "  1 = verify shares for YubiKey 1"
  echo "  2 = verify shares for YubiKey 2"
  exit 1
fi

KEY_NUM="$1"
TEMP_DIR="temp_keys"

# ── Detect pkcs11 library ─────────────────────────────────────────────────────

if [[ -f /opt/homebrew/lib/libykcs11.dylib ]]; then
  PKCS11_LIB=/opt/homebrew/lib/libykcs11.dylib   # Apple Silicon
elif [[ -f /usr/local/lib/libykcs11.dylib ]]; then
  PKCS11_LIB=/usr/local/lib/libykcs11.dylib       # Intel Mac
else
  echo "❌ Could not find libykcs11.dylib. Install opensc: brew install opensc"
  exit 1
fi

# ── Helper ────────────────────────────────────────────────────────────────────

PASS=0
FAIL=0
AES_TMP="${TEMP_DIR}/aes_key_verify_$$.bin"

cleanup() {
  [[ -f "$AES_TMP" ]] && shred -u "$AES_TMP" 2>/dev/null || true
}
trap cleanup EXIT

verify_share() {
  local label="$1"          # human-readable label
  local enc_file="$2"       # path to .enc file
  local key_enc_file="$3"   # path to .key.enc file
  local plain_file="$4"     # path to original plaintext .txt

  echo ""
  echo "── Verifying: ${label} ──"

  if [[ ! -f "$enc_file" ]]; then
    echo "❌ Missing encrypted file: ${enc_file}"
    FAIL=$((FAIL + 1))
    return
  fi
  if [[ ! -f "$key_enc_file" ]]; then
    echo "❌ Missing key file: ${key_enc_file}"
    FAIL=$((FAIL + 1))
    return
  fi
  if [[ ! -f "$plain_file" ]]; then
    echo "❌ Missing plaintext file: ${plain_file} (needed for comparison)"
    FAIL=$((FAIL + 1))
    return
  fi

  # Decrypt the AES key using the YubiKey private key (prompts for PIN)
  echo "   → Insert YubiKey ${KEY_NUM} if not already inserted. Enter PIN when prompted."
  pkcs11-tool --module "$PKCS11_LIB" \
    --slot 0 \
    --id 03 \
    --decrypt \
    --mechanism RSA-PKCS \
    --input  "$key_enc_file" \
    --output "$AES_TMP" \
    --login

  # Decrypt the share using the recovered AES key
  decrypted=$(openssl enc -d -aes-256-cbc -pbkdf2 \
    -in "$enc_file" \
    -pass file:"$AES_TMP")

  shred -u "$AES_TMP"

  original=$(cat "$plain_file")

  if [[ "$decrypted" == "$original" ]]; then
    echo "   ✅ ${label}: OK"
    PASS=$((PASS + 1))
  else
    echo "   ❌ ${label}: MISMATCH — decrypted content does not match original"
    FAIL=$((FAIL + 1))
  fi
}

# ── Run verifications ─────────────────────────────────────────────────────────

echo ""
echo "======================================"
echo " YubiKey ${KEY_NUM} share verification"
echo "======================================"

verify_share \
  "custodian_component_share${KEY_NUM}" \
  "${TEMP_DIR}/custodian_component_share${KEY_NUM}.enc" \
  "${TEMP_DIR}/custodian_component_share${KEY_NUM}.key.enc" \
  "${TEMP_DIR}/custodian_component_share${KEY_NUM}.txt"

verify_share \
  "vault_unseal_share${KEY_NUM}" \
  "${TEMP_DIR}/vault_unseal_share${KEY_NUM}.enc" \
  "${TEMP_DIR}/vault_unseal_share${KEY_NUM}.key.enc" \
  "${TEMP_DIR}/vault_unseal_share${KEY_NUM}.txt"

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "======================================"
echo " Results: ${PASS} passed, ${FAIL} failed"
echo "======================================"

if [[ $FAIL -gt 0 ]]; then
  echo ""
  echo "❌ Verification FAILED. Do NOT shred the public key or plaintext files."
  echo "   Re-run steps 7–8 to re-encrypt the affected share(s)."
  exit 1
else
  echo ""
  echo "✅ All shares verified. Safe to proceed to Step 10 (shred public key)."
  exit 0
fi
