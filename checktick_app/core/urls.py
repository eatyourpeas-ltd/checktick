from django.urls import path

from . import views, views_billing, views_platform_admin

app_name = "core"

urlpatterns = [
    path("home", views.home, name="home"),
    path("hosting", views.hosting, name="hosting"),
    path("pricing", views.pricing, name="pricing"),
    path("healthz", views.healthz, name="healthz"),
    path("profile", views.profile, name="profile"),
    path("my-surveys/", views.my_surveys, name="my_surveys"),
    path("signup/", views.signup, name="signup"),
    path("complete-signup/", views.complete_signup, name="complete_signup"),
    path("docs/", views.docs_index, name="docs_index"),
    path("docs/<slug:slug>/", views.docs_page, name="docs_page"),
    path("branding/", views.configure_branding, name="configure_branding"),
    path("delete-account/", views.delete_account, name="delete_account"),
    # Organization setup
    path("org-setup/<str:token>/", views.org_setup, name="org_setup"),
    # Platform Admin (superuser only)
    path(
        "platform-admin/",
        views_platform_admin.platform_admin_dashboard,
        name="platform_admin_dashboard",
    ),
    path(
        "platform-admin/organizations/",
        views_platform_admin.organization_list,
        name="platform_admin_org_list",
    ),
    path(
        "platform-admin/organizations/create/",
        views_platform_admin.organization_create,
        name="platform_admin_org_create",
    ),
    path(
        "platform-admin/organizations/<int:org_id>/",
        views_platform_admin.organization_detail,
        name="platform_admin_org_detail",
    ),
    path(
        "platform-admin/organizations/<int:org_id>/edit/",
        views_platform_admin.organization_edit,
        name="platform_admin_org_edit",
    ),
    path(
        "platform-admin/organizations/<int:org_id>/invite/",
        views_platform_admin.organization_generate_invite,
        name="platform_admin_org_invite",
    ),
    path(
        "platform-admin/organizations/<int:org_id>/send-invite/",
        views_platform_admin.organization_send_invite_email,
        name="platform_admin_org_send_invite",
    ),
    path(
        "platform-admin/organizations/<int:org_id>/toggle-active/",
        views_platform_admin.organization_toggle_active,
        name="platform_admin_org_toggle_active",
    ),
    path(
        "platform-admin/stats/",
        views_platform_admin.organization_stats,
        name="platform_admin_stats",
    ),
    # Billing
    path(
        "subscription/", views_billing.subscription_portal, name="subscription_portal"
    ),
    path(
        "subscription/cancel/",
        views_billing.cancel_subscription,
        name="cancel_subscription",
    ),
    path(
        "subscription/payment-history/",
        views_billing.payment_history,
        name="payment_history",
    ),
    path("billing/success/", views_billing.checkout_success, name="checkout_success"),
    path(
        "billing/update-team-name/",
        views_billing.update_team_name,
        name="update_team_name",
    ),
    path("webhooks/payment/", views_billing.payment_webhook, name="payment_webhook"),
]
