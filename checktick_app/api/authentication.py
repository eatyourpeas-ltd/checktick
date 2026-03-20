import hashlib

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from checktick_app.core.models import UserAPIKey


class APIKeyAuthentication(BaseAuthentication):
    """Authenticate requests using ``Authorization: Bearer ct_live_...`` headers.

    Falls through (returns ``None``) for any token that does not start with the
    ``ct_live_`` prefix, allowing other authentication classes to handle
    session-based requests and Swagger UI use.
    """

    KEY_PREFIX = "ct_live_"

    def authenticate(self, request):
        header = get_authorization_header(request).decode("utf-8", errors="ignore")
        if not header.startswith(f"Bearer {self.KEY_PREFIX}"):
            return None  # Not an API key — fall through to next auth class

        raw_key = header[len("Bearer ") :]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            api_key = UserAPIKey.objects.select_related("user").get(
                key_hash=key_hash,
                revoked=False,
            )
        except UserAPIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key.")

        from django.utils import timezone

        if api_key.expires_at and api_key.expires_at < timezone.now():
            raise AuthenticationFailed("API key has expired.")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
