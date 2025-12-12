import csv
from datetime import date
from io import StringIO

from django.contrib import admin
from django.http import HttpResponse

from .models import (
    Payment,
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


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for payment records with CSV export for VAT returns."""

    list_display = (
        "invoice_number",
        "invoice_date",
        "user",
        "tier",
        "get_amount_ex_vat_display",
        "get_vat_amount_display",
        "get_amount_inc_vat_display",
        "status",
    )
    list_filter = (
        "status",
        "tier",
        "invoice_date",
        "payment_provider",
    )
    search_fields = (
        "invoice_number",
        "user__username",
        "user__email",
        "customer_email",
        "payment_id",
        "subscription_id",
    )
    readonly_fields = (
        "invoice_number",
        "created_at",
        "updated_at",
        "confirmed_at",
    )
    date_hierarchy = "invoice_date"
    ordering = ["-invoice_date", "-created_at"]

    fieldsets = (
        (
            "Invoice Details",
            {
                "fields": (
                    "invoice_number",
                    "invoice_date",
                    "status",
                ),
            },
        ),
        (
            "Customer",
            {
                "fields": (
                    "user",
                    "customer_name",
                    "customer_email",
                ),
            },
        ),
        (
            "Subscription",
            {
                "fields": (
                    "tier",
                    "billing_period_start",
                    "billing_period_end",
                ),
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "amount_ex_vat",
                    "vat_rate",
                    "vat_amount",
                    "amount_inc_vat",
                    "currency",
                ),
            },
        ),
        (
            "Payment Provider",
            {
                "fields": (
                    "payment_provider",
                    "payment_id",
                    "subscription_id",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "confirmed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["export_to_csv", "export_quarter_to_csv"]

    def get_amount_ex_vat_display(self, obj):
        return obj.get_amount_ex_vat_display()

    get_amount_ex_vat_display.short_description = "Amount (ex VAT)"
    get_amount_ex_vat_display.admin_order_field = "amount_ex_vat"

    def get_vat_amount_display(self, obj):
        return obj.get_vat_amount_display()

    get_vat_amount_display.short_description = "VAT"
    get_vat_amount_display.admin_order_field = "vat_amount"

    def get_amount_inc_vat_display(self, obj):
        return obj.get_amount_inc_vat_display()

    get_amount_inc_vat_display.short_description = "Total (inc VAT)"
    get_amount_inc_vat_display.admin_order_field = "amount_inc_vat"

    @admin.action(description="Export selected payments to CSV")
    def export_to_csv(self, request, queryset):
        """Export selected payments to CSV for VAT returns."""
        return self._generate_csv(queryset, "payments_export.csv")

    @admin.action(description="Export current quarter to CSV")
    def export_quarter_to_csv(self, request, queryset):
        """Export all payments from current quarter to CSV."""
        today = date.today()
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        quarter_start = date(today.year, quarter_start_month, 1)

        # Calculate quarter end
        if quarter_start_month == 10:
            quarter_end = date(today.year + 1, 1, 1)
        else:
            quarter_end = date(today.year, quarter_start_month + 3, 1)

        quarter_payments = Payment.objects.filter(
            invoice_date__gte=quarter_start,
            invoice_date__lt=quarter_end,
            status=Payment.PaymentStatus.CONFIRMED,
        )

        quarter_name = f"Q{((today.month - 1) // 3) + 1}_{today.year}"
        return self._generate_csv(quarter_payments, f"vat_return_{quarter_name}.csv")

    def _generate_csv(self, queryset, filename):
        """Generate CSV from payment queryset for VAT returns.

        Only includes financial data required for HMRC - no personal customer data.
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header row - financial data only, no PII
        writer.writerow(
            [
                "Invoice Number",
                "Invoice Date",
                "Subscription ID",
                "Tier",
                "Amount (ex VAT) GBP",
                "VAT Rate %",
                "VAT Amount GBP",
                "Total (inc VAT) GBP",
                "Status",
            ]
        )

        # Data rows
        for payment in queryset:
            writer.writerow(
                [
                    payment.invoice_number,
                    payment.invoice_date.isoformat(),
                    payment.subscription_id,
                    payment.tier,
                    f"{payment.amount_ex_vat / 100:.2f}",
                    f"{float(payment.vat_rate) * 100:.0f}",
                    f"{payment.vat_amount / 100:.2f}",
                    f"{payment.amount_inc_vat / 100:.2f}",
                    payment.status,
                ]
            )

        # Summary row
        confirmed_payments = queryset.filter(status=Payment.PaymentStatus.CONFIRMED)
        total_ex_vat = sum(p.amount_ex_vat for p in confirmed_payments) / 100
        total_vat = sum(p.vat_amount for p in confirmed_payments) / 100
        total_inc_vat = sum(p.amount_inc_vat for p in confirmed_payments) / 100

        writer.writerow([])
        writer.writerow(
            [
                "TOTALS",
                "",
                "",
                "",
                f"{total_ex_vat:.2f}",
                "",
                f"{total_vat:.2f}",
                f"{total_inc_vat:.2f}",
                f"{confirmed_payments.count()} confirmed",
            ]
        )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
