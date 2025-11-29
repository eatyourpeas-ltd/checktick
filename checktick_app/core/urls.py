from django.urls import path

from . import views, views_billing

app_name = "core"

urlpatterns = [
    path("home", views.home, name="home"),
    path("hosting", views.hosting, name="hosting"),
    path("pricing", views.pricing, name="pricing"),
    path("healthz", views.healthz, name="healthz"),
    path("profile", views.profile, name="profile"),
    path("signup/", views.signup, name="signup"),
    path("complete-signup/", views.complete_signup, name="complete_signup"),
    path("docs/", views.docs_index, name="docs_index"),
    path("docs/<slug:slug>/", views.docs_page, name="docs_page"),
    path("branding/", views.configure_branding, name="configure_branding"),
    path("delete-account/", views.delete_account, name="delete_account"),
    # Billing
    path(
        "subscription/", views_billing.subscription_portal, name="subscription_portal"
    ),
    path(
        "subscription/cancel/",
        views_billing.cancel_subscription,
        name="cancel_subscription",
    ),
    path("billing/success/", views_billing.checkout_success, name="checkout_success"),
    path("webhooks/payment/", views_billing.payment_webhook, name="payment_webhook"),
]
