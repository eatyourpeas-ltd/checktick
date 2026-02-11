import os
import secrets
from typing import Any

from csp.decorators import csp_exempt
from django.contrib.auth import get_user_model
from django.db import models
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
from rest_framework.throttling import UserRateThrottle

from checktick_app.surveys.models import (
    AuditLog,
    DataSet,
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    RecoveryAuditEntry,
    RecoveryRequest,
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
        # Check tier limits for survey creation
        from checktick_app.core.tier_limits import check_survey_creation_limit

        can_create, reason = check_survey_creation_limit(self.request.user)
        if not can_create:
            raise PermissionDenied(reason)

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

        # Check if any questions are patient template type
        has_patient_template = any(
            item.get("type") == "template_patient" for item in items
        )
        if has_patient_template:
            from checktick_app.core.tier_limits import check_patient_data_permission

            can_collect, reason = check_patient_data_permission(request.user)
            if not can_collect:
                return Response(
                    {
                        "errors": [
                            {
                                "field": "type",
                                "value": "template_patient",
                                "message": f"{reason} Patient details templates require a paid subscription.",
                            }
                        ]
                    },
                    status=403,
                )

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

        # Enforce encryption requirement for ALL surveys (not just patient data surveys)
        # API users must set up encryption through the web interface before publishing
        # Note: Survey count limits are already enforced at survey creation time
        if is_first_publish and not survey.has_any_encryption():
            raise serializers.ValidationError(
                {
                    "encryption": "All surveys require encryption to be set up before publishing. Please use the web interface to configure encryption, then publish via API.",
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
        role = serializer.validated_data.get("role")

        if not self._can_manage(survey):
            raise PermissionDenied("Not allowed to manage users for this survey")

        # Check tier limits for collaboration
        from checktick_app.core.tier_limits import (
            check_collaboration_limit,
            check_collaborators_per_survey_limit,
        )

        # Determine collaboration type from role
        collaboration_type = (
            "editor"
            if role in [SurveyMembership.Role.CREATOR, SurveyMembership.Role.EDITOR]
            else "viewer"
        )

        # Check if user can add this type of collaborator
        can_add, limit_reason = check_collaboration_limit(
            self.request.user, collaboration_type
        )
        if not can_add:
            raise PermissionDenied(limit_reason)

        # Check per-survey collaborator limit
        can_add_to_survey, survey_reason = check_collaborators_per_survey_limit(survey)
        if not can_add_to_survey:
            raise PermissionDenied(survey_reason)

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


@csp_exempt()
def swagger_ui(request):
    """Render an embedded Swagger UI that points at the API schema endpoint.

    CSP is exempted on this route to allow loading Swagger UI assets.
    """
    return render(request, "api/swagger.html", {})


@csp_exempt()
def redoc_ui(request):
    """Render an embedded ReDoc UI pointing at the API schema endpoint.

    CSP is exempted on this route to allow loading ReDoc assets.
    """
    return render(request, "api/redoc.html", {})


# =============================================================================
# Key Recovery API
# =============================================================================


# -----------------------------------------------------------------------------
# Recovery Throttle Classes - Strict rate limits for security-sensitive actions
# -----------------------------------------------------------------------------


class RecoveryCreateThrottle(UserRateThrottle):
    """
    Strict throttle for creating recovery requests.
    Limit: 3 requests per hour per user.
    """

    scope = "recovery_create"
    rate = "3/hour"


class RecoveryApprovalThrottle(UserRateThrottle):
    """
    Strict throttle for approval/rejection actions.
    Limit: 10 actions per hour per admin.
    """

    scope = "recovery_approval"
    rate = "10/hour"


class RecoveryViewThrottle(UserRateThrottle):
    """
    Moderate throttle for viewing recovery requests.
    Limit: 60 views per minute per user.
    """

    scope = "recovery_view"
    rate = "60/minute"


# -----------------------------------------------------------------------------
# Recovery Audit Logging Helper
# -----------------------------------------------------------------------------


def log_recovery_audit(
    recovery_request,
    event_type: str,
    actor_type: str,
    severity: str = "info",
    actor_id: int | None = None,
    actor_email: str | None = None,
    actor_ip: str | None = None,
    actor_user_agent: str = "",
    details: dict | None = None,
) -> "RecoveryAuditEntry":
    """
    Create an immutable audit log entry for a recovery action.

    Args:
        recovery_request: The RecoveryRequest instance
        event_type: Type of event (e.g., 'request_submitted', 'primary_approval')
        actor_type: 'user', 'admin', or 'system'
        severity: 'info', 'warning', or 'critical'
        actor_id: User ID of the actor
        actor_email: Email of the actor
        actor_ip: IP address of the actor
        actor_user_agent: User agent string
        details: Additional JSON details

    Returns:
        The created RecoveryAuditEntry
    """
    import hashlib
    import json

    # Get previous entry hash for chain integrity
    previous_entry = recovery_request.audit_entries.order_by("-timestamp").first()
    previous_hash = previous_entry.entry_hash if previous_entry else ""

    # Create entry
    entry = RecoveryAuditEntry(
        recovery_request=recovery_request,
        event_type=event_type,
        severity=severity,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        actor_ip=actor_ip,
        actor_user_agent=actor_user_agent,
        details=details or {},
        previous_hash=previous_hash,
    )

    # Calculate entry hash for tamper detection
    hash_data = json.dumps(
        {
            "request_id": str(recovery_request.id),
            "event_type": event_type,
            "severity": severity,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "details": details or {},
            "previous_hash": previous_hash,
        },
        sort_keys=True,
    )
    entry.entry_hash = hashlib.sha256(hash_data.encode()).hexdigest()

    entry.save()
    return entry


# -----------------------------------------------------------------------------
# Recovery Serializers
# -----------------------------------------------------------------------------


class RecoveryRequestSerializer(serializers.ModelSerializer):
    """Serializer for recovery request list and details."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    survey_name = serializers.CharField(source="survey.name", read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField()

    class Meta:

        model = RecoveryRequest
        fields = [
            "id",
            "request_code",
            "user_email",
            "survey_name",
            "status",
            "submitted_at",
            "verification_completed_at",
            "approved_at",
            "time_delay_until",
            "time_delay_hours",
            "completed_at",
            "time_remaining_seconds",
        ]
        read_only_fields = fields

    def get_time_remaining_seconds(self, obj) -> int | None:
        remaining = obj.time_remaining
        if remaining:
            return int(remaining.total_seconds())
        return None


class RecoveryRequestCreateSerializer(serializers.Serializer):
    """Serializer for creating a new recovery request."""

    survey_id = serializers.IntegerField(
        help_text="ID of the survey to recover access to"
    )
    reason = serializers.CharField(
        max_length=1000,
        help_text="Explanation of why recovery is needed",
    )


class RecoveryApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting recovery requests."""

    reason = serializers.CharField(
        max_length=1000,
        help_text="Verification notes or reason for decision",
    )


class RecoveryCancelSerializer(serializers.Serializer):
    """Serializer for cancelling recovery requests."""

    reason = serializers.CharField(
        max_length=1000,
        required=False,
        default="",
        help_text="Reason for cancellation",
    )


class RecoveryAdminDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for admins reviewing recovery requests."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    survey_name = serializers.CharField(source="survey.name", read_only=True)
    survey_slug = serializers.CharField(source="survey.slug", read_only=True)
    primary_approver_email = serializers.EmailField(
        source="primary_approver.email", read_only=True, allow_null=True
    )
    secondary_approver_email = serializers.EmailField(
        source="secondary_approver.email", read_only=True, allow_null=True
    )
    rejected_by_email = serializers.EmailField(
        source="rejected_by.email", read_only=True, allow_null=True
    )
    time_remaining_seconds = serializers.SerializerMethodField()
    identity_verifications = serializers.SerializerMethodField()
    is_verification_complete = serializers.BooleanField(read_only=True)

    class Meta:

        model = RecoveryRequest
        fields = [
            "id",
            "request_code",
            "user_email",
            "user_username",
            "survey_name",
            "survey_slug",
            "status",
            "submitted_at",
            "verification_completed_at",
            "approved_at",
            "time_delay_until",
            "time_delay_hours",
            "completed_at",
            "time_remaining_seconds",
            "primary_approver_email",
            "primary_approved_at",
            "primary_reason",
            "secondary_approver_email",
            "secondary_approved_at",
            "secondary_reason",
            "rejected_by_email",
            "rejected_at",
            "rejection_reason",
            "user_context",
            "identity_verifications",
            "is_verification_complete",
        ]
        read_only_fields = fields

    def get_time_remaining_seconds(self, obj) -> int | None:
        remaining = obj.time_remaining
        if remaining:
            return int(remaining.total_seconds())
        return None

    def get_identity_verifications(self, obj) -> list:
        return [
            {
                "id": str(v.id),
                "verification_type": v.verification_type,
                "status": v.status,
                "submitted_at": v.submitted_at,
                "verified_at": v.verified_at,
            }
            for v in obj.identity_verifications.all()
        ]


class IsPlatformAdmin(permissions.BasePermission):
    """Permission that requires user to be a platform admin (staff or superuser)."""

    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_superuser)


class RecoveryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for key recovery requests.

    Users can:
    - Create recovery requests for their own surveys
    - View status of their own recovery requests
    - Cancel their own pending requests

    Platform admins can:
    - View all recovery requests
    - Approve or reject requests
    - Execute completed requests

    Rate Limits:
    - Create requests: 3/hour per user
    - View requests: 60/minute per user
    - Admin actions (approve/reject): 10/hour per admin
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [RecoveryViewThrottle]
    http_method_names = ["get", "post"]

    def get_throttles(self):
        """Apply action-specific throttles."""
        if self.action == "create":
            return [RecoveryCreateThrottle()]
        if self.action in ["approve_primary", "approve_secondary", "reject"]:
            return [RecoveryApprovalThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "create":
            return RecoveryRequestCreateSerializer
        if self.action in ["approve_primary", "approve_secondary", "reject"]:
            return RecoveryApprovalSerializer
        if self.action == "cancel":
            return RecoveryCancelSerializer
        if self.action in ["retrieve", "admin_list"] and self.request.user.is_staff:
            return RecoveryAdminDetailSerializer
        return RecoveryRequestSerializer

    def get_queryset(self):

        user = self.request.user

        # Platform admins see all requests
        if user.is_staff or user.is_superuser:
            return RecoveryRequest.objects.select_related(
                "user",
                "survey",
                "primary_approver",
                "secondary_approver",
                "rejected_by",
            ).prefetch_related("identity_verifications")

        # Regular users only see their own requests
        return RecoveryRequest.objects.filter(user=user).select_related(
            "user", "survey"
        )

    def create(self, request):
        """
        Create a new recovery request.

        The user must own responses on the specified survey.
        """
        from checktick_app.surveys.models import Survey

        serializer = RecoveryRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        survey_id = serializer.validated_data["survey_id"]
        reason = serializer.validated_data["reason"]

        # Check survey exists and user has responses
        try:
            survey = Survey.objects.get(id=survey_id)
        except Survey.DoesNotExist:
            return Response({"error": "Survey not found"}, status=404)

        # Check user has encrypted responses on this survey
        has_encrypted_responses = (
            survey.responses.filter(submitted_by=request.user)
            .exclude(enc_demographics__isnull=True)
            .exists()
        )

        has_whole_response_encrypted = (
            survey.responses.filter(submitted_by=request.user)
            .exclude(enc_answers__isnull=True)
            .exists()
        )

        if not has_encrypted_responses and not has_whole_response_encrypted:
            return Response(
                {"error": "No encrypted data found for this survey"},
                status=400,
            )

        # Check no pending request already exists
        existing = RecoveryRequest.objects.filter(
            user=request.user,
            survey=survey,
            status__in=[
                RecoveryRequest.Status.PENDING_VERIFICATION,
                RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
                RecoveryRequest.Status.AWAITING_PRIMARY,
                RecoveryRequest.Status.AWAITING_SECONDARY,
                RecoveryRequest.Status.IN_TIME_DELAY,
                RecoveryRequest.Status.READY_FOR_EXECUTION,
            ],
        ).exists()

        if existing:
            return Response(
                {"error": "A pending recovery request already exists for this survey"},
                status=400,
            )

        # Determine time delay based on user tier
        time_delay_hours = 48  # Individual users: 48 hours
        if survey.organization:
            time_delay_hours = 24  # Organization users: 24 hours

        # Create the recovery request
        recovery_request = RecoveryRequest.objects.create(
            user=request.user,
            survey=survey,
            time_delay_hours=time_delay_hours,
            user_context={
                "email": request.user.email,
                "username": request.user.username,
                "account_created": str(request.user.date_joined),
                "reason": reason,
                "ip_address": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )

        # Audit log: request submitted
        log_recovery_audit(
            recovery_request=recovery_request,
            event_type="request_submitted",
            actor_type="user",
            severity="info",
            actor_id=request.user.id,
            actor_email=request.user.email,
            actor_ip=self._get_client_ip(request),
            actor_user_agent=request.META.get("HTTP_USER_AGENT", ""),
            details={
                "survey_id": survey.id,
                "survey_name": survey.name,
                "reason": reason,
                "time_delay_hours": time_delay_hours,
            },
        )

        # Send notification emails
        self._send_request_notifications(recovery_request, reason)

        output_serializer = RecoveryRequestSerializer(recovery_request)
        return Response(output_serializer.data, status=201)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a recovery request."""
        recovery_request = self.get_object()

        # Check user owns this request or is admin
        if recovery_request.user != request.user and not request.user.is_staff:
            raise PermissionDenied("You can only cancel your own recovery requests")

        # Check request can be cancelled
        cancellable_statuses = [
            recovery_request.Status.PENDING_VERIFICATION,
            recovery_request.Status.VERIFICATION_IN_PROGRESS,
            recovery_request.Status.AWAITING_PRIMARY,
            recovery_request.Status.AWAITING_SECONDARY,
            recovery_request.Status.IN_TIME_DELAY,
        ]

        if recovery_request.status not in cancellable_statuses:
            return Response(
                {
                    "error": f"Cannot cancel request in status: {recovery_request.status}"
                },
                status=400,
            )

        serializer = RecoveryCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recovery_request.cancel(
            user=request.user,
            reason=serializer.validated_data.get("reason", "User cancelled request"),
        )

        # Note: audit logging is handled by RecoveryRequest.cancel()

        # Send cancellation notification
        self._send_cancellation_notification(recovery_request)

        output_serializer = RecoveryRequestSerializer(recovery_request)
        return Response(output_serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsPlatformAdmin],
    )
    def approve_primary(self, request, pk=None):
        """Primary admin approval for a recovery request."""
        recovery_request = self.get_object()

        serializer = RecoveryApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            recovery_request.approve_primary(
                admin=request.user,
                reason=serializer.validated_data["reason"],
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        # Note: audit logging is handled by RecoveryRequest.approve_primary()

        output_serializer = RecoveryAdminDetailSerializer(recovery_request)
        return Response(output_serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsPlatformAdmin],
    )
    def approve_secondary(self, request, pk=None):
        """Secondary admin approval for a recovery request (starts time delay)."""

        from checktick_app.core.email_utils import send_recovery_approved_email

        recovery_request = self.get_object()

        serializer = RecoveryApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            recovery_request.approve_secondary(
                admin=request.user,
                reason=serializer.validated_data["reason"],
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        # Note: audit logging is handled by RecoveryRequest.approve_secondary()

        # Send approval notification with time delay info
        send_recovery_approved_email(
            to_email=recovery_request.user.email,
            user_name=recovery_request.user.username,
            request_id=recovery_request.request_code,
            survey_name=recovery_request.survey.name,
            time_delay_hours=recovery_request.time_delay_hours,
            access_available_at=recovery_request.time_delay_until.strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
            approved_by="Platform Administrator",
        )

        output_serializer = RecoveryAdminDetailSerializer(recovery_request)
        return Response(output_serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsPlatformAdmin],
    )
    def reject(self, request, pk=None):
        """Reject a recovery request."""
        from checktick_app.core.email_utils import send_recovery_rejected_email

        recovery_request = self.get_object()

        serializer = RecoveryApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recovery_request.reject(
            admin=request.user,
            reason=serializer.validated_data["reason"],
        )

        # Note: audit logging is handled by RecoveryRequest.reject()

        # Send rejection notification
        send_recovery_rejected_email(
            to_email=recovery_request.user.email,
            user_name=recovery_request.user.username,
            request_id=recovery_request.request_code,
            survey_name=recovery_request.survey.name,
            reason=serializer.validated_data["reason"],
            rejected_by="Platform Administrator",
        )

        output_serializer = RecoveryAdminDetailSerializer(recovery_request)
        return Response(output_serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated, IsPlatformAdmin],
        url_path="admin",
    )
    def admin_list(self, request):
        """List all recovery requests for admin dashboard."""

        queryset = self.get_queryset()

        # Filter by status if provided
        status = request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Pagination
        page_size = int(request.query_params.get("page_size", 20))
        page = int(request.query_params.get("page", 1))
        offset = (page - 1) * page_size

        total = queryset.count()
        requests = queryset[offset : offset + page_size]

        serializer = RecoveryAdminDetailSerializer(requests, many=True)
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsPlatformAdmin],
        url_path="check-time-delay",
    )
    def check_time_delay(self, request, pk=None):
        """Check if time delay has completed and update status."""
        recovery_request = self.get_object()

        completed = recovery_request.check_time_delay_complete()

        if completed:
            # Send ready notification
            from django.conf import settings

            from checktick_app.core.email_utils import send_recovery_ready_email

            site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
            recovery_url = (
                f"{site_url}/recovery/complete/{recovery_request.request_code}/"
            )

            send_recovery_ready_email(
                to_email=recovery_request.user.email,
                user_name=recovery_request.user.username,
                request_id=recovery_request.request_code,
                survey_name=recovery_request.survey.name,
                recovery_url=recovery_url,
            )

        output_serializer = RecoveryAdminDetailSerializer(recovery_request)
        return Response(
            {
                "time_delay_complete": completed,
                "request": output_serializer.data,
            }
        )

    def _get_client_ip(self, request) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _send_request_notifications(self, recovery_request, reason: str) -> None:
        """Send notifications when a recovery request is created."""
        from django.conf import settings

        from checktick_app.core.email_utils import (
            send_recovery_admin_notification_email,
            send_recovery_request_submitted_email,
            send_recovery_security_alert_email,
        )

        site_url = getattr(settings, "SITE_URL", "http://localhost:8000")

        # Notify user
        send_recovery_request_submitted_email(
            to_email=recovery_request.user.email,
            user_name=recovery_request.user.username,
            request_id=recovery_request.request_code,
            survey_name=recovery_request.survey.name,
            reason=reason,
        )

        # Notify platform admins
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        dashboard_url = f"{site_url}/admin/recovery/{recovery_request.id}/"

        for admin in admin_users:
            send_recovery_admin_notification_email(
                to_email=admin.email,
                admin_name=admin.username,
                request_id=recovery_request.request_code,
                requester_name=recovery_request.user.username,
                requester_email=recovery_request.user.email,
                survey_name=recovery_request.survey.name,
                reason=reason,
                dashboard_url=dashboard_url,
            )

        # Send security alert to user
        action_url = f"{site_url}/security/report-unauthorized/"
        send_recovery_security_alert_email(
            to_email=recovery_request.user.email,
            user_name=recovery_request.user.username,
            request_id=recovery_request.request_code,
            survey_name=recovery_request.survey.name,
            alert_type="Recovery Request Initiated",
            alert_details="A key recovery request was submitted for your account. "
            "If you did not initiate this request, please report it immediately.",
            action_url=action_url,
        )

    def _send_cancellation_notification(self, recovery_request) -> None:
        """Send notification when a recovery request is cancelled."""
        from checktick_app.core.email_utils import send_recovery_cancelled_email

        send_recovery_cancelled_email(
            to_email=recovery_request.user.email,
            user_name=recovery_request.user.username,
            request_id=recovery_request.request_code,
            survey_name=recovery_request.survey.name,
            cancelled_by=(
                "You"
                if recovery_request.cancelled_by == recovery_request.user
                else "Platform Administrator"
            ),
            reason=recovery_request.cancellation_reason,
        )
