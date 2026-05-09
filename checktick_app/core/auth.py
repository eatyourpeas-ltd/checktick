"""
Custom OIDC Authentication Backend for Clinicians

Integrates Google and Azure OIDC authentication with the existing
patient data encryption system. Maintains your custom user model
as the source of truth while enabling SSO convenience.

Features:
- OIDC-derived encryption keys for seamless survey access
- No manual key entry required for OIDC users
- Maintains backward compatibility with password-based users
- Supports multiple OIDC providers per user account
"""

import logging
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

User = get_user_model()
logger = logging.getLogger(__name__)


def generate_username(email: str) -> str:
    """
    Generate a username from email for OIDC users.

    Clinicians may have multiple accounts (hospital + personal),
    so we use email as the primary identifier.
    """
    return email.lower()


def derive_key_from_oidc_identity(
    oidc_provider: str, oidc_subject: str, user_salt: bytes
) -> bytes:
    """
    Derive encryption key from OIDC identity.

    This creates a stable encryption key based on the user's OIDC identity
    that doesn't change when they change their password at the provider.

    Args:
        oidc_provider: Provider name (google, azure, etc.)
        oidc_subject: OIDC subject identifier (stable per user)
        user_salt: Unique salt for this user

    Returns:
        32-byte encryption key
    """
    # Combine provider + subject for uniqueness across providers
    identity = f"{oidc_provider}:{oidc_subject}".encode("utf-8")

    # Use PBKDF2 with user-specific salt for key derivation
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=user_salt, iterations=200_000
    )

    return kdf.derive(identity)


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Custom OIDC backend that integrates with healthcare encryption system.

    Features:
    - Links OIDC accounts to existing custom user model
    - Preserves encryption keys tied to stable user IDs
    - Supports both Google and Azure authentication
    - Allows multiple OIDC providers per user
    """

    def authenticate(self, request, **credentials):
        """Override to ensure backend is used during OIDC callback."""
        logger.info("CustomOIDCAuthenticationBackend.authenticate called")

        # Only handle OIDC authentication - if this looks like username/password auth, skip
        if "username" in credentials and "password" in credentials:
            logger.info("Username/password credentials detected, skipping OIDC backend")
            return None

        self.request = request
        result = super().authenticate(request, **credentials)
        logger.info(f"Authentication result: {result}")
        return result

    def get_userinfo(
        self, access_token: str, id_token: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get user info from the appropriate provider based on session or token issuer."""

        # For now, let's use the default implementation and add provider detection later
        logger.info("Getting OIDC userinfo...")

        # Try default implementation first
        try:
            # Get user information from OIDC provider
            userinfo = super().get_userinfo(access_token, id_token, payload)
            logger.info(f"Got userinfo: {userinfo}")

            # Handle Azure-specific email extraction
            provider = None
            if hasattr(self, "request") and self.request.session.get("oidc_provider"):
                provider = self.request.session.get("oidc_provider")

            if provider == "azure" and userinfo:
                # For Azure, handle email extraction from userPrincipalName if mail is None
                if ("email" not in userinfo or not userinfo.get("email")) and (
                    "mail" not in userinfo or not userinfo.get("mail")
                ):
                    if "userPrincipalName" in userinfo:
                        upn = userinfo["userPrincipalName"]
                        logger.info(f"Extracting email from Azure UPN: {upn}")

                        if "#EXT#" in upn:
                            # Extract email before #EXT# and convert underscores back to @
                            email_part = upn.split("#EXT#")[0]
                            if "_" in email_part:
                                # Convert first underscore back to @
                                email = email_part.replace("_", "@", 1)
                                userinfo["email"] = email
                                logger.info(f"Extracted email from UPN: {email}")
                            else:
                                userinfo["email"] = upn
                        else:
                            userinfo["email"] = upn

            return userinfo
        except Exception as e:
            logger.error(f"Error getting userinfo: {e}")

            # Fallback to manual provider detection
            provider = None
            if hasattr(self, "request") and self.request.session.get("oidc_provider"):
                provider = self.request.session.get("oidc_provider")

            # Fallback to determining provider from token issuer
            if not provider:
                issuer = payload.get("iss", "")
                if "accounts.google.com" in issuer:
                    provider = "google"
                elif "login.microsoftonline.com" in issuer:
                    provider = "azure"

            if provider == "google":
                return self._get_google_userinfo(access_token)
            elif provider == "azure":
                return self._get_azure_userinfo(access_token)
            else:
                logger.warning(f"Unknown OIDC provider: {provider}")
                raise

    def _get_google_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Get user info from Google's userinfo endpoint."""
        import requests

        response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _get_azure_userinfo(self, access_token):
        """Get userinfo from Azure OIDC userinfo endpoint (works with openid scope)."""
        try:
            import requests

            response = requests.get(
                "https://graph.microsoft.com/oidc/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            userinfo = response.json()
            logger.info(f"Azure Graph userinfo: {list(userinfo.keys())}")

            # Microsoft Graph returns 'mail' or 'userPrincipalName' for email
            if "mail" in userinfo and userinfo["mail"]:
                userinfo["email"] = userinfo["mail"]
            elif "userPrincipalName" in userinfo:
                # For external users, userPrincipalName might be like:
                # 'eatyourpeasapps_gmail.com#EXT#@eatyourpeasappsgmail.onmicrosoft.com'
                # Extract the original email
                upn = userinfo["userPrincipalName"]
                if "#EXT#" in upn:
                    # Extract email before #EXT# and convert underscores back to @
                    email_part = upn.split("#EXT#")[0]
                    if "_" in email_part:
                        # Convert first underscore back to @
                        email = email_part.replace("_", "@", 1)
                        userinfo["email"] = email
                        logger.info(f"Extracted email from UPN: {email}")
                    else:
                        userinfo["email"] = upn
                else:
                    userinfo["email"] = upn

            return userinfo
        except Exception as e:
            logger.error(f"Failed to get Azure userinfo: {e}")
            return None

    def create_user(self, claims: Dict[str, Any]):
        """
        Create a new user from OIDC claims.

        Creates basic OIDC user account with UserOIDC relationship.
        """

        email = claims.get("email")
        if not email:
            raise SuspiciousOperation("OIDC user missing email claim")

        # Determine provider from claims
        provider = self._get_provider_from_claims(claims)

        # Get subject identifier - Azure uses 'id', others typically use 'sub'
        subject_id = claims.get("sub") or claims.get("id")

        if not subject_id:
            logger.error(
                f"OIDC user missing subject identifier. Available claims: {list(claims.keys())}"
            )
            raise SuspiciousOperation("OIDC user missing subject identifier")

        # Generate username from email
        username = generate_username(email)

        # Create user with OIDC info and encryption support
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=claims.get("given_name", ""),
                last_name=claims.get("family_name", ""),
            )

            # Create UserOIDC record for this user
            from .models import UserOIDC

            UserOIDC.get_or_create_for_user(
                user=user,
                provider=provider,
                subject=subject_id,
                email_verified=claims.get("email_verified", False),
            )

            logger.info(
                f"Successfully created new OIDC healthcare user: {email} (provider: {provider})"
            )
            return user
        except Exception as e:
            logger.error(f"Failed to create OIDC user {email}: {e}")
            raise

    def update_user(self, user, claims: Dict[str, Any]):
        """
        Update existing user with latest OIDC claims.

        Preserves core user data while updating profile information
        and ensuring UserOIDC record exists.
        """

        # Update basic profile info
        user.first_name = claims.get("given_name", user.first_name)
        user.last_name = claims.get("family_name", user.last_name)
        user.email = claims.get("email", user.email)

        # Link this OIDC account if not already linked
        provider = self._get_provider_from_claims(claims)
        # Get subject identifier - Azure uses 'id', others typically use 'sub'
        subject_id = claims.get("sub") or claims.get("id")

        # Create or update UserOIDC record
        if subject_id:
            from .models import UserOIDC

            UserOIDC.get_or_create_for_user(
                user=user,
                provider=provider,
                subject=subject_id,
                email_verified=claims.get("email_verified", False),
            )
            logger.info(f"Updated OIDC record for existing user: {user.email}")

        user.save()
        logger.info(f"Saved updated user: {user.email}, is_active={user.is_active}")
        return user

    def get_or_create_user(
        self, access_token: str, id_token: str, payload: Dict[str, Any]
    ) -> Optional[User]:
        """
        Get or create user, integrating with existing custom user model.

        This allows clinicians to:
        1. Link OIDC to existing accounts (preserves encryption keys)
        2. Create new accounts via OIDC
        3. Use multiple OIDC providers with same account
        """
        logger.info("CustomOIDCAuthenticationBackend.get_or_create_user called")
        try:
            claims = self.get_userinfo(access_token, id_token, payload)
            email = claims.get("email")

            if not email:
                logger.warning("OIDC claims missing email")
                return None

            # Try to find existing user by email (primary linking method)
            try:
                user = User.objects.get(email=email)
                logger.info(f"Found existing user for OIDC login: {email}")
                # Mark that this user already existed
                user._oidc_user_existed = True
                updated_user = self.update_user(user, claims)
                logger.info(
                    f"Successfully updated existing user: {email}, active={updated_user.is_active}"
                )
                return updated_user
            except User.DoesNotExist:
                # Create new user if allowed
                if getattr(settings, "OIDC_CREATE_USER", True):
                    logger.info(f"Creating new user via OIDC: {email}")
                    user = self.create_user(claims)
                    # Mark that this user was newly created
                    if user:
                        user._oidc_user_existed = False
                        logger.info(
                            f"Successfully created new user: {email}, active={user.is_active}"
                        )
                    return user
                else:
                    logger.warning(f"OIDC user creation disabled, rejecting: {email}")
                    return None
        except Exception as e:
            logger.error(f"Error in OIDC get_or_create_user: {e}")
            return None

    def _get_provider_from_claims(self, claims: Dict[str, Any]) -> str:
        """Determine OIDC provider from claims."""
        issuer = claims.get("iss", "")

        if "accounts.google.com" in issuer:
            return "google"
        elif "login.microsoftonline.com" in issuer:
            return "azure"
        else:
            return "unknown"

    def _link_oidc_account(
        self, user: User, provider: str, claims: Dict[str, Any]
    ) -> None:
        """
        Link OIDC account to user for future authentication.

        This allows the same clinician to authenticate via:
        - Google account (personal)
        - Azure account (hospital)
        - Traditional password
        """
        # Store provider-specific subject ID for future linking
        # Get subject identifier - Azure uses 'id', others typically use 'sub'
        subject_id = claims.get("sub") or claims.get("id")
        if not subject_id:
            return

        # You could extend User model to store these, or use a separate model
        # For now, we rely on email matching for linking
        logger.info(f"Linked {provider} account to user {user.email}")
