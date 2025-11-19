from django.conf import settings
from django.contrib import admin

from .models import (
    CollectionDefinition,
    CollectionItem,
    DataSet,
    Organization,
    PublishedQuestionGroup,
    QuestionGroup,
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
        return super().get_queryset(request).select_related(
            "publisher", "organization", "source_group"
        )


# Configure admin site branding after admin is imported
_brand_title = getattr(settings, "BRAND_TITLE", "CheckTick")
admin.site.site_header = f"{_brand_title} Admin"
admin.site.site_title = f"{_brand_title} Admin"
admin.site.index_title = "Administration"
