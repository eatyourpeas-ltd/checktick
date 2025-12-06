"""
Two-Factor Authentication (2FA) views using TOTP.

Provides views for:
- Setting up 2FA with authenticator apps
- Verifying 2FA during login
- Disabling 2FA
- Managing backup codes
"""

import base64
import io
import logging
import secrets
from urllib.parse import quote

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice

logger = logging.getLogger(__name__)


def generate_totp_qr_code(
    device: TOTPDevice, user_email: str, issuer: str | None = None
) -> str:
    """Generate a base64-encoded QR code for TOTP setup.

    Args:
        device: The TOTP device to generate the QR code for
        user_email: The user's email address
        issuer: The issuer name (defaults to site title or 'CheckTick')

    Returns:
        Base64-encoded PNG image string
    """
    if issuer is None:
        # Try to get site branding
        try:
            from .models import SiteBranding

            branding = SiteBranding.objects.first()
            issuer = branding.title if branding else "CheckTick"
        except Exception:
            issuer = "CheckTick"

    # Build the otpauth URI
    # Format: otpauth://totp/ISSUER:email?secret=SECRET&issuer=ISSUER&algorithm=SHA1&digits=6&period=30
    secret = base64.b32encode(bytes.fromhex(device.key)).decode("utf-8").rstrip("=")
    label = f"{issuer}:{user_email}"
    uri = (
        f"otpauth://totp/{quote(label)}?"
        f"secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )

    # Generate QR code
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def get_totp_secret_display(device: TOTPDevice) -> str:
    """Get a human-readable display of the TOTP secret.

    Shows the secret in groups of 4 characters for easy manual entry.
    """
    secret = base64.b32encode(bytes.fromhex(device.key)).decode("utf-8").rstrip("=")
    # Group in chunks of 4 for readability
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def is_password_user(user) -> bool:
    """Check if a user authenticates via password (vs SSO/OIDC)."""
    # If user has a usable password, they're a password user
    return user.has_usable_password()


@login_required
def two_factor_setup(request):
    """Set up 2FA for the current user."""
    user = request.user

    # Check if user is a password user - only they need 2FA
    if not is_password_user(user):
        messages.info(
            request,
            _(
                "Two-factor authentication is not required for accounts using single sign-on (SSO)."
            ),
        )
        return redirect("core:profile")

    # Check if user already has 2FA enabled
    if user_has_device(user, confirmed=True):
        messages.info(
            request, _("Two-factor authentication is already enabled for your account.")
        )
        return redirect("core:two_factor_manage")

    # Get or create an unconfirmed device
    device, created = TOTPDevice.objects.get_or_create(
        user=user,
        confirmed=False,
        defaults={"name": "Authenticator App"},
    )

    if request.method == "POST":
        token = request.POST.get("token", "").replace(" ", "")

        if device.verify_token(token):
            # Token is valid - confirm the device
            device.confirmed = True
            device.save()

            # Generate backup codes
            backup_codes = generate_backup_codes(user)

            messages.success(
                request,
                _("Two-factor authentication has been enabled for your account."),
            )
            logger.info(f"2FA enabled for user {user.id}")

            # Show backup codes page
            return render(
                request,
                "core/2fa/backup_codes.html",
                {
                    "backup_codes": backup_codes,
                    "is_initial_setup": True,
                },
            )
        else:
            messages.error(request, _("Invalid verification code. Please try again."))
            # Regenerate device on failure to prevent timing attacks
            device.delete()
            device = TOTPDevice.objects.create(
                user=user,
                name="Authenticator App",
                confirmed=False,
            )

    # Generate QR code
    qr_code = generate_totp_qr_code(device, user.email)
    secret_display = get_totp_secret_display(device)

    return render(
        request,
        "core/2fa/setup.html",
        {
            "qr_code": qr_code,
            "secret_display": secret_display,
        },
    )


@login_required
def two_factor_manage(request):
    """Manage 2FA settings."""
    user = request.user

    if not is_password_user(user):
        messages.info(
            request,
            _(
                "Two-factor authentication is not required for accounts using single sign-on (SSO)."
            ),
        )
        return redirect("core:profile")

    has_2fa = user_has_device(user, confirmed=True)

    if not has_2fa:
        return redirect("core:two_factor_setup")

    return render(
        request,
        "core/2fa/manage.html",
        {
            "has_2fa": has_2fa,
        },
    )


@login_required
def two_factor_disable(request):
    """Disable 2FA for the current user."""
    user = request.user

    if request.method != "POST":
        return redirect("core:two_factor_manage")

    # Verify current password before disabling
    password = request.POST.get("password", "")
    if not user.check_password(password):
        messages.error(request, _("Incorrect password. Please try again."))
        return redirect("core:two_factor_manage")

    # Remove all TOTP devices and backup codes
    TOTPDevice.objects.filter(user=user).delete()

    messages.success(request, _("Two-factor authentication has been disabled."))
    logger.info(f"2FA disabled for user {user.id}")

    return redirect("core:profile")


@login_required
def two_factor_regenerate_backup_codes(request):
    """Generate new backup codes, invalidating old ones."""
    user = request.user

    if request.method != "POST":
        return redirect("core:two_factor_manage")

    if not user_has_device(user, confirmed=True):
        messages.error(request, _("Two-factor authentication is not enabled."))
        return redirect("core:two_factor_setup")

    # Verify current password before regenerating
    password = request.POST.get("password", "")
    if not user.check_password(password):
        messages.error(request, _("Incorrect password. Please try again."))
        return redirect("core:two_factor_manage")

    backup_codes = generate_backup_codes(user)
    logger.info(f"Backup codes regenerated for user {user.id}")

    return render(
        request,
        "core/2fa/backup_codes.html",
        {
            "backup_codes": backup_codes,
            "is_initial_setup": False,
        },
    )


def generate_backup_codes(user, count: int = 10) -> list[str]:
    """Generate new backup codes for a user.

    Backup codes are stored as unconfirmed static devices.
    Each code can only be used once.

    Args:
        user: The user to generate codes for
        count: Number of codes to generate (default 10)

    Returns:
        List of plaintext backup codes
    """
    from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

    # Remove any existing backup codes device
    StaticDevice.objects.filter(user=user, name="Backup Codes").delete()

    # Create new device for backup codes
    device = StaticDevice.objects.create(
        user=user,
        name="Backup Codes",
        confirmed=True,
    )

    # Generate codes
    codes = []
    for i in range(count):
        # Generate 8-character alphanumeric code
        code = secrets.token_hex(4).upper()
        codes.append(code)
        StaticToken.objects.create(device=device, token=code)

    return codes


def two_factor_verify(request):
    """Verify 2FA token during login.

    This view is called after username/password authentication
    when the user has 2FA enabled.
    """
    # Get the pending user from session
    pending_user_id = request.session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect("login")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        del request.session["pending_2fa_user_id"]
        return redirect("login")

    if request.method == "POST":
        token = request.POST.get("token", "").replace(" ", "").replace("-", "").upper()

        # Try TOTP device first
        for device in TOTPDevice.objects.filter(user=user, confirmed=True):
            if device.verify_token(token):
                # Clear pending state and log in
                del request.session["pending_2fa_user_id"]
                auth_login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
                messages.success(
                    request, _("Successfully signed in with two-factor authentication.")
                )
                return redirect(
                    request.session.pop("next", settings.LOGIN_REDIRECT_URL)
                )

        # Try backup codes
        from django_otp.plugins.otp_static.models import StaticDevice

        for device in StaticDevice.objects.filter(
            user=user, name="Backup Codes", confirmed=True
        ):
            if device.verify_token(token):
                # Backup code was used (and is now deleted)
                del request.session["pending_2fa_user_id"]
                auth_login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
                messages.warning(
                    request,
                    _(
                        "Signed in using a backup code. Consider regenerating your backup codes."
                    ),
                )
                return redirect(
                    request.session.pop("next", settings.LOGIN_REDIRECT_URL)
                )

        messages.error(request, _("Invalid verification code. Please try again."))

    return render(request, "core/2fa/verify.html")


def check_2fa_required(user) -> bool:
    """Check if 2FA verification is required for a user.

    Returns True if the user has 2FA enabled and needs to verify.
    """
    if not is_password_user(user):
        return False
    return user_has_device(user, confirmed=True)


class TwoFactorLoginView(auth_views.LoginView):
    """Custom login view that handles 2FA verification.

    After successful username/password authentication, if the user has 2FA enabled,
    they are redirected to the 2FA verification page.
    """

    def form_valid(self, form):
        """Handle successful login form submission."""
        user = form.get_user()

        if check_2fa_required(user):
            # Store user ID and next URL for after 2FA verification
            self.request.session["pending_2fa_user_id"] = user.pk
            next_url = self.get_success_url()
            if next_url and next_url != settings.LOGIN_REDIRECT_URL:
                self.request.session["next"] = next_url
            return redirect("core:two_factor_verify")

        # No 2FA required - proceed with normal login
        return super().form_valid(form)
