"""Tests for whole-response encryption for patient data surveys."""

import os

from django.contrib.auth import get_user_model
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyResponse

User = get_user_model()

TEST_PASSWORD = "x"  # noqa: S105


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser", email="test@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def patient_group(db, user):
    """Create a question group with patient data template."""
    return QuestionGroup.objects.create(
        name="Patient Details",
        owner=user,
        schema={
            "template": "patient_details_encrypted",
            "fields": ["first_name", "last_name", "nhs_number", "date_of_birth"],
        },
    )


@pytest.fixture
def non_patient_group(db, user):
    """Create a question group without patient data template."""
    return QuestionGroup.objects.create(
        name="General Questions",
        owner=user,
        schema={
            "fields": [
                {"key": "q1", "label": "Question 1", "type": "text"},
                {"key": "q2", "label": "Question 2", "type": "text"},
            ]
        },
    )


@pytest.fixture
def survey_with_patient_data(db, user, patient_group):
    """Create a survey that collects patient data."""
    survey = Survey.objects.create(
        owner=user,
        name="Patient Survey",
        slug="patient-survey",
    )
    survey.question_groups.add(patient_group)
    return survey


@pytest.fixture
def survey_without_patient_data(db, user, non_patient_group):
    """Create a survey that does NOT collect patient data."""
    survey = Survey.objects.create(
        owner=user,
        name="General Survey",
        slug="general-survey",
    )
    survey.question_groups.add(non_patient_group)
    return survey


@pytest.mark.django_db
class TestSurveyPatientDataDetection:
    """Test that surveys correctly detect patient data collection."""

    def test_survey_with_patient_data_detects_correctly(self, survey_with_patient_data):
        """Survey with patient details template should detect patient data."""
        assert survey_with_patient_data.collects_patient_data() is True

    def test_survey_without_patient_data_detects_correctly(
        self, survey_without_patient_data
    ):
        """Survey without patient details template should not detect patient data."""
        assert survey_without_patient_data.collects_patient_data() is False

    def test_requires_whole_response_encryption(self, survey_with_patient_data):
        """Patient data surveys should require whole response encryption."""
        assert survey_with_patient_data.requires_whole_response_encryption() is True

    def test_non_patient_survey_no_whole_encryption(self, survey_without_patient_data):
        """Non-patient surveys should not require whole response encryption."""
        assert survey_without_patient_data.requires_whole_response_encryption() is False


@pytest.mark.django_db
class TestSSOPassphraseRequirement:
    """Test SSO passphrase requirement for patient data surveys."""

    def test_default_requires_passphrase_for_patient_data(
        self, survey_with_patient_data
    ):
        """By default, patient data surveys require passphrase for SSO users."""
        assert survey_with_patient_data.require_passphrase_for_patient_data is True
        assert survey_with_patient_data.sso_user_needs_passphrase() is True

    def test_can_disable_passphrase_requirement(self, survey_with_patient_data):
        """Organizations can disable passphrase requirement if security policy permits."""
        survey_with_patient_data.require_passphrase_for_patient_data = False
        survey_with_patient_data.save()
        assert survey_with_patient_data.sso_user_needs_passphrase() is False

    def test_non_patient_survey_no_passphrase_requirement(
        self, survey_without_patient_data
    ):
        """Non-patient surveys don't require passphrase for SSO users."""
        assert survey_without_patient_data.sso_user_needs_passphrase() is False


@pytest.mark.django_db
class TestWholeResponseEncryption:
    """Test encrypting and decrypting complete survey responses."""

    def test_store_and_load_answers(self, survey_with_patient_data, user):
        """Test basic store/load of encrypted answers."""
        survey_key = os.urandom(32)  # Random 32-byte KEK

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
        )

        answers = {
            "q1_chest_pain": "moderate",
            "q2_duration": "5 days",
            "q3_notes": "Patient reports intermittent pain",
        }

        # Store encrypted answers
        response.store_answers(survey_key, answers)
        response.save()

        # Reload from database
        response.refresh_from_db()

        # Load decrypted answers
        loaded = response.load_answers(survey_key)

        assert loaded == answers
        # Plaintext answers should be cleared
        assert response.answers == {}

    def test_store_complete_response_with_demographics(
        self, survey_with_patient_data, user
    ):
        """Test storing complete response with answers AND demographics."""
        survey_key = os.urandom(32)

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
        )

        answers = {
            "q1": "yes",
            "q2": "moderate",
            "q3_notes": "Clinical observation notes here",
        }
        demographics = {
            "first_name": "John",
            "last_name": "Smith",
            "nhs_number": "1234567890",
            "date_of_birth": "1980-01-15",
        }

        # Store complete encrypted response
        response.store_complete_response(survey_key, answers, demographics)
        response.save()

        # Reload from database
        response.refresh_from_db()

        # Load complete response
        loaded = response.load_complete_response(survey_key)

        assert loaded["answers"] == answers
        assert loaded["demographics"] == demographics
        # Both plaintext fields should be cleared
        assert response.answers == {}
        assert response.enc_demographics is None

    def test_load_complete_response_legacy_format(self, survey_with_patient_data, user):
        """Test loading legacy format (separate enc_demographics + answers)."""
        survey_key = os.urandom(32)

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
        )

        # Set up legacy format
        response.answers = {"q1": "answer1", "q2": "answer2"}
        demographics = {"first_name": "Jane", "nhs_number": "9876543210"}
        response.store_demographics(survey_key, demographics)
        response.save()

        response.refresh_from_db()

        # load_complete_response should handle legacy format
        loaded = response.load_complete_response(survey_key)

        assert loaded["answers"] == {"q1": "answer1", "q2": "answer2"}
        assert loaded["demographics"] == demographics

    def test_is_encrypted_property(self, survey_with_patient_data, user):
        """Test the is_encrypted property correctly reports encryption status."""
        survey_key = os.urandom(32)

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
        )

        # Initially not encrypted
        assert response.is_encrypted is False

        # After storing encrypted answers
        response.store_answers(survey_key, {"q1": "test"})
        assert response.is_encrypted is True

    def test_wrong_key_fails_to_decrypt(self, survey_with_patient_data, user):
        """Test that wrong key fails to decrypt (authenticated encryption)."""
        correct_key = os.urandom(32)
        wrong_key = os.urandom(32)

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
        )

        response.store_answers(correct_key, {"q1": "secret data"})
        response.save()
        response.refresh_from_db()

        # Attempting to decrypt with wrong key should fail
        with pytest.raises(Exception):  # AES-GCM raises InvalidTag
            response.load_answers(wrong_key)


@pytest.mark.django_db
class TestBackwardsCompatibility:
    """Test backwards compatibility with existing encrypted data."""

    def test_non_patient_survey_requires_encryption(
        self, survey_without_patient_data, user
    ):
        """All surveys (including non-patient) now require encryption setup.

        Non-patient surveys don't use whole-response encryption, but they
        still need encryption to be configured before publishing.
        """
        # Survey should not require whole-response encryption
        assert survey_without_patient_data.requires_whole_response_encryption() is False

        # But it should still require *some* form of encryption setup before publishing
        # (This is enforced in the publish workflow, not in the response storage)
        # Non-patient surveys can store answers in plaintext during testing/draft phase,
        # but must have encryption configured (encrypted_kek_*) before going live

        response = SurveyResponse.objects.create(
            survey=survey_without_patient_data,
            submitted_by=user,
            answers={"q1": "answer1", "q2": "answer2"},
        )

        response.refresh_from_db()

        # During draft phase, answers can be in plaintext
        loaded = response.load_answers(b"dummy_key_not_used")
        assert loaded == {"q1": "answer1", "q2": "answer2"}
        assert response.enc_answers is None

    def test_legacy_demographics_only_encryption(self, survey_with_patient_data, user):
        """Test that legacy demographics-only encryption still works."""
        survey_key = os.urandom(32)

        response = SurveyResponse.objects.create(
            survey=survey_with_patient_data,
            submitted_by=user,
            answers={"q1": "plaintext answer"},  # Legacy: answers in plaintext
        )

        # Legacy: only demographics encrypted
        demographics = {"nhs_number": "1234567890"}
        response.store_demographics(survey_key, demographics)
        response.save()

        response.refresh_from_db()

        # Legacy methods should still work
        assert response.load_demographics(survey_key) == demographics
        # Plaintext answers should be accessible
        assert response.answers == {"q1": "plaintext answer"}
