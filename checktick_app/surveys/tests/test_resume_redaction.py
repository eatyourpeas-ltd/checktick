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


@pytest.mark.django_db
class TestPublishWorkflowToggle:
    """The allow_resume and allow_response_redaction toggles are wired into
    the publication workflow (publish_settings view)."""

    def test_publish_preserves_default_toggles(self, client, survey_owner):
        """Publishing with the toggle checkboxes checked keeps them True.

        Uses staff audience + opt-out declaration to avoid the encryption
        setup redirect — the toggles are independent of audience/encryption.
        """
        from django.urls import reverse

        s = Survey.objects.create(
            owner=survey_owner,
            name="Pub",
            slug="pub-toggle-default",
            status=Survey.Status.DRAFT,
            visibility=Survey.Visibility.PUBLIC,
        )
        client.force_login(survey_owner)
        client.post(
            reverse("surveys:publish_settings", args=[s.slug]),
            {
                "action": "publish",
                "visibility": "public",
                "respondent_audience": "staff",
                "encryption_opt_out": "on",
                "no_patient_data_ack": "on",
                "allow_resume": "on",
                "allow_response_redaction": "on",
            },
        )
        s.refresh_from_db()
        assert s.status == Survey.Status.PUBLISHED
        assert s.allow_resume is True
        assert s.allow_response_redaction is True

    def test_publish_can_disable_resume(self, client, survey_owner):
        from django.urls import reverse

        s = Survey.objects.create(
            owner=survey_owner,
            name="Pub",
            slug="pub-toggle-no-resume",
            status=Survey.Status.DRAFT,
            visibility=Survey.Visibility.PUBLIC,
        )
        client.force_login(survey_owner)
        client.post(
            reverse("surveys:publish_settings", args=[s.slug]),
            {
                "action": "publish",
                "visibility": "public",
                "respondent_audience": "staff",
                "encryption_opt_out": "on",
                "no_patient_data_ack": "on",
                "allow_resume": "",  # unchecked
                "allow_response_redaction": "on",
            },
        )
        s.refresh_from_db()
        assert s.allow_resume is False
        assert s.allow_response_redaction is True

    def test_publish_can_disable_redaction(self, client, survey_owner):
        from django.urls import reverse

        s = Survey.objects.create(
            owner=survey_owner,
            name="Pub",
            slug="pub-toggle-no-redaction",
            status=Survey.Status.DRAFT,
            visibility=Survey.Visibility.PUBLIC,
        )
        client.force_login(survey_owner)
        client.post(
            reverse("surveys:publish_settings", args=[s.slug]),
            {
                "action": "publish",
                "visibility": "public",
                "respondent_audience": "staff",
                "encryption_opt_out": "on",
                "no_patient_data_ack": "on",
                "allow_resume": "on",
                "allow_response_redaction": "",  # unchecked
            },
        )
        s.refresh_from_db()
        assert s.allow_resume is True
        assert s.allow_response_redaction is False

    def test_save_action_updates_toggles(self, client, survey_owner):
        """The 'save' action (for already-published surveys) also persists
        the toggles."""
        from django.urls import reverse

        s = Survey.objects.create(
            owner=survey_owner,
            name="Pub",
            slug="pub-save-toggle",
            status=Survey.Status.PUBLISHED,
            visibility=Survey.Visibility.PUBLIC,
            respondent_audience=Survey.RespondentAudience.PUBLIC,
            audience_confirmed=True,
            allow_resume=True,
            allow_response_redaction=True,
        )
        client.force_login(survey_owner)
        client.post(
            reverse("surveys:publish_settings", args=[s.slug]),
            {
                "action": "save",
                "visibility": "public",
                "allow_resume": "",  # disable
                "allow_response_redaction": "on",
            },
        )
        s.refresh_from_db()
        assert s.allow_resume is False
        assert s.allow_response_redaction is True


@pytest.fixture
def public_survey_for_resume(survey_owner, test_organization):
    """A public survey with allow_resume=True for resume token tests."""
    from checktick_app.surveys.models import SurveyQuestion

    s = Survey.objects.create(
        owner=survey_owner,
        name="Resume Survey",
        slug="resume-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
        organization=test_organization,
        allow_resume=True,
    )
    q = SurveyQuestion.objects.create(
        survey=s, text="Q1", type=SurveyQuestion.Types.TEXT, required=False, order=0
    )
    s._test_q1_id = q.id
    return s


@pytest.mark.django_db
class TestSaveAndComeBackLater:
    """The 'save_resume' action issues a resume token for public surveys."""

    def test_save_resume_creates_progress_with_token(
        self, client, public_survey_for_resume
    ):
        """Clicking 'Save and come back later' creates a SurveyProgress row
        with a resume token and returns the resume URL."""
        from django.urls import reverse

        url = reverse("surveys:take", kwargs={"slug": public_survey_for_resume.slug})
        q_id = public_survey_for_resume._test_q1_id

        response = client.post(
            url,
            {
                "action": "save_resume",
                f"q_{q_id}": "My answer",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "resume_url" in data
        assert "resume_token" in data
        assert "/take/resume/" in data["resume_url"]

        # A progress row was created with the resume token
        progress = SurveyProgress.objects.get(survey=public_survey_for_resume)
        assert progress.resume_token is not None
        assert str(progress.resume_token) == data["resume_token"]
        assert progress.partial_answers[str(q_id)] == "My answer"
        assert progress.status == SurveyProgress.Status.IN_PROGRESS

    def test_save_resume_reuses_existing_token(self, client, public_survey_for_resume):
        """A second 'save_resume' call reuses the existing progress row's
        token rather than creating a new one."""
        from django.urls import reverse

        url = reverse("surveys:take", kwargs={"slug": public_survey_for_resume.slug})
        q_id = public_survey_for_resume._test_q1_id

        # First save
        response1 = client.post(
            url,
            {"action": "save_resume", f"q_{q_id}": "Answer 1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        token1 = response1.json()["resume_token"]

        # Second save — should reuse the same token
        response2 = client.post(
            url,
            {"action": "save_resume", f"q_{q_id}": "Answer 2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        token2 = response2.json()["resume_token"]

        assert token1 == token2
        assert (
            SurveyProgress.objects.filter(survey=public_survey_for_resume).count() == 1
        )

    def test_save_resume_disabled_when_allow_resume_false(
        self, client, public_survey_for_resume
    ):
        """When allow_resume is False, the save_resume action is rejected."""
        from django.urls import reverse

        public_survey_for_resume.allow_resume = False
        public_survey_for_resume.save(update_fields=["allow_resume"])

        url = reverse("surveys:take", kwargs={"slug": public_survey_for_resume.slug})
        q_id = public_survey_for_resume._test_q1_id

        response = client.post(
            url,
            {"action": "save_resume", f"q_{q_id}": "Answer"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 403
        assert not SurveyProgress.objects.filter(
            survey=public_survey_for_resume
        ).exists()


@pytest.mark.django_db
class TestResumeRoute:
    """The /take/resume/<uuid>/ route resolves a resume token and continues
    the survey."""

    def test_resume_route_returns_survey_with_saved_answers(
        self, client, public_survey_for_resume
    ):
        """Resuming via token shows the survey with previously saved answers."""
        from django.urls import reverse

        # Create a progress row with a resume token
        progress = _make_progress(
            public_survey_for_resume,
            partial_answers={str(public_survey_for_resume._test_q1_id): "Saved"},
            answered_count=1,
        )

        url = reverse(
            "surveys:take_resume", kwargs={"resume_token": progress.resume_token}
        )
        response = client.get(url)

        assert response.status_code == 200
        context = response.context
        assert context["show_progress"] is True
        assert (
            context["saved_answers"][str(public_survey_for_resume._test_q1_id)]
            == "Saved"
        )

    def test_resume_route_invalid_token_shows_expired_page(self, client):
        """An unknown resume token shows the neutral expired page, not a 500."""
        from django.urls import reverse

        unknown_token = uuid.uuid4()
        url = reverse("surveys:take_resume", kwargs={"resume_token": unknown_token})
        response = client.get(url)

        assert response.status_code == 404
        assert b"expired" in response.content.lower()

    def test_resume_route_expired_token_shows_expired_page(
        self, client, public_survey_for_resume
    ):
        """An expired resume token shows the neutral expired page."""
        from django.urls import reverse

        progress = _make_progress(
            public_survey_for_resume,
            expires_at=timezone.now() - timedelta(days=1),
        )
        url = reverse(
            "surveys:take_resume", kwargs={"resume_token": progress.resume_token}
        )
        response = client.get(url)

        assert response.status_code == 404
        assert b"expired" in response.content.lower()

    def test_resume_route_completed_token_shows_expired_page(
        self, client, public_survey_for_resume
    ):
        """A resume token for a completed survey shows the expired page."""
        from django.urls import reverse

        progress = _make_progress(public_survey_for_resume)
        token = progress.resume_token
        progress.mark_completed()

        url = reverse("surveys:take_resume", kwargs={"resume_token": token})
        response = client.get(url)

        assert response.status_code == 404

    def test_resume_route_authenticated_survey_token_rejected(
        self, client, survey, survey_owner
    ):
        """A resume token for an authenticated survey is rejected (resume
        tokens are only for public/unlisted surveys)."""
        from django.urls import reverse

        progress = _make_progress(survey, user=survey_owner)
        url = reverse(
            "surveys:take_resume", kwargs={"resume_token": progress.resume_token}
        )
        response = client.get(url)

        # Should show the expired page, not the survey
        assert response.status_code == 404
