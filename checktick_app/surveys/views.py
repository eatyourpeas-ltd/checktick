from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import logging
import re
import secrets
from typing import Any, Iterable, Union

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, models, transaction
from django.db.models import Q, QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
    QueryDict,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .color import hex_to_oklch
from .external_datasets import get_available_datasets
from .llm_client import ConversationalSurveyLLM
from .markdown_import import BulkParseError, parse_bulk_markdown_with_collections
from .models import (
    SUPPORTED_SURVEY_LANGUAGES,
    AuditLog,
    CollectionDefinition,
    CollectionItem,
    DataSet,
    LLMConversationSession,
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    RecoveryAuditEntry,
    RecoveryRequest,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyProgress,
    SurveyQuestion,
    SurveyQuestionCondition,
    SurveyResponse,
)
from .permissions import (
    can_create_datasets,
    can_edit_dataset,
    can_edit_survey,
    can_export_survey_data,
    can_manage_org_users,
    can_manage_survey_users,
    can_view_survey,
    require_can_create_datasets,
    require_can_edit,
    require_can_edit_dataset,
    require_can_view,
)
from .utils import verify_key

logger = logging.getLogger(__name__)

# Demographics field definitions: key -> display label
DEMOGRAPHIC_FIELD_DEFS: dict[str, str] = {
    "first_name": "First name",
    "surname": "Surname",
    "date_of_birth": "Date of birth",
    "ethnicity": "Ethnicity",
    "sex": "Sex",
    "gender": "Gender",
    "nhs_number": "NHS number",
    "hospital_number": "Hospital number",
    "post_code": "Post code",
    "address_first_line": "Address line 1",
    "address_second_line": "Address line 2",
    "city": "City",
    "country": "Country",
}


def _get_patient_group_and_fields(
    survey: Survey,
) -> tuple[QuestionGroup | None, list[str]]:
    group = survey.question_groups.filter(
        schema__template="patient_details_encrypted"
    ).first()
    if not group:
        return None, []
    raw = group.schema or {}
    sel = raw.get("fields") or []
    # sanitize selection
    fields = [k for k in sel if k in DEMOGRAPHIC_FIELD_DEFS]
    return group, fields


# Professional details (non-encrypted) field definitions
PROFESSIONAL_FIELD_DEFS: dict[str, str] = {
    "title": "Title",
    "first_name": "First name",
    "surname": "Surname",
    "job_title": "Job title",
    "employing_trust": "Employing Trust",
    "employing_health_board": "Employing Health Board",
    "integrated_care_board": "Integrated Care Board",
    "nhs_england_region": "NHS England region",
    "country": "Country",
    "gp_surgery": "GP surgery",
}

# Fields that can optionally include an ODS code alongside their text
PROFESSIONAL_ODS_FIELDS = {
    "employing_trust",
    "employing_health_board",
    "integrated_care_board",
    "gp_surgery",
}

# Map professional fields to external dataset keys (for prefilled dropdowns)
PROFESSIONAL_FIELD_TO_DATASET = {
    "employing_trust": "nhs_trusts",
    "employing_health_board": "welsh_lhbs",
    "integrated_care_board": "integrated_care_boards",
    "nhs_england_region": "nhs_england_regions",
    "gp_surgery": "hospitals_england_wales",  # GP surgeries could use hospitals dataset
}

PATIENT_TEMPLATE_DEFAULT_FIELDS = [
    "first_name",
    "surname",
    "hospital_number",
    "date_of_birth",
]

PROFESSIONAL_TEMPLATE_DEFAULT_FIELDS = [
    "title",
    "first_name",
    "surname",
    "job_title",
    "employing_trust",
    "employing_health_board",
    "integrated_care_board",
    "nhs_england_region",
    "country",
    "gp_surgery",
]

PROFESSIONAL_TEMPLATE_DEFAULT_ODS = {
    "employing_trust": False,
    "employing_health_board": False,
    "integrated_care_board": False,
    "gp_surgery": False,
}


CONDITION_OPERATORS_REQUIRING_VALUE = {
    SurveyQuestionCondition.Operator.EQUALS,
    SurveyQuestionCondition.Operator.NOT_EQUALS,
    SurveyQuestionCondition.Operator.CONTAINS,
    SurveyQuestionCondition.Operator.NOT_CONTAINS,
    SurveyQuestionCondition.Operator.GREATER_THAN,
    SurveyQuestionCondition.Operator.GREATER_EQUAL,
    SurveyQuestionCondition.Operator.LESS_THAN,
    SurveyQuestionCondition.Operator.LESS_EQUAL,
}


def _normalize_patient_template_options(raw: Any) -> dict[str, Any]:
    """Return a normalized patient template options payload.

    Ensures we have a field entry for every known demographic key and that each
    entry includes a boolean ``selected`` flag. ``include_imd`` is only enabled
    when Post code is selected. This helper accepts historic formats where
    ``fields`` could be a simple list of strings or a list of dicts without an
    explicit ``selected`` flag.
    """

    options = raw if isinstance(raw, dict) else {}
    if not isinstance(options, dict):
        options = {}
    else:
        options = {**options}

    template_key = options.get("template") or "patient_details_encrypted"
    fields_data = options.get("fields")

    selected_keys: set[str] = set()
    meta_map: dict[str, dict[str, Any]] = {}

    if isinstance(fields_data, list):
        for item in fields_data:
            if isinstance(item, str):
                selected_keys.add(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("value")
                if not key:
                    continue
                meta_map[key] = item
                if "selected" in item:
                    if bool(item.get("selected")):
                        selected_keys.add(key)
                else:
                    # Pre-refactor payloads only listed selected fields
                    selected_keys.add(key)
    elif isinstance(fields_data, dict):
        for key, val in fields_data.items():
            if val:
                selected_keys.add(str(key))

    if not selected_keys and not meta_map:
        selected_keys = set(PATIENT_TEMPLATE_DEFAULT_FIELDS)

    normalized_fields: list[dict[str, Any]] = []
    for key, label in DEMOGRAPHIC_FIELD_DEFS.items():
        meta = meta_map.get(key, {}) if isinstance(meta_map.get(key), dict) else {}
        if "selected" in meta:
            selected = bool(meta.get("selected"))
        else:
            selected = key in selected_keys
        display_label = meta.get("label") or label
        normalized_fields.append(
            {
                "key": key,
                "label": display_label,
                "selected": bool(selected),
            }
        )

    include_imd = bool(options.get("include_imd"))
    has_postcode = any(
        field["key"] == "post_code" and field.get("selected")
        for field in normalized_fields
    )
    if not has_postcode:
        include_imd = False

    normalized: dict[str, Any] = {
        "template": template_key,
        "fields": normalized_fields,
        "include_imd": include_imd,
    }

    for key, value in options.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def _normalize_professional_template_options(raw: Any) -> dict[str, Any]:
    """Return a normalized professional template options payload.

    Populates every known professional field with a ``selected`` flag and, for
    fields that support ODS, an ``ods_enabled`` flag. Accepts historic formats
    where ``fields`` was a list of strings or dicts with ``has_ods``.
    """

    options = raw if isinstance(raw, dict) else {}
    if not isinstance(options, dict):
        options = {}
    else:
        options = {**options}

    template_key = options.get("template") or "professional_details"
    fields_data = options.get("fields")

    selected_keys: set[str] = set()
    meta_map: dict[str, dict[str, Any]] = {}

    if isinstance(fields_data, list):
        for item in fields_data:
            if isinstance(item, str):
                selected_keys.add(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("value")
                if not key:
                    continue
                meta_map[key] = item
                if "selected" in item:
                    if bool(item.get("selected")):
                        selected_keys.add(key)
                else:
                    selected_keys.add(key)
    elif isinstance(fields_data, dict):
        for key, val in fields_data.items():
            if val:
                selected_keys.add(str(key))

    if not selected_keys and not meta_map:
        selected_keys = set(PROFESSIONAL_TEMPLATE_DEFAULT_FIELDS)

    ods_map = options.get("ods") if isinstance(options.get("ods"), dict) else {}

    normalized_fields: list[dict[str, Any]] = []
    for key, label in PROFESSIONAL_FIELD_DEFS.items():
        meta = meta_map.get(key, {}) if isinstance(meta_map.get(key), dict) else {}
        if "selected" in meta:
            selected = bool(meta.get("selected"))
        else:
            selected = key in selected_keys
        display_label = meta.get("label") or label
        allow_ods = key in PROFESSIONAL_ODS_FIELDS

        if "ods_enabled" in meta:
            ods_enabled = bool(meta.get("ods_enabled"))
        elif "has_ods" in meta:
            ods_enabled = bool(meta.get("has_ods"))
        elif allow_ods and isinstance(ods_map, dict):
            ods_enabled = bool(ods_map.get(key))
        else:
            ods_enabled = bool(PROFESSIONAL_TEMPLATE_DEFAULT_ODS.get(key))

        if not selected or not allow_ods:
            ods_enabled = False

        field_entry = {
            "key": key,
            "label": display_label,
            "selected": bool(selected),
            "allow_ods": allow_ods,
            "ods_enabled": bool(ods_enabled),
        }
        # Legacy compatibility for template rendering code that still expects has_ods
        field_entry["has_ods"] = field_entry["allow_ods"] and field_entry["ods_enabled"]
        normalized_fields.append(field_entry)

    normalized_ods = {
        field["key"]: field["ods_enabled"]
        for field in normalized_fields
        if field["allow_ods"]
    }

    normalized: dict[str, Any] = {
        "template": template_key,
        "fields": normalized_fields,
        "ods": normalized_ods,
    }

    for key, value in options.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def _render_template_question_row(
    request: HttpRequest,
    survey: Survey,
    question: SurveyQuestion,
    *,
    group: QuestionGroup | None = None,
    keep_open: bool = False,
    message: str | None = None,
) -> HttpResponse:
    """Re-render a single question row after an HTMX update."""

    question.refresh_from_db()
    prepared = _prepare_question_rendering(survey, [question])
    if prepared:
        question = prepared[0]
    if question.type == SurveyQuestion.Types.TEMPLATE_PATIENT:
        question.options = _normalize_patient_template_options(question.options)
    elif question.type == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL:
        question.options = _normalize_professional_template_options(question.options)

    ctx: dict[str, Any] = {
        "q": question,
        "keep_template_panel_open": keep_open,
    }
    if message:
        ctx["row_message"] = message
    if group is not None:
        ctx["group"] = group
    else:
        ctx["groups"] = survey.question_groups.filter(owner=request.user)
    return render(request, "surveys/partials/question_row.html", ctx)


def _get_professional_group_and_fields(
    survey: Survey,
) -> tuple[QuestionGroup | None, list[str], dict[str, bool]]:
    """Return the Professional details group, selected fields, and ODS toggles map.

    Schema example:
    {"template": "professional_details", "fields": [...], "ods": {field: bool}}
    """
    group = survey.question_groups.filter(
        schema__template="professional_details"
    ).first()
    if not group:
        return None, [], {}
    raw = group.schema or {}
    sel = raw.get("fields") or []
    fields = [k for k in sel if k in PROFESSIONAL_FIELD_DEFS]
    ods_map = raw.get("ods") or {}
    # sanitize ods map to only allowed fields
    ods_clean = {k: bool(ods_map.get(k)) for k in PROFESSIONAL_ODS_FIELDS}
    return group, fields, ods_clean


def _survey_collects_patient_data(survey: Survey) -> bool:
    grp, fields = _get_patient_group_and_fields(survey)
    return bool(grp and fields)


def _verify_captcha(request: HttpRequest) -> bool:
    """Server-side hCaptcha verification.

    Expects POST token in 'h-captcha-response'. Uses settings.HCAPTCHA_SECRET.
    Returns True if verification passes or if not configured (fails closed only when required upstream).
    """
    secret = getattr(settings, "HCAPTCHA_SECRET", None)
    if not secret:
        # Not configured; treat as pass. Enforcement happens in views based on survey.captcha_required.
        return True
    token = request.POST.get("h-captcha-response")
    if not token:
        return False
    try:
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode(
            {
                "secret": secret,
                "response": token,
                "remoteip": request.META.get("REMOTE_ADDR", ""),
            }
        ).encode()
        req = urllib.request.Request("https://hcaptcha.com/siteverify", data=data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            import json as _json

            payload = _json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("success"))
    except Exception:
        return False


@login_required
def survey_list(request: HttpRequest) -> HttpResponse:
    # Creators/Viewers: only see surveys they created (owner)
    # Admins: see all surveys in their organization
    user = request.user
    surveys = Survey.objects.none()
    if user.is_authenticated:
        owned = Survey.objects.filter(owner=user)
        org_ids = user.org_memberships.values_list("organization_id", flat=True)  # type: ignore[attr-defined]
        if org_ids:
            org_surveys = Survey.objects.filter(organization_id__in=list(org_ids))
            # keep only those the user can view (admins of those orgs)
            org_surveys = [s for s in org_surveys if can_view_survey(user, s)]
            surveys = owned | Survey.objects.filter(id__in=[s.id for s in org_surveys])  # type: ignore[attr-defined]
        else:
            surveys = owned

    # Filter to only show original surveys (not translations)
    # Translations will be shown as sub-items under their originals
    original_surveys = surveys.filter(is_original=True)

    # Enrich surveys with translation data
    from .models import LANGUAGE_FLAGS, LANGUAGE_NAMES

    surveys_with_translations = []
    for survey in original_surveys:
        # Get all translations for this survey
        translations = survey.get_available_translations()
        translation_data = []
        for trans in translations:
            translation_data.append(
                {
                    "survey": trans,
                    "flag": LANGUAGE_FLAGS.get(trans.language, "🏳️"),
                    "language_name": LANGUAGE_NAMES.get(trans.language, trans.language),
                    "status": trans.status,
                }
            )

        surveys_with_translations.append(
            {
                "survey": survey,
                "translations": translation_data,
                "translation_count": len(translation_data),
                "flag": LANGUAGE_FLAGS.get(survey.language, "🏳️"),
                "language_name": LANGUAGE_NAMES.get(survey.language, survey.language),
            }
        )

    return render(
        request,
        "surveys/list.html",
        {
            "surveys": original_surveys,
            "surveys_with_translations": surveys_with_translations,
            "supported_languages": SUPPORTED_SURVEY_LANGUAGES,
            "language_flags": LANGUAGE_FLAGS,
        },
    )


class SurveyCreateForm(forms.ModelForm):
    slug = forms.SlugField(
        required=False, help_text="Leave blank to auto-generate from name"
    )

    # Encryption options
    ENCRYPTION_CHOICES = [
        ("none", "No encryption"),
        ("option2", "Password + Recovery Phrase encryption"),
    ]

    encryption_option = forms.ChoiceField(
        choices=ENCRYPTION_CHOICES,
        required=False,
        initial="none",
        widget=forms.RadioSelect,
        help_text="Choose encryption method for sensitive survey data",
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text="Password for unlocking encrypted survey data",
    )

    recovery_phrase = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="12-word recovery phrase as backup unlock method",
    )

    class Meta:
        model = Survey
        fields = ["name", "slug", "description"]

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if not name:
            raise forms.ValidationError("Name is required")
        return name

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        name = self.cleaned_data.get("name", "")

        # If slug is not provided, generate it from name
        if not slug and name:
            # Clean the name: remove brackets, apostrophes, and other non-alphanumeric chars
            import re

            cleaned_name = re.sub(
                r"[^\w\s-]", "", name
            )  # Remove special chars except spaces and hyphens
            slug = slugify(cleaned_name)

        # If still no slug after generation, raise error
        if not slug:
            raise forms.ValidationError("Could not generate slug from name")

        # Check for uniqueness
        if Survey.objects.filter(slug=slug).exists():
            raise forms.ValidationError("Slug already in use")

        return slug

    def clean(self):
        cleaned_data = super().clean()
        encryption_option = cleaned_data.get("encryption_option")
        password = cleaned_data.get("password")
        recovery_phrase = cleaned_data.get("recovery_phrase")

        if encryption_option == "option2":
            if not password:
                raise forms.ValidationError("Password is required for encryption")
            if not recovery_phrase:
                raise forms.ValidationError(
                    "Recovery phrase is required for encryption"
                )

            # Validate recovery phrase has 12 words
            words = recovery_phrase.strip().split()
            if len(words) != 12:
                raise forms.ValidationError("Recovery phrase must be exactly 12 words")

        return cleaned_data


@login_required
@require_http_methods(["GET", "POST"])
def survey_create(request: HttpRequest) -> HttpResponse:
    """
    Create a new survey with encryption support.

    Supports traditional dual-path encryption for all users.
    OIDC integration will be re-added after UserOIDC model integration is complete.
    """
    # Check tier limits for survey creation
    from checktick_app.core.tier_limits import check_survey_creation_limit

    can_create, reason = check_survey_creation_limit(request.user)
    if not can_create:
        messages.error(request, reason)
        return redirect("surveys:list")
    if request.method == "POST":
        form = SurveyCreateForm(request.POST)
        if form.is_valid():
            survey: Survey = form.save(commit=False)
            survey.owner = request.user

            # Handle traditional encryption if requested
            encryption_option = form.cleaned_data.get("encryption_option")

            if encryption_option == "option2":
                # Set up dual encryption
                password = form.cleaned_data.get("password")
                recovery_phrase = form.cleaned_data.get("recovery_phrase")

                if password and recovery_phrase:
                    try:
                        import os

                        survey_kek = os.urandom(32)

                        # Store hash for legacy API compatibility
                        from .utils import make_key_hash

                        digest, salt = make_key_hash(survey_kek)
                        survey.key_hash = digest
                        survey.key_salt = salt

                        # Save the survey first to get a primary key
                        survey.save()

                        # Set up dual encryption
                        recovery_words = recovery_phrase.strip().split()
                        survey.set_dual_encryption(survey_kek, password, recovery_words)

                        # Also set up OIDC encryption if user has OIDC authentication
                        if hasattr(request.user, "oidc"):
                            try:
                                survey.set_oidc_encryption(survey_kek, request.user)
                                logger.info(
                                    f"Added OIDC encryption for survey {survey.slug} (provider: {request.user.oidc.provider})"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to add OIDC encryption to survey {survey.slug}: {e}"
                                )
                                # Don't fail the entire survey creation if OIDC encryption fails

                        # Also set up organization encryption if user belongs to an organization
                        if (
                            survey.organization
                            and survey.organization.encrypted_master_key
                        ):
                            try:
                                survey.set_org_encryption(
                                    survey_kek, survey.organization
                                )
                                logger.info(
                                    f"Added organization encryption for survey {survey.slug} (org: {survey.organization.name})"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to add organization encryption to survey {survey.slug}: {e}"
                                )
                                # Don't fail the entire survey creation if org encryption fails

                        # Determine success message based on encryption methods
                        if hasattr(request.user, "oidc"):
                            provider_name = request.user.oidc.provider.title()
                            messages.success(
                                request,
                                f"Survey created with dual-path encryption + automatic {provider_name} unlock! "
                                "Keep your password and recovery phrase safe.",
                            )
                        else:
                            messages.success(
                                request,
                                "Survey created with dual-path encryption! "
                                "Keep your password and recovery phrase safe.",
                            )
                        return redirect("surveys:dashboard", slug=survey.slug)

                    except Exception as e:
                        logger.error(f"Failed to create encrypted survey: {e}")
                        messages.error(
                            request,
                            "Failed to set up encryption. Please check your password and recovery phrase.",
                        )
                        return render(request, "surveys/create.html", {"form": form})

            # No encryption or other options
            survey.save()
            return redirect("surveys:dashboard", slug=survey.slug)
    else:
        form = SurveyCreateForm()
    return render(request, "surveys/create.html", {"form": form})


@login_required
def survey_clone(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Clone an existing survey, creating a complete copy with all questions and settings.
    """
    # Get the source survey
    survey = get_object_or_404(Survey, slug=slug)

    # Check permissions - require edit access to clone
    require_can_edit(request.user, survey)

    try:
        # Create the clone using the model method
        cloned_survey = survey.create_clone()

        messages.success(
            request,
            f'Survey cloned successfully! The new survey "{cloned_survey.name}" has been created as a draft.',
        )
        return redirect("surveys:dashboard", slug=cloned_survey.slug)

    except Exception as e:
        logger.error(f"Failed to clone survey {slug}: {e}")
        messages.error(
            request, "Failed to clone survey. Please try again or contact support."
        )
        return redirect("surveys:list")


@login_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_detail(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    # Only authenticated users with view permission may access any survey
    require_can_view(request.user, survey)

    # Prevent the survey owner from submitting responses directly in the live view
    if request.user.is_authenticated and survey.owner_id == request.user.id:
        messages.info(
            request,
            "You are the owner. Use Groups to manage questions or Preview to see the participant view.",
        )
        return redirect("surveys:groups", slug=slug)

    # Determine demographics and professional configuration upfront
    patient_group, demographics_fields = _get_patient_group_and_fields(survey)
    prof_group, professional_fields, professional_ods = (
        _get_professional_group_and_fields(survey)
    )

    if request.method == "POST":
        answers = {}
        template_patient_payload: dict[str, str] = {}
        template_professional_payload: dict[str, str] = {}
        for q in survey.questions.all():
            key = f"q_{q.id}"
            if q.type == SurveyQuestion.Types.TEMPLATE_PATIENT:
                fields_meta = []
                opts = q.options or {}
                try:
                    fields_meta = opts.get("fields", []) if hasattr(opts, "get") else []
                except Exception:
                    fields_meta = []
                block: dict[str, str] = {}
                for field in fields_meta:
                    fkey = field.get("key") if isinstance(field, dict) else field
                    if not fkey:
                        continue
                    selected = True
                    if isinstance(field, dict) and "selected" in field:
                        selected = bool(field.get("selected"))
                    if not selected:
                        continue
                    val = request.POST.get(f"{key}_{fkey}")
                    if val:
                        block[str(fkey)] = val
                if block:
                    template_patient_payload.update(block)
                answers[str(q.id)] = {
                    "template": "patient_details_encrypted",
                    "fields": list(block.keys()),
                }
                continue
            if q.type == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL:
                fields_meta = []
                opts = q.options or {}
                try:
                    fields_meta = opts.get("fields", []) if hasattr(opts, "get") else []
                except Exception:
                    fields_meta = []
                block: dict[str, str] = {}
                for field in fields_meta:
                    fkey = field.get("key") if isinstance(field, dict) else field
                    if not fkey:
                        continue
                    selected = True
                    if isinstance(field, dict) and "selected" in field:
                        selected = bool(field.get("selected"))
                    if not selected:
                        continue
                    val = request.POST.get(f"{key}_{fkey}")
                    if val:
                        block[str(fkey)] = val
                    allow_ods = (
                        bool(field.get("allow_ods"))
                        if isinstance(field, dict)
                        else False
                    )
                    ods_enabled = (
                        bool(field.get("ods_enabled"))
                        if isinstance(field, dict)
                        else False
                    )
                    if allow_ods and ods_enabled:
                        ods_val = request.POST.get(f"{key}_{fkey}_ods")
                        if ods_val:
                            block[f"{fkey}_ods"] = ods_val
                if block:
                    template_professional_payload.update(block)
                answers[str(q.id)] = {
                    "template": "professional_details",
                    "fields": list(block.keys()),
                }
                continue
            value = (
                request.POST.getlist(key)
                if q.type in {"mc_multi", "orderable"}
                else request.POST.get(key)
            )
            answers[str(q.id)] = value

        # Collect professional details (non-encrypted)
        professional_payload = {**template_professional_payload}
        for field in professional_fields:
            val = request.POST.get(f"prof_{field}")
            if val:
                professional_payload[field] = val
            # Optional ODS code for certain fields
            if professional_ods.get(field):
                ods_val = request.POST.get(f"prof_{field}_ods")
                if ods_val:
                    professional_payload[f"{field}_ods"] = ods_val

        resp = SurveyResponse(
            survey=survey,
            answers={
                **answers,
                **(
                    {"professional": professional_payload}
                    if professional_payload
                    else {}
                ),
            },
            submitted_by=request.user if request.user.is_authenticated else None,
        )
        # Optionally store demographics if provided under special keys
        demo = {**template_patient_payload}
        for field in demographics_fields:
            val = request.POST.get(field)
            if val:
                demo[field] = val
        # Option 4: Re-derive KEK from stored credentials
        if demo:
            survey_key = get_survey_key_from_session(request, slug)
            if survey_key:
                resp.store_demographics(survey_key, demo)
        try:
            resp.save()
        except Exception:
            messages.error(request, "You have already submitted this survey.")
            return redirect("surveys:detail", slug=slug)

        messages.success(request, "Thank you for your response.")
        return redirect("surveys:detail", slug=slug)

    _prepare_question_rendering(survey)
    # Prepare ordered questions by group position, then by question order within group
    all_questions = list(
        survey.questions.select_related("group").prefetch_related("images").all()
    )
    qs = _order_questions_by_group(survey, all_questions)

    # Mark questions that have SHOW conditions (should be hidden by default)
    questions_with_show_conditions = set(
        SurveyQuestionCondition.objects.filter(
            target_question__survey=survey, action=SurveyQuestionCondition.Action.SHOW
        ).values_list("target_question_id", flat=True)
    )

    for i, q in enumerate(qs, start=1):
        setattr(q, "idx", i)
        prev_gid = qs[i - 2].group_id if i - 2 >= 0 else None
        next_gid = qs[i].group_id if i < len(qs) else None
        curr_gid = q.group_id
        setattr(q, "group_start", bool(curr_gid and curr_gid != prev_gid))
        setattr(q, "group_end", bool(curr_gid and curr_gid != next_gid))
        setattr(q, "has_show_condition", q.id in questions_with_show_conditions)
    has_patient_template = any(
        getattr(q, "type", None) == SurveyQuestion.Types.TEMPLATE_PATIENT for q in qs
    )
    has_professional_template = any(
        getattr(q, "type", None) == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL
        for q in qs
    )
    show_patient_details = patient_group is not None and not has_patient_template
    show_professional_details = prof_group is not None and not has_professional_template
    # Style overrides
    style = survey.style or {}
    brand_overrides = {
        "title": style.get("title"),
        "icon_url": style.get("icon_url"),
        "theme_name": style.get("theme_name"),
        "font_heading": style.get("font_heading"),
        "font_body": style.get("font_body"),
        "primary_hex": style.get("primary_color"),
        "font_css_url": style.get("font_css_url"),
    }

    # Build branching configuration for client-side logic
    branching_config = _build_branching_config(qs)

    ctx = {
        "survey": survey,
        "questions": qs,
        "branching_config": json.dumps(branching_config),
        "show_patient_details": show_patient_details,
        "demographics_fields": demographics_fields,
        "demographic_defs": DEMOGRAPHIC_FIELD_DEFS,
        "demographics_fields_with_labels": [
            (k, DEMOGRAPHIC_FIELD_DEFS[k]) for k in demographics_fields
        ],
        "show_professional_details": show_professional_details,
        "professional_fields": professional_fields,
        "professional_defs": PROFESSIONAL_FIELD_DEFS,
        "professional_ods": professional_ods,
        "professional_field_datasets": PROFESSIONAL_FIELD_TO_DATASET,
    }
    if any(
        v for k, v in brand_overrides.items() if k != "primary_hex"
    ) or brand_overrides.get("primary_hex"):
        # Only override if any per-survey style is set; otherwise use context processor defaults
        ctx["brand"] = {
            "title": brand_overrides.get("title")
            or getattr(settings, "BRAND_TITLE", "CheckTick"),
            "icon_url": brand_overrides.get("icon_url")
            or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
            "theme_name": brand_overrides.get("theme_name")
            or getattr(settings, "BRAND_THEME", "checktick"),
            "font_heading": brand_overrides.get("font_heading")
            or getattr(
                settings,
                "BRAND_FONT_HEADING",
                "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
            ),
            "font_body": brand_overrides.get("font_body")
            or getattr(
                settings,
                "BRAND_FONT_BODY",
                "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            ),
            "font_css_url": brand_overrides.get("font_css_url")
            or getattr(
                settings,
                "BRAND_FONT_CSS_URL",
                "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
            ),
            "primary": hex_to_oklch(brand_overrides.get("primary_hex") or ""),
        }
    return render(
        request,
        "surveys/detail.html",
        ctx,
    )


@login_required
@require_http_methods(["GET", "POST"])
def survey_preview(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)

    # Handle POST in preview mode - redirect to preview thank you without saving
    if request.method == "POST":
        return redirect("surveys:preview_thank_you", slug=slug)

    # Render the same detail template in preview mode
    _prepare_question_rendering(survey)
    all_questions = list(
        survey.questions.select_related("group").prefetch_related("images").all()
    )
    qs = _order_questions_by_group(survey, all_questions)

    # Mark questions that have SHOW conditions (should be hidden by default)
    questions_with_show_conditions = set(
        SurveyQuestionCondition.objects.filter(
            target_question__survey=survey, action=SurveyQuestionCondition.Action.SHOW
        ).values_list("target_question_id", flat=True)
    )

    for i, q in enumerate(qs, start=1):
        setattr(q, "idx", i)
        prev_gid = qs[i - 2].group_id if i - 2 >= 0 else None
        next_gid = qs[i].group_id if i < len(qs) else None
        curr_gid = q.group_id
        setattr(q, "group_start", bool(curr_gid and curr_gid != prev_gid))
        setattr(q, "group_end", bool(curr_gid and curr_gid != next_gid))
        setattr(q, "has_show_condition", q.id in questions_with_show_conditions)
    patient_group, demographics_fields = _get_patient_group_and_fields(survey)
    prof_group, professional_fields, professional_ods = (
        _get_professional_group_and_fields(survey)
    )
    show_patient_details = patient_group is not None
    show_professional_details = prof_group is not None
    style = survey.style or {}
    brand_overrides = {
        "title": style.get("title"),
        "icon_url": style.get("icon_url"),
        "theme_name": style.get("theme_name"),
        "font_heading": style.get("font_heading"),
        "font_body": style.get("font_body"),
        "primary_hex": style.get("primary_color"),
        "font_css_url": style.get("font_css_url"),
    }

    # Build branching configuration for client-side logic
    branching_config = _build_branching_config(qs)

    ctx = {
        "survey": survey,
        "questions": qs,
        "branching_config": json.dumps(branching_config),
        "show_patient_details": show_patient_details,
        "demographics_fields": demographics_fields,
        "demographic_defs": DEMOGRAPHIC_FIELD_DEFS,
        "demographics_fields_with_labels": [
            (k, DEMOGRAPHIC_FIELD_DEFS[k]) for k in demographics_fields
        ],
        "show_professional_details": show_professional_details,
        "professional_fields": professional_fields,
        "professional_defs": PROFESSIONAL_FIELD_DEFS,
        "professional_ods": professional_ods,
        "professional_field_datasets": PROFESSIONAL_FIELD_TO_DATASET,
        "is_preview": True,  # Flag to indicate this is preview mode
    }
    if any(
        v for k, v in brand_overrides.items() if k != "primary_hex"
    ) or brand_overrides.get("primary_hex"):
        ctx["brand"] = {
            "title": brand_overrides.get("title")
            or getattr(settings, "BRAND_TITLE", "CheckTick"),
            "icon_url": brand_overrides.get("icon_url")
            or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
            "theme_name": brand_overrides.get("theme_name")
            or getattr(settings, "BRAND_THEME", "checktick"),
            "font_heading": brand_overrides.get("font_heading")
            or getattr(
                settings,
                "BRAND_FONT_HEADING",
                "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
            ),
            "font_body": brand_overrides.get("font_body")
            or getattr(
                settings,
                "BRAND_FONT_BODY",
                "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            ),
            "font_css_url": brand_overrides.get("font_css_url")
            or getattr(
                settings,
                "BRAND_FONT_CSS_URL",
                "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
            ),
            "primary": hex_to_oklch(brand_overrides.get("primary_hex") or ""),
        }
    return render(
        request,
        "surveys/detail.html",
        ctx,
    )


def _prefetch_conditions(
    qs: QuerySet[SurveyQuestion],
) -> QuerySet[SurveyQuestion]:
    try:
        return qs.prefetch_related(
            "conditions__target_question",
        )
    except DatabaseError as exc:  # pragma: no cover - exercised via tests
        logger.warning("Skipping condition prefetch due to database error: %s", exc)
        return qs


def _load_conditions(question: SurveyQuestion) -> list[SurveyQuestionCondition]:
    try:
        return list(question.conditions.all())
    except DatabaseError as exc:  # pragma: no cover - exercised via tests
        logger.warning(
            "Skipping condition load for question %s due to database error: %s",
            question.id,
            exc,
        )
        return []


def _build_branching_config(questions: list[SurveyQuestion]) -> dict[str, Any]:
    """
    Build JavaScript-friendly configuration for client-side branching logic.

    Returns a dictionary that will be JSON-serialized for the frontend:
    {
        "questions": [question_ids in order],
        "conditions": {question_id: [conditions]},
        "show_conditions": {question_id: [incoming SHOW conditions]}
    }
    """
    config: dict[str, Any] = {"questions": [], "conditions": {}, "show_conditions": {}}

    for q in questions:
        q_id = str(q.id)
        config["questions"].append(q_id)

        # Get outgoing conditions from this question
        try:
            conditions = list(q.conditions.all())
        except Exception:
            conditions = []

        if conditions:
            config["conditions"][q_id] = []
            for cond in conditions:
                cond_data = {
                    "operator": cond.operator,
                    "value": cond.value or "",
                    "action": cond.action,
                    "target_question": (
                        str(cond.target_question.id) if cond.target_question else None
                    ),
                }
                config["conditions"][q_id].append(cond_data)

    # Build show_conditions map (incoming SHOW conditions)
    for q in questions:
        q_id = str(q.id)
        try:
            show_conditions = SurveyQuestionCondition.objects.filter(
                target_question=q, action=SurveyQuestionCondition.Action.SHOW
            ).select_related("question")

            if show_conditions.exists():
                config["show_conditions"][q_id] = []
                for cond in show_conditions:
                    cond_data = {
                        "source_question": str(cond.question.id),
                        "operator": cond.operator,
                        "value": cond.value or "",
                    }
                    config["show_conditions"][q_id].append(cond_data)
        except Exception:
            pass

    return config


def _order_questions_by_group(
    survey: Survey, questions: list[SurveyQuestion]
) -> list[SurveyQuestion]:
    """Order questions by group position (from survey.style['group_order']), then by question.order within each group.

    This ensures that when groups are reordered via drag-and-drop, questions appear in the correct sequence
    without breaking question-to-question branching logic.
    """
    style = survey.style or {}
    group_order = style.get("group_order", [])

    # Separate questions by group
    grouped_questions: dict[int | None, list[SurveyQuestion]] = {}
    ungrouped_questions: list[SurveyQuestion] = []

    for q in questions:
        if q.group_id:
            grouped_questions.setdefault(q.group_id, []).append(q)
        else:
            ungrouped_questions.append(q)

    # Sort questions within each group by their order field
    for group_id in grouped_questions:
        grouped_questions[group_id].sort(key=lambda q: (q.order, q.id))

    # Build final ordered list
    ordered = []

    # Add groups in their specified order
    for gid in group_order:
        gid = int(gid) if str(gid).isdigit() else None
        if gid and gid in grouped_questions:
            ordered.extend(grouped_questions[gid])
            del grouped_questions[gid]

    # Add any remaining groups not in group_order (sorted by group_id)
    for gid in sorted(grouped_questions.keys()):
        ordered.extend(grouped_questions[gid])

    # Add ungrouped questions at the end, sorted by order
    ungrouped_questions.sort(key=lambda q: (q.order, q.id))
    ordered.extend(ungrouped_questions)

    return ordered


def _prepare_question_rendering(
    survey: Survey, questions: Iterable[SurveyQuestion] | None = None
) -> list[SurveyQuestion]:
    """Attach view helper attributes used by the builder templates.

    Currently sets ``num_scale_values`` for likert questions, along with
    ``builder_payload`` and ``builder_payload_json`` that power the client-side
    editor. Returns the processed sequence so callers can reuse the prepared
    objects.
    """

    questions_iter: list[SurveyQuestion] = []
    try:
        if questions is None:
            base_qs = survey.questions.select_related("group").all()
            questions_iter = list(_prefetch_conditions(base_qs))
        elif isinstance(questions, QuerySet):
            base_qs = questions.select_related("group")
            questions_iter = list(_prefetch_conditions(base_qs))
        else:
            questions_iter = [q for q in questions if isinstance(q, SurveyQuestion)]
            ids = [q.id for q in questions_iter if q.id is not None]
            if ids:
                hydrated_qs = survey.questions.select_related("group").filter(
                    id__in=ids
                )
                hydrated_qs = _prefetch_conditions(hydrated_qs)
                hydrated = {q.id: q for q in hydrated_qs}
                questions_iter = [hydrated.get(q.id, q) for q in questions_iter]
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Falling back to raw question list: %s", exc)
        if questions is None:
            questions_iter = list(survey.questions.select_related("group"))
        elif isinstance(questions, QuerySet):
            questions_iter = list(questions)
        else:
            questions_iter = [q for q in questions if isinstance(q, SurveyQuestion)]

    all_questions_meta: list[dict[str, Any]] = []
    try:
        for item in (
            survey.questions.select_related("group")
            .only("id", "text", "order", "group__name")
            .all()
        ):
            text = (item.text or "Untitled question").strip() or "Untitled question"
            order_display = item.order + 1 if item.order is not None else None
            prefix = f"Q{order_display}" if order_display else f"ID {item.id}"
            group_name = item.group.name if getattr(item, "group", None) else ""
            label = f"{prefix} • {text}"
            if group_name:
                label = f"{label} ({group_name})"
            all_questions_meta.append(
                {
                    "id": item.id,
                    "order": item.order,
                    "label": label,
                    "group_id": item.group_id,
                    "group_name": group_name,
                }
            )
    except Exception:
        all_questions_meta = []

    all_groups_meta: list[dict[str, Any]] = []
    try:
        for grp in survey.question_groups.only("id", "name").all():
            all_groups_meta.append(
                {"id": grp.id, "label": grp.name or f"Group {grp.id}"}
            )
    except Exception:
        all_groups_meta = []

    operators_meta = [
        {
            "value": value,
            "label": label,
            "requires_value": value in CONDITION_OPERATORS_REQUIRING_VALUE,
        }
        for value, label in SurveyQuestionCondition.Operator.choices
    ]
    actions_meta = [
        {
            "value": value,
            "label": label,
        }
        for value, label in SurveyQuestionCondition.Action.choices
    ]
    condition_meta = {
        "operators": operators_meta,
        "actions": actions_meta,
    }

    for q in questions_iter:
        try:
            if q.type == SurveyQuestion.Types.TEMPLATE_PATIENT:
                q.options = _normalize_patient_template_options(q.options)
            elif q.type == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL:
                q.options = _normalize_professional_template_options(q.options)
            if (
                q.type == "likert"
                and isinstance(q.options, list)
                and q.options
                and isinstance(q.options[0], dict)
                and q.options[0].get("type") == "number-scale"
            ):
                meta = q.options[0]
                minv = int(meta.get("min", 1))
                maxv = int(meta.get("max", 5))
                if maxv < minv:
                    minv, maxv = maxv, minv
                setattr(q, "num_scale_values", list(range(minv, maxv + 1)))
            else:
                setattr(q, "num_scale_values", None)
            payload = _serialize_question_for_builder(
                q,
                all_questions=all_questions_meta,
                all_groups=all_groups_meta,
                condition_meta=condition_meta,
            )
            setattr(q, "builder_payload", payload)
            try:
                payload_json = json.dumps(payload, separators=(",", ":"))
            except TypeError:
                payload_json = "null"
            setattr(q, "builder_payload_json", payload_json)
        except Exception:
            setattr(q, "num_scale_values", None)
            setattr(q, "builder_payload", {})
            setattr(q, "builder_payload_json", "null")
    return questions_iter


def _parse_builder_question_form(data: QueryDict) -> dict[str, Any]:
    text = (data.get("text") or "").strip()
    qtype = (data.get("type") or SurveyQuestion.Types.TEXT).strip()
    if not qtype:
        qtype = SurveyQuestion.Types.TEXT
    required = (data.get("required") or "").lower() in {"on", "true", "1", "yes"}

    options: Any = []
    if qtype in {
        SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        SurveyQuestion.Types.MULTIPLE_CHOICE_MULTI,
        SurveyQuestion.Types.DROPDOWN,
        SurveyQuestion.Types.ORDERABLE,
        SurveyQuestion.Types.IMAGE_CHOICE,
    }:
        raw = data.get("options", "")
        option_lines = [line.strip() for line in raw.splitlines() if line.strip()]

        # Parse follow-up text configuration for each option
        # Format: option_N_followup=on, option_N_followup_label="custom label"
        options = []
        for idx, opt_text in enumerate(option_lines):
            opt_dict: dict[str, Any] = {"label": opt_text, "value": opt_text}

            # Check if this option should have a follow-up text input
            followup_key = f"option_{idx}_followup"
            followup_label_key = f"option_{idx}_followup_label"

            if data.get(followup_key) in {"on", "true", "1", "yes"}:
                followup_label = (data.get(followup_label_key) or "").strip()
                if not followup_label:
                    followup_label = f"Please elaborate on '{opt_text}'"
                opt_dict["followup_text"] = {"enabled": True, "label": followup_label}

            options.append(opt_dict)

        # Prefilled dataset handling is now done via dataset_key return value
        # Options remain as list for compatibility
    elif qtype == SurveyQuestion.Types.YESNO:
        # For Yes/No questions, check if either option should have follow-up text
        options = [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]

        for idx, opt in enumerate(options):
            followup_key = f"yesno_{opt['value']}_followup"
            followup_label_key = f"yesno_{opt['value']}_followup_label"

            if data.get(followup_key) in {"on", "true", "1", "yes"}:
                followup_label = (data.get(followup_label_key) or "").strip()
                if not followup_label:
                    followup_label = "Please elaborate"
                opt["followup_text"] = {"enabled": True, "label": followup_label}
    elif qtype == SurveyQuestion.Types.LIKERT:
        likert_mode = (data.get("likert_mode") or "categories").strip()
        if likert_mode == "number":
            try:
                min_v = int(data.get("likert_min", "1"))
            except (TypeError, ValueError):
                min_v = 1
            try:
                max_v = int(data.get("likert_max", "5"))
            except (TypeError, ValueError):
                max_v = 5
            options = [
                {
                    "type": "number-scale",
                    "min": min_v,
                    "max": max_v,
                    "left": (data.get("likert_left_label") or "").strip(),
                    "right": (data.get("likert_right_label") or "").strip(),
                }
            ]
        else:
            raw = data.get("likert_categories", "")
            options = [line.strip() for line in raw.splitlines() if line.strip()]
    elif qtype == SurveyQuestion.Types.TEXT:
        text_format = (data.get("text_format") or "free").strip()
        if text_format not in {"number", "free"}:
            text_format = "free"
        options = [{"type": "text", "format": text_format}]
    else:
        options = []

    # Extract dataset key for dropdown questions
    dataset_key = None
    if qtype == SurveyQuestion.Types.DROPDOWN:
        dataset_key = (data.get("prefilled_dataset") or "").strip() or None

    return {
        "text": text,
        "type": qtype,
        "required": required,
        "options": options,
        "dataset_key": dataset_key,
    }


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _build_condition_payload(
    survey: Survey,
    question: SurveyQuestion,
    data: QueryDict,
    *,
    instance: SurveyQuestionCondition | None = None,
) -> dict[str, Any]:
    operator = (data.get("operator") or "").strip() or (
        instance.operator if instance else SurveyQuestionCondition.Operator.EQUALS
    )
    if operator not in SurveyQuestionCondition.Operator.values:
        operator = SurveyQuestionCondition.Operator.EQUALS

    action = (data.get("action") or "").strip() or (
        instance.action if instance else SurveyQuestionCondition.Action.JUMP_TO
    )
    if action not in SurveyQuestionCondition.Action.values:
        action = SurveyQuestionCondition.Action.JUMP_TO

    description = (data.get("description") or "").strip()
    if not description and instance and instance.description:
        description = instance.description

    value = data.get("value")
    if value is None and instance is not None:
        value = instance.value
    else:
        value = (value or "").strip()

    order_raw = data.get("order")
    order = _safe_int(order_raw)
    if order is None:
        order = instance.order if instance else None
    if order is None:
        next_order = (
            question.conditions.aggregate(models.Max("order")).get("order__max") or -1
        ) + 1
        order = next_order

    target_question: SurveyQuestion | None = None
    target_question_raw = data.get("target_question")

    # Allow END_SURVEY without target
    if action == "end_survey":
        target_question = None
    elif target_question_raw:
        target_question_id = _safe_int(target_question_raw)
        if target_question_id is None:
            raise ValidationError({"target_question": "Invalid target question."})
        try:
            target_question = SurveyQuestion.objects.get(
                id=target_question_id, survey=survey
            )
        except SurveyQuestion.DoesNotExist as exc:
            raise ValidationError(
                {"target_question": "Target question must belong to this survey."}
            ) from exc
    elif instance:
        target_question = instance.target_question
    else:
        raise ValidationError(
            {
                "target_question": "Target question is required (unless action is END_SURVEY).",
            }
        )

    return {
        "operator": operator,
        "action": action,
        "description": description,
        "value": value or "",
        "order": order,
        "target_question": target_question,
    }


def _duplicate_question(question: SurveyQuestion) -> SurveyQuestion:
    """Clone a question immediately after the original within the survey order."""
    order = question.order
    with transaction.atomic():
        SurveyQuestion.objects.filter(survey=question.survey, order__gt=order).update(
            order=models.F("order") + 1
        )
        cloned = SurveyQuestion.objects.create(
            survey=question.survey,
            group=question.group,
            text=question.text,
            type=question.type,
            options=deepcopy(question.options),
            required=question.required,
            order=order + 1,
        )
    return cloned


def _serialize_question_for_builder(
    question: SurveyQuestion,
    *,
    all_questions: Iterable[dict[str, Any]] | None = None,
    all_groups: Iterable[dict[str, Any]] | None = None,
    condition_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": question.id,
        "text": question.text or "",
        "type": question.type,
        "required": bool(question.required),
        "group_id": question.group_id,
        "survey_slug": question.survey.slug if hasattr(question, "survey") else None,
    }

    options = question.options or []
    if question.type == SurveyQuestion.Types.TEXT:
        fmt = "free"
        if isinstance(options, list) and options and isinstance(options[0], dict):
            fmt = str(options[0].get("format") or fmt)
        payload["text_format"] = fmt
    elif question.type in {
        SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        SurveyQuestion.Types.MULTIPLE_CHOICE_MULTI,
        SurveyQuestion.Types.DROPDOWN,
        SurveyQuestion.Types.ORDERABLE,
        SurveyQuestion.Types.IMAGE_CHOICE,
    }:
        values: list[str] = []
        option_followup_config: dict[str, dict[str, Any]] = {}
        prefilled_dataset: str | None = None

        # Check if options is a prefilled dataset dict
        if isinstance(options, dict) and options.get("type") == "prefilled":
            prefilled_dataset = options.get("dataset_key")
            option_values = options.get("values", [])
            if isinstance(option_values, list):
                for idx, opt in enumerate(option_values):
                    if isinstance(opt, str):
                        val = opt.strip()
                        if val:
                            values.append(val)
                    elif isinstance(opt, dict):
                        label = opt.get("label", "").strip()
                        if label:
                            values.append(label)
                        # Check for follow-up text configuration
                        if opt.get("followup_text") and opt["followup_text"].get(
                            "enabled"
                        ):
                            option_followup_config[str(idx)] = {
                                "label": opt["followup_text"].get(
                                    "label", "Please elaborate"
                                )
                            }
        elif isinstance(options, list):
            for idx, opt in enumerate(options):
                if isinstance(opt, str):
                    val = opt.strip()
                    if val:
                        values.append(val)
                elif isinstance(opt, dict):
                    candidate = opt.get("label") or opt.get("value")
                    if candidate:
                        values.append(str(candidate).strip())
                    # Check for follow-up text configuration
                    if opt.get("followup_text") and opt["followup_text"].get("enabled"):
                        option_followup_config[str(idx)] = {
                            "label": opt["followup_text"].get(
                                "label", "Please elaborate"
                            )
                        }

        payload["options"] = values
        if option_followup_config:
            payload["followup_config"] = option_followup_config
        # Include dataset key if linked to a dataset
        if question.dataset:
            payload["prefilled_dataset"] = question.dataset.key
        elif prefilled_dataset:
            # Backward compatibility for old metadata format
            payload["prefilled_dataset"] = prefilled_dataset

        # For image questions, include the uploaded images
        if question.type == SurveyQuestion.Types.IMAGE_CHOICE:
            images_data = []
            try:
                for img in question.images.all():
                    images_data.append(
                        {
                            "id": img.id,
                            "url": img.url,
                            "label": img.label or "",
                            "order": img.order,
                        }
                    )
            except Exception:
                pass
            payload["images"] = images_data
    elif question.type == SurveyQuestion.Types.YESNO:
        # For Yes/No questions, check for follow-up text config
        yesno_followup_config: dict[str, dict[str, Any]] = {}
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict):
                    value = opt.get("value")
                    if (
                        value in ("yes", "no")
                        and opt.get("followup_text")
                        and opt["followup_text"].get("enabled")
                    ):
                        yesno_followup_config[value] = {
                            "label": opt["followup_text"].get(
                                "label", "Please elaborate"
                            )
                        }
        if yesno_followup_config:
            payload["yesno_followup_config"] = yesno_followup_config
    elif question.type == SurveyQuestion.Types.LIKERT:
        if (
            isinstance(options, list)
            and options
            and isinstance(options[0], dict)
            and options[0].get("type") == "number-scale"
        ):
            meta = options[0]
            payload["likert_mode"] = "number"
            try:
                payload["likert_min"] = int(meta.get("min", 1))
            except (TypeError, ValueError):
                payload["likert_min"] = 1
            try:
                payload["likert_max"] = int(meta.get("max", 5))
            except (TypeError, ValueError):
                payload["likert_max"] = 5
            payload["likert_left_label"] = str(meta.get("left") or "").strip()
            payload["likert_right_label"] = str(meta.get("right") or "").strip()
        else:
            payload["likert_mode"] = "categories"
            labels: list[str] = []
            if isinstance(options, list):
                for opt in options:
                    if isinstance(opt, str):
                        val = opt.strip()
                        if val:
                            labels.append(val)
                    elif isinstance(opt, dict):
                        candidate = opt.get("label") or opt.get("value")
                        if candidate:
                            labels.append(str(candidate).strip())
            payload["likert_categories"] = labels

    operators_meta = list((condition_meta or {}).get("operators", []))
    if not operators_meta:
        operators_meta = [
            {
                "value": value,
                "label": label,
                "requires_value": value in CONDITION_OPERATORS_REQUIRING_VALUE,
            }
            for value, label in SurveyQuestionCondition.Operator.choices
        ]
    actions_meta = list((condition_meta or {}).get("actions", []))
    if not actions_meta:
        actions_meta = [
            {
                "value": value,
                "label": label,
            }
            for value, label in SurveyQuestionCondition.Action.choices
        ]

    target_questions: list[dict[str, Any]] = []
    default_question_id: int | None = None
    if all_questions:
        for meta in all_questions:
            if meta.get("id") == question.id:
                continue
            entry = {
                "id": meta.get("id"),
                "label": meta.get("label") or f"Question {meta.get('id')}",
                "group_id": meta.get("group_id"),
                "group_name": meta.get("group_name"),
            }
            target_questions.append(entry)
            if default_question_id is None and entry.get("id") is not None:
                default_question_id = int(entry["id"])

    has_question_targets = bool(target_questions)

    payload["condition_options"] = {
        "operators": operators_meta,
        "actions": actions_meta,
        "target_questions": target_questions,
        "has_question_targets": has_question_targets,
        "default_question_id": default_question_id,
        "can_create": has_question_targets,
    }

    conditions_payload: list[dict[str, Any]] = []
    for cond in _load_conditions(question):
        target_type = "question"
        target_label = ""
        target_id: int | None = None
        if cond.target_question is not None:
            target_id = cond.target_question.id
            target_label = (
                cond.target_question.text or f"Question {target_id}"
            ).strip()

        if cond.operator in CONDITION_OPERATORS_REQUIRING_VALUE:
            comparison = cond.value or ""
            condition_clause = f'{cond.get_operator_display()} "{comparison}"'.strip()
        else:
            condition_clause = cond.get_operator_display()
        summary = (
            f"{condition_clause} → {cond.get_action_display()} {target_label}".strip()
        )

        conditions_payload.append(
            {
                "id": cond.id,
                "operator": cond.operator,
                "operator_label": cond.get_operator_display(),
                "action": cond.action,
                "action_label": cond.get_action_display(),
                "value": cond.value or "",
                "description": cond.description or "",
                "order": cond.order,
                "target": {
                    "type": target_type,
                    "id": target_id,
                    "label": target_label,
                },
                "summary": summary,
                "requires_value": cond.operator in CONDITION_OPERATORS_REQUIRING_VALUE,
            }
        )

    payload["conditions"] = conditions_payload

    return payload


@login_required
def survey_dashboard(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)
    total = survey.responses.count()
    # Simple analytics
    now = timezone.now()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last7 = now - timezone.timedelta(days=7)
    today_count = survey.responses.filter(submitted_at__gte=start_today).count()
    last7_count = survey.responses.filter(submitted_at__gte=last7).count()
    # Sparkline data: last 14 full days (oldest -> newest)
    from collections import OrderedDict

    spark_points = ""
    spark_labels = []
    invites_points = ""
    survey_not_started = survey.start_at and survey.start_at > now

    if not survey_not_started:
        # Show from publication date (or last 14 days, whichever is more recent)
        # This gives a complete picture of the survey's lifetime submissions
        if survey.start_at:
            # Use the survey's publication start date
            survey_start_day = survey.start_at.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start_date = survey_start_day
        else:
            # No start date specified - show last 14 days as fallback
            start_date = start_today - timezone.timedelta(days=13)

        # Ensure we always show at least 2 days for a proper line graph
        if start_date == start_today:
            start_date = start_today - timezone.timedelta(days=1)

        day_counts = OrderedDict()
        current_day = start_date
        # Always include at least up to and including today
        end_day = start_today + timezone.timedelta(days=1)
        # Also build invites-per-day alongside response counts so we can
        # render both series in the sparkline.
        invite_day_counts = OrderedDict()
        while current_day < end_day:
            next_day = current_day + timezone.timedelta(days=1)
            day_counts[current_day.date().isoformat()] = survey.responses.filter(
                submitted_at__gte=current_day, submitted_at__lt=next_day
            ).count()
            invite_day_counts[current_day.date().isoformat()] = (
                survey.access_tokens.filter(
                    created_at__gte=current_day,
                    created_at__lt=next_day,
                    note__icontains="Invited",
                ).count()
            )
            current_day = next_day

        # Build sparkline polyline points (0..100 width, 0..24 height)
        response_values = list(day_counts.values())
        invite_values = list(invite_day_counts.values())
        dates = list(day_counts.keys())

        if response_values or invite_values:  # Create sparkline even if all zeros
            # Use combined max so both series share the same vertical scale
            max_v = max(
                max(response_values) if response_values else 0,
                max(invite_values) if invite_values else 0,
            )
            max_v = max_v if max_v > 0 else 1
            n = len(dates)
            width = 100.0
            height = 24.0
            dx = width / (n - 1) if n > 1 else width

            # Response series (primary)
            resp_pts = []
            for i, v in enumerate(response_values):
                x = dx * i
                y = height - (float(v) / float(max_v)) * height
                resp_pts.append(f"{x:.1f},{y:.1f}")
            spark_points = " ".join(resp_pts)

            # Invite series (secondary)
            invite_pts = []
            for i, v in enumerate(invite_values):
                x = dx * i
                y = height - (float(v) / float(max_v)) * height
                invite_pts.append(f"{x:.1f},{y:.1f}")
            invites_points = " ".join(invite_pts)

            # Create labels for axis
            if n > 0:
                spark_labels = [
                    {"date": dates[0], "label": "Start"},
                    {"date": dates[-1], "label": "Today"},
                    {"max_count": max_v},
                ]
    # Derived status
    is_live = survey.is_live()
    visible = (
        survey.get_visibility_display()
        if hasattr(survey, "get_visibility_display")
        else "Authenticated"
    )
    groups = (
        survey.question_groups.filter(owner=request.user)
        .annotate(
            q_count=models.Count(
                "surveyquestion", filter=models.Q(surveyquestion__survey=survey)
            )
        )
        .order_by("name")
    )
    # Per-survey style overrides for branding on dashboard
    style = survey.style or {}
    brand_overrides = {
        "title": style.get("title"),
        "icon_url": style.get("icon_url"),
        "theme_name": style.get("theme_name"),
        "font_heading": style.get("font_heading"),
        "font_body": style.get("font_body"),
        "primary_hex": style.get("primary_color"),
        "font_css_url": style.get("font_css_url"),
    }
    ctx = {
        "survey": survey,
        "total": total,
        "groups": groups,
        "is_live": is_live,
        "visible": visible,
        "today_count": today_count,
        "last7_count": last7_count,
        "spark_points": spark_points,
        "spark_labels": spark_labels,
        # Invites stats
        "invites_sent": survey.access_tokens.filter(note__icontains="Invited").count(),
        "invites_pending": survey.access_tokens.filter(
            note__icontains="Invited", response__isnull=True
        ).count(),
        "invites_points": invites_points,
        "survey_not_started": survey_not_started,
        "can_manage_users": can_manage_survey_users(request.user, survey),
        # Data governance
        "can_export": (
            survey.is_closed and can_export_survey_data(request.user, survey)
        ),
        # Check if survey has any questions for signposting
        "has_questions": survey.question_groups.filter(
            surveyquestion__survey=survey
        ).exists(),
        # Translation management
        "available_translations": survey.get_available_translations(),
        "supported_languages": SUPPORTED_SURVEY_LANGUAGES,
    }

    # Import language constants for flags
    from .models import LANGUAGE_FLAGS

    ctx["language_flags"] = LANGUAGE_FLAGS

    if any(
        v for k, v in brand_overrides.items() if k != "primary_hex"
    ) or brand_overrides.get("primary_hex"):
        ctx["brand"] = {
            "title": brand_overrides.get("title")
            or getattr(settings, "BRAND_TITLE", "CheckTick"),
            "icon_url": brand_overrides.get("icon_url")
            or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
            "theme_name": brand_overrides.get("theme_name")
            or getattr(settings, "BRAND_THEME", "checktick"),
            "font_heading": brand_overrides.get("font_heading")
            or getattr(
                settings,
                "BRAND_FONT_HEADING",
                "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
            ),
            "font_body": brand_overrides.get("font_body")
            or getattr(
                settings,
                "BRAND_FONT_BODY",
                "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            ),
            "font_css_url": brand_overrides.get("font_css_url")
            or getattr(
                settings,
                "BRAND_FONT_CSS_URL",
                "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
            ),
            "primary": hex_to_oklch(brand_overrides.get("primary_hex") or ""),
        }
    return render(request, "surveys/dashboard.html", ctx)


@login_required
@require_http_methods(["POST"])
def update_survey_title(request: HttpRequest, slug: str) -> JsonResponse:
    """Update the title/name of a survey via AJAX."""
    try:
        survey = get_object_or_404(Survey, slug=slug)
        require_can_edit(request.user, survey)

        data = json.loads(request.body)
        new_title = data.get("title", "").strip()

        if not new_title:
            return JsonResponse({"success": False, "error": "Title cannot be empty"})

        survey.name = new_title
        survey.save(update_fields=["name"])

        return JsonResponse({"success": True})
    except PermissionDenied as e:
        return JsonResponse({"success": False, "error": str(e)}, status=403)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def survey_invites_pending(request: HttpRequest, slug: str) -> HttpResponse:
    """List invited email addresses that have not yet submitted a response.

    This shows tokens created via the invite workflow where there is no
    associated response yet.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)

    tokens = survey.access_tokens.filter(
        note__icontains="Invited", response__isnull=True
    ).order_by("-created_at")

    invites = []
    for t in tokens:
        # Note format used when creating invites: 'Invited: email@domain'
        email = None
        if t.note and ":" in t.note:
            email = t.note.split(":", 1)[1].strip()
        invites.append({"token": t, "email": email or t.note or ""})

    return render(
        request, "surveys/invites_pending.html", {"survey": survey, "invites": invites}
    )


@login_required
@require_http_methods(["POST"])
def survey_invite_resend(
    request: HttpRequest, slug: str, token_id: int
) -> HttpResponse:
    """Resend an invitation email for a pending access token.

    Only allows resending for tokens that haven't been used yet (no response).
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    token = get_object_or_404(
        SurveyAccessToken,
        id=token_id,
        survey=survey,
        note__icontains="Invited",
        response__isnull=True,
    )

    # Extract email from note (format: "Invited: email@domain.com")
    email = None
    if token.note and ":" in token.note:
        email = token.note.split(":", 1)[1].strip()

    if not email or "@" not in email:
        messages.error(request, "Cannot resend: invalid email address in token note.")
        return redirect("surveys:invites_pending", slug=slug)

    # Send the invitation email
    from checktick_app.core.email_utils import send_survey_invite_email

    contact_email = request.user.email if request.user.email else None

    if send_survey_invite_email(
        to_email=email,
        survey=survey,
        token=token.token,
        contact_email=contact_email,
    ):
        messages.success(request, f"Invitation resent to {email}")
    else:
        messages.error(request, f"Failed to resend invitation to {email}")

    return redirect("surveys:invites_pending", slug=slug)


@login_required
@require_http_methods(["GET", "POST"])
def survey_delete(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Delete a survey with confirmation.

    GET: Show confirmation page
    POST: Delete survey if name confirmation matches

    Only owner or org admin can delete surveys.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    if request.method == "GET":
        # Show confirmation page
        return render(
            request,
            "surveys/delete_confirm.html",
            {"survey": survey},
        )

    # POST: Process deletion with confirmation
    confirm_name = request.POST.get("confirm_name", "").strip()

    if not confirm_name:
        messages.error(request, "Please enter the survey name to confirm deletion.")
        return render(
            request,
            "surveys/delete_confirm.html",
            {"survey": survey, "error": "confirmation_required"},
            status=400,
        )

    if confirm_name != survey.name:
        messages.error(
            request,
            f"Survey name does not match. Please type '{survey.name}' exactly to confirm deletion.",
        )
        return render(
            request,
            "surveys/delete_confirm.html",
            {"survey": survey, "error": "name_mismatch", "confirm_name": confirm_name},
            status=400,
        )

    # Log deletion before deleting
    survey_name = survey.name
    survey_slug = survey.slug
    organization = survey.organization

    # Delete survey (cascades to questions, responses, etc.)
    survey.delete()

    # Create audit log
    AuditLog.objects.create(
        actor=request.user,
        scope=AuditLog.Scope.SURVEY,
        survey=None,  # Survey is deleted
        organization=organization,
        action=AuditLog.Action.REMOVE,
        target_user=request.user,
        metadata={
            "survey_name": survey_name,
            "survey_slug": survey_slug,
        },
    )

    messages.success(request, f"Survey '{survey_name}' has been permanently deleted.")

    # Redirect to surveys list or home
    return redirect("core:home")


def _parse_email_addresses(text: str) -> list[str]:
    """Parse email addresses from various formats.

    Supports:
    - One per line: email@domain.com
    - Outlook format: Name <email@domain.com>
    - Semicolon separated: email1@domain.com; email2@domain.com
    - Combined: Name1 <email1@domain.com>; Name2 <email2@domain.com>

    Returns list of email addresses.
    """
    import re

    # First split by semicolons and newlines
    raw_entries = re.split(r"[;\n]", text)

    email_list = []
    # Extract email from each entry (handle both plain and "Name <email>" formats)
    email_pattern = r"<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"

    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue

        # Try to find email in angle brackets first (Outlook format)
        match = re.search(email_pattern, entry)
        if match:
            # Group 1 is email in angle brackets, group 2 is plain email
            email = match.group(1) or match.group(2)
            if email:
                email_list.append(email.strip())

    return email_list


@login_required
@require_http_methods(["GET", "POST"])
def survey_publish_settings(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Dedicated publish settings page with clearer UX.
    Handles both initial publish and editing published surveys.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    if request.method == "POST":
        action = request.POST.get("action", "publish")

        # Parse fields
        visibility = request.POST.get("visibility") or survey.visibility
        start_at_str = request.POST.get("start_at") or None
        end_at_str = request.POST.get("end_at") or None
        max_responses = request.POST.get("max_responses") or None
        captcha_required = bool(request.POST.get("captcha_required"))
        # If survey is already published with no_patient_data_ack=True, preserve it (disabled checkboxes don't submit)
        no_patient_data_ack = bool(request.POST.get("no_patient_data_ack")) or (
            survey.status == Survey.Status.PUBLISHED and survey.no_patient_data_ack
        )
        invite_emails = request.POST.get("invite_emails", "").strip()

        # Parse dates
        from django.utils.dateparse import parse_datetime

        start_at = parse_datetime(start_at_str) if start_at_str else None
        end_at = parse_datetime(end_at_str) if end_at_str else None

        if max_responses:
            try:
                max_responses = int(max_responses)
            except ValueError:
                max_responses = None

        # Validate patient data acknowledgment for non-auth visibility
        collects_patient = _survey_collects_patient_data(survey)
        if (
            visibility
            in {
                Survey.Visibility.PUBLIC,
                Survey.Visibility.UNLISTED,
                Survey.Visibility.TOKEN,
            }
            and collects_patient
        ):
            if not no_patient_data_ack:
                messages.error(
                    request,
                    "To use public, unlisted, or tokenized visibility, confirm that no patient data is collected.",
                )
                return render(
                    request, "surveys/publish_settings.html", {"survey": survey}
                )

        # Handle different actions
        if action == "close":
            # Close the survey and start retention period
            survey.close_survey(request.user)

            # Send closure confirmation email
            _send_survey_closure_notification(survey, request.user)

            messages.success(
                request,
                f"Survey has been closed. Data will be retained for {survey.retention_months} months.",
            )
            return redirect("surveys:dashboard", slug=slug)

        elif action == "publish":
            # Publishing for the first time
            prev_status = survey.status

            # Check if encryption setup is needed
            # Only surveys that collect patient data require encryption
            needs_encryption_setup = (
                collects_patient
                and prev_status != Survey.Status.PUBLISHED
                and not survey.has_any_encryption()
            )

            if needs_encryption_setup:
                # Check if user can collect patient data (FREE tier cannot)
                from checktick_app.core.tier_limits import check_patient_data_permission

                can_collect, reason = check_patient_data_permission(request.user)
                if not can_collect:
                    messages.error(
                        request,
                        f"{reason} Your survey contains patient data questions that require encryption.",
                    )
                    return render(
                        request, "surveys/publish_settings.html", {"survey": survey}
                    )

                # Store pending publish settings in session
                request.session["pending_publish"] = {
                    "slug": slug,
                    "visibility": visibility,
                    "start_at": start_at.isoformat() if start_at else None,
                    "end_at": end_at.isoformat() if end_at else None,
                    "max_responses": max_responses,
                    "captcha_required": captcha_required,
                    "no_patient_data_ack": no_patient_data_ack,
                }
                return redirect("surveys:encryption_setup", slug=slug)

            # Apply settings
            survey.visibility = visibility
            survey.start_at = start_at
            survey.end_at = end_at
            survey.max_responses = max_responses
            survey.captcha_required = captcha_required
            survey.no_patient_data_ack = no_patient_data_ack

            # Handle allow_any_authenticated for authenticated surveys
            if visibility == Survey.Visibility.AUTHENTICATED:
                allow_any_authenticated = (
                    request.POST.get("allow_any_authenticated") == "on"
                )
                survey.allow_any_authenticated = allow_any_authenticated
            else:
                survey.allow_any_authenticated = False

            # Set status to PUBLISHED
            survey.status = Survey.Status.PUBLISHED

            # On first publish, set published_at and start_at if not provided
            if prev_status != Survey.Status.PUBLISHED and not survey.published_at:
                survey.published_at = timezone.now()
                # If start_at not provided, set it to now (survey starts immediately)
                if not survey.start_at:
                    survey.start_at = timezone.now()

            # Generate unlisted key if needed
            if (
                survey.visibility == Survey.Visibility.UNLISTED
                and not survey.unlisted_key
            ):
                import secrets

                survey.unlisted_key = secrets.token_urlsafe(24)

            survey.save()

            # Publish selected translations if any are checked
            published_count = 0
            publish_translations = request.POST.getlist("publish_translations")
            if publish_translations:
                for translation_slug in publish_translations:
                    try:
                        translation = Survey.objects.get(
                            slug=translation_slug, translated_from=survey
                        )
                        if translation.status != Survey.Status.PUBLISHED:
                            translation.status = Survey.Status.PUBLISHED
                            translation.published_at = timezone.now()
                            # Copy relevant publish settings from parent
                            translation.visibility = survey.visibility
                            translation.start_at = survey.start_at
                            translation.end_at = survey.end_at
                            translation.max_responses = survey.max_responses
                            translation.captcha_required = survey.captcha_required
                            translation.no_patient_data_ack = survey.no_patient_data_ack
                            translation.allow_any_authenticated = (
                                survey.allow_any_authenticated
                            )
                            if survey.visibility == Survey.Visibility.UNLISTED:
                                # Generate unique unlisted key for translation
                                # Always generate new key to avoid duplicates
                                import secrets

                                translation.unlisted_key = secrets.token_urlsafe(24)
                            translation.save()
                            published_count += 1
                    except Survey.DoesNotExist:
                        continue

                if published_count > 0:
                    messages.success(
                        request,
                        f"Survey published with {published_count} translation(s)!",
                    )

            # Process invite emails if provided - start async sending
            if invite_emails and visibility in [
                Survey.Visibility.TOKEN,
                Survey.Visibility.AUTHENTICATED,
            ]:
                import threading
                import uuid

                from django.core.cache import cache

                # Parse email addresses
                email_list = _parse_email_addresses(invite_emails)

                # Generate task ID
                task_id = str(uuid.uuid4())

                # Set initial status in cache
                cache.set(
                    f"email_task_{task_id}",
                    {
                        "status": "processing",
                        "progress": 0,
                        "message": f"Starting to send {len(email_list)} invitation(s)...",
                        "sent_count": 0,
                        "failed_count": 0,
                    },
                    timeout=3600,
                )

                # Start background thread
                thread = threading.Thread(
                    target=_send_invites_background,
                    args=(
                        survey.id,
                        email_list,
                        visibility,
                        survey.end_at,
                        request.user.email if request.user.email else None,
                        request.user.id,
                        task_id,
                    ),
                )
                thread.start()

                # Store task ID in session for status tracking
                request.session["pending_invites"] = {
                    "slug": slug,
                    "task_id": task_id,
                    "email_count": len(email_list),
                }

                if published_count > 0:
                    messages.success(
                        request,
                        f"Survey published with {published_count} translation(s)! Sending invitations...",
                    )
                else:
                    messages.success(
                        request, "Survey has been published! Sending invitations..."
                    )
            else:
                if published_count > 0:
                    messages.success(
                        request,
                        f"Survey published with {published_count} translation(s)!",
                    )
                else:
                    messages.success(request, "Survey has been published successfully!")

            return redirect("surveys:dashboard", slug=slug)

        elif action == "save":
            # Saving changes to already-published survey
            survey.visibility = visibility
            survey.start_at = start_at
            survey.end_at = end_at
            survey.max_responses = max_responses
            survey.captcha_required = captcha_required
            survey.no_patient_data_ack = no_patient_data_ack

            # Handle allow_any_authenticated for authenticated surveys
            if visibility == Survey.Visibility.AUTHENTICATED:
                allow_any_authenticated = (
                    request.POST.get("allow_any_authenticated") == "on"
                )
                survey.allow_any_authenticated = allow_any_authenticated
            else:
                survey.allow_any_authenticated = False

            # Generate unlisted key if needed
            if (
                survey.visibility == Survey.Visibility.UNLISTED
                and not survey.unlisted_key
            ):
                import secrets

                survey.unlisted_key = secrets.token_urlsafe(24)

            survey.save()

            # Publish selected translations if any are checked
            publish_translations = request.POST.getlist("publish_translations")
            published_count = 0
            if publish_translations:
                for translation_slug in publish_translations:
                    try:
                        translation = Survey.objects.get(
                            slug=translation_slug, translated_from=survey
                        )
                        if translation.status != Survey.Status.PUBLISHED:
                            translation.status = Survey.Status.PUBLISHED
                            translation.published_at = timezone.now()
                            # Copy relevant publish settings from parent
                            translation.visibility = survey.visibility
                            translation.start_at = survey.start_at
                            translation.end_at = survey.end_at
                            translation.max_responses = survey.max_responses
                            translation.captcha_required = survey.captcha_required
                            translation.no_patient_data_ack = survey.no_patient_data_ack
                            translation.allow_any_authenticated = (
                                survey.allow_any_authenticated
                            )
                            if survey.visibility == Survey.Visibility.UNLISTED:
                                # Generate unique unlisted key for translation
                                # Always generate new key to avoid duplicates
                                import secrets

                                translation.unlisted_key = secrets.token_urlsafe(24)
                            translation.save()
                            published_count += 1
                    except Survey.DoesNotExist:
                        continue

            # Process invite emails if provided - use async sending
            if invite_emails and visibility in [
                Survey.Visibility.TOKEN,
                Survey.Visibility.AUTHENTICATED,
            ]:
                # Store invitation request in session for status tracking
                request.session["pending_invites"] = {
                    "slug": slug,
                    "email_count": len(_parse_email_addresses(invite_emails)),
                }

                messages.success(request, "Settings updated! Sending invitations...")
            else:
                if published_count > 0:
                    messages.success(
                        request,
                        f"Settings updated! Published {published_count} translation(s).",
                    )
                else:
                    messages.success(request, "Publication settings updated.")

            return redirect("surveys:dashboard", slug=slug)

    # GET request - show the form
    # Get available translations
    available_translations = survey.get_available_translations()

    # Check if there are any draft translations
    has_draft_translations = any(
        t.status == Survey.Status.DRAFT for t in available_translations
    )

    # Get supported languages for dropdown
    supported_languages = [
        {"code": code, "name": name}
        for code, name in SUPPORTED_SURVEY_LANGUAGES
        if code != survey.language
    ]

    context = {
        "survey": survey,
        "available_translations": available_translations,
        "has_draft_translations": has_draft_translations,
        "supported_languages": supported_languages,
    }

    return render(request, "surveys/publish_settings.html", context)


@login_required
@require_http_methods(["POST"])
def create_translation_async(request: HttpRequest, slug: str) -> JsonResponse:
    """
    Create a translation of a survey asynchronously.
    Returns a task_id for polling status.
    """
    import json
    import threading
    import uuid

    from django.core.cache import cache

    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    # Handle both JSON and form data
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
            target_language = data.get("target_language") or data.get("language")
            force_retranslate = data.get("force_retranslate", False)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        target_language = request.POST.get("language") or request.POST.get(
            "target_language"
        )
        force_retranslate = request.POST.get("force_retranslate") == "true"

    if not target_language:
        return JsonResponse({"error": "Language parameter required"}, status=400)

    # Validate language code
    if target_language not in dict(SUPPORTED_SURVEY_LANGUAGES):
        return JsonResponse({"error": "Invalid language code"}, status=400)

    # Check if translation already exists
    existing = survey.get_translation(target_language)
    if existing and not force_retranslate:
        return JsonResponse(
            {
                "error": f"Translation to {target_language} already exists",
                "translation_slug": existing.slug,
            },
            status=400,
        )

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Set initial status
    cache.set(
        f"translation_task_{task_id}",
        {
            "status": "processing",
            "progress": 0,
            "message": "Creating translation...",
        },
        timeout=3600,  # 1 hour
    )

    def translate_in_background():
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        translation = None
        is_retranslate = False  # Track if we're re-translating an existing survey

        try:
            # Create or get existing translation survey
            cache.set(
                f"translation_task_{task_id}",
                {
                    "status": "processing",
                    "progress": 25,
                    "message": (
                        "Creating survey structure..."
                        if not existing
                        else "Preparing to re-translate..."
                    ),
                },
                timeout=3600,
            )

            if existing and force_retranslate:
                # Re-use existing translation survey
                translation = existing
                is_retranslate = True  # Mark as re-translate to preserve on failure
                logger.info(
                    f"Re-translating existing survey {translation.slug} for {survey.slug} in {target_language}"
                )
            else:
                # Create new translation survey
                translation = survey.create_translation(target_language=target_language)
                logger.info(
                    f"Created translation survey {translation.slug} for {survey.slug} in {target_language}"
                )

            # Run LLM translation
            cache.set(
                f"translation_task_{task_id}",
                {
                    "status": "processing",
                    "progress": 50,
                    "message": "Translating content with AI...",
                },
                timeout=3600,
            )

            results = survey.translate_survey_content(translation, use_llm=True)
            logger.info(
                f"Translation results for {translation.slug}: {results['translated_fields']} fields, errors: {results['errors']}"
            )

            # Update final status
            if results["success"]:
                cache.set(
                    f"translation_task_{task_id}",
                    {
                        "status": "completed",
                        "progress": 100,
                        "message": "Translation completed successfully",
                        "translation_slug": translation.slug,
                        "translated_fields": results["translated_fields"],
                        "warnings": results.get("warnings", []),
                    },
                    timeout=3600,
                )
            else:
                error_msg = (
                    "; ".join(results["errors"])
                    if results["errors"]
                    else "Unknown error"
                )
                logger.error(f"Translation failed for {translation.slug}: {error_msg}")

                # Only delete if this was a new translation, not a re-translate
                if translation and not is_retranslate:
                    logger.info(
                        f"Deleting failed translation survey {translation.slug}"
                    )
                    translation.delete()
                elif is_retranslate:
                    logger.info(
                        f"Preserving existing translation survey {translation.slug} after failed re-translate"
                    )

                cache.set(
                    f"translation_task_{task_id}",
                    {
                        "status": "error",
                        "progress": 100,
                        "message": f"Translation failed: {error_msg}",
                        "errors": results["errors"],
                    },
                    timeout=3600,
                )

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Translation exception for {survey.slug}: {error_details}")

            # Only delete the failed translation if it was just created, not if re-translating
            if translation and not is_retranslate:
                try:
                    logger.info(
                        f"Deleting failed translation survey {translation.slug} after exception"
                    )
                    translation.delete()
                except Exception as delete_error:
                    logger.error(f"Failed to delete translation survey: {delete_error}")
            elif translation and is_retranslate:
                logger.info(
                    f"Preserving existing translation survey {translation.slug} after exception"
                )

            cache.set(
                f"translation_task_{task_id}",
                {
                    "status": "error",
                    "progress": 100,
                    "message": f"Translation error: {str(e)}",
                },
                timeout=3600,
            )

    # Start background thread
    thread = threading.Thread(target=translate_in_background)
    thread.daemon = True
    thread.start()

    return JsonResponse({"task_id": task_id})


@login_required
@require_http_methods(["GET"])
def translation_status(request: HttpRequest, slug: str, task_id: str) -> JsonResponse:
    """Poll status of an async translation task."""
    from django.core.cache import cache

    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)

    status_data = cache.get(f"translation_task_{task_id}")

    if not status_data:
        return JsonResponse(
            {"status": "error", "message": "Task not found or expired"}, status=404
        )

    return JsonResponse(status_data)


def _send_invites_background(
    survey_id: int,
    email_list: list[str],
    visibility: str,
    end_at,
    contact_email: str,
    user_id: int,
    task_id: str,
) -> None:
    """Background task to send survey invitation emails."""
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    from checktick_app.core.email_utils import (
        send_authenticated_survey_invite_existing_user,
        send_authenticated_survey_invite_new_user,
        send_survey_invite_email,
    )

    User = get_user_model()

    try:
        survey = Survey.objects.get(id=survey_id)
        user = User.objects.get(id=user_id)

        sent_count = 0
        failed_emails = []
        total_emails = len(email_list)

        for idx, email_address in enumerate(email_list):
            # Update progress
            progress = int(((idx + 1) / total_emails) * 100)
            cache.set(
                f"email_task_{task_id}",
                {
                    "status": "processing",
                    "progress": progress,
                    "message": f"Sending invitation {idx + 1} of {total_emails}...",
                    "sent_count": sent_count,
                    "failed_count": len(failed_emails),
                },
                timeout=3600,
            )

            # Validate email format (basic check)
            if "@" not in email_address or "." not in email_address.split("@")[1]:
                failed_emails.append(f"{email_address} (invalid format)")
                continue

            if visibility == Survey.Visibility.TOKEN:
                # Create anonymous token
                token = SurveyAccessToken(
                    survey=survey,
                    token=secrets.token_urlsafe(24),
                    created_by=user,
                    expires_at=end_at if end_at else None,
                    note=f"Invited: {email_address}",
                    for_authenticated=False,
                )
                token.save()

                # Send invitation email
                if send_survey_invite_email(
                    to_email=email_address,
                    survey=survey,
                    token=token.token,
                    contact_email=contact_email,
                ):
                    sent_count += 1
                else:
                    failed_emails.append(email_address)

            elif visibility == Survey.Visibility.AUTHENTICATED:
                # Create authenticated invitation token
                token = SurveyAccessToken(
                    survey=survey,
                    token=secrets.token_urlsafe(24),
                    created_by=user,
                    expires_at=end_at if end_at else None,
                    note=f"Invited: {email_address}",
                    for_authenticated=True,
                )
                token.save()

                # Check if user exists
                user_exists = User.objects.filter(email=email_address).exists()

                # Send appropriate email
                if user_exists:
                    email_sent = send_authenticated_survey_invite_existing_user(
                        to_email=email_address,
                        survey=survey,
                        contact_email=contact_email,
                    )
                else:
                    email_sent = send_authenticated_survey_invite_new_user(
                        to_email=email_address,
                        survey=survey,
                        contact_email=contact_email,
                    )

                if email_sent:
                    sent_count += 1
                else:
                    failed_emails.append(email_address)

        # Update final status
        cache.set(
            f"email_task_{task_id}",
            {
                "status": "completed",
                "progress": 100,
                "message": "All invitations processed",
                "sent_count": sent_count,
                "failed_emails": failed_emails,
            },
            timeout=3600,
        )

    except Exception as e:
        cache.set(
            f"email_task_{task_id}",
            {
                "status": "error",
                "message": f"Failed to send invitations: {str(e)}",
            },
            timeout=3600,
        )


@login_required
@require_http_methods(["POST"])
def send_invites_async(request: HttpRequest, slug: str) -> JsonResponse:
    """Start async email sending for survey invitations."""
    import threading
    import uuid

    from django.core.cache import cache

    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    invite_emails = request.POST.get("invite_emails", "").strip()

    if not invite_emails:
        return JsonResponse({"error": "No email addresses provided"}, status=400)

    # Parse email addresses
    email_list = _parse_email_addresses(invite_emails)

    if not email_list:
        return JsonResponse({"error": "No valid email addresses found"}, status=400)

    # Get parameters
    visibility = survey.visibility
    end_at = survey.end_at
    contact_email = request.user.email if request.user.email else None

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Set initial status in cache
    cache.set(
        f"email_task_{task_id}",
        {
            "status": "processing",
            "progress": 0,
            "message": f"Starting to send {len(email_list)} invitation(s)...",
            "sent_count": 0,
            "failed_count": 0,
        },
        timeout=3600,
    )

    # Start background thread
    thread = threading.Thread(
        target=_send_invites_background,
        args=(
            survey.id,
            email_list,
            visibility,
            end_at,
            contact_email,
            request.user.id,
            task_id,
        ),
    )
    thread.start()

    return JsonResponse({"task_id": task_id, "total_emails": len(email_list)})


@login_required
@require_http_methods(["GET"])
def email_status(request: HttpRequest, slug: str, task_id: str) -> JsonResponse:
    """Poll status of an async email sending task."""
    from django.core.cache import cache

    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)

    status_data = cache.get(f"email_task_{task_id}")

    if not status_data:
        return JsonResponse(
            {"status": "error", "message": "Task not found or expired"}, status=404
        )

    return JsonResponse(status_data)


@login_required
@require_http_methods(["POST"])
def survey_publish_update(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    # Parse fields
    status = request.POST.get("status") or survey.status
    visibility = request.POST.get("visibility") or survey.visibility
    start_at = request.POST.get("start_at") or None
    end_at = request.POST.get("end_at") or None
    max_responses = request.POST.get("max_responses") or None
    captcha_required = bool(request.POST.get("captcha_required"))
    no_patient_data_ack = bool(request.POST.get("no_patient_data_ack"))

    # Coerce types
    from django.utils.dateparse import parse_datetime

    if start_at:
        start_at = parse_datetime(start_at)
    if end_at:
        end_at = parse_datetime(end_at)
    if max_responses:
        try:
            max_responses = int(max_responses)
            if max_responses <= 0:
                max_responses = None
        except Exception:
            max_responses = None

    # Enforce patient-data + non-auth visibility disclaimer
    collects_patient = _survey_collects_patient_data(survey)
    if (
        visibility
        in {
            Survey.Visibility.PUBLIC,
            Survey.Visibility.UNLISTED,
            Survey.Visibility.TOKEN,
        }
        and collects_patient
    ):
        if not no_patient_data_ack and visibility != Survey.Visibility.AUTHENTICATED:
            messages.error(
                request,
                "To use public, unlisted, or tokenized visibility, confirm that no patient data is collected.",
            )
            return redirect("surveys:dashboard", slug=slug)

    # Check if encryption setup is needed
    prev_status = survey.status

    # Determine if we need to redirect to encryption setup
    # Only surveys that collect patient data require encryption
    # Organization + SSO users: auto-encrypt without setup page
    # Organization + Password users: need setup if no encryption yet
    # Individual + SSO users: need to choose SSO-only vs SSO+recovery
    # Individual + Password users: need setup if no encryption yet

    collects_patient = _survey_collects_patient_data(survey)
    is_org_member = survey.organization is not None
    is_sso_user = hasattr(request.user, "oidc")
    is_first_publish = (
        prev_status != Survey.Status.PUBLISHED and status == Survey.Status.PUBLISHED
    )
    has_encryption = survey.has_any_encryption()

    # Auto-encrypt for organization SSO users (no setup page needed)
    # Only if survey collects patient data
    if (
        collects_patient
        and is_org_member
        and is_sso_user
        and is_first_publish
        and not has_encryption
    ):
        import os

        # Generate survey encryption key
        kek = os.urandom(32)

        # Set up OIDC encryption for automatic unlock
        try:
            survey.set_oidc_encryption(kek, request.user)
            logger.info(
                f"Added OIDC encryption for org survey {survey.slug} during publish (provider: {request.user.oidc.provider})"
            )
        except Exception as e:
            logger.error(f"Failed to add OIDC encryption: {e}")
            messages.error(
                request, "Failed to set up SSO encryption. Please try again."
            )
            return redirect("surveys:dashboard", slug=slug)

        # Set up organization encryption for admin recovery
        if survey.organization and survey.organization.encrypted_master_key:
            try:
                survey.set_org_encryption(kek, survey.organization)
                logger.info(
                    f"Added organization encryption for survey {survey.slug} during publish (org: {survey.organization.name})"
                )
            except Exception as e:
                logger.warning(f"Failed to add organization encryption: {e}")

        # Continue with publish (encryption is set up)
        provider_name = request.user.oidc.provider.title()
        messages.success(
            request,
            f"Survey encrypted automatically with your {provider_name} account + organization recovery.",
        )

    # All other cases: check if encryption setup is needed
    # Only redirect to setup if survey collects patient data and has no encryption
    elif collects_patient and is_first_publish and not has_encryption:
        # Store pending publish settings in session
        request.session["pending_publish"] = {
            "slug": slug,
            "status": status,
            "visibility": visibility,
            "start_at": start_at.isoformat() if start_at else None,
            "end_at": end_at.isoformat() if end_at else None,
            "max_responses": max_responses,
            "captcha_required": captcha_required,
            "no_patient_data_ack": no_patient_data_ack,
        }
        # Redirect to encryption setup page
        return redirect("surveys:encryption_setup", slug=slug)

    # Apply changes
    survey.status = status
    survey.visibility = visibility
    survey.start_at = start_at
    survey.end_at = end_at
    survey.max_responses = max_responses
    survey.captcha_required = captcha_required
    survey.no_patient_data_ack = no_patient_data_ack
    # On first publish, set published_at and start_at if not provided
    if (
        prev_status != Survey.Status.PUBLISHED
        and status == Survey.Status.PUBLISHED
        and not survey.published_at
    ):
        survey.published_at = timezone.now()
        # If start_at not provided, set it to now
        if not survey.start_at:
            survey.start_at = timezone.now()
    # Generate unlisted key if needed
    if survey.visibility == Survey.Visibility.UNLISTED and not survey.unlisted_key:
        survey.unlisted_key = secrets.token_urlsafe(24)
    survey.save()
    messages.success(request, "Publish settings updated.")
    return redirect("surveys:dashboard", slug=slug)


@login_required
@require_http_methods(["GET", "POST"])
def survey_encryption_setup(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Encryption setup page for users publishing surveys.

    - SSO individual users: choose between SSO-only or SSO+recovery
    - Password individual users: password + recovery phrase (traditional)
    - Organization users: should not reach this page (auto-encrypted)
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    # Check if we have pending publish settings
    pending = request.session.get("pending_publish", {})
    if pending.get("slug") != slug:
        messages.error(request, "No pending publish action found.")
        return redirect("surveys:dashboard", slug=slug)

    # Check if survey already has encryption
    if survey.has_any_encryption():
        messages.info(request, "Survey already has encryption enabled.")
        return redirect("surveys:dashboard", slug=slug)

    is_sso_user = hasattr(request.user, "oidc")
    is_org_member = survey.organization is not None

    if request.method == "POST":
        import os

        from .utils import generate_bip39_phrase

        kek = os.urandom(32)  # 256-bit survey encryption key

        # Handle SSO user choice (individual users only)
        if is_sso_user and not is_org_member:
            encryption_choice = request.POST.get("encryption_choice", "")

            if encryption_choice == "sso_only":
                # SSO-only encryption (no password/recovery phrase)
                try:
                    survey.set_oidc_encryption(kek, request.user)
                    logger.info(
                        f"Set up SSO-only encryption for survey {survey.slug} (provider: {request.user.oidc.provider})"
                    )
                except Exception as e:
                    logger.error(f"Failed to set up SSO-only encryption: {e}")
                    messages.error(
                        request, "Failed to set up SSO encryption. Please try again."
                    )
                    return render(
                        request,
                        "surveys/encryption_setup.html",
                        {
                            "survey": survey,
                            "is_sso_user": is_sso_user,
                            "is_org_member": is_org_member,
                        },
                    )

                # Apply pending publish settings and complete
                _apply_pending_publish_settings(survey, pending)

                # Clear session data
                if "pending_publish" in request.session:
                    del request.session["pending_publish"]

                provider_name = request.user.oidc.provider.title()
                messages.success(
                    request,
                    f"Survey published with SSO-only encryption ({provider_name}). "
                    f"Your survey will auto-unlock when you sign in.",
                )
                return redirect("surveys:dashboard", slug=slug)

            elif encryption_choice == "sso_recovery":
                # SSO + recovery phrase (belt and suspenders)
                recovery_words = generate_bip39_phrase(12)

                try:
                    # Set up OIDC encryption
                    survey.set_oidc_encryption(kek, request.user)
                    # Set up recovery phrase encryption (no password)
                    from .utils import create_recovery_hint, encrypt_kek_with_passphrase

                    recovery_phrase = " ".join(recovery_words)
                    survey.encrypted_kek_recovery = encrypt_kek_with_passphrase(
                        kek, recovery_phrase
                    )
                    survey.recovery_code_hint = create_recovery_hint(recovery_words)
                    survey.save(
                        update_fields=["encrypted_kek_recovery", "recovery_code_hint"]
                    )

                    logger.info(
                        f"Set up SSO+recovery encryption for survey {survey.slug} (provider: {request.user.oidc.provider})"
                    )
                except Exception as e:
                    logger.error(f"Failed to set up SSO+recovery encryption: {e}")
                    messages.error(
                        request, "Failed to set up encryption. Please try again."
                    )
                    return render(
                        request,
                        "surveys/encryption_setup.html",
                        {
                            "survey": survey,
                            "is_sso_user": is_sso_user,
                            "is_org_member": is_org_member,
                        },
                    )

                # Apply pending publish settings
                _apply_pending_publish_settings(survey, pending)

                # Store recovery phrase for display
                request.session["encryption_display"] = {
                    "slug": slug,
                    "recovery_phrase": recovery_phrase,
                    "recovery_hint": survey.recovery_code_hint,
                    "is_sso_recovery": True,
                }

                # Clear pending publish settings
                if "pending_publish" in request.session:
                    del request.session["pending_publish"]

                # Redirect to recovery phrase display
                return redirect("surveys:encryption_display", slug=slug)

            else:
                messages.error(request, "Please select an encryption option.")
                return render(
                    request,
                    "surveys/encryption_setup.html",
                    {
                        "survey": survey,
                        "is_sso_user": is_sso_user,
                        "is_org_member": is_org_member,
                    },
                )

        # Handle password-based user (traditional dual encryption)
        else:
            password = request.POST.get("password", "").strip()
            password_confirm = request.POST.get("password_confirm", "").strip()

            # Validate password
            if not password:
                messages.error(request, "Password is required.")
                return render(
                    request,
                    "surveys/encryption_setup.html",
                    {
                        "survey": survey,
                        "is_sso_user": is_sso_user,
                        "is_org_member": is_org_member,
                    },
                )

            if len(password) < 12:
                messages.error(request, "Password must be at least 12 characters.")
                return render(
                    request,
                    "surveys/encryption_setup.html",
                    {
                        "survey": survey,
                        "is_sso_user": is_sso_user,
                        "is_org_member": is_org_member,
                    },
                )

            if password != password_confirm:
                messages.error(request, "Passwords do not match.")
                return render(
                    request,
                    "surveys/encryption_setup.html",
                    {
                        "survey": survey,
                        "is_sso_user": is_sso_user,
                        "is_org_member": is_org_member,
                    },
                )

            # Generate 12-word recovery phrase
            recovery_words = generate_bip39_phrase(12)

            # Set up dual encryption
            survey.set_dual_encryption(kek, password, recovery_words)

            # Also set up OIDC encryption if user has OIDC authentication (org password users)
            if is_sso_user:
                try:
                    survey.set_oidc_encryption(kek, request.user)
                    logger.info(
                        f"Added OIDC encryption for survey {survey.slug} during encryption setup (provider: {request.user.oidc.provider})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to add OIDC encryption to survey {survey.slug}: {e}"
                    )

            # Also set up organization encryption if survey belongs to an organization
            if survey.organization and survey.organization.encrypted_master_key:
                try:
                    survey.set_org_encryption(kek, survey.organization)
                    logger.info(
                        f"Added organization encryption for survey {survey.slug} during encryption setup (org: {survey.organization.name})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to add organization encryption to survey {survey.slug}: {e}"
                    )

            # Apply pending publish settings
            _apply_pending_publish_settings(survey, pending)

            # Store KEK and recovery phrase in session for key display page (one-time access)
            request.session["encryption_display"] = {
                "slug": slug,
                "kek_hex": kek.hex(),
                "recovery_phrase": " ".join(recovery_words),
                "recovery_hint": survey.recovery_code_hint,
            }

            # Clear pending publish settings
            if "pending_publish" in request.session:
                del request.session["pending_publish"]

            # Redirect to key display page
            return redirect("surveys:encryption_display", slug=slug)

    # GET request: show encryption setup form
    return render(
        request,
        "surveys/encryption_setup.html",
        {
            "survey": survey,
            "is_sso_user": is_sso_user,
            "is_org_member": is_org_member,
        },
    )


def _apply_pending_publish_settings(survey: Survey, pending: dict) -> None:
    """
    Helper function to apply pending publish settings to a survey.
    Used by survey_encryption_setup after encryption is configured.
    """
    from django.utils.dateparse import parse_datetime

    # Set status to PUBLISHED (this is a publish action)
    survey.status = Survey.Status.PUBLISHED
    survey.visibility = pending.get("visibility", survey.visibility)
    start_at_str = pending.get("start_at")
    end_at_str = pending.get("end_at")
    survey.start_at = parse_datetime(start_at_str) if start_at_str else None
    survey.end_at = parse_datetime(end_at_str) if end_at_str else None
    survey.max_responses = pending.get("max_responses")
    survey.captcha_required = pending.get("captcha_required", False)
    survey.no_patient_data_ack = pending.get("no_patient_data_ack", False)

    # Set published_at and start_at if first publish
    if survey.status == Survey.Status.PUBLISHED and not survey.published_at:
        survey.published_at = timezone.now()
        # If start_at not provided, set it to now
        if not survey.start_at:
            survey.start_at = timezone.now()

    # Generate unlisted key if needed
    if survey.visibility == Survey.Visibility.UNLISTED and not survey.unlisted_key:
        survey.unlisted_key = secrets.token_urlsafe(24)

    survey.save()


@login_required
@require_http_methods(["GET", "POST"])
def survey_encryption_display(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Display encryption key and recovery phrase once after setup.
    Keys are stored in session and cleared after viewing.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    # Check if we have encryption display data in session
    display_data = request.session.get("encryption_display", {})
    if display_data.get("slug") != slug:
        messages.error(
            request,
            "Encryption keys have already been displayed or no setup data found.",
        )
        return redirect("surveys:dashboard", slug=slug)

    # Prepare display data
    kek_hex = display_data.get("kek_hex", "")
    recovery_phrase = display_data.get("recovery_phrase", "")
    recovery_hint = display_data.get("recovery_hint", "")
    recovery_words = recovery_phrase.split() if recovery_phrase else []

    if request.method == "POST":
        # User has acknowledged viewing the keys - clear session data
        if "encryption_display" in request.session:
            del request.session["encryption_display"]
        messages.success(
            request, "Survey published successfully with encryption enabled."
        )
        return redirect("surveys:dashboard", slug=slug)

    context = {
        "survey": survey,
        "kek_hex": kek_hex,
        "recovery_phrase": recovery_phrase,
        "recovery_words": recovery_words,
        "recovery_hint": recovery_hint,
    }
    return render(request, "surveys/encryption_display.html", context)


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take(request: HttpRequest, slug: str) -> HttpResponse:
    """Participant-facing endpoint. Supports AUTHENTICATED and PUBLIC visibility here.
    UNLISTED and TOKEN have dedicated routes.
    """
    survey = get_object_or_404(Survey, slug=slug)
    if not survey.is_live():
        # Determine specific reason for being closed
        from django.utils import timezone

        now = timezone.now()
        if survey.status != Survey.Status.PUBLISHED:
            return redirect("surveys:closed", slug=slug)
        elif survey.start_at and survey.start_at > now:
            return redirect(f"/surveys/{slug}/closed/?reason=not_started")
        elif survey.end_at and now > survey.end_at:
            return redirect(f"/surveys/{slug}/closed/?reason=ended")
        elif survey.max_responses and hasattr(survey, "responses"):
            if survey.responses.count() >= survey.max_responses:
                return redirect(f"/surveys/{slug}/closed/?reason=max_responses")
        return redirect("surveys:closed", slug=slug)
    if survey.visibility == Survey.Visibility.UNLISTED:
        raise Http404()
    if survey.visibility == Survey.Visibility.TOKEN:
        # Redirect to generic info page or 404
        raise Http404()
    if (
        survey.visibility == Survey.Visibility.AUTHENTICATED
        and not request.user.is_authenticated
    ):
        # Enforce login
        messages.info(request, "Please sign in to take this survey.")
        return redirect("/accounts/login/?next=" + request.path)

    # For authenticated surveys, check invitation if not allowing any authenticated
    if (
        survey.visibility == Survey.Visibility.AUTHENTICATED
        and request.user.is_authenticated
        and not survey.allow_any_authenticated
    ):
        # Check if user has a valid invitation
        user_email = request.user.email
        has_invitation = SurveyAccessToken.objects.filter(
            survey=survey,
            for_authenticated=True,
            note__icontains=f"Invited: {user_email}",
        ).exists()

        if not has_invitation:
            messages.error(
                request,
                "You do not have permission to access this survey. "
                "This survey is invitation-only.",
            )
            return redirect("surveys:closed", slug=slug)

    # If survey requires CAPTCHA for anonymous users
    if (
        request.method == "POST"
        and not request.user.is_authenticated
        and survey.captcha_required
    ):
        if not _verify_captcha(request):
            messages.error(request, "CAPTCHA verification failed.")
            return redirect("surveys:take", slug=slug)

    return _handle_participant_submission(request, survey, token_obj=None)


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take_unlisted(request: HttpRequest, slug: str, key: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    if (
        not survey.is_live()
        or survey.visibility != Survey.Visibility.UNLISTED
        or survey.unlisted_key != key
    ):
        # Determine specific reason if survey exists but is closed
        if (
            survey.visibility == Survey.Visibility.UNLISTED
            and survey.unlisted_key == key
        ):
            if not survey.is_live():
                from django.utils import timezone

                now = timezone.now()
                if survey.status != Survey.Status.PUBLISHED:
                    return redirect("surveys:closed", slug=slug)
                elif survey.start_at and survey.start_at > now:
                    return redirect(f"/surveys/{slug}/closed/?reason=not_started")
                elif survey.end_at and now > survey.end_at:
                    return redirect(f"/surveys/{slug}/closed/?reason=ended")
                elif survey.max_responses and hasattr(survey, "responses"):
                    if survey.responses.count() >= survey.max_responses:
                        return redirect(f"/surveys/{slug}/closed/?reason=max_responses")
        raise Http404()
    if (
        request.method == "POST"
        and not request.user.is_authenticated
        and survey.captcha_required
    ):
        if not _verify_captcha(request):
            messages.error(request, "CAPTCHA verification failed.")
            return redirect("surveys:take_unlisted", slug=slug, key=key)
    return _handle_participant_submission(request, survey, token_obj=None)


@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take_token(request: HttpRequest, slug: str, token: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    if not survey.is_live() or survey.visibility != Survey.Visibility.TOKEN:
        if survey.visibility == Survey.Visibility.TOKEN and not survey.is_live():
            # Survey exists and has correct visibility but is closed
            from django.utils import timezone

            now = timezone.now()
            if survey.status != Survey.Status.PUBLISHED:
                return redirect("surveys:closed", slug=slug)
            elif survey.start_at and survey.start_at > now:
                return redirect(f"/surveys/{slug}/closed/?reason=not_started")
            elif survey.end_at and now > survey.end_at:
                return redirect(f"/surveys/{slug}/closed/?reason=ended")
            elif survey.max_responses and hasattr(survey, "responses"):
                if survey.responses.count() >= survey.max_responses:
                    return redirect(f"/surveys/{slug}/closed/?reason=max_responses")
        raise Http404()
    tok = get_object_or_404(SurveyAccessToken, survey=survey, token=token)
    if not tok.is_valid():
        # Token expired or already used - redirect to closed page
        if tok.used_at:
            return redirect(f"/surveys/{slug}/closed/?reason=token_used")
        else:
            return redirect(f"/surveys/{slug}/closed/?reason=token_expired")
    if (
        request.method == "POST"
        and not request.user.is_authenticated
        and survey.captcha_required
    ):
        if not _verify_captcha(request):
            messages.error(request, "CAPTCHA verification failed.")
            return redirect("surveys:take_token", slug=slug, token=token)
    return _handle_participant_submission(request, survey, token_obj=tok)


def _handle_participant_submission(
    request: HttpRequest, survey: Survey, token_obj: SurveyAccessToken | None
) -> HttpResponse:
    # Block survey owner from taking their own survey
    if request.user.is_authenticated and survey.owner_id == request.user.id:
        messages.info(
            request,
            "You cannot submit responses to your own survey. Use Preview to test the survey.",
        )
        return redirect("surveys:dashboard", slug=survey.slug)

    # Disallow collecting patient data on non-authenticated visibilities unless explicitly acknowledged at publish.
    collects_patient = _survey_collects_patient_data(survey)
    if (
        collects_patient
        and survey.visibility != Survey.Visibility.AUTHENTICATED
        and not survey.no_patient_data_ack
    ):
        messages.error(
            request,
            "This survey cannot be taken without authentication due to patient data.",
        )
        raise Http404()

    # Get or create progress record
    progress, _ = _get_or_create_progress(request, survey, token_obj)

    if request.method == "POST":
        # Check if this is a draft save (AJAX request)
        is_draft = request.POST.get("action") == "save_draft"
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Prevent duplicate submission for tokenized link
        if token_obj and SurveyResponse.objects.filter(access_token=token_obj).exists():
            return redirect(f"/surveys/{survey.slug}/closed/?reason=token_used")

        answers = {}
        for q in survey.questions.all():
            key = f"q_{q.id}"
            value = (
                request.POST.getlist(key)
                if q.type in {"mc_multi", "orderable"}
                else request.POST.get(key)
            )
            # Only save non-empty answers for draft
            if value or not is_draft:
                answers[str(q.id)] = value

        # If this is a draft save, update progress and return JSON
        if is_draft and is_ajax:
            progress.update_progress(answers)
            return JsonResponse(
                {
                    "success": True,
                    "progress": {
                        "percentage": progress.calculate_progress_percentage(),
                        "answered": progress.answered_count,
                        "total": progress.total_questions,
                    },
                }
            )

        # Professional details (non-encrypted)
        _, professional_fields, professional_ods = _get_professional_group_and_fields(
            survey
        )
        professional_payload = {}
        for field in professional_fields:
            val = request.POST.get(f"prof_{field}")
            if val:
                professional_payload[field] = val
            if professional_ods.get(field):
                ods_val = request.POST.get(f"prof_{field}_ods")
                if ods_val:
                    professional_payload[f"{field}_ods"] = ods_val

        resp = SurveyResponse(
            survey=survey,
            answers={
                **answers,
                **(
                    {"professional": professional_payload}
                    if professional_payload
                    else {}
                ),
            },
            submitted_by=request.user if request.user.is_authenticated else None,
            access_token=token_obj if token_obj else None,
        )
        # Demographics: only store if authenticated and key in session
        patient_group, demographics_fields = _get_patient_group_and_fields(survey)
        demo = {}
        for field in demographics_fields:
            val = request.POST.get(field)
            if val:
                demo[field] = val
        # Option 4: Re-derive KEK from stored credentials
        if demo:
            survey_key = get_survey_key_from_session(request, survey.slug)
            if survey_key:
                resp.store_demographics(survey_key, demo)

        try:
            resp.save()
        except Exception:
            messages.error(request, "You have already submitted this survey.")
            return redirect("surveys:take", slug=survey.slug)

        # Mark token as used
        if token_obj:
            token_obj.used_at = timezone.now()
            if request.user.is_authenticated:
                token_obj.used_by = request.user
            token_obj.save(update_fields=["used_at", "used_by"])

        # Delete progress record after successful submission
        if progress:
            progress.delete()

        messages.success(request, "Thank you for your response.")
        # Redirect to thank-you page
        return redirect("surveys:thank_you", slug=survey.slug)

    # GET: render using existing detail template
    _prepare_question_rendering(survey)
    qs = list(survey.questions.select_related("group").all())
    for i, q in enumerate(qs, start=1):
        setattr(q, "idx", i)
        prev_gid = qs[i - 2].group_id if i - 2 >= 0 else None
        next_gid = qs[i].group_id if i < len(qs) else None
        curr_gid = q.group_id
        setattr(q, "group_start", bool(curr_gid and curr_gid != prev_gid))
        setattr(q, "group_end", bool(curr_gid and curr_gid != next_gid))
    patient_group, demographics_fields = _get_patient_group_and_fields(survey)
    prof_group, professional_fields, professional_ods = (
        _get_professional_group_and_fields(survey)
    )
    show_patient_details = patient_group is not None
    show_professional_details = prof_group is not None
    ctx = {
        "survey": survey,
        "questions": qs,
        "show_patient_details": show_patient_details,
        "demographics_fields": demographics_fields,
        "demographic_defs": DEMOGRAPHIC_FIELD_DEFS,
        "demographics_fields_with_labels": [
            (k, DEMOGRAPHIC_FIELD_DEFS[k]) for k in demographics_fields
        ],
        "show_professional_details": show_professional_details,
        "professional_fields": professional_fields,
        "professional_defs": PROFESSIONAL_FIELD_DEFS,
        "professional_ods": professional_ods,
        "professional_field_datasets": PROFESSIONAL_FIELD_TO_DATASET,
        "is_preview": False,  # Flag to indicate this is public submission
        # Progress tracking
        "show_progress": True,
        "progress_percentage": progress.calculate_progress_percentage(),
        "answered_count": progress.answered_count,
        "total_questions": progress.total_questions,
        "saved_answers": progress.partial_answers,
        "last_saved": progress.updated_at if progress.answered_count > 0 else None,
    }
    return render(request, "surveys/detail.html", ctx)


@require_http_methods(["GET"])
def survey_closed(request: HttpRequest, slug: str) -> HttpResponse:
    """Landing page for surveys that are closed, ended, or at capacity.

    Provides user-friendly messaging instead of 404 errors.
    Accepts optional 'reason' query parameter to customize the message.
    """
    survey = Survey.objects.filter(slug=slug).first()
    reason = request.GET.get("reason", "closed")
    return render(
        request, "surveys/survey_closed.html", {"survey": survey, "reason": reason}
    )


@require_http_methods(["GET"])
def survey_thank_you(request: HttpRequest, slug: str) -> HttpResponse:
    """Simple post-submission landing page for participants.

    Does not leak whether a survey exists beyond being reachable from a valid submission.
    """
    survey = Survey.objects.filter(slug=slug).first()
    # Render generic thank you even if survey missing to avoid information leakage
    return render(
        request, "surveys/thank_you.html", {"survey": survey, "is_preview": False}
    )


@login_required
@require_http_methods(["GET"])
def survey_preview_thank_you(request: HttpRequest, slug: str) -> HttpResponse:
    """Thank you page for preview mode - no data is saved."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)
    return render(
        request,
        "surveys/preview_thank_you.html",
        {"survey": survey, "is_preview": True},
    )


@login_required
@require_http_methods(["GET", "POST"])
def survey_tokens(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    if request.method == "POST":
        try:
            count = int(request.POST.get("count", "0"))
        except ValueError:
            count = 0
        note = (request.POST.get("note") or "").strip()
        from django.utils.dateparse import parse_datetime

        expires_raw = request.POST.get("expires_at")
        expires_at = parse_datetime(expires_raw) if expires_raw else None
        created = []
        for _ in range(max(0, min(count, 1000))):
            t = SurveyAccessToken(
                survey=survey,
                token=secrets.token_urlsafe(24),
                created_by=request.user,
                expires_at=expires_at,
                note=note,
            )
            t.save()
            created.append(t)
        messages.success(request, f"Created {len(created)} tokens.")
        return redirect("surveys:tokens", slug=slug)
    tokens = survey.access_tokens.order_by("-created_at")[:500]
    return render(request, "surveys/tokens.html", {"survey": survey, "tokens": tokens})


@login_required
def survey_tokens_export_csv(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["token", "created_at", "expires_at", "used_at", "used_by", "note"])
    for t in survey.access_tokens.all():
        writer.writerow(
            [
                t.token,
                t.created_at.isoformat(),
                t.expires_at.isoformat() if t.expires_at else "",
                t.used_at.isoformat() if t.used_at else "",
                (t.used_by_id or ""),
                t.note,
            ]
        )
    resp = HttpResponse(output.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f"attachment; filename=survey_{survey.id}_tokens.csv"
    return resp


@login_required
@require_http_methods(["POST"])
def survey_style_update(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    style = survey.style or {}
    # Accept simple fields; ignore if blank to allow fallback to platform defaults
    for key in (
        "title",
        "icon_url",
        "theme_name",
        "font_heading",
        "font_body",
        "primary_color",
        "font_css_url",
    ):
        val = (request.POST.get(key) or "").strip()
        if val:
            style[key] = val
        elif key in style:
            # allow clearing by leaving blank
            style.pop(key)
    survey.style = style
    survey.save(update_fields=["style"])
    messages.success(request, "Style updated.")
    return redirect("surveys:dashboard", slug=slug)


"""
Deprecated Collections SSR views were removed. Repeats are created and managed
from the Groups UI and bulk upload. Collections remain as backend entities only.
"""


@login_required
def survey_groups(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    can_edit = can_edit_survey(request.user, survey)
    groups_qs = survey.question_groups.annotate(
        q_count=models.Count(
            "surveyquestion", filter=models.Q(surveyquestion__survey=survey)
        )
    )
    # Apply explicit saved order if present in survey.style
    order_ids = []
    style = survey.style or {}
    if isinstance(style.get("group_order"), list):
        order_ids = [int(gid) for gid in style["group_order"] if str(gid).isdigit()]
    groups_map = {g.id: g for g in groups_qs}
    ordered = [groups_map[g_id] for g_id in order_ids if g_id in groups_map]
    remaining = [g for g in groups_qs if g.id not in order_ids]
    groups = ordered + sorted(remaining, key=lambda g: g.name.lower())
    # Apply style overrides so navigation reflects survey branding while managing groups
    style = survey.style or {}
    brand_overrides = {
        "title": style.get("title"),
        "icon_url": style.get("icon_url"),
        "theme_name": style.get("theme_name"),
        "font_heading": style.get("font_heading"),
        "font_body": style.get("font_body"),
        "primary_hex": style.get("primary_color"),
        "font_css_url": style.get("font_css_url"),
    }
    # Map groups to any repeats (collections) they participate in
    group_repeat_map: dict[int, list[CollectionDefinition]] = {}
    for item in CollectionItem.objects.select_related("collection", "group").filter(
        collection__survey=survey, group__isnull=False
    ):
        group_repeat_map.setdefault(item.group_id, []).append(item.collection)

    # Prepare display info for repeats
    repeat_info: dict[int, dict] = {}
    for g in groups:
        cols = group_repeat_map.get(g.id, [])
        if cols:
            info_list = []
            for c in cols:
                cap = (
                    "Unlimited"
                    if (c.max_count is None or int(c.max_count) <= 0)
                    else str(c.max_count)
                )
                parent_note = f" (child of {c.parent.name})" if c.parent_id else ""
                info_list.append(f"{c.name} — max {cap}{parent_note}")
            repeat_info[g.id] = {"is_repeated": True, "tooltip": "; ".join(info_list)}
        else:
            repeat_info[g.id] = {"is_repeated": False, "tooltip": ""}

    existing_repeats = list(
        CollectionDefinition.objects.filter(survey=survey).order_by("name")
    )

    # Check if survey is in readonly mode due to tier downgrade
    patient_data_readonly = survey.is_patient_data_readonly()
    if patient_data_readonly:
        # Override can_edit for patient data surveys owned by downgraded users
        can_edit = False
        messages.warning(
            request,
            _(
                "This survey contains patient data and is currently read-only. "
                "Your account tier does not include patient data collection. "
                "Upgrade to Pro or higher to edit this survey."
            ),
        )

    ctx = {
        "survey": survey,
        "groups": groups,
        "can_edit": can_edit,
        "repeat_info": repeat_info,
        "existing_repeats": existing_repeats,
        "patient_data_readonly": patient_data_readonly,
    }
    if any(
        v for k, v in brand_overrides.items() if k != "primary_hex"
    ) or brand_overrides.get("primary_hex"):
        ctx["brand"] = {
            "title": brand_overrides.get("title")
            or getattr(settings, "BRAND_TITLE", "CheckTick"),
            "icon_url": brand_overrides.get("icon_url")
            or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
            "theme_name": brand_overrides.get("theme_name")
            or getattr(settings, "BRAND_THEME", "checktick"),
            "font_heading": brand_overrides.get("font_heading")
            or getattr(
                settings,
                "BRAND_FONT_HEADING",
                "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
            ),
            "font_body": brand_overrides.get("font_body")
            or getattr(
                settings,
                "BRAND_FONT_BODY",
                "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            ),
            "font_css_url": brand_overrides.get("font_css_url")
            or getattr(
                settings,
                "BRAND_FONT_CSS_URL",
                "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
            ),
            "primary": hex_to_oklch(brand_overrides.get("primary_hex") or ""),
        }
    return render(request, "surveys/groups.html", ctx)


@login_required
@require_http_methods(["POST"])
def survey_groups_repeat_create(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Create a repeat (CollectionDefinition) from selected groups.
    Optional parent_id nests this repeat one level under an existing repeat.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Please provide a name for the repeat.")
        return redirect("surveys:groups", slug=slug)
    min_count = request.POST.get("min_count") or "0"
    max_count_raw = (request.POST.get("max_count") or "").strip().lower()
    max_count: int | None
    if max_count_raw in ("", "unlimited", "-1"):
        max_count = None
    else:
        try:
            max_count = int(max_count_raw)
            if max_count < 1:
                max_count = None
        except Exception:
            max_count = None
    # Cardinality: one iff max_count == 1
    cardinality = (
        CollectionDefinition.Cardinality.ONE
        if (max_count == 1)
        else CollectionDefinition.Cardinality.MANY
    )

    # Parse group ids
    gids_csv = request.POST.get("group_ids", "")
    gid_list = [int(x) for x in gids_csv.split(",") if x.isdigit()]
    # Keep only those attached to this survey
    valid_ids = set(
        survey.question_groups.filter(id__in=gid_list).values_list("id", flat=True)
    )
    gid_list = [g for g in gid_list if g in valid_ids]
    if not gid_list:
        messages.error(request, "Select at least one group to include in the repeat.")
        return redirect("surveys:groups", slug=slug)

    # Ensure unique key per survey
    def _unique_key(base: str) -> str:
        k = slugify(base)
        if not k:
            k = "repeat"
        cand = k
        i = 2
        while CollectionDefinition.objects.filter(survey=survey, key=cand).exists():
            cand = f"{k}-{i}"
            i += 1
        return cand

    cd = CollectionDefinition(
        survey=survey,
        key=_unique_key(name),
        name=name,
        cardinality=cardinality,
        min_count=int(min_count) if str(min_count).isdigit() else 0,
        max_count=max_count,
    )
    # Optional parent
    parent_id = request.POST.get("parent_id")
    if parent_id and str(parent_id).isdigit():
        parent = CollectionDefinition.objects.filter(
            id=int(parent_id), survey=survey
        ).first()
        if parent:
            cd.parent = parent
    try:
        cd.full_clean()
    except Exception as e:
        messages.error(request, f"Invalid repeat configuration: {e}")
        return redirect("surveys:groups", slug=slug)
    cd.save()

    # Create items in the order provided
    # Keep current ordering of groups in the survey where possible
    order_index = 0
    for gid in gid_list:
        grp = survey.question_groups.filter(id=gid).first()
        if not grp:
            continue
        CollectionItem.objects.create(
            collection=cd,
            item_type=CollectionItem.ItemType.GROUP,
            group=grp,
            order=order_index,
        )
        order_index += 1

    # If we set a parent, add this as a child item under the parent
    if cd.parent_id:
        max_item_order = (
            CollectionItem.objects.filter(collection=cd.parent)
            .order_by("-order")
            .values_list("order", flat=True)
            .first()
        )
        next_idx = (max_item_order + 1) if max_item_order is not None else 0
        CollectionItem.objects.create(
            collection=cd.parent,
            item_type=CollectionItem.ItemType.COLLECTION,
            child_collection=cd,
            order=next_idx,
        )

    messages.success(request, "Repeat created and groups added.")
    return redirect("surveys:groups", slug=slug)


@login_required
@require_http_methods(["POST"])
def survey_group_repeat_remove(
    request: HttpRequest, slug: str, gid: int
) -> HttpResponse:
    """Remove the given group from any repeats (collections) in this survey.

    If a collection becomes empty after removal, delete it as well. This provides
    a simple toggle-like UX from the Groups page to undo a repeat association.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid)
    # Only allow removing if the group is attached to this survey
    if not survey.question_groups.filter(id=group.id).exists():
        return HttpResponse(status=404)

    # Remove items linking this group within this survey's collections
    items_qs = CollectionItem.objects.filter(
        collection__survey=survey, item_type=CollectionItem.ItemType.GROUP, group=group
    )
    affected_collections = set(items_qs.values_list("collection_id", flat=True))
    deleted, _ = items_qs.delete()

    # Re-number remaining items per affected collection and delete empties
    for cid in affected_collections:
        col = CollectionDefinition.objects.filter(id=cid, survey=survey).first()
        if not col:
            continue
        remaining = list(col.items.order_by("order", "id"))
        if not remaining:
            # If this collection is a child of a parent collection, remove its link too
            CollectionItem.objects.filter(child_collection=col).delete()
            col.delete()
            continue
        # Compact orders
        for idx, it in enumerate(remaining):
            if it.order != idx:
                it.order = idx
                it.save(update_fields=["order"])

    if deleted:
        messages.success(request, "Group removed from repeat.")
    else:
        messages.info(request, "This group was not part of a repeat.")
    return redirect("surveys:groups", slug=slug)


@login_required
@require_http_methods(["POST"])
def survey_groups_reorder(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    order_csv = request.POST.get("order", "")
    ids = [int(i) for i in order_csv.split(",") if i.isdigit()]
    # Filter to ids that belong to this survey
    # Only allow reordering groups that belong to this survey (owner may differ; permission handled above)
    valid_ids = set(
        survey.question_groups.filter(id__in=ids).values_list("id", flat=True)
    )
    ids = [i for i in ids if i in valid_ids]
    style = survey.style or {}
    style["group_order"] = ids
    survey.style = style
    survey.save(update_fields=["style"])
    messages.success(request, "Group order updated.")
    return redirect("surveys:groups", slug=slug)


@login_required
@require_http_methods(["GET", "POST"])
def org_users(request: HttpRequest, org_id: int) -> HttpResponse:
    User = get_user_model()
    org = get_object_or_404(Organization, id=org_id)
    if not can_manage_org_users(request.user, org):
        raise Http404
    # Admin can list and edit memberships (promote/demote within org, but not self-promote to superuser etc.)
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        email = (request.POST.get("email") or "").strip().lower()
        target_user = None
        if email:
            target_user = User.objects.filter(email__iexact=email).first()
        if not target_user and user_id:
            target_user = get_object_or_404(User, id=user_id)
        role = request.POST.get("role")
        if action == "add" and target_user:
            mem, created = OrganizationMembership.objects.update_or_create(
                organization=org,
                user=target_user,
                defaults={"role": role or OrganizationMembership.Role.VIEWER},
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=org,
                action=AuditLog.Action.ADD if created else AuditLog.Action.UPDATE,
                target_user=target_user,
                metadata={"role": mem.role},
            )
            messages.success(request, "User added/updated in organization.")
        elif action == "update":
            mem = get_object_or_404(
                OrganizationMembership, organization=org, user=target_user
            )
            # Prevent self-demotion lockout: allow but warn (optional). For simplicity, allow update.
            if role in dict(OrganizationMembership.Role.choices):
                mem.role = role
                mem.save(update_fields=["role"])
                AuditLog.objects.create(
                    actor=request.user,
                    scope=AuditLog.Scope.ORGANIZATION,
                    organization=org,
                    action=AuditLog.Action.UPDATE,
                    target_user=mem.user,
                    metadata={"role": mem.role},
                )
                messages.success(request, "Membership updated.")
        elif action == "remove":
            mem = get_object_or_404(
                OrganizationMembership, organization=org, user=target_user
            )
            # Prevent self-removal if this is the last admin
            if (
                mem.user_id == request.user.id
                and mem.role == OrganizationMembership.Role.ADMIN
            ):
                messages.error(
                    request, "You cannot remove yourself as an organization admin."
                )
                return redirect("surveys:org_users", org_id=org.id)
            mem.delete()
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=org,
                action=AuditLog.Action.REMOVE,
                target_user=mem.user,
                metadata={"role": mem.role},
            )
            messages.success(request, "User removed from organization.")
        return redirect("surveys:org_users", org_id=org.id)

    members = (
        OrganizationMembership.objects.select_related("user")
        .filter(organization=org)
        .order_by("user__username")
    )
    return render(request, "surveys/org_users.html", {"org": org, "members": members})


@login_required
@require_http_methods(["GET", "POST"])
def survey_users(request: HttpRequest, slug: str) -> HttpResponse:
    User = get_user_model()
    survey = get_object_or_404(Survey, slug=slug)
    # Only users who can manage survey users should access this view
    can_manage = can_manage_survey_users(request.user, survey)
    if not can_manage:
        raise Http404

    if request.method == "POST":
        if not can_manage:
            return HttpResponse(status=403)
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        email = (request.POST.get("email") or "").strip().lower()
        target_user = None
        if email:
            target_user = User.objects.filter(email__iexact=email).first()
        if not target_user and user_id:
            target_user = get_object_or_404(User, id=user_id)
        role = request.POST.get("role")
        if role and role not in dict(SurveyMembership.Role.choices):
            return HttpResponse(status=400)

        # Check tier limits for collaboration
        if action == "add" and target_user:
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
            can_add, limit_reason = check_collaboration_limit(
                request.user, collaboration_type
            )
            if not can_add:
                messages.error(request, limit_reason)
                return redirect("surveys:survey_users", slug=survey.slug)

            # Check per-survey collaborator limit
            can_add_to_survey, survey_reason = check_collaborators_per_survey_limit(
                survey
            )
            if not can_add_to_survey:
                messages.error(request, survey_reason)
                return redirect("surveys:survey_users", slug=survey.slug)

        if action == "add" and target_user:
            smem, created = SurveyMembership.objects.update_or_create(
                survey=survey,
                user=target_user,
                defaults={"role": role or SurveyMembership.Role.VIEWER},
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.ADD if created else AuditLog.Action.UPDATE,
                target_user=target_user,
                metadata={"role": smem.role},
            )
            messages.success(request, "User added to survey.")
        elif action == "update":
            mem = get_object_or_404(SurveyMembership, survey=survey, user=target_user)
            # creators cannot promote to org admin here; only role is creator/viewer at survey level
            mem.role = role or SurveyMembership.Role.VIEWER
            mem.save(update_fields=["role"])
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.UPDATE,
                target_user=mem.user,
                metadata={"role": mem.role},
            )
            messages.success(request, "Membership updated.")
        elif action == "remove":
            mem = get_object_or_404(SurveyMembership, survey=survey, user=target_user)
            mem.delete()
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.REMOVE,
                target_user=mem.user,
                metadata={"role": mem.role},
            )
            messages.success(request, "User removed from survey.")
        return redirect("surveys:survey_users", slug=survey.slug)

    memberships = (
        SurveyMembership.objects.select_related("user")
        .filter(survey=survey)
        .order_by("user__username")
    )
    return render(
        request,
        "surveys/survey_users.html",
        {"survey": survey, "memberships": memberships, "can_manage": can_manage},
    )


@login_required
def user_management_hub(request: HttpRequest) -> HttpResponse:
    from .models import Team, TeamMembership

    # Single organisation model: pick the organisation where user is ADMIN (or None)
    org = (
        Organization.objects.filter(
            memberships__user=request.user,
            memberships__role=OrganizationMembership.Role.ADMIN,
        )
        .select_related("owner")
        .first()
    )

    # Get teams where user is ADMIN
    managed_teams_qs = Team.objects.filter(
        memberships__user=request.user, memberships__role=TeamMembership.Role.ADMIN
    ).select_related("owner", "organization")

    if request.method == "POST":
        # HTMX quick add flows
        scope = request.POST.get("scope")
        email = (request.POST.get("email") or "").strip().lower()
        role = request.POST.get("role")
        User = get_user_model()

        # Handle team creation (org admins only)
        if scope == "create_team":
            if not org or not can_manage_org_users(request.user, org):
                return HttpResponse("Not authorized to create teams", status=403)
            team_name = (request.POST.get("team_name") or "").strip()
            team_size = request.POST.get("team_size", Team.Size.SMALL)
            if not team_name:
                return HttpResponse("Team name is required", status=400)
            if team_size not in dict(Team.Size.choices):
                team_size = Team.Size.SMALL
            # Create team under this org
            new_team = Team.objects.create(
                name=team_name,
                owner=request.user,
                organization=org,
                size=team_size,
            )
            # Add creator as team admin
            TeamMembership.objects.create(
                team=new_team,
                user=request.user,
                role=TeamMembership.Role.ADMIN,
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=org,
                action=AuditLog.Action.CREATE,
                metadata={
                    "team_id": new_team.id,
                    "team_name": new_team.name,
                    "team_size": new_team.size,
                },
            )
            return HttpResponse(f"Team '{team_name}' created", status=200)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return HttpResponse("User not found by email", status=400)

        if scope == "org":
            if not org or not can_manage_org_users(request.user, org):
                return HttpResponse(status=403)
            mem, created = OrganizationMembership.objects.update_or_create(
                organization=org,
                user=user,
                defaults={"role": role or OrganizationMembership.Role.VIEWER},
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=org,
                action=AuditLog.Action.ADD if created else AuditLog.Action.UPDATE,
                target_user=user,
                metadata={"role": mem.role},
            )
            return HttpResponse("Added/updated in organisation", status=200)

        elif scope == "team":
            team_id = request.POST.get("team_id")
            if not team_id:
                return HttpResponse("Team ID required", status=400)
            team = get_object_or_404(Team, id=team_id)

            # Check if user can manage this team
            is_team_admin = TeamMembership.objects.filter(
                team=team, user=request.user, role=TeamMembership.Role.ADMIN
            ).exists()
            is_org_admin = (
                team.organization
                and OrganizationMembership.objects.filter(
                    organization=team.organization,
                    user=request.user,
                    role=OrganizationMembership.Role.ADMIN,
                ).exists()
            )

            if not (is_team_admin or is_org_admin):
                return HttpResponse(status=403)

            # Check team capacity
            if not team.can_add_members():
                return HttpResponse(
                    f"Team is at maximum capacity ({team.max_members} members)",
                    status=400,
                )

            mem, created = TeamMembership.objects.update_or_create(
                team=team,
                user=user,
                defaults={"role": role or TeamMembership.Role.VIEWER},
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=team.organization,
                action=AuditLog.Action.ADD if created else AuditLog.Action.UPDATE,
                target_user=user,
                metadata={"role": mem.role, "team_id": team.id, "team_name": team.name},
            )
            return HttpResponse("Added/updated in team", status=200)

        elif scope == "survey":
            slug = request.POST.get("slug") or ""
            survey = get_object_or_404(Survey, slug=slug)
            if not can_manage_survey_users(request.user, survey):
                return HttpResponse(status=403)
            smem, created = SurveyMembership.objects.update_or_create(
                survey=survey,
                user=user,
                defaults={"role": role or SurveyMembership.Role.VIEWER},
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.ADD if created else AuditLog.Action.UPDATE,
                target_user=user,
                metadata={"role": smem.role},
            )
            return HttpResponse("Added/updated in survey", status=200)

    # Build users grouped by surveys for this organisation
    grouped = []
    manageable_surveys = Survey.objects.none()
    members = OrganizationMembership.objects.none()
    org_teams = []

    if org:
        members = (
            OrganizationMembership.objects.select_related("user")
            .filter(organization=org)
            .order_by("user__username")
        )
        manageable_surveys = (
            Survey.objects.filter(organization=org)
            .select_related("organization")
            .order_by("name")
        )
        for sv in manageable_surveys:
            sv_members = (
                SurveyMembership.objects.select_related("user")
                .filter(survey=sv)
                .order_by("user__username")
            )
            grouped.append({"survey": sv, "members": sv_members})

        # Get teams within this organisation
        org_teams_qs = Team.objects.filter(organization=org).prefetch_related(
            "memberships__user"
        )
        for team in org_teams_qs:
            team_members = team.memberships.select_related("user").order_by(
                "user__username"
            )
            org_teams.append({"team": team, "members": team_members})

    # Build data for teams user manages (not within their org)
    managed_teams = []
    for team in managed_teams_qs:
        team_members = team.memberships.select_related("user").order_by(
            "user__username"
        )
        managed_teams.append({"team": team, "members": team_members})

    return render(
        request,
        "surveys/user_management_hub.html",
        {
            "org": org,
            "members": members,
            "grouped": grouped,
            "org_teams": org_teams,
            "managed_teams": managed_teams,
        },
    )


@login_required
@require_http_methods(["POST"])
def survey_group_create(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    name = request.POST.get("name", "").strip() or "New Group"
    g = QuestionGroup.objects.create(name=name, owner=request.user)
    survey.question_groups.add(g)
    messages.success(request, "Group created.")
    # After creating, return to Groups view so the new group appears immediately
    return redirect("surveys:groups", slug=slug)


@login_required
@require_http_methods(["POST"])
def survey_group_edit(request: HttpRequest, slug: str, gid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    group.name = request.POST.get("name", group.name)
    group.description = request.POST.get("description", group.description)
    group.save(update_fields=["name", "description"])
    messages.success(request, "Group updated.")
    return redirect("surveys:dashboard", slug=slug)


@login_required
@require_http_methods(["POST"])
def survey_group_delete(request: HttpRequest, slug: str, gid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    # Detach from this survey; optionally delete the group if not used elsewhere
    survey.question_groups.remove(group)
    if not group.surveys.exists():
        group.delete()
    messages.success(request, "Group deleted.")
    # After deletion, return to Groups view so the list refreshes in place
    return redirect("surveys:groups", slug=slug)


@login_required
@require_http_methods(["POST"])
def survey_group_create_from_template(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    template = request.POST.get("template")
    if template == "patient_details_encrypted":
        g = QuestionGroup.objects.create(
            name="Patient details (encrypted)",
            description="Optional demographics captured securely.",
            owner=request.user,
            schema={
                "template": "patient_details_encrypted",
                # default initial selection per spec
                "fields": PATIENT_TEMPLATE_DEFAULT_FIELDS.copy(),
            },
        )
        survey.question_groups.add(g)
        messages.success(
            request,
            "Patient details group created. These fields will appear at the bottom of the participant form.",
        )
    elif template == "professional_details":
        g = QuestionGroup.objects.create(
            name="Professional details",
            description="Information about the professional.",
            owner=request.user,
            schema={
                "template": "professional_details",
                "fields": PROFESSIONAL_TEMPLATE_DEFAULT_FIELDS.copy(),
                # ODS toggles per field
                "ods": PROFESSIONAL_TEMPLATE_DEFAULT_ODS.copy(),
            },
        )
        survey.question_groups.add(g)
        messages.success(request, "Professional details group created.")
    else:
        messages.error(request, "Unknown template.")
    return redirect("surveys:groups", slug=slug)


def get_survey_key_from_session(request: HttpRequest, survey_slug: str) -> bytes | None:
    """
    Option 4: Re-derive KEK from stored credentials on each request.
    This provides forward secrecy - no key material persists in sessions.
    Credentials are encrypted with session-specific key.
    Returns None if session expired (>30 min) or credentials invalid.
    """
    import base64
    from datetime import timedelta

    from django.utils import timezone

    from .utils import decrypt_sensitive

    # Check if unlock is valid
    if not request.session.get("unlock_credentials"):
        return None

    # Check timestamp (30 minute timeout)
    verified_at_str = request.session.get("unlock_verified_at")
    if not verified_at_str:
        return None

    verified_at = timezone.datetime.fromisoformat(verified_at_str)
    # Ensure timezone-aware comparison
    if timezone.is_naive(verified_at):
        verified_at = timezone.make_aware(verified_at)

    if timezone.now() - verified_at > timedelta(minutes=30):
        # Session expired - clear credentials
        request.session.pop("unlock_credentials", None)
        request.session.pop("unlock_method", None)
        request.session.pop("unlock_verified_at", None)
        request.session.pop("unlock_survey_slug", None)
        return None

    # Check survey matches
    if request.session.get("unlock_survey_slug") != survey_slug:
        return None

    # Decrypt credentials
    try:
        session_key = request.session.session_key
        if not session_key:
            return None

        encrypted_creds_b64 = request.session.get("unlock_credentials")
        encrypted_creds = base64.b64decode(encrypted_creds_b64)
        creds = decrypt_sensitive(session_key.encode("utf-8"), encrypted_creds)

        # Re-derive KEK based on method
        unlock_method = request.session.get("unlock_method")
        survey = Survey.objects.get(slug=survey_slug)

        if unlock_method == "password":
            password = creds.get("password")
            if password:
                return survey.unlock_with_password(password)
        elif unlock_method == "recovery":
            recovery_phrase = creds.get("recovery_phrase")
            if recovery_phrase:
                return survey.unlock_with_recovery(recovery_phrase)
        elif unlock_method == "oidc":
            oidc_provider = creds.get("oidc_provider")
            oidc_subject = creds.get("oidc_subject")
            if oidc_provider and oidc_subject:
                return survey.unlock_with_oidc(request.user)
        elif unlock_method == "organization_recovery":
            organization_id = creds.get("organization_id")
            if organization_id:
                org = Organization.objects.get(id=organization_id)
                return survey.unlock_with_org_key(org)
        elif unlock_method == "legacy":
            legacy_key_b64 = creds.get("legacy_key")
            if legacy_key_b64:
                return base64.b64decode(legacy_key_b64)

        return None
    except Exception:
        # If anything fails, clear session and return None
        request.session.pop("unlock_credentials", None)
        request.session.pop("unlock_method", None)
        request.session.pop("unlock_verified_at", None)
        request.session.pop("unlock_survey_slug", None)
        return None


def _get_or_create_progress(
    request: HttpRequest, survey: Survey, token_obj: SurveyAccessToken | None
):
    """
    Get or create progress record for current user/session.
    Returns tuple of (SurveyProgress, created: bool)
    """
    from datetime import timedelta

    total_questions = survey.questions.count()
    expires_at = timezone.now() + timedelta(days=30)

    if request.user.is_authenticated:
        # Authenticated user
        progress, created = SurveyProgress.objects.get_or_create(
            survey=survey,
            user=request.user,
            defaults={
                "total_questions": total_questions,
                "expires_at": expires_at,
                "access_token": token_obj,
            },
        )
    else:
        # Anonymous user - use session
        if not request.session.session_key:
            request.session.create()

        progress, created = SurveyProgress.objects.get_or_create(
            survey=survey,
            session_key=request.session.session_key,
            defaults={
                "total_questions": total_questions,
                "expires_at": expires_at,
                "access_token": token_obj,
            },
        )

    if not created:
        # Update expiry on access and total questions if survey changed
        progress.expires_at = expires_at
        progress.total_questions = total_questions
        progress.save(update_fields=["expires_at", "total_questions"])

    return progress, created


@login_required
@require_http_methods(["GET", "POST"])
def survey_unlock(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Survey unlock page for encrypted surveys.

    Supports:
    1. OIDC automatic unlock (for SSO users)
    2. Dual encryption (password/recovery phrase)
    3. Legacy key verification (backward compatibility)
    """
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)

    # Ensure we have fresh data from database
    survey.refresh_from_db()

    # Try OIDC automatic unlock first (if available and not already unlocked)
    if (
        survey.has_oidc_encryption()
        and survey.can_user_unlock_automatically(request.user)
        and request.session.get("unlock_survey_slug") != slug
    ):
        kek = survey.unlock_with_oidc(request.user)
        if kek:
            # Log OIDC automatic unlock
            from .models import AuditLog

            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                action=AuditLog.Action.UPDATE,
                survey=survey,
                target_user=request.user,
                metadata={"unlock_method": "oidc_automatic"},
            )

            # Store OIDC unlock credentials for session
            import base64

            from django.utils import timezone

            from .utils import encrypt_sensitive

            session_key = request.session.session_key or request.session.create()

            # Store OIDC identity for re-derivation
            oidc_record = request.user.oidc
            encrypted_creds = encrypt_sensitive(
                session_key.encode("utf-8"),
                {
                    "oidc_provider": oidc_record.provider,
                    "oidc_subject": oidc_record.subject,
                    "survey_slug": slug,
                },
            )
            request.session["unlock_credentials"] = base64.b64encode(
                encrypted_creds
            ).decode("ascii")
            request.session["unlock_method"] = "oidc"
            request.session["unlock_verified_at"] = timezone.now().isoformat()
            request.session["unlock_survey_slug"] = slug

            messages.success(
                request,
                f"Survey automatically unlocked with your {oidc_record.provider.title()} account.",
            )
            return redirect("surveys:dashboard", slug=slug)

    # Determine unlock method based on form data
    unlock_method = request.POST.get(
        "unlock_method", "password"
    )  # 'password' or 'recovery'

    if request.method == "POST":
        kek = None

        # Try Option 2 dual encryption first (if available)
        if survey.has_dual_encryption():
            if unlock_method == "password":
                password = request.POST.get("password", "").strip()
                if password:
                    kek = survey.unlock_with_password(password)
                    if kek:
                        # Log successful password unlock
                        from .models import AuditLog

                        AuditLog.objects.create(
                            actor=request.user,
                            scope=AuditLog.Scope.SURVEY,
                            action=AuditLog.Action.UPDATE,
                            survey=survey,
                            target_user=request.user,
                            metadata={"unlock_method": "password"},
                        )
                        # Option 4: Store credentials for re-derivation, not the KEK itself
                        # Encrypt password with session-specific key for forward secrecy
                        import base64

                        from django.utils import timezone

                        session_key = (
                            request.session.session_key or request.session.create()
                        )
                        from .utils import encrypt_sensitive

                        encrypted_creds = encrypt_sensitive(
                            session_key.encode("utf-8"),
                            {"password": password, "survey_slug": slug},
                        )
                        request.session["unlock_credentials"] = base64.b64encode(
                            encrypted_creds
                        ).decode("ascii")
                        request.session["unlock_method"] = "password"
                        request.session["unlock_verified_at"] = (
                            timezone.now().isoformat()
                        )
                        request.session["unlock_survey_slug"] = slug
                        messages.success(request, "Survey unlocked with password.")
                        return redirect("surveys:dashboard", slug=slug)
                    else:
                        messages.error(request, "Invalid password.")

            elif unlock_method == "recovery":
                recovery_phrase = request.POST.get("recovery_phrase", "").strip()
                if recovery_phrase:
                    kek = survey.unlock_with_recovery(recovery_phrase)
                    if kek:
                        # Log recovery phrase unlock (important for audit trail)
                        from .models import AuditLog

                        AuditLog.objects.create(
                            actor=request.user,
                            scope=AuditLog.Scope.SURVEY,
                            action=AuditLog.Action.UPDATE,
                            survey=survey,
                            target_user=request.user,
                            metadata={"unlock_method": "recovery_phrase"},
                        )
                        # Option 4: Store credentials for re-derivation, not the KEK itself
                        # Encrypt recovery phrase with session-specific key for forward secrecy
                        import base64

                        from django.utils import timezone

                        session_key = (
                            request.session.session_key or request.session.create()
                        )
                        from .utils import encrypt_sensitive

                        encrypted_creds = encrypt_sensitive(
                            session_key.encode("utf-8"),
                            {"recovery_phrase": recovery_phrase, "survey_slug": slug},
                        )
                        request.session["unlock_credentials"] = base64.b64encode(
                            encrypted_creds
                        ).decode("ascii")
                        request.session["unlock_method"] = "recovery"
                        request.session["unlock_verified_at"] = (
                            timezone.now().isoformat()
                        )
                        request.session["unlock_survey_slug"] = slug
                        messages.success(
                            request, "Survey unlocked with recovery phrase."
                        )
                        return redirect("surveys:dashboard", slug=slug)
                    else:
                        messages.error(request, "Invalid recovery phrase.")

        # Fallback to legacy key verification (old surveys)
        else:
            key = request.POST.get("key", "").encode("utf-8")
            if survey.key_hash and survey.key_salt:
                # Convert memoryview to bytes if needed (PostgreSQL BinaryField)
                key_hash = (
                    bytes(survey.key_hash)
                    if isinstance(survey.key_hash, memoryview)
                    else survey.key_hash
                )
                key_salt = (
                    bytes(survey.key_salt)
                    if isinstance(survey.key_salt, memoryview)
                    else survey.key_salt
                )

                if verify_key(key, key_hash, key_salt):
                    # Option 4: Store credentials for re-derivation (legacy path)
                    # For legacy, we store the raw key encrypted with session key
                    import base64

                    from django.utils import timezone

                    session_key = (
                        request.session.session_key or request.session.create()
                    )
                    from .utils import encrypt_sensitive

                    encrypted_creds = encrypt_sensitive(
                        session_key.encode("utf-8"),
                        {
                            "legacy_key": base64.b64encode(key).decode("ascii"),
                            "survey_slug": slug,
                        },
                    )
                    request.session["unlock_credentials"] = base64.b64encode(
                        encrypted_creds
                    ).decode("ascii")
                    request.session["unlock_method"] = "legacy"
                    request.session["unlock_verified_at"] = timezone.now().isoformat()
                    request.session["unlock_survey_slug"] = slug
                    messages.success(request, "Survey unlocked for this session.")
                    return redirect("surveys:dashboard", slug=slug)
            messages.error(request, "Invalid key.")

    context = {
        "survey": survey,
        "has_dual_encryption": survey.has_dual_encryption(),
        "has_oidc_encryption": survey.has_oidc_encryption(),
        "can_auto_unlock": survey.can_user_unlock_automatically(request.user),
        "recovery_hint": (
            survey.recovery_code_hint if survey.has_dual_encryption() else None
        ),
    }
    return render(request, "surveys/unlock.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def organization_key_recovery(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Organization key recovery view.

    Allows organization owners and admins to unlock surveys created by their members
    using the organization master key (Option 1: Key Escrow).

    This is for administrative recovery scenarios only and all access is audited.
    """
    survey = get_object_or_404(Survey, slug=slug)

    # Check if survey belongs to an organization
    if not survey.organization:
        messages.error(request, "This survey does not belong to an organization.")
        return redirect("surveys:dashboard", slug=slug)

    # Check if survey has organization encryption
    if not survey.has_org_encryption():
        messages.error(
            request, "This survey does not have organization-level encryption enabled."
        )
        return redirect("surveys:dashboard", slug=slug)

    # Check if user is owner or admin of the organization
    org = survey.organization
    is_org_owner = org.owner == request.user
    is_org_admin = OrganizationMembership.objects.filter(
        organization=org, user=request.user, role=OrganizationMembership.Role.ADMIN
    ).exists()

    if not (is_org_owner or is_org_admin):
        messages.error(
            request,
            "Only organization owners and admins can perform key recovery.",
        )
        return redirect("surveys:dashboard", slug=slug)

    # Don't allow recovery if user is the survey owner (they should use their own unlock methods)
    if survey.owner == request.user:
        messages.info(
            request,
            "You are the owner of this survey. Please use the regular unlock page instead.",
        )
        return redirect("surveys:unlock", slug=slug)

    if request.method == "POST":
        # Confirm the recovery action - requires EXACT "recover" (case-sensitive for security)
        confirm = request.POST.get("confirm", "").strip()
        if confirm != "recover":
            messages.error(
                request,
                'Please type "recover" to confirm this administrative key recovery action.',
            )
            # Re-render the page with the error message
            context = {
                "survey": survey,
                "organization": org,
                "is_org_owner": is_org_owner,
                "is_org_admin": is_org_admin,
                "survey_owner": survey.owner,
            }
            return render(request, "surveys/organization_key_recovery.html", context)

        # Attempt to unlock with organization key
        kek = survey.unlock_with_org_key(org)

        if kek:
            # Create audit log entry for key recovery
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                action=AuditLog.Action.KEY_RECOVERY,
                survey=survey,
                organization=org,
                target_user=survey.owner,
                metadata={
                    "recovery_method": "organization_master_key",
                    "survey_owner": survey.owner.username,
                    "org_role": "owner" if is_org_owner else "admin",
                },
            )

            # Store organization key recovery credentials in session
            import base64

            from .utils import encrypt_sensitive

            session_key = request.session.session_key or request.session.create()

            # Store organization ID for re-derivation (don't store the master key itself)
            encrypted_creds = encrypt_sensitive(
                session_key.encode("utf-8"),
                {
                    "organization_id": org.id,
                    "survey_slug": slug,
                    "recovery_type": "organization",
                },
            )
            request.session["unlock_credentials"] = base64.b64encode(
                encrypted_creds
            ).decode("ascii")
            request.session["unlock_method"] = "organization_recovery"
            request.session["unlock_verified_at"] = timezone.now().isoformat()
            request.session["unlock_survey_slug"] = slug

            logger.warning(
                f"Organization key recovery performed by {request.user.username} "
                f"for survey {slug} owned by {survey.owner.username} "
                f"(organization: {org.name})"
            )

            messages.success(
                request,
                f"Survey unlocked using organization key recovery. This action has been logged. "
                f"Survey owner: {survey.owner.username}",
            )
            return redirect("surveys:dashboard", slug=slug)
        else:
            logger.error(
                f"Organization key recovery failed for survey {slug} by {request.user.username}"
            )
            messages.error(
                request,
                "Failed to unlock survey with organization key. Please contact technical support.",
            )

    context = {
        "survey": survey,
        "organization": org,
        "is_org_owner": is_org_owner,
        "is_org_admin": is_org_admin,
        "survey_owner": survey.owner,
    }
    return render(request, "surveys/organization_key_recovery.html", context)


@login_required
def survey_export_csv(
    request: HttpRequest, slug: str
) -> Union[HttpResponse, StreamingHttpResponse]:
    survey = get_object_or_404(Survey, slug=slug, owner=request.user)
    # Option 4: Re-derive KEK from stored credentials
    survey_key = get_survey_key_from_session(request, slug)
    if not survey_key:
        messages.error(request, "Unlock survey first.")
        return redirect("surveys:unlock", slug=slug)

    def generate():
        import csv
        from io import StringIO

        header = ["id", "submitted_at", "answers"]
        s = StringIO()
        writer = csv.writer(s)
        writer.writerow(header)
        yield s.getvalue()
        s.seek(0)
        s.truncate(0)
        for r in survey.responses.iterator():
            writer.writerow([r.id, r.submitted_at.isoformat(), json.dumps(r.answers)])
            yield s.getvalue()
            s.seek(0)
            s.truncate(0)

    resp = StreamingHttpResponse(generate(), content_type="text/csv")
    resp["Content-Disposition"] = f"attachment; filename={slug}-responses.csv"
    return resp


# -------------------- Builder (HTMX/SSR) --------------------


@login_required
def group_builder(request: HttpRequest, slug: str, gid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    patient_group, demographics_fields = _get_patient_group_and_fields(survey)
    show_patient_details = patient_group is not None
    include_imd = (
        bool((patient_group.schema or {}).get("include_imd"))
        if patient_group
        else False
    )
    prof_group, professional_fields, professional_ods = (
        _get_professional_group_and_fields(survey)
    )
    show_professional_details = prof_group is not None
    professional_ods_on = [k for k, v in (professional_ods or {}).items() if v]
    professional_ods_pairs = [
        {"key": k, "label": PROFESSIONAL_FIELD_DEFS[k], "on": bool(v)}
        for k, v in (professional_ods or {}).items()
    ]
    style = survey.style or {}
    brand_overrides = {
        "title": style.get("title"),
        "icon_url": style.get("icon_url"),
        "theme_name": style.get("theme_name"),
        "font_heading": style.get("font_heading"),
        "font_body": style.get("font_body"),
        "primary": style.get("primary_color"),
    }
    can_edit = can_edit_survey(request.user, survey)

    # Check if user can collect patient data (FREE tier cannot)
    from checktick_app.core.tier_limits import check_patient_data_permission

    can_collect_patient_data, _ = check_patient_data_permission(request.user)

    ctx = {
        "survey": survey,
        "group": group,
        "questions": questions,
        "can_edit": can_edit,
        "can_collect_patient_data": can_collect_patient_data,
        "show_patient_details": show_patient_details,
        "demographics_fields": demographics_fields,
        "demographic_defs": DEMOGRAPHIC_FIELD_DEFS,
        "demographics_fields_with_labels": [
            (k, DEMOGRAPHIC_FIELD_DEFS[k]) for k in demographics_fields
        ],
        "include_imd": include_imd,
        "show_professional_details": show_professional_details,
        "professional_fields": professional_fields,
        "professional_defs": PROFESSIONAL_FIELD_DEFS,
        "professional_ods": professional_ods,
        "professional_ods_on": professional_ods_on,
        "professional_ods_pairs": professional_ods_pairs,
        "professional_field_datasets": PROFESSIONAL_FIELD_TO_DATASET,
        "available_datasets": get_available_datasets(organization=survey.organization),
    }
    if any(brand_overrides.values()):
        ctx["brand"] = {
            "title": brand_overrides.get("title")
            or getattr(settings, "BRAND_TITLE", "CheckTick"),
            "icon_url": brand_overrides.get("icon_url")
            or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
            "theme_name": brand_overrides.get("theme_name")
            or getattr(settings, "BRAND_THEME", "checktick"),
            "font_heading": brand_overrides.get("font_heading")
            or getattr(
                settings,
                "BRAND_FONT_HEADING",
                "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
            ),
            "font_body": brand_overrides.get("font_body")
            or getattr(
                settings,
                "BRAND_FONT_BODY",
                "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            ),
            "font_css_url": getattr(
                settings,
                "BRAND_FONT_CSS_URL",
                "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
            ),
            "primary": brand_overrides.get("primary"),
        }
    return render(
        request,
        "surveys/group_builder.html",
        ctx,
    )


@login_required
@require_http_methods(["POST"])
def builder_demographics_update(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = survey.question_groups.filter(
        schema__template="patient_details_encrypted"
    ).first()
    if not group:
        raise Http404
    selected = request.POST.getlist("fields")
    allowed = [k for k in selected if k in DEMOGRAPHIC_FIELD_DEFS]
    schema = group.schema or {}
    schema["fields"] = allowed
    # include_imd only applies when post_code is selected
    include_imd_flag = request.POST.get("include_imd") in ("on", "true", "1")
    if "post_code" in allowed:
        schema["include_imd"] = bool(include_imd_flag)
    else:
        schema["include_imd"] = False
    group.schema = schema
    group.save(update_fields=["schema"])

    # Re-render the partial for the builder preview
    _, demographics_fields = _get_patient_group_and_fields(survey)
    include_imd = bool((group.schema or {}).get("include_imd"))
    return render(
        request,
        "surveys/partials/demographics_builder.html",
        {
            "survey": survey,
            "show_patient_details": True,
            "demographics_fields": demographics_fields,
            "demographic_defs": DEMOGRAPHIC_FIELD_DEFS,
            "include_imd": include_imd,
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_professional_update(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = survey.question_groups.filter(
        schema__template="professional_details"
    ).first()
    if not group:
        raise Http404
    selected = request.POST.getlist("fields")
    allowed = [k for k in selected if k in PROFESSIONAL_FIELD_DEFS]
    schema = group.schema or {}
    schema["fields"] = allowed
    # ODS toggles per field
    new_ods: dict[str, bool] = {}
    for k in PROFESSIONAL_ODS_FIELDS:
        if k in allowed:
            new_ods[k] = request.POST.get(f"ods_{k}") in ("on", "true", "1")
        else:
            new_ods[k] = False
    schema["ods"] = new_ods
    group.schema = schema
    group.save(update_fields=["schema"])

    # Re-render the partial for the builder preview
    _, professional_fields, professional_ods = _get_professional_group_and_fields(
        survey
    )
    professional_ods_on = [k for k, v in (professional_ods or {}).items() if v]
    professional_ods_pairs = [
        {"key": k, "label": PROFESSIONAL_FIELD_DEFS[k], "on": bool(v)}
        for k, v in (professional_ods or {}).items()
    ]
    return render(
        request,
        "surveys/partials/professional_builder.html",
        {
            "survey": survey,
            "show_professional_details": True,
            "professional_fields": professional_fields,
            "professional_defs": PROFESSIONAL_FIELD_DEFS,
            "professional_ods": professional_ods,
            "professional_ods_on": professional_ods_on,
            "professional_ods_pairs": professional_ods_pairs,
            "professional_field_datasets": PROFESSIONAL_FIELD_TO_DATASET,
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_question_create(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    form_data = _parse_builder_question_form(request.POST)
    text = form_data["text"]
    qtype = form_data["type"]
    required = form_data["required"]
    options = form_data["options"]
    dataset_key = form_data.get("dataset_key")
    group_id = request.POST.get("group_id")
    group = (
        QuestionGroup.objects.filter(id=group_id, owner=request.user).first()
        if group_id
        else None
    )
    order = (survey.questions.aggregate(models.Max("order")).get("order__max") or 0) + 1

    # Look up dataset if provided (with access control)
    dataset = None
    if dataset_key:
        from django.db.models import Q

        from .models import DataSet

        dataset = DataSet.objects.filter(
            Q(is_global=True) | Q(organization=survey.organization),
            key=dataset_key,
            is_active=True,
        ).first()

    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text or "Untitled",
        type=qtype,
        options=options,
        required=required,
        order=order,
        dataset=dataset,
    )
    questions_qs = survey.questions.select_related("group").all()
    questions = _prepare_question_rendering(survey, questions_qs)
    groups = survey.question_groups.filter(owner=request.user)
    return render(
        request,
        "surveys/partials/questions_list.html",
        {
            "survey": survey,
            "questions": questions,
            "groups": groups,
            "message": "Question created.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_question_copy(request: HttpRequest, slug: str, qid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    _duplicate_question(question)
    questions_qs = survey.questions.select_related("group").all()
    questions = _prepare_question_rendering(survey, questions_qs)
    groups = survey.question_groups.filter(owner=request.user)
    return render(
        request,
        "surveys/partials/questions_list.html",
        {
            "survey": survey,
            "questions": questions,
            "groups": groups,
            "message": "Question copied.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_question_condition_create(
    request: HttpRequest, slug: str, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    try:
        payload = _build_condition_payload(survey, question, request.POST)
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    condition = SurveyQuestionCondition(question=question, **payload)
    try:
        condition.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)
    condition.save()
    context_group_id = _safe_int(request.POST.get("context_group_id"))
    group_context = (
        survey.question_groups.filter(id=context_group_id).first()
        if context_group_id
        else None
    )
    return _render_template_question_row(
        request,
        survey,
        condition.question,
        group=group_context,
        message="Condition added.",
    )


@login_required
@require_http_methods(["POST"])
def builder_question_condition_update(
    request: HttpRequest, slug: str, qid: int, cid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    condition = get_object_or_404(SurveyQuestionCondition, id=cid, question=question)
    try:
        payload = _build_condition_payload(
            survey, question, request.POST, instance=condition
        )
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    for field, value in payload.items():
        setattr(condition, field, value)

    try:
        condition.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)

    condition.save(
        update_fields=[
            "operator",
            "action",
            "description",
            "value",
            "order",
            "target_question",
            "updated_at",
        ]
    )
    context_group_id = _safe_int(request.POST.get("context_group_id"))
    group_context = (
        survey.question_groups.filter(id=context_group_id).first()
        if context_group_id
        else None
    )
    return _render_template_question_row(
        request,
        survey,
        question,
        group=group_context,
        message="Condition updated.",
    )


@login_required
@require_http_methods(["POST"])
def builder_question_condition_delete(
    request: HttpRequest, slug: str, qid: int, cid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    condition = get_object_or_404(SurveyQuestionCondition, id=cid, question=question)
    condition.delete()
    context_group_id = _safe_int(request.POST.get("context_group_id"))
    group_context = (
        survey.question_groups.filter(id=context_group_id).first()
        if context_group_id
        else None
    )
    return _render_template_question_row(
        request,
        survey,
        question,
        group=group_context,
        message="Condition removed.",
    )


@login_required
@require_http_methods(["POST"])
def builder_group_question_create(
    request: HttpRequest, slug: str, gid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    form_data = _parse_builder_question_form(request.POST)
    text = form_data["text"]
    qtype = form_data["type"]
    required = form_data["required"]
    options = form_data["options"]
    dataset_key = form_data.get("dataset_key")
    order = (survey.questions.aggregate(models.Max("order")).get("order__max") or 0) + 1

    # Look up dataset if provided (with access control)
    dataset = None
    if dataset_key:
        from django.db.models import Q

        from .models import DataSet

        dataset = DataSet.objects.filter(
            Q(is_global=True) | Q(organization=survey.organization),
            key=dataset_key,
            is_active=True,
        ).first()

    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text or "Untitled",
        type=qtype,
        options=options,
        required=required,
        order=order,
        dataset=dataset,
    )
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    return render(
        request,
        "surveys/partials/questions_list_group.html",
        {
            "survey": survey,
            "group": group,
            "questions": questions,
            "message": "Question created.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_group_question_copy(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey, group=group)
    _duplicate_question(question)
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    return render(
        request,
        "surveys/partials/questions_list_group.html",
        {
            "survey": survey,
            "group": group,
            "questions": questions,
            "message": "Question copied.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_group_template_add(
    request: HttpRequest, slug: str, gid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    template_key = request.POST.get("template")
    required = request.POST.get("required") in ("on", "true", "1")
    message = "Template added."
    if template_key == "patient_details_encrypted":
        # Check if user can collect patient data (FREE tier cannot)
        from checktick_app.core.tier_limits import check_patient_data_permission

        can_collect, reason = check_patient_data_permission(request.user)
        if not can_collect:
            messages.error(request, reason)
            questions_qs = survey.questions.select_related("group").filter(group=group)
            questions = _prepare_question_rendering(survey, questions_qs)
            return render(
                request,
                "surveys/partials/questions_list_group.html",
                {
                    "survey": survey,
                    "group": group,
                    "questions": questions,
                    "message": reason,
                },
            )

        if survey.questions.filter(
            group=group, type=SurveyQuestion.Types.TEMPLATE_PATIENT
        ).exists():
            message = "Patient details template already exists in this group."
        else:
            order = (
                survey.questions.aggregate(models.Max("order")).get("order__max") or 0
            ) + 1
            default_options = _normalize_patient_template_options(
                {
                    "template": template_key,
                    "fields": [
                        {
                            "key": field,
                            "label": DEMOGRAPHIC_FIELD_DEFS.get(field, field),
                            "selected": True,
                        }
                        for field in PATIENT_TEMPLATE_DEFAULT_FIELDS
                    ],
                    "include_imd": False,
                }
            )
            SurveyQuestion.objects.create(
                survey=survey,
                group=group,
                text="Patient details (encrypted)",
                type=SurveyQuestion.Types.TEMPLATE_PATIENT,
                options=default_options,
                required=required,
                order=order,
            )
    elif template_key == "professional_details":
        if survey.questions.filter(
            group=group, type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL
        ).exists():
            message = "Professional details template already exists in this group."
        else:
            order = (
                survey.questions.aggregate(models.Max("order")).get("order__max") or 0
            ) + 1
            default_options = _normalize_professional_template_options(
                {
                    "template": template_key,
                    "fields": [
                        {
                            "key": field,
                            "label": PROFESSIONAL_FIELD_DEFS.get(field, field),
                            "selected": True,
                            "ods_enabled": bool(
                                PROFESSIONAL_TEMPLATE_DEFAULT_ODS.get(field)
                            ),
                        }
                        for field in PROFESSIONAL_TEMPLATE_DEFAULT_FIELDS
                    ],
                }
            )
            SurveyQuestion.objects.create(
                survey=survey,
                group=group,
                text="Professional details",
                type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
                options=default_options,
                required=required,
                order=order,
            )
    else:
        message = "Unknown template."
        messages.error(request, "Unknown template.")
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    return render(
        request,
        "surveys/partials/questions_list_group.html",
        {
            "survey": survey,
            "group": group,
            "questions": questions,
            "message": message,
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_question_template_patient_update(
    request: HttpRequest, slug: str, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(
        SurveyQuestion,
        id=qid,
        survey=survey,
        type=SurveyQuestion.Types.TEMPLATE_PATIENT,
    )

    normalized = _normalize_patient_template_options(question.options)
    selected = {
        key for key in request.POST.getlist("fields") if key in DEMOGRAPHIC_FIELD_DEFS
    }
    include_imd = request.POST.get("include_imd") in ("on", "true", "1")

    updated_fields: list[dict[str, Any]] = []
    for field in normalized.get("fields", []):
        key = field.get("key")
        if not key:
            continue
        updated_fields.append(
            {
                "key": key,
                "label": field.get("label") or DEMOGRAPHIC_FIELD_DEFS.get(key, key),
                "selected": key in selected,
            }
        )

    question.options = _normalize_patient_template_options(
        {**normalized, "fields": updated_fields, "include_imd": include_imd}
    )
    question.save(update_fields=["options"])

    return _render_template_question_row(request, survey, question, keep_open=True)


@login_required
@require_http_methods(["POST"])
def builder_group_question_template_patient_update(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    question = get_object_or_404(
        SurveyQuestion,
        id=qid,
        survey=survey,
        group=group,
        type=SurveyQuestion.Types.TEMPLATE_PATIENT,
    )

    normalized = _normalize_patient_template_options(question.options)
    selected = {
        key for key in request.POST.getlist("fields") if key in DEMOGRAPHIC_FIELD_DEFS
    }
    include_imd = request.POST.get("include_imd") in ("on", "true", "1")

    updated_fields: list[dict[str, Any]] = []
    for field in normalized.get("fields", []):
        key = field.get("key")
        if not key:
            continue
        updated_fields.append(
            {
                "key": key,
                "label": field.get("label") or DEMOGRAPHIC_FIELD_DEFS.get(key, key),
                "selected": key in selected,
            }
        )

    question.options = _normalize_patient_template_options(
        {**normalized, "fields": updated_fields, "include_imd": include_imd}
    )
    question.save(update_fields=["options"])

    return _render_template_question_row(
        request, survey, question, group=group, keep_open=True
    )


@login_required
@require_http_methods(["POST"])
def builder_question_template_professional_update(
    request: HttpRequest, slug: str, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(
        SurveyQuestion,
        id=qid,
        survey=survey,
        type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
    )

    normalized = _normalize_professional_template_options(question.options)
    selected = {
        key for key in request.POST.getlist("fields") if key in PROFESSIONAL_FIELD_DEFS
    }
    ods_flags = {
        key: request.POST.get(f"ods_{key}") in ("on", "true", "1")
        for key in PROFESSIONAL_ODS_FIELDS
    }

    updated_fields: list[dict[str, Any]] = []
    for field in normalized.get("fields", []):
        key = field.get("key")
        if not key:
            continue
        allow_ods = bool(field.get("allow_ods")) or key in PROFESSIONAL_ODS_FIELDS
        ods_enabled = allow_ods and ods_flags.get(key, False)
        if key not in selected:
            ods_enabled = False
        updated_fields.append(
            {
                "key": key,
                "label": field.get("label") or PROFESSIONAL_FIELD_DEFS.get(key, key),
                "selected": key in selected,
                "allow_ods": allow_ods,
                "ods_enabled": ods_enabled,
            }
        )

    question.options = _normalize_professional_template_options(
        {**normalized, "fields": updated_fields}
    )
    question.save(update_fields=["options"])

    return _render_template_question_row(request, survey, question, keep_open=True)


@login_required
@require_http_methods(["POST"])
def builder_group_question_template_professional_update(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    question = get_object_or_404(
        SurveyQuestion,
        id=qid,
        survey=survey,
        group=group,
        type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
    )

    normalized = _normalize_professional_template_options(question.options)
    selected = {
        key for key in request.POST.getlist("fields") if key in PROFESSIONAL_FIELD_DEFS
    }
    ods_flags = {
        key: request.POST.get(f"ods_{key}") in ("on", "true", "1")
        for key in PROFESSIONAL_ODS_FIELDS
    }

    updated_fields: list[dict[str, Any]] = []
    for field in normalized.get("fields", []):
        key = field.get("key")
        if not key:
            continue
        allow_ods = bool(field.get("allow_ods")) or key in PROFESSIONAL_ODS_FIELDS
        ods_enabled = allow_ods and ods_flags.get(key, False)
        if key not in selected:
            ods_enabled = False
        updated_fields.append(
            {
                "key": key,
                "label": field.get("label") or PROFESSIONAL_FIELD_DEFS.get(key, key),
                "selected": key in selected,
                "allow_ods": allow_ods,
                "ods_enabled": ods_enabled,
            }
        )

    question.options = _normalize_professional_template_options(
        {**normalized, "fields": updated_fields}
    )
    question.save(update_fields=["options"])

    return _render_template_question_row(
        request, survey, question, group=group, keep_open=True
    )


@login_required
@require_http_methods(["POST"])
def builder_question_edit(request: HttpRequest, slug: str, qid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    q = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    form_data = _parse_builder_question_form(request.POST)
    q.text = form_data["text"] or "Untitled"
    q.type = form_data["type"]
    q.required = form_data["required"]
    q.options = form_data["options"]
    dataset_key = form_data.get("dataset_key")
    group_id = request.POST.get("group_id")
    q.group = (
        QuestionGroup.objects.filter(id=group_id, owner=request.user).first()
        if group_id
        else None
    )

    # Look up dataset if provided (with access control)
    if dataset_key:
        from django.db.models import Q

        from .models import DataSet

        q.dataset = DataSet.objects.filter(
            Q(is_global=True) | Q(organization=survey.organization),
            key=dataset_key,
            is_active=True,
        ).first()
    else:
        q.dataset = None

    q.save()
    return _render_template_question_row(
        request,
        survey,
        q,
        message="Question updated.",
    )


@login_required
@require_http_methods(["POST"])
def builder_group_question_edit(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    q = get_object_or_404(SurveyQuestion, id=qid, survey=survey, group=group)
    form_data = _parse_builder_question_form(request.POST)
    q.text = form_data["text"] or "Untitled"
    q.type = form_data["type"]
    q.required = form_data["required"]
    q.options = form_data["options"]
    dataset_key = form_data.get("dataset_key")

    # Look up dataset if provided (with access control)
    if dataset_key:
        from django.db.models import Q

        from .models import DataSet

        q.dataset = DataSet.objects.filter(
            Q(is_global=True) | Q(organization=survey.organization),
            key=dataset_key,
            is_active=True,
        ).first()
    else:
        q.dataset = None

    q.save()
    return _render_template_question_row(
        request,
        survey,
        q,
        group=group,
        message="Question updated.",
    )


@login_required
@require_http_methods(["POST"])
def builder_question_delete(request: HttpRequest, slug: str, qid: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    q = get_object_or_404(SurveyQuestion, id=qid, survey=survey)
    q.delete()
    questions_qs = survey.questions.select_related("group").all()
    questions = _prepare_question_rendering(survey, questions_qs)
    groups = survey.question_groups.filter(owner=request.user)
    return render(
        request,
        "surveys/partials/questions_list.html",
        {
            "survey": survey,
            "questions": questions,
            "groups": groups,
            "message": "Question deleted.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_group_question_delete(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    q = get_object_or_404(SurveyQuestion, id=qid, survey=survey, group=group)
    q.delete()
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    return render(
        request,
        "surveys/partials/questions_list_group.html",
        {
            "survey": survey,
            "group": group,
            "questions": questions,
            "message": "Question deleted.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_questions_reorder(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    order_csv = request.POST.get("order", "")  # expects comma-separated ids
    ids = [int(i) for i in order_csv.split(",") if i.isdigit()]
    for idx, qid in enumerate(ids):
        SurveyQuestion.objects.filter(id=qid, survey=survey).update(order=idx)
    questions_qs = survey.questions.select_related("group").all()
    questions = _prepare_question_rendering(survey, questions_qs)
    groups = survey.question_groups.filter(owner=request.user)
    return render(
        request,
        "surveys/partials/questions_list.html",
        {
            "survey": survey,
            "questions": questions,
            "groups": groups,
            "message": "Order updated.",
        },
    )


@login_required
@require_http_methods(["POST"])
def builder_group_questions_reorder(
    request: HttpRequest, slug: str, gid: int
) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    order_csv = request.POST.get("order", "")
    ids = [int(i) for i in order_csv.split(",") if i.isdigit()]
    for idx, qid in enumerate(ids):
        SurveyQuestion.objects.filter(id=qid, survey=survey, group=group).update(
            order=idx
        )
    questions_qs = survey.questions.select_related("group").filter(group=group)
    questions = _prepare_question_rendering(survey, questions_qs)
    return render(
        request,
        "surveys/partials/questions_list_group.html",
        {
            "survey": survey,
            "group": group,
            "questions": questions,
            "message": "Order updated.",
        },
    )


# Maximum file size for uploaded images (1MB)
MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1MB
# Maximum image dimensions
MAX_IMAGE_DIMENSION = 800
# Allowed image formats (extensions)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
# Allowed MIME types
ALLOWED_IMAGE_MIMES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/svg+xml",
}


def _validate_and_process_image(uploaded_file) -> tuple[bool, str]:
    """
    Validate and optionally resize an uploaded image.

    Returns:
        (success, error_message) - if success is False, error_message contains
        the reason
    """
    import os

    from PIL import Image

    # Check file size
    if uploaded_file.size > MAX_IMAGE_SIZE:
        return False, _("Image file is too large. Maximum size is 1MB.")

    # Check extension
    _base, ext = os.path.splitext(uploaded_file.name.lower())
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, _("Invalid image format. Allowed formats: PNG, JPG, WebP, SVG.")

    # Check MIME type
    content_type = uploaded_file.content_type
    if content_type not in ALLOWED_IMAGE_MIMES:
        return False, _("Invalid image type. Allowed types: PNG, JPG, WebP, SVG.")

    # For SVG files, we skip dimension checks and PIL processing
    if ext == ".svg" or content_type == "image/svg+xml":
        return True, ""

    # Validate the image can be opened and check dimensions
    try:
        img = Image.open(uploaded_file)
        img.verify()  # Verify it's a valid image

        # Re-open after verify (verify closes the file)
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)

        # Resize if too large
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            img.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS
            )

            # Save the resized image back to the file
            from io import BytesIO

            buffer = BytesIO()
            img_format = (
                "PNG"
                if ext == ".png"
                else "JPEG"
                if ext in (".jpg", ".jpeg")
                else "WEBP"
            )
            img.save(buffer, format=img_format, quality=85)
            buffer.seek(0)

            # Update the file content
            uploaded_file.file = buffer
            uploaded_file.size = buffer.getbuffer().nbytes

        uploaded_file.seek(0)
        return True, ""

    except Exception as e:
        return False, _("Invalid or corrupted image file: %(error)s") % {
            "error": str(e)
        }


@login_required
@require_http_methods(["POST"])
def builder_question_image_upload(
    request: HttpRequest, slug: str, qid: int
) -> HttpResponse:
    """Upload an image for an image choice question (no group)."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(
        SurveyQuestion, id=qid, survey=survey, group__isnull=True
    )
    return _handle_image_upload(request, survey, question)


@login_required
@require_http_methods(["POST"])
def builder_group_question_image_upload(
    request: HttpRequest, slug: str, gid: int, qid: int
) -> HttpResponse:
    """Upload an image for an image choice question (with group)."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey, group=group)
    return _handle_image_upload(request, survey, question)


def _handle_image_upload(
    request: HttpRequest, survey: Survey, question: SurveyQuestion
) -> HttpResponse:
    """Common handler for image uploads."""
    from .models import QuestionImage

    if question.type != SurveyQuestion.Types.IMAGE_CHOICE:
        return JsonResponse(
            {"success": False, "error": _("Question is not an image choice type.")},
            status=400,
        )

    uploaded_file = request.FILES.get("image")
    if not uploaded_file:
        return JsonResponse(
            {"success": False, "error": _("No image file provided.")},
            status=400,
        )

    # Validate and process the image
    success, error = _validate_and_process_image(uploaded_file)
    if not success:
        return JsonResponse({"success": False, "error": error}, status=400)

    # Get the label from the request
    label = request.POST.get("label", "").strip()

    # Calculate the order for the new image
    max_order = question.images.aggregate(models.Max("order")).get("order__max") or 0

    # Create the QuestionImage
    image = QuestionImage.objects.create(
        question=question,
        image=uploaded_file,
        label=label,
        order=max_order + 1,
    )

    return JsonResponse(
        {
            "success": True,
            "image": {
                "id": image.id,
                "url": image.url,
                "label": image.label,
                "order": image.order,
            },
            "message": _("Image uploaded successfully."),
        }
    )


@login_required
@require_http_methods(["POST", "DELETE"])
def builder_question_image_delete(
    request: HttpRequest, slug: str, qid: int, img_id: int
) -> HttpResponse:
    """Delete an image from an image choice question (no group)."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    question = get_object_or_404(
        SurveyQuestion, id=qid, survey=survey, group__isnull=True
    )
    return _handle_image_delete(request, survey, question, img_id)


@login_required
@require_http_methods(["POST", "DELETE"])
def builder_group_question_image_delete(
    request: HttpRequest, slug: str, gid: int, qid: int, img_id: int
) -> HttpResponse:
    """Delete an image from an image choice question (with group)."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    group = get_object_or_404(QuestionGroup, id=gid, surveys=survey)
    question = get_object_or_404(SurveyQuestion, id=qid, survey=survey, group=group)
    return _handle_image_delete(request, survey, question, img_id)


def _handle_image_delete(
    request: HttpRequest, survey: Survey, question: SurveyQuestion, img_id: int
) -> HttpResponse:
    """Common handler for image deletion."""
    from .models import QuestionImage

    image = get_object_or_404(QuestionImage, id=img_id, question=question)

    # Delete the file from storage
    if image.image:
        image.image.delete(save=False)

    # Delete the model instance
    image.delete()

    return JsonResponse(
        {
            "success": True,
            "message": _("Image deleted successfully."),
        }
    )


@login_required
@require_http_methods(["POST"])
def builder_group_create(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)
    name = request.POST.get("name", "").strip() or "New Group"
    g = QuestionGroup.objects.create(name=name, owner=request.user)
    questions_qs = survey.questions.select_related("group").all()
    questions = _prepare_question_rendering(survey, questions_qs)
    survey.question_groups.add(g)
    groups = survey.question_groups.filter(owner=request.user)
    return render(
        request,
        "surveys/partials/questions_list.html",
        {"survey": survey, "questions": questions, "groups": groups},
    )


def _clear_existing_bulk_import_content(survey: Survey) -> dict[str, int]:
    """Remove existing groups, questions, and collections before an import."""

    removed_questions = survey.questions.count()
    removed_collections = survey.collections.count()

    existing_groups = list(survey.question_groups.prefetch_related("surveys").all())
    groups_detached = len(existing_groups)

    shared_or_external_ids: set[int] = set()
    for group in existing_groups:
        if group.shared or any(s.id != survey.id for s in group.surveys.all()):
            shared_or_external_ids.add(group.id)

    # Remove dependent structures first to satisfy FK constraints
    survey.collections.all().delete()
    survey.questions.all().delete()

    # Detach all question groups from the survey, then delete the ones that are
    # unshared and no longer referenced elsewhere.
    survey.question_groups.clear()
    deletable_group_ids = [
        group.id for group in existing_groups if group.id not in shared_or_external_ids
    ]
    if deletable_group_ids:
        QuestionGroup.objects.filter(id__in=deletable_group_ids).delete()

    return {
        "questions": removed_questions,
        "collections": removed_collections,
        "detached_groups": groups_detached,
        "deleted_groups": len(deletable_group_ids),
    }


def _handle_llm_new_session(request: HttpRequest, survey: Survey) -> JsonResponse:
    """
    Handle LLM new session creation (AJAX only).
    Security: Only authenticated users with edit permission can create sessions.
    """
    if not settings.LLM_ENABLED:
        return JsonResponse(
            {"status": "error", "message": "AI generation not available"}, status=400
        )

    # Deactivate any existing session
    LLMConversationSession.objects.filter(
        survey=survey, user=request.user, is_active=True
    ).update(is_active=False)

    # Create new session
    session = LLMConversationSession.objects.create(survey=survey, user=request.user)

    # Audit log
    AuditLog.objects.create(
        actor=request.user,
        scope=AuditLog.Scope.SURVEY,
        survey=survey,
        action=AuditLog.Action.ADD,
        target_user=request.user,
        metadata={"action": "llm_session_started", "session_id": str(session.id)},
    )

    return JsonResponse(
        {
            "status": "success",
            "session_id": str(session.id),
            "message": "New conversation started",
        }
    )


def _handle_llm_send_message(request: HttpRequest, survey: Survey) -> JsonResponse:
    """
    Handle LLM message sending (AJAX only).
    Security: Session must belong to requesting user, no survey modification occurs here.
    """
    if not settings.LLM_ENABLED:
        return JsonResponse(
            {"status": "error", "message": "AI generation not available"}, status=400
        )

    # Get user's active session
    session = LLMConversationSession.objects.filter(
        survey=survey, user=request.user, is_active=True
    ).first()

    if not session:
        return JsonResponse(
            {"status": "error", "message": "No active session"}, status=400
        )

    user_message = request.POST.get("message", "").strip()
    if not user_message:
        return JsonResponse(
            {"status": "error", "message": "Message cannot be empty"}, status=400
        )

    # Add user message to history
    session.add_message("user", user_message)

    try:
        # Get LLM response
        llm_client = ConversationalSurveyLLM()
        llm_response = llm_client.chat(session.get_conversation_for_llm())

        if not llm_response:
            return JsonResponse(
                {"status": "error", "message": "Failed to get response from AI"},
                status=500,
            )

        # Add assistant response to history
        session.add_message("assistant", llm_response)

        # Try to extract and validate markdown
        markdown = llm_client.extract_markdown(llm_response)
        markdown_valid = False
        validation_errors = []

        if markdown:
            # Sanitize
            markdown = llm_client.sanitize_markdown(markdown)

            # Validate against parser (but don't create anything yet!)
            try:
                parse_bulk_markdown_with_collections(markdown)
                markdown_valid = True

                # Update session with valid markdown
                session.current_markdown = markdown
                session.save()

            except BulkParseError as e:
                validation_errors.append(str(e))

        # Audit log for message
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=survey,
            action=AuditLog.Action.UPDATE,
            target_user=request.user,
            metadata={
                "action": "llm_message_sent",
                "session_id": str(session.id),
                "markdown_valid": markdown_valid,
            },
        )

        return JsonResponse(
            {
                "status": "success",
                "assistant_message": llm_response,
                "markdown": markdown if markdown else session.current_markdown,
                "markdown_valid": markdown_valid,
                "validation_errors": validation_errors,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except ValueError as e:
        logger.error(f"LLM configuration error: {e}")
        return JsonResponse(
            {"status": "error", "message": "AI generation not properly configured"},
            status=500,
        )
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Unexpected error occurred"}, status=500
        )


def _handle_llm_new_session(request: HttpRequest, survey: Survey) -> JsonResponse:
    """Handle AJAX request to start a new LLM conversation session."""
    if not settings.LLM_ENABLED:
        return JsonResponse(
            {"status": "error", "message": "AI generation is not available"}, status=400
        )

    # Deactivate any existing active sessions
    LLMConversationSession.objects.filter(
        survey=survey, user=request.user, is_active=True
    ).update(is_active=False)

    # Create new session
    session = LLMConversationSession.objects.create(survey=survey, user=request.user)

    # Log audit
    AuditLog.objects.create(
        actor=request.user,
        scope=AuditLog.Scope.SURVEY,
        survey=survey,
        action=AuditLog.Action.ADD,
        target_user=request.user,
        metadata={"action": "llm_session_started", "session_id": str(session.id)},
    )

    return JsonResponse(
        {
            "status": "success",
            "session_id": str(session.id),
            "message": "New conversation started",
        }
    )


def _handle_llm_send_message(request: HttpRequest, survey: Survey) -> JsonResponse:
    """Handle AJAX request to send message to LLM."""
    if not settings.LLM_ENABLED:
        return JsonResponse(
            {"status": "error", "message": "AI generation is not available"}, status=400
        )

    # Get active session
    session = LLMConversationSession.objects.filter(
        survey=survey, user=request.user, is_active=True
    ).first()

    if not session:
        return JsonResponse(
            {"status": "error", "message": "No active session"}, status=400
        )

    user_message = request.POST.get("message", "").strip()
    if not user_message:
        return JsonResponse(
            {"status": "error", "message": "Message cannot be empty"}, status=400
        )

    # Add user message to history
    session.add_message("user", user_message)

    try:
        # Get LLM response
        llm_client = ConversationalSurveyLLM()
        llm_response = llm_client.chat(session.get_conversation_for_llm())

        if not llm_response:
            return JsonResponse(
                {"status": "error", "message": "Failed to get response from AI"},
                status=500,
            )

        # Add assistant response to history
        session.add_message("assistant", llm_response)

        # Try to extract markdown
        markdown = llm_client.extract_markdown(llm_response)
        markdown_valid = False
        validation_errors = []

        if markdown:
            # Sanitize
            markdown = llm_client.sanitize_markdown(markdown)

            # Validate against parser
            try:
                parse_bulk_markdown_with_collections(markdown)
                markdown_valid = True

                # Update session with valid markdown
                session.current_markdown = markdown
                session.save()

            except BulkParseError as e:
                validation_errors.append(str(e))

        # Log audit
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=survey,
            action=AuditLog.Action.UPDATE,
            target_user=request.user,
            metadata={
                "action": "llm_message_sent",
                "session_id": str(session.id),
                "message_count": len(session.conversation_history),
                "markdown_valid": markdown_valid,
            },
        )

        return JsonResponse(
            {
                "status": "success",
                "assistant_message": llm_response,
                "markdown": markdown if markdown else session.current_markdown,
                "markdown_valid": markdown_valid,
                "validation_errors": validation_errors,
                "timestamp": timezone.now().isoformat(),
            }
        )

    except ValueError as e:
        logger.error(f"LLM configuration error: {e}")
        return JsonResponse(
            {"status": "error", "message": "AI generation not properly configured"},
            status=500,
        )
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Unexpected error occurred"}, status=500
        )


@login_required
def _handle_llm_ai_chat(
    request: HttpRequest, survey: Survey, data: dict
) -> StreamingHttpResponse:
    """Handle JSON AJAX request for AI chat with streaming - modern interface."""
    if not settings.LLM_ENABLED:
        return JsonResponse({"error": "AI generation is not available"}, status=400)

    user_message = data.get("message", "").strip()
    if not user_message:
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    session_id = data.get("session_id")

    # Get or create session
    if session_id:
        try:
            session = LLMConversationSession.objects.get(
                id=session_id, survey=survey, user=request.user, is_active=True
            )
            # Refresh from database to ensure we have latest conversation history
            session.refresh_from_db()
        except LLMConversationSession.DoesNotExist:
            session = None
    else:
        session = None

    if not session:
        # Deactivate any existing active sessions
        LLMConversationSession.objects.filter(
            survey=survey, user=request.user, is_active=True
        ).update(is_active=False)

        # Create new session
        session = LLMConversationSession.objects.create(
            survey=survey, user=request.user
        )

        # Log audit
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            survey=survey,
            action=AuditLog.Action.ADD,
            target_user=request.user,
            metadata={"action": "llm_session_started", "session_id": str(session.id)},
        )

    # Add user message to history
    session.add_message("user", user_message)

    def stream_response():
        """Generator function for streaming LLM response."""
        import json

        try:
            # Send session_id first
            yield f"data: {json.dumps({'session_id': str(session.id)})}\n\n"

            # Get LLM response stream
            llm_client = ConversationalSurveyLLM()
            full_response = ""

            for chunk in llm_client.chat_stream(session.get_conversation_for_llm()):
                if chunk:
                    full_response += chunk
                    # Send each chunk as SSE
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            if not full_response:
                yield f"data: {json.dumps({'error': 'Failed to get response from AI'})}\n\n"
                return

            # Add complete assistant response to history
            session.add_message("assistant", full_response)

            # Try to extract markdown
            markdown = llm_client.extract_markdown(full_response)

            if markdown:
                # Sanitize
                markdown = llm_client.sanitize_markdown(markdown)

                # Validate against parser
                try:
                    parse_bulk_markdown_with_collections(markdown)
                    # Update session with valid markdown
                    session.current_markdown = markdown
                    session.save()
                except BulkParseError:
                    # Markdown extraction found but invalid - include in response anyway
                    pass

            # Log audit
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.SURVEY,
                survey=survey,
                action=AuditLog.Action.UPDATE,
                target_user=request.user,
                metadata={
                    "action": "llm_message_sent",
                    "session_id": str(session.id),
                    "has_markdown": bool(markdown),
                },
            )

            # Send final metadata
            yield f"data: {json.dumps({'done': True, 'markdown': markdown})}\n\n"

        except Exception as e:
            logger.exception("Error in LLM chat stream: %s", e)
            yield f"data: {json.dumps({'error': 'An error occurred processing your request'})}\n\n"

    response = StreamingHttpResponse(
        stream_response(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _handle_llm_get_sessions(request: HttpRequest, survey: Survey) -> JsonResponse:
    """Get list of all LLM conversation sessions for the current survey and user."""
    try:
        sessions = (
            LLMConversationSession.objects.filter(survey=survey, user=request.user)
            .order_by("-updated_at")
            .values(
                "id",
                "created_at",
                "updated_at",
                "is_active",
                "conversation_history",
                "current_markdown",
            )
        )

        session_list = []
        for session in sessions:
            # Get message count and last message preview
            history = session.get("conversation_history", [])
            message_count = len(history)
            last_message = ""
            if history:
                # Get last user message for preview
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        last_message = msg.get("content", "")[:100]
                        break

            session_list.append(
                {
                    "id": str(session["id"]),
                    "created_at": session["created_at"].isoformat(),
                    "updated_at": session["updated_at"].isoformat(),
                    "is_active": session["is_active"],
                    "message_count": message_count,
                    "last_message_preview": last_message,
                    "has_markdown": bool(session.get("current_markdown")),
                }
            )

        return JsonResponse({"sessions": session_list})

    except Exception as e:
        logger.exception("Error fetching LLM sessions: %s", e)
        return JsonResponse(
            {"error": "An error occurred fetching sessions"}, status=500
        )


def _handle_llm_get_session_details(
    request: HttpRequest, survey: Survey, data: dict
) -> JsonResponse:
    """Get full details of a specific LLM conversation session."""
    try:
        session_id = data.get("session_id")
        if not session_id:
            return JsonResponse({"error": "session_id is required"}, status=400)

        try:
            session = LLMConversationSession.objects.get(
                id=session_id, survey=survey, user=request.user
            )
        except LLMConversationSession.DoesNotExist:
            return JsonResponse({"error": "Session not found"}, status=404)

        return JsonResponse(
            {
                "id": str(session.id),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "is_active": session.is_active,
                "conversation_history": session.conversation_history,
                "current_markdown": session.current_markdown,
            }
        )

    except Exception as e:
        logger.exception("Error fetching LLM session details: %s", e)
        return JsonResponse(
            {"error": "An error occurred fetching session details"}, status=500
        )


def bulk_upload(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    # Check if LLM is enabled for context
    llm_enabled = settings.LLM_ENABLED

    # Handle JSON AJAX requests for LLM functionality
    if request.content_type == "application/json":
        try:
            import json

            data = json.loads(request.body)
            action = data.get("action")

            if action == "ai_chat":
                return _handle_llm_ai_chat(request, survey, data)
            elif action == "get_sessions":
                return _handle_llm_get_sessions(request, survey)
            elif action == "get_session_details":
                return _handle_llm_get_session_details(request, survey, data)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Handle legacy AJAX requests for LLM functionality
    if (
        request.method == "POST"
        and request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        action = request.POST.get("action")

        if action == "new_session":
            return _handle_llm_new_session(request, survey)
        elif action == "send_message":
            return _handle_llm_send_message(request, survey)

    # Original bulk upload logic continues
    # Get tab parameter from URL to pre-select a tab
    initial_tab = request.GET.get("tab", "manual")  # default to manual
    if initial_tab not in ["manual", "ai", "history"]:
        initial_tab = "manual"

    # Check if survey has existing questions and export to markdown
    has_questions = survey.question_groups.filter(
        surveyquestion__survey=survey
    ).exists()

    existing_markdown = ""
    if has_questions:
        existing_markdown = _export_survey_to_markdown(survey)

    context = {
        "survey": survey,
        "example": _bulk_upload_example_md(),
        "llm_enabled": llm_enabled,
        "initial_tab": initial_tab,
        "markdown": existing_markdown,  # Pre-populate with existing questions
    }

    # Get or create LLM session if LLM is enabled
    if llm_enabled:
        llm_session = LLMConversationSession.objects.filter(
            survey=survey, user=request.user, is_active=True
        ).first()
        if llm_session:
            context["llm_session"] = llm_session
            context["conversation_history"] = llm_session.conversation_history
            context["current_markdown"] = llm_session.current_markdown

    if request.method == "POST":
        md = request.POST.get("markdown", "")
        try:
            parsed = parse_bulk_markdown_with_collections(md)
        except BulkParseError as e:
            context["error"] = str(e)
            context["markdown"] = md
            return render(request, "surveys/bulk_upload.html", context)
        repeats = parsed.get("repeats") or []
        created_collections = 0
        created_items = 0

        removal_stats: dict[str, int] = {}

        try:
            with transaction.atomic():
                removal_stats = _clear_existing_bulk_import_content(survey)

                next_order = 0
                created_groups_in_order: list[QuestionGroup] = []
                group_ref_map: dict[str, QuestionGroup] = {}
                question_ref_map: dict[str, SurveyQuestion] = {}
                pending_branch_payloads: list[dict[str, Any]] = []

                for g in parsed["groups"]:
                    grp = QuestionGroup.objects.create(
                        name=g["name"],
                        description=g.get("description", ""),
                        owner=request.user,
                    )
                    survey.question_groups.add(grp)
                    created_groups_in_order.append(grp)
                    if g.get("ref"):
                        group_ref_map[g["ref"]] = grp
                    for q in g["questions"]:
                        question = SurveyQuestion.objects.create(
                            survey=survey,
                            group=grp,
                            text=q["title"],
                            type=q["final_type"],
                            options=q["final_options"],
                            required=q.get("required", False),
                            order=next_order,
                        )
                        next_order += 1
                        if q.get("ref"):
                            question_ref_map[q["ref"]] = question
                        if q.get("branches"):
                            pending_branch_payloads.append(
                                {
                                    "question": question,
                                    "branches": q["branches"],
                                }
                            )

                for payload in pending_branch_payloads:
                    question = payload["question"]
                    branches = payload.get("branches") or []
                    for branch in branches:
                        target_question = None
                        target_ref = branch.get("target_ref")
                        target_type = branch.get("target_type")
                        if target_type == "question":
                            target_question = question_ref_map.get(target_ref)

                        if not target_question:
                            raise BulkParseError(
                                f"Unable to resolve branch target '{target_ref}' for question '{question.text}'"
                            )

                        SurveyQuestionCondition.objects.create(
                            question=question,
                            operator=branch.get("operator"),
                            value=branch.get("value", ""),
                            target_question=target_question,
                            action=SurveyQuestionCondition.Action.JUMP_TO,
                            order=branch.get("order", 0),
                            description=branch.get("description", ""),
                        )

                def _unique_key(base: str) -> str:
                    k = slugify(base)
                    if not k:
                        k = "collection"
                    candidate = k
                    i = 2
                    while CollectionDefinition.objects.filter(
                        survey=survey, key=candidate
                    ).exists():
                        candidate = f"{k}-{i}"
                        i += 1
                    return candidate

                defs_by_group_index: dict[int, CollectionDefinition] = {}
                for rep in repeats:
                    gi = int(rep.get("group_index"))
                    max_count = rep.get("max_count")
                    name = (
                        created_groups_in_order[gi].name
                        if gi < len(created_groups_in_order)
                        else parsed["groups"][gi]["name"]
                    )
                    key = _unique_key(name)
                    cardinality = (
                        CollectionDefinition.Cardinality.ONE
                        if (isinstance(max_count, int) and max_count == 1)
                        else CollectionDefinition.Cardinality.MANY
                    )
                    cd = CollectionDefinition.objects.create(
                        survey=survey,
                        key=key,
                        name=name,
                        cardinality=cardinality,
                        max_count=max_count,
                    )
                    defs_by_group_index[gi] = cd
                    created_collections += 1

                for rep in repeats:
                    gi = int(rep.get("group_index"))
                    parent_index = rep.get("parent_index")
                    if parent_index is not None:
                        child_cd = defs_by_group_index.get(gi)
                        parent_cd = defs_by_group_index.get(int(parent_index))
                        if (
                            child_cd
                            and parent_cd
                            and child_cd.parent_id != parent_cd.id
                        ):
                            child_cd.parent = parent_cd
                            child_cd.full_clean()
                            child_cd.save(update_fields=["parent"])

                for gi, cd in defs_by_group_index.items():
                    order = 0
                    if gi < len(created_groups_in_order):
                        grp = created_groups_in_order[gi]
                        CollectionItem.objects.create(
                            collection=cd,
                            item_type=CollectionItem.ItemType.GROUP,
                            group=grp,
                            order=order,
                        )
                        created_items += 1
                        order += 1
                    for rep in repeats:
                        if rep.get("parent_index") == gi:
                            child_cd = defs_by_group_index.get(int(rep["group_index"]))
                            if child_cd:
                                if child_cd.parent_id != cd.id:
                                    child_cd.parent = cd
                                    child_cd.full_clean()
                                    child_cd.save(update_fields=["parent"])
                                CollectionItem.objects.create(
                                    collection=cd,
                                    item_type=CollectionItem.ItemType.COLLECTION,
                                    child_collection=child_cd,
                                    order=order,
                                )
                                created_items += 1
                                order += 1

        except BulkParseError as e:
            context["error"] = str(e)
            context["markdown"] = md
            return render(request, "surveys/bulk_upload.html", context)
        except ValidationError as e:
            messages_list = getattr(e, "messages", None)
            context["error"] = ", ".join(messages_list) if messages_list else str(e)
            context["markdown"] = md
            return render(request, "surveys/bulk_upload.html", context)

        summary_parts = [
            f"Bulk upload successful: added {len(parsed['groups'])} group(s) and questions."
        ]
        if repeats:
            summary_parts.append(
                f" Also created {created_collections} collection(s) and {created_items} item(s)."
            )
        if (
            removal_stats.get("detached_groups")
            or removal_stats.get("questions")
            or removal_stats.get("collections")
        ):
            summary_parts.append(" Previous survey content was replaced.")

        messages.success(request, "".join(summary_parts))
        return redirect("surveys:dashboard", slug=survey.slug)
    return render(request, "surveys/bulk_upload.html", context)


def _export_survey_to_markdown(survey: Survey) -> str:
    """Export existing survey questions to markdown format."""
    from collections import defaultdict

    # Get all collections for this survey
    collections = (
        CollectionDefinition.objects.filter(survey=survey)
        .select_related("parent")
        .prefetch_related("items")
    )

    # Build collection hierarchy
    parent_collections = {}
    child_collections = defaultdict(list)

    for coll in collections:
        if coll.parent is None:
            parent_collections[coll.id] = coll
        else:
            child_collections[coll.parent_id].append(coll)

    # Get all question groups for this survey
    groups = (
        survey.question_groups.all()
        .prefetch_related(
            models.Prefetch(
                "surveyquestion_set",
                queryset=SurveyQuestion.objects.filter(survey=survey).order_by("order"),
            )
        )
        .order_by("id")
    )

    # Build markdown
    lines = []

    for group in groups:
        # Check if this group is part of a collection
        parent_coll_item = (
            CollectionItem.objects.filter(group=group, collection__parent__isnull=True)
            .select_related("collection")
            .first()
        )

        child_coll_item = (
            CollectionItem.objects.filter(group=group, collection__parent__isnull=False)
            .select_related("collection")
            .first()
        )

        indent = ""

        # If this is a child collection group
        if child_coll_item:
            indent = "> "
            # Add REPEAT marker for child collection (only once per collection)
            first_item = (
                CollectionItem.objects.filter(collection=child_coll_item.collection)
                .order_by("order")
                .first()
            )
            if first_item and first_item.group_id == group.id:
                max_count = child_coll_item.collection.max_count or 0
                if max_count > 0:
                    lines.append(f"{indent}REPEAT-{max_count}")
                else:
                    lines.append(f"{indent}REPEAT")

        # If this is a parent collection group
        elif parent_coll_item:
            # Add REPEAT marker for parent collection (only once per collection)
            first_item = (
                CollectionItem.objects.filter(collection=parent_coll_item.collection)
                .order_by("order")
                .first()
            )
            if first_item and first_item.group_id == group.id:
                max_count = parent_coll_item.collection.max_count or 0
                if max_count > 0:
                    lines.append(f"REPEAT-{max_count}")
                else:
                    lines.append("REPEAT")

        # Add group heading
        group_ref = group.name.lower().replace(" ", "-")
        lines.append(f"{indent}# {group.name} {{{group_ref}}}")
        if group.description:
            lines.append(f"{indent}{group.description}")
        lines.append("")

        # Add questions
        for question in group.surveyquestion_set.all():
            required = "*" if question.required else ""
            question_ref = question.text.lower()[:30].replace(" ", "-").strip("-")
            lines.append(f"{indent}## {question.text}{required} {{{question_ref}}}")

            # Determine the export type name
            export_type = question.type

            # Handle special cases where DB type differs from markdown type
            if question.type == "text" and question.options:
                # Check if it's text number
                if isinstance(question.options, list) and len(question.options) > 0:
                    first_option = question.options[0]
                    if (
                        first_option.get("type") == "text"
                        and first_option.get("format") == "number"
                    ):
                        export_type = "text number"
            elif question.type == "likert" and question.options:
                # Check if it's categories or number
                if isinstance(question.options, list) and len(question.options) > 0:
                    first_option = question.options[0]
                    if first_option.get("type") == "categories":
                        export_type = "likert categories"
                    elif first_option.get("type") in ["number", "number-scale"]:
                        export_type = "likert number"

            # Question type
            lines.append(f"{indent}({export_type})")

            # Handle likert type (which can be categories or number)
            if question.type == "likert" and question.options:
                # Check if it's categories or number type
                if isinstance(question.options, list) and len(question.options) > 0:
                    first_option = question.options[0]
                    if (
                        first_option.get("type") == "categories"
                        and "labels" in first_option
                    ):
                        # Likert categories - export as list
                        for label in first_option["labels"]:
                            lines.append(f"{indent}- {label}")
                    elif first_option.get("type") in ["number", "number-scale"]:
                        # Likert number - export min/max/labels
                        min_val = first_option.get("min")
                        max_val = first_option.get("max")
                        left_label = first_option.get("left_label", "")
                        right_label = first_option.get("right_label", "")
                        if min_val is not None:
                            lines.append(f"{indent}min: {min_val}")
                        if max_val is not None:
                            lines.append(f"{indent}max: {max_val}")
                        if left_label:
                            lines.append(f"{indent}left: {left_label}")
                        if right_label:
                            lines.append(f"{indent}right: {right_label}")

            # Options for question types that need them
            elif question.type in [
                "mc_single",
                "mc_multi",
                "dropdown",
                "orderable",
                "yesno",
                "image",
                "likert categories",
            ]:
                if question.options:
                    for option in question.options:
                        # Options can have 'text', 'label', or 'value' keys
                        option_text = (
                            option.get("text")
                            or option.get("label")
                            or option.get("value", "")
                        )
                        lines.append(f"{indent}- {option_text}")
                        # Check for follow-up text
                        if option.get("has_followup_text"):
                            followup_label = option.get(
                                "followup_text_label", "Please specify"
                            )
                            lines.append(f"{indent}  + {followup_label}")

            # Likert number settings
            elif question.type == "likert number":
                if question.options:
                    min_val = question.options.get("min")
                    max_val = question.options.get("max")
                    left_label = question.options.get("left_label", "")
                    right_label = question.options.get("right_label", "")

                    if min_val is not None:
                        lines.append(f"{indent}min: {min_val}")
                    if max_val is not None:
                        lines.append(f"{indent}max: {max_val}")
                    if left_label:
                        lines.append(f"{indent}left: {left_label}")
                    if right_label:
                        lines.append(f"{indent}right: {right_label}")

            # Branching rules
            conditions = SurveyQuestionCondition.objects.filter(question=question)
            for condition in conditions:
                operator = condition.operator
                value = condition.value or ""
                if condition.target_question:
                    target_ref = (
                        condition.target_question.text.lower()[:30]
                        .replace(" ", "-")
                        .strip("-")
                    )
                    lines.append(
                        f"{indent}? when {operator} {value} -> {{{target_ref}}}"
                    )

            lines.append("")

    return "\n".join(lines)


def _bulk_upload_example_md() -> str:
    return (
        "REPEAT-5\n"
        "# Patient {patient}\n"
        "Basic info about respondents\n\n"
        "## Age* {patient-age}\n"
        "Age in years\n"
        "(text number)\n\n"
        "? when greater_than 17 -> {follow-up-overall}\n\n"
        "## Gender* {patient-gender}\n"
        "Self-described gender\n"
        "(mc_single)\n"
        "- Female\n"
        "- Male\n"
        "- Non-binary\n"
        "  + Please specify\n"
        "- Prefer not to say\n\n"
        "> REPEAT\n"
        "> # Visit {visit}\n"
        "> Details about each visit\n\n"
        "> ## Date of visit* {visit-date}\n"
        "> (text)\n\n"
        "> ## Reason for visit {visit-reason}\n"
        "> (mc_multi)\n"
        "> - Routine check-up\n"
        "> - Acute illness\n"
        ">   + Please describe symptoms\n"
        "> - Follow-up appointment\n"
        "> - Other\n"
        ">   + Please specify\n\n"
        "# Follow up {follow-up}\n"
        "Post-visit questions\n\n"
        "## Overall satisfaction* {follow-up-overall}\n"
        "Rate from 1 to 5\n"
        "(likert number)\n"
        "min: 1\n"
        "max: 5\n"
        "left: Very poor\n"
        "right: Excellent\n\n"
        "## Recommend to a friend {follow-up-recommend}\n"
        "Likelihood to recommend\n"
        "(likert categories)\n"
        "- Very unlikely\n"
        "- Unlikely\n"
        "- Neutral\n"
        "- Likely\n"
        "- Very likely\n"
    )


# ============================================================================
# Email Notification Helpers
# ============================================================================


def _send_survey_closure_notification(survey: Survey, user: User) -> None:
    """
    Send email notification to survey owner when survey is closed.

    Confirms closure and reminds about retention timeline.
    """
    from django.conf import settings
    from django.template.loader import render_to_string

    from checktick_app.core.email_utils import get_platform_branding, send_branded_email

    subject = f"Survey Closed: {survey.name}"

    closed_time = survey.closed_at.strftime("%B %d, %Y at %I:%M %p")
    deletion_date = survey.deletion_date.strftime("%B %d, %Y")

    branding = get_platform_branding()

    markdown_content = render_to_string(
        "emails/data_governance/survey_closed.md",
        {
            "survey": survey,
            "closed_by": user,
            "closed_time": closed_time,
            "response_count": survey.responses.count(),
            "deletion_date": deletion_date,
            "warning_schedule": "30 days, 7 days, and 1 day before deletion",
            "brand_title": branding["title"],
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        },
    )

    send_branded_email(
        to_email=survey.owner.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
    )


# ==============================================================================
# Dataset Management Views
# ==============================================================================


@login_required
def dataset_list(request: HttpRequest) -> HttpResponse:
    """List all datasets available to the user (global + their org datasets)."""
    from django.core.paginator import Paginator

    user = request.user

    # Get organizations where user is a member
    user_orgs = Organization.objects.filter(memberships__user=user)

    # Build base queryset: global datasets + datasets from user's organizations + individual user datasets
    base_datasets = DataSet.objects.filter(
        Q(is_global=True)
        | Q(organization__in=user_orgs)
        | Q(created_by=user, organization__isnull=True),
        is_active=True,
    ).select_related("organization", "created_by", "parent")

    # Get all unique tags from base datasets (before filtering) for facets
    all_tags = {}
    for dataset in base_datasets:
        for tag in dataset.tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1

    # Sort tags by count (descending) then alphabetically
    available_tags = sorted(
        [(tag, count) for tag, count in all_tags.items()],
        key=lambda x: (-x[1], x[0]),
    )

    # Now apply filters
    datasets = base_datasets

    # Apply category filter if provided
    category_filter = request.GET.get("category")
    if category_filter:
        datasets = datasets.filter(category=category_filter)

    # Apply tag filter if provided (AND logic for multiple tags)
    tag_filter = request.GET.get("tags")
    selected_tags = []
    if tag_filter:
        selected_tags = [t.strip() for t in tag_filter.split(",") if t.strip()]
        for tag in selected_tags:
            datasets = datasets.filter(tags__contains=[tag])

    # Order datasets
    datasets = datasets.order_by("-created_at")

    # Pagination (20 per page)
    paginator = Paginator(datasets, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get user's organizations for create permission check
    can_create = can_create_datasets(user)

    # Get unique categories for filter dropdown
    categories = DataSet.CATEGORY_CHOICES

    return render(
        request,
        "surveys/dataset_list.html",
        {
            "page_obj": page_obj,
            "can_create": can_create,
            "categories": categories,
            "available_tags": available_tags,
            "selected_category": category_filter,
            "selected_tags": selected_tags,
        },
    )


@login_required
def dataset_detail(request: HttpRequest, dataset_id: int) -> HttpResponse:
    """View details of a specific dataset."""
    user = request.user

    # Get user's organizations
    user_orgs = Organization.objects.filter(memberships__user=user)

    # Get dataset and check access
    dataset = get_object_or_404(
        DataSet.objects.filter(
            Q(is_global=True) | Q(organization__in=user_orgs), is_active=True
        ).select_related("organization", "created_by", "parent"),
        id=dataset_id,
    )

    # Check if user can edit this dataset
    user_can_edit = can_edit_dataset(user, dataset)

    # Get questions using this dataset
    questions_using = SurveyQuestion.objects.filter(dataset=dataset).select_related(
        "survey", "group"
    )

    return render(
        request,
        "surveys/dataset_detail.html",
        {
            "dataset": dataset,
            "can_edit": user_can_edit,
            "questions_using": questions_using,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def dataset_create(request: HttpRequest) -> HttpResponse:
    """Create a new dataset."""
    require_can_create_datasets(request.user)

    # Get organizations where user is ADMIN or CREATOR
    user_orgs = Organization.objects.filter(
        memberships__user=request.user,
        memberships__role__in=[
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.CREATOR,
        ],
    )

    if request.method == "POST":
        # Extract form data
        key = request.POST.get("key", "").strip()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        tags_text = request.POST.get("tags", "").strip()
        organization_id = request.POST.get("organization", "").strip()
        options_text = request.POST.get("options", "").strip()

        # All user-created datasets have these defaults
        category = "user_created"
        source_type = "manual"

        # Validate
        errors = []

        if not name:
            errors.append("Name is required")

        # Parse tags
        tags = []
        if tags_text:
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

        # Auto-generate key from name if not provided or invalid
        if not key:
            # Generate key from name
            key = (
                name.lower()
                .strip()
                .replace(" ", "_")
                # Replace any non-alphanumeric chars with underscore
                .translate(
                    str.maketrans({c: "_" for c in "!@#$%^&*()+=[]{}|\\:;\"'<>,.?/"})
                )
            )
            key = re.sub(r"_+", "_", key)  # Collapse multiple underscores
            key = key.strip("_")  # Remove leading/trailing underscores

        if not re.match(r"^[a-z0-9_-]+$", key):
            errors.append(
                "Generated key is invalid. Please use a simpler name with only letters, numbers, and spaces."
            )

        # Check for duplicate keys and make unique if needed
        if DataSet.objects.filter(key=key).exists():
            # For individual users, append user ID; for org users, append timestamp
            if not organization_id:
                key = f"{key}_u{request.user.id}"
                # If still duplicate, add timestamp
                if DataSet.objects.filter(key=key).exists():
                    import time

                    key = f"{key}_{int(time.time())}"
            else:
                import time

                key = f"{key}_{int(time.time())}"

        # Handle organization - optional for individual users
        org = None
        if organization_id:
            try:
                org = Organization.objects.get(id=organization_id)
                # Verify user has permission in this org
                if not user_orgs.filter(id=org.id).exists():
                    errors.append(
                        "You don't have permission in the selected organization"
                    )
            except Organization.DoesNotExist:
                errors.append("Invalid organization selected")

        # Parse options intelligently
        options = []
        options_dict = {}
        has_keyed_options = False
        line_errors = []

        if options_text:
            lines = [line.strip() for line in options_text.split("\n") if line.strip()]

            for idx, line in enumerate(lines, 1):
                # Check if line contains " - " separator (key-value format)
                if " - " in line:
                    has_keyed_options = True
                    parts = line.split(" - ", 1)
                    if len(parts) == 2:
                        option_key = parts[0].strip()
                        option_value = parts[1].strip()
                        if option_key and option_value:
                            options_dict[option_key] = option_value
                        else:
                            line_errors.append(f"Line {idx}: Empty key or value")
                    else:
                        line_errors.append(f"Line {idx}: Invalid format")
                else:
                    # Simple option - store for auto-key generation
                    options.append(line)

            # Convert to dict format (always use dict for consistency)
            if has_keyed_options:
                if options:
                    # Mixed format detected
                    errors.append(
                        "Mixed format detected. Use either simple format (one value per line) "
                        "OR key-value format (key - value) for all options, not both."
                    )
                elif not options_dict:
                    errors.append(
                        "Key-value format detected but no valid entries found. "
                        "Ensure format is 'key - value' with space-dash-space separator."
                    )
                else:
                    # Use the manually entered key-value pairs
                    options = options_dict
            elif options:
                # Auto-generate keys for simple list format
                # Use sequential numbers as keys for simplicity and reliability
                options_dict = {}
                for idx, value in enumerate(options, 1):
                    # Use zero-padded numbers as keys (e.g., "001", "002")
                    auto_key = f"{idx:03d}"
                    options_dict[auto_key] = value
                options = options_dict
            else:
                errors.append("At least one option is required")

        if line_errors:
            errors.extend(line_errors)

        if not options:
            errors.append("At least one option is required")

        if errors:
            messages.error(request, " | ".join(errors))
            return render(
                request,
                "surveys/dataset_form.html",
                {
                    "organizations": user_orgs,
                    "form_data": request.POST,
                    "is_create": True,
                },
            )

        # Create dataset
        dataset = DataSet.objects.create(
            key=key,
            name=name,
            description=description,
            category=category,
            source_type=source_type,
            organization=org,  # Can be None for individual users
            is_global=False,  # Regular users cannot create global datasets
            options=options,
            tags=tags,
            created_by=request.user,
        )

        messages.success(request, f"Dataset '{dataset.name}' created successfully")
        return redirect("surveys:dataset_detail", dataset_id=dataset.id)

    # Check if cloning from existing dataset
    clone_from_id = request.GET.get("clone_from")
    clone_source = None
    initial_data = {}

    if clone_from_id:
        try:
            # Get the source dataset to clone from
            all_user_orgs = Organization.objects.filter(memberships__user=request.user)
            clone_source = DataSet.objects.filter(
                Q(is_global=True)
                | Q(organization__in=all_user_orgs)
                | Q(created_by=request.user, organization__isnull=True),
                is_active=True,
                id=clone_from_id,
            ).first()

            if clone_source:
                # Pre-fill form with source dataset data
                options_text = "\n".join(
                    [f"{key} - {value}" for key, value in clone_source.options.items()]
                )
                tags_text = ", ".join(clone_source.tags) if clone_source.tags else ""

                initial_data = {
                    "name": f"{clone_source.name} (Custom)",
                    "description": clone_source.description,
                    "options": options_text,
                    "tags": tags_text,
                }
        except (ValueError, DataSet.DoesNotExist):
            pass

    return render(
        request,
        "surveys/dataset_form.html",
        {
            "organizations": user_orgs,
            "is_create": True,
            "clone_source": clone_source,
            "form_data": initial_data,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def dataset_edit(request: HttpRequest, dataset_id: int) -> HttpResponse:
    """Edit an existing dataset."""
    user = request.user

    # Get user's organizations
    user_orgs = Organization.objects.filter(
        memberships__user=user,
        memberships__role__in=[
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.CREATOR,
        ],
    )

    # Get dataset - check if accessible first
    all_user_orgs = Organization.objects.filter(memberships__user=user)
    dataset = get_object_or_404(
        DataSet.objects.filter(
            Q(is_global=True)
            | Q(organization__in=all_user_orgs)
            | Q(created_by=user, organization__isnull=True),
            is_active=True,
        ),
        id=dataset_id,
    )

    require_can_edit_dataset(user, dataset)

    if request.method == "POST":
        # Extract form data
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        tags_text = request.POST.get("tags", "").strip()
        options_text = request.POST.get("options", "").strip()

        # Validate
        errors = []

        if not name:
            errors.append("Name is required")

        # Parse tags
        tags = []
        if tags_text:
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

        # Parse options intelligently (same logic as create)
        options = []
        options_dict = {}
        has_keyed_options = False
        line_errors = []

        if options_text:
            lines = [line.strip() for line in options_text.split("\n") if line.strip()]

            for idx, line in enumerate(lines, 1):
                # Check if line contains " - " separator (key-value format)
                if " - " in line:
                    has_keyed_options = True
                    parts = line.split(" - ", 1)
                    if len(parts) == 2:
                        option_key = parts[0].strip()
                        option_value = parts[1].strip()
                        if option_key and option_value:
                            options_dict[option_key] = option_value
                        else:
                            line_errors.append(f"Line {idx}: Empty key or value")
                    else:
                        line_errors.append(f"Line {idx}: Invalid format")
                else:
                    # Simple option - store for auto-key generation
                    options.append(line)

            # Convert to dict format (always use dict for consistency)
            if has_keyed_options:
                if options:
                    # Mixed format detected
                    errors.append(
                        "Mixed format detected. Use either simple format (one value per line) "
                        "OR key-value format (key - value) for all options, not both."
                    )
                elif not options_dict:
                    errors.append(
                        "Key-value format detected but no valid entries found. "
                        "Ensure format is 'key - value' with space-dash-space separator."
                    )
                else:
                    # Use the manually entered key-value pairs
                    options = options_dict
            elif options:
                # Auto-generate keys for simple list format
                options_dict = {}
                for idx, value in enumerate(options, 1):
                    auto_key = f"{idx:03d}"
                    options_dict[auto_key] = value
                options = options_dict
            else:
                errors.append("At least one option is required")

        if line_errors:
            errors.extend(line_errors)

        if not options:
            errors.append("At least one option is required")

        if errors:
            messages.error(request, " | ".join(errors))
            return render(
                request,
                "surveys/dataset_form.html",
                {
                    "dataset": dataset,
                    "organizations": user_orgs,
                    "form_data": request.POST,
                    "is_create": False,
                },
            )

        # Update dataset
        dataset.name = name
        dataset.description = description
        dataset.options = options
        dataset.tags = tags
        dataset.increment_version()
        dataset.save()

        messages.success(request, f"Dataset '{dataset.name}' updated successfully")
        return redirect("surveys:dataset_detail", dataset_id=dataset.id)

    # Prepare initial form data
    # Convert options dict to text format for textarea (all datasets use dict now)
    options_text = "\n".join(
        [f"{key} - {value}" for key, value in dataset.options.items()]
    )

    # Convert tags list to comma-separated string
    tags_text = ", ".join(dataset.tags) if dataset.tags else ""

    form_data = {
        "key": dataset.key,
        "name": dataset.name,
        "description": dataset.description,
        "category": dataset.category,
        "source_type": dataset.source_type,
        "organization": dataset.organization_id,
        "options": options_text,
        "tags": tags_text,
    }

    return render(
        request,
        "surveys/dataset_form.html",
        {
            "dataset": dataset,
            "organizations": user_orgs,
            "form_data": form_data,
            "is_create": False,
        },
    )


@login_required
@require_http_methods(["POST"])
def dataset_delete(request: HttpRequest, dataset_id: int) -> HttpResponse:
    """Soft delete a dataset (set is_active=False)."""
    user = request.user

    # Get dataset - check if accessible first
    all_user_orgs = Organization.objects.filter(memberships__user=user)
    dataset = get_object_or_404(
        DataSet.objects.filter(
            Q(is_global=True)
            | Q(organization__in=all_user_orgs)
            | Q(created_by=user, organization__isnull=True),
            is_active=True,
        ),
        id=dataset_id,
    )

    require_can_edit_dataset(user, dataset)

    # Soft delete
    dataset.is_active = False
    dataset.save(update_fields=["is_active"])

    messages.success(request, f"Dataset '{dataset.name}' deleted successfully")
    return redirect("surveys:dataset_list")


# Published Question Group Templates


@login_required
def published_templates_list(request):
    """Browse published question group templates."""
    from django.core.paginator import Paginator
    from django.db.models import Q

    user = request.user

    # Get user's organizations
    user_org_ids = list(
        OrganizationMembership.objects.filter(user=user).values_list(
            "organization_id", flat=True
        )
    )

    # Base queryset: active templates
    templates = PublishedQuestionGroup.objects.filter(
        status=PublishedQuestionGroup.Status.ACTIVE
    ).select_related("publisher", "organization")

    # Filter by visibility:
    # - Individual users (not in any org): only global templates
    # - Organization users: global templates + their org's templates
    if user_org_ids:
        # User is in at least one organization - show global and their org templates
        templates = templates.filter(
            Q(publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL)
            | Q(
                publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
                organization_id__in=user_org_ids,
            )
        )
    else:
        # Individual user not in any organization - only global templates
        templates = templates.filter(
            publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL
        )

    # Search filter
    search = request.GET.get("search", "").strip()
    if search:
        templates = templates.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(tags__icontains=search)
        )

    # Level filter
    level = request.GET.get("level", "").strip()
    if level in ["global", "organization"]:
        templates = templates.filter(publication_level=level)

    # Tag filter
    tag = request.GET.get("tag", "").strip()
    if tag:
        templates = templates.filter(tags__contains=[tag])

    # Language filter
    language = request.GET.get("language", "").strip()
    if language:
        templates = templates.filter(language=language)

    # Ordering
    order = request.GET.get("order", "-created_at")
    if order in ["name", "-name", "-created_at", "-import_count"]:
        templates = templates.order_by(order)

    # Get all tags for filter dropdown
    all_tags = set()
    for template in PublishedQuestionGroup.objects.filter(
        status=PublishedQuestionGroup.Status.ACTIVE
    ):
        all_tags.update(template.tags or [])

    # Pagination
    paginator = Paginator(templates, 20)  # 20 templates per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get user's surveys for import dropdown
    user_surveys = Survey.objects.filter(owner=request.user).order_by("-created_at")[
        :20
    ]

    return render(
        request,
        "surveys/published_templates_list.html",
        {
            "page_obj": page_obj,
            "search_query": search,
            "selected_level": level,
            "selected_language": language,
            "selected_order": order,
            "all_tags": sorted(all_tags),
            "user_surveys": user_surveys,
        },
    )


@login_required
def published_template_detail(request, template_id):
    """View details of a published template."""
    from .permissions import can_import_published_template

    template = get_object_or_404(PublishedQuestionGroup, pk=template_id)

    # Check access
    if not can_import_published_template(request.user, template):
        raise PermissionDenied("You do not have access to this template.")

    # Get user's surveys for import dropdown
    user_surveys = Survey.objects.filter(owner=request.user).order_by("-created_at")[
        :20
    ]

    # Check if user can delete this template
    can_delete = template.publisher == request.user

    return render(
        request,
        "surveys/published_template_detail.html",
        {
            "template": template,
            "user_surveys": user_surveys,
            "can_delete": can_delete,
        },
    )


@login_required
def published_template_preview(request, template_id):
    """Preview markdown for a published template."""
    from .permissions import can_import_published_template

    template = get_object_or_404(PublishedQuestionGroup, pk=template_id)

    # Check access
    if not can_import_published_template(request.user, template):
        raise PermissionDenied("You do not have access to this template.")

    return render(
        request,
        "surveys/published_template_preview.html",
        {
            "template": template,
            "markdown": template.markdown,
        },
    )


@login_required
@ratelimit(key="user", rate="10/d", block=True)
def question_group_publish(request, slug, gid):
    """Publish a QuestionGroup as a template."""
    from .forms import PublishQuestionGroupForm
    from .permissions import require_can_edit

    survey = get_object_or_404(Survey, slug=slug)
    require_can_edit(request.user, survey)

    group = get_object_or_404(QuestionGroup, pk=gid, owner=request.user)

    # Prevent publishing of imported question groups
    if group.imported_from:
        messages.error(
            request,
            "Cannot publish question groups that were imported from templates to prevent copyright issues.",
        )
        return redirect("surveys:group_builder", slug=slug, gid=gid)

    # Check if group has questions
    questions = SurveyQuestion.objects.filter(survey=survey, group=group)
    if not questions.exists():
        messages.error(request, "Cannot publish an empty question group.")
        return redirect("surveys:group_builder", slug=slug, gid=gid)

    if request.method == "POST":
        form = PublishQuestionGroupForm(
            request.POST, user=request.user, question_group=group, survey=survey
        )
        if form.is_valid():
            # Generate markdown from group
            markdown = _export_question_group_to_markdown(group, survey)

            # Create publication
            publication = form.save(commit=False)
            publication.source_group = group
            publication.publisher = request.user
            publication.markdown = markdown

            # Set organization if org-level
            if (
                publication.publication_level
                == PublishedQuestionGroup.PublicationLevel.ORGANIZATION
            ):
                # Get organization from survey
                if not survey.organization:
                    messages.error(
                        request,
                        "Organization-level publishing requires the survey to be associated with an organization.",
                    )
                    return redirect("surveys:group_builder", slug=slug, gid=gid)
                publication.organization = survey.organization

            publication.save()

            messages.success(
                request,
                f"Question group '{publication.name}' published successfully!",
            )
            return redirect(
                "surveys:published_template_detail", template_id=publication.pk
            )
    else:
        form = PublishQuestionGroupForm(
            user=request.user, question_group=group, survey=survey
        )

    return render(
        request,
        "surveys/question_group_publish.html",
        {
            "survey": survey,
            "group": group,
            "form": form,
            "questions": questions,
        },
    )


@login_required
@ratelimit(key="user", rate="50/h", block=True)
def published_template_import(request, template_id, slug):
    """Import a published template into a survey."""
    from .markdown_import import parse_bulk_markdown
    from .permissions import require_can_edit, require_can_import_published_template

    template = get_object_or_404(PublishedQuestionGroup, pk=template_id)
    survey = get_object_or_404(Survey, slug=slug)

    require_can_edit(request.user, survey)
    require_can_import_published_template(request.user, template)

    if request.method == "POST":
        try:
            # Parse markdown
            groups = parse_bulk_markdown(template.markdown)

            if not groups:
                messages.error(request, "Template has no valid groups to import.")
                return redirect("surveys:published_templates_list")

            # Import first group (templates typically have one group)
            group_data = groups[0]

            # Create QuestionGroup
            new_group = QuestionGroup.objects.create(
                name=group_data.get("name", template.name),
                description=group_data.get("description", ""),
                owner=request.user,
                imported_from=template,
            )

            # Add to survey
            survey.question_groups.add(new_group)

            # Create questions
            for q_data in group_data.get("questions", []):
                SurveyQuestion.objects.create(
                    survey=survey,
                    group=new_group,
                    text=q_data.get("text", ""),
                    type=q_data.get("type", "short_text"),
                    options=q_data.get("options"),
                    required=q_data.get("required", False),
                    order=q_data.get("order", 0),
                )

            # Increment import count
            template.increment_import_count()

            messages.success(
                request,
                f"Template '{template.name}' imported successfully!",
            )
            return redirect("surveys:group_builder", slug=slug, gid=new_group.pk)

        except Exception as e:
            messages.error(request, f"Error importing template: {str(e)}")
            return redirect(
                "surveys:published_template_detail", template_id=template_id
            )

    return render(
        request,
        "surveys/published_template_import.html",
        {
            "template": template,
            "survey": survey,
        },
    )


@login_required
def published_template_delete(request, template_id):
    """Soft delete a published template."""
    from .permissions import require_can_delete_published_template

    template = get_object_or_404(PublishedQuestionGroup, pk=template_id)
    require_can_delete_published_template(request.user, template)

    if request.method == "POST":
        # Soft delete
        template.status = PublishedQuestionGroup.Status.DELETED
        template.save(update_fields=["status"])

        messages.success(request, f"Template '{template.name}' deleted successfully.")
        return redirect("surveys:published_templates_list")

    return render(
        request,
        "surveys/published_template_delete.html",
        {
            "template": template,
        },
    )


def _export_question_group_to_markdown(group: QuestionGroup, survey: Survey) -> str:
    """Export a single QuestionGroup to markdown format with attribution."""
    lines = []

    # Add attribution as HTML comment if it exists
    if hasattr(group, "attribution") and group.attribution:
        import json

        attribution = group.attribution
        # Human-readable line
        parts = []
        if "authors" in attribution and attribution["authors"]:
            authors = attribution["authors"]
            if len(authors) == 1:
                parts.append(authors[0].get("name", ""))
            elif len(authors) > 1:
                parts.append(f"{authors[0].get('name', '')} et al.")
        if "year" in attribution:
            parts.append(f"({attribution['year']})")
        if "pmid" in attribution:
            parts.append(f"PMID: {attribution['pmid']}")

        human_line = ", ".join(p for p in parts if p)

        # Add comment
        if human_line:
            lines.append(f"<!-- Attribution: {human_line}")
            lines.append(f"     {json.dumps(attribution)} -->")
            lines.append("")

    # Add group heading
    group_ref = group.name.lower().replace(" ", "-")
    lines.append(f"# {group.name} {{{group_ref}}}")
    if group.description:
        lines.append(group.description)
    lines.append("")

    # Get questions for this group
    questions = SurveyQuestion.objects.filter(survey=survey, group=group).order_by(
        "order"
    )

    # Add questions
    for question in questions:
        required = "*" if question.required else ""
        question_ref = question.text.lower()[:30].replace(" ", "-").strip("-")
        lines.append(f"## {question.text}{required} {{{question_ref}}}")

        # Determine the export type name
        export_type = question.type

        # Handle special cases where DB type differs from markdown type
        if question.type == "text" and question.options:
            # Check if it's text number
            if isinstance(question.options, list) and len(question.options) > 0:
                first_option = question.options[0]
                if (
                    first_option.get("type") == "text"
                    and first_option.get("format") == "number"
                ):
                    export_type = "text number"
        elif question.type == "likert" and question.options:
            # Check if it's categories or number
            if isinstance(question.options, list) and len(question.options) > 0:
                first_option = question.options[0]
                if first_option.get("type") == "categories":
                    export_type = "likert categories"
                elif first_option.get("type") in ["number", "number-scale"]:
                    export_type = "likert number"

        # Question type
        lines.append(f"({export_type})")

        # Handle likert type (which can be categories or number)
        if question.type == "likert" and question.options:
            # Check if it's categories or number type
            if isinstance(question.options, list) and len(question.options) > 0:
                first_option = question.options[0]
                if (
                    first_option.get("type") == "categories"
                    and "labels" in first_option
                ):
                    # Likert categories - export as list
                    for label in first_option["labels"]:
                        lines.append(f"- {label}")
                elif first_option.get("type") in ["number", "number-scale"]:
                    # Likert number - export min/max/labels
                    min_val = first_option.get("min")
                    max_val = first_option.get("max")
                    left_label = first_option.get("left_label", "")
                    right_label = first_option.get("right_label", "")
                    if min_val is not None:
                        lines.append(f"min: {min_val}")
                    if max_val is not None:
                        lines.append(f"max: {max_val}")
                    if left_label:
                        lines.append(f"left: {left_label}")
                    if right_label:
                        lines.append(f"right: {right_label}")

        # Options for question types that need them
        elif question.type in [
            "mc_single",
            "mc_multi",
            "dropdown",
            "orderable",
            "yesno",
            "image",
            "likert categories",
        ]:
            if question.options:
                for option in question.options:
                    # Options can have 'text', 'label', or 'value' keys
                    option_text = (
                        option.get("text")
                        or option.get("label")
                        or option.get("value", "")
                    )
                    lines.append(f"- {option_text}")
                    # Check for follow-up text
                    if option.get("has_followup_text"):
                        followup_label = option.get(
                            "followup_text_label", "Please specify"
                        )
                        lines.append(f"  + {followup_label}")

        # Likert number settings
        elif question.type == "likert number":
            if question.options:
                min_val = question.options.get("min")
                max_val = question.options.get("max")
                left_label = question.options.get("left_label", "")
                right_label = question.options.get("right_label", "")

                if min_val is not None:
                    lines.append(f"min: {min_val}")
                if max_val is not None:
                    lines.append(f"max: {max_val}")
                if left_label:
                    lines.append(f"left: {left_label}")
                if right_label:
                    lines.append(f"right: {right_label}")

        # Branching rules
        conditions = SurveyQuestionCondition.objects.filter(question=question)
        for condition in conditions:
            operator = condition.operator
            value = condition.value or ""
            if condition.target_question:
                target_ref = (
                    condition.target_question.text.lower()[:30]
                    .replace(" ", "-")
                    .strip("-")
                )
                lines.append(f"? when {operator} {value} -> {{{target_ref}}}")

        lines.append("")

    return "\n".join(lines)


@login_required
def branching_data_api(request: HttpRequest, slug: str) -> JsonResponse:
    """
    API endpoint to provide branching visualization data.
    Returns all questions and their conditions for the survey.
    """
    survey = get_object_or_404(Survey, slug=slug)
    require_can_view(request.user, survey)

    # Get all questions ordered properly
    questions_qs = survey.questions.select_related("group").prefetch_related(
        "conditions", "conditions__target_question"
    )
    ordered_questions = _order_questions_by_group(survey, list(questions_qs))

    # Get repeat information for groups
    group_repeat_map: dict[int, list[CollectionDefinition]] = {}
    for item in CollectionItem.objects.select_related("collection", "group").filter(
        collection__survey=survey, group__isnull=False
    ):
        group_repeat_map.setdefault(item.group_id, []).append(item.collection)

    # Build group repeat info with max counts
    group_repeats: dict[str, dict] = {}
    for group_id, collections in group_repeat_map.items():
        max_counts = []
        for c in collections:
            if c.max_count and int(c.max_count) > 0:
                max_counts.append(int(c.max_count))

        if max_counts:
            # Use the first max_count if there are multiple collections
            group_repeats[str(group_id)] = {"is_repeated": True, "count": max_counts[0]}
        else:
            group_repeats[str(group_id)] = {
                "is_repeated": True,
                "count": None,  # Unlimited
            }

    questions_data = []
    conditions_data = {}

    for index, q in enumerate(ordered_questions):
        question_data = {
            "id": str(q.id),
            "text": q.text,
            "order": index,
            "group_name": q.group.name if q.group else None,
            "group_id": str(q.group.id) if q.group else None,
        }
        questions_data.append(question_data)

        # Get conditions for this question
        conditions = list(q.conditions.all())
        if conditions:
            conditions_data[str(q.id)] = []
            for cond in conditions:
                cond_data = {
                    "operator": cond.operator,
                    "value": cond.value or "",
                    "action": cond.action,
                    "target_question": (
                        str(cond.target_question.id) if cond.target_question else None
                    ),
                    "description": cond.description or "",
                }
                conditions_data[str(q.id)].append(cond_data)

    return JsonResponse(
        {
            "questions": questions_data,
            "conditions": conditions_data,
            "group_repeats": group_repeats,
        }
    )


# ============================================================================
# SUPERUSER RECOVERY DASHBOARD VIEWS
# Platform-level key recovery console for superusers only.
# Rate limited: 5 actions/hour for sensitive operations.
# ============================================================================


def superuser_required(view_func):
    """
    Decorator that requires the user to be a superuser.
    Returns 403 Forbidden for non-superusers.
    """
    from functools import wraps

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.is_superuser:
            raise PermissionDenied("This page is restricted to platform superusers.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@login_required
@superuser_required
@ratelimit(key="user", rate="30/h", block=True)
def recovery_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Platform Recovery Console for superusers.

    Shows ALL recovery requests across ALL organizations.
    Superusers can:
    - View all pending recovery requests
    - Approve/reject requests (as emergency override)
    - Execute recoveries
    - Enter keys/passphrases for emergency recovery

    Rate limited: 30 views/hour to prevent abuse.
    """
    # Superuser sees ALL recovery requests
    recovery_requests = RecoveryRequest.objects.select_related(
        "user",
        "survey",
        "survey__organization",
        "primary_approver",
        "secondary_approver",
    ).order_by("-submitted_at")

    # Apply filter
    filter_param = request.GET.get("filter", "all")
    if filter_param == "pending":
        recovery_requests = recovery_requests.filter(
            status__in=[
                RecoveryRequest.Status.PENDING_VERIFICATION,
                RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
            ]
        )
    elif filter_param == "approval":
        recovery_requests = recovery_requests.filter(
            status__in=[
                RecoveryRequest.Status.AWAITING_PRIMARY,
                RecoveryRequest.Status.AWAITING_SECONDARY,
            ]
        )
    elif filter_param == "delay":
        recovery_requests = recovery_requests.filter(
            status=RecoveryRequest.Status.IN_TIME_DELAY
        )
    elif filter_param == "ready":
        recovery_requests = recovery_requests.filter(
            status=RecoveryRequest.Status.READY_FOR_EXECUTION
        )
    elif filter_param == "completed":
        recovery_requests = recovery_requests.filter(
            status__in=[
                RecoveryRequest.Status.COMPLETED,
                RecoveryRequest.Status.REJECTED,
                RecoveryRequest.Status.CANCELLED,
            ]
        )

    # Calculate stats across ALL requests
    all_requests = RecoveryRequest.objects.all()
    stats = {
        "total": all_requests.count(),
        "pending": all_requests.filter(
            status__in=[
                RecoveryRequest.Status.PENDING_VERIFICATION,
                RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
            ]
        ).count(),
        "awaiting_approval": all_requests.filter(
            status__in=[
                RecoveryRequest.Status.AWAITING_PRIMARY,
                RecoveryRequest.Status.AWAITING_SECONDARY,
            ]
        ).count(),
        "in_delay": all_requests.filter(
            status=RecoveryRequest.Status.IN_TIME_DELAY
        ).count(),
        "ready": all_requests.filter(
            status=RecoveryRequest.Status.READY_FOR_EXECUTION
        ).count(),
        "completed": all_requests.filter(
            status=RecoveryRequest.Status.COMPLETED
        ).count(),
    }

    # Statuses that can be rejected
    rejectable_statuses = [
        RecoveryRequest.Status.PENDING_VERIFICATION,
        RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
        RecoveryRequest.Status.AWAITING_PRIMARY,
        RecoveryRequest.Status.AWAITING_SECONDARY,
    ]

    context = {
        "is_superuser": True,
        "recovery_requests": recovery_requests,
        "stats": stats,
        "filter": filter_param,
        "can_approve_primary": True,  # Superusers can do anything
        "can_approve_secondary": True,
        "can_emergency_override": True,  # Superuser special
        "rejectable_statuses": rejectable_statuses,
        "user": request.user,
    }
    return render(request, "surveys/recovery_dashboard.html", context)


@login_required
@superuser_required
@ratelimit(key="user", rate="30/h", block=True)
def recovery_detail(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Detailed view of a single recovery request for superusers.
    """
    recovery_request = get_object_or_404(
        RecoveryRequest.objects.select_related(
            "user",
            "survey",
            "survey__organization",
            "primary_approver",
            "secondary_approver",
            "rejected_by",
            "cancelled_by",
            "executed_by",
        ),
        id=request_id,
    )

    # Get identity verifications
    identity_verifications = recovery_request.identity_verifications.all().order_by(
        "verification_type"
    )

    # Get audit entries
    audit_entries = recovery_request.audit_entries.all().order_by("-timestamp")[:50]

    # Statuses that can be rejected
    rejectable_statuses = [
        RecoveryRequest.Status.PENDING_VERIFICATION,
        RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
        RecoveryRequest.Status.AWAITING_PRIMARY,
        RecoveryRequest.Status.AWAITING_SECONDARY,
    ]

    context = {
        "recovery_request": recovery_request,
        "identity_verifications": identity_verifications,
        "audit_entries": audit_entries,
        "can_approve_primary": True,
        "can_approve_secondary": True,
        "can_emergency_override": True,
        "rejectable_statuses": rejectable_statuses,
        "user": request.user,
        "is_superuser": True,
    }
    return render(request, "surveys/recovery_detail.html", context)


@login_required
@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def recovery_approve_primary(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Approve a recovery request as primary approver (superuser override).

    Rate limited: 5 approvals/hour.
    """
    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Cannot approve your own request
    if recovery_request.user == request.user:
        messages.error(request, "You cannot approve your own recovery request.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    # Check status
    if recovery_request.status != RecoveryRequest.Status.AWAITING_PRIMARY:
        messages.error(request, "This request is not awaiting primary approval.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    try:
        recovery_request.approve_primary(
            admin=request.user,
            reason=f"Superuser override approval via Platform Recovery Console by {request.user.email}",
        )

        # Log superuser action
        logger.warning(
            f"SUPERUSER ACTION: {request.user.email} approved primary for recovery request "
            f"{recovery_request.request_code} (survey: {recovery_request.survey.slug})"
        )

        messages.success(
            request, "Primary approval granted successfully (superuser override)."
        )
    except Exception as e:
        messages.error(request, f"Error approving request: {e}")

    return redirect("surveys:recovery_detail", request_id=request_id)


@login_required
@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def recovery_approve_secondary(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Approve a recovery request as secondary approver (superuser override).

    Rate limited: 5 approvals/hour.
    """
    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Cannot approve your own request
    if recovery_request.user == request.user:
        messages.error(request, "You cannot approve your own recovery request.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    # Note: superusers CAN be both primary and secondary in emergency scenarios
    # This is intentional - sometimes there's only one superuser available

    # Check status
    if recovery_request.status != RecoveryRequest.Status.AWAITING_SECONDARY:
        messages.error(request, "This request is not awaiting secondary approval.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    try:
        recovery_request.approve_secondary(
            admin=request.user,
            reason=f"Superuser override approval via Platform Recovery Console by {request.user.email}",
        )

        # Log superuser action
        logger.warning(
            f"SUPERUSER ACTION: {request.user.email} approved secondary for recovery request "
            f"{recovery_request.request_code} (survey: {recovery_request.survey.slug})"
        )

        messages.success(
            request,
            f"Secondary approval granted (superuser override). Time delay of {recovery_request.time_delay_hours} hours has started.",
        )
    except Exception as e:
        messages.error(request, f"Error approving request: {e}")

    return redirect("surveys:recovery_detail", request_id=request_id)


@login_required
@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def recovery_reject(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Reject a recovery request (superuser).

    Rate limited: 5 rejections/hour.
    """
    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Check status
    rejectable_statuses = [
        RecoveryRequest.Status.PENDING_VERIFICATION,
        RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
        RecoveryRequest.Status.AWAITING_PRIMARY,
        RecoveryRequest.Status.AWAITING_SECONDARY,
    ]

    if recovery_request.status not in rejectable_statuses:
        messages.error(request, "This request cannot be rejected in its current state.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    reason = request.POST.get(
        "reason", "Rejected via Platform Recovery Console (superuser)"
    )

    try:
        recovery_request.reject(admin=request.user, reason=reason)

        # Log superuser action
        logger.warning(
            f"SUPERUSER ACTION: {request.user.email} rejected recovery request "
            f"{recovery_request.request_code} (survey: {recovery_request.survey.slug}). Reason: {reason}"
        )

        messages.success(request, "Recovery request has been rejected.")
    except Exception as e:
        messages.error(request, f"Error rejecting request: {e}")

    return redirect("surveys:recovery_detail", request_id=request_id)


@login_required
@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="3/h", block=True)
def recovery_execute(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Execute a recovery request that has passed the time delay (superuser).

    Rate limited: 3 executions/hour (very sensitive operation).

    Requires:
    - new_password: The user's new password for re-encrypting the survey KEK
    """
    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Validate new password was provided
    new_password = request.POST.get("new_password", "").strip()
    confirm_password = request.POST.get("confirm_password", "").strip()

    if not new_password:
        messages.error(request, "A new password is required to execute recovery.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    if len(new_password) < 8:
        messages.error(request, "Password must be at least 8 characters long.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    if new_password != confirm_password:
        messages.error(request, "Passwords do not match.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    # Check if in time delay and ready
    if recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY:
        if (
            recovery_request.time_delay_until
            and timezone.now() >= recovery_request.time_delay_until
        ):
            recovery_request.status = RecoveryRequest.Status.READY_FOR_EXECUTION
            recovery_request.save(update_fields=["status"])
        else:
            messages.error(request, "Time delay has not completed yet.")
            return redirect("surveys:recovery_detail", request_id=request_id)

    # Check status
    if recovery_request.status != RecoveryRequest.Status.READY_FOR_EXECUTION:
        messages.error(request, "This request is not ready for execution.")
        return redirect("surveys:recovery_detail", request_id=request_id)

    try:
        # Execute recovery via model method (handles Vault integration)
        recovery_request.execute_recovery(admin=request.user, new_password=new_password)

        # Create audit entry for the superuser action
        recovery_request._create_audit_entry(
            event_type="recovery_executed_superuser",
            severity=RecoveryAuditEntry.Severity.CRITICAL,
            actor_type="superuser",
            actor_id=request.user.id,
            actor_email=request.user.email,
            details={
                "action": "execute_recovery",
                "source": "platform_recovery_console",
                "superuser_override": True,
            },
        )

        # Log superuser action
        logger.warning(
            f"SUPERUSER ACTION: {request.user.email} executed recovery for request "
            f"{recovery_request.request_code} (user: {recovery_request.user.email}, "
            f"survey: {recovery_request.survey.slug})"
        )

        # Send completion notification to the user
        try:
            from checktick_app.core.email_utils import send_recovery_completed_email

            survey_url = request.build_absolute_uri(
                reverse(
                    "surveys:dashboard", kwargs={"slug": recovery_request.survey.slug}
                )
            )
            send_recovery_completed_email(
                to_email=recovery_request.user.email,
                user_name=recovery_request.user.get_full_name()
                or recovery_request.user.username,
                request_id=recovery_request.request_code,
                survey_name=recovery_request.survey.name,
                survey_url=survey_url,
            )
        except Exception as email_err:
            logger.error(f"Failed to send recovery completion email: {email_err}")

        messages.success(
            request,
            "Recovery has been executed successfully. The user's survey data has been "
            "re-encrypted with their new password and they have been notified by email.",
        )

    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Recovery execution failed: {e}")
        messages.error(
            request,
            f"Error executing recovery: {e}. Please check Vault connectivity and try again.",
        )

    return redirect("surveys:recovery_detail", request_id=request_id)


# =============================================================================
# ADMIN RECOVERY DASHBOARD (Organization/Team Admins)
# =============================================================================


def get_admin_context(request: HttpRequest) -> dict:
    """
    Determine the admin context (org or team) from request parameters.

    Returns context dict with:
    - context_type: 'organization' or 'team'
    - organization/team: the relevant object
    - dashboard_title: appropriate title
    - tier_display/tier_badge_class: for UI display
    - can_approve_primary/secondary, can_reject: permission flags
    """
    from checktick_app.surveys.models import (
        Organization,
        OrganizationMembership,
        Team,
        TeamMembership,
    )

    org_id = request.GET.get("org")
    team_id = request.GET.get("team")

    context = {
        "context_type": None,
        "organization": None,
        "team": None,
        "dashboard_title": "Recovery Dashboard",
        "tier_display": "Admin",
        "tier_badge_class": "badge-primary",
        "can_approve_primary": False,
        "can_approve_secondary": False,
        "can_reject": False,
        "is_admin": False,
    }

    if org_id:
        try:
            org = Organization.objects.get(id=org_id)
            # Check if user is org owner or admin
            is_owner = org.owner == request.user
            is_admin = OrganizationMembership.objects.filter(
                organization=org,
                user=request.user,
                role__in=[
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.DATA_CUSTODIAN,
                ],
            ).exists()

            if is_owner or is_admin:
                context.update(
                    {
                        "context_type": "organization",
                        "organization": org,
                        "dashboard_title": f"{org.name} Recovery Dashboard",
                        "tier_display": "Organisation Admin",
                        "tier_badge_class": "badge-secondary",
                        "can_approve_primary": True,
                        "can_approve_secondary": True,
                        "can_reject": True,
                        "is_admin": True,
                    }
                )
        except Organization.DoesNotExist:
            pass

    elif team_id:
        try:
            team = Team.objects.get(id=team_id)
            # Check if user is team owner or admin
            is_owner = team.owner == request.user
            is_admin = TeamMembership.objects.filter(
                team=team,
                user=request.user,
                role=TeamMembership.Role.ADMIN,
            ).exists()

            if is_owner or is_admin:
                # Determine if this is a standalone team or org-hosted
                if team.organization:
                    tier_display = "Team Admin"
                    tier_badge_class = "badge-accent"
                else:
                    tier_display = "Team Owner"
                    tier_badge_class = "badge-primary"

                context.update(
                    {
                        "context_type": "team",
                        "team": team,
                        "dashboard_title": f"{team.name} Recovery Dashboard",
                        "tier_display": tier_display,
                        "tier_badge_class": tier_badge_class,
                        "can_approve_primary": True,
                        "can_approve_secondary": True,
                        "can_reject": True,
                        "is_admin": True,
                    }
                )
        except Team.DoesNotExist:
            pass

    return context


def get_scoped_recovery_requests(context: dict):
    """Get recovery requests scoped to the admin's org/team."""
    from checktick_app.surveys.models import RecoveryRequest

    if context["context_type"] == "organization":
        org = context["organization"]
        # Get all surveys belonging to this org
        return RecoveryRequest.objects.filter(survey__organization=org).select_related(
            "user", "survey", "primary_approver", "secondary_approver"
        )

    elif context["context_type"] == "team":
        team = context["team"]
        # Get all surveys belonging to this team
        return RecoveryRequest.objects.filter(survey__team=team).select_related(
            "user", "survey", "primary_approver", "secondary_approver"
        )

    return RecoveryRequest.objects.none()


@login_required
@ratelimit(key="user", rate="20/h", block=True)
def admin_recovery_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Recovery dashboard for organization/team admins.

    Scopes requests to the admin's org or team.
    Rate limited: 20 requests/hour.
    """
    context = get_admin_context(request)

    if not context["is_admin"]:
        messages.error(
            request, "You do not have permission to access recovery management."
        )
        return redirect("surveys:list")

    # Get scoped requests
    requests_qs = get_scoped_recovery_requests(context)

    # Calculate stats
    stats = {
        "total": requests_qs.count(),
        "pending": requests_qs.filter(
            status__in=[
                RecoveryRequest.Status.PENDING_VERIFICATION,
                RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
                RecoveryRequest.Status.AWAITING_PRIMARY,
                RecoveryRequest.Status.AWAITING_SECONDARY,
            ]
        ).count(),
        "in_delay": requests_qs.filter(
            status=RecoveryRequest.Status.IN_TIME_DELAY
        ).count(),
        "completed": requests_qs.filter(
            status=RecoveryRequest.Status.COMPLETED
        ).count(),
        "rejected": requests_qs.filter(status=RecoveryRequest.Status.REJECTED).count(),
    }

    # Apply filter
    filter_param = request.GET.get("filter", "all")
    if filter_param == "pending":
        requests_qs = requests_qs.filter(
            status__in=[
                RecoveryRequest.Status.PENDING_VERIFICATION,
                RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
                RecoveryRequest.Status.AWAITING_PRIMARY,
                RecoveryRequest.Status.AWAITING_SECONDARY,
            ]
        )
    elif filter_param == "approved":
        requests_qs = requests_qs.filter(
            status__in=[
                RecoveryRequest.Status.IN_TIME_DELAY,
                RecoveryRequest.Status.READY_FOR_EXECUTION,
            ]
        )
    elif filter_param == "completed":
        requests_qs = requests_qs.filter(status=RecoveryRequest.Status.COMPLETED)
    elif filter_param == "rejected":
        requests_qs = requests_qs.filter(
            status__in=[
                RecoveryRequest.Status.REJECTED,
                RecoveryRequest.Status.CANCELLED,
            ]
        )

    requests_qs = requests_qs.order_by("-submitted_at")

    context.update(
        {
            "requests": requests_qs,
            "stats": stats,
            "filter": filter_param,
            "user": request.user,
        }
    )

    return render(request, "surveys/admin_recovery_dashboard.html", context)


@login_required
@ratelimit(key="user", rate="20/h", block=True)
def admin_recovery_detail(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Recovery request detail view for organization/team admins.

    Rate limited: 20 requests/hour.
    """
    context = get_admin_context(request)

    if not context["is_admin"]:
        messages.error(request, "You do not have permission to view this request.")
        return redirect("surveys:list")

    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Verify the request belongs to admin's scope
    scoped_requests = get_scoped_recovery_requests(context)
    if not scoped_requests.filter(id=request_id).exists():
        messages.error(
            request, "This recovery request is not within your administrative scope."
        )
        return redirect("surveys:admin_recovery_dashboard")

    # Get verifications and audit entries
    verifications = recovery_request.identity_verifications.all()
    audit_entries = recovery_request.audit_entries.order_by("-timestamp")[:20]

    # Determine if user can take action
    can_take_action = recovery_request.status in [
        RecoveryRequest.Status.AWAITING_PRIMARY,
        RecoveryRequest.Status.AWAITING_SECONDARY,
        RecoveryRequest.Status.PENDING_VERIFICATION,
        RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
    ]

    context.update(
        {
            "request_obj": recovery_request,
            "verifications": verifications,
            "audit_entries": audit_entries,
            "can_take_action": can_take_action,
            "user": request.user,
        }
    )

    return render(request, "surveys/admin_recovery_detail.html", context)


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def admin_recovery_approve_primary(
    request: HttpRequest, request_id: str
) -> HttpResponse:
    """
    Approve a recovery request as primary approver (org/team admin).

    Rate limited: 5 approvals/hour.
    """
    context = get_admin_context(request)

    if not context["is_admin"] or not context["can_approve_primary"]:
        return HttpResponseForbidden("Permission denied")

    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Verify scope
    scoped_requests = get_scoped_recovery_requests(context)
    if not scoped_requests.filter(id=request_id).exists():
        return HttpResponseForbidden("Request not in your scope")

    # Cannot approve your own request
    if recovery_request.user == request.user:
        messages.error(request, "You cannot approve your own recovery request.")
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    if recovery_request.status != RecoveryRequest.Status.AWAITING_PRIMARY:
        messages.error(request, "This request is not awaiting primary approval.")
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    try:
        context_type = context["context_type"]
        context_name = (
            context["organization"].name
            if context_type == "organization"
            else context["team"].name
        )

        recovery_request.approve_primary(
            admin=request.user,
            reason=f"Approved via {context_type.title()} Recovery Dashboard ({context_name}) by {request.user.email}",
        )

        logger.info(
            f"ADMIN ACTION: {request.user.email} approved primary for recovery request "
            f"{recovery_request.request_code} ({context_type}: {context_name})"
        )

        messages.success(
            request,
            "Primary approval granted. Awaiting secondary approval from another administrator.",
        )
    except Exception as e:
        messages.error(request, f"Error approving request: {e}")

    # Redirect with context preserved
    redirect_url = reverse(
        "surveys:admin_recovery_detail", kwargs={"request_id": request_id}
    )
    if context["context_type"] == "organization":
        redirect_url += f"?org={context['organization'].id}"
    elif context["context_type"] == "team":
        redirect_url += f"?team={context['team'].id}"

    return redirect(redirect_url)


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def admin_recovery_approve_secondary(
    request: HttpRequest, request_id: str
) -> HttpResponse:
    """
    Approve a recovery request as secondary approver (org/team admin).

    Rate limited: 5 approvals/hour.
    """
    context = get_admin_context(request)

    if not context["is_admin"] or not context["can_approve_secondary"]:
        return HttpResponseForbidden("Permission denied")

    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Verify scope
    scoped_requests = get_scoped_recovery_requests(context)
    if not scoped_requests.filter(id=request_id).exists():
        return HttpResponseForbidden("Request not in your scope")

    # Cannot approve your own request
    if recovery_request.user == request.user:
        messages.error(request, "You cannot approve your own recovery request.")
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    # Cannot be same person as primary approver
    if recovery_request.primary_approver == request.user:
        messages.error(
            request, "Secondary approver must be different from primary approver."
        )
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    if recovery_request.status != RecoveryRequest.Status.AWAITING_SECONDARY:
        messages.error(request, "This request is not awaiting secondary approval.")
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    try:
        context_type = context["context_type"]
        context_name = (
            context["organization"].name
            if context_type == "organization"
            else context["team"].name
        )

        recovery_request.approve_secondary(
            admin=request.user,
            reason=f"Approved via {context_type.title()} Recovery Dashboard ({context_name}) by {request.user.email}",
        )

        logger.info(
            f"ADMIN ACTION: {request.user.email} approved secondary for recovery request "
            f"{recovery_request.request_code} ({context_type}: {context_name})"
        )

        messages.success(
            request,
            f"Secondary approval granted. Time delay of {recovery_request.time_delay_hours} hours has started.",
        )
    except Exception as e:
        messages.error(request, f"Error approving request: {e}")

    # Redirect with context preserved
    redirect_url = reverse(
        "surveys:admin_recovery_detail", kwargs={"request_id": request_id}
    )
    if context["context_type"] == "organization":
        redirect_url += f"?org={context['organization'].id}"
    elif context["context_type"] == "team":
        redirect_url += f"?team={context['team'].id}"

    return redirect(redirect_url)


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def admin_recovery_reject(request: HttpRequest, request_id: str) -> HttpResponse:
    """
    Reject a recovery request (org/team admin).

    Rate limited: 5 rejections/hour.
    """
    context = get_admin_context(request)

    if not context["is_admin"] or not context["can_reject"]:
        return HttpResponseForbidden("Permission denied")

    recovery_request = get_object_or_404(RecoveryRequest, id=request_id)

    # Verify scope
    scoped_requests = get_scoped_recovery_requests(context)
    if not scoped_requests.filter(id=request_id).exists():
        return HttpResponseForbidden("Request not in your scope")

    rejectable_statuses = [
        RecoveryRequest.Status.PENDING_VERIFICATION,
        RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
        RecoveryRequest.Status.AWAITING_PRIMARY,
        RecoveryRequest.Status.AWAITING_SECONDARY,
    ]

    if recovery_request.status not in rejectable_statuses:
        messages.error(request, "This request cannot be rejected in its current state.")
        return redirect("surveys:admin_recovery_detail", request_id=request_id)

    reason = request.POST.get("reason", "Rejected by administrator")

    try:
        context_type = context["context_type"]
        context_name = (
            context["organization"].name
            if context_type == "organization"
            else context["team"].name
        )

        recovery_request.reject(admin=request.user, reason=reason)

        logger.info(
            f"ADMIN ACTION: {request.user.email} rejected recovery request "
            f"{recovery_request.request_code} ({context_type}: {context_name}). Reason: {reason}"
        )

        messages.success(request, "Recovery request has been rejected.")
    except Exception as e:
        messages.error(request, f"Error rejecting request: {e}")

    # Redirect to dashboard with context
    redirect_url = reverse("surveys:admin_recovery_dashboard")
    if context["context_type"] == "organization":
        redirect_url += f"?org={context['organization'].id}"
    elif context["context_type"] == "team":
        redirect_url += f"?team={context['team'].id}"

    return redirect(redirect_url)
