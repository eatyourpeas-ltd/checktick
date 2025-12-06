from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from checktick_app.core.views import BrandedPasswordResetView
from checktick_app.core.views_2fa import TwoFactorLoginView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="core:home", permanent=False)),
    path("admin/", admin.site.urls),
    # Auth routes (explicit to avoid include conflicts)
    path(
        "accounts/login/",
        TwoFactorLoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html"
        ),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    # Password reset (use branded view + templates)
    path(
        "accounts/password_reset/",
        BrandedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("", include("checktick_app.core.urls")),
    path("surveys/", include("checktick_app.surveys.urls")),
    path("api/", include("checktick_app.api.urls")),
    # OIDC authentication for healthcare SSO - ensure callback is accessible
    path("oidc/", include("checktick_app.core.oidc_urls")),
]

# Serve uploaded media (icons) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Debug views for testing error pages
    from checktick_app.core.debug_error_views import (
        error_test_menu,
        trigger_403,
        trigger_404,
        trigger_405,
        trigger_500,
        trigger_lockout,
    )

    urlpatterns += [
        path("debug/errors/", error_test_menu, name="debug_error_menu"),
        path("debug/errors/403", trigger_403, name="debug_403"),
        path("debug/errors/404", trigger_404, name="debug_404"),
        path("debug/errors/405", trigger_405, name="debug_405"),
        path("debug/errors/500", trigger_500, name="debug_500"),
        path("debug/errors/lockout", trigger_lockout, name="debug_lockout"),
    ]

# Custom error handlers
handler403 = "checktick_app.core.error_handlers.custom_permission_denied_view"
handler404 = "checktick_app.core.error_handlers.custom_page_not_found_view"
handler500 = "checktick_app.core.error_handlers.custom_server_error_view"
