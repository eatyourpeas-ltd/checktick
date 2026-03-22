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

    def admin_view(self, view, cacheable=False):  # type: ignore[override]
        # Intercept before Django's own admin_view wrapper can issue a redirect
        # to the login page.  Unauthorized requests receive a 404 so the admin
        # URL is not advertised to unauthenticated or non-superuser visitors.
        original = super().admin_view(view, cacheable)

        def inner(request, *args, **kwargs):
            if not self.has_permission(request):
                raise Http404
            return original(request, *args, **kwargs)

        return inner

    def login(self, request, extra_context=None):  # type: ignore[override]
        # Extra guard: if someone hits /admin/login/ directly (which is not
        # wrapped by admin_view), return 404 rather than showing the login form.
        raise Http404


class CheckTickAdminConfig(AdminConfig):
    default_site = "checktick_app.admin.CheckTickAdminSite"
