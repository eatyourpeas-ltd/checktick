"""
Basic tests for Team and TeamMembership models.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

from checktick_app.surveys.models import Organization, Team, TeamMembership

User = get_user_model()


@pytest.mark.django_db
class TestTeamModel:
    def test_create_standalone_team(self):
        """Test creating a standalone team (no organisation)."""
        user = User.objects.create_user(username="owner", email="owner@test.com")
        team = Team.objects.create(
            name="Standalone Team",
            owner=user,
            size=Team.Size.SMALL,
        )

        assert team.name == "Standalone Team"
        assert team.owner == user
        assert team.organization is None
        assert team.max_members == 5
        assert team.max_surveys == 50
        assert team.subscription_id == ""

    def test_create_org_hosted_team(self):
        """Test creating a team within an organisation."""
        owner = User.objects.create_user(username="org_owner", email="org@test.com")
        org = Organization.objects.create(name="Test Org", owner=owner)

        team = Team.objects.create(
            name="Org Team",
            owner=owner,
            organization=org,
            size=Team.Size.MEDIUM,
        )

        assert team.organization == org
        assert team.max_members == 10

    def test_team_size_limits(self):
        """Test max_members property for different sizes."""
        user = User.objects.create_user(username="user", email="user@test.com")

        small = Team.objects.create(name="Small", owner=user, size=Team.Size.SMALL)
        assert small.max_members == 5

        medium = Team.objects.create(name="Medium", owner=user, size=Team.Size.MEDIUM)
        assert medium.max_members == 10

        large = Team.objects.create(name="Large", owner=user, size=Team.Size.LARGE)
        assert large.max_members == 20

        custom = Team.objects.create(
            name="Custom",
            owner=user,
            size=Team.Size.CUSTOM,
            custom_max_members=50,
        )
        assert custom.max_members == 50

    def test_can_add_members(self):
        """Test team capacity checking."""
        owner = User.objects.create_user(username="owner", email="owner@test.com")
        team = Team.objects.create(
            name="Small Team",
            owner=owner,
            size=Team.Size.SMALL,  # 5 members max
        )

        # Initially empty
        assert team.can_add_members() is True
        assert team.current_member_count() == 0

        # Add 5 members
        for i in range(5):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@test.com",
            )
            TeamMembership.objects.create(team=team, user=user, role="viewer")

        # At capacity
        assert team.current_member_count() == 5
        assert team.can_add_members() is False


@pytest.mark.django_db
class TestTeamMembership:
    def test_create_team_membership(self):
        """Test creating a team membership."""
        owner = User.objects.create_user(username="owner", email="owner@test.com")
        member = User.objects.create_user(username="member", email="member@test.com")

        team = Team.objects.create(name="Test Team", owner=owner)
        membership = TeamMembership.objects.create(
            team=team,
            user=member,
            role=TeamMembership.Role.CREATOR,
        )

        assert membership.team == team
        assert membership.user == member
        assert membership.role == TeamMembership.Role.CREATOR

    def test_team_user_unique_constraint(self):
        """Test that (team, user) is unique."""
        owner = User.objects.create_user(username="owner", email="owner@test.com")
        member = User.objects.create_user(username="member", email="member@test.com")

        team = Team.objects.create(name="Test Team", owner=owner)

        # First membership OK
        TeamMembership.objects.create(team=team, user=member, role="viewer")

        # Duplicate should fail
        with pytest.raises(IntegrityError):
            TeamMembership.objects.create(team=team, user=member, role="admin")

    def test_team_membership_roles(self):
        """Test all team membership roles."""
        owner = User.objects.create_user(username="owner", email="owner@test.com")
        team = Team.objects.create(name="Test Team", owner=owner)

        admin = User.objects.create_user(username="admin", email="admin@test.com")
        creator = User.objects.create_user(username="creator", email="creator@test.com")
        viewer = User.objects.create_user(username="viewer", email="viewer@test.com")

        admin_mem = TeamMembership.objects.create(
            team=team, user=admin, role=TeamMembership.Role.ADMIN
        )
        creator_mem = TeamMembership.objects.create(
            team=team, user=creator, role=TeamMembership.Role.CREATOR
        )
        viewer_mem = TeamMembership.objects.create(
            team=team, user=viewer, role=TeamMembership.Role.VIEWER
        )

        assert admin_mem.role == "admin"
        assert creator_mem.role == "creator"
        assert viewer_mem.role == "viewer"

    def test_multiple_teams_per_user(self):
        """Test that a user can belong to multiple teams."""
        owner = User.objects.create_user(username="owner", email="owner@test.com")
        member = User.objects.create_user(username="member", email="member@test.com")

        team1 = Team.objects.create(name="Team 1", owner=owner)
        team2 = Team.objects.create(name="Team 2", owner=owner)

        TeamMembership.objects.create(team=team1, user=member, role="creator")
        TeamMembership.objects.create(team=team2, user=member, role="admin")

        assert member.team_memberships.count() == 2
        assert team1.memberships.count() == 1
        assert team2.memberships.count() == 1
