---
title: Encryption Technical Reference
category: api
priority: 6
---

# Encryption Technical Reference

This document provides technical implementation details for developers working on CheckTick's encryption system. For user guides, see [Encryption for Users](/docs/encryption-for-users/). For admin procedures, see [Key Management for Administrators](/docs/key-management-for-administrators/).

---

CheckTick implements a security-first approach to handling sensitive patient data, using per-survey encryption keys with AES-GCM encryption. This document describes the current implementation and planned enhancements for organizational and individual users.

## Table of Contents

- [Current Implementation](#current-implementation)
  - [Overview](#overview)
  - [How It Works](#how-it-works)
  - [Current Security Properties](#current-security-properties)
  - [Session Security Model](#session-security-model)
- [Implementation Status](#implementation-status)
  - [Completed Features](#-completed-features)
  - [Future Enhancements](#-future-enhancements)
- [Web Application Integration](#web-application-integration)
  - [Survey Creation via Web Interface](#survey-creation-via-web-interface)
  - [Key Display Workflow](#key-display-workflow)
  - [Survey Unlocking](#survey-unlocking-via-web-interface)
  - [User Experience Flow](#user-experience-flow)
- [OIDC Integration and Authentication](#oidc-integration-and-authentication)
  - [Benefits and Architecture](#oidc-benefits-for-checktick)
  - [Implementation Details](#implementation-with-oidc)
- [Implementation Roadmap](#implementation-roadmap)
- [Security Best Practices](#security-best-practices)
- [Compliance and Regulations](#compliance-and-regulations)
- [Migration and Upgrade Path](#migration-and-upgrade-path)
- [Technical Reference](#technical-reference)
- [Testing](#testing)
- [Related Documentation](#related-documentation)

## Current Implementation

CheckTick implements a **production-ready dual-encryption system** (Option 2 + Option 4) for clinicians and organizations:

### Overview

CheckTick protects sensitive demographic data using **dual-path encryption** with:

- **Primary Method**: Password-based unlock for daily use
- **Backup Method**: BIP39 recovery phrase for account recovery
- **Algorithm**: AES-GCM (Authenticated Encryption with Associated Data)
- **Key Derivation**: Scrypt KDF (n=2^14, r=8, p=1)
- **Key Size**: 256-bit (32 bytes)
- **Authentication**: PBKDF2-HMAC-SHA256 (200,000 iterations)
- **Forward Secrecy**: KEK re-derived on each request, never persisted
- **Session Security**: 30-minute timeout with encrypted credential storage

### How It Works

#### 1. Survey Creation

When a survey is created via the web interface, users choose their encryption method:

```python
# Generate random 32-byte survey encryption key (KEK)
kek = os.urandom(32)

# Set up dual-path encryption (Option 2)
password = request.POST.get("password")  # User's chosen password
recovery_words = generate_bip39_phrase(12)  # Generated 12-word phrase

# Encrypt KEK with both password and recovery phrase
survey.set_dual_encryption(kek, password, recovery_words)

# Display recovery phrase to user (one-time only)
# User must write it down and confirm they've saved it
```

The dual encryption process:

1. **Password Path**: KEK encrypted with user's password using Scrypt KDF
2. **Recovery Path**: KEK encrypted with BIP39 recovery phrase using PBKDF2
3. **Storage**: Only encrypted KEKs stored, never plaintext keys
4. **Hint**: First and last words of recovery phrase stored as hint (e.g., "apple...zebra")

#### 2. Data Encryption

When patient data is collected in a survey response:

```python
# Sensitive fields (encrypted)
demographics = {
    "first_name": "John",
    "last_name": "Smith",
    "date_of_birth": "1980-01-01",
    "nhs_number": "1234567890",
    "address": "123 Main St"
}

# Encrypt with survey key
encrypted_blob = encrypt_sensitive(survey_key, demographics)
response.enc_demographics = encrypted_blob  # Stored in database
```

The encryption process:

1. Derives encryption key from survey key using Scrypt KDF with random salt
2. Generates random 12-byte nonce
3. Encrypts JSON data with AES-GCM
4. Stores: `salt (16 bytes) | nonce (12 bytes) | ciphertext`

#### 2b. Whole-Response Encryption (Patient Data Surveys)

When a survey collects patient data (identified by a `patient_details_encrypted` question group), the **entire survey response** is encrypted - not just the demographics:

```python
# Patient data survey: encrypt ENTIRE response
if survey.requires_whole_response_encryption():
    # Combine all data into single encrypted blob
    full_response = {
        "answers": {
            "q1_chest_pain": "mild",
            "q2_duration": "3 days",
            "q3_previous_history": "yes",
            "q4_notes": "Patient describes intermittent pain..."
        },
        "demographics": {
            "first_name": "John",
            "nhs_number": "1234567890",
            "date_of_birth": "1980-01-01"
        }
    }

    # Store complete encrypted response
    response.store_complete_response(survey_key, answers, demographics)
    # response.enc_answers contains the encrypted blob
    # response.answers is cleared (empty dict)
    # response.enc_demographics is None (not used)
```

**Why whole-response encryption for patient data:**

- Clinical observations (symptoms, notes) should be protected alongside identifiers
- Free-text answers may contain identifying information
- Complete protection prevents "re-identification" attacks
- Simpler mental model: "patient data survey = everything encrypted"

#### 3. Data Decryption

To view encrypted data, users must "unlock" the survey:

```python
# User provides password or recovery phrase
unlock_method = request.POST.get("unlock_method")

if unlock_method == "password":
    # Derive KEK from user's password
    password = request.POST.get("password")
    survey_kek = survey.unlock_with_password(password)
elif unlock_method == "recovery":
    # Derive KEK from recovery phrase
    recovery_phrase = request.POST.get("recovery_phrase")
    survey_kek = survey.unlock_with_recovery(recovery_phrase)

if survey_kek:
    # Store encrypted credentials in session (not the KEK)
    # KEK is re-derived on each request for forward secrecy
    session_key = request.session.session_key or request.session.create()
    encrypted_creds = encrypt_sensitive(session_key.encode('utf-8'), {
        'password': password,  # or recovery_phrase
        'survey_slug': survey.slug
    })
    request.session["unlock_credentials"] = base64.b64encode(encrypted_creds).decode('ascii')
    request.session["unlock_method"] = unlock_method
    request.session["unlock_verified_at"] = timezone.now().isoformat()
    request.session["unlock_survey_slug"] = survey.slug

# On each request needing the KEK, re-derive it
survey_key = get_survey_key_from_session(request, survey.slug)
if survey_key:
    demographics = response.load_demographics(survey_key)
```

### Current Security Properties

✅ **Zero-Knowledge**: Server never stores encryption keys in plaintext
✅ **Dual-Path Encryption**: Password + recovery phrase backup method
✅ **Per-Survey Isolation**: Each survey has unique encryption key
✅ **Authenticated Encryption**: AES-GCM prevents tampering
✅ **Strong KDF**: Scrypt protects against brute-force attacks
✅ **Forward Secrecy**: KEK re-derived on each request, never persisted in session
✅ **Minimal Session Storage**: Only encrypted credentials stored, not key material
✅ **Automatic Timeout**: 30-minute session expiration for unlocked surveys
✅ **Recovery Phrase**: BIP39-compatible 12-word backup phrases
✅ **Production Ready**: 46/46 unit tests + 7/7 integration tests passing
✅ **Healthcare Compliant**: Designed for clinician workflows

### Session Security Model

CheckTick implements a **forward secrecy** model where encryption keys are never persisted in sessions:

**What's Stored in Sessions:**

- `unlock_credentials`: Encrypted blob containing user's password or recovery phrase
- `unlock_method`: Which method was used ("password" or "recovery")
- `unlock_verified_at`: ISO timestamp of when unlock occurred
- `unlock_survey_slug`: Which survey was unlocked

**What's NOT Stored:**

- ❌ The KEK (Key Encryption Key) itself
- ❌ Any plaintext key material
- ❌ Decrypted credentials

**How It Works:**

1. **User Unlocks Survey**: Provides password or recovery phrase
2. **Credentials Encrypted**: Credentials encrypted with session-specific key using `encrypt_sensitive()`
3. **KEK Derived & Verified**: KEK derived and verified, then discarded
4. **Session Metadata Stored**: Only encrypted credentials + metadata stored in session
5. **Each Request**: KEK re-derived on-demand via `get_survey_key_from_session()`
6. **Automatic Cleanup**: After 30 minutes or on error, session data cleared

**Security Benefits:**

- **Forward Secrecy**: Compromise of session storage doesn't reveal KEK
- **Time-Limited Access**: Automatic 30-minute timeout enforced
- **Survey Isolation**: Slug validation prevents cross-survey access
- **No Key Material in Memory**: KEK exists only during request processing

**Helper Function:**

```python
def get_survey_key_from_session(request: HttpRequest, survey_slug: str) -> Optional[bytes]:
    """
    Re-derive KEK from encrypted session credentials.
    Returns None if timeout expired (>30 min) or validation fails.
    """
    # Check credentials exist
    if not request.session.get("unlock_credentials"):
        return None

    # Validate 30-minute timeout
    verified_at_str = request.session.get("unlock_verified_at")
    verified_at = timezone.datetime.fromisoformat(verified_at_str)
    if timezone.is_naive(verified_at):
        verified_at = timezone.make_aware(verified_at)

    if timezone.now() - verified_at > timedelta(minutes=30):
        # Clear expired session
        request.session.pop("unlock_credentials", None)
        request.session.pop("unlock_method", None)
        request.session.pop("unlock_verified_at", None)
        request.session.pop("unlock_survey_slug", None)
        return None

    # Validate survey slug matches
    if request.session.get("unlock_survey_slug") != survey_slug:
        return None

    # Decrypt credentials with session key
    session_key = request.session.session_key
    encrypted_creds_b64 = request.session.get("unlock_credentials")
    encrypted_creds = base64.b64decode(encrypted_creds_b64)

    credentials = decrypt_sensitive(session_key.encode('utf-8'), encrypted_creds)

    # Re-derive KEK based on method
    survey = Survey.objects.get(slug=survey_slug)
    unlock_method = request.session.get("unlock_method")

    if unlock_method == "password":
        return survey.unlock_with_password(credentials["password"])
    elif unlock_method == "recovery":
        return survey.unlock_with_recovery(credentials["recovery_phrase"])
    elif unlock_method == "legacy":
        # Legacy key stored as base64
        return base64.b64decode(credentials["legacy_key"])

    return None
```

## Web Application Integration

The web application implements **dual-path encryption** (Option 2) for all surveys created via the interface. Users can unlock surveys with either their password or recovery phrase.

### Survey Creation via Web Interface

When a user creates a survey through the web application at `/surveys/create/`:

```python
@login_required
@require_http_methods(["GET", "POST"])
def survey_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SurveyCreateForm(request.POST)
        if form.is_valid():
            survey: Survey = form.save(commit=False)
            survey.owner = request.user

            # Generate encryption key automatically
            encryption_key = os.urandom(32)
            survey.set_key(encryption_key)  # Stores hash + salt only

            survey.save()

            # Show key ONCE to user (enhanced approach below)
            request.session['new_survey_key'] = encryption_key
            request.session['new_survey_slug'] = survey.slug

            return redirect("surveys:key-display", slug=survey.slug)
    else:
        form = SurveyCreateForm()
    return render(request, "surveys/create.html", {"form": form})
```

### Key Display Workflow

After survey creation, users are redirected to a **one-time key display page** that shows the encryption key with clear warnings:

```html
<!-- surveys/templates/surveys/key_display.html -->
<div class="max-w-2xl mx-auto">
  <div class="alert alert-warning shadow-lg mb-6">
    <div>
      <svg class="stroke-current flex-shrink-0 h-6 w-6">...</svg>
      <div>
        <h3 class="font-bold">⚠️ Critical: Save Your Encryption Key</h3>
        <div class="text-sm">
          This key encrypts sensitive patient data in your survey.
          <strong>It will only be shown once.</strong>
        </div>
      </div>
    </div>
  </div>

  <div class="card bg-base-100 shadow-xl">
    <div class="card-body">
      <h2 class="card-title">Survey: {{ survey.name }}</h2>

      <!-- Encryption Key Display -->
      <div class="form-control">
        <label class="label">
          <span class="label-text font-semibold">Encryption Key</span>
        </label>
        <div class="input-group">
          <input
            type="text"
            readonly
            value="{{ encryption_key_b64 }}"
            class="input input-bordered w-full font-mono text-sm"
            id="encryption-key"
          />
          <button
            class="btn btn-square"
            onclick="copyToClipboard()"
            title="Copy to clipboard"
          >
            📋
          </button>
        </div>
      </div>

      <!-- Download Options -->
      <div class="flex gap-2 mt-4">
        <button
          class="btn btn-primary"
          onclick="downloadKeyFile()"
        >
          📥 Download Key File
        </button>
        <button
          class="btn btn-secondary"
          onclick="printKey()"
        >
          🖨️ Print Key
        </button>
      </div>

      <!-- User Type Specific Messaging -->
      {% if user.organization_memberships.exists %}
        <!-- Organization User -->
        <div class="alert alert-info mt-6">
          <div>
            <svg class="stroke-current flex-shrink-0 h-6 w-6">...</svg>
            <div>
              <h4 class="font-bold">Organization Account</h4>
              <ul class="text-sm list-disc list-inside mt-2">
                <li>Your organization can recover this key if lost</li>
                <li>Organization admins can access encrypted data</li>
                <li>All key access is logged for compliance</li>
                <li>Multi-person approval required for emergency recovery</li>
              </ul>
            </div>
          </div>
        </div>
      {% else %}
        <!-- Individual User -->
        <div class="alert alert-error mt-6">
          <div>
            <svg class="stroke-current flex-shrink-0 h-6 w-6">...</svg>
            <div>
              <h4 class="font-bold">Individual Account - Important</h4>
              <ul class="text-sm list-disc list-inside mt-2">
                <li>⚠️ You are solely responsible for this key</li>
                <li>⚠️ Lost key = permanent data loss (no recovery)</li>
                <li>⚠️ Save in a secure location (password manager recommended)</li>
                <li>⚠️ Consider printing and storing offline</li>
              </ul>
            </div>
          </div>
        </div>
      {% endif %}

      <!-- Acknowledgment Checkbox -->
      <div class="form-control mt-6">
        <label class="label cursor-pointer justify-start gap-3">
          <input
            type="checkbox"
            class="checkbox checkbox-primary"
            id="acknowledge"
            required
          />
          <span class="label-text">
            I have saved the encryption key securely. I understand the risks of losing it.
          </span>
        </label>
      </div>

      <!-- Continue Button -->
      <div class="card-actions justify-end mt-6">
        <button
          class="btn btn-primary btn-wide"
          id="continue-btn"
          disabled
          onclick="window.location.href='{% url 'surveys:groups' slug=survey.slug %}'"
        >
          Continue to Survey Builder →
        </button>
      </div>
    </div>
  </div>
</div>

<script>
  // Enable continue button only after acknowledgment
  document.getElementById('acknowledge').addEventListener('change', function() {
    document.getElementById('continue-btn').disabled = !this.checked;
  });

  // Copy to clipboard
  function copyToClipboard() {
    const input = document.getElementById('encryption-key');
    input.select();
    document.execCommand('copy');
    alert('Encryption key copied to clipboard!');
  }

  // Download key as text file
  function downloadKeyFile() {
    const key = document.getElementById('encryption-key').value;
    const surveyName = '{{ survey.name|escapejs }}';
    const content = `CheckTick Survey Encryption Key
Survey: ${surveyName}
Created: {{ now|date:"Y-m-d H:i:s" }}

Encryption Key (Base64):
${key}

⚠️ IMPORTANT SECURITY INFORMATION ⚠️
- Store this file in a secure location
- Never share via email or messaging
- Use a password manager or encrypted storage
- Without this key, encrypted patient data cannot be accessed
- See documentation: /docs/patient-data-encryption/

Generated by CheckTick Survey Platform
`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `checktick-survey-${surveyName.toLowerCase().replace(/\s+/g, '-')}-encryption-key.txt`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  // Print key
  function printKey() {
    window.print();
  }
</script>
```

### Account Creation Integration

The encryption approach is communicated clearly during account signup:

#### Organization Account Signup

```html
<!-- registration/signup_organization.html -->
<div class="alert alert-info mb-6">
  <h3 class="font-bold">🏢 Organization Account Benefits</h3>
  <ul class="text-sm list-disc list-inside mt-2">
    <li><strong>Collaborative:</strong> Multiple users can manage surveys</li>
    <li><strong>Key Recovery:</strong> Organization can recover lost encryption keys</li>
    <li><strong>Audit Trail:</strong> All key access logged for compliance</li>
    <li><strong>Enterprise Security:</strong> Keys backed up in AWS/Azure Key Vault</li>
    <li><strong>HIPAA/GDPR Ready:</strong> Meets healthcare compliance standards</li>
  </ul>
</div>
```

#### Individual Account Signup

```html
<!-- registration/signup_individual.html -->
<div class="alert alert-warning mb-6">
  <h3 class="font-bold">👤 Individual Account Notice</h3>
  <ul class="text-sm list-disc list-inside mt-2">
    <li><strong>Personal Responsibility:</strong> You manage your own encryption keys</li>
    <li><strong>No Recovery Service:</strong> Lost keys cannot be recovered by CheckTick</li>
    <li><strong>Data Loss Risk:</strong> Losing your key means losing encrypted data</li>
    <li><strong>Best For:</strong> Small studies, personal projects, non-critical data</li>
  </ul>

  <div class="form-control mt-4">
    <label class="label cursor-pointer justify-start gap-3">
      <input type="checkbox" class="checkbox checkbox-warning" required />
      <span class="label-text">
        I understand that CheckTick cannot recover lost encryption keys for individual accounts.
        I will store all survey keys securely.
      </span>
    </label>
  </div>
</div>
```

### Helping Users Store Keys Safely

For **individual users** who don't have organizational key recovery, CheckTick implements a **multi-method recovery approach** that balances security with usability. Individual users are given multiple ways to store and recover their encryption keys without relying on browser storage or third-party services.

#### Current Implementation: Password + Recovery Phrase (Option 2)

The current working solution provides **dual recovery paths** for individual users:

```
Survey Encryption Key (KEK)
├─ Password-Encrypted Copy
│  └─ Encrypted with user's password-derived key
│  └─ Used for normal day-to-day access
│
└─ Recovery Code-Encrypted Copy
   └─ Encrypted with BIP39 recovery phrase-derived key
   └─ 12-word mnemonic phrase shown ONCE at creation
   └─ Provides backup if password is lost
```

**Key Features:**

- **Dual Access Methods**: User can unlock with either their account password OR the recovery phrase
- **Zero-Knowledge**: Server stores only encrypted versions, never plaintext keys
- **Offline Backup**: Recovery phrase can be written down or printed and stored physically
- **User Responsibility**: Clear warnings that losing BOTH password and recovery phrase = permanent data loss

**Database Schema:**

```python
class Survey(models.Model):
    # Current fields (for legacy API compatibility)
    key_salt = models.BinaryField()
    key_hash = models.BinaryField()

    # Option 2: Individual user encryption
    encrypted_kek_password = models.BinaryField(null=True)
    encrypted_kek_recovery = models.BinaryField(null=True)
    recovery_code_hint = models.CharField(max_length=100, blank=True)
```

**Implementation at Survey Creation:**

```python
@login_required
@require_http_methods(["GET", "POST"])
def survey_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SurveyCreateForm(request.POST)
        if form.is_valid():
            survey: Survey = form.save(commit=False)
            survey.owner = request.user

            # Generate master encryption key for this survey
            survey_kek = os.urandom(32)

            # Store hash for legacy API compatibility
            digest, salt = make_key_hash(survey_kek)
            survey.key_hash = digest
            survey.key_salt = salt

            # Determine encryption strategy
            if request.user.organization_memberships.exists():
                # Organization user - implement Option 1 (future)
                setup_organization_encryption(survey, survey_kek, request.user)
            else:
                # Individual user - implement Option 2 (current)
                setup_individual_encryption(survey, survey_kek, request.user)

            survey.save()

            # Redirect to key display page
            request.session['new_survey_key_b64'] = base64.b64encode(survey_kek).decode()
            request.session['new_survey_slug'] = survey.slug

            return redirect("surveys:key-display", slug=survey.slug)
    else:
        form = SurveyCreateForm()
    return render(request, "surveys/create.html", {"form": form})


def setup_individual_encryption(survey: Survey, survey_kek: bytes, user: User):
    """Set up encryption for individual users with dual recovery."""

    # Method 1: Password-based encryption (primary access)
    password_key = derive_key_from_password(user.password)
    survey.encrypted_kek_password = encrypt_sensitive(
        password_key,
        {"kek": survey_kek.hex()}
    )

    # Method 2: Recovery phrase-based encryption (backup access)
    recovery_phrase = generate_bip39_phrase(words=12)
    recovery_key = derive_key_from_passphrase(recovery_phrase)
    survey.encrypted_kek_recovery = encrypt_sensitive(
        recovery_key,
        {"kek": survey_kek.hex()}
    )

    # Store recovery phrase in session to show user ONCE
    request.session['recovery_phrase'] = recovery_phrase


def generate_bip39_phrase(words: int = 12) -> str:
    """
    Generate a BIP39-compatible mnemonic phrase.

    Uses standard BIP39 wordlist for better compatibility with
    password managers and recovery tools.
    """
    from mnemonic import Mnemonic

    mnemo = Mnemonic("english")
    # Generate based on entropy: 128 bits = 12 words, 256 bits = 24 words
    bits = 128 if words == 12 else 256
    return mnemo.generate(strength=bits)


def derive_key_from_passphrase(passphrase: str) -> bytes:
    """
    Derive encryption key from recovery passphrase.

    Uses PBKDF2 with high iteration count to slow brute-force attacks.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"checktick-recovery-phrase-salt-v1",  # Fixed salt for passphrases
        iterations=200_000
    )
    return kdf.derive(passphrase.encode('utf-8'))
```

**User Interface - Key Display Page:**

```html
<!-- surveys/templates/surveys/key_display.html -->
<div class="max-w-3xl mx-auto p-6">

  <!-- Critical Warning Banner -->
  <div class="alert alert-error shadow-lg mb-6">
    <div>
      <svg class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <div>
        <h3 class="font-bold text-lg">⚠️ Critical: Save Your Encryption Keys</h3>
        <div class="text-sm mt-2">
          This survey uses end-to-end encryption for patient data security.
          <strong>You must save BOTH keys below.</strong> They will only be shown once.
          Without them, encrypted data cannot be recovered.
        </div>
      </div>
    </div>
  </div>

  <div class="card bg-base-100 shadow-xl">
    <div class="card-body">
      <h2 class="card-title text-2xl">Survey Created: {{ survey.name }}</h2>

      <!-- Method 1: Survey Encryption Key (Base64) -->
      <div class="divider">Primary Access Method</div>

      <div class="form-control">
        <label class="label">
          <span class="label-text font-semibold text-lg">
            🔐 Survey Encryption Key (Base64)
          </span>
        </label>
        <div class="input-group">
          <input
            type="text"
            readonly
            value="{{ encryption_key_b64 }}"
            class="input input-bordered w-full font-mono text-sm"
            id="encryption-key"
          />
          <button
            class="btn btn-square"
            onclick="copyToClipboard('encryption-key')"
            title="Copy to clipboard"
          >
            📋
          </button>
        </div>
        <label class="label">
          <span class="label-text-alt">
            Use this key to unlock the survey when signed in.
          </span>
        </label>
      </div>

      <!-- Method 2: Recovery Phrase (12 Words) -->
      <div class="divider mt-6">Backup Recovery Method</div>

      <div class="form-control">
        <label class="label">
          <span class="label-text font-semibold text-lg">
            🔑 Recovery Phrase (12 Words)
          </span>
        </label>
        <div class="bg-base-200 p-4 rounded-lg">
          <div class="grid grid-cols-3 gap-3 font-mono text-sm" id="recovery-phrase">
            {% for word in recovery_phrase_words %}
              <div class="bg-base-100 p-2 rounded">
                <span class="text-xs text-gray-500">{{ forloop.counter }}.</span>
                <span class="font-semibold">{{ word }}</span>
              </div>
            {% endfor %}
          </div>
        </div>
        <label class="label">
          <span class="label-text-alt">
            Write these words down in order. They can recover your data if you lose the encryption key.
          </span>
        </label>
      </div>

      <!-- Download and Print Options -->
      <div class="flex flex-wrap gap-3 mt-6">
        <button class="btn btn-primary gap-2" onclick="downloadKeyFile()">
          📥 Download Keys as Text File
        </button>
        <button class="btn btn-secondary gap-2" onclick="downloadRecoverySheet()">
          📄 Download Printable Recovery Sheet
        </button>
        <button class="btn btn-accent gap-2" onclick="window.print()">
          🖨️ Print This Page
        </button>
      </div>

      <!-- Security Best Practices -->
      <div class="alert alert-info mt-6">
        <div>
          <svg class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <h4 class="font-bold">Recommended Storage Methods:</h4>
            <ul class="text-sm list-disc list-inside mt-2 space-y-1">
              <li><strong>Password Manager:</strong> Store both keys in a password manager (1Password, Bitwarden, etc.)</li>
              <li><strong>Offline Backup:</strong> Print the recovery sheet and store in a safe place</li>
              <li><strong>Encrypted Storage:</strong> Save the text file in encrypted cloud storage (not email!)</li>
              <li><strong>Multiple Copies:</strong> Keep recovery phrase in 2-3 separate secure locations</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Individual User Warning -->
      <div class="alert alert-warning mt-4">
        <div>
          <svg class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <h4 class="font-bold">👤 Individual Account - Important</h4>
            <ul class="text-sm list-disc list-inside mt-2">
              <li>⚠️ You are solely responsible for these keys</li>
              <li>⚠️ CheckTick cannot recover lost keys for individual accounts</li>
              <li>⚠️ Losing BOTH the encryption key AND recovery phrase = permanent data loss</li>
              <li>⚠️ Never share these keys via email or messaging apps</li>
              <li>💡 Consider upgrading to an Organization account for key recovery options</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Acknowledgment Checkbox -->
      <div class="form-control mt-6">
        <label class="label cursor-pointer justify-start gap-3">
          <input
            type="checkbox"
            class="checkbox checkbox-error checkbox-lg"
            id="acknowledge"
            required
          />
          <span class="label-text font-semibold">
            I have saved BOTH the encryption key and recovery phrase securely.
            I understand that losing both will result in permanent, unrecoverable data loss.
          </span>
        </label>
      </div>

      <!-- Continue Button -->
      <div class="card-actions justify-end mt-6">
        <button
          class="btn btn-primary btn-wide btn-lg"
          id="continue-btn"
          disabled
          onclick="clearKeysAndContinue()"
        >
          Continue to Survey Builder →
        </button>
      </div>
    </div>
  </div>
</div>

<script>
  // Enable continue button only after acknowledgment
  document.getElementById('acknowledge').addEventListener('change', function() {
    document.getElementById('continue-btn').disabled = !this.checked;
  });

  // Copy to clipboard
  function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    input.select();
    document.execCommand('copy');

    // Show feedback
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = '✓';
    setTimeout(() => btn.textContent = originalText, 1500);
  }

  // Download both keys as text file
  function downloadKeyFile() {
    const key = document.getElementById('encryption-key').value;
    const recoveryWords = Array.from(
      document.querySelectorAll('#recovery-phrase .font-semibold')
    ).map(el => el.textContent).join(' ');

    const surveyName = '{{ survey.name|escapejs }}';
    const content = `CheckTick Survey Encryption Keys
=====================================

Survey: ${surveyName}
Created: {{ now|date:"Y-m-d H:i:s" }}

ENCRYPTION KEY (Base64):
${key}

RECOVERY PHRASE (12 Words):
${recoveryWords}

⚠️ CRITICAL SECURITY INFORMATION ⚠️
────────────────────────────────────
• Store this file in a secure location (password manager or encrypted storage)
• NEVER share via email, messaging apps, or unencrypted cloud storage
• You need EITHER the encryption key OR the recovery phrase to access data
• Losing BOTH means permanent data loss - CheckTick cannot recover them
• Consider printing a backup and storing in a physical safe

RECOMMENDED STORAGE:
────────────────────
✓ Password manager (1Password, Bitwarden, LastPass, etc.)
✓ Encrypted USB drive in safe deposit box
✓ Printed copy in fireproof safe
✓ Encrypted cloud storage with strong password

DO NOT STORE:
────────────
✗ Unencrypted email
✗ Text messages or chat apps
✗ Unencrypted cloud drives
✗ Shared network drives
✗ Browser bookmarks or notes

For more information:
https://docs.checktick.app/patient-data-encryption/

Generated by CheckTick Survey Platform
`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `checktick-${surveyName.toLowerCase().replace(/\s+/g, '-')}-encryption-keys-{{ now|date:"Y-m-d" }}.txt`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  // Download printable recovery sheet (formatted PDF-ready)
  function downloadRecoverySheet() {
    const key = document.getElementById('encryption-key').value;
    const recoveryWords = Array.from(
      document.querySelectorAll('#recovery-phrase .font-semibold')
    ).map(el => el.textContent);

    const surveyName = '{{ survey.name|escapejs }}';

    let recoveryGrid = '';
    for (let i = 0; i < 12; i++) {
      recoveryGrid += `${i + 1}. ${recoveryWords[i]}\n`;
    }

    const content = `
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║              CHECKTICK SURVEY - ENCRYPTION RECOVERY SHEET            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

Survey Name: ${surveyName}
Created: {{ now|date:"Y-m-d H:i:s" }}

─────────────────────────────────────────────────────────────────────

RECOVERY PHRASE (12 Words)
══════════════════════════

${recoveryGrid}

─────────────────────────────────────────────────────────────────────

ENCRYPTION KEY (Base64)
═══════════════════════

${key}

─────────────────────────────────────────────────────────────────────

⚠️  CRITICAL INSTRUCTIONS ⚠️

1. STORE SECURELY
   • Keep in a fireproof safe or secure location
   • Treat like cash, passport, or bank account details
   • Do NOT leave in plain sight

2. RECOVERY METHODS
   • Use recovery phrase if you forget encryption key
   • Use encryption key for normal survey access
   • You need EITHER one to access encrypted data

3. PROTECTION
   • Do not photograph or scan this document
   • Do not share via email or messaging
   • Shred securely when no longer needed

4. DATA LOSS WARNING
   • Losing BOTH keys = permanent data loss
   • CheckTick cannot recover keys for individual accounts
   • No backdoor or recovery service exists

─────────────────────────────────────────────────────────────────────

For technical documentation:
https://docs.checktick.app/patient-data-encryption/

Generated by CheckTick Survey Platform
© ${new Date().getFullYear()}

═══════════════════════════════════════════════════════════════════
`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `checktick-${surveyName.toLowerCase().replace(/\s+/g, '-')}-recovery-sheet-{{ now|date:"Y-m-d" }}.txt`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  // Clear keys from session and continue
  function clearKeysAndContinue() {
    // Keys are cleared from session server-side after first view
    window.location.href = '{% url "surveys:groups" slug=survey.slug %}';
  }
</script>

<style>
  @media print {
    .btn, .alert { page-break-inside: avoid; }
    #continue-btn { display: none; }
  }
</style>
```

> **Note:** For the complete unlock implementation with forward secrecy, see the **[Session Security Model](#session-security-model)** section above, which includes the `get_survey_key_from_session()` helper function and proper credential encryption pattern.

#### OIDC Identity-Based Keys (Now Available)

With OIDC (OpenID Connect) authentication now implemented, individual users have **automatic key derivation from their identity provider** (Google, Microsoft, GitHub, etc.).

**How OIDC Improves Key Management:**

```
OIDC-Enhanced Individual User Encryption
├─ OIDC Identity-Derived Key (Primary - Auto-unlock)
│  └─ Derived from stable OIDC subject identifier
│  └─ No manual key entry needed when signed in
│  └─ MFA handled by identity provider (Google/Microsoft)
│
├─ Recovery Phrase (Backup)
│  └─ Still generated for offline/fallback access
│  └─ Used if OIDC provider has issues
│
└─ Password-Based Key (Legacy Support)
   └─ For users who don't use OIDC
```

**Benefits of OIDC (now implemented):**

✅ **No Manual Key Management**: Keys automatically available when user authenticates via Google/Microsoft
✅ **MFA Built-In**: Multi-factor authentication handled by identity provider
✅ **Survives Password Changes**: OIDC subject ID is stable across password resets
✅ **Better UX**: "Sign in with Google" → automatic survey unlock
✅ **Recovery Phrase as Backup**: Still available if OIDC provider has issues

**Current Status**: OIDC integration is **production ready** with comprehensive test coverage. Individual users now have access to all three unlock methods: password, recovery phrase, and OIDC automatic unlock.

### Survey Unlocking via Web Interface

Users unlock surveys to view encrypted data through `/surveys/<slug>/unlock/`:

```python
@login_required
@require_http_methods(["GET", "POST"])
def survey_unlock(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)

    if request.method == "POST":
        unlock_method = request.POST.get("unlock_method")

        if unlock_method == "password":
            # Password-based unlock (Option 4 pattern)
            password = request.POST.get("password", "")
            survey_kek = survey.unlock_with_password(password)

            if survey_kek:
                # Store encrypted credentials, NOT the KEK
                session_key = request.session.session_key or request.session.create()
                encrypted_creds = encrypt_sensitive(session_key.encode('utf-8'), {
                    'password': password,
                    'survey_slug': slug
                })
                request.session["unlock_credentials"] = base64.b64encode(encrypted_creds).decode('ascii')
                request.session["unlock_method"] = "password"
                request.session["unlock_verified_at"] = timezone.now().isoformat()
                request.session["unlock_survey_slug"] = slug

                # Log access
                AuditLog.objects.create(
                    actor=request.user,
                    scope=AuditLog.Scope.SURVEY,
                    survey=survey,
                    action=AuditLog.Action.KEY_ACCESS,
                    metadata={"unlocked_at": timezone.now().isoformat(), "method": "password"}
                )

                messages.success(request, _("Survey unlocked for 30 minutes."))
                return redirect("surveys:dashboard", slug=slug)

            messages.error(request, _("Invalid password."))

        elif unlock_method == "recovery":
            # Recovery phrase unlock (Option 4 pattern)
            recovery_phrase = request.POST.get("recovery_phrase", "").strip()
            survey_kek = survey.unlock_with_recovery(recovery_phrase)

            if survey_kek:
                # Store encrypted credentials, NOT the KEK
                session_key = request.session.session_key or request.session.create()
                encrypted_creds = encrypt_sensitive(session_key.encode('utf-8'), {
                    'recovery_phrase': recovery_phrase,
                    'survey_slug': slug
                })
                request.session["unlock_credentials"] = base64.b64encode(encrypted_creds).decode('ascii')
                request.session["unlock_method"] = "recovery"
                request.session["unlock_verified_at"] = timezone.now().isoformat()
                request.session["unlock_survey_slug"] = slug

                # Log access
                AuditLog.objects.create(
                    actor=request.user,
                    scope=AuditLog.Scope.SURVEY,
                    survey=survey,
                    action=AuditLog.Action.KEY_ACCESS,
                    metadata={"unlocked_at": timezone.now().isoformat(), "method": "recovery_phrase"}
                )

                messages.success(request, _("Survey unlocked using recovery phrase for 30 minutes."))
                return redirect("surveys:dashboard", slug=slug)

            messages.error(request, _("Invalid recovery phrase."))

        elif unlock_method == "legacy":
            # Legacy key-based unlock (for API compatibility)
            key_b64 = request.POST.get("key", "")
            try:
                key = base64.b64decode(key_b64)
                if verify_key(key, bytes(survey.key_hash), bytes(survey.key_salt)):
                    # Store encrypted key, NOT plaintext
                    session_key = request.session.session_key or request.session.create()
                    encrypted_creds = encrypt_sensitive(session_key.encode('utf-8'), {
                        'legacy_key': key_b64,
                        'survey_slug': slug
                    })
                    request.session["unlock_credentials"] = base64.b64encode(encrypted_creds).decode('ascii')
                    request.session["unlock_method"] = "legacy"
                    request.session["unlock_verified_at"] = timezone.now().isoformat()
                    request.session["unlock_survey_slug"] = slug

                    # Log access
                    AuditLog.objects.create(
                        actor=request.user,
                        scope=AuditLog.Scope.SURVEY,
                        survey=survey,
                        action=AuditLog.Action.KEY_ACCESS,
                        metadata={"unlocked_at": timezone.now().isoformat(), "method": "legacy_key"}
                    )

                    messages.success(request, _("Survey unlocked for 30 minutes."))
                    return redirect("surveys:dashboard", slug=slug)
            except Exception:
                pass

            messages.error(request, _("Invalid encryption key."))

    return render(request, "surveys/unlock.html", {
        "survey": survey,
        "has_dual_encryption": survey.has_dual_encryption(),
        "recovery_hint": survey.recovery_code_hint if survey.recovery_code_hint else None
    })
```

> **Note:** The unlock view now supports three methods (password/recovery/legacy) and implements Option 4 forward secrecy by storing only encrypted credentials. The KEK is re-derived on each request via `get_survey_key_from_session()`.

### Viewing Encrypted Data

Once unlocked, encrypted demographics are automatically decrypted when viewing responses:

```python
@login_required
def survey_responses(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)

    # Get KEK via re-derivation (Option 4 pattern)
    survey_key = get_survey_key_from_session(request, slug)
    if not survey_key:
        messages.warning(request, _("Please unlock survey to view encrypted patient data."))
        return redirect("surveys:unlock", slug=slug)

    responses = []

    for response in survey.responses.all():
        response_data = {
            "id": response.id,
            "submitted_at": response.submitted_at,
            "answers": response.answers,
        }

        # Decrypt demographics if present
        if response.enc_demographics:
            try:
                demographics = response.load_demographics(survey_key)
                response_data["demographics"] = demographics
            except Exception:
                response_data["demographics_error"] = "Decryption failed"

        responses.append(response_data)

    return render(request, "surveys/responses.html", {
        "survey": survey,
        "responses": responses,
    })
```

> **Note:** Uses `get_survey_key_from_session()` to re-derive the KEK on each request. If the session has timed out (>30 minutes) or is invalid, the user is redirected to unlock the survey again.

### CSV Export with Decryption

Exporting data includes decrypted demographics when survey is unlocked:

```python
@login_required
def survey_export_csv(
    request: HttpRequest, slug: str
) -> Union[HttpResponse, StreamingHttpResponse]:
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)

    # Get KEK via re-derivation (Option 4 pattern)
    survey_key = get_survey_key_from_session(request, slug)
    if not survey_key:
        messages.error(request, _("Please unlock survey first to export with patient data."))
        return redirect("surveys:unlock", slug=slug)

    def generate():
        import csv
        from io import StringIO

        # Build header with demographic fields
        header = ["id", "submitted_at", "first_name", "last_name",
                  "date_of_birth", "nhs_number", "answers"]
        s = StringIO()
        writer = csv.writer(s)
        writer.writerow(header)
        yield s.getvalue()
        s.seek(0)
        s.truncate(0)

        for r in survey.responses.iterator():
            # Decrypt demographics
            demographics = {}
            if r.enc_demographics:
                try:
                    demographics = r.load_demographics(survey_key)
                except Exception:
                    demographics = {"error": "decryption_failed"}

            row = [
                r.id,
                r.submitted_at.isoformat(),
                demographics.get("first_name", ""),
                demographics.get("last_name", ""),
                demographics.get("date_of_birth", ""),
                demographics.get("nhs_number", ""),
                json.dumps(r.answers)
            ]
            writer.writerow(row)
            yield s.getvalue()
            s.seek(0)
            s.truncate(0)

    resp = StreamingHttpResponse(generate(), content_type="text/csv")
    resp["Content-Disposition"] = f"attachment; filename={slug}-responses.csv"
    return resp
```

### Session Security

Encryption keys in session are protected by Django's security features:

```python
# checktick_app/settings.py

# Session security
SESSION_COOKIE_SECURE = True  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Strict'  # CSRF protection
SESSION_COOKIE_AGE = 3600  # 1 hour timeout

# Keys expire after session
# User must re-unlock for each session
```

### User Experience Flow

**For Organization Users:**

1. **Signup** → See benefits of org key recovery
2. **Create Survey** → Key generated automatically
3. **View Key** → See key + org recovery message
4. **Download/Save** → Multiple backup options
5. **Acknowledge** → Confirm key saved
6. **Build Survey** → Add questions, distribute
7. **Unlock (when needed)** → Enter key OR org admin recovery
8. **View Data** → Encrypted data visible during session

**For Individual Users:**

1. **Signup** → Warning about key responsibility
2. **Acknowledge** → Must accept data loss risk
3. **Create Survey** → Key generated automatically
4. **View Key** → See key + strong warnings
5. **Download/Save** → Encouraged to use password manager
6. **Acknowledge** → Confirm key saved securely
7. **Build Survey** → Add questions, distribute
8. **Unlock (when needed)** → Enter key (no recovery option)
9. **View Data** → Encrypted data visible during session

### Unified Security Model

The web application and API share the same security infrastructure:

```python
# Shared encryption utilities (checktick_app/surveys/utils.py)

def encrypt_sensitive(passphrase_key: bytes, data: dict) -> bytes:
    """Used by both API and web interface"""
    # Same implementation for all entry points

def decrypt_sensitive(passphrase_key: bytes, blob: bytes) -> dict:
    """Used by both API and web interface"""
    # Same implementation for all entry points

def make_key_hash(key: bytes) -> tuple[bytes, bytes]:
    """Used by both API and web interface"""
    # Same implementation for all entry points

def verify_key(key: bytes, digest: bytes, salt: bytes) -> bool:
    """Used by both API and web interface"""
    # Same implementation for all entry points
```

### Benefits of Unified Approach

✅ **Consistent Security**: Same encryption regardless of entry point
✅ **Interoperability**: API and web users can collaborate on same surveys
✅ **Single Audit Trail**: All access logged via same `AuditLog` model
✅ **Unified Testing**: One test suite covers both interfaces
✅ **Clear Documentation**: Users understand security model regardless of interface
✅ **Maintainability**: Single codebase for encryption logic

## OIDC Integration and Authentication

CheckTick plans to implement **OpenID Connect (OIDC)** for authentication, which **significantly enhances** the encryption security model without changing the core encryption approach.

### Why OIDC Works Perfectly with Encryption

OIDC provides **authentication** (proving who you are), while the encryption keys provide **authorization** (accessing encrypted data). These are complementary, not competing:

```
┌─────────────────────────────────────────────────┐
│         Authentication Layer (OIDC)              │
│  • Proves user identity via SSO provider         │
│  • Handles MFA/2FA at identity provider          │
│  • Issues JWT tokens for session management      │
│  • No password stored in CheckTick                  │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│         Authorization Layer (Encryption)         │
│  • Survey encryption keys control data access    │
│  • Independent of authentication method          │
│  • User must have BOTH valid auth AND key       │
│  • Zero-knowledge encryption maintained          │
└─────────────────────────────────────────────────┘
```

### OIDC Benefits for CheckTick

#### 1. Enhanced Security
- **MFA/2FA** handled by identity provider (Google, Microsoft, Okta, etc.)
- **No password storage** in CheckTick (one less attack vector)
- **Single Sign-On (SSO)** for organizational users
- **Centralized access control** via identity provider
- **Audit trail** from both OIDC provider and CheckTick

#### 2. Better User Experience
- **One login** for multiple services
- **MFA already configured** at identity provider
- **Password reset** handled by identity provider
- **Device trust** and conditional access policies
- **Familiar login flow** (e.g., "Sign in with Google")

#### 3. Enterprise Readiness
- **Works with existing enterprise identity systems** (Azure AD, Okta, Auth0)
- **Role mapping** from OIDC claims to CheckTick permissions
- **Group membership** automatically synchronized
- **Compliance** with enterprise security policies

### How OIDC Changes the Key Management

OIDC **improves** the planned encryption enhancements, especially for Option 1 (Organizations):

#### Before OIDC (Password-Based)

```python
# User-encrypted KEK derived from password
user_password = "user's password"
user_key = derive_key_from_password(user_password)
encrypted_kek_user = encrypt(survey_kek, user_key)

# Problem: If user changes password, KEK must be re-encrypted
# Problem: Password complexity requirements needed
# Problem: Password storage/hashing overhead
```

#### With OIDC (Identity-Based)

```python
# User-encrypted KEK derived from OIDC subject identifier
oidc_subject = "google-oauth2|123456789"  # Stable user identifier
user_key = derive_key_from_oidc_subject(oidc_subject, user_salt)
encrypted_kek_user = encrypt(survey_kek, user_key)

# Benefits:
# ✅ Stable identifier (doesn't change with password)
# ✅ No password storage in CheckTick
# ✅ MFA handled by identity provider
# ✅ User can change password without re-encrypting data
```

### Updated Architecture with OIDC

#### Option 1: Organization Users with OIDC

```
Authentication Flow:
1. User clicks "Sign in with [Provider]"
2. Redirected to OIDC provider (e.g., Azure AD)
3. User authenticates (with MFA if configured)
4. OIDC provider returns ID token + access token
5. CheckTick validates token and creates session
6. User identity stored: oidc_provider + subject_id

Survey Encryption Key (KEK) Storage:
├─ User-Encrypted Copy
│  └─ Derived from OIDC subject + user salt
│     └─ Stable across password changes
│     └─ User has primary access when authenticated
│
├─ Organization-Encrypted Copy
│  └─ Encrypted with organization master key
│     └─ Stored in AWS KMS / Azure Key Vault
│     └─ Org admins can decrypt for recovery
│
└─ Emergency Recovery Shares
   └─ Shamir's Secret Sharing (3-of-5 threshold)
      └─ Distributed to designated administrators
```

#### Option 2: Individual Users with OIDC

```
Authentication Flow:
1. User signs in with Google/Microsoft/GitHub
2. MFA handled by provider (if enabled)
3. OIDC token validated by CheckTick
4. User session created

Survey Encryption Key (KEK) Storage:
├─ OIDC-Derived Copy
│  └─ Derived from OIDC subject + user salt
│     └─ User must authenticate to access
│
└─ Recovery Code-Encrypted Copy
   └─ Encrypted with BIP39 recovery phrase
      └─ Shown once at survey creation
      └─ Independent backup method
```

### Implementation with OIDC

#### User Model Changes

```python
# checktick_app/core/models.py

from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # OIDC fields
    oidc_provider = models.CharField(
        max_length=100,
        blank=True,
        help_text="OIDC provider (google, microsoft, okta, etc.)"
    )
    oidc_subject = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Stable OIDC subject identifier"
    )
    oidc_email_verified = models.BooleanField(
        default=False,
        help_text="Email verified by OIDC provider"
    )

    # Key derivation salt (unique per user)
    key_derivation_salt = models.BinaryField(
        null=True,
        help_text="Salt for deriving encryption keys from OIDC identity"
    )

    # Legacy password users (migrated to OIDC over time)
    is_oidc_user = models.BooleanField(
        default=False,
        help_text="User authenticates via OIDC"
    )
```

#### Survey Key Encryption with OIDC

```python
# checktick_app/surveys/utils.py

def derive_key_from_oidc_identity(
    oidc_provider: str,
    oidc_subject: str,
    user_salt: bytes
) -> bytes:
    """
    Derive encryption key from OIDC identity.

    This is stable across password changes but unique per user.
    """
    # Combine provider + subject for uniqueness
    identity = f"{oidc_provider}:{oidc_subject}".encode('utf-8')

    # Use PBKDF2 with user-specific salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=user_salt,
        iterations=200_000
    )

    return kdf.derive(identity)


def encrypt_survey_kek_for_user(survey_kek: bytes, user: User) -> bytes:
    """Encrypt survey KEK for a specific user."""

    if user.is_oidc_user:
        # OIDC users: derive key from stable identity
        user_key = derive_key_from_oidc_identity(
            user.oidc_provider,
            user.oidc_subject,
            user.key_derivation_salt
        )
    else:
        # Legacy users: derive from password (to be migrated)
        user_key = derive_key_from_password(user.password)

    # Encrypt KEK with user key
    return encrypt_sensitive(user_key, {"kek": survey_kek.hex()})


def decrypt_survey_kek_for_user(
    encrypted_kek: bytes,
    user: User
) -> bytes:
    """Decrypt survey KEK for a specific user."""

    if user.is_oidc_user:
        user_key = derive_key_from_oidc_identity(
            user.oidc_provider,
            user.oidc_subject,
            user.key_derivation_salt
        )
    else:
        user_key = derive_key_from_password(user.password)

    decrypted = decrypt_sensitive(user_key, encrypted_kek)
    return bytes.fromhex(decrypted["kek"])
```

#### Survey Creation with OIDC

```python
# checktick_app/surveys/views.py

@login_required
@require_http_methods(["GET", "POST"])
def survey_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SurveyCreateForm(request.POST)
        if form.is_valid():
            survey: Survey = form.save(commit=False)
            survey.owner = request.user

            # Generate survey encryption key (KEK)
            survey_kek = os.urandom(32)

            # Store hash for verification (legacy compatibility)
            digest, salt = make_key_hash(survey_kek)
            survey.key_hash = digest
            survey.key_salt = salt

            # Encrypt KEK for user (OIDC or password-based)
            if request.user.is_oidc_user:
                survey.encrypted_kek_user = encrypt_survey_kek_for_user(
                    survey_kek,
                    request.user
                )
                # User can unlock via OIDC authentication alone
                # No manual key entry needed for OIDC users!
            else:
                # Legacy: show key once for manual storage
                request.session['new_survey_key'] = survey_kek

            # Organization users: also encrypt with org master key
            if request.user.organization_memberships.exists():
                org = request.user.organization_memberships.first().organization
                org_master_key = get_org_master_key(org)
                survey.encrypted_kek_org = encrypt_survey_kek_with_org_key(
                    survey_kek,
                    org_master_key
                )

            survey.save()

            # OIDC users skip manual key display
            if request.user.is_oidc_user:
                messages.success(
                    request,
                    "Survey created! Encryption is automatic with your account."
                )
                return redirect("surveys:groups", slug=survey.slug)
            else:
                return redirect("surveys:key-display", slug=survey.slug)
    else:
        form = SurveyCreateForm()
    return render(request, "surveys/create.html", {"form": form})
```

#### Auto-Unlock for OIDC Users

```python
@login_required
def survey_responses(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)

    # OIDC users: automatic unlock if user has encrypted KEK
    if request.user.is_oidc_user and survey.encrypted_kek_user:
        try:
            # Decrypt KEK using user's OIDC identity
            survey_kek = decrypt_survey_kek_for_user(
                survey.encrypted_kek_user,
                request.user
            )

            # Store encrypted credentials (Option 4 pattern)
            session_key = request.session.session_key or request.session.create()
            encrypted_creds = encrypt_sensitive(session_key.encode('utf-8'), {
                'oidc_derived_key': base64.b64encode(survey_kek).decode('ascii'),
                'survey_slug': slug
            })
            request.session["unlock_credentials"] = base64.b64encode(encrypted_creds).decode('ascii')
            request.session["unlock_method"] = "oidc"
            request.session["unlock_verified_at"] = timezone.now().isoformat()
            request.session["unlock_survey_slug"] = slug

            # Log auto-unlock
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.KEY_ACCESS,
                metadata={
                    "method": "oidc_auto_unlock",
                    "provider": request.user.oidc_provider
                }
            )
        except Exception as e:
            messages.error(request, _("Unable to unlock survey automatically."))
            return redirect("surveys:unlock", slug=slug)

    # Legacy users or OIDC users without encrypted KEK: check session
    survey_key = get_survey_key_from_session(request, slug)
    if not survey_key:
        messages.warning(request, _("Please unlock survey to view encrypted data."))
        return redirect("surveys:unlock", slug=slug)

    # Continue with response viewing...
```

### Migration Strategy

#### Phase 1: Add OIDC Support (Backward Compatible)
```python
# Support both legacy and OIDC users
# New users can choose OIDC
# Existing users continue with password
```

#### Phase 2: Migrate Existing Users to OIDC
```python
@login_required
def migrate_to_oidc(request: HttpRequest):
    """One-time migration for legacy users."""
    if request.user.is_oidc_user:
        messages.info(request, "Already using OIDC.")
        return redirect("home")

    if request.method == "POST":
        # User has authenticated with OIDC provider
        oidc_provider = request.POST.get("oidc_provider")
        oidc_subject = request.POST.get("oidc_subject")

        # Generate user salt for key derivation
        user_salt = os.urandom(16)

        # Re-encrypt all survey KEKs with OIDC-derived key
        for survey in Survey.objects.filter(owner=request.user):
            if survey.encrypted_kek_user:
                # Decrypt with old password-based key
                old_kek = decrypt_survey_kek_for_user(
                    survey.encrypted_kek_user,
                    request.user  # Uses password
                )

                # Update user to OIDC
                request.user.oidc_provider = oidc_provider
                request.user.oidc_subject = oidc_subject
                request.user.key_derivation_salt = user_salt
                request.user.is_oidc_user = True

                # Re-encrypt with new OIDC-derived key
                survey.encrypted_kek_user = encrypt_survey_kek_for_user(
                    old_kek,
                    request.user  # Now uses OIDC
                )
                survey.save()

        request.user.save()
        messages.success(request, "Migrated to OIDC successfully!")
        return redirect("home")
```

### Security Benefits of OIDC + Encryption

#### Defense in Depth

```
Layer 1: OIDC Authentication
├─ MFA at identity provider
├─ Device trust policies
├─ Conditional access (IP, location)
└─ Session management

Layer 2: CheckTick Authorization
├─ Role-based access control
├─ Survey ownership verification
└─ Organization membership checks

Layer 3: Encryption Key Control
├─ Survey-specific encryption keys
├─ Zero-knowledge architecture
├─ Per-user encrypted KEKs
└─ Organization recovery options
```

#### Attack Scenarios and Mitigations

| Attack | Without OIDC | With OIDC |
|--------|--------------|-----------|
| **Credential Stuffing** | Vulnerable if weak passwords | Protected by identity provider MFA |
| **Phishing** | Credentials stolen → account access | MFA prevents access; CheckTick never sees password |
| **Database Breach** | Password hashes exposed | No passwords stored; OIDC subjects useless alone |
| **Session Hijacking** | Need password to re-authenticate | MFA required at identity provider |
| **Insider Threat** | Admin could reset password | Cannot reset OIDC identity; org recovery needed |
| **Lost Credentials** | Manual password reset | Identity provider handles recovery |

### SSO and Patient Data: Passphrase Requirement

While OIDC auto-unlock is convenient, it's not appropriate for all scenarios. When surveys collect patient data, additional explicit authentication is required:

```python
# Survey checks if SSO user needs passphrase
if survey.sso_user_needs_passphrase():
    # User must set up password-based encryption even with SSO
    # Auto-unlock alone is NOT sufficient for patient data

    # On first publish:
    # 1. User enters a passphrase (separate from SSO)
    # 2. KEK is encrypted with passphrase (encrypted_kek_password)
    # 3. Recovery phrase also generated (encrypted_kek_recovery)
    # 4. OIDC encryption may also be set up for convenience
    pass
```

**Why require passphrase for SSO + patient data:**

1. **Explicit Intent**: Unlocking patient data should require conscious action, not happen automatically on login
2. **Device Compromise**: If SSO session is compromised, patient data remains protected
3. **Shared Devices**: Clinical workstations may have persistent SSO sessions
4. **Audit Clarity**: Passphrase entry creates clear "intent to access" audit event
5. **Regulatory Compliance**: Some frameworks require explicit authentication for PHI access

**Configuration in Survey Model:**

```python
class Survey(models.Model):
    # Default: True - SSO users need passphrase for patient data
    require_passphrase_for_patient_data = models.BooleanField(
        default=True,
        help_text="Require SSO users to set a passphrase when survey collects patient data"
    )

    def sso_user_needs_passphrase(self) -> bool:
        """Check if SSO users need to set a passphrase for this survey."""
        return self.collects_patient_data() and self.require_passphrase_for_patient_data
```

Organizations can disable this requirement if their security policy permits auto-unlock for patient data (e.g., in controlled clinical environments).

### User Experience with OIDC

#### Organization User Flow

1. **Signup**: "Sign in with Microsoft" (organization SSO)
2. **Create Survey**: Automatic encryption (no manual key management!)
3. **Patient Data Survey**: Prompted to set passphrase on first publish
4. **View Data**: Auto-unlock for non-patient data; passphrase required for patient data
5. **Recovery**: Organization admin can recover if needed
6. **MFA**: Handled by Microsoft/Google/Okta

#### Individual User Flow

1. **Signup**: "Sign in with Google"
2. **Create Survey**: Shows recovery phrase (backup method)
3. **View Data**: Auto-unlock + optional manual key for extra security
4. **Recovery**: Recovery phrase if OIDC provider issues
5. **MFA**: Enable at Google/Microsoft level

### Configuration Example

```python
# checktick_app/settings.py

OIDC_ENABLED = env.bool("OIDC_ENABLED", default=True)

OIDC_PROVIDERS = {
    "google": {
        "client_id": env("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": env("GOOGLE_OAUTH_CLIENT_SECRET"),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scopes": ["openid", "email", "profile"],
        "display_name": "Google",
    },
    "microsoft": {
        "client_id": env("MICROSOFT_OAUTH_CLIENT_ID"),
        "client_secret": env("MICROSOFT_OAUTH_CLIENT_SECRET"),
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        "scopes": ["openid", "email", "profile"],
        "display_name": "Microsoft",
    },
    "okta": {
        # Enterprise OIDC provider for organizations
        "client_id": env("OKTA_CLIENT_ID"),
        "client_secret": env("OKTA_CLIENT_SECRET"),
        "authorize_url": env("OKTA_AUTHORIZE_URL"),
        "token_url": env("OKTA_TOKEN_URL"),
        "userinfo_url": env("OKTA_USERINFO_URL"),
        "scopes": ["openid", "email", "profile", "groups"],
        "display_name": "Okta",
    },
}

# Recommended packages:
# - mozilla-django-oidc (mature, well-maintained)
# - authlib (flexible, supports multiple providers)
# - social-auth-app-django (comprehensive social auth)
```

### Why OIDC is Better Than 2FA Alone

| Feature | Password + 2FA | OIDC + MFA |
|---------|---------------|------------|
| **User Experience** | Manage password + 2FA code | Single SSO login |
| **Security** | CheckTick stores password hashes | CheckTick stores nothing |
| **MFA Management** | Per-application setup | Centralized at identity provider |
| **Account Recovery** | Reset in CheckTick | Identity provider handles |
| **Enterprise Integration** | Manual user provisioning | Automatic via OIDC groups |
| **Audit Trail** | CheckTick logs only | CheckTick + identity provider |
| **Encryption Key Stability** | Changes with password | Stable OIDC subject |
| **Attack Surface** | Password storage + 2FA | No password, delegated auth |

### Recommendation

✅ **Implement OIDC** instead of building custom 2FA
✅ **Support multiple providers** (Google, Microsoft, Okta)
✅ **Auto-unlock for OIDC users** via encrypted KEKs
✅ **Keep recovery phrases** for individual users as backup
✅ **Organization master keys** remain unchanged
✅ **Migrate existing users** gradually to OIDC

**Result**: Better security, better UX, less code to maintain, and the encryption model becomes even stronger!

## Implementation Status

### ✅ Completed Features

**Option 2: Individual Users (Dual Encryption)** - **PRODUCTION READY**
- Password + recovery phrase dual-path encryption ✅
- 12-word BIP39-compatible recovery phrases ✅
- Forward secrecy session model ✅
- 30-minute session timeouts ✅
- Cross-survey isolation ✅
- Legacy compatibility maintained ✅
- Comprehensive test coverage (46/46 unit + 7/7 integration tests) ✅

**OIDC Integration** - **PRODUCTION READY**
- OpenID Connect authentication with Google, Microsoft, Azure providers ✅
- Automatic survey unlocking for OIDC-authenticated users ✅
- OIDC identity-based key derivation with user-specific salts ✅
- Triple encryption support: Password + Recovery Phrase + OIDC automatic unlock ✅
- Seamless fallback to manual unlock methods ✅
- Comprehensive OIDC test coverage (8/8 tests passing) ✅

### 🔄 Future Enhancements

**Option 1: Organization Users (Key Escrow)** - **ROADMAP**

For healthcare organizations requiring administrative key recovery:

#### Architecture

```
Survey Encryption Key (KEK)
├─ User-Encrypted Copy
│  └─ Encrypted with user's password/recovery phrase (Option 2)
│     └─ User has primary control
│
├─ Organization-Encrypted Copy
│  └─ Encrypted with organization master key
│     └─ Stored in AWS KMS / Azure Key Vault
│     └─ Org admins can decrypt for recovery
│
└─ Emergency Recovery Shares (Optional)
   └─ Shamir's Secret Sharing (3-of-5 threshold)
      └─ Distributed to designated administrators
      └─ Requires multiple people for catastrophic recovery
```

#### Benefits
- **User Control**: Individual users maintain primary access via Option 2
- **Administrative Recovery**: Organization admins can recover user data
- **Compliance**: HIPAA/GDPR compliant with proper audit trails
- **Disaster Recovery**: Multi-party recovery for emergency scenarios

**Database Schema for Future Implementation:**

```python
# Additional fields for organization key escrow
class Survey(models.Model):
    # Current fields remain (dual encryption + OIDC)
    encrypted_kek_org = models.BinaryField(null=True)  # Org-encrypted KEK
    recovery_threshold = models.IntegerField(default=3)
    recovery_shares_count = models.IntegerField(default=5)
```

**Key Storage:**
```python
# At survey creation
survey_kek = os.urandom(32)  # Master encryption key

# 1. Encrypt with user's password
user_key = derive_key_from_password(user.password)
survey.encrypted_kek_user = encrypt(survey_kek, user_key)

# 2. Encrypt with organization master key (from KMS)
org_master_key = kms_client.decrypt(organization.kms_key_id)
survey.encrypted_kek_org = encrypt(survey_kek, org_master_key)

# 3. Create recovery shares (optional)
shares = create_secret_shares(survey_kek, threshold=3, total=5)
# Distribute to designated org admins
```

**Recovery Workflow:**

1. **Normal Access**: User enters password → decrypt KEK → access data
2. **User Forgot Password**: Org ADMIN uses org master key → decrypt KEK → access data
3. **Catastrophic Loss**: 3 designated admins combine recovery shares → reconstruct KEK

**Audit Logging:**
```python
# Log all key access
AuditLog.objects.create(
    actor=admin_user,
    scope=AuditLog.Scope.SURVEY,
    action=AuditLog.Action.KEY_RECOVERY,
    survey=survey,
    metadata={"recovery_method": "organization_master_key"}
)
```

### Option 2: Individual Users (Personal Responsibility)

**For individual users not part of an organization**, implement **User-Controlled with Recovery Code**:

#### Architecture

```
Survey Encryption Key (KEK)
├─ Password-Encrypted Copy
│  └─ Encrypted with user's password-derived key
│
└─ Recovery Code-Encrypted Copy
   └─ Encrypted with recovery phrase-derived key
      └─ BIP39-style 12-24 word recovery phrase
      └─ Shown ONCE at creation
      └─ User MUST save securely
```

#### Benefits

- **User Maintains Control**: True zero-knowledge architecture
- **Dual Recovery**: Password OR recovery code can decrypt
- **No Third-Party**: No organizational key escrow
- **Simple**: Straightforward implementation
- **Privacy**: Maximum patient privacy

#### Risks and Mitigations

⚠️ **Risk**: If user loses both password AND recovery code → permanent data loss

**Mitigations:**
- Clear warnings at survey creation
- Force download of recovery code file
- Email recovery code (encrypted with user's public key)
- Require acknowledgment: "I understand data loss is permanent"
- Provide key strength verification tool

#### Implementation Details

**Database Schema:**
```python
class Survey(models.Model):
    # Current fields remain
    key_salt = models.BinaryField()
    key_hash = models.BinaryField()

    # New fields for Option 2
    encrypted_kek_password = models.BinaryField()  # Password-encrypted
    encrypted_kek_recovery = models.BinaryField()  # Recovery code-encrypted
    recovery_code_hint = models.CharField(max_length=100, blank=True)
```

**Key Storage:**
```python
# At survey creation
survey_kek = os.urandom(32)

# Generate BIP39-style recovery phrase
recovery_phrase = generate_bip39_phrase(words=12)  # e.g., "apple tree house..."

# 1. Encrypt with user's password
password_key = derive_key_from_password(user.password)
survey.encrypted_kek_password = encrypt(survey_kek, password_key)

# 2. Encrypt with recovery phrase
recovery_key = derive_key_from_passphrase(recovery_phrase)
survey.encrypted_kek_recovery = encrypt(survey_kek, recovery_key)

# Show user ONCE with clear warnings
return {
    "survey_key_b64": base64.b64encode(survey_kek).decode(),
    "recovery_phrase": recovery_phrase,
    "warning": "⚠️ SAVE BOTH SECURELY. Without them, encrypted data is permanently lost."
}
```

**UI Workflow:**

```html
<!-- Survey Creation Success -->
<div class="alert alert-warning">
  <h3>⚠️ Critical: Save Your Encryption Keys</h3>
  <p>Your survey uses end-to-end encryption for patient data.</p>

  <div class="card">
    <h4>Survey Encryption Key</h4>
    <code>{{ survey_key_b64 }}</code>
    <button>Download Key File</button>
  </div>

  <div class="card">
    <h4>Recovery Phrase (12 Words)</h4>
    <code>{{ recovery_phrase }}</code>
    <button>Download Recovery File</button>
  </div>

  <div class="checkbox">
    <input type="checkbox" required>
    <label>
      I have saved both the encryption key and recovery phrase.
      I understand that losing both will result in permanent data loss.
    </label>
  </div>
</div>
```

### Account Type Detection

The system automatically determines which option to use:

```python
def get_encryption_strategy(user: User, survey: Survey) -> str:
    """Determine encryption strategy based on user type."""

    # Check if user belongs to an organization
    if user.organization_memberships.exists():
        return "organization"  # Use Option 1

    # Individual user
    return "individual"  # Use Option 2
```

### Clear Communication at Signup

**For Organization Members:**
```
✅ Your organization can recover lost encryption keys
✅ Organization admins can access data if you're unavailable
✅ All key access is logged for compliance
✅ Multi-person approval required for emergency recovery
```

**For Individual Users:**
```
⚠️ You are solely responsible for your encryption keys
⚠️ Lost keys = permanent data loss (no recovery possible)
⚠️ Save your recovery phrase in a secure location
⚠️ Consider using a password manager
⚠️ Recommended: Print and store recovery phrase offline
```

## Implementation Roadmap

### ✅ Phase 1: Dual Encryption (COMPLETED - October 2025)

**Option 2: Individual Users with Dual Paths**
- Password + BIP39 recovery phrase ✅
- AES-GCM authenticated encryption ✅
- Forward secrecy session security ✅
- Cross-survey isolation ✅
- Legacy compatibility ✅
- Production test coverage ✅

### ✅ Phase 2: OIDC Authentication (COMPLETED - October 2025)

**OIDC Integration Features:**
- OpenID Connect authentication with multiple providers ✅
- Google, Microsoft, Azure, and custom OIDC provider support ✅
- Automatic survey unlocking for OIDC-authenticated users ✅
- OIDC identity-based key derivation with unique user salts ✅
- Triple encryption: Password + Recovery Phrase + OIDC automatic unlock ✅
- Backward compatibility with existing dual encryption ✅
- Comprehensive test coverage (8/8 OIDC tests passing) ✅

**Current Status**: **PRODUCTION READY** for clinicians and organizations

### 🚀 Phase 3: Organization Key Management (FUTURE)

**Option 1: Organization Users with Key Escrow**
- User encryption (primary access) via Option 2 + OIDC
- Organization recovery via AWS KMS/Azure Key Vault
- Optional multi-party recovery shares
- Full audit trail integration

**Use Case**: Large healthcare organizations requiring administrative recovery

---

## Security Best Practices

### For All Users

1. **Never share encryption keys** via email or messaging
2. **Use strong passwords** for account access
3. **Enable 2FA** on your account
4. **Regularly backup** recovery codes offline
5. **Test recovery** process before collecting real data

### For Organization Admins

1. **Rotate KMS keys** annually
2. **Maintain audit logs** of all key access
3. **Designate recovery admins** carefully (trusted individuals)
4. **Document procedures** in disaster recovery plan
5. **Regular security reviews** of key management

### For Individual Users

1. **Store recovery phrase** in password manager
2. **Print recovery phrase** and store in safe location
3. **Never lose both** password and recovery phrase
4. **Test recovery** before collecting patient data
5. **Consider organizational account** for critical data

## Compliance and Regulations

### GDPR Compliance

✅ **Data Minimization**: Only necessary fields encrypted
✅ **Right to Erasure**: Survey deletion removes all encrypted data
✅ **Data Portability**: Export functionality available
✅ **Breach Notification**: Encrypted data protected even if breached
✅ **Audit Trail**: All access logged via `AuditLog`

### HIPAA Compliance (Healthcare Organizations)

✅ **Administrative Safeguards**: Role-based access control
✅ **Technical Safeguards**: AES-256 encryption, audit logs
✅ **Physical Safeguards**: KMS hardware security modules
✅ **Encryption**: Patient data encrypted at rest and in transit
✅ **Access Controls**: Multi-factor authentication required

### NHS Data Security Standards

✅ **Data Security**: End-to-end encryption
✅ **Secure Access**: Session-based key management
✅ **Audit**: Comprehensive logging
✅ **Incident Response**: Clear recovery procedures
✅ **Training**: Documentation for staff

## Migration and Upgrade Path

### For Existing Deployments

**Current Legacy Surveys**: Automatically supported without changes
**New Surveys**: Created with dual encryption (password + recovery phrase)
**User Experience**: Seamless transition with improved security

### Upgrade Considerations

**Database**: Migration `0011_survey_encryption_option2.py` adds new fields
**Backward Compatibility**: Legacy key-based surveys continue working
**Performance**: No impact on existing encrypted data
**Training**: Users need brief overview of recovery phrase workflow

### OIDC Migration (Future)

**Phase 1**: Add OIDC as optional authentication method
**Phase 2**: Gradual migration of users to OIDC providers
**Phase 3**: Enhanced features for OIDC-authenticated users

**Migration preserves all existing encryption** - users keep current survey access

## Technical Reference

### Encryption Utilities

```python
# checktick_app/surveys/utils.py

def encrypt_sensitive(passphrase_key: bytes, data: dict) -> bytes:
    """
    Encrypt sensitive data dictionary with AES-GCM.

    Args:
        passphrase_key: 32-byte encryption key
        data: Dictionary of sensitive fields

    Returns:
        Encrypted blob: salt(16) | nonce(12) | ciphertext
    """
    key, salt = derive_key(passphrase_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode("utf-8")
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return salt + nonce + ct

def decrypt_sensitive(passphrase_key: bytes, blob: bytes) -> dict:
    """
    Decrypt sensitive data blob.

    Args:
        passphrase_key: 32-byte encryption key
        blob: Encrypted blob from encrypt_sensitive()

    Returns:
        Decrypted dictionary

    Raises:
        InvalidTag: If ciphertext is tampered or key is wrong
    """
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(passphrase_key)
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(nonce, ct, None)
    return json.loads(pt.decode("utf-8"))
```

### Key Verification

```python
def make_key_hash(key: bytes) -> tuple[bytes, bytes]:
    """Create hash and salt for key verification."""
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000
    )
    digest = kdf.derive(key)
    return digest, salt

def verify_key(key: bytes, digest: bytes, salt: bytes) -> bool:
    """Verify a key matches stored hash."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000
    )
    try:
        kdf.verify(key, digest)
        return True
    except Exception:
        return False
```

## Testing

CheckTick includes comprehensive test coverage for encryption with **production-ready validation**:

### Unit Tests (46/46 ✅)

```bash
# Run all encryption unit tests
docker compose exec web python manage.py test checktick_app.surveys.tests.test_survey_unlock_view

# Run dual encryption tests
docker compose exec web python manage.py test checktick_app.surveys.tests.test_models

# Run utility function tests
docker compose exec web python manage.py test checktick_app.surveys.tests.test_utils
```

**Coverage:**
- Dual encryption setup and unlock ✅
- Password and recovery phrase validation ✅
- BIP39 phrase generation and normalization ✅
- Session security and timeouts ✅
- Legacy compatibility ✅
- Cross-survey isolation ✅

### Integration Tests (7/7 ✅)

```bash
# Run end-to-end encryption workflow tests
docker compose exec web python manage.py test tests.test_encryption_integration
```

**End-to-End Validation:**
1. **Complete Password Unlock Workflow** - Clinicians unlock with passwords ✅
2. **Recovery Phrase Workflow** - BIP39 backup method works end-to-end ✅
3. **Session Timeout Security** - 30-minute timeout enforced ✅
4. **Encrypted Data Export** - CSV export after unlock ✅
5. **Invalid Attempt Handling** - Wrong credentials rejected ✅
6. **Cross-Survey Isolation** - Survey encryption is isolated ✅
7. **Legacy Compatibility** - Existing surveys continue working ✅

### Test Implementation Notes

- **Real Encryption Used**: Tests use actual `survey.set_dual_encryption()` methods, not mocks
- **Production Workflow**: Integration tests validate the complete clinician workflow
- **Security Validation**: Forward secrecy, session isolation, and timeout behavior verified
- **Healthcare Ready**: Tests designed for healthcare deployment scenarios

### Performance Tests

```bash
# Test encryption performance under load
docker compose exec web python manage.py test checktick_app.surveys.tests.test_performance
```

## Related Documentation

- [Authentication and Permissions](authentication-and-permissions.md)
- [User Management](user-management.md)
- [API Reference](api.md)
- [Getting Started](getting-started.md)

## Support and Questions

For security-related questions or to report vulnerabilities:

- **Security Issues**: Please report privately via GitHub Security Advisories
- **General Questions**: Open a GitHub issue or discussion
- **Commercial Support**: Contact for healthcare deployment assistance

---

## 📋 Current Implementation Summary

**✅ PRODUCTION READY (October 2025)**

CheckTick implements a complete healthcare-grade encryption system with:

- **Triple Encryption Support**: Password + Recovery Phrase + OIDC automatic unlock
- **OIDC Integration**: Seamless SSO with Google, Microsoft, Azure, and custom providers
- **Healthcare Compliance**: Designed for clinical workflows with audit trails
- **Zero-Knowledge Architecture**: Server never stores encryption keys in plaintext
- **Comprehensive Testing**: 46/46 unit tests + 7/7 integration tests + 8/8 OIDC tests

**🎯 Next Priority**: Organization key escrow for administrative recovery

**Last Updated**: October 2025
**Version**: 3.0 (OIDC Integration Release)
