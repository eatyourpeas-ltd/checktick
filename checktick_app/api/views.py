import os
import secrets
from typing import Any

from csp.decorators import csp_exempt
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from checktick_app.surveys.models import (
    AuditLog,
    DataSet,
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyQuestion,
)
from checktick_app.surveys.permissions import can_edit_survey, can_view_survey

User = get_user_model()


class SurveySerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ["id", "name", "slug", "description", "start_at", "end_at"]


class SurveyPublishSettingsSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Survey.Status.choices)
    visibility = serializers.ChoiceField(choices=Survey.Visibility.choices)
    start_at = serializers.DateTimeField(allow_null=True, required=False)
    end_at = serializers.DateTimeField(allow_null=True, required=False)
    max_responses = serializers.IntegerField(
        allow_null=True, required=False, min_value=1
    )
    captcha_required = serializers.BooleanField(required=False)
    no_patient_data_ack = serializers.BooleanField(required=False)

    def to_representation(self, instance: Survey) -> dict[str, Any]:
        data = {
            "status": instance.status,
            "visibility": instance.visibility,
            "start_at": instance.start_at,
            "end_at": instance.end_at,
            "max_responses": instance.max_responses,
            "captcha_required": instance.captcha_required,
            "no_patient_data_ack": instance.no_patient_data_ack,
            "published_at": instance.published_at,
        }
        # Helpful links
        if instance.visibility == Survey.Visibility.PUBLIC:
            data["public_link"] = f"/surveys/{instance.slug}/take/"
        if instance.visibility == Survey.Visibility.UNLISTED and instance.unlisted_key:
            data["unlisted_link"] = (
                f"/surveys/{instance.slug}/take/unlisted/{instance.unlisted_key}/"
            )
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


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
    Permission for dataset management.

    - LIST: Requires authentication (authenticated users can list datasets they have access to)
    - RETRIEVE: Anonymous users can retrieve individual datasets (needed for public surveys)
    - POST: Authenticated users excluding VIEWER role (individual users and org ADMIN/CREATOR/EDITOR)
    - PUT/PATCH/DELETE: User must be ADMIN or CREATOR in the dataset's organization
    - NHS DD datasets cannot be modified
    """

    def has_permission(self, request, view):
        """Check if user can access the dataset API at all."""
        # List action requires authentication
        if view.action == "list" and not request.user.is_authenticated:
            return False

        # Retrieve allows anonymous access for public datasets
        if not request.user.is_authenticated:
            return request.method in permissions.SAFE_METHODS

        if request.method in permissions.SAFE_METHODS:
            return True

        # For POST, check create permission (excludes VIEWER role)
        if request.method == "POST":
            from checktick_app.surveys.permissions import can_create_datasets

            return can_create_datasets(request.user)

        return True

    def has_object_permission(self, request, view, obj):
        """Check if user can modify this specific dataset."""
        if request.method in permissions.SAFE_METHODS:
            return True

        # Superusers can do anything
        if request.user.is_superuser:
            return True

        # Allow creating custom versions from ANY global dataset
        if view.action == "create_custom_version" and obj.is_global:
            # Permission is checked in the action itself (needs ADMIN/CREATOR)
            return True

        # Allow publishing datasets user has access to
        if view.action == "publish_dataset":
            # Permission is checked in the action itself
            return True

        # Cannot modify NHS DD datasets
        if obj.category == "nhs_dd":
            return False

        # Cannot modify global datasets without organization/creator (platform-wide like NHS DD)
        if obj.is_global and not obj.organization and obj.created_by != request.user:
            return False

        # Individual user datasets - check if user is the creator
        if not obj.organization:
            return obj.created_by == request.user

        # Check organization membership
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


class SurveyViewSet(viewsets.ModelViewSet):
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

    def perform_create(self, serializer):
        obj = serializer.save(owner=self.request.user)
        import os

        key = os.urandom(32)
        obj.set_key(key)
        # Attach to serializer context for response augmentation
        self._created_key = key

    def perform_destroy(self, instance):
        """Delete survey with audit logging."""
        survey_name = instance.name
        survey_slug = instance.slug
        organization = instance.organization

        instance.delete()

        # Log deletion
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=None,  # Survey is deleted
            organization=organization,
            action=AuditLog.Action.REMOVE,
            target_user=self.request.user,
            metadata={
                "survey_name": survey_name,
                "survey_slug": survey_slug,
            },
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, OrgOwnerOrAdminPermission],
    )
    def seed(self, request, pk=None):
        survey = self.get_object()
        # get_object already runs object permission checks via check_object_permissions
        payload = request.data
        created = 0
        # JSON schema: [{text, type, options=[], group_name, order}]
        items = payload if isinstance(payload, list) else payload.get("items", [])

        # Valid question types from SurveyQuestion.Types
        valid_types = [choice[0] for choice in SurveyQuestion.Types.choices]

        # Validate all items first before creating any
        errors = []
        for idx, item in enumerate(items):
            question_type = item.get("type")

            # Check if type is provided
            if not question_type:
                errors.append(
                    {
                        "index": idx,
                        "field": "type",
                        "message": "Question type is required.",
                        "valid_types": valid_types,
                    }
                )
                continue

            # Check if type is valid
            if question_type not in valid_types:
                errors.append(
                    {
                        "index": idx,
                        "field": "type",
                        "value": question_type,
                        "message": f"Invalid question type '{question_type}'. Must be one of: {', '.join(valid_types)}",
                        "valid_types": valid_types,
                    }
                )

            # Check if text is provided (optional but recommended)
            if not item.get("text"):
                errors.append(
                    {
                        "index": idx,
                        "field": "text",
                        "message": "Question text is recommended (will default to 'Untitled' if omitted).",
                        "severity": "warning",
                    }
                )

            # Check if options are provided for types that require them
            types_requiring_options = [
                "mc_single",
                "mc_multi",
                "dropdown",
                "orderable",
                "yesno",
                "likert",
            ]
            if question_type in types_requiring_options and not item.get("options"):
                errors.append(
                    {
                        "index": idx,
                        "field": "options",
                        "message": f"Question type '{question_type}' requires an 'options' field.",
                        "severity": "warning",
                    }
                )

        # Return validation errors if any critical errors found
        critical_errors = [e for e in errors if e.get("severity") != "warning"]
        if critical_errors:
            return Response(
                {
                    "errors": critical_errors,
                    "warnings": [e for e in errors if e.get("severity") == "warning"],
                },
                status=400,
            )

        # Create questions
        for item in items:
            group = None
            gname = item.get("group_name")
            if gname:
                group, _ = QuestionGroup.objects.get_or_create(
                    name=gname, owner=request.user
                )
            SurveyQuestion.objects.create(
                survey=survey,
                group=group,
                text=item.get("text", "Untitled"),
                type=item.get("type", "text"),
                options=item.get("options", []),
                required=bool(item.get("required", False)),
                order=int(item.get("order", 0)),
            )
            created += 1

        # Return success with warnings if any
        warnings = [e for e in errors if e.get("severity") == "warning"]
        response_data = {"created": created}
        if warnings:
            response_data["warnings"] = warnings

        return Response(response_data)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        # Return base64 key once to creator
        key = getattr(self, "_created_key", None)
        if key is not None:
            import base64

            resp.data["one_time_key_b64"] = base64.b64encode(key).decode("ascii")
        return resp

    @action(
        detail=True,
        methods=["get", "put"],
        permission_classes=[permissions.IsAuthenticated, OrgOwnerOrAdminPermission],
        url_path="publish",
    )
    def publish_settings(self, request, pk=None):
        """GET/PUT publish settings with SSR-equivalent validation and safeguards."""
        survey = self.get_object()
        ser = SurveyPublishSettingsSerializer(instance=survey)
        if request.method.lower() == "get":
            return Response(ser.data)
        # PUT
        ser = SurveyPublishSettingsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        # Extract values or keep existing
        status = data.get("status", survey.status)
        visibility = data.get("visibility", survey.visibility)
        start_at = data.get("start_at", survey.start_at)
        end_at = data.get("end_at", survey.end_at)
        max_responses = data.get("max_responses", survey.max_responses)
        captcha_required = data.get("captcha_required", survey.captcha_required)
        no_patient_data_ack = data.get(
            "no_patient_data_ack", survey.no_patient_data_ack
        )

        # Enforce patient-data + non-auth visibility disclaimer
        from checktick_app.surveys.views import _survey_collects_patient_data

        collects_patient = _survey_collects_patient_data(survey)
        non_auth_vis = {
            Survey.Visibility.PUBLIC,
            Survey.Visibility.UNLISTED,
            Survey.Visibility.TOKEN,
        }
        if (
            visibility in non_auth_vis
            and collects_patient
            and not no_patient_data_ack
            and visibility != Survey.Visibility.AUTHENTICATED
        ):
            raise serializers.ValidationError(
                {
                    "no_patient_data_ack": "To use public, unlisted, or tokenized visibility, confirm that no patient data is collected.",
                }
            )

        prev_status = survey.status
        is_first_publish = (
            prev_status != Survey.Status.PUBLISHED and status == Survey.Status.PUBLISHED
        )

        # Enforce encryption requirement for surveys collecting patient data
        # API users must set up encryption through the web interface before publishing
        if collects_patient and is_first_publish and not survey.has_any_encryption():
            raise serializers.ValidationError(
                {
                    "encryption": "This survey collects patient data and requires encryption to be set up before publishing. Please use the web interface to configure encryption, then publish via API.",
                }
            )
        survey.status = status
        survey.visibility = visibility
        survey.start_at = start_at
        survey.end_at = end_at
        survey.max_responses = max_responses
        survey.captcha_required = captcha_required
        survey.no_patient_data_ack = no_patient_data_ack
        if (
            prev_status != Survey.Status.PUBLISHED
            and status == Survey.Status.PUBLISHED
            and not survey.published_at
        ):
            survey.published_at = timezone.now()
        if survey.visibility == Survey.Visibility.UNLISTED and not survey.unlisted_key:
            survey.unlisted_key = secrets.token_urlsafe(24)
        survey.save()
        return Response(SurveyPublishSettingsSerializer(instance=survey).data)

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

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[permissions.IsAuthenticated, OrgOwnerOrAdminPermission],
    )
    def tokens(self, request, pk=None):
        """List or create invite tokens for a survey."""
        survey = self.get_object()
        if request.method.lower() == "get":
            tokens = survey.access_tokens.order_by("-created_at")[:500]
            data = [
                {
                    "token": t.token,
                    "created_at": t.created_at,
                    "expires_at": t.expires_at,
                    "used_at": t.used_at,
                    "used_by": t.used_by_id,
                    "note": t.note,
                }
                for t in tokens
            ]
            return Response({"items": data, "count": len(data)})
        # POST create
        count_raw = request.data.get("count", 0)
        try:
            count = int(count_raw)
        except Exception:
            count = 0
        count = max(0, min(count, 1000))
        note = (request.data.get("note") or "").strip()
        expires_raw = request.data.get("expires_at")
        expires_at = None
        if expires_raw:
            expires_at = (
                parse_datetime(expires_raw)
                if isinstance(expires_raw, str)
                else expires_raw
            )
        created = []
        for _ in range(count):
            t = SurveyAccessToken(
                survey=survey,
                token=secrets.token_urlsafe(24),
                created_by=request.user,
                expires_at=expires_at,
                note=note,
            )
            t.save()
            created.append(
                {
                    "token": t.token,
                    "created_at": t.created_at,
                    "expires_at": t.expires_at,
                    "note": t.note,
                }
            )
        return Response({"created": len(created), "items": created})


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = OrganizationMembership
        fields = ["id", "organization", "user", "username", "role", "created_at"]
        read_only_fields = ["created_at"]


class SurveyMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = SurveyMembership
        fields = ["id", "survey", "user", "username", "role", "created_at"]
        read_only_fields = ["created_at"]


class OrganizationMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Only orgs where the user is admin
        admin_orgs = Organization.objects.filter(
            memberships__user=user, memberships__role=OrganizationMembership.Role.ADMIN
        )
        return OrganizationMembership.objects.filter(
            organization__in=admin_orgs
        ).select_related("user", "organization")

    def perform_create(self, serializer):
        org = serializer.validated_data.get("organization")
        if not OrganizationMembership.objects.filter(
            organization=org,
            user=self.request.user,
            role=OrganizationMembership.Role.ADMIN,
        ).exists():
            raise PermissionDenied("Not an admin for this organization")
        instance = serializer.save()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.ORGANIZATION,
            organization=org,
            action=AuditLog.Action.ADD,
            target_user=instance.user,
            metadata={"role": instance.role},
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        org = instance.organization
        if not OrganizationMembership.objects.filter(
            organization=org,
            user=self.request.user,
            role=OrganizationMembership.Role.ADMIN,
        ).exists():
            raise PermissionDenied("Not an admin for this organization")
        instance = serializer.save()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.ORGANIZATION,
            organization=org,
            action=AuditLog.Action.UPDATE,
            target_user=instance.user,
            metadata={"role": instance.role},
        )

    def perform_destroy(self, instance):
        org = instance.organization
        if not OrganizationMembership.objects.filter(
            organization=org,
            user=self.request.user,
            role=OrganizationMembership.Role.ADMIN,
        ).exists():
            raise PermissionDenied("Not an admin for this organization")
        # Prevent org admin removing themselves
        if (
            instance.user_id == self.request.user.id
            and instance.role == OrganizationMembership.Role.ADMIN
        ):
            raise PermissionDenied(
                "You cannot remove yourself as an organization admin"
            )
        instance.delete()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.ORGANIZATION,
            organization=org,
            action=AuditLog.Action.REMOVE,
            target_user=instance.user,
            metadata={"role": instance.role},
        )


class SurveyMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = SurveyMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # user can see memberships for surveys they can view
        allowed_survey_ids = []
        for s in Survey.objects.all():
            if s.owner_id == user.id:
                allowed_survey_ids.append(s.id)
            elif (
                s.organization_id
                and OrganizationMembership.objects.filter(
                    organization=s.organization,
                    user=user,
                    role=OrganizationMembership.Role.ADMIN,
                ).exists()
            ):
                allowed_survey_ids.append(s.id)
            elif SurveyMembership.objects.filter(user=user, survey=s).exists():
                allowed_survey_ids.append(s.id)
        return SurveyMembership.objects.filter(
            survey_id__in=allowed_survey_ids
        ).select_related("user", "survey")

    def _can_manage(self, survey: Survey) -> bool:
        # Individual users (surveys without organization) cannot share surveys
        if not survey.organization_id:
            return False
        # org admin, owner, or survey creator can manage
        if survey.owner_id == self.request.user.id:
            return True
        if (
            survey.organization_id
            and OrganizationMembership.objects.filter(
                organization=survey.organization,
                user=self.request.user,
                role=OrganizationMembership.Role.ADMIN,
            ).exists()
        ):
            return True
        return SurveyMembership.objects.filter(
            user=self.request.user, survey=survey, role=SurveyMembership.Role.CREATOR
        ).exists()

    def perform_create(self, serializer):
        survey = serializer.validated_data.get("survey")
        if not self._can_manage(survey):
            raise PermissionDenied("Not allowed to manage users for this survey")
        instance = serializer.save()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=instance.survey,
            action=AuditLog.Action.ADD,
            target_user=instance.user,
            metadata={"role": instance.role},
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if not self._can_manage(instance.survey):
            raise PermissionDenied("Not allowed to manage users for this survey")
        instance = serializer.save()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=instance.survey,
            action=AuditLog.Action.UPDATE,
            target_user=instance.user,
            metadata={"role": instance.role},
        )

    def perform_destroy(self, instance):
        if not self._can_manage(instance.survey):
            raise PermissionDenied("Not allowed to manage users for this survey")
        instance.delete()
        AuditLog.objects.create(
            actor=self.request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=instance.survey,
            action=AuditLog.Action.REMOVE,
            target_user=instance.user,
            metadata={"role": instance.role},
        )


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()


class ScopedUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)


class ScopedUserViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="org/(?P<org_id>[^/.]+)/create")
    def create_in_org(self, request, org_id=None):
        # Only org admins can create users within their org context
        org = Organization.objects.get(id=org_id)
        if not OrganizationMembership.objects.filter(
            organization=org, user=request.user, role=OrganizationMembership.Role.ADMIN
        ).exists():
            raise PermissionDenied("Not an admin for this organization")
        ser = ScopedUserCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        email = (data.get("email") or "").strip().lower()
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                if User.objects.filter(username=data["username"]).exists():
                    raise serializers.ValidationError({"username": "already exists"})
                user = User.objects.create_user(
                    username=data["username"], email=email, password=data["password"]
                )
        else:
            if User.objects.filter(username=data["username"]).exists():
                raise serializers.ValidationError({"username": "already exists"})
            user = User.objects.create_user(
                username=data["username"], email="", password=data["password"]
            )
        # Optionally add as viewer by default
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=user,
            defaults={"role": OrganizationMembership.Role.VIEWER},
        )
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.ORGANIZATION,
            organization=org,
            action=AuditLog.Action.ADD,
            target_user=user,
            metadata={"created_via": "org"},
        )
        return Response({"id": user.id, "username": user.username, "email": user.email})

    @action(
        detail=False, methods=["post"], url_path="survey/(?P<survey_id>[^/.]+)/create"
    )
    def create_in_survey(self, request, survey_id=None):
        # Survey creators/admins/owner can create users within the survey context
        survey = Survey.objects.get(id=survey_id)

        # Individual users (surveys without organization) cannot share surveys
        if not survey.organization_id:
            raise PermissionDenied("Individual users cannot share surveys")

        # Reuse the SurveyMembershipViewSet _can_manage logic inline
        def can_manage(user):
            if survey.owner_id == user.id:
                return True
            if (
                survey.organization_id
                and OrganizationMembership.objects.filter(
                    organization=survey.organization,
                    user=user,
                    role=OrganizationMembership.Role.ADMIN,
                ).exists()
            ):
                return True
            return SurveyMembership.objects.filter(
                user=user, survey=survey, role=SurveyMembership.Role.CREATOR
            ).exists()

        if not can_manage(request.user):
            raise PermissionDenied("Not allowed to manage users for this survey")
        ser = ScopedUserCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        email = (data.get("email") or "").strip().lower()
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                if User.objects.filter(username=data["username"]).exists():
                    raise serializers.ValidationError({"username": "already exists"})
                user = User.objects.create_user(
                    username=data["username"], email=email, password=data["password"]
                )
        else:
            if User.objects.filter(username=data["username"]).exists():
                raise serializers.ValidationError({"username": "already exists"})
            user = User.objects.create_user(
                username=data["username"], email="", password=data["password"]
            )
        SurveyMembership.objects.get_or_create(
            survey=survey, user=user, defaults={"role": SurveyMembership.Role.VIEWER}
        )
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=survey,
            action=AuditLog.Action.ADD,
            target_user=user,
            metadata={"created_via": "survey"},
        )
        return Response({"id": user.id, "username": user.username, "email": user.email})


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


class DataSetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing DataSet objects.

    GET /api/datasets/ - List all accessible datasets
    GET /api/datasets/{key}/ - Retrieve specific dataset
    POST /api/datasets/ - Create new dataset (ADMIN/CREATOR only)
    PATCH /api/datasets/{key}/ - Update dataset (ADMIN/CREATOR of org only)
    DELETE /api/datasets/{key}/ - Delete dataset (ADMIN/CREATOR of org only)

    Access control:
    - List/Retrieve: Shows global datasets + user's organization datasets
    - Create: Requires ADMIN or CREATOR role in an organization
    - Update/Delete: Requires ADMIN or CREATOR role in dataset's organization
    - NHS DD datasets cannot be modified or deleted
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

    def perform_create(self, serializer):
        """Set created_by to current user and assign to organization if applicable."""
        user = self.request.user
        # TODO: In future, check if user has pro account

        # Determine organization from request or user's first org
        org_id = self.request.data.get("organization")
        org = None

        if org_id:
            # Verify user has ADMIN/CREATOR role in specified org
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                raise PermissionDenied("Organization not found")

            membership = OrganizationMembership.objects.filter(
                organization=org,
                user=user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.CREATOR,
                ],
            ).first()
            if not membership:
                raise PermissionDenied(
                    "You must be an ADMIN or CREATOR in this organization"
                )
        else:
            # Try to use first organization where user is ADMIN/CREATOR
            membership = OrganizationMembership.objects.filter(
                user=user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.CREATOR,
                ],
            ).first()
            if membership:
                org = membership.organization
            # If no org membership, org remains None (individual user dataset)

        # Generate unique key if not provided
        import time

        from django.utils.text import slugify

        name = self.request.data.get("name", "dataset")
        base_key = slugify(name)[:50]  # Limit to 50 chars

        # Add org or user ID plus timestamp for uniqueness
        if org:
            key = f"{base_key}_{org.id}_{int(time.time())}"
        else:
            key = f"{base_key}_u{user.id}_{int(time.time())}"

        # Ensure uniqueness
        counter = 1
        original_key = key
        while DataSet.objects.filter(key=key).exists():
            key = f"{original_key}_{counter}"
            counter += 1

        # Set defaults for user-created datasets
        serializer.save(
            key=key,
            created_by=user,
            organization=org,  # Can be None for individual users
            category="user_created",
            source_type="manual",
            is_custom=True,
            is_global=False,  # Datasets are not global by default
        )

    def perform_update(self, serializer):
        """Increment version on update."""
        instance = self.get_object()
        serializer.save(version=instance.version + 1)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsOrgAdminOrCreator],
        url_path="create-custom",
    )
    def create_custom_version(self, request, key=None):
        """
        Create a customized version of a global dataset.

        POST /api/datasets/{key}/create-custom/
        Body: {
            "name": "Optional custom name",
            "organization": "Optional organization ID (defaults to user's first org)"
        }

        Returns the newly created custom dataset.
        """
        dataset = self.get_object()
        user = request.user

        # Verify dataset is global
        if not dataset.is_global:
            return Response(
                {"error": "Can only create custom versions of global datasets"},
                status=400,
            )

        # Get organization
        # TODO: In future, check if user has pro account
        org_id = request.data.get("organization")
        custom_name = request.data.get("name")
        org = None

        if org_id:
            # Verify user has ADMIN/CREATOR role in specified org
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                return Response({"error": "Organization not found"}, status=404)

            membership = OrganizationMembership.objects.filter(
                organization=org,
                user=user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.CREATOR,
                ],
            ).first()
            if not membership:
                return Response(
                    {"error": "You must be an ADMIN or CREATOR in this organization"},
                    status=403,
                )
        else:
            # Try to use first organization where user is ADMIN/CREATOR
            membership = OrganizationMembership.objects.filter(
                user=user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.CREATOR,
                ],
            ).first()
            if membership:
                org = membership.organization
            # If no org membership, org remains None (individual user dataset)

        # Create custom version
        try:
            custom_dataset = dataset.create_custom_version(
                user=user, organization=org, custom_name=custom_name
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        serializer = self.get_serializer(custom_dataset)
        return Response(serializer.data, status=201)

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

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsOrgAdminOrCreator],
        url_path="publish",
    )
    def publish_dataset(self, request, key=None):
        """
        Publish a dataset globally.

        POST /api/datasets/{key}/publish/

        Makes the dataset available to all users while retaining
        creator/organization attribution.
        """
        dataset = self.get_object()
        user = request.user
        # TODO: In future, check if user has pro account

        # Verify user has permission to publish
        if dataset.is_global:
            return Response(
                {"error": "Dataset is already published globally"}, status=400
            )

        # Verify user owns the dataset (either created it or is ADMIN/CREATOR in org)
        if dataset.organization:
            # Organization dataset - verify user is ADMIN/CREATOR in the organization
            membership = OrganizationMembership.objects.filter(
                organization=dataset.organization,
                user=user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.CREATOR,
                ],
            ).first()

            if not membership:
                return Response(
                    {
                        "error": "You must be an ADMIN or CREATOR in the dataset's organization"
                    },
                    status=403,
                )
        else:
            # Individual user dataset - verify user created it
            if dataset.created_by != user:
                return Response(
                    {"error": "You can only publish datasets you created"},
                    status=403,
                )

        # Publish the dataset
        try:
            dataset.publish()
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        serializer = self.get_serializer(dataset)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete by setting is_active=False."""
        instance = self.get_object()

        # Prevent deletion of NHS DD datasets
        if instance.category == "nhs_dd":
            raise PermissionDenied("NHS Data Dictionary datasets cannot be deleted")

        # Prevent deletion of published datasets with dependents
        if instance.published_at and instance.has_dependents():
            return Response(
                {
                    "error": "Cannot delete published dataset that has custom versions created by others. "
                    "This dataset is being used as a base for other lists."
                },
                status=400,
            )

        # Soft delete
        instance.is_active = False
        instance.save()

        return Response(status=204)


@csp_exempt
def swagger_ui(request):
    """Render an embedded Swagger UI that points at the API schema endpoint.

    CSP is exempted on this route to allow loading Swagger UI assets.
    """
    return render(request, "api/swagger.html", {})


@csp_exempt
def redoc_ui(request):
    """Render an embedded ReDoc UI pointing at the API schema endpoint.

    CSP is exempted on this route to allow loading ReDoc assets.
    """
    return render(request, "api/redoc.html", {})
