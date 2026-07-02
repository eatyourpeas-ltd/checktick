---
title: OIDC SSO Setup
category: configuration
priority: 5
---

This guide provides step-by-step instructions for setting up Single Sign-On (SSO) authentication for healthcare organisations using Google OAuth and Microsoft Azure AD.

## Overview

CheckTick supports healthcare SSO through:

- **Google OAuth**: For clinicians with personal Google accounts
- **Microsoft Azure AD**: For hospital staff with organisational Microsoft 365 accounts
- **Multi-provider support**: Users can authenticate via either method

## Prerequisites

Before starting, ensure you have:

- Administrator access to your Azure AD tenant (for Azure setup)
- Owner/Editor access to a Google Cloud Project (for Google setup)
- CheckTick deployment with HTTPS enabled (required for production)
- Access to your CheckTick environment variables

## Environment Variables

Add these variables to your `.env` file:

```bash
# Azure AD Configuration
OIDC_RP_CLIENT_ID_AZURE=your-azure-client-id
OIDC_RP_CLIENT_SECRET_AZURE=your-azure-client-secret
OIDC_OP_TENANT_ID_AZURE=your-azure-tenant-id

# Google OAuth Configuration
OIDC_RP_CLIENT_ID_GOOGLE=your-google-client-id
OIDC_RP_CLIENT_SECRET_GOOGLE=your-google-client-secret

# OIDC Protocol Configuration (required)
OIDC_RP_SIGN_ALGO=RS256
OIDC_OP_JWKS_ENDPOINT_GOOGLE=https://www.googleapis.com/oauth2/v3/certs
OIDC_OP_JWKS_ENDPOINT_AZURE=https://login.microsoftonline.com/common/discovery/v2.0/keys
```

## Azure AD Setup (Microsoft 365 Organisations)

### Step 1: Register Application in Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com/)
2. Go to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: `CheckTick Healthcare Platform`
   - **Supported account types**: **Accounts in any organizational directory and personal Microsoft accounts**
     - This is the recommended audience for CheckTick. It allows clinicians to sign in with personal Microsoft accounts (e.g. `outlook.com`, `hotmail.com`) today, and is also ready for future organizational SSO (e.g. NHS Login, hospital M365 tenants) without re-registering the app.
     - Other options:
       - **Accounts in this organizational directory only** (single tenant): use only if all clinicians belong to one Entra ID tenant. The configured `OIDC_OP_TENANT_ID_AZURE` will be used in endpoint URLs.
       - **Accounts in any organizational directory** (multitenant org): work/school accounts only; personal Microsoft accounts will be rejected with `unauthorized_client`.
       - **Personal Microsoft accounts only**: consumers only; no organizational SSO.
   - **Redirect URI**:
     - **Type**: Web (not SPA — CheckTick is a confidential client that stores a client secret server-side)
     - **URL**: `https://your-checktick-domain.com/oidc/callback/`
     - **Development**: Also add `http://localhost:8000/oidc/callback/`

> **Important — audience changes are not editable on an existing registration.**
> Azure does not allow changing `signInAudience` via the Manifest editor after creation (you will see `invalid specified value for property signInAudience` or `Property api.requestedAccessTokenVersion is invalid`). To switch audiences, create a **new** app registration with the desired account type selected at creation time. Azure automatically sets `requestedAccessTokenVersion: 1` for the personal+org audience — no manifest editing is required.
>
> **Token version note:** The personal+org audience requires access token version 1. This only affects the format of access tokens sent to Graph; the OIDC ID tokens that `mozilla-django-oidc` validates are still v2.0 RS256 and are validated against the v2.0 discovery/keys endpoints. No code changes are required.

### Step 2: Configure Application Settings

1. **Authentication** tab:
   - Under **Redirect URIs**, ensure your callback URLs are listed (platform type **Web**)
   - **Front-channel logout URL**: `https://your-checktick-domain.com/accounts/logout/`
   - **Implicit grant and hybrid flows**: Leave unchecked (CheckTick uses authorization code flow)

2. **Certificates & secrets** tab:
   - Click **New client secret**
   - **Description**: `CheckTick OIDC Secret`
   - **Expires**: Choose appropriate duration (24 months recommended)
   - **Copy the secret value** (this is your `OIDC_RP_CLIENT_SECRET_AZURE`)

3. **API permissions** tab:
   - Ensure these delegated permissions are present:
     - `openid` (OpenID Connect sign-in)
     - `profile` (View users' basic profile)
     - `email` (View users' email address)
     - `User.Read` (Read user profiles)
   - Click **Grant admin consent** if you have admin rights
   - These permissions work for both personal and organizational accounts

### Step 3: Note Configuration Values

From the **Overview** tab, copy:

- **Application (client) ID** → `OIDC_RP_CLIENT_ID_AZURE`
- **Directory (tenant) ID** → `OIDC_OP_TENANT_ID_AZURE`

> **Tenant ID usage:** CheckTick uses `OIDC_OP_TENANT_ID_AZURE` to build the Azure authorize/token/JWKS endpoint URLs. For the recommended personal+org audience, the tenant placeholder `/common/` is used at runtime (the configured tenant ID is still required for documentation and for future single-tenant deployments). If `OIDC_OP_TENANT_ID_AZURE` is empty, CheckTick falls back to `/common/`.

### Step 4: Configure External User Access (Optional)

For guest users (external clinicians):

1. Go to **Azure AD** > **External Identities** > **External collaboration settings**
2. Under **Guest user access**, ensure appropriate permissions
3. Under **Guest invite settings**, configure as needed

## Google Cloud Setup (Personal Google Accounts)

### Step 1: Create Google Cloud Project

1. Navigate to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing:
   - **Project name**: `CheckTick Healthcare SSO`
   - **Organisation**: Your healthcare organisation (if applicable)

### Step 2: Enable APIs

1. Go to **APIs & Services** > **Library**
2. Search and enable:
   - **Google+ API** (or **People API**)
   - **OpenID Connect API**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Choose **External** (unless using Google Workspace)
3. Configure:
   - **App name**: `CheckTick Healthcare Platform`
   - **User support email**: Your healthcare IT support email
   - **App domain**: Your CheckTick domain
   - **Authorized domains**: Add your CheckTick domain
   - **Developer contact**: Your IT contact email
4. **Scopes**: Add `openid`, `email`, `profile`
5. **Test users**: Add clinician emails for testing

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client IDs**
3. Configure:
   - **Application type**: Web application
   - **Name**: `CheckTick Healthcare SSO`
   - **Authorized redirect URIs**:
     - Production: `https://your-checktick-domain.com/oidc/callback/`
     - Development: `http://localhost:8000/oidc/callback/`

### Step 5: Note Configuration Values

Copy the generated:

- **Client ID** → `OIDC_RP_CLIENT_ID_GOOGLE`
- **Client Secret** → `OIDC_RP_CLIENT_SECRET_GOOGLE`

## Deployment Configuration

### Update Environment Variables

1. Add all OIDC variables to your production `.env` file
2. Restart your CheckTick application:

   ```bash
   docker compose restart web
   ```

### Verify Configuration

1. Navigate to your CheckTick login page
2. You should see:
   - "Sign in with Google" button
   - "Sign in with Microsoft" button
   - Traditional email/password login

### Test Authentication

1. **Test Google SSO**:
   - Click "Sign in with Google"
   - Authenticate with a Google account
   - Verify user creation and login

2. **Test Azure SSO**:
   - Click "Sign in with Microsoft"
   - Authenticate with a Microsoft 365 account
   - Verify user creation and login

## OIDC Encryption Integration

### Automatic Survey Unlocking

CheckTick now supports **automatic survey unlocking** for OIDC users. This feature:

- **Eliminates manual key entry** for SSO users
- **Seamlessly integrates** with existing password/recovery phrase encryption
- **Maintains security** through OIDC identity-based key derivation
- **Preserves backward compatibility** with traditional encryption methods

### How It Works

When creating an encrypted survey:

1. **Dual encryption is set up** with password + recovery phrase (as usual)
2. **OIDC encryption is automatically added** if the user has SSO authentication
3. **Same survey key** is encrypted three ways:
   - With user's password
   - With recovery phrase
   - With OIDC identity (automatic)

When unlocking a survey:

1. **OIDC users** are automatically unlocked when they sign in
2. **Fallback options** remain available (password/recovery phrase)
3. **Non-OIDC users** use traditional unlock methods

### User Experience

**For OIDC Users:**

- Create survey → Automatic encryption setup
- Access survey → Automatic unlock (no manual key entry), including surveys that collect patient data
- Green success message: "Survey automatically unlocked with your Google/Microsoft account"
- Optional: choose SSO + Recovery Phrase during encryption setup for a manual fallback

**For Traditional Users:**

- Standard password/recovery phrase workflow unchanged
- Can upgrade to OIDC authentication to gain automatic unlock

### Security Model

**Key Derivation:**

```
OIDC Key = PBKDF2(
    provider:subject,    # "google:12345" or "azure:user@hospital.org"
    user_salt,          # Unique 32-byte salt per user
    100000 iterations   # Same strength as password encryption
)
```

**Encryption Flow:**

1. Survey KEK encrypts all patient data
2. KEK is encrypted with OIDC-derived key
3. Encrypted KEK stored in `survey.encrypted_kek_oidc`
4. User's salt stored in `UserOIDC.key_derivation_salt`

**Access Control:**

- Only the exact OIDC identity can decrypt
- Provider + subject must match exactly
- Different providers/accounts cannot cross-decrypt

### Implementation Details

**Model Changes:**

- `Survey.encrypted_kek_oidc`: OIDC-encrypted survey key
- `Survey.has_oidc_encryption()`: Check if OIDC unlock available
- `Survey.unlock_with_oidc(user)`: Automatic unlock method
- `UserOIDC.key_derivation_salt`: Unique salt per OIDC user

**View Integration:**

- `survey_create`: Automatically adds OIDC encryption for SSO users
- `survey_unlock`: Attempts automatic unlock before manual methods
- Audit logging for all unlock methods including OIDC

**Template Updates:**

- Automatic unlock notification for OIDC users
- Visual indicators for encryption methods available
- Fallback UI for manual unlock when needed

### Migration and Compatibility

**Existing Surveys:**

- Continue to work with password/recovery phrase
- OIDC encryption can be added retroactively
- No disruption to existing workflows

**Mixed Authentication:**

- Users can have both OIDC and password authentication
- All unlock methods work independently
- Users can switch between authentication types

**Backward Compatibility:**

- Traditional encryption fully preserved
- API endpoints unchanged
- Existing integrations unaffected

## Security Considerations

### Production Requirements

- **HTTPS Required**: SSO only works with HTTPS in production
- **Secure Cookies**: Ensure `SECURE_SSL_REDIRECT=True`
- **CSRF Protection**: CheckTick automatically handles CSRF for SSO flows

### Redirect URI Security

- Always use exact redirect URIs (avoid wildcards)
- Use different OAuth apps for development vs production
- Regularly rotate client secrets

### User Account Linking

- Users are automatically linked via email address
- Same user can authenticate via multiple methods
- Encryption keys preserved across authentication methods

## Troubleshooting

### Common Issues

1. **"Redirect URI mismatch"**:
   - Verify exact callback URLs in cloud consoles
   - Check for trailing slashes and HTTP vs HTTPS

2. **"Invalid client"**:
   - Verify client ID and secret in environment variables
   - Check for extra spaces or quotes

3. **"unauthorized_client: The client does not exist or is not enabled for consumers"**:
   - The app registration's supported account types do not include personal Microsoft accounts, but the user is signing in with a personal account (`outlook.com`, `hotmail.com`, etc.).
   - Fix: create a new app registration with **Accounts in any organizational directory and personal Microsoft accounts** (see Step 1). This audience cannot be enabled on an existing org-only registration via the Manifest editor.

4. **"invalid specified value for property signInAudience"** or **"Property api.requestedAccessTokenVersion is invalid"** when saving the manifest:
   - Azure does not allow changing `signInAudience` on an existing registration. Create a new registration with the desired audience selected at creation time instead.

5. **"Access denied"**:
   - Verify API permissions in Azure AD
   - Check OAuth consent screen configuration in Google

6. **"Email not found"**:
   - Ensure `email` scope is requested
   - For Azure: verify `User.Read` permission

### Log Analysis

Enable debug logging to troubleshoot:

```bash
# In .env
DEBUG=True

# Check logs
docker compose logs web --follow
```

Look for:

- `CustomOIDCAuthenticationBackend.authenticate called`
- `Got userinfo:` with user data
- `Extracted email from UPN:` for Azure external users

### Development Testing

For local development:

```bash
# Use HTTP callback URLs
OIDC_CALLBACK_URL=http://localhost:8000/oidc/callback/

# Test with ngrok for HTTPS
ngrok http 8000
# Update cloud console redirect URIs with ngrok HTTPS URL
```

## Support

For additional help:

- Check CheckTick logs: `docker compose logs web`
- Review Azure AD sign-in logs in Azure Portal
- Check Google Cloud audit logs
- Contact your CheckTick administrator

## Example Production Configuration

```bash
# Production .env example
DEBUG=False
ALLOWED_HOSTS=checktick.hospital.org
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://checktick.hospital.org

# Azure AD for hospital staff
OIDC_RP_CLIENT_ID_AZURE=a1b2c3d4-e5f6-7890-abcd-ef1234567890
OIDC_RP_CLIENT_SECRET_AZURE=your-secret-from-azure
OIDC_OP_TENANT_ID_AZURE=hospital-tenant-id

# Google OAuth for external clinicians
OIDC_RP_CLIENT_ID_GOOGLE=123456789-abcdef.apps.googleusercontent.com
OIDC_RP_CLIENT_SECRET_GOOGLE=your-secret-from-google

# Protocol configuration (unchanged)
OIDC_RP_SIGN_ALGO=RS256
OIDC_OP_JWKS_ENDPOINT_GOOGLE=https://www.googleapis.com/oauth2/v3/certs
OIDC_OP_JWKS_ENDPOINT_AZURE=https://login.microsoftonline.com/common/discovery/v2.0/keys
```
