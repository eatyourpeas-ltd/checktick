"""Tests for the publish-flow audience prompt and encryption opt-out
declaration (encryption planning doc §5.2).

The creator must confirm who fills the survey in before publishing. For
password-user, staff-audience surveys without patient identifiers, an
explicit, audit-logged declaration is the only path to publishing without
encryption. Patient/public audience surveys always require encryption.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import AuditLog, Survey

User = get_user_model()

TEST_PASSWORD = "x"  # noqa: S105


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="publisher", email="pub@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def draft_survey(db, owner):
    return Survey.objects.create(owner=owner, name="Draft", slug="draft-audience")


def _publish_post(**extra):
    data = {"action": "publish", "visibility": "public"}
    data.update(extra)
    return data


@pytest.mark.django_db
class TestPublishAudiencePrompt:
    def test_first_publish_requires_audience_confirmation(
        self, client, owner, draft_survey
    ):
        client.force_login(owner)
        client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(),
        )
        draft_survey.refresh_from_db()
        assert draft_survey.status != Survey.Status.PUBLISHED
        # The audience must now be confirmed
        assert draft_survey.audience_confirmed is False

    def test_staff_audience_with_declaration_publishes_without_encryption(
        self, client, owner, draft_survey
    ):
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="staff", encryption_opt_out="on"),
        )
        assert resp.status_code == 302
        draft_survey.refresh_from_db()
        assert draft_survey.status == Survey.Status.PUBLISHED
        assert draft_survey.respondent_audience == Survey.RespondentAudience.STAFF
        assert draft_survey.audience_confirmed is True
        assert draft_survey.has_any_encryption() is False
        # Declaration recorded and audit-logged (not a grandfathered entry)
        assert draft_survey.has_encryption_opt_out() is True
        assert draft_survey.encryption_opt_out_declaration_version == "1.0"
        log = AuditLog.objects.filter(
            survey=draft_survey,
            action=AuditLog.Action.ENCRYPTION_OPT_OUT_DECLARED,
        ).first()
        assert log is not None
        assert log.metadata.get("grandfathered") is None
        assert log.metadata.get("declaration_version") == "1.0"
        # Plaintext storage is now legitimate for this survey
        assert draft_survey.requires_whole_response_encryption() is False

    def test_patient_audience_requires_encryption_setup(
        self, client, owner, draft_survey
    ):
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="patient"),
        )
        # Redirected to encryption setup; survey not published
        assert resp.status_code == 302
        assert "encryption" in resp["Location"]
        draft_survey.refresh_from_db()
        assert draft_survey.status != Survey.Status.PUBLISHED
        # Audience confirmation was applied though
        assert draft_survey.respondent_audience == Survey.RespondentAudience.PATIENT
        assert draft_survey.audience_confirmed is True

    def test_public_audience_requires_encryption_setup(
        self, client, owner, draft_survey
    ):
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="public"),
        )
        assert resp.status_code == 302
        assert "encryption" in resp["Location"]

    def test_declaration_ignored_for_sso_owner(self, client, db, draft_survey, owner):
        """SSO owners cannot opt out: the declaration must not enable
        plaintext publishing."""
        UserOIDC.objects.create(user=owner, provider="google", subject="sub-pub-1")
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="staff", encryption_opt_out="on"),
        )
        assert resp.status_code == 302
        assert "encryption" in resp["Location"]
        draft_survey.refresh_from_db()
        assert draft_survey.status != Survey.Status.PUBLISHED
        assert draft_survey.encryption_opt_out_at is None

    def test_declaration_not_recorded_without_checkbox(
        self, client, owner, draft_survey
    ):
        client.force_login(owner)
        client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="staff"),
        )
        draft_survey.refresh_from_db()
        assert draft_survey.encryption_opt_out_at is None
