from django.contrib import admin

from .models import (
    SiteBranding,
    UserEmailPreferences,
    UserLanguagePreference,
    UserProfile,
)


@admin.register(SiteBranding)
class SiteBrandingAdmin(admin.ModelAdmin):
    """Admin interface for platform-level branding and theme settings."""

    list_display = (
        "id",
        "default_theme",
        "theme_preset_light",
        "theme_preset_dark",
        "updated_at",
    )
    fieldsets = (
        (
            "Theme Settings",
            {
                "fields": (
                    "default_theme",
                    "theme_preset_light",
                    "theme_preset_dark",
                ),
            },
        ),
        (
            "Custom Theme CSS",
            {
                "fields": ("theme_light_css", "theme_dark_css"),
                "classes": ("collapse",),
                "description": "Advanced: Custom CSS from daisyUI Theme Generator. Overrides presets if provided.",
            },
        ),
        (
            "Icons",
            {
                "fields": (
                    "icon_url",
                    "icon_file",
                    "icon_url_dark",
                    "icon_file_dark",
                ),
            },
        ),
        (
            "Fonts",
            {
                "fields": ("font_heading", "font_body", "font_css_url"),
            },
        ),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Only allow one SiteBranding instance
        return not SiteBranding.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the singleton branding object
        return False


@admin.register(UserEmailPreferences)
class UserEmailPreferencesAdmin(admin.ModelAdmin):
    """Admin interface for user email notification preferences."""

    list_display = (
        "user",
        "send_team_invitation_email",
        "send_survey_invitation_email",
        "notify_on_critical",
    )
    list_filter = (
        "send_team_invitation_email",
        "send_survey_invitation_email",
        "notify_on_critical",
    )
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserLanguagePreference)
class UserLanguagePreferenceAdmin(admin.ModelAdmin):
    """Admin interface for user language preferences."""

    list_display = ("user", "language")
    list_filter = ("language",)
    search_fields = ("user__username", "user__email")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for user account tiers and profiles."""

    list_display = (
        "user",
        "account_tier",
        "subscription_status",
        "payment_provider",
        "tier_changed_at",
    )
    list_filter = (
        "account_tier",
        "subscription_status",
        "payment_provider",
        "custom_branding_enabled",
    )
    search_fields = (
        "user__username",
        "user__email",
        "payment_customer_id",
        "payment_subscription_id",
    )
    readonly_fields = ("created_at", "updated_at", "tier_changed_at")
    fieldsets = (
        (
            "User Information",
            {
                "fields": ("user",),
            },
        ),
        (
            "Account Tier",
            {
                "fields": (
                    "account_tier",
                    "tier_changed_at",
                ),
            },
        ),
        (
            "Payment Information",
            {
                "fields": (
                    "payment_provider",
                    "payment_customer_id",
                    "payment_subscription_id",
                    "subscription_status",
                    "subscription_current_period_end",
                ),
            },
        ),
        (
            "Enterprise Features",
            {
                "fields": ("custom_branding_enabled",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
