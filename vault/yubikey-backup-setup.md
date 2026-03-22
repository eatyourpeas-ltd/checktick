# YubiKey Backup Setup

Step-by-step guide for configuring new or backup YubiKeys to encrypt the custodian component shares and Vault unseal keys.

---

## Assumptions

- The custodian component has already been split into 4 Shamir shares, saved as plaintext files:
  - `temp_keys/custodian_component_share1.txt`
  - `temp_keys/custodian_component_share2.txt`
  - `temp_keys/custodian_component_share3.txt`
  - `temp_keys/custodian_component_share4.txt`

If this needs doing, it can be done using the full custodian component:

```bash
docker compose exec web python manage.py split_custodian_component \
    --custodian-component a1b2c3d4e5f67890abcdef1234567890... \
    --shares 4 \
    --threshold 3
```

- The Vault unseal keys have been saved as plaintext files:
  - `temp_keys/vault_unseal_share1.txt`
  - `temp_keys/vault_unseal_share2.txt`
  - `temp_keys/vault_unseal_share3.txt`
  - `temp_keys/vault_unseal_share4.txt`
- `ykman` (YubiKey Manager CLI) is installed: `brew install ykman`
- `openssl` is available (built in to macOS)
- You are working from the root of the `checktick` repository
- Only **one YubiKey is inserted at a time**

> ⚠️ **Never commit any `.txt`, `.pem`, `.bin`, `.enc`, or `.key.enc` files to git.**
> Ensure `temp_keys/` is in `.gitignore`.

---

## YubiKey 1

### Step 1: Reset PIV application

```bash
ykman piv reset
```

Confirm when prompted. This wipes all existing PIV credentials.

### Step 2: Set Management Key

```bash
ykman piv access change-management-key --generate --protect
```

This generates a random management key and protects it with the PIN.

### Step 3: Set PIN

```bash
ykman piv access change-pin
```

- Default PIN: `123456`
- Change to a strong 6–8 digit PIN
- Record the PIN securely in your password manager — **separately from the YubiKey**

### Step 4: Set PUK (PIN Unblocking Key)

```bash
ykman piv access change-puk
```

- Default PUK: `12345678`
- Change to a strong 8 digit code
- Record the PUK securely in your password manager — **separately from the YubiKey**

### Step 5: Generate RSA-2048 key pair

```bash
ykman piv keys generate --algorithm RSA2048 9d temp_keys/pubkey1.pem
```

The private key is generated **on the YubiKey** and never exported. `pubkey1.pem` is the public key, written to disk.

### Step 6: Create self-signed certificate

```bash
ykman piv certificates generate --subject "CN=Vault Share Key 1" 9d temp_keys/pubkey1.pem
```

---

### Step 7: Encrypt custodian component share 1

```bash
openssl rand -out temp_keys/aes_key.bin 32

cat temp_keys/custodian_component_share1.txt | \
  openssl enc -aes-256-cbc -salt -pbkdf2 \
  -pass file:temp_keys/aes_key.bin \
  -out temp_keys/custodian_component_share1.enc

openssl pkeyutl -encrypt \
  -pubin -inkey temp_keys/pubkey1.pem \
  -in temp_keys/aes_key.bin \
  -out temp_keys/custodian_component_share1.key.enc

shred -u temp_keys/aes_key.bin
```

---

### Step 8: Encrypt Vault unseal share 1

```bash
openssl rand -out temp_keys/aes_key.bin 32

cat temp_keys/vault_unseal_share1.txt | \
  openssl enc -aes-256-cbc -salt -pbkdf2 \
  -pass file:temp_keys/aes_key.bin \
  -out temp_keys/vault_unseal_share1.enc

openssl pkeyutl -encrypt \
  -pubin -inkey temp_keys/pubkey1.pem \
  -in temp_keys/aes_key.bin \
  -out temp_keys/vault_unseal_share1.key.enc

shred -u temp_keys/aes_key.bin
```

### Step 9: Verify decryption (while plaintext files still exist)

With **YubiKey 1 still inserted**, run the verification script. You will be prompted for the YubiKey PIN twice (once per share).

```bash
./vault/verify-yubikey-shares.sh 1
```

> ⚠️ Only proceed to Step 10 if the script exits with **✅ All shares verified**. If it reports a mismatch, re-run steps 7–8 before shredding anything.

### Step 10: Shred the public key

```bash
shred -u temp_keys/pubkey1.pem
```

**YubiKey 1 output files** (upload all 4 to Bitwarden, labelled for YubiKey 1):

- `temp_keys/custodian_component_share1.enc`
- `temp_keys/custodian_component_share1.key.enc`
- `temp_keys/vault_unseal_share1.enc`
- `temp_keys/vault_unseal_share1.key.enc`

---

## YubiKey 2

Remove YubiKey 1 and insert YubiKey 2 before proceeding.

### Step 1: Reset PIV application

```bash
ykman piv reset
```

### Step 2: Set Management Key

```bash
ykman piv access change-management-key --generate --protect
```

### Step 3: Set PIN

```bash
ykman piv access change-pin
```

- Default PIN: `123456`
- Change to a strong 6–8 digit PIN (use a **different PIN** to YubiKey 1)
- Record securely in your password manager

### Step 4: Set PUK

```bash
ykman piv access change-puk
```

- Default PUK: `12345678`
- Change to a strong 8 digit code (use a **different PUK** to YubiKey 1)
- Record securely in your password manager

### Step 5: Generate RSA-2048 key pair

```bash
ykman piv keys generate --algorithm RSA2048 9d temp_keys/pubkey2.pem
```

### Step 6: Create self-signed certificate

```bash
ykman piv certificates generate --subject "CN=Vault Share Key 2" 9d temp_keys/pubkey2.pem
```

---

### Step 7: Encrypt custodian component share 2

```bash
openssl rand -out temp_keys/aes_key.bin 32

cat temp_keys/custodian_component_share2.txt | \
  openssl enc -aes-256-cbc -salt -pbkdf2 \
  -pass file:temp_keys/aes_key.bin \
  -out temp_keys/custodian_component_share2.enc

openssl pkeyutl -encrypt \
  -pubin -inkey temp_keys/pubkey2.pem \
  -in temp_keys/aes_key.bin \
  -out temp_keys/custodian_component_share2.key.enc

shred -u temp_keys/aes_key.bin
```

---

### Step 8: Encrypt Vault unseal share 2

```bash
openssl rand -out temp_keys/aes_key.bin 32

cat temp_keys/vault_unseal_share2.txt | \
  openssl enc -aes-256-cbc -salt -pbkdf2 \
  -pass file:temp_keys/aes_key.bin \
  -out temp_keys/vault_unseal_share2.enc

openssl pkeyutl -encrypt \
  -pubin -inkey temp_keys/pubkey2.pem \
  -in temp_keys/aes_key.bin \
  -out temp_keys/vault_unseal_share2.key.enc

shred -u temp_keys/aes_key.bin
```

### Step 9: Verify decryption (while plaintext files still exist)

With **YubiKey 2 still inserted**, run the verification script. You will be prompted for the YubiKey PIN twice (once per share).

```bash
./vault/verify-yubikey-shares.sh 2
```

> ⚠️ Only proceed to Step 10 if the script exits with **✅ All shares verified**. If it reports a mismatch, re-run steps 7–8 before shredding anything.

### Step 10: Shred the public key

```bash
shred -u temp_keys/pubkey2.pem
```

**YubiKey 2 output files** (upload all 4 to Bitwarden, labelled for YubiKey 2):

- `temp_keys/custodian_component_share2.enc`
- `temp_keys/custodian_component_share2.key.enc`
- `temp_keys/vault_unseal_share2.enc`
- `temp_keys/vault_unseal_share2.key.enc`

---

## After Both YubiKeys Are Done

### Upload encrypted files to Bitwarden

Upload all 8 `.enc` and `.key.enc` files to Bitwarden as file attachments, clearly labelled with which YubiKey they correspond to.

### Handle physical backup shares (shares 3 & 4)

Shares 3 and 4 go to physical storage — **do not encrypt these with a YubiKey**:

- `custodian_component_share3.txt` → physical safe
- `custodian_component_share4.txt` → cold storage (e.g. bank safety deposit box)
- `vault_unseal_share3.txt` → physical safe
- `vault_unseal_share4.txt` → cold storage

Print or write them down before shredding the files.

### Shred all remaining plaintext share files

```bash
shred -u temp_keys/custodian_component_share1.txt
shred -u temp_keys/custodian_component_share2.txt
shred -u temp_keys/custodian_component_share3.txt
shred -u temp_keys/custodian_component_share4.txt
shred -u temp_keys/vault_unseal_share1.txt
shred -u temp_keys/vault_unseal_share2.txt
shred -u temp_keys/vault_unseal_share3.txt
shred -u temp_keys/vault_unseal_share4.txt
```

---

## Re-exporting a Public Key

If you ever need to re-encrypt something for an existing YubiKey (e.g. during key rotation), you can re-export its public key without resetting the YubiKey:

```bash
# With YubiKey 1 inserted:
ykman piv certificates export 9d temp_keys/pubkey1.pem

# With YubiKey 2 inserted:
ykman piv certificates export 9d temp_keys/pubkey2.pem
```

---

## Security Reminders

- Store each YubiKey in a **separate secure location**
- Store PINs **separately** from YubiKeys (password manager or sealed envelope)
- Never write the PIN on the YubiKey itself
- After 3 wrong PIN attempts the YubiKey locks — use the PUK to unblock
- After 3 wrong PUK attempts the PIV application is **permanently locked**
- Test the decryption process quarterly using `vault/unseal_vault.sh` and `scripts/unseal-platform-key.sh`
