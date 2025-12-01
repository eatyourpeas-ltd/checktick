"""
Tests for FREE tier patient data restrictions.

These tests verify that FREE tier users cannot:
1. Create surveys with patient data templates
2. Publish surveys containing patient data
3. Access patient data surveys after downgrading from a paid tier
"""

import pytest
from django.contrib.auth import get_user_model

from checktick_app.core.models import UserProfile
from checktick_app.core.tier_limits import check_patient_data_permission
from checktick_app.surveys.models import QuestionGroup, Survey

User = get_user_model()

TEST_PASSWORD = "testpass123"  # noqa: S105


@pytest.fixture
def free_user(db):
    """Create a FREE tier user."""
    user = User.objects.create_user(
        username="freeuser",
        email="free@test.com",
        password=TEST_PASSWORD,
    )
    # Profile is auto-created, default tier is FREE
    return user


@pytest.fixture
def pro_user(db):
    """Create a PRO tier user."""
    user = User.objects.create_user(
        username="prouser",
        email="pro@test.com",
        password=TEST_PASSWORD,
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.save()
    return user


@pytest.fixture
def team_user(db):
    """Create a TEAM tier user."""
    user = User.objects.create_user(
        username="teamuser",
        email="team@test.com",
        password=TEST_PASSWORD,
    )
    user.profile.account_tier = UserProfile.AccountTier.TEAM_SMALL
    user.profile.save()
    return user


@pytest.fixture
def organisation_user(db):
    """Create an ORGANISATION tier user."""
    user = User.objects.create_user(
        username="orguser",
        email="org@test.com",
        password=TEST_PASSWORD,
    )
    user.profile.account_tier = UserProfile.AccountTier.ORGANIZATION
    user.profile.save()
    return user


@pytest.fixture
def patient_details_group(db, pro_user):
    """Create a patient details question group (requires encryption)."""
    return QuestionGroup.objects.create(
        name="Patient Details",
        owner=pro_user,
        schema={
            "template": "patient_details_encrypted",
            "fields": [
                {"name": "nhs_number", "type": "text", "required": True},
                {"name": "date_of_birth", "type": "date", "required": True},
            ],
        },
    )


@pytest.fixture
def survey_with_patient_data(db, pro_user, patient_details_group):
    """Create a survey that collects patient data."""
    survey = Survey.objects.create(
        name="Patient Survey",
        slug="patient-survey",
        owner=pro_user,
    )
    survey.question_groups.add(patient_details_group)
    return survey


@pytest.fixture
def regular_group(db, pro_user):
    """Create a regular question group (no patient data)."""
    return QuestionGroup.objects.create(
        name="Feedback",
        owner=pro_user,
        schema={
            "fields": [
                {"name": "rating", "type": "number", "required": True},
                {"name": "comments", "type": "text", "required": False},
            ],
        },
    )


@pytest.fixture
def regular_survey(db, pro_user, regular_group):
    """Create a regular survey without patient data."""
    survey = Survey.objects.create(
        name="Feedback Survey",
        slug="feedback-survey",
        owner=pro_user,
    )
    survey.question_groups.add(regular_group)
    return survey


class TestPatientDataPermissions:
    """Test tier-based patient data permissions."""

    def test_free_tier_cannot_collect_patient_data(self, free_user):
        """FREE tier users should not be allowed to collect patient data."""
        can_collect, message = check_patient_data_permission(free_user)
        assert can_collect is False
        assert "upgrade" in message.lower()

    def test_pro_tier_can_collect_patient_data(self, pro_user):
        """PRO tier users should be allowed to collect patient data."""
        can_collect, message = check_patient_data_permission(pro_user)
        assert can_collect is True
        assert message == ""

    def test_team_tier_can_collect_patient_data(self, team_user):
        """TEAM tier users should be allowed to collect patient data."""
        can_collect, message = check_patient_data_permission(team_user)
        assert can_collect is True
        assert message == ""

    def test_organisation_tier_can_collect_patient_data(self, organisation_user):
        """ORGANISATION tier users should be allowed to collect patient data."""
        can_collect, message = check_patient_data_permission(organisation_user)
        assert can_collect is True
        assert message == ""


class TestSurveyPatientDataDetection:
    """Test that surveys correctly detect patient data."""

    def test_survey_detects_patient_data(self, survey_with_patient_data):
        """Survey should detect when it contains patient data templates."""
        assert survey_with_patient_data.collects_patient_data() is True

    def test_survey_detects_no_patient_data(self, regular_survey):
        """Survey should detect when it has no patient data templates."""
        assert regular_survey.collects_patient_data() is False


class TestDowngradeScenario:
    """Test the downgrade scenario where user had patient data access but lost it."""

    def test_patient_survey_readonly_after_downgrade(self, db, pro_user, patient_details_group):
        """Patient data survey should be readonly after user downgrades to FREE."""
        # Create survey while user is on PRO
        survey = Survey.objects.create(
            name="Patient Survey",
            slug="patient-survey-downgrade",
            owner=pro_user,
        )
        survey.question_groups.add(patient_details_group)

        # Survey should not be readonly while on PRO
        assert survey.is_patient_data_readonly() is False

        # Downgrade user to FREE
        pro_user.profile.account_tier = UserProfile.AccountTier.FREE
        pro_user.profile.save()

        # Refresh survey to get updated user state
        survey.refresh_from_db()

        # Survey should now be readonly
        assert survey.is_patient_data_readonly() is True

    def test_regular_survey_not_readonly_after_downgrade(self, db, pro_user, regular_group):
        """Regular survey should not be affected by downgrade."""
        survey = Survey.objects.create(
            name="Regular Survey",
            slug="regular-survey-downgrade",
            owner=pro_user,
        )
        survey.question_groups.add(regular_group)

        # Downgrade user to FREE
        pro_user.profile.account_tier = UserProfile.AccountTier.FREE
        pro_user.profile.save()

        survey.refresh_from_db()

        # Regular survey should not be readonly
        assert survey.is_patient_data_readonly() is False

    def test_patient_survey_not_readonly_on_paid_tier(self, survey_with_patient_data):
        """Patient data survey should not be readonly on paid tier."""
        assert survey_with_patient_data.is_patient_data_readonly() is False


class TestFreeTierPatientDataRestrictions:
    """Test that FREE tier users are blocked from patient data operations."""

    def test_free_user_cannot_add_patient_group_to_survey(self, db, free_user):
        """FREE tier user should be blocked from adding patient data groups."""
        # Create a survey owned by FREE user
        survey = Survey.objects.create(
            name="Free User Survey",
            slug="free-user-survey",
            owner=free_user,
        )

        # Create patient data group
        patient_group = QuestionGroup.objects.create(
            name="Patient Details",
            owner=free_user,
            schema={
                "template": "patient_details_encrypted",
                "fields": [{"name": "nhs_number", "type": "text"}],
            },
        )

        # Add group to survey
        survey.question_groups.add(patient_group)

        # The survey now has patient data but user can't collect it
        can_collect, _ = check_patient_data_permission(free_user)
        assert can_collect is False

        # Survey should be in readonly state
        assert survey.is_patient_data_readonly() is True


class TestTierUpgradeScenario:
    """Test that upgrading enables patient data collection."""

    def test_upgrade_enables_patient_data(self, db, free_user):
        """Upgrading from FREE to PRO should enable patient data collection."""
        # Initially cannot collect
        can_collect, _ = check_patient_data_permission(free_user)
        assert can_collect is False

        # Upgrade to PRO
        free_user.profile.account_tier = UserProfile.AccountTier.PRO
        free_user.profile.save()

        # Now can collect
        can_collect, _ = check_patient_data_permission(free_user)
        assert can_collect is True

    def test_upgrade_unlocks_patient_survey(self, db, free_user):
        """Upgrading should unlock previously readonly patient data surveys."""
        # Create patient data group and survey while on FREE
        patient_group = QuestionGroup.objects.create(
            name="Patient Details",
            owner=free_user,
            schema={
                "template": "patient_details_encrypted",
                "fields": [{"name": "nhs_number", "type": "text"}],
            },
        )
        survey = Survey.objects.create(
            name="Locked Survey",
            slug="locked-survey",
            owner=free_user,
        )
        survey.question_groups.add(patient_group)

        # Should be readonly on FREE
        assert survey.is_patient_data_readonly() is True

        # Upgrade to PRO
        free_user.profile.account_tier = UserProfile.AccountTier.PRO
        free_user.profile.save()

        survey.refresh_from_db()

        # Should no longer be readonly
        assert survey.is_patient_data_readonly() is False
