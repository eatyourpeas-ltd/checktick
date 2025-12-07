"""Custom middleware for CheckTick application."""

from django.conf import settings as django_settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation

# Django's session key for storing language preference
LANGUAGE_SESSION_KEY = "_language"

# URLs that should be accessible without 2FA setup
TWO_FACTOR_EXEMPT_URLS = [
    "/app/2fa/",  # 2FA setup/manage pages
    "/accounts/logout/",  # Allow logout
    "/admin/",  # Admin site (has its own auth)
    "/api/",  # API uses token auth
    "/oidc/",  # OIDC auth flow
    "/static/",  # Static files
    "/media/",  # Media files
]


class Require2FAMiddleware:
    """Middleware to enforce 2FA setup for password users.

    Password users who haven't set up 2FA will be redirected to
    the 2FA setup page until they complete enrollment. This ensures
    all password-authenticated users have 2FA protection.

    SSO/OIDC users are exempt as their identity provider handles MFA.

    Can be disabled by setting REQUIRE_2FA = False in settings (useful for tests).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if 2FA requirement is disabled (e.g., for tests)
        if not getattr(django_settings, "REQUIRE_2FA", True):
            return self.get_response(request)

        # Only check authenticated users
        if request.user.is_authenticated:
            # Skip exempt URLs
            path = request.path
            if any(path.startswith(exempt) for exempt in TWO_FACTOR_EXEMPT_URLS):
                return self.get_response(request)

            # Import here to avoid circular imports
            from checktick_app.core.views_2fa import is_password_user

            # Only enforce for password users
            if is_password_user(request.user):
                # Check if they have 2FA set up
                from django_otp import user_has_device

                if not user_has_device(request.user, confirmed=True):
                    # Redirect to 2FA setup
                    setup_url = reverse("core:two_factor_setup")
                    if path != setup_url:
                        # Preserve the intended destination
                        if path and path != "/" and not path.startswith("/app/2fa/"):
                            request.session["2fa_next"] = request.get_full_path()
                        return redirect(setup_url)

        return self.get_response(request)


class UserLanguageMiddleware:
    """Middleware to set language based on user's saved preference.

    This middleware should be placed after LocaleMiddleware in the
    MIDDLEWARE setting. It checks if the user is authenticated and
    has a language preference saved, then activates that language
    for the request.

    This takes precedence over browser language detection but can
    still be overridden by explicit session language setting.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply if user is authenticated and has a preference
        if request.user.is_authenticated:
            try:
                # Import here to avoid circular imports
                from checktick_app.core.models import UserLanguagePreference

                preference = UserLanguagePreference.objects.filter(
                    user=request.user
                ).first()
                if preference and preference.language:
                    # Activate the user's preferred language
                    language = preference.language
                    print(
                        f"DEBUG Middleware: User {request.user.username} has language preference: {language}"
                    )
                    # Normalize language code (en-gb -> en-gb)
                    translation.activate(language)
                    request.LANGUAGE_CODE = language
                    # Also set in session so it persists across requests
                    if hasattr(request, "session"):
                        session_lang_before = request.session.get(LANGUAGE_SESSION_KEY)
                        request.session[LANGUAGE_SESSION_KEY] = language
                        request.session.modified = True
                        print(
                            f"DEBUG Middleware: Session language was: {session_lang_before}, now: {language}"
                        )
            except Exception:
                # If anything goes wrong (e.g., table doesn't exist yet during migration),
                # just continue without setting language preference
                pass

        response = self.get_response(request)
        return response
