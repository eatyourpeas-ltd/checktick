from django.urls import path

from . import views

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
]
