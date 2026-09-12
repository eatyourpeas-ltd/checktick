"""
Tests for the resume and redaction feature (see docs/survey-progress-tracking.md).

Step 1: model fields and migration.
Covers the new SurveyProgress fields (resume_token, status,
current_repeat_index, selected_group_ids, completed_at) and Survey fields
(allow_resume, allow_response_redaction), plus the new model methods
(mark_completed, mark_abandoned, is_expired, find_by_resume_token).
"""

from datetime import timedelta
import uuid

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    Survey,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture
def survey_owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def test_organization(survey_owner):
    return Organization.objects.create(name="Test Org", owner=survey_owner)


@pytest.fixture
def survey(survey_owner, test_organization):
    s = Survey.objects.create(
        owner=survey_owner,
        name="Test Survey",
        slug="test-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        organization=test_organization,
    )
    SurveyQuestion.objects.create(
        survey=s, text="Q1", type=SurveyQuestion.Types.TEXT, required=True, order=0
    )
    return s


def _make_progress(survey, **kwargs):
    """Helper to create a SurveyProgress row with sensible defaults."""
    defaults = {
        "total_questions": 1,
        "expires_at": timezone.now() + timedelta(days=30),
    }
    defaults.update(kwargs)
    return SurveyProgress.objects.create(survey=survey, **defaults)


@pytest.mark.django_db
class TestSurveyProgressNewFields:
    """New fields added by the resume/redaction migration."""

    def test_resume_token_default_generated(self, survey, survey_owner):
        """A new SurveyProgress row gets a UUID resume_token by default."""
        progress = _make_progress(survey, user=survey_owner)
        assert progress.resume_token is not None
        assert isinstance(progress.resume_token, uuid.UUID)

    def test_status_defaults_to_in_progress(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.status == SurveyProgress.Status.IN_PROGRESS

    def test_current_repeat_index_defaults_none(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.current_repeat_index is None

    def test_selected_group_ids_defaults_empty_list(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.selected_group_ids == []

    def test_completed_at_defaults_none(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.completed_at is None

    def test_resume_token_unique(self, survey, survey_owner, django_user_model):
        """Two progress rows must have different resume tokens."""
        other = django_user_model.objects.create_user(
            username="other@example.com", password=TEST_PASSWORD
        )
        p1 = _make_progress(survey, user=survey_owner)
        p2 = _make_progress(survey, user=other)
        assert p1.resume_token != p2.resume_token


@pytest.mark.django_db
class TestSurveyProgressStatusTransitions:
    """mark_completed, mark_abandoned, is_expired, find_by_resume_token."""

    def test_mark_completed_sets_status_and_completed_at(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.status == SurveyProgress.Status.IN_PROGRESS
        assert progress.completed_at is None

        progress.mark_completed()

        progress.refresh_from_db()
        assert progress.status == SurveyProgress.Status.COMPLETED
        assert progress.completed_at is not None

    def test_mark_completed_clears_resume_token(self, survey, survey_owner):
        """The resume token is invalidated on submit — its job is done."""
        progress = _make_progress(survey, user=survey_owner)
        assert progress.resume_token is not None
        token = progress.resume_token

        progress.mark_completed()

        progress.refresh_from_db()
        assert progress.resume_token is None
        # The old token no longer resolves
        assert SurveyProgress.find_by_resume_token(token) is None

    def test_mark_abandoned_sets_status(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        progress.mark_abandoned()

        progress.refresh_from_db()
        assert progress.status == SurveyProgress.Status.ABANDONED

    def test_is_expired_true_when_past_expiry(self, survey, survey_owner):
        progress = _make_progress(
            survey, user=survey_owner, expires_at=timezone.now() - timedelta(days=1)
        )
        assert progress.is_expired() is True

    def test_is_expired_false_when_future(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        assert progress.is_expired() is False

    def test_find_by_resume_token_returns_progress(self, survey, survey_owner):
        progress = _make_progress(survey, user=survey_owner)
        found = SurveyProgress.find_by_resume_token(progress.resume_token)
        assert found is not None
        assert found.pk == progress.pk

    def test_find_by_resume_token_returns_none_for_completed(
        self, survey, survey_owner
    ):
        progress = _make_progress(survey, user=survey_owner)
        token = progress.resume_token
        progress.mark_completed()

        assert SurveyProgress.find_by_resume_token(token) is None

    def test_find_by_resume_token_returns_none_for_expired(self, survey, survey_owner):
        progress = _make_progress(
            survey, user=survey_owner, expires_at=timezone.now() - timedelta(days=1)
        )
        assert SurveyProgress.find_by_resume_token(progress.resume_token) is None

    def test_find_by_resume_token_returns_none_for_unknown(self):
        unknown = uuid.uuid4()
        assert SurveyProgress.find_by_resume_token(unknown) is None


@pytest.mark.django_db
class TestSurveyResumeRedactionToggles:
    """Survey.allow_resume and Survey.allow_response_redaction fields."""

    def test_allow_resume_defaults_true(self, survey_owner, test_organization):
        s = Survey.objects.create(
            owner=survey_owner,
            name="S",
            slug="s1",
            organization=test_organization,
        )
        assert s.allow_resume is True

    def test_allow_response_redaction_defaults_true(
        self, survey_owner, test_organization
    ):
        s = Survey.objects.create(
            owner=survey_owner,
            name="S",
            slug="s2",
            organization=test_organization,
        )
        assert s.allow_response_redaction is True

    def test_allow_resume_can_be_disabled(self, survey_owner, test_organization):
        s = Survey.objects.create(
            owner=survey_owner,
            name="S",
            slug="s3",
            organization=test_organization,
            allow_resume=False,
        )
        assert s.allow_resume is False

    def test_allow_response_redaction_can_be_disabled(
        self, survey_owner, test_organization
    ):
        s = Survey.objects.create(
            owner=survey_owner,
            name="S",
            slug="s4",
            organization=test_organization,
            allow_response_redaction=False,
        )
        assert s.allow_response_redaction is False
