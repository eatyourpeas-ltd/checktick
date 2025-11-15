from django.conf import settings
from django.contrib import admin

from .models import (
    CollectionDefinition,
    CollectionItem,
    Organization,
    QuestionGroup,
    Survey,
    SurveyProgress,
    SurveyQuestion,
    SurveyResponse,
)


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


# Configure admin site branding after admin is imported
_brand_title = getattr(settings, "BRAND_TITLE", "CheckTick")
admin.site.site_header = f"{_brand_title} Admin"
admin.site.site_title = f"{_brand_title} Admin"
admin.site.index_title = "Administration"
