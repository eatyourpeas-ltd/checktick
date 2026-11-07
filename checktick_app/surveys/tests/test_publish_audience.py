"""Tests for the publish-flow respondent-audience prompt and the universal
encryption requirement (encryption planning doc §5.2).

The creator must confirm who fills the survey in before publishing. Every
survey encrypts responses at rest: there is no opt-out. The historical
opt-out declaration rows (explicit "1.0" and grandfathered "legacy-1.0")
remain honoured by the predicate for data access, but the publish flow
never creates them — posting the removed `encryption_opt_out` field is
ignored and encryption setup is required for all first-time publishers.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

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

    def test_staff_audience_requires_encryption_setup(
        self, client, owner, draft_survey
    ):
        """Staff-audience surveys encrypt too — the removed opt-out field is
        ignored and encryption setup is required before publishing."""
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[draft_survey.slug]),
            _publish_post(respondent_audience="staff", encryption_opt_out="on"),
        )
        # Redirected to encryption setup; survey not published
        assert resp.status_code == 302
        assert "encryption" in resp["Location"]
        draft_survey.refresh_from_db()
        assert draft_survey.status != Survey.Status.PUBLISHED
        assert draft_survey.respondent_audience == Survey.RespondentAudience.STAFF
        assert draft_survey.audience_confirmed is True
        # No opt-out declaration was created by the removed mechanism
        assert draft_survey.encryption_opt_out_at is None
        assert draft_survey.has_encryption_opt_out() is False
        # The predicate requires encryption
        assert draft_survey.requires_whole_response_encryption() is True
        # No opt-out declaration audit event exists
        assert not AuditLog.objects.filter(
            survey=draft_survey,
            action=AuditLog.Action.ENCRYPTION_OPT_OUT_DECLARED,
        ).exists()

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

    def test_no_patient_data_declaration_audit_logged_on_publish(
        self, client, owner, db
    ):
        """The no-patient-data declaration required for public visibility is
        audit-logged when the survey is first published (the platform
        owner's defensive record)."""
        survey = Survey.objects.create(
            owner=owner, name="Public", slug="public-audit-ack"
        )
        # Pre-existing encryption skips the setup redirect
        survey.encrypted_kek_password = b"w" * 32
        survey.save()
        client.force_login(owner)
        resp = client.post(
            reverse("surveys:publish_settings", args=[survey.slug]),
            _publish_post(respondent_audience="staff", no_patient_data_ack="on"),
        )
        assert resp.status_code == 302
        survey.refresh_from_db()
        assert survey.status == Survey.Status.PUBLISHED
        assert survey.no_patient_data_ack is True
        log = AuditLog.objects.filter(
            survey=survey,
            action=AuditLog.Action.NO_PATIENT_DATA_DECLARED,
        ).first()
        assert log is not None
        assert log.actor == owner

    def test_no_patient_data_declaration_not_logged_without_ack(
        self, client, owner, db
    ):
        """Publishing an authenticated survey without the ack logs nothing."""
        survey = Survey.objects.create(
            owner=owner, name="Auth", slug="auth-no-ack-audit"
        )
        survey.encrypted_kek_password = b"w" * 32
        survey.save()
        client.force_login(owner)
        client.post(
            reverse("surveys:publish_settings", args=[survey.slug]),
            {
                "action": "publish",
                "visibility": "authenticated",
                "respondent_audience": "staff",
                "allow_any_authenticated": "on",
            },
        )
        survey.refresh_from_db()
        assert survey.status == Survey.Status.PUBLISHED
        assert not AuditLog.objects.filter(
            survey=survey,
            action=AuditLog.Action.NO_PATIENT_DATA_DECLARED,
        ).exists()
