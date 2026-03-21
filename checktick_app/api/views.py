import os

from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import render
from django.utils import timezone
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.response import Response

from checktick_app.surveys.models import (
    DataSet,
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    Survey,
)
from checktick_app.surveys.permissions import can_edit_survey, can_view_survey

User = get_user_model()


class SurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ["id", "name", "slug", "description", "start_at", "end_at"]


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "owner_id", None) == getattr(request.user, "id", None)


class OrgOwnerOrAdminPermission(permissions.BasePermission):
    """Object-level permission that mirrors SSR rules using surveys.permissions.

    - SAFE methods require can_view_survey
    - Unsafe methods require can_edit_survey
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return can_view_survey(request.user, obj)
        return can_edit_survey(request.user, obj)


class DataSetSerializer(serializers.ModelSerializer):
    """Serializer for DataSet model with read/write support."""

    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    is_editable = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    can_publish = serializers.SerializerMethodField()

    # Explicitly define parent to use key instead of ID
    parent = serializers.SlugRelatedField(
        slug_field="key",
        queryset=DataSet.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = DataSet
        fields = [
            "key",
            "name",
            "description",
            "category",
            "source_type",
            "reference_url",
            "is_custom",
            "is_global",
            "organization",
            "organization_name",
            "parent",
            "parent_name",
            "options",
            "format_pattern",
            "tags",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
            "published_at",
            "version",
            "is_active",
            "is_editable",
            "can_publish",
        ]
        read_only_fields = [
            "key",  # Auto-generated in perform_create
            "created_by",
            "created_at",
            "updated_at",
            "published_at",
            "version",
            "created_by_username",
            "organization_name",
            "parent_name",
            "is_editable",
            "can_publish",
        ]

    def get_is_editable(self, obj):
        """Determine if current user can edit this dataset."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        # NHS DD datasets are never editable
        if obj.category == "nhs_dd":
            return False

        # Global datasets without organization can only be edited by superusers
        if obj.is_global and not obj.organization:
            return request.user.is_superuser

        # Organization datasets: check if user is admin or creator in that org
        if obj.organization:
            membership = OrganizationMembership.objects.filter(
                organization=obj.organization, user=request.user
            ).first()
            if membership and membership.role in [
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.CREATOR,
            ]:
                return True

        return False

    def get_can_publish(self, obj):
        """Determine if current user can publish this dataset globally."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        # Already published
        if obj.is_global:
            return False

        # Must be organization-owned
        if not obj.organization:
            return False

        # NHS DD datasets cannot be published
        if obj.category == "nhs_dd":
            return False

        # User must be ADMIN or CREATOR in the organization
        membership = OrganizationMembership.objects.filter(
            organization=obj.organization, user=request.user
        ).first()
        if membership and membership.role in [
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.CREATOR,
        ]:
            return True

        return False

    def validate(self, attrs):
        """Validate dataset creation/update."""
        # Prevent editing NHS DD datasets
        if self.instance and self.instance.category == "nhs_dd":
            raise serializers.ValidationError(
                "NHS Data Dictionary datasets cannot be modified"
            )

        # Ensure options is a dict (all datasets use key-value format)
        if "options" in attrs:
            if not isinstance(attrs["options"], dict):
                raise serializers.ValidationError(
                    {"options": "Must be a dictionary of code: name pairs"}
                )

        # Ensure tags is a list
        if "tags" in attrs and not isinstance(attrs["tags"], list):
            raise serializers.ValidationError({"tags": "Must be a list of strings"})

        # Validate key format (slug-like)
        if "key" in attrs:
            import re

            if not re.match(r"^[a-z0-9_-]+$", attrs["key"]):
                raise serializers.ValidationError(
                    {
                        "key": "Key must contain only lowercase letters, numbers, hyphens, and underscores"
                    }
                )

        return attrs


class IsOrgAdminOrCreator(permissions.BasePermission):
    """
    Permission for dataset access.

    - LIST: Requires authentication.
    - RETRIEVE: Anonymous users can retrieve individual datasets (needed for public surveys).
    """

    def has_permission(self, request, view):
        """Check if user can access the dataset API at all."""
        # List action requires authentication
        if view.action == "list" and not request.user.is_authenticated:
            return False

        # Retrieve allows anonymous access for public datasets
        if not request.user.is_authenticated:
            return request.method in permissions.SAFE_METHODS

        return True

    def has_object_permission(self, request, view, obj):
        """All remaining actions are safe (read-only)."""
        return True


class SurveyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SurveySerializer
    permission_classes = [permissions.IsAuthenticated, OrgOwnerOrAdminPermission]

    def get_queryset(self):
        user = self.request.user
        # Owner's surveys
        owned = Survey.objects.filter(owner=user)
        # Org-admin surveys: any survey whose organization has the user as ADMIN
        org_admin = Survey.objects.filter(
            organization__memberships__user=user,
            organization__memberships__role=OrganizationMembership.Role.ADMIN,
        )
        # Survey membership: surveys where user has explicit membership
        survey_member = Survey.objects.filter(memberships__user=user)
        return (owned | org_admin | survey_member).distinct()

    def get_object(self):
        """Fetch object without scoping to queryset, then run object permissions.

        This ensures authenticated users receive 403 (Forbidden) rather than
        404 (Not Found) when they lack permission on an existing object.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        obj = Survey.objects.select_related("organization").get(
            **{self.lookup_field: lookup_value}
        )
        self.check_object_permissions(self.request, obj)
        return obj

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated, OrgOwnerOrAdminPermission],
        url_path="metrics/responses",
    )
    def responses_metrics(self, request, pk=None):
        """Return counts of completed responses for this survey.

        SAFE method follows can_view_survey rules via OrgOwnerOrAdminPermission.
        """
        survey = self.get_object()
        now = timezone.now()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total = survey.responses.count()
        today = survey.responses.filter(submitted_at__gte=start_today).count()
        last7 = survey.responses.filter(
            submitted_at__gte=now - timezone.timedelta(days=7)
        ).count()
        last14 = survey.responses.filter(
            submitted_at__gte=now - timezone.timedelta(days=14)
        ).count()
        return Response(
            {
                "total": total,
                "today": today,
                "last7": last7,
                "last14": last14,
            }
        )


# Conditional throttle decorator for healthcheck
if os.environ.get("PYTEST_CURRENT_TEST"):

    @api_view(["GET"])
    @permission_classes([permissions.AllowAny])
    @throttle_classes([])
    def healthcheck(request):
        return Response({"status": "ok"})

else:

    @api_view(["GET"])
    @permission_classes([permissions.AllowAny])
    def healthcheck(request):
        return Response({"status": "ok"})


class DataSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for DataSet objects.

    GET /api/datasets/ - List accessible datasets
    GET /api/datasets/{key}/ - Retrieve a specific dataset
    GET /api/datasets/available-tags/ - List unique tags
    """

    serializer_class = DataSetSerializer
    permission_classes = [IsOrgAdminOrCreator]
    lookup_field = "key"

    def get_queryset(self):
        """
        Filter datasets based on user's organization access.

        Query parameters:
        - tags: Comma-separated list of tags to filter by (AND logic)
        - search: Search in name and description
        - category: Filter by category

        Returns:
        - Global datasets (is_global=True)
        - Datasets belonging to user's organizations
        - Active datasets only by default
        """
        from django.db.models import Q

        user = self.request.user
        queryset = DataSet.objects.filter(is_active=True)

        # Anonymous users see only global datasets
        if not user.is_authenticated:
            queryset = queryset.filter(is_global=True)
        else:
            # Get user's organizations
            user_orgs = Organization.objects.filter(memberships__user=user)

            # Filter: global OR in user's organizations OR created by user (individual datasets)
            queryset = queryset.filter(
                Q(is_global=True)
                | Q(organization__in=user_orgs)
                | Q(created_by=user, organization__isnull=True)
            )

        # Filter by tags if provided
        tags_param = self.request.query_params.get("tags")
        if tags_param:
            tags = [tag.strip() for tag in tags_param.split(",")]
            # Filter datasets that contain ALL specified tags
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        # Search in name and description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        # Filter by category
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by("category", "name")

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="available-tags",
    )
    def available_tags(self, request):
        """
        Get all unique tags from accessible datasets.

        GET /api/datasets/available-tags/

        Returns a list of tags with counts for faceted filtering.
        """
        from collections import Counter

        # Get accessible queryset (respects user permissions)
        queryset = self.get_queryset()

        # Collect all tags
        all_tags = []
        for dataset in queryset:
            if dataset.tags:
                all_tags.extend(dataset.tags)

        # Count occurrences
        tag_counts = Counter(all_tags)

        # Format as list of {tag, count} sorted by count descending
        tags_list = [
            {"tag": tag, "count": count} for tag, count in tag_counts.most_common()
        ]

        return Response({"tags": tags_list})


class PublishedQuestionGroupSerializer(serializers.ModelSerializer):
    """Serializer for PublishedQuestionGroup with read-only list/retrieve."""

    publisher_username = serializers.CharField(
        source="publisher.username", read_only=True
    )
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, allow_null=True
    )
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = PublishedQuestionGroup
        fields = [
            "id",
            "name",
            "description",
            "markdown",
            "publication_level",
            "publisher",
            "publisher_username",
            "organization",
            "organization_name",
            "attribution",
            "show_publisher_credit",
            "tags",
            "language",
            "version",
            "status",
            "import_count",
            "created_at",
            "updated_at",
            "can_delete",
        ]
        read_only_fields = [
            "id",
            "publisher",
            "import_count",
            "created_at",
            "updated_at",
        ]

    def get_can_delete(self, obj):
        """Check if current user can delete this template."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.publisher == request.user


class PublishedQuestionGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for browsing published question group templates.

    Provides read-only endpoints for listing and retrieving published templates.
    Users can only see:
    - Global templates (publication_level='global')
    - Organization templates from their own organization(s)

    List supports filtering by:
    - publication_level: 'global' or 'organization'
    - language: language code (e.g., 'en', 'cy')
    - tags: comma-separated list of tags
    - search: search in name and description
    - ordering: 'name', '-created_at', '-import_count'
    """

    serializer_class = PublishedQuestionGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["publication_level", "language"]
    search_fields = ["name", "description", "tags"]
    ordering_fields = ["name", "created_at", "import_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter templates based on user's access."""
        user = self.request.user

        # Base query: only active templates
        qs = PublishedQuestionGroup.objects.filter(
            status=PublishedQuestionGroup.Status.ACTIVE
        )

        # User can see:
        # 1. Global templates
        # 2. Organization templates from their own organizations
        user_org_ids = OrganizationMembership.objects.filter(user=user).values_list(
            "organization_id", flat=True
        )

        qs = qs.filter(
            models.Q(publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL)
            | models.Q(
                publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
                organization_id__in=user_org_ids,
            )
        )

        # Apply filters
        publication_level = self.request.query_params.get("publication_level")
        if publication_level:
            qs = qs.filter(publication_level=publication_level)

        language = self.request.query_params.get("language")
        if language:
            qs = qs.filter(language=language)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search)
                | models.Q(description__icontains=search)
            )

        tags = self.request.query_params.get("tags")
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tag_list:
                qs = qs.filter(tags__contains=tag)

        # Apply ordering
        ordering = self.request.query_params.get("ordering")
        if ordering:
            # Validate ordering field
            valid_fields = {
                "name",
                "-name",
                "created_at",
                "-created_at",
                "import_count",
                "-import_count",
            }
            if ordering in valid_fields:
                qs = qs.order_by(ordering)

        return qs.select_related("publisher", "organization")

    @action(detail=False, methods=["post"], url_path="publish")
    def publish_from_group(self, request):
        """
        Publish a question group as a template.

        Required fields:
        - question_group_id: ID of the QuestionGroup to publish
        - name: Template name
        - description: Template description
        - publication_level: 'organization' or 'global'
        - language: Language code (default: 'en')

        Optional fields:
        - tags: List of tags
        - attribution: Dict with authors, citation, doi, pmid, license, year
        - show_publisher_credit: Boolean (default: True)
        - organization_id: Required if publication_level='organization'
        """
        from checktick_app.surveys.views import _export_question_group_to_markdown

        # Validate input
        question_group_id = request.data.get("question_group_id")
        if not question_group_id:
            return Response({"error": "question_group_id is required"}, status=400)

        try:
            group = QuestionGroup.objects.get(id=question_group_id)
        except QuestionGroup.DoesNotExist:
            return Response({"error": "Question group not found"}, status=404)

        # Check if user can access this group
        survey = group.surveys.first()
        if not survey:
            return Response(
                {"error": "Question group must be part of a survey"}, status=400
            )

        if not can_edit_survey(request.user, survey):
            return Response(
                {"error": "You don't have permission to publish this question group"},
                status=403,
            )

        # Check if this group was imported from another template
        if group.imported_from:
            return Response(
                {
                    "error": "Cannot publish question groups that were imported from templates. "
                    "This protects copyright and prevents circular attribution issues."
                },
                status=400,
            )

        # Validate required fields
        name = request.data.get("name")
        description = request.data.get("description", "")
        publication_level = request.data.get("publication_level")
        language = request.data.get("language", "en")

        if not name:
            return Response({"error": "name is required"}, status=400)
        if not publication_level:
            return Response({"error": "publication_level is required"}, status=400)
        if publication_level not in [
            PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
            PublishedQuestionGroup.PublicationLevel.GLOBAL,
        ]:
            return Response(
                {"error": "publication_level must be 'organization' or 'global'"},
                status=400,
            )

        # Handle organization requirement for organization-level publications
        organization = None
        if publication_level == PublishedQuestionGroup.PublicationLevel.ORGANIZATION:
            org_id = request.data.get("organization_id")
            if not org_id:
                return Response(
                    {
                        "error": "organization_id is required for organization-level publications"
                    },
                    status=400,
                )

            try:
                organization = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                return Response({"error": "Organization not found"}, status=404)

            # Check if user is admin in this organization
            membership = OrganizationMembership.objects.filter(
                user=request.user,
                organization=organization,
                role=OrganizationMembership.Role.ADMIN,
            ).first()

            if not membership:
                return Response(
                    {
                        "error": "You must be an ADMIN in the organization to publish at organization level"
                    },
                    status=403,
                )

        # Global publications require superuser
        if publication_level == PublishedQuestionGroup.PublicationLevel.GLOBAL:
            if not request.user.is_superuser:
                return Response(
                    {"error": "Only administrators can publish global templates"},
                    status=403,
                )

        # Export to markdown
        markdown = _export_question_group_to_markdown(group, survey)

        # Create the published template
        template = PublishedQuestionGroup.objects.create(
            source_group=group,
            publisher=request.user,
            organization=organization,
            publication_level=publication_level,
            name=name,
            description=description,
            markdown=markdown,
            attribution=request.data.get("attribution", {}),
            show_publisher_credit=request.data.get("show_publisher_credit", True),
            tags=request.data.get("tags", []),
            language=language,
            version=request.data.get("version", ""),
            status=PublishedQuestionGroup.Status.ACTIVE,
        )

        serializer = self.get_serializer(template)
        return Response(serializer.data, status=201)


def redoc_ui(request):
    """Render an embedded ReDoc UI pointing at the API schema endpoint."""
    return render(request, "api/redoc.html", {})
