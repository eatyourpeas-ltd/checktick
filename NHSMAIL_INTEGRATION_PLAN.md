# NHSmail OIDC Integration Implementation Plan

**Status**: Implementation guide for NHSmail Single Sign-On via OIDC
**Date**: May 2026
**Scope**: Add NHSmail as third OIDC provider alongside Google and Azure
**Integration Point**: Encrypted survey auto-unlock via OIDC identity derivation

---

## Overview

This document scaffolds the implementation of NHSmail OIDC integration into CheckTick. The integration leverages the existing OIDC encryption workflow — each NHSmail user gets a unique derived key based on their NHSmail OIDC identity, enabling automatic survey unlock just like Google and Azure.

**Key Principle**: Provider="nhsmail" is routed through the same `CustomOIDCAuthenticationBackend`, issue/subject detection, claim mapping, and encryption key derivation as google/azure.

---

## Files to Modify

| File | Purpose | Changes |
|------|---------|---------|
| `checktick_app/settings.py` | OIDC provider config | Add nhsmail provider config + env vars |
| `checktick_app/core/oidc_views.py` | Provider routing & callback | Add nhsmail routing + claim handling |
| `checktick_app/core/auth.py` | User creation & claim mapping | Enhance claim normalization for NHSmail emails |
| `checktick_app/core/oidc_urls.py` | URL routing | Add nhsmail login button context |
| `docs/oidc-sso-setup.md` | Setup documentation | Add NHSmail section + registration steps |
| `checktick_app/templates/registration/healthcare_login.html` | Login page | Add NHSmail sign-in button |
| `checktick_app/core/tests/test_oidc_auth.py` | Auth tests | Add NHSmail provider tests |

**Optional**:

- `.env.example` — Add NHSmail env var examples
- CI/CD deployment docs — Document secret injection for NHSmail

---

## Implementation Steps

### 1. Environment Variables & Settings

**File**: `checktick_app/settings.py`

Add to the env config block (around line 49):

```python
# In ENV_VARS section (around line 49)
    OIDC_RP_CLIENT_ID_NHSMAIL=(str, ""),
    OIDC_RP_CLIENT_SECRET_NHSMAIL=(str, ""),
```

Add to the OIDC section (after line 729):

```python
# Around line 730, after AZURE config
OIDC_RP_CLIENT_ID_NHSMAIL = env("OIDC_RP_CLIENT_ID_NHSMAIL")
OIDC_RP_CLIENT_SECRET_NHSMAIL = env("OIDC_RP_CLIENT_SECRET_NHSMAIL")
OIDC_OP_JWKS_ENDPOINT_NHSMAIL = "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/discovery/v2.0/keys"
```

Add to `OIDC_PROVIDERS` dict (after line 762, after azure block):

```python
    "nhsmail": {
        "OIDC_RP_CLIENT_ID": OIDC_RP_CLIENT_ID_NHSMAIL,
        "OIDC_RP_CLIENT_SECRET": OIDC_RP_CLIENT_SECRET_NHSMAIL,
        "OIDC_OP_AUTHORIZATION_ENDPOINT": "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/authorize",
        "OIDC_OP_TOKEN_ENDPOINT": "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/token",
        "OIDC_OP_USER_ENDPOINT": "https://graph.microsoft.com/oidc/userinfo",
        "OIDC_OP_JWKS_ENDPOINT": OIDC_OP_JWKS_ENDPOINT_NHSMAIL,
        "OIDC_RP_SCOPES": "openid email profile",
    },
```

**Why the specific tenant ID**: `37c354b2-85b0-47f5-b222-07b48d774ee3` is the NHSmail Entra ID tenant documented in their technical guidance. This ensures tokens are validated against NHSmail's keys, not generic Azure common endpoint.

---

### 2. Provider Routing in OIDC Views

**File**: `checktick_app/core/oidc_views.py`

**In `HealthcareOIDCAuthView.get()` (line 217-234)**, add nhsmail support:

```python
def get(self, request: HttpRequest) -> HttpResponse:
    """Initiate OIDC authentication for specified provider."""
    provider = request.GET.get("provider", "google")
    signup_mode = request.GET.get("signup") == "true"
    logger.info(
        f"Starting OIDC authentication for provider: {provider}, signup_mode: {signup_mode}"
    )

    request.session["oidc_provider"] = provider
    if signup_mode:
        request.session["oidc_signup_mode"] = True

    # Configure OIDC settings based on provider
    if provider == "azure":
        self._configure_azure_settings()
    elif provider == "nhsmail":
        self._configure_nhsmail_settings()
    else:
        self._configure_google_settings()

    return super().get(request)
```

**Add new method** (after `_configure_azure_settings`, around line 269):

```python
def _configure_nhsmail_settings(self) -> None:
    """Configure instance variables for NHSmail OIDC."""
    logger.info("Configuring NHSmail OIDC settings")
    self.OIDC_RP_CLIENT_ID = settings.OIDC_RP_CLIENT_ID_NHSMAIL
    self.OIDC_RP_CLIENT_SECRET = settings.OIDC_RP_CLIENT_SECRET_NHSMAIL
    self.OIDC_OP_AUTH_ENDPOINT = (
        "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/authorize"
    )
    self.OIDC_OP_AUTHORIZATION_ENDPOINT = (
        "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/authorize"
    )
    self.OIDC_OP_TOKEN_ENDPOINT = (
        "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/token"
    )
    self.OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
    self.OIDC_OP_JWKS_ENDPOINT = settings.OIDC_OP_JWKS_ENDPOINT_NHSMAIL
    # NHSmail standard scopes; allatclaims optional if you need token-contained claims
    self.OIDC_RP_SCOPES = "openid email profile"
```

**In `HealthcareOIDCCallbackView.get()` (line 42-76)**, add nhsmail elif:

```python
original_settings = {}
try:
    if provider == "azure":
        logger.info("Temporarily setting Django settings for Azure")
        # ... existing azure block ...
    elif provider == "nhsmail":
        logger.info("Temporarily setting Django settings for NHSmail")
        # Store original values
        original_settings["OIDC_RP_CLIENT_ID"] = settings.OIDC_RP_CLIENT_ID
        original_settings["OIDC_RP_CLIENT_SECRET"] = settings.OIDC_RP_CLIENT_SECRET
        original_settings["OIDC_OP_TOKEN_ENDPOINT"] = settings.OIDC_OP_TOKEN_ENDPOINT
        original_settings["OIDC_OP_USER_ENDPOINT"] = settings.OIDC_OP_USER_ENDPOINT
        original_settings["OIDC_OP_JWKS_ENDPOINT"] = settings.OIDC_OP_JWKS_ENDPOINT
        original_settings["OIDC_RP_SCOPES"] = getattr(settings, "OIDC_RP_SCOPES", "openid email")

        # Set NHSmail values
        settings.OIDC_RP_CLIENT_ID = settings.OIDC_RP_CLIENT_ID_NHSMAIL
        settings.OIDC_RP_CLIENT_SECRET = settings.OIDC_RP_CLIENT_SECRET_NHSMAIL
        settings.OIDC_OP_TOKEN_ENDPOINT = (
            "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/oauth2/v2.0/token"
        )
        settings.OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
        settings.OIDC_OP_JWKS_ENDPOINT = settings.OIDC_OP_JWKS_ENDPOINT_NHSMAIL
        settings.OIDC_RP_SCOPES = "openid email profile"

        logger.info(f"Set NHSmail token endpoint: {settings.OIDC_OP_TOKEN_ENDPOINT}")
```

---

### 3. Claim Mapping & Provider Detection

**File**: `checktick_app/core/auth.py`

**Update `_get_provider_from_claims()` (line 352-363)** to be more robust:

```python
def _get_provider_from_claims(self, claims: Dict[str, Any]) -> str:
    """Determine OIDC provider from claims."""
    issuer = claims.get("iss", "")

    if "accounts.google.com" in issuer:
        return "google"
    elif "37c354b2-85b0-47f5-b222-07b48d774ee3" in issuer:
        # NHSmail uses this specific Entra tenant ID
        return "nhsmail"
    elif "login.microsoftonline.com" in issuer:
        # Generic Azure (must check NHSmail tenant first)
        return "azure"
    else:
        return "unknown"
```

**Enhance `get_userinfo()` to handle NHSmail email claims (line 92-162)**:

After the Azure section (around line 131), add NHSmail handling:

```python
            if provider == "nhsmail" and userinfo:
                # NHSmail returns email in 'email', 'EmailAddress', or 'upn'
                if "email" not in userinfo or not userinfo.get("email"):
                    # Try EmailAddress (NHSmail OIDC claim from profile scope)
                    if "EmailAddress" in userinfo and userinfo["EmailAddress"]:
                        userinfo["email"] = userinfo["EmailAddress"]
                        logger.info(f"Extracted email from EmailAddress: {userinfo['email']}")
                    # Fallback to upn (User Principal Name = email in NHSmail)
                    elif "upn" in userinfo and userinfo["upn"]:
                        userinfo["email"] = userinfo["upn"]
                        logger.info(f"Extracted email from upn: {userinfo['email']}")

            return userinfo
```

**Update fallback provider detection (line 142-162)** to include NHSmail:

```python
            # Fallback to determining provider from token issuer
            if not provider:
                issuer = payload.get("iss", "")
                if "accounts.google.com" in issuer:
                    provider = "google"
                elif "37c354b2-85b0-47f5-b222-07b48d774ee3" in issuer:
                    provider = "nhsmail"
                elif "login.microsoftonline.com" in issuer:
                    provider = "azure"

            if provider == "google":
                return self._get_google_userinfo(access_token)
            elif provider == "nhsmail":
                # NHSmail follows standard OIDC; super().get_userinfo should work
                # but fallback to userinfo endpoint if needed
                try:
                    return super().get_userinfo(access_token, id_token, payload)
                except Exception as e:
                    logger.warning(f"NHSmail standard userinfo failed: {e}, trying graph endpoint")
                    return self._get_nhsmail_userinfo(access_token)
            elif provider == "azure":
                return self._get_azure_userinfo(access_token)
            else:
                logger.warning(f"Unknown OIDC provider: {provider}")
                raise
```

**Add NHSmail userinfo fallback method (after `_get_azure_userinfo()`, around line 215)**:

```python
def _get_nhsmail_userinfo(self, access_token: str) -> Dict[str, Any]:
    """Get userinfo from NHSmail Graph OIDC endpoint."""
    try:
        import requests

        response = requests.get(
            "https://graph.microsoft.com/oidc/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        userinfo = response.json()
        logger.info(f"NHSmail Graph userinfo: {list(userinfo.keys())}")

        # NHSmail returns 'email', 'EmailAddress', or 'upn'
        if "email" not in userinfo or not userinfo.get("email"):
            if "EmailAddress" in userinfo and userinfo["EmailAddress"]:
                userinfo["email"] = userinfo["EmailAddress"]
            elif "upn" in userinfo and userinfo["upn"]:
                userinfo["email"] = userinfo["upn"]

        return userinfo
    except Exception as e:
        logger.error(f"Failed to get NHSmail userinfo: {e}")
        raise
```

---

### 4. Login Page Button

**File**: `checktick_app/core/oidc_urls.py`

Update `HealthcareLoginView.get()` context (line 304-312):

```python
def get(self, request: HttpRequest) -> HttpResponse:
    """Display healthcare login options."""
    context = {
        "google_login_url": reverse("oidc:oidc_authentication_init") + "?provider=google",
        "azure_login_url": reverse("oidc:oidc_authentication_init") + "?provider=azure",
        "nhsmail_login_url": reverse("oidc:oidc_authentication_init") + "?provider=nhsmail",
        "traditional_login_url": reverse("login"),
        "next": request.GET.get("next", "/surveys/"),
    }
    return render(request, self.template_name, context)
```

**File**: `checktick_app/templates/registration/healthcare_login.html`

Add NHSmail button (after Azure button, before traditional login):

```html
<!-- NHSmail SSO -->
<a href="{{ nhsmail_login_url }}" class="btn btn-outline-primary btn-lg w-100 mb-2">
    <i class="fas fa-envelope"></i> Sign in with NHSmail
</a>
```

---

### 5. Documentation

**File**: `docs/oidc-sso-setup.md`

Add new section after "## Google Cloud Setup" section, before "## Deployment Configuration":

```markdown
## NHSmail Setup (NHS Organisation SSO)

### Prerequisites

- Recognised NHS organisation with valid ODS code
- Authority to submit SSO onboarding request
- Redirect URI: `https://your-checktick-domain.com/oidc/callback/` (must be HTTPS, no wildcards, no querystring)

### Step 1: Submit Onboarding Request

1. Download the **NHSmail Single Sign-On Request Form** from [NHSmail Support Site](https://support.nhs.net/)
2. Complete the form with:
   - **Application Name**: CheckTick Healthcare Platform
   - **Scope/Purpose**: Clinical survey and audit data collection
   - **Redirect URIs**: `https://your-checktick-domain.com/oidc/callback/`
   - **Scopes**: `openid`, `email`, `profile`
   - **Security Group**: Select appropriate MFA policy (recommend: "Require MFA on all requests")
   - **Claims**: Select Email, UserPrincipalName, DisplayName, ODS (if applicable)
3. Email the completed form to `helpdesk@nhs.net` with subject: "Single Sign On application onboarding request"
4. If your application requires **Azure AD authentication**, submit an additional **Application Assessment Request** at https://support.nhs.net/knowledge-base/request-an-application-assessment/

### Step 2: Receive Credentials

On approval, NHSmail will provide:
- **Client ID** (`client_id`) → `OIDC_RP_CLIENT_ID_NHSMAIL`
- **Client Secret** (`client_secret`) → `OIDC_RP_CLIENT_SECRET_NHSMAIL`
- Confirmation of registered redirect URI

### Step 3: Configure Environment Variables

Add to your `.env`:

```bash
# NHSmail OIDC Configuration
OIDC_RP_CLIENT_ID_NHSMAIL=<your-nhsmail-client-id>
OIDC_RP_CLIENT_SECRET_NHSMAIL=<your-nhsmail-client-secret>
```

### Step 4: Deploy and Test

1. Restart your application with new environment variables
2. Navigate to login page — you should see "Sign in with NHSmail" button
3. Click and authenticate with your NHS email account
4. Verify user is created with correct email and OIDC provider set to "nhsmail"

### Key Differences from Azure/Google

| Aspect | NHSmail | Azure | Google |
|--------|---------|-------|--------|
| Issuer | `https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/v2.0` | `https://login.microsoftonline.com/common/v2.0` | `https://accounts.google.com` |
| JWKS Endpoint | NHSmail tenant-specific | Azure common | Google |
| Registration | Manual form + assessment | Azure Portal | Google Cloud Console |
| Email Claim | `email` or `upn` | `mail` or `userPrincipalName` | `email` |
| Token Audience | Client ID | Client ID | Client ID |
| MFA Policy | Configurable per app | Per-user or org-wide | Per-user |

### Troubleshooting NHSmail Integration

**"Redirect URI mismatch"**

- Verify exact URL matches what you registered (including trailing slash, https, no querystring)
- Check for typos in domain name

**"Access denied"**

- Ensure your user account is authorized by your NHS organisation's admin
- Check that your application assessment passed if required

**"Email not found in claims"**

- NHSmail may return `upn` (User Principal Name) instead of `email`
- Application automatically maps `upn` to email; if still failing, contact NHSmail support
- Verify `email` and `profile` scopes are requested

**User creation fails**

- Check logs for claim extraction errors
- Ensure `email`/`upn` claim is present in token (request it in `claims` parameter if needed)

```

---

### 6. Tests

**File**: `checktick_app/core/tests/test_oidc_auth.py`

Add NHSmail provider tests:

```python
def test_nhsmail_provider_detection(self):
    """Test that NHSmail issuer is correctly detected."""
    claims = {
        "iss": "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/v2.0",
        "sub": "nhsmail_subject_123",
        "email": "alice@nhs.net",
    }
    backend = CustomOIDCAuthenticationBackend()
    provider = backend._get_provider_from_claims(claims)
    self.assertEqual(provider, "nhsmail")

def test_nhsmail_email_claim_normalization(self):
    """Test that NHSmail upn claim is normalized to email."""
    userinfo = {
        "sub": "nhsmail_subject_456",
        "upn": "bob@nhs.net",
        "given_name": "Bob",
        "family_name": "Smith",
    }
    # Simulate NHSmail userinfo response
    # Expect email to be extracted from upn
    self.assertEqual(userinfo.get("upn"), "bob@nhs.net")
    # After processing, email should be set
    if "email" not in userinfo:
        userinfo["email"] = userinfo.get("upn")
    self.assertEqual(userinfo.get("email"), "bob@nhs.net")

def test_nhsmail_user_creation_with_oidc_encryption(self):
    """Test that NHSmail OIDC user gets correct encryption key derivation."""
    claims = {
        "iss": "https://login.microsoftonline.com/37c354b2-85b0-47f5-b222-07b48d774ee3/v2.0",
        "sub": "nhsmail_789",
        "email": "charlie@nhs.net",
        "given_name": "Charlie",
        "family_name": "Jones",
    }
    backend = CustomOIDCAuthenticationBackend()
    user = backend.create_user(claims)

    # User should be created
    self.assertIsNotNone(user)
    self.assertEqual(user.email, "charlie@nhs.net")

    # UserOIDC record should link NHSmail provider
    from checktick_app.core.models import UserOIDC
    oidc_record = UserOIDC.objects.get(user=user, provider="nhsmail")
    self.assertEqual(oidc_record.subject, "nhsmail_789")

    # Encryption key should be derived from nhsmail provider
    from checktick_app.core.auth import derive_key_from_oidc_identity
    key = derive_key_from_oidc_identity("nhsmail", "nhsmail_789", oidc_record.key_derivation_salt)
    self.assertEqual(len(key), 32)  # 32 bytes for encryption
```

---

## Deployment & Go-Live Checklist

### Before Code Deployment

- [ ] **NHSmail Onboarding Approved**
  - Application assessment completed (if required)
  - Client ID and Secret received from NHSmail
  - Redirect URI registered in NHSmail: `https://your-domain/oidc/callback/`

- [ ] **DNS & HTTPS**
  - Domain is HTTPS-ready and certificate is valid
  - No HTTPS warnings for redirect domain

- [ ] **Environment Setup**
  - Secrets manager configured (e.g., HashiCorp Vault, AWS Secrets Manager, GitHub Secrets)
  - `OIDC_RP_CLIENT_ID_NHSMAIL` and `OIDC_RP_CLIENT_SECRET_NHSMAIL` values stored securely
  - Access controlled — only deployment pipeline can read

### Code Deployment

- [ ] All changes from Implementation Steps 1–6 merged to `main`
- [ ] Tests passing: `s/test --no-a11y` or equivalent
- [ ] Linting passing: `s/lint`
- [ ] Code review approved

### Post-Deployment

- [ ] Inject NHSmail env vars into production environment
- [ ] Restart application (e.g., `docker compose restart web`)
- [ ] Verify login page displays "Sign in with NHSmail" button
- [ ] **Test with pilot NHS user**:
  1. Click "Sign in with NHSmail"
  2. Authenticate with NHS email (e.g., user@nhs.net)
  3. Verify redirect to surveys page (not signup)
  4. Create encrypted survey, verify auto-unlock works
  5. Check logs for provider="nhsmail" in UserOIDC records

### Ongoing Operations

- [ ] **Monitoring**: Alert if NHSmail token endpoint returns errors (5xx)
- [ ] **Secret Rotation**: Establish process to rotate `OIDC_RP_CLIENT_SECRET_NHSMAIL` annually
- [ ] **Support Escalation**: Document NHSmail support contact (helpdesk@nhs.net) for authentication issues
- [ ] **Audit Logging**: Ensure all NHSmail logins are logged (already done via django-axes / UserOIDC records)
- [ ] **Multi-Provider Account Linking**: Test that same user can link google + azure + nhsmail accounts

---

## Security Considerations

1. **Client Secret Storage**: Never commit or log client secrets. Use environment variables or secrets manager.
2. **Redirect URI Exactness**: NHSmail requires exact redirect URI match (no wildcards, no query parameters). Verify registration matches deployment domain.
3. **HTTPS Enforcement**: Redirect URIs must use HTTPS. Never test with `http://` in production.
4. **Token Validation**: `CustomOIDCAuthenticationBackend` validates token signature using JWKS endpoint (tenant-specific for NHSmail). This is automatic via mozilla-django-oidc.
5. **Claim Validation**: Issuer and audience are validated. If either mismatches, authentication fails.
6. **Email Domain Validation (Optional)**: Consider restricting to `@nhs.net` domain if only NHS staff should use this OIDC provider:
   ```python
   if provider == "nhsmail":
       if not email.endswith("@nhs.net"):
           raise SuspiciousOperation("NHSmail user must have @nhs.net email")
   ```

---

## Files Summary

### Modified Files

| File | Lines Changed | Reason |
|------|---------------|--------|
| `checktick_app/settings.py` | ~15 | Add NHSmail env vars, provider config, tenant-specific endpoints |
| `checktick_app/core/oidc_views.py` | ~40 | Add nhsmail routing in auth view + callback, settings config method |
| `checktick_app/core/auth.py` | ~30 | Add NHSmail claim mapping, userinfo fallback, issuer detection |
| `checktick_app/core/oidc_urls.py` | ~3 | Add nhsmail_login_url to context |
| `checktick_app/templates/registration/healthcare_login.html` | ~3 | Add NHSmail button |
| `docs/oidc-sso-setup.md` | ~80 | Add NHSmail setup section + troubleshooting |
| `checktick_app/core/tests/test_oidc_auth.py` | ~50 | Add NHSmail provider tests |

**Total**: ~220 lines of new/modified code

### No Changes Needed

- `checktick_app/core/models.py` — UserOIDC model already supports provider="nhsmail"
- `checktick_app/surveys/views.py` — Encryption key derivation already provider-agnostic
- `.env` — Just add new NHSmail vars

---

## Testing Scenarios

1. **Happy path**: NHS user → NHSmail login → auto-unlock encrypted survey ✓
2. **Account linking**: Same email via Google + NHSmail → both providers linked, separate encryption keys ✓
3. **Claim fallback**: NHSmail returns `upn` instead of `email` → email extracted and user created ✓
4. **Token validation fail**: Invalid issuer in token → authentication fails, redirect to login ✓
5. **Missing email claim**: Token lacks email/upn → user creation fails with clear error ✓
6. **New user via NHSmail**: Creates account, sets provider="nhsmail", encryption key derived ✓
7. **Existing user + NHSmail**: Finds by email, links UserOIDC record with provider="nhsmail" ✓

---

## Go-Live Success Criteria

- [ ] NHSmail button visible and clickable on login page
- [ ] Clicking NHSmail button redirects to NHSmail login
- [ ] NHS user authenticates and is redirected to surveys
- [ ] User record created with correct email and provider="nhsmail"
- [ ] Encrypted survey can be created and auto-unlocks for NHSmail user
- [ ] Logs show no errors related to token validation or claim mapping
- [ ] NHSmail users can link existing account (email match)
- [ ] Multi-provider account linking works (user has google + azure + nhsmail records)
- [ ] Pilot users report successful experience

---

## Rollback Plan

If critical issues arise:

1. Remove NHSmail provider from `OIDC_PROVIDERS` in settings
2. Remove NHSmail button from login template
3. Restart application
4. Existing NHSmail UserOIDC records will persist (not deleted) for recovery

This keeps code in place but disables the feature until fixed.

---

## Next Steps

1. Obtain NHSmail credentials (submit form, wait for approval)
2. Implement changes from Implementation Steps 1–6
3. Run tests: `s/test --no-a11y` && `s/lint`
4. Deploy to staging with NHSmail credentials
5. Run testing scenarios above
6. Collect NHS pilot user feedback
7. Deploy to production with go-live checklist
