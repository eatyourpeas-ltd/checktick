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


# Published Question Group Permissions


def can_publish_question_group(user, group, level: str, survey=None) -> bool:
    """Check if user can publish a question group at given level."""
    from .models import OrganizationMembership

    if not user.is_authenticated:
        return False

    # Must be owner of the group
    if group.owner_id != user.id:
        return False

    if level == "global":
        # Anyone (except org VIEWERs) can publish globally
        # Check if user is an org VIEWER
        if OrganizationMembership.objects.filter(
            user=user, role=OrganizationMembership.Role.VIEWER
        ).exists():
            # If they're a VIEWER in any org, they can't publish
            return False
        return True

    if level == "organization":
        # Must have an organization associated with the survey
        if not survey or not survey.organization:
            return False
        # Must be CREATOR or ADMIN in that organization
        membership = OrganizationMembership.objects.filter(
            user=user,
            organization=survey.organization,
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.CREATOR,
            ],
        ).exists()
        return membership

    return False


def can_import_published_template(user, template) -> bool:
    """Check if user can import a published template."""
    from .models import OrganizationMembership, PublishedQuestionGroup

    if not user.is_authenticated:
        return False

    # Must be active
    if template.status != PublishedQuestionGroup.Status.ACTIVE:
        return False

    # Global templates available to all authenticated users
    if template.publication_level == PublishedQuestionGroup.PublicationLevel.GLOBAL:
        return True

    # Organization templates only for org members
    if (
        template.publication_level
        == PublishedQuestionGroup.PublicationLevel.ORGANIZATION
    ):
        if template.organization:
            return OrganizationMembership.objects.filter(
                user=user, organization=template.organization
            ).exists()

    return False


def can_delete_published_template(user, template) -> bool:
    """Check if user can delete a published template."""
    if not user.is_authenticated:
        return False

    # Superusers can delete any template
    if user.is_superuser:
        return True

    # Publishers can delete their own templates
    return template.publisher_id == user.id


def require_can_publish_question_group(user, group, level: str) -> None:
    if not can_publish_question_group(user, group, level):
        raise PermissionDenied(
            "You do not have permission to publish this question group."
        )


def require_can_import_published_template(user, template) -> None:
    if not can_import_published_template(user, template):
        raise PermissionDenied("You do not have permission to import this template.")


def require_can_delete_published_template(user, template) -> None:
    if not can_delete_published_template(user, template):
        raise PermissionDenied("You do not have permission to delete this template.")


# ============================================================================
# Team Permissions
# ============================================================================


def can_view_team_survey(user, survey: Survey) -> bool:
    """
    Check if a user can view a team survey.

    Access hierarchy:
    1. Survey owner (always has access)
    2. Organisation admin (if team belongs to org)
    3. Team admin
    4. Team creator/viewer (can view surveys)
    5. Survey membership (CREATOR, EDITOR, VIEWER)

    Args:
        user: The user to check permissions for
        survey: The survey to check access to

    Returns:
        bool: True if user can view the survey, False otherwise
    """
    from .models import TeamMembership

    if not user.is_authenticated:
        return False

    if not survey.team:
        # Not a team survey, use existing can_view_survey logic
        return can_view_survey(user, survey)

    # Survey owner always has access
    if survey.owner_id == getattr(user, "id", None):
        return True

    # Check if user is organization admin (if team is hosted by org)
    if survey.team.organization:
        if is_org_admin(user, survey.team.organization):
            return True

    # Check team membership - all team members can view surveys
    if TeamMembership.objects.filter(team=survey.team, user=user).exists():
        return True

    # Check survey membership (explicit share)
    if SurveyMembership.objects.filter(user=user, survey=survey).exists():
        return True

    return False


def can_edit_team_survey(user, survey: Survey) -> bool:
    """
    Check if a user can edit a team survey.

    Access hierarchy:
    1. Survey owner (always has edit access)
    2. Organisation admin (if team belongs to org)
    3. Team admin
    4. Team creator (can edit surveys)
    5. Survey membership with CREATOR or EDITOR role

    Args:
        user: The user to check permissions for
        survey: The survey to check edit access to

    Returns:
        bool: True if user can edit the survey, False otherwise
    """
    from .models import TeamMembership

    if not user.is_authenticated:
        return False

    if not survey.team:
        # Not a team survey, use existing can_edit_survey logic
        return can_edit_survey(user, survey)

    # Survey owner always has edit access
    if survey.owner_id == getattr(user, "id", None):
        return True

    # Check if user is organization admin (if team is hosted by org)
    if survey.team.organization:
        if is_org_admin(user, survey.team.organization):
            return True

    # Check team membership - admin and creator can edit
    if TeamMembership.objects.filter(
        team=survey.team, user=user, role__in=["admin", "creator"]
    ).exists():
        return True

    # Check survey membership for explicit edit permissions
    if SurveyMembership.objects.filter(
        user=user,
        survey=survey,
        role__in=[SurveyMembership.Role.CREATOR, SurveyMembership.Role.EDITOR],
    ).exists():
        return True

    return False


def can_manage_team(user, team) -> bool:
    """
    Check if a user can manage a team (add/remove members, change settings).

    Access hierarchy:
    1. Team owner (always has access)
    2. Organisation admin (if team belongs to org)
    3. Team admin

    Args:
        user: The user to check permissions for
        team: The team to check management permissions for

    Returns:
        bool: True if user can manage the team, False otherwise
    """
    from .models import TeamMembership

    if not user.is_authenticated:
        return False

    # Team owner always has access
    if team.owner_id == getattr(user, "id", None):
        return True

    # Check if user is organization admin (if team is hosted by org)
    if team.organization:
        if is_org_admin(user, team.organization):
            return True

    # Check if user is team admin
    return TeamMembership.objects.filter(team=team, user=user, role="admin").exists()


def can_add_team_member(user, team) -> bool:
    """
    Check if a user can add new members to a team.

    Requirements:
    1. User must have management permissions (owner, org admin, or team admin)
    2. Team must have capacity for new members

    Args:
        user: The user attempting to add members
        team: The team to add members to

    Returns:
        bool: True if user can add members, False otherwise
    """
    if not can_manage_team(user, team):
        return False

    return team.can_add_members()


def can_create_survey_in_team(user, team) -> bool:
    """
    Check if a user can create a new survey in a team.

    Requirements:
    1. User must be team member with creator or admin role
    2. Team must not have reached survey limit
    3. If team is in organization, check org permissions as well

    Args:
        user: The user attempting to create a survey
        team: The team to create survey in

    Returns:
        bool: True if user can create surveys, False otherwise
    """
    from .models import TeamMembership

    if not user.is_authenticated:
        return False

    # Check if team has capacity for more surveys
    if not team.can_create_surveys():
        return False

    # Team owner can always create surveys
    if team.owner_id == getattr(user, "id", None):
        return True

    # Organization admins can create surveys in their org's teams
    if team.organization:
        if is_org_admin(user, team.organization):
            return True

    # Team members with creator or admin role can create surveys
    return TeamMembership.objects.filter(
        team=team, user=user, role__in=["admin", "creator"]
    ).exists()


def get_user_team_role(user, team):
    """
    Get the user's role in a team.

    Args:
        user: The user to check
        team: The team to check membership in

    Returns:
        str: The role ('admin', 'creator', 'viewer') or None if not a member
    """
    from .models import TeamMembership

    if not user.is_authenticated:
        return None

    if team.owner_id == getattr(user, "id", None):
        return "admin"

    membership = TeamMembership.objects.filter(team=team, user=user).first()

    return membership.role if membership else None


# Require functions for teams (raise PermissionDenied)


def require_can_manage_team(user, team) -> None:
    if not can_manage_team(user, team):
        raise PermissionDenied("You do not have permission to manage this team.")


def require_can_add_team_member(user, team) -> None:
    if not can_add_team_member(user, team):
        if not can_manage_team(user, team):
            raise PermissionDenied("You do not have permission to manage this team.")
        raise PermissionDenied("This team has reached its member capacity.")


def require_can_create_survey_in_team(user, team) -> None:
    if not can_create_survey_in_team(user, team):
        if not team.can_create_surveys():
            raise PermissionDenied("This team has reached its survey limit.")
        raise PermissionDenied(
            "You do not have permission to create surveys in this team."
        )
