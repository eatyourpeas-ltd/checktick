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

from checktick_app.surveys.external_datasets import (
    DatasetFetchError,
    fetch_dataset,
    get_available_datasets,
)
from checktick_app.surveys.models import (
    AuditLog,
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


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_datasets(request):
    """
    List available prefilled datasets for dropdowns.

    Returns global datasets plus organization-specific datasets
    if user belongs to an organization.
    """
    # Get user's organization from their surveys (if any)
    organization = None
    if request.user.is_authenticated:
        # Get first organization from user's surveys
        user_survey = request.user.surveys.select_related("organization").first()
        if user_survey:
            organization = user_survey.organization

    datasets = get_available_datasets(organization=organization)
    return Response(
        {"datasets": [{"key": key, "name": name} for key, name in datasets.items()]}
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def get_dataset(request, dataset_key):
    """
    Fetch options for a specific dataset from external API or database.

    Returns cached data when available to minimize external API calls.
    Allows anonymous access to support public survey submissions.

    Access control: Only returns datasets that are either global or
    belong to the requesting user's organization.
    """
    try:
        # Get user's organization if authenticated
        organization = None
        if request.user.is_authenticated:
            user_survey = request.user.surveys.select_related("organization").first()
            if user_survey:
                organization = user_survey.organization

        # Verify user has access to this dataset
        from django.db.models import Q

        from checktick_app.surveys.models import DataSet

        dataset_obj = (
            DataSet.objects.filter(key=dataset_key, is_active=True)
            .filter(
                Q(is_global=True) | Q(organization=organization)
                if organization
                else Q(is_global=True)
            )
            .first()
        )

        if dataset_obj:
            # Return from database
            options = dataset_obj.options
        else:
            # Fall back to external API (for backward compatibility)
            options = fetch_dataset(dataset_key)

        return Response({"dataset_key": dataset_key, "options": options})
    except DatasetFetchError as e:
        # Check if it's a validation error (invalid key) vs external API error
        error_msg = str(e)
        if "Unknown dataset key" in error_msg:
            return Response({"error": error_msg}, status=400)
        # External API failures return 502 Bad Gateway
        return Response({"error": error_msg}, status=502)


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
