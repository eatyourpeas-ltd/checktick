from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.http import Http404


class CheckTickAdminSite(AdminSite):
    site_header = f"{getattr(settings, 'BRAND_TITLE', 'CheckTick')} Admin"
    site_title = f"{getattr(settings, 'BRAND_TITLE', 'CheckTick')} Admin"
    index_title = "Administration"

    def has_permission(self, request):  # type: ignore[override]
        # Restrict access strictly to active superusers
        return bool(
            request.user and request.user.is_active and request.user.is_superuser
        )

    def login(self, request, extra_context=None):  # type: ignore[override]
        # Do not expose the Django admin login form. Superusers must already be
        # authenticated via the main application login before accessing /admin/.
        raise Http404


class CheckTickAdminConfig(AdminConfig):
    default_site = "checktick_app.admin.CheckTickAdminSite"
