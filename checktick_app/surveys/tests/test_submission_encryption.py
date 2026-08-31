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


@pytest.fixture
def keypair_survey(db, user):
    """Survey with a submission keypair; private key wrapped with password."""
    private_key, public_key = generate_submission_keypair()
    survey = Survey.objects.create(
        owner=user,
        name="Keypair Survey",
        slug="keypair-survey",
        submission_public_key=public_key,
        encrypted_kek_password=encrypt_kek_with_passphrase(
            private_key, "OwnerPassword123"
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
