from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CollectionDefinition,
    CollectionItem,
    DataSet,
    IdentityVerification,
    Organization,
    PublishedQuestionGroup,
    QuestionGroup,
    RecoveryAuditEntry,
    RecoveryRequest,
    Survey,
    SurveyProgress,
    SurveyQuestion,
    SurveyResponse,
)


@admin.register(DataSet)
class DataSetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "category",
        "organization",
        "is_global",
        "published_at",
        "is_active",
        "version",
        "created_at",
    )
    list_filter = (
        "category",
        "is_global",
        "is_active",
        "is_custom",
        "created_at",
        "published_at",
    )
    search_fields = ("name", "key", "description", "tags")
    readonly_fields = (
        "created_at",
        "updated_at",
        "version",
        "created_by",
        "last_synced_at",
        "published_at",
    )
    actions = ["publish_datasets", "create_custom_version_action"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "key",
                    "name",
                    "description",
                    "category",
                    "source_type",
                )
            },
        ),
        (
            "Options",
            {
                "fields": (
                    "options",
                    "format_pattern",
                )
            },
        ),
        (
            "Access Control",
            {
                "fields": (
                    "is_global",
                    "published_at",
                    "organization",
                    "is_active",
                    "tags",
                )
            },
        ),
        (
            "Customization",
            {
                "fields": (
                    "is_custom",
                    "parent",
                )
            },
        ),
        (
            "External API",
            {
                "fields": (
                    "external_api_endpoint",
                    "external_api_url",
                    "sync_frequency_hours",
                    "last_synced_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "NHS DD Metadata",
            {
                "fields": (
                    "reference_url",
                    "nhs_dd_page_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "version",
                )
            },
        ),
    )

    def publish_datasets(self, request, queryset):
        """Admin action to publish selected datasets globally."""
        published_count = 0
        errors = []

        for dataset in queryset:
            try:
                if dataset.is_global:
                    errors.append(f"{dataset.name}: Already published")
                elif not dataset.organization:
                    errors.append(f"{dataset.name}: No organization (cannot publish)")
                elif dataset.category == "nhs_dd":
                    errors.append(
                        f"{dataset.name}: NHS DD datasets cannot be published"
                    )
                else:
                    dataset.publish()
                    published_count += 1
            except Exception as e:
                errors.append(f"{dataset.name}: {str(e)}")

        if published_count > 0:
            self.message_user(
                request,
                f"Successfully published {published_count} dataset(s) globally.",
                level="success",
            )

        if errors:
            self.message_user(
                request,
                f"Errors: {'; '.join(errors)}",
                level="warning",
            )

    publish_datasets.short_description = "Publish selected datasets globally"

    def create_custom_version_action(self, request, queryset):
        """Admin action to create custom versions of selected datasets."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one dataset to create a custom version from.",
                level="error",
            )
            return

        dataset = queryset.first()

        if not dataset.is_global:
            self.message_user(
                request,
                f"Cannot create custom version: {dataset.name} is not a global dataset.",
                level="error",
            )
            return

        # Check if user has an organization
        user_orgs = request.user.org_memberships.filter(
            role__in=["admin", "creator"]
        ).select_related("organization")

        if not user_orgs.exists():
            self.message_user(
                request,
                "You must be an ADMIN or CREATOR in an organization to create custom versions.",
                level="error",
            )
            return

        # Use first organization
        org = user_orgs.first().organization

        try:
            custom = dataset.create_custom_version(
                user=request.user,
                organization=org,
                custom_name=f"{dataset.name} (Custom - {org.name})",
            )
            self.message_user(
                request,
                f"Successfully created custom version: {custom.name} (key: {custom.key})",
                level="success",
            )
        except Exception as e:
            self.message_user(
                request, f"Error creating custom version: {str(e)}", level="error"
            )

    create_custom_version_action.short_description = (
        "Create custom version from selected dataset"
    )

    def get_readonly_fields(self, request, obj=None):
        """Make NHS DD datasets fully read-only."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.category == "nhs_dd" and not obj.is_custom:
            # NHS DD datasets are read-only except for is_active
            return [
                f.name for f in obj._meta.fields if f.name not in ("id", "is_active")
            ]
        return readonly


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "owner")


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "shared", "created_at")


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "slug", "start_at", "end_at", "created_at")
    inlines = [SurveyQuestionInline]


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("survey", "submitted_at")


@admin.register(SurveyProgress)
class SurveyProgressAdmin(admin.ModelAdmin):
    list_display = (
        "survey",
        "user",
        "session_key",
        "answered_count",
        "total_questions",
        "updated_at",
        "expires_at",
    )
    list_filter = ("survey", "updated_at", "expires_at")
    search_fields = ("survey__name", "survey__slug", "user__username", "session_key")
    readonly_fields = ("created_at", "updated_at", "last_question_answered_at")


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    # CollectionItem has two FKs to CollectionDefinition (collection, child_collection)
    # This inline should attach via the 'collection' FK
    fk_name = "collection"
    extra = 0


@admin.register(CollectionDefinition)
class CollectionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "survey", "cardinality", "parent")
    list_filter = ("survey", "cardinality")
    search_fields = ("name", "key")
    inlines = [CollectionItemInline]


@admin.register(PublishedQuestionGroup)
class PublishedQuestionGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "publication_level",
        "publisher",
        "organization",
        "status",
        "import_count",
        "language",
        "created_at",
    )
    list_filter = (
        "publication_level",
        "status",
        "language",
        "created_at",
        "organization",
    )
    search_fields = ("name", "description", "tags", "publisher__email")
    readonly_fields = (
        "source_group",
        "publisher",
        "markdown",
        "import_count",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "description",
                    "language",
                    "version",
                    "tags",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "publication_level",
                    "organization",
                    "status",
                    "source_group",
                    "publisher",
                )
            },
        ),
        (
            "Attribution",
            {
                "fields": (
                    "attribution",
                    "show_publisher_credit",
                )
            },
        ),
        (
            "Content",
            {
                "fields": ("markdown",),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "import_count",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return (
            super()
            .get_queryset(request)
            .select_related("publisher", "organization", "source_group")
        )


# ============================================================================
# RECOVERY REQUEST ADMINISTRATION
# ============================================================================


class IdentityVerificationInline(admin.TabularInline):
    """Inline display of identity verifications for a recovery request."""

    model = IdentityVerification
    extra = 0
    readonly_fields = (
        "verification_type",
        "status",
        "document_type",
        "submitted_at",
        "verified_at",
        "verified_by",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class RecoveryAuditEntryInline(admin.TabularInline):
    """Inline display of audit entries for a recovery request."""

    model = RecoveryAuditEntry
    extra = 0
    readonly_fields = (
        "timestamp",
        "event_type",
        "severity",
        "actor_type",
        "actor_email",
        "actor_ip",
    )
    can_delete = False
    ordering = ["-timestamp"]
    max_num = 20  # Show last 20 entries inline

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RecoveryRequest)
class RecoveryRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for managing recovery requests.

    Provides platform administrators with tools to:
    - View all recovery requests across the platform
    - Approve/reject requests as primary or secondary approver
    - Monitor time delay periods
    - Execute approved recoveries
    - Review full audit trails
    """

    list_display = (
        "request_code",
        "user_display",
        "survey_display",
        "status_badge",
        "submitted_at",
        "time_delay_status",
        "approvals_display",
    )
    list_filter = (
        "status",
        "submitted_at",
        "time_delay_hours",
    )
    search_fields = (
        "request_code",
        "user__email",
        "user__username",
        "survey__name",
        "survey__slug",
    )
    readonly_fields = (
        "id",
        "request_code",
        "user",
        "survey",
        "submitted_at",
        "verification_completed_at",
        "approved_at",
        "time_delay_until",
        "completed_at",
        "primary_approver",
        "primary_approved_at",
        "secondary_approver",
        "secondary_approved_at",
        "rejected_by",
        "rejected_at",
        "cancelled_by",
        "cancelled_at",
        "executed_by",
    )
    inlines = [IdentityVerificationInline, RecoveryAuditEntryInline]
    actions = [
        "approve_as_primary",
        "approve_as_secondary",
        "reject_request",
        "execute_recovery",
    ]

    fieldsets = (
        (
            "Request Information",
            {
                "fields": (
                    "id",
                    "request_code",
                    "user",
                    "survey",
                    "status",
                    "submitted_at",
                )
            },
        ),
        (
            "Primary Authorization",
            {
                "fields": (
                    "primary_approver",
                    "primary_approved_at",
                    "primary_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Secondary Authorization",
            {
                "fields": (
                    "secondary_approver",
                    "secondary_approved_at",
                    "secondary_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Time Delay",
            {
                "fields": (
                    "time_delay_hours",
                    "time_delay_until",
                    "approved_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Rejection Details",
            {
                "fields": (
                    "rejected_by",
                    "rejected_at",
                    "rejection_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cancellation Details",
            {
                "fields": (
                    "cancelled_by",
                    "cancelled_at",
                    "cancellation_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Completion",
            {
                "fields": (
                    "executed_by",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user",
                "survey",
                "primary_approver",
                "secondary_approver",
                "rejected_by",
                "cancelled_by",
                "executed_by",
            )
        )

    @admin.display(description="User")
    def user_display(self, obj):
        return f"{obj.user.email}"

    @admin.display(description="Survey")
    def survey_display(self, obj):
        return (
            f"{obj.survey.name[:30]}..."
            if len(obj.survey.name) > 30
            else obj.survey.name
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending_verification": "#f59e0b",  # amber
            "verification_in_progress": "#3b82f6",  # blue
            "awaiting_primary": "#8b5cf6",  # purple
            "awaiting_secondary": "#6366f1",  # indigo
            "in_time_delay": "#ec4899",  # pink
            "ready_for_execution": "#10b981",  # green
            "completed": "#22c55e",  # bright green
            "rejected": "#ef4444",  # red
            "cancelled": "#6b7280",  # gray
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Time Delay")
    def time_delay_status(self, obj):
        """Show time delay progress."""
        if obj.status != RecoveryRequest.Status.IN_TIME_DELAY:
            return "-"
        if not obj.time_delay_until:
            return "-"

        now = timezone.now()
        if now >= obj.time_delay_until:
            return format_html(
                '<span style="color: #10b981; font-weight: 500;">✓ Ready</span>'
            )

        remaining = obj.time_delay_until - now
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return format_html(
            '<span style="color: #f59e0b;">{}h {}m remaining</span>',
            hours,
            minutes,
        )

    @admin.display(description="Approvals")
    def approvals_display(self, obj):
        """Show approval status."""
        primary = "✓" if obj.primary_approved_at else "○"
        secondary = "✓" if obj.secondary_approved_at else "○"
        return format_html(
            '<span title="Primary: {}, Secondary: {}">{} / {}</span>',
            obj.primary_approver.email if obj.primary_approver else "Pending",
            obj.secondary_approver.email if obj.secondary_approver else "Pending",
            primary,
            secondary,
        )

    @admin.action(description="Approve as Primary Approver")
    def approve_as_primary(self, request, queryset):
        """Approve selected requests as primary approver."""
        approved = 0
        errors = []

        for recovery_request in queryset:
            if recovery_request.status != RecoveryRequest.Status.AWAITING_PRIMARY:
                errors.append(
                    f"{recovery_request.request_code}: Not awaiting primary approval"
                )
                continue
            if recovery_request.user == request.user:
                errors.append(
                    f"{recovery_request.request_code}: Cannot approve your own request"
                )
                continue

            try:
                recovery_request.approve_primary(
                    approver=request.user, reason="Approved via admin interface"
                )
                approved += 1
            except Exception as e:
                errors.append(f"{recovery_request.request_code}: {str(e)}")

        if approved:
            messages.success(
                request, f"Primary approval granted for {approved} request(s)."
            )
        if errors:
            messages.warning(request, f"Errors: {'; '.join(errors)}")

    @admin.action(description="Approve as Secondary Approver")
    def approve_as_secondary(self, request, queryset):
        """Approve selected requests as secondary approver."""
        approved = 0
        errors = []

        for recovery_request in queryset:
            if recovery_request.status != RecoveryRequest.Status.AWAITING_SECONDARY:
                errors.append(
                    f"{recovery_request.request_code}: Not awaiting secondary approval"
                )
                continue
            if recovery_request.primary_approver == request.user:
                errors.append(
                    f"{recovery_request.request_code}: Same admin cannot give both approvals"
                )
                continue
            if recovery_request.user == request.user:
                errors.append(
                    f"{recovery_request.request_code}: Cannot approve your own request"
                )
                continue

            try:
                recovery_request.approve_secondary(
                    approver=request.user, reason="Approved via admin interface"
                )
                approved += 1
            except Exception as e:
                errors.append(f"{recovery_request.request_code}: {str(e)}")

        if approved:
            messages.success(
                request, f"Secondary approval granted for {approved} request(s)."
            )
        if errors:
            messages.warning(request, f"Errors: {'; '.join(errors)}")

    @admin.action(description="Reject Selected Requests")
    def reject_request(self, request, queryset):
        """Reject selected recovery requests."""
        rejected = 0
        errors = []

        rejectable_statuses = [
            RecoveryRequest.Status.PENDING_VERIFICATION,
            RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
            RecoveryRequest.Status.AWAITING_PRIMARY,
            RecoveryRequest.Status.AWAITING_SECONDARY,
        ]

        for recovery_request in queryset:
            if recovery_request.status not in rejectable_statuses:
                errors.append(
                    f"{recovery_request.request_code}: Cannot reject (status: {recovery_request.get_status_display()})"
                )
                continue

            try:
                recovery_request.reject(
                    rejector=request.user,
                    reason="Rejected via admin interface - please contact support for details",
                )
                rejected += 1
            except Exception as e:
                errors.append(f"{recovery_request.request_code}: {str(e)}")

        if rejected:
            messages.success(request, f"Rejected {rejected} request(s).")
        if errors:
            messages.warning(request, f"Errors: {'; '.join(errors)}")

    @admin.action(description="Execute Recovery (after time delay)")
    def execute_recovery(self, request, queryset):
        """
        Execute recovery for requests that have passed time delay.

        NOTE: This action requires a new password to be set for each user.
        For actual execution with Vault integration, use the Platform Recovery Console
        which provides a secure interface for entering the new password.
        """
        # Since we need a password per request, redirect to the recovery console
        if queryset.count() > 1:
            messages.error(
                request,
                "Recovery execution must be done one at a time through the "
                "Platform Recovery Console to set each user's new password securely.",
            )
            return

        recovery_request = queryset.first()

        # Validate status
        if recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY:
            if (
                recovery_request.time_delay_until
                and timezone.now() >= recovery_request.time_delay_until
            ):
                recovery_request.status = RecoveryRequest.Status.READY_FOR_EXECUTION
                recovery_request.save(update_fields=["status"])
                messages.info(
                    request,
                    f"Request {recovery_request.request_code} is now ready for execution.",
                )
            else:
                messages.error(
                    request,
                    f"Time delay for {recovery_request.request_code} has not completed yet.",
                )
                return
        elif recovery_request.status != RecoveryRequest.Status.READY_FOR_EXECUTION:
            messages.error(
                request,
                f"Request {recovery_request.request_code} is not ready for execution "
                f"(status: {recovery_request.get_status_display()}).",
            )
            return

        # Redirect to recovery console for secure password entry
        from django.urls import reverse

        recovery_url = reverse(
            "surveys:recovery_detail", kwargs={"request_id": recovery_request.id}
        )
        messages.info(
            request,
            f"Request {recovery_request.request_code} is ready. "
            f"Please use the Platform Recovery Console to execute with a new password: "
            f"{request.build_absolute_uri(recovery_url)}",
        )


@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
    """Admin interface for identity verification records."""

    list_display = (
        "verification_type",
        "status_badge",
        "recovery_request_code",
        "user_email",
        "submitted_at",
        "verified_at",
        "verified_by",
    )
    list_filter = (
        "verification_type",
        "status",
        "submitted_at",
    )
    search_fields = (
        "recovery_request__request_code",
        "recovery_request__user__email",
    )
    readonly_fields = (
        "id",
        "recovery_request",
        "verification_type",
        "submitted_at",
        "verified_at",
        "verified_by",
        "video_call_scheduled_at",
        "video_call_duration_minutes",
    )
    actions = ["verify_identity", "reject_verification"]

    fieldsets = (
        (
            "Verification",
            {
                "fields": (
                    "id",
                    "recovery_request",
                    "verification_type",
                    "status",
                )
            },
        ),
        (
            "Document Details",
            {
                "fields": (
                    "document_type",
                    "document_path",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Video Call",
            {
                "fields": (
                    "video_call_scheduled_at",
                    "video_call_duration_minutes",
                    "video_recording_path",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Security Questions",
            {
                "fields": (
                    "questions_asked",
                    "correct_answers",
                    "total_questions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Verification Result",
            {
                "fields": (
                    "submitted_at",
                    "verified_at",
                    "verified_by",
                    "verification_notes",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return (
            super()
            .get_queryset(request)
            .select_related("recovery_request", "recovery_request__user", "verified_by")
        )

    @admin.display(description="Request Code")
    def recovery_request_code(self, obj):
        return obj.recovery_request.request_code

    @admin.display(description="User")
    def user_email(self, obj):
        return obj.recovery_request.user.email

    @admin.display(description="Status")
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending": "#f59e0b",  # amber
            "submitted": "#3b82f6",  # blue
            "verified": "#22c55e",  # green
            "rejected": "#ef4444",  # red
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.action(description="Mark as Verified")
    def verify_identity(self, request, queryset):
        """Verify selected identity verifications."""
        verified = 0
        for verification in queryset:
            if verification.status in [
                IdentityVerification.Status.PENDING,
                IdentityVerification.Status.SUBMITTED,
            ]:
                verification.status = IdentityVerification.Status.VERIFIED
                verification.verified_at = timezone.now()
                verification.verified_by = request.user
                verification.save()
                verified += 1

        if verified:
            messages.success(request, f"Verified {verified} identity verification(s).")

    @admin.action(description="Reject Verification")
    def reject_verification(self, request, queryset):
        """Reject selected identity verifications."""
        rejected = 0
        for verification in queryset:
            if verification.status in [
                IdentityVerification.Status.PENDING,
                IdentityVerification.Status.SUBMITTED,
            ]:
                verification.status = IdentityVerification.Status.REJECTED
                verification.verified_at = timezone.now()
                verification.verified_by = request.user
                verification.save()
                rejected += 1

        if rejected:
            messages.success(request, f"Rejected {rejected} identity verification(s).")


@admin.register(RecoveryAuditEntry)
class RecoveryAuditEntryAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for recovery audit entries.

    Audit entries are immutable - they cannot be edited or deleted
    through the admin interface to maintain integrity.
    """

    list_display = (
        "timestamp",
        "recovery_request_code",
        "event_type",
        "severity_badge",
        "actor_display",
        "actor_ip",
        "forwarded_to_siem",
    )
    list_filter = (
        "event_type",
        "severity",
        "actor_type",
        "forwarded_to_siem",
        "timestamp",
    )
    search_fields = (
        "recovery_request__request_code",
        "actor_email",
        "event_type",
    )
    readonly_fields = (
        "id",
        "recovery_request",
        "timestamp",
        "event_type",
        "severity",
        "actor_type",
        "actor_id",
        "actor_email",
        "actor_ip",
        "actor_user_agent",
        "details",
        "entry_hash",
        "previous_hash",
        "forwarded_to_siem",
        "forwarded_at",
    )
    ordering = ["-timestamp"]

    fieldsets = (
        (
            "Event",
            {
                "fields": (
                    "id",
                    "recovery_request",
                    "timestamp",
                    "event_type",
                    "severity",
                )
            },
        ),
        (
            "Actor",
            {
                "fields": (
                    "actor_type",
                    "actor_id",
                    "actor_email",
                    "actor_ip",
                    "actor_user_agent",
                )
            },
        ),
        (
            "Details",
            {
                "fields": ("details",),
            },
        ),
        (
            "Integrity",
            {
                "fields": (
                    "entry_hash",
                    "previous_hash",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "SIEM",
            {
                "fields": (
                    "forwarded_to_siem",
                    "forwarded_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        return (
            super()
            .get_queryset(request)
            .select_related("recovery_request", "recovery_request__user")
        )

    def has_add_permission(self, request):
        """Prevent adding audit entries manually."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting audit entries."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing audit entries."""
        return False

    @admin.display(description="Request Code")
    def recovery_request_code(self, obj):
        return obj.recovery_request.request_code

    @admin.display(description="Severity")
    def severity_badge(self, obj):
        """Display severity as colored badge."""
        colors = {
            "info": "#3b82f6",  # blue
            "warning": "#f59e0b",  # amber
            "critical": "#ef4444",  # red
        }
        color = colors.get(obj.severity, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px; font-weight: 500; text-transform: uppercase;">{}</span>',
            color,
            obj.severity,
        )

    @admin.display(description="Actor")
    def actor_display(self, obj):
        if obj.actor_email:
            return f"{obj.actor_type}: {obj.actor_email}"
        return obj.actor_type


# Configure admin site branding after admin is imported
_brand_title = getattr(settings, "BRAND_TITLE", "CheckTick")
admin.site.site_header = f"{_brand_title} Admin"
admin.site.site_title = f"{_brand_title} Admin"
admin.site.index_title = "Administration"
