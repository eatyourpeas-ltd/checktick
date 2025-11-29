"""
Tests for team-based permissions.

Tests the permission functions and decorators for team functionality.
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
import pytest

from checktick_app.surveys.decorators import (
    team_admin_required,
    team_creator_required,
    team_member_required,
)
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    Team,
    TeamMembership,
)
from checktick_app.surveys.permissions import (
    can_add_team_member,
    can_create_survey_in_team,
    can_edit_team_survey,
    can_manage_team,
    can_view_team_survey,
    get_user_team_role,
)

TEST_PASSWORD = "ComplexTestPassword123!"


@pytest.mark.django_db
class TestTeamViewPermissions:
    """Test view permissions for team surveys."""

    def test_team_owner_can_view_survey(self):
        """Team owner can view any survey in their team."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(owner, survey) is True

    def test_team_admin_can_view_survey(self):
        """Team admin can view surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(admin, survey) is True

    def test_team_creator_can_view_survey(self):
        """Team creator can view surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(creator, survey) is True

    def test_team_viewer_can_view_survey(self):
        """Team viewer can view surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=viewer, role="viewer")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(viewer, survey) is True

    def test_non_member_cannot_view_survey(self):
        """Non-team-member cannot view team survey."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(other, survey) is False

    def test_org_admin_can_view_team_survey(self):
        """Organization admin can view surveys in org's teams."""
        org_owner = User.objects.create_user(
            username="org_owner", password=TEST_PASSWORD
        )
        team_owner = User.objects.create_user(
            username="team_owner", password=TEST_PASSWORD
        )
        org_admin = User.objects.create_user(
            username="org_admin", password=TEST_PASSWORD
        )

        org = Organization.objects.create(name="Test Org", owner=org_owner)
        OrganizationMembership.objects.create(
            organization=org, user=org_admin, role="admin"
        )

        team = Team.objects.create(
            name="Test Team", owner=team_owner, organization=org, size="small"
        )
        survey = Survey.objects.create(
            name="Test Survey", owner=team_owner, team=team, slug="test-survey"
        )

        assert can_view_team_survey(org_admin, survey) is True


@pytest.mark.django_db
class TestTeamEditPermissions:
    """Test edit permissions for team surveys."""

    def test_team_owner_can_edit_survey(self):
        """Team owner can edit any survey in their team."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_edit_team_survey(owner, survey) is True

    def test_team_admin_can_edit_survey(self):
        """Team admin can edit surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_edit_team_survey(admin, survey) is True

    def test_team_creator_can_edit_survey(self):
        """Team creator can edit surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_edit_team_survey(creator, survey) is True

    def test_team_viewer_cannot_edit_survey(self):
        """Team viewer cannot edit surveys (read-only)."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=viewer, role="viewer")
        survey = Survey.objects.create(
            name="Test Survey", owner=owner, team=team, slug="test-survey"
        )

        assert can_edit_team_survey(viewer, survey) is False


@pytest.mark.django_db
class TestTeamManagementPermissions:
    """Test management permissions for teams."""

    def test_team_owner_can_manage_team(self):
        """Team owner can always manage their team."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        assert can_manage_team(owner, team) is True

    def test_team_admin_can_manage_team(self):
        """Team admin can manage the team."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")

        assert can_manage_team(admin, team) is True

    def test_team_creator_cannot_manage_team(self):
        """Team creator cannot manage team (no member management)."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        assert can_manage_team(creator, team) is False

    def test_org_admin_can_manage_team(self):
        """Organization admin can manage teams in their org."""
        org_owner = User.objects.create_user(
            username="org_owner", password=TEST_PASSWORD
        )
        team_owner = User.objects.create_user(
            username="team_owner", password=TEST_PASSWORD
        )
        org_admin = User.objects.create_user(
            username="org_admin", password=TEST_PASSWORD
        )

        org = Organization.objects.create(name="Test Org", owner=org_owner)
        OrganizationMembership.objects.create(
            organization=org, user=org_admin, role="admin"
        )

        team = Team.objects.create(
            name="Test Team", owner=team_owner, organization=org, size="small"
        )

        assert can_manage_team(org_admin, team) is True


@pytest.mark.django_db
class TestTeamMemberCapacity:
    """Test team member capacity checks."""

    def test_can_add_member_when_under_capacity(self):
        """Can add member when team is under capacity."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        # Small team: max 5 members, currently 0 memberships

        assert can_add_team_member(owner, team) is True

    def test_cannot_add_member_when_at_capacity(self):
        """Cannot add member when team is at capacity."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        # Add 5 members (small team limit)
        for i in range(5):
            user = User.objects.create_user(username=f"user{i}", password=TEST_PASSWORD)
            TeamMembership.objects.create(team=team, user=user, role="viewer")

        assert can_add_team_member(owner, team) is False

    def test_non_admin_cannot_add_member(self):
        """Non-admin cannot add members even if capacity available."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        assert can_add_team_member(creator, team) is False


@pytest.mark.django_db
class TestTeamSurveyCreation:
    """Test survey creation permissions in teams."""

    def test_team_owner_can_create_survey(self):
        """Team owner can create surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        assert can_create_survey_in_team(owner, team) is True

    def test_team_admin_can_create_survey(self):
        """Team admin can create surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")

        assert can_create_survey_in_team(admin, team) is True

    def test_team_creator_can_create_survey(self):
        """Team creator can create surveys."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        assert can_create_survey_in_team(creator, team) is True

    def test_team_viewer_cannot_create_survey(self):
        """Team viewer cannot create surveys (read-only)."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=viewer, role="viewer")

        assert can_create_survey_in_team(viewer, team) is False

    def test_cannot_create_survey_at_limit(self):
        """Cannot create survey when team is at survey limit."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        # Create 50 surveys (team limit)
        for i in range(50):
            Survey.objects.create(
                name=f"Survey {i}", owner=owner, team=team, slug=f"survey-{i}"
            )

        assert can_create_survey_in_team(owner, team) is False


@pytest.mark.django_db
class TestGetUserTeamRole:
    """Test getting user's role in a team."""

    def test_team_owner_returns_admin(self):
        """Team owner returns 'admin' role."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        assert get_user_team_role(owner, team) == "admin"

    def test_team_admin_returns_admin(self):
        """Team admin membership returns 'admin' role."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")

        assert get_user_team_role(admin, team) == "admin"

    def test_team_creator_returns_creator(self):
        """Team creator membership returns 'creator' role."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        assert get_user_team_role(creator, team) == "creator"

    def test_team_viewer_returns_viewer(self):
        """Team viewer membership returns 'viewer' role."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=viewer, role="viewer")

        assert get_user_team_role(viewer, team) == "viewer"

    def test_non_member_returns_none(self):
        """Non-member returns None."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        assert get_user_team_role(other, team) is None


@pytest.mark.django_db
class TestTeamDecorators:
    """Test team permission decorators."""

    def test_team_member_required_allows_member(self):
        """team_member_required decorator allows team member access."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        member = User.objects.create_user(username="member", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=member, role="viewer")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = member

        @team_member_required()
        def test_view(request, team_id):
            return "success"

        result = test_view(request, team_id=team.id)
        assert result == "success"

    def test_team_member_required_blocks_non_member(self):
        """team_member_required decorator blocks non-member."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = other

        @team_member_required()
        def test_view(request, team_id):
            return "success"

        with pytest.raises(PermissionDenied):
            test_view(request, team_id=team.id)

    def test_team_admin_required_allows_admin(self):
        """team_admin_required decorator allows admin access."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=admin, role="admin")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = admin

        @team_admin_required
        def test_view(request, team_id):
            return "success"

        result = test_view(request, team_id=team.id)
        assert result == "success"

    def test_team_admin_required_blocks_creator(self):
        """team_admin_required decorator blocks creator."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = creator

        @team_admin_required
        def test_view(request, team_id):
            return "success"

        with pytest.raises(PermissionDenied):
            test_view(request, team_id=team.id)

    def test_team_creator_required_allows_creator(self):
        """team_creator_required decorator allows creator access."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=creator, role="creator")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = creator

        @team_creator_required
        def test_view(request, team_id):
            return "success"

        result = test_view(request, team_id=team.id)
        assert result == "success"

    def test_team_creator_required_blocks_viewer(self):
        """team_creator_required decorator blocks viewer."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        team = Team.objects.create(name="Test Team", owner=owner, size="small")
        TeamMembership.objects.create(team=team, user=viewer, role="viewer")

        factory = RequestFactory()
        request = factory.get("/")
        request.user = viewer

        @team_creator_required
        def test_view(request, team_id):
            return "success"

        with pytest.raises(PermissionDenied):
            test_view(request, team_id=team.id)
