"""
Tests for data subject request handling and response freeze mechanism.

These tests ensure:
1. Receipt tokens are only generated for pseudonymous surveys
2. Anonymous surveys do NOT receive receipt tokens
3. Frozen responses are excluded from exports
4. DataSubjectRequest workflow functions correctly
5. Freeze permissions are enforced correctly
"""

from datetime import timedelta
import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DataSubjectRequest,
    Organization,
    OrganizationMembership,
    ResponseFreezeLog,
    Survey,
    SurveyResponse,
    Team,
    TeamMembership,
)
from checktick_app.surveys.services.export_service import ExportService

User = get_user_model()

# Use constant for test passwords to satisfy pre-commit hook
TEST_PASSWORD = "x"


@pytest.fixture
def owner(db):
    """Create a survey owner user."""
    return User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user for freezing responses."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def respondent(db):
    """Create a respondent user."""
    return User.objects.create_user(
        username="respondent",
        email="respondent@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def authenticated_survey(owner):
    """Create a survey with authenticated visibility."""
    return Survey.objects.create(
        owner=owner,
        name="Authenticated Survey",
        slug="authenticated-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
    )


@pytest.fixture
def token_survey(owner):
    """Create a survey with token visibility."""
    return Survey.objects.create(
        owner=owner,
        name="Token Survey",
        slug="token-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )


@pytest.fixture
def public_survey(owner):
    """Create a survey with public (anonymous) visibility."""
    return Survey.objects.create(
        owner=owner,
        name="Public Survey",
        slug="public-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )


@pytest.fixture
def unlisted_survey(owner):
    """Create a survey with unlisted (anonymous) visibility."""
    return Survey.objects.create(
        owner=owner,
        name="Unlisted Survey",
        slug="unlisted-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.UNLISTED,
    )


class TestReceiptTokenGeneration:
    """Tests for receipt token generation logic."""

    def test_authenticated_survey_response_is_pseudonymous(
        self, authenticated_survey, respondent
    ):
        """Authenticated survey responses should be pseudonymous."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        assert response.is_pseudonymous is True

    def test_token_survey_response_is_pseudonymous(self, token_survey):
        """Token survey responses should be pseudonymous."""
        response = SurveyResponse.objects.create(
            survey=token_survey,
            answers={"q1": "answer1"},
        )
        # Token survey without access_token or submitted_by - still pseudonymous
        # because the survey visibility implies identity tracking
        assert response.is_pseudonymous is True

    def test_public_survey_response_is_anonymous(self, public_survey):
        """Public survey responses without auth should be anonymous."""
        response = SurveyResponse.objects.create(
            survey=public_survey,
            answers={"q1": "answer1"},
        )
        assert response.is_pseudonymous is False

    def test_unlisted_survey_response_is_anonymous(self, unlisted_survey):
        """Unlisted survey responses without auth should be anonymous."""
        response = SurveyResponse.objects.create(
            survey=unlisted_survey,
            answers={"q1": "answer1"},
        )
        assert response.is_pseudonymous is False

    def test_receipt_token_generated_for_pseudonymous(
        self, authenticated_survey, respondent
    ):
        """Receipt tokens should be generated for pseudonymous responses."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        token = response.generate_receipt_token()
        assert token is not None
        assert isinstance(token, uuid.UUID)
        assert response.receipt_token == token

    def test_receipt_token_not_generated_for_anonymous(self, public_survey):
        """Receipt tokens should NOT be generated for anonymous responses."""
        response = SurveyResponse.objects.create(
            survey=public_survey,
            answers={"q1": "answer1"},
        )
        token = response.generate_receipt_token()
        assert token is None
        assert response.receipt_token is None

    def test_receipt_token_idempotent(self, authenticated_survey, respondent):
        """Calling generate_receipt_token twice returns same token."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        token1 = response.generate_receipt_token()
        token2 = response.generate_receipt_token()
        assert token1 == token2


class TestResponseFreeze:
    """Tests for response freeze mechanism."""

    def test_freeze_response(self, authenticated_survey, respondent, admin_user):
        """Freezing a response should set all freeze fields."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Data subject request pending (DSR-123)",
            frozen_by_user=admin_user,
        )

        response.refresh_from_db()
        assert response.is_frozen is True
        assert response.frozen_at is not None
        assert response.frozen_reason == "Data subject request pending (DSR-123)"
        assert response.frozen_by == admin_user

    def test_unfreeze_response(self, authenticated_survey, respondent, admin_user):
        """Unfreezing should clear freeze fields but preserve resolution note."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Data subject request pending",
            frozen_by_user=admin_user,
        )
        response.unfreeze(resolution_note="Controller confirmed lawful basis")

        response.refresh_from_db()
        assert response.is_frozen is False
        assert response.frozen_at is None
        assert response.frozen_by is None
        assert "RESOLVED" in response.frozen_reason
        assert "Controller confirmed lawful basis" in response.frozen_reason

    def test_frozen_responses_excluded_from_export(
        self, authenticated_survey, respondent, admin_user
    ):
        """Frozen responses should be excluded from exports."""
        from checktick_app.surveys.models import SurveyQuestion

        # Create a question so answers appear in CSV
        question = SurveyQuestion.objects.create(
            survey=authenticated_survey,
            text="Test Question",
            type="text",
            order=1,
        )

        # Create two responses
        _ = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={str(question.id): "normal response"},
        )
        # Create another user for the second response (unique constraint)
        other_respondent = User.objects.create_user(
            username="other_respondent",
            email="other@example.com",
            password=TEST_PASSWORD,
        )
        response2 = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=other_respondent,
            answers={str(question.id): "frozen response"},
        )

        # Freeze one response
        response2.freeze(
            reason="Data subject request",
            frozen_by_user=admin_user,
        )

        # Close survey for export
        authenticated_survey.close_survey(admin_user)

        # Generate CSV - should only include unfrozen response
        csv_data = ExportService._generate_csv(authenticated_survey)

        assert "normal response" in csv_data
        assert "frozen response" not in csv_data

    def test_all_frozen_responses_blocks_export(
        self, authenticated_survey, respondent, admin_user
    ):
        """Export should fail if all responses are frozen."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"1": "only response"},
        )
        response.freeze(
            reason="Data subject request",
            frozen_by_user=admin_user,
        )

        # Close survey for export
        authenticated_survey.close_survey(admin_user)

        with pytest.raises(ValueError) as exc_info:
            ExportService.create_export(
                survey=authenticated_survey,
                user=admin_user,
            )

        assert "frozen" in str(exc_info.value).lower()


class TestDataSubjectRequest:
    """Tests for DataSubjectRequest model and workflow."""

    def test_create_data_subject_request(self, authenticated_survey, admin_user):
        """Create a basic data subject request."""
        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            request_type=DataSubjectRequest.RequestType.ERASURE,
            respondent_email="respondent@example.com",
            request_details="Please delete my response",
            created_by=admin_user,
        )

        assert dsr.status == DataSubjectRequest.Status.RECEIVED
        assert dsr.controller_notified_at is None
        assert dsr.controller_deadline is None

    def test_notify_controller_sets_deadline(self, authenticated_survey, admin_user):
        """Notifying controller should set 30-day deadline."""
        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            request_type=DataSubjectRequest.RequestType.ERASURE,
            respondent_email="respondent@example.com",
            request_details="Please delete my response",
            created_by=admin_user,
        )

        dsr.notify_controller()

        dsr.refresh_from_db()
        assert dsr.status == DataSubjectRequest.Status.REFERRED
        assert dsr.controller_notified_at is not None
        assert dsr.controller_deadline is not None

        # Deadline should be ~30 days from notification
        expected_deadline = dsr.controller_notified_at + timedelta(days=30)
        assert abs((dsr.controller_deadline - expected_deadline).total_seconds()) < 60

    def test_is_overdue_before_deadline(self, authenticated_survey, admin_user):
        """Request should not be overdue before deadline."""
        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            request_type=DataSubjectRequest.RequestType.ACCESS,
            respondent_email="respondent@example.com",
            request_details="Please provide my data",
            created_by=admin_user,
        )
        dsr.notify_controller()

        assert dsr.is_overdue is False

    def test_is_overdue_after_deadline(self, authenticated_survey, admin_user):
        """Request should be overdue after deadline passes."""
        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            request_type=DataSubjectRequest.RequestType.ACCESS,
            respondent_email="respondent@example.com",
            request_details="Please provide my data",
            created_by=admin_user,
        )
        dsr.notify_controller()

        # Manually set deadline to past
        dsr.controller_deadline = timezone.now() - timedelta(days=1)
        dsr.save()

        assert dsr.is_overdue is True

    def test_escalate_freezes_response(
        self, authenticated_survey, respondent, admin_user
    ):
        """Escalating a request should freeze the associated response."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        response.generate_receipt_token()

        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            response=response,
            request_type=DataSubjectRequest.RequestType.ERASURE,
            respondent_email="respondent@example.com",
            receipt_token=response.receipt_token,
            request_details="Please delete my response",
            created_by=admin_user,
        )

        dsr.escalate(freeze_response=True)

        dsr.refresh_from_db()
        response.refresh_from_db()

        assert dsr.status == DataSubjectRequest.Status.FROZEN
        assert dsr.escalated_at is not None
        assert response.is_frozen is True

    def test_resolve_unfreezes_response(
        self, authenticated_survey, respondent, admin_user
    ):
        """Resolving a request should unfreeze the associated response."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        response.generate_receipt_token()

        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            response=response,
            request_type=DataSubjectRequest.RequestType.ACCESS,
            respondent_email="respondent@example.com",
            receipt_token=response.receipt_token,
            request_details="Please provide my data",
            created_by=admin_user,
        )

        # Freeze first
        dsr.escalate(freeze_response=True)
        assert response.is_frozen is True

        # Then resolve
        dsr.resolve(
            resolution_notes="Controller provided data to respondent",
            resolved_by=admin_user,
        )

        dsr.refresh_from_db()
        response.refresh_from_db()

        assert dsr.status == DataSubjectRequest.Status.RESOLVED
        assert dsr.resolved_at is not None
        assert response.is_frozen is False

    def test_find_by_receipt_token(self, authenticated_survey, respondent, admin_user):
        """Should be able to find DSR by receipt token."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        token = response.generate_receipt_token()

        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            response=response,
            request_type=DataSubjectRequest.RequestType.OBJECTION,
            respondent_email="respondent@example.com",
            receipt_token=token,
            request_details="I object to processing",
            created_by=admin_user,
        )

        found = DataSubjectRequest.find_by_receipt_token(token)
        assert found == dsr

    def test_days_until_deadline(self, authenticated_survey, admin_user):
        """Should correctly calculate days until deadline."""
        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            request_type=DataSubjectRequest.RequestType.ERASURE,
            respondent_email="respondent@example.com",
            request_details="Delete my data",
            created_by=admin_user,
        )
        dsr.notify_controller()

        # Should be approximately 30 days (29 or 30 depending on timing)
        assert 28 <= dsr.days_until_deadline <= 30


class TestFreezePermissions:
    """Tests for freeze/unfreeze permission enforcement."""

    def test_controller_initiated_freeze(self, authenticated_survey, respondent, owner):
        """Controller can freeze responses they own."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Respondent requested data review",
            frozen_by_user=owner,
            source="controller",
        )

        response.refresh_from_db()
        assert response.is_frozen is True
        assert response.freeze_source == SurveyResponse.FreezeSource.CONTROLLER

    def test_platform_initiated_freeze(
        self, authenticated_survey, respondent, admin_user
    ):
        """Platform admin can freeze with platform source."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="DSR escalation - controller non-responsive",
            frozen_by_user=admin_user,
            source="platform",
        )

        response.refresh_from_db()
        assert response.is_frozen is True
        assert response.freeze_source == SurveyResponse.FreezeSource.PLATFORM
        assert response.is_platform_frozen is True

    def test_owner_can_unfreeze_controller_frozen(
        self, authenticated_survey, respondent, owner
    ):
        """Survey owner can unfreeze controller-initiated freezes."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Investigation pending",
            frozen_by_user=owner,
            source="controller",
        )

        assert response.can_unfreeze(owner) is True

    def test_owner_cannot_unfreeze_platform_frozen(
        self, authenticated_survey, respondent, owner, admin_user
    ):
        """Survey owner CANNOT unfreeze platform-initiated freezes."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="DSR escalation",
            frozen_by_user=admin_user,
            source="platform",
        )

        assert response.can_unfreeze(owner) is False

    def test_superuser_can_unfreeze_any(
        self, authenticated_survey, respondent, admin_user
    ):
        """Superuser can unfreeze any frozen response."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Platform freeze",
            frozen_by_user=admin_user,
            source="platform",
        )

        assert response.can_unfreeze(admin_user) is True

    def test_org_admin_can_unfreeze_controller_frozen(self, owner, respondent):
        """Organization admin can unfreeze controller-initiated freezes."""
        org = Organization.objects.create(name="Test Org", owner=owner)
        org_admin = User.objects.create_user(
            username="org_admin",
            email="org_admin@example.com",
            password=TEST_PASSWORD,
        )
        OrganizationMembership.objects.create(
            organization=org,
            user=org_admin,
            role=OrganizationMembership.Role.ADMIN,
        )

        survey = Survey.objects.create(
            owner=owner,
            organization=org,
            name="Org Survey",
            slug="org-survey-freeze-test",
            status=Survey.Status.PUBLISHED,
            visibility=Survey.Visibility.AUTHENTICATED,
        )

        response = SurveyResponse.objects.create(
            survey=survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Controller freeze",
            frozen_by_user=owner,
            source="controller",
        )

        assert response.can_unfreeze(org_admin) is True

    def test_team_admin_can_unfreeze_controller_frozen(self, owner, respondent):
        """Team admin can unfreeze controller-initiated freezes on team surveys."""
        team = Team.objects.create(name="Test Team", owner=owner)
        team_admin = User.objects.create_user(
            username="team_admin",
            email="team_admin@example.com",
            password=TEST_PASSWORD,
        )
        TeamMembership.objects.create(
            team=team,
            user=team_admin,
            role=TeamMembership.Role.ADMIN,
        )

        survey = Survey.objects.create(
            owner=owner,
            team=team,
            name="Team Survey",
            slug="team-survey-freeze-test",
            status=Survey.Status.PUBLISHED,
            visibility=Survey.Visibility.AUTHENTICATED,
        )

        response = SurveyResponse.objects.create(
            survey=survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Controller freeze",
            frozen_by_user=owner,
            source="controller",
        )

        assert response.can_unfreeze(team_admin) is True

    def test_random_user_cannot_unfreeze(self, authenticated_survey, respondent, owner):
        """Random users cannot unfreeze responses."""
        random_user = User.objects.create_user(
            username="random",
            email="random@example.com",
            password=TEST_PASSWORD,
        )

        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )

        response.freeze(
            reason="Controller freeze",
            frozen_by_user=owner,
            source="controller",
        )

        assert response.can_unfreeze(random_user) is False


class TestResponseFreezeLog:
    """Tests for freeze audit logging."""

    def test_freeze_creates_log(self, authenticated_survey, respondent, admin_user):
        """Freezing via DSR escalation creates a log entry."""
        response = SurveyResponse.objects.create(
            survey=authenticated_survey,
            submitted_by=respondent,
            answers={"q1": "answer1"},
        )
        response.generate_receipt_token()

        dsr = DataSubjectRequest.objects.create(
            survey=authenticated_survey,
            response=response,
            request_type=DataSubjectRequest.RequestType.ERASURE,
            respondent_email="respondent@example.com",
            receipt_token=response.receipt_token,
            request_details="Delete my data",
            created_by=admin_user,
        )

        dsr.escalate(freeze_response=True)

        logs = ResponseFreezeLog.objects.filter(response=response)
        assert logs.count() == 1

        log = logs.first()
        assert log.action == ResponseFreezeLog.Action.FREEZE
        assert log.source == SurveyResponse.FreezeSource.PLATFORM
        assert log.data_subject_request == dsr
        assert "DSR escalation" in log.reason


class TestSurveySuspension:
    """Tests for survey suspension functionality."""

    def test_suspend_survey(self, authenticated_survey, admin_user):
        """Suspending a survey sets status and metadata."""
        authenticated_survey.suspend(
            reason="Non-compliance with data subject request",
            suspended_by=admin_user,
        )

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.status == Survey.Status.SUSPENDED
        assert authenticated_survey.is_suspended is True
        assert authenticated_survey.suspended_at is not None
        assert authenticated_survey.suspended_by == admin_user
        assert "Non-compliance" in authenticated_survey.suspended_reason

    def test_suspended_survey_is_not_live(self, authenticated_survey, admin_user):
        """Suspended surveys should not be live."""
        assert authenticated_survey.is_live() is True

        authenticated_survey.suspend(
            reason="Test suspension",
            suspended_by=admin_user,
        )

        assert authenticated_survey.is_live() is False

    def test_unsuspend_survey(self, authenticated_survey, admin_user):
        """Unsuspending restores survey to published status."""
        authenticated_survey.suspend(
            reason="Test suspension",
            suspended_by=admin_user,
        )

        authenticated_survey.unsuspend(unsuspend_reason="Issue resolved")

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.status == Survey.Status.PUBLISHED
        assert authenticated_survey.is_suspended is False
        assert authenticated_survey.suspended_at is None
        assert "RESOLVED" in authenticated_survey.suspended_reason

    def test_dsr_warning_flag(self, authenticated_survey):
        """DSR warning can be set and cleared."""
        authenticated_survey.set_dsr_warning(
            "You have 1 pending data subject request. Please respond within 7 days."
        )

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.has_pending_dsr is True
        assert (
            "pending data subject request" in authenticated_survey.dsr_warning_message
        )

        authenticated_survey.clear_dsr_warning()

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.has_pending_dsr is False
        assert authenticated_survey.dsr_warning_message == ""
