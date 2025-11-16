from __future__ import annotations

from django.core.exceptions import PermissionDenied

from .models import Organization, OrganizationMembership, Survey, SurveyMembership


def is_org_admin(user, org: Organization | None) -> bool:
    if not user.is_authenticated or org is None:
        return False
    return OrganizationMembership.objects.filter(
        user=user, organization=org, role=OrganizationMembership.Role.ADMIN
    ).exists()


def can_view_survey(user, survey: Survey) -> bool:
    if not user.is_authenticated:
        return False
    if survey.owner_id == getattr(user, "id", None):
        return True
    # Organization owner can view all surveys in their organization
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True
    if survey.organization_id and is_org_admin(user, survey.organization):
        return True
    # creators and viewers of the specific survey can view it
    if SurveyMembership.objects.filter(user=user, survey=survey).exists():
        return True
    return False


def can_edit_survey(user, survey: Survey) -> bool:
    # Edit requires: owner, org owner, org admin, or survey-level creator/editor
    if not user.is_authenticated:
        return False
    if survey.owner_id == getattr(user, "id", None):
        return True
    # Organization owner can edit all surveys in their organization
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True
    if survey.organization_id and is_org_admin(user, survey.organization):
        return True
    return SurveyMembership.objects.filter(
        user=user,
        survey=survey,
        role__in=[SurveyMembership.Role.CREATOR, SurveyMembership.Role.EDITOR],
    ).exists()


def can_manage_org_users(user, org: Organization) -> bool:
    return is_org_admin(user, org)


def can_manage_survey_users(user, survey: Survey) -> bool:
    # Individual users (surveys without organization) cannot share surveys
    if not survey.organization_id:
        return False
    # Only survey creators (not editors), org admins, or owner can manage users on a survey
    if survey.organization_id and is_org_admin(user, survey.organization):
        return True
    if survey.owner_id == getattr(user, "id", None):
        return True
    # Only CREATOR role can manage users, EDITOR cannot
    return SurveyMembership.objects.filter(
        user=user, survey=survey, role=SurveyMembership.Role.CREATOR
    ).exists()


def require_can_view(user, survey: Survey) -> None:
    if not can_view_survey(user, survey):
        raise PermissionDenied("You do not have permission to view this survey.")


def require_can_edit(user, survey: Survey) -> None:
    if not can_edit_survey(user, survey):
        raise PermissionDenied("You do not have permission to edit this survey.")


def user_has_org_membership(user) -> bool:
    if not user.is_authenticated:
        return False
    return OrganizationMembership.objects.filter(user=user).exists()


def can_create_datasets(user) -> bool:
    """Check if user can create datasets.

    Allowed:
    - Individual users (not part of any organization)
    - Organization members with ADMIN or CREATOR roles

    Not allowed:
    - VIEWER role members (read-only, cannot create anything)
    - Unauthenticated users

    Future: Will restrict individual users to pro accounts only.
    """
    if not user.is_authenticated:
        return False

    from .models import OrganizationMembership

    # Check user's organization memberships
    memberships = OrganizationMembership.objects.filter(user=user)

    # If user has no org memberships, they're an individual user - allow
    if not memberships.exists():
        return True

    # If user has ADMIN or CREATOR role in any org, allow
    if memberships.filter(
        role__in=[
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.CREATOR,
        ]
    ).exists():
        return True

    # User only has VIEWER or EDITOR roles - deny
    return False


def can_edit_dataset(user, dataset) -> bool:
    """Check if user can edit a specific dataset."""
    if not user.is_authenticated:
        return False

    # NHS DD datasets are read-only
    if dataset.category == "nhs_dd" and not dataset.is_custom:
        return False

    # Global datasets can only be edited by superusers
    if dataset.is_global and not user.is_superuser:
        return False

    # Individual user datasets - check if user is the creator
    if dataset.organization is None:
        return dataset.created_by == user

    # Organization datasets - user must be ADMIN or CREATOR in the dataset's organization
    return OrganizationMembership.objects.filter(
        user=user,
        organization=dataset.organization,
        role__in=[
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.CREATOR,
        ],
    ).exists()


def require_can_create_datasets(user) -> None:
    if not can_create_datasets(user):
        # TODO: Update message when pro accounts are implemented
        raise PermissionDenied("You must be authenticated to create datasets.")


def require_can_edit_dataset(user, dataset) -> None:
    if not can_edit_dataset(user, dataset):
        raise PermissionDenied("You do not have permission to edit this dataset.")


# ============================================================================
# Data Governance Permissions
# ============================================================================


def can_close_survey(user, survey: Survey) -> bool:
    """
    Only survey owner or organization owner can close a survey.
    Closing starts the retention period countdown.
    """
    if not user.is_authenticated:
        return False
    if survey.owner_id == getattr(user, "id", None):
        return True
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True
    return False


def can_export_survey_data(user, survey: Survey) -> bool:
    """
    Survey owner, organization owner, org admins, and data custodians can export.
    Viewers and editors cannot export (view/edit only).
    """
    if not user.is_authenticated:
        return False

    # Survey owner can always export
    if survey.owner_id == getattr(user, "id", None):
        return True

    # Organization owner can export all surveys in their org
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True

    # Organization admins can export
    if survey.organization_id and is_org_admin(user, survey.organization):
        return True

    # Check if user is an active data custodian for this survey
    from .models import DataCustodian

    if DataCustodian.objects.filter(
        user=user, survey=survey, revoked_at__isnull=True
    ).exists():
        # Verify custodianship is still active (not expired)
        custodian = DataCustodian.objects.filter(
            user=user, survey=survey, revoked_at__isnull=True
        ).first()
        if custodian and custodian.is_active:
            return True

    return False


def can_extend_retention(user, survey: Survey) -> bool:
    """
    Only organization owner can extend retention beyond the default period.
    This is a privileged operation requiring business justification.
    """
    if not user.is_authenticated:
        return False

    # Organization owner only (not even survey owner)
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True

    # If no organization, survey owner can extend
    if not survey.organization_id and survey.owner_id == getattr(user, "id", None):
        return True

    return False


def can_manage_legal_hold(user, survey: Survey) -> bool:
    """
    Only organization owner can place or remove legal holds.
    This is a critical compliance operation.
    """
    if not user.is_authenticated:
        return False

    # Organization owner only
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True

    # If no organization, survey owner can manage holds
    if not survey.organization_id and survey.owner_id == getattr(user, "id", None):
        return True

    return False


def can_manage_data_custodians(user, survey: Survey) -> bool:
    """
    Only organization owner can grant/revoke data custodian access.
    Survey owners cannot delegate custodian access for security.
    """
    if not user.is_authenticated:
        return False

    # Organization owner only (not survey owner for security)
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True

    # If no organization, survey owner can manage custodians
    if not survey.organization_id and survey.owner_id == getattr(user, "id", None):
        return True

    return False


def can_soft_delete_survey(user, survey: Survey) -> bool:
    """
    Survey owner or organization owner can soft delete.
    Soft deletion has a 30-day grace period before hard deletion.
    """
    if not user.is_authenticated:
        return False
    if survey.owner_id == getattr(user, "id", None):
        return True
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True
    return False


def can_hard_delete_survey(user, survey: Survey) -> bool:
    """
    Only organization owner can hard delete (permanent, irreversible).
    Survey owner cannot hard delete for safety - requires org-level approval.
    """
    if not user.is_authenticated:
        return False

    # Organization owner only
    if survey.organization_id and survey.organization.owner_id == getattr(
        user, "id", None
    ):
        return True

    # If no organization, survey owner can hard delete (with caution)
    if not survey.organization_id and survey.owner_id == getattr(user, "id", None):
        return True

    return False


# Require functions for data governance (raise PermissionDenied)


def require_can_close_survey(user, survey: Survey) -> None:
    if not can_close_survey(user, survey):
        raise PermissionDenied("You do not have permission to close this survey.")


def require_can_export_survey_data(user, survey: Survey) -> None:
    if not can_export_survey_data(user, survey):
        raise PermissionDenied("You do not have permission to export survey data.")


def require_can_extend_retention(user, survey: Survey) -> None:
    if not can_extend_retention(user, survey):
        raise PermissionDenied(
            "You do not have permission to extend retention for this survey."
        )


def require_can_manage_legal_hold(user, survey: Survey) -> None:
    if not can_manage_legal_hold(user, survey):
        raise PermissionDenied(
            "You do not have permission to manage legal holds for this survey."
        )


def require_can_manage_data_custodians(user, survey: Survey) -> None:
    if not can_manage_data_custodians(user, survey):
        raise PermissionDenied(
            "You do not have permission to manage data custodians for this survey."
        )


def require_can_soft_delete_survey(user, survey: Survey) -> None:
    if not can_soft_delete_survey(user, survey):
        raise PermissionDenied("You do not have permission to delete this survey.")


def require_can_hard_delete_survey(user, survey: Survey) -> None:
    if not can_hard_delete_survey(user, survey):
        raise PermissionDenied(
            "You do not have permission to permanently delete this survey."
        )
