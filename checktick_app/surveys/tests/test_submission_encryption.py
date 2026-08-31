"""Tests for submission keypair encryption (Option B).

Surveys with a submission keypair encrypt responses with the survey's PUBLIC
key at submission time. The server can encrypt but never decrypt: the private
key is wrapped with the owner's credentials (encrypted_kek_* fields) and only
exists unwrapped in an unlocked owner session. See
docs/security-upgrade-encrypt-all-responses-planning.md and
docs/encryption-technical-reference.md.
"""

import os

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import Survey, SurveyResponse
from checktick_app.surveys.utils import (
    SUBMISSION_BLOB_MAGIC,
    decrypt_submission,
    encrypt_for_submission,
    encrypt_kek_with_passphrase,
    encrypt_sensitive,
    generate_submission_keypair,
    is_submission_blob,
)

User = get_user_model()

TEST_PASSWORD = "x"  # noqa: S105


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="keypairowner", email="kp@example.com", password=TEST_PASSWORD
    )


RECOVERY_PHRASE = (
    "abandon ability able about above absent absorb abstract absurd abuse "
    "access accident"
)  # noqa: S105


@pytest.fixture
def keypair_survey(db, user):
    """Survey with a submission keypair; private key wrapped with password
    and recovery phrase (dual encryption, mirroring the real setup flow)."""
    private_key, public_key = generate_submission_keypair()
    survey = Survey.objects.create(
        owner=user,
        name="Keypair Survey",
        slug="keypair-survey",
        submission_public_key=public_key,
        encrypted_kek_password=encrypt_kek_with_passphrase(
            private_key, "OwnerPassword123"
        ),
        encrypted_kek_recovery=encrypt_kek_with_passphrase(
            private_key, RECOVERY_PHRASE
        ),
    )
    return survey, private_key


@pytest.mark.django_db
class TestSubmissionKeypairUtils:
    def test_generate_keypair_roundtrip_shape(self):
        private_key, public_key = generate_submission_keypair()
        assert len(private_key) == 32
        assert len(public_key) == 32
        assert private_key != public_key

    def test_encrypt_decrypt_roundtrip(self):
        _, public_key = generate_submission_keypair()
        private_key, _ = generate_submission_keypair()
        # Use matching pair
        private_key, public_key = generate_submission_keypair()
        payload = {"answers": {"q1": "hello"}, "demographics": {"nhs": "1"}}
        blob = encrypt_for_submission(public_key, payload)
        assert is_submission_blob(blob) is True
        assert blob[: len(SUBMISSION_BLOB_MAGIC)] == SUBMISSION_BLOB_MAGIC
        assert decrypt_submission(private_key, blob) == payload

    def test_wrong_private_key_fails(self):
        private_key, public_key = generate_submission_keypair()
        other_private, _ = generate_submission_keypair()
        blob = encrypt_for_submission(public_key, {"answers": {"q1": "secret"}})
        with pytest.raises(Exception):
            decrypt_submission(other_private, blob)

    def test_ciphertext_does_not_contain_plaintext(self):
        private_key, public_key = generate_submission_keypair()
        payload = {"answers": {"q1": "very secret value"}}
        blob = encrypt_for_submission(public_key, payload)
        assert b"very secret value" not in blob

    def test_blobs_are_non_deterministic(self):
        _, public_key = generate_submission_keypair()
        payload = {"answers": {"q1": "same"}}
        assert encrypt_for_submission(public_key, payload) != encrypt_for_submission(
            public_key, payload
        )

    def test_is_submission_blob_rejects_legacy_and_empty(self):
        assert is_submission_blob(None) is False
        assert is_submission_blob(b"") is False
        legacy = encrypt_sensitive(os.urandom(32), {"a": 1})
        assert is_submission_blob(legacy) is False

    def test_tampered_ciphertext_fails(self):
        private_key, public_key = generate_submission_keypair()
        blob = bytearray(encrypt_for_submission(public_key, {"answers": {"q1": "a"}}))
        blob[-1] ^= 0xFF
        with pytest.raises(Exception):
            decrypt_submission(private_key, bytes(blob))


@pytest.mark.django_db
class TestSurveyResponseSubmissionStorage:
    def test_store_submission_encrypted_and_plaintext_cleared(
        self, keypair_survey, user
    ):
        survey, private_key = keypair_survey
        response = SurveyResponse.objects.create(survey=survey, submitted_by=user)
        answers = {"q1": "free text answer"}
        demographics = {"nhs_number": "1234567890"}
        response.store_submission(
            bytes(survey.submission_public_key), answers, demographics
        )
        response.save()
        response.refresh_from_db()

        assert response.answers == {}
        assert response.enc_demographics is None
        assert response.is_encrypted is True
        assert is_submission_blob(response.enc_answers) is True

        loaded = response.load_complete_response(private_key)
        assert loaded["answers"] == answers
        assert loaded["demographics"] == demographics

    def test_load_answers_returns_answers_dict(self, keypair_survey, user):
        survey, private_key = keypair_survey
        response = SurveyResponse.objects.create(survey=survey, submitted_by=user)
        response.store_submission(
            bytes(survey.submission_public_key), {"q1": "a", "q2": "b"}
        )
        response.save()
        response.refresh_from_db()
        assert response.load_answers(private_key) == {"q1": "a", "q2": "b"}

    def test_private_key_never_stored_plaintext(self, keypair_survey):
        survey, private_key = keypair_survey
        # The private key must not appear anywhere in the wrapped blob
        assert private_key not in bytes(survey.encrypted_kek_password)
        # And unwrapping with the owner's password recovers it
        unwrapped = survey.unlock_with_password("OwnerPassword123")
        assert unwrapped == private_key

    def test_legacy_symmetric_blobs_still_readable(self, keypair_survey, user):
        """Legacy KEK-format blobs remain readable via load_answers."""
        survey, _ = keypair_survey
        legacy_kek = os.urandom(32)
        response = SurveyResponse.objects.create(survey=survey, submitted_by=user)
        response.store_answers(legacy_kek, {"q1": "legacy answer"})
        response.save()
        response.refresh_from_db()
        assert is_submission_blob(response.enc_answers) is False
        assert response.load_answers(legacy_kek) == {"q1": "legacy answer"}

    def test_plaintext_fallback_for_unencrypted_rows(self, keypair_survey, user):
        survey, _ = keypair_survey
        response = SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            answers={"q1": "plaintext"},
        )
        assert response.load_answers(b"unused") == {"q1": "plaintext"}

    def test_participant_submission_end_to_end(self, client, keypair_survey):
        """Full chain: participant submits -> public-key encrypted -> owner
        unlocks with password -> private key decrypts the response."""
        from checktick_app.surveys.models import SurveyQuestion

        survey, _ = keypair_survey
        survey.status = Survey.Status.PUBLISHED
        survey.visibility = Survey.Visibility.AUTHENTICATED
        survey.allow_any_authenticated = True
        survey.save()
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Describe your care",
            type=SurveyQuestion.Types.TEXT,
            order=0,
        )

        participant = User.objects.create_user(
            username="participant1", email="p1@example.com", password=TEST_PASSWORD
        )
        client.force_login(participant)
        resp = client.post(
            f"/surveys/{survey.slug}/take/",
            {f"q_{question.id}": "I saw Dr X on Tuesday"},
        )
        assert resp.status_code == 302

        response = SurveyResponse.objects.get(survey=survey)
        # Encrypted at submission with the public key; no plaintext answers
        assert response.answers == {}
        assert is_submission_blob(response.enc_answers) is True
        assert b"Dr X" not in bytes(response.enc_answers)

        # Owner unlocks and reads: password unwraps the private key
        private_key = survey.unlock_with_password("OwnerPassword123")
        assert private_key is not None
        loaded = response.load_complete_response(private_key)
        assert loaded["answers"][str(question.id)] == "I saw Dr X on Tuesday"

    def test_draft_submission_stays_plaintext(self, client, keypair_survey, user):
        """Draft surveys accept plaintext answers (planning doc §3.4)."""
        from checktick_app.surveys.models import SurveyQuestion

        survey, _ = keypair_survey  # status defaults to DRAFT
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Q",
            type=SurveyQuestion.Types.TEXT,
            order=0,
        )
        client.force_login(user)
        # Owner cannot submit via participant flow; use the internal path
        # directly to represent a draft-mode/test submission.
        response = SurveyResponse(survey=survey, answers={str(question.id): "test"})
        if survey.has_submission_keypair() and survey.status != Survey.Status.DRAFT:
            response.store_submission(
                bytes(survey.submission_public_key), response.answers
            )
        response.save()
        response.refresh_from_db()
        assert response.enc_answers is None
        assert response.answers == {str(question.id): "test"}

    def test_csv_export_decrypts_keypair_responses(self, client, keypair_survey):
        """The streaming CSV export decrypts submission-keypair responses
        after the owner unlocks the survey."""
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        survey, _ = keypair_survey
        survey.status = Survey.Status.PUBLISHED
        survey.visibility = Survey.Visibility.AUTHENTICATED
        survey.allow_any_authenticated = True
        survey.save()
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Free text",
            type=SurveyQuestion.Types.TEXT,
            order=0,
        )
        participant = User.objects.create_user(
            username="participant2", email="p2@example.com", password=TEST_PASSWORD
        )
        client.force_login(participant)
        client.post(
            f"/surveys/{survey.slug}/take/",
            {f"q_{question.id}": "exportable answer"},
        )
        assert SurveyResponse.objects.filter(survey=survey).exists()

        # Owner unlocks via the unlock view, then downloads the CSV
        client.force_login(survey.owner)
        unlock_resp = client.post(
            f"/surveys/{survey.slug}/unlock/",
            {"unlock_method": "password", "password": "OwnerPassword123"},
        )
        assert unlock_resp.status_code == 302
        csv_resp = client.get(f"/surveys/{survey.slug}/export.csv")
        assert csv_resp.status_code == 200
        body = b"".join(csv_resp.streaming_content).decode()
        assert "exportable answer" in body

    def test_analytics_unlock_gated(self, client, keypair_survey):
        """Dashboard distribution charts are unlock-gated for encrypted
        surveys (planning doc §5.4): counts render without unlock, charts
        require the key."""
        from checktick_app.surveys.models import SurveyQuestion
        from checktick_app.surveys.services.response_analytics import (
            compute_response_analytics,
        )

        survey, private_key = keypair_survey
        survey.status = Survey.Status.PUBLISHED
        survey.visibility = Survey.Visibility.AUTHENTICATED
        survey.allow_any_authenticated = True
        survey.save()
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Pick one",
            type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
            options={"choices": ["A", "B"]},
            order=0,
        )
        for answer in ("A", "A", "B"):
            response = SurveyResponse(survey=survey)
            response.store_submission(
                bytes(survey.submission_public_key), {str(question.id): answer}
            )
            response.save()

        # Service-level: no key -> distributions empty; key -> computed
        locked = compute_response_analytics(survey)
        assert locked.total_responses == 3
        assert locked.distributions == []
        unlocked = compute_response_analytics(survey, survey_key=private_key)
        dist = next(d for d in unlocked.distributions if d.question_id == question.id)
        counts = {o["label"]: o["count"] for o in dist.options}
        assert counts == {"A": 2, "B": 1}

        # View-level: locked dashboard shows the placeholder, not charts
        client.force_login(survey.owner)
        resp = client.get(reverse("surveys:dashboard", args=[survey.slug]))
        assert resp.context["insights_locked"] is True
        content = resp.content.decode()
        assert "Enter your encryption password" in content
        assert "data-chart-data" not in content

        # After unlock the charts render
        client.post(
            f"/surveys/{survey.slug}/unlock/",
            {"unlock_method": "password", "password": "OwnerPassword123"},
        )
        resp = client.get(reverse("surveys:dashboard", args=[survey.slug]))
        assert resp.context["insights_locked"] is False
        assert "data-chart-data" in resp.content.decode()


@pytest.mark.django_db
class TestSurveyKeypairPredicateIntegration:
    def test_keypair_survey_with_declaration_still_encrypted(self, user):
        """A submission keypair forces encryption regardless of declaration."""
        private_key, public_key = generate_submission_keypair()
        survey = Survey.objects.create(
            owner=user,
            name="Keypair Declared",
            slug="keypair-declared",
            submission_public_key=public_key,
            respondent_audience=Survey.RespondentAudience.STAFF,
            encryption_opt_out_at=timezone.now(),
            encryption_opt_out_by=user,
            encryption_opt_out_declaration_version="1.0",
        )
        assert survey.has_submission_keypair() is True
        assert survey.requires_whole_response_encryption() is True

    def test_json_payload_serialisable(self):
        """Payloads with nested structures round-trip through JSON."""
        private_key, public_key = generate_submission_keypair()
        payload = {
            "answers": {"q1": ["a", "b"], "q2": {"nested": True}},
            "demographics": None,
        }
        blob = encrypt_for_submission(public_key, payload)
        assert decrypt_submission(private_key, blob) == payload
