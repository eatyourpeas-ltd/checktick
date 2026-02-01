"""
Data Governance Views

Handles data governance operations that extend existing survey functionality:
- Data exports with secure download tokens
- Retention period extensions
- Legal holds
- Data custodian management

Note: Survey closure and deletion are handled by existing views in views.py
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AuditLog, DataCustodian, DataExport, LegalHold, Survey
from .permissions import (
    require_can_export_survey_data,
    require_can_extend_retention,
    require_can_manage_data_custodians,
    require_can_manage_legal_hold,
)
from .services import ExportService, RetentionService
from .views import get_survey_key_from_session

# ============================================================================
# Data Export
# ============================================================================


@login_required
@transaction.atomic
def survey_export_create(request: HttpRequest, slug: str) -> HttpResponse:
    """Create a new data export with secure download link."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_export_survey_data(request.user, survey)

    if request.method == "POST":
        password = request.POST.get("password", "").strip() or None
        attestation_accepted = request.POST.get("attestation_accepted") in [
            "true",
            "True",
            True,
            "1",
            1,
        ]

        # Validate attestation
        if not attestation_accepted:
            messages.error(
                request, "You must confirm that you are authorized to export this data."
            )
            # Return to form with error
            response_count = survey.responses.count()
            context = {
                "survey": survey,
                "response_count": response_count,
            }
            return render(
                request, "surveys/data_governance/export_create.html", context
            )

        # Get survey key from session if survey is encrypted
        survey_key = None
        if survey.requires_whole_response_encryption():
            survey_key = get_survey_key_from_session(request, slug)
            if not survey_key:
                messages.error(
                    request,
                    "Please unlock the survey before exporting encrypted data.",
                )
                return redirect("survey_unlock", slug=slug)

        try:
            export = ExportService.create_export(
                survey, request.user, password, survey_key=survey_key
            )

            # Log export creation in audit log
            AuditLog.log_data_governance(
                actor=request.user,
                action=AuditLog.Action.DATA_EXPORTED,
                survey=survey,
                message=f"Survey data export created: {export.response_count} responses, "
                f"encrypted={'Yes' if export.is_encrypted else 'No'}",
                request=request,
                metadata={
                    "export_id": str(export.id),
                    "response_count": export.response_count,
                    "is_encrypted": export.is_encrypted,
                    "survey_encrypted": survey.requires_whole_response_encryption(),
                },
            )

            # Send email notifications to survey owner and org owner
            _send_export_creation_notifications(survey, request.user, export)

            messages.success(
                request,
                f"Export created successfully. {export.response_count} responses exported.",
            )

            return redirect(
                "surveys:survey_export_download", slug=slug, export_id=export.id
            )

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("surveys:dashboard", slug=slug)

    # GET request - show export form
    response_count = survey.responses.count()

    context = {
        "survey": survey,
        "response_count": response_count,
    }

    return render(request, "surveys/data_governance/export_create.html", context)


@login_required
def survey_export_download(
    request: HttpRequest, slug: str, export_id: str
) -> HttpResponse:
    """Display download link for an export."""
    survey = get_object_or_404(Survey, slug=slug)
    export = get_object_or_404(DataExport, id=export_id, survey=survey)

    require_can_export_survey_data(request.user, survey)

    # Generate download URL
    download_url = ExportService.get_download_url(export)

    context = {
        "survey": survey,
        "export": export,
        "download_url": download_url,
        "expires_at": export.download_url_expires_at,
    }

    return render(request, "surveys/data_governance/export_download.html", context)


@login_required
def survey_export_file(
    request: HttpRequest, slug: str, export_id: str, token: str
) -> HttpResponse:
    """Download the actual export file (validates token)."""
    survey = get_object_or_404(Survey, slug=slug)
    export = get_object_or_404(DataExport, id=export_id, survey=survey)

    # Validate download token
    if not ExportService.validate_download_token(export, token):
        messages.error(request, "Invalid or expired download link.")
        return redirect("surveys:dashboard", slug=slug)

    # Get survey key from session if survey is encrypted
    survey_key = None
    if survey.requires_whole_response_encryption():
        survey_key = get_survey_key_from_session(request, slug)
        if not survey_key:
            messages.error(
                request,
                "Please unlock the survey before downloading encrypted data.",
            )
            return redirect("survey_unlock", slug=slug)

    # Generate CSV on-the-fly (more secure than object storage)
    csv_data = ExportService._generate_csv(survey, survey_key=survey_key)

    # Record download
    ExportService.record_download(export)

    # Log download in audit log
    AuditLog.log_data_governance(
        actor=request.user,
        action=AuditLog.Action.DATA_EXPORTED,
        survey=survey,
        message=f"Survey data export downloaded: {export.response_count} responses, "
        f"download #{export.download_count}",
        request=request,
        metadata={
            "export_id": str(export.id),
            "response_count": export.response_count,
            "download_count": export.download_count,
            "is_encrypted": export.is_encrypted,
        },
    )

    # Send email notification about download
    _send_export_download_notifications(survey, request.user, export)

    # Return CSV file
    response = HttpResponse(csv_data, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="survey_{slug}_export.csv"'

    return response


def _send_export_creation_notifications(
    survey: Survey, exporter: "User", export: DataExport
) -> None:
    """Send email notifications when export is created."""
    from django.conf import settings

    subject = f"[CheckTick] Data export created: {survey.name}"
    message = f"""
A data export has been created for survey: {survey.name}

Export Details:
- Created by: {exporter.get_full_name() or exporter.username} ({exporter.email})
- Response count: {export.response_count}
- Encrypted: {'Yes' if export.is_encrypted else 'No'}
- Created at: {export.created_at.strftime('%Y-%m-%d %H:%M UTC')}
- Export ID: {export.id}

This is an automated notification for audit purposes.
"""

    # Email survey owner
    if survey.owner and survey.owner.email:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[survey.owner.email],
                fail_silently=False,
            )
        except Exception as e:
            # Log but don't fail the request
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send export notification to survey owner: {e}")

    # Email org owner if survey belongs to an organization
    if (
        survey.organization
        and survey.organization.owner
        and survey.organization.owner.email
    ):
        if survey.organization.owner.email != survey.owner.email:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[survey.organization.owner.email],
                    fail_silently=False,
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send export notification to org owner: {e}")


def _send_export_download_notifications(
    survey: Survey, downloader: "User", export: DataExport
) -> None:
    """Send email notifications when export is downloaded."""
    from django.conf import settings

    subject = f"[CheckTick] Data export downloaded: {survey.name}"
    message = f"""
A data export has been downloaded for survey: {survey.name}

Download Details:
- Downloaded by: {downloader.get_full_name() or downloader.username} ({downloader.email})
- Response count: {export.response_count}
- Download count: {export.download_count}
- Export created: {export.created_at.strftime('%Y-%m-%d %H:%M UTC')}
- Downloaded at: {export.downloaded_at.strftime('%Y-%m-%d %H:%M UTC') if export.downloaded_at else 'N/A'}
- Export ID: {export.id}

This is an automated notification for audit purposes.
"""

    # Email survey owner
    if survey.owner and survey.owner.email:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[survey.owner.email],
                fail_silently=False,
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send download notification to survey owner: {e}")

    # Email org owner if different from survey owner
    if (
        survey.organization
        and survey.organization.owner
        and survey.organization.owner.email
    ):
        if survey.organization.owner.email != survey.owner.email:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[survey.organization.owner.email],
                    fail_silently=False,
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send download notification to org owner: {e}")


# ============================================================================
# Retention Management
# ============================================================================


@login_required
@transaction.atomic
def survey_extend_retention(request: HttpRequest, slug: str) -> HttpResponse:
    """Extend retention period for a survey."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_extend_retention(request.user, survey)

    if request.method == "POST":
        months = int(request.POST.get("months", 0))
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(request, "Please provide a reason for extending retention.")
            return redirect("survey_extend_retention", slug=slug)

        if months < 1:
            messages.error(request, "Please specify a valid number of months.")
            return redirect("survey_extend_retention", slug=slug)

        try:
            RetentionService.extend_retention(survey, months, request.user, reason)

            messages.success(
                request,
                f"Retention extended by {months} months. "
                f"New deletion date: {survey.deletion_date.strftime('%Y-%m-%d')}",
            )

            return redirect("surveys:dashboard", slug=slug)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("survey_extend_retention", slug=slug)

    # GET request - show extension form
    context = {
        "survey": survey,
        "current_retention": survey.retention_months,
        "max_extension": 24 - survey.retention_months,
        "deletion_date": survey.deletion_date,
    }

    return render(request, "surveys/data_governance/extend_retention.html", context)


# ============================================================================
# Legal Holds
# ============================================================================


@login_required
@transaction.atomic
def survey_legal_hold_place(request: HttpRequest, slug: str) -> HttpResponse:
    """Place a legal hold on a survey."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_manage_legal_hold(request.user, survey)

    # Check if already has active legal hold
    if hasattr(survey, "legal_hold") and survey.legal_hold.is_active:
        messages.warning(request, "This survey already has an active legal hold.")
        return redirect("surveys:dashboard", slug=slug)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        authority = request.POST.get("authority", "").strip()

        if not reason or not authority:
            messages.error(request, "Please provide both reason and authority.")
            return redirect("survey_legal_hold_place", slug=slug)

        hold = LegalHold.objects.create(
            survey=survey,
            placed_by=request.user,
            reason=reason,
            authority=authority,
        )

        # Send email notification
        _send_legal_hold_placed_notification(
            hold, survey, request.user, reason, authority
        )

        messages.success(
            request, "Legal hold placed successfully. Survey cannot be deleted."
        )
        return redirect("surveys:dashboard", slug=slug)

    # GET request - show form
    context = {
        "survey": survey,
    }

    return render(request, "surveys/data_governance/legal_hold_place.html", context)


@login_required
@transaction.atomic
def survey_legal_hold_remove(request: HttpRequest, slug: str) -> HttpResponse:
    """Remove a legal hold from a survey."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_manage_legal_hold(request.user, survey)

    if not hasattr(survey, "legal_hold") or not survey.legal_hold.is_active:
        messages.warning(request, "This survey does not have an active legal hold.")
        return redirect("surveys:dashboard", slug=slug)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(
                request, "Please provide a reason for removing the legal hold."
            )
            return redirect("survey_legal_hold_remove", slug=slug)

        survey.legal_hold.remove(request.user, reason)

        messages.success(request, "Legal hold removed.")
        return redirect("surveys:dashboard", slug=slug)

    # GET request - show confirmation
    context = {
        "survey": survey,
        "legal_hold": survey.legal_hold,
    }

    return render(request, "surveys/data_governance/legal_hold_remove.html", context)


# ============================================================================
# Data Custodians
# ============================================================================


@login_required
@transaction.atomic
def survey_custodian_grant(request: HttpRequest, slug: str) -> HttpResponse:
    """Grant data custodian access to a user."""
    survey = get_object_or_404(Survey, slug=slug)
    require_can_manage_data_custodians(request.user, survey)

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        reason = request.POST.get("reason", "").strip()
        duration_days = request.POST.get("duration_days", "").strip()

        if not user_id or not reason:
            messages.error(request, "Please provide both user and reason.")
            return redirect("survey_custodian_grant", slug=slug)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("survey_custodian_grant", slug=slug)

        # Check if user already has active custodian access
        existing = DataCustodian.objects.filter(
            survey=survey,
            user=user,
            revoked_at__isnull=True,
        ).first()

        if existing:
            messages.warning(
                request, f"{user.username} already has active custodian access."
            )
            return redirect("surveys:dashboard", slug=slug)

        # Create custodian grant
        expires_at = None
        if duration_days:
            try:
                days = int(duration_days)
                expires_at = timezone.now() + timedelta(days=days)
            except ValueError:
                messages.error(request, "Invalid duration.")
                return redirect("survey_custodian_grant", slug=slug)

        DataCustodian.objects.create(
            survey=survey,
            user=user,
            granted_by=request.user,
            reason=reason,
            expires_at=expires_at,
        )

        # Send email notification to the custodian
        _send_custodian_assignment_notification(
            survey, user, request.user, reason, expires_at
        )

        messages.success(request, f"Data custodian access granted to {user.username}.")

        return redirect("surveys:dashboard", slug=slug)

    # GET request - show form
    # Get organization members as potential custodians
    potential_custodians = User.objects.none()
    if survey.organization:
        potential_custodians = (
            User.objects.filter(
                organization_memberships__organization=survey.organization
            )
            .exclude(id=request.user.id)
            .distinct()
        )

    context = {
        "survey": survey,
        "potential_custodians": potential_custodians,
    }

    return render(request, "surveys/data_governance/custodian_grant.html", context)


@login_required
@transaction.atomic
def survey_custodian_revoke(
    request: HttpRequest, slug: str, custodian_id: int
) -> HttpResponse:
    """Revoke data custodian access."""
    survey = get_object_or_404(Survey, slug=slug)
    custodian = get_object_or_404(
        DataCustodian, id=custodian_id, survey=survey, revoked_at__isnull=True
    )

    require_can_manage_data_custodians(request.user, survey)

    if request.method == "POST":
        custodian.revoke(request.user)

        messages.success(
            request, f"Data custodian access revoked for {custodian.user.username}."
        )

        return redirect("surveys:dashboard", slug=slug)

    # GET request - show confirmation
    context = {
        "survey": survey,
        "custodian": custodian,
    }

    return render(request, "surveys/data_governance/custodian_revoke.html", context)


# ============================================================================
# Email Notification Helpers
# ============================================================================
# Helper Functions
# ============================================================================


def _send_custodian_assignment_notification(
    survey: Survey, custodian_user: User, granted_by: User, reason: str, expires_at
) -> None:
    """
    Send email notification to user when they are assigned as data custodian.
    """
    from django.template.loader import render_to_string

    from checktick_app.core.email_utils import get_platform_branding, send_branded_email

    subject = f"Data Custodian Role Assigned: {survey.name}"

    expiry_date = None
    if expires_at:
        expiry_date = expires_at.strftime("%B %d, %Y at %I:%M %p")

    branding = get_platform_branding()

    markdown_content = render_to_string(
        "emails/data_governance/custodian_assigned.md",
        {
            "custodian_user": custodian_user,
            "survey": survey,
            "granted_by": granted_by,
            "reason": reason,
            "expires_at": expires_at,
            "expiry_date": expiry_date,
            "brand_title": branding["title"],
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        },
    )

    send_branded_email(
        to_email=custodian_user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
    )


def _send_legal_hold_placed_notification(
    hold, survey: Survey, user: User, reason: str, authority: str
) -> None:
    """
    Send email notification when legal hold is placed on a survey.
    """
    from django.template.loader import render_to_string

    from checktick_app.core.email_utils import get_platform_branding, send_branded_email

    subject = f"⚠️ LEGAL HOLD PLACED: {survey.name}"

    placed_date = hold.placed_at.strftime("%B %d, %Y at %I:%M %p")

    branding = get_platform_branding()

    markdown_content = render_to_string(
        "emails/data_governance/legal_hold_placed.md",
        {
            "survey": survey,
            "placed_by": user,
            "placed_date": placed_date,
            "reference_number": authority,
            "case_description": authority,
            "reason": reason,
            "brand_title": branding["title"],
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        },
    )

    # Send to survey owner
    send_branded_email(
        to_email=survey.owner.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
    )

    # Send to organization owner if exists
    if survey.organization:
        if survey.organization.owner.email != survey.owner.email:
            send_branded_email(
                to_email=survey.organization.owner.email,
                subject=subject,
                markdown_content=markdown_content,
                branding=branding,
            )
