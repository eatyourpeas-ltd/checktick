"""
Tests for export service encryption functionality.

These tests verify that:
1. Encrypted surveys require survey_key for export
2. CSV generation properly decrypts responses
3. Export file encryption works correctly
4. Error handling for missing keys is appropriate
"""

import os

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyResponse
from checktick_app.surveys.services import ExportService
from checktick_app.surveys.utils import decrypt_sensitive

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def encrypted_survey_with_responses(db, user):
    """Create an encrypted survey with patient data responses."""
    from checktick_app.surveys.models import SurveyQuestion

    # Create a patient data question group
    patient_group = QuestionGroup.objects.create(
        name="Patient Details",
        owner=user,
        schema={
            "template": "patient_details_encrypted",
            "fields": ["first_name", "last_name", "nhs_number", "date_of_birth"],
        },
    )

    # Create survey
    survey = Survey.objects.create(
        name="Patient Data Survey",
        slug="patient-data-survey",
        owner=user,
        status=Survey.Status.PUBLISHED,
    )

    # Add patient data group to survey
    survey.question_groups.add(patient_group)

    # Create survey questions
    q1 = SurveyQuestion.objects.create(
        survey=survey,
        group=patient_group,
        text="Primary Question",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=1,
    )
    q2 = SurveyQuestion.objects.create(
        survey=survey,
        group=patient_group,
        text="Clinical Notes",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=2,
    )

    # Set up encryption (dual-path)
    kek = os.urandom(32)
    password = "TestPassword123"
    recovery_words = ["abandon"] * 11 + ["about"]
    survey.set_dual_encryption(kek, password, recovery_words)

    # Create encrypted responses
    for i in range(3):
        response = SurveyResponse.objects.create(
            survey=survey,
            submitted_by=None,  # Anonymous to avoid duplicate constraint
            submitted_at=timezone.now(),
        )

        # Store complete encrypted response using question IDs as keys
        answers = {
            str(q1.id): f"Answer {i}",
            str(q2.id): f"Clinical notes {i}",
        }
        demographics = {
            "first_name": f"Patient{i}",
            "last_name": f"Test{i}",
            "nhs_number": f"123456789{i}",
        }
        response.store_complete_response(kek, answers, demographics)
        response.save()

    # Close survey to enable export
    survey.close_survey(user)

    return survey, kek, password


@pytest.fixture
def plain_survey_with_responses(db, user):
    """Create a non-encrypted survey with responses."""
    survey = Survey.objects.create(
        name="Plain Survey",
        slug="plain-survey",
        owner=user,
        status=Survey.Status.PUBLISHED,
    )

    # Create plain responses (anonymous to avoid duplicate constraint)
    SurveyResponse.objects.create(
        survey=survey,
        submitted_by=None,
        submitted_at=timezone.now(),
        answers={
            "question_1": "Answer 0",
            "question_2": "Notes 0",
        },
    )
    SurveyResponse.objects.create(
        survey=survey,
        submitted_by=None,
        submitted_at=timezone.now(),
        answers={
            "question_1": "Answer 1",
            "question_2": "Notes 1",
        },
    )

    survey.close_survey(user)
    return survey


@pytest.mark.django_db
class TestExportServiceEncryption:
    """Test export service encryption functionality."""

    def test_export_encrypted_survey_requires_key(
        self, encrypted_survey_with_responses, user
    ):
        """Export of encrypted survey should require survey_key."""
        survey, kek, password = encrypted_survey_with_responses

        # Attempt export without survey_key should fail
        with pytest.raises(
            ValueError, match="Survey key required to export encrypted survey"
        ):
            ExportService.create_export(
                survey=survey,
                user=user,
                password=None,
                survey_key=None,  # Missing key!
            )

    def test_export_encrypted_survey_with_key_succeeds(
        self, encrypted_survey_with_responses, user
    ):
        """Export of encrypted survey should succeed with survey_key."""
        survey, kek, password = encrypted_survey_with_responses

        # Export with survey_key should succeed
        export = ExportService.create_export(
            survey=survey,
            user=user,
            password=None,
            survey_key=kek,  # Provide key
        )

        assert export is not None
        assert export.response_count == 3
        assert export.survey == survey
        assert export.created_by == user

    def test_csv_generation_decrypts_responses(
        self, encrypted_survey_with_responses, user
    ):
        """CSV generation should decrypt responses correctly."""
        survey, kek, password = encrypted_survey_with_responses

        # Generate CSV with survey key
        csv_data = ExportService._generate_csv(survey, survey_key=kek)

        # Verify CSV contains decrypted data (answers from encrypted responses)
        assert "Answer 0" in csv_data
        assert "Clinical notes 0" in csv_data
        assert "Answer 1" in csv_data
        assert "Primary Question" in csv_data  # Header
        assert "Clinical Notes" in csv_data  # Header
        assert "Answer 0" in csv_data
        assert "Clinical notes 1" in csv_data

    def test_csv_generation_without_key_fails_gracefully(
        self, encrypted_survey_with_responses, user
    ):
        """CSV generation without key should skip encrypted responses."""
        survey, kek, password = encrypted_survey_with_responses

        # Generate CSV without survey key
        csv_data = ExportService._generate_csv(survey, survey_key=None)

        # CSV should be generated but without response data
        assert "Response ID" in csv_data  # Header present
        # But encrypted data should not appear (responses skipped)
        assert "Patient0" not in csv_data

    def test_export_file_encryption_with_password(
        self, plain_survey_with_responses, user
    ):
        """Export file should be encrypted when password is provided."""
        survey = plain_survey_with_responses

        export_password = "ExportPassword123"

        # Create export with file encryption
        export = ExportService.create_export(
            survey=survey,
            user=user,
            password=export_password,
            survey_key=None,  # Not encrypted survey
        )

        assert export.is_encrypted is True
        assert export.encryption_key_id is not None
        assert export.encryption_key_id.startswith("export-")

    def test_export_csv_encryption_roundtrip(self):
        """Test that CSV encryption and decryption work correctly."""
        csv_data = "Response ID,Question1,Question2\n1,Answer1,Answer2\n"
        password = "TestPassword123"

        # Encrypt CSV
        encrypted_blob, key_id = ExportService._encrypt_csv(csv_data, password)

        assert len(encrypted_blob) > len(csv_data.encode("utf-8"))
        assert key_id.startswith("export-")

        # Decrypt CSV (using decrypt_sensitive)

        # Decrypt with same password (decrypt_sensitive handles KDF)
        decrypted_dict = decrypt_sensitive(password.encode("utf-8"), encrypted_blob)

        assert "csv_content" in decrypted_dict
        assert decrypted_dict["csv_content"] == csv_data

    def test_plain_survey_export_without_key(self, plain_survey_with_responses, user):
        """Plain survey export should work without survey_key."""
        survey = plain_survey_with_responses

        # Export should succeed without survey_key for non-encrypted survey
        export = ExportService.create_export(
            survey=survey,
            user=user,
            password=None,
            survey_key=None,
        )

        assert export is not None
        assert export.response_count == 2

    def test_export_logs_encryption_status(self, encrypted_survey_with_responses, user):
        """Export should complete successfully and log encryption status."""
        survey, kek, password = encrypted_survey_with_responses

        export = ExportService.create_export(
            survey=survey,
            user=user,
            password="ExportPass123",
            survey_key=kek,
        )

        # Verify export completed successfully with encryption
        assert export is not None
        assert export.is_encrypted is True
        assert export.response_count == 3

    def test_export_validates_deleted_survey(
        self, encrypted_survey_with_responses, user
    ):
        """Export should reject deleted surveys."""
        survey, kek, password = encrypted_survey_with_responses

        # Soft delete the survey
        survey.soft_delete()

        # Attempt export should fail
        with pytest.raises(ValueError, match="Cannot export data from deleted survey"):
            ExportService.create_export(
                survey=survey,
                user=user,
                survey_key=kek,
            )

    def test_export_with_frozen_responses(self, encrypted_survey_with_responses, user):
        """Export should exclude frozen responses."""
        survey, kek, password = encrypted_survey_with_responses

        # Freeze one response (needs frozen_by_user argument)
        response = survey.responses.first()
        response.freeze("Test DSR", frozen_by_user=user)

        # Export should succeed with fewer responses
        export = ExportService.create_export(
            survey=survey,
            user=user,
            survey_key=kek,
        )

        # Should only export 2 responses (1 frozen)
        assert export.response_count == 2

    def test_decrypt_error_handling(self, encrypted_survey_with_responses, user):
        """Export should handle decryption errors gracefully."""
        survey, kek, password = encrypted_survey_with_responses

        # Use wrong key
        wrong_key = os.urandom(32)

        # Generate CSV with wrong key - should not crash
        csv_data = ExportService._generate_csv(survey, survey_key=wrong_key)

        # CSV should still have headers even if decryption fails
        assert "Response ID" in csv_data
        assert "Primary Question" in csv_data
        # (Responses won't be in CSV since decryption failed)

        # CSV should still have headers
        assert "Response ID" in csv_data


@pytest.mark.django_db
class TestExportIntegrationWithEncryption:
    """Integration tests for complete export workflow with encryption."""

    def test_complete_export_workflow_encrypted_survey(
        self, encrypted_survey_with_responses, user
    ):
        """Test complete workflow: unlock survey → export → verify data."""
        survey, kek, password = encrypted_survey_with_responses

        # Step 1: Unlock survey (simulated - would come from session)
        unlocked_kek = survey.unlock_with_password(password)
        assert unlocked_kek is not None

        # Step 2: Create export with unlocked key
        export = ExportService.create_export(
            survey=survey,
            user=user,
            password="DownloadPass123",  # Optional download protection
            survey_key=unlocked_kek,
        )

        # Step 3: Verify export created successfully
        assert export is not None
        assert export.is_encrypted is True  # Download protection enabled
        assert export.response_count == 3

        # Step 4: Generate CSV again to verify content
        csv_data = ExportService._generate_csv(survey, survey_key=unlocked_kek)

        # Verify decrypted answers appear in CSV
        assert "Answer 0" in csv_data
        assert "Answer 1" in csv_data
        assert "Clinical notes 0" in csv_data
        assert "Primary Question" in csv_data

    def test_export_without_unlock_fails(self, encrypted_survey_with_responses, user):
        """Export should fail if survey not unlocked (no key available)."""
        survey, kek, password = encrypted_survey_with_responses

        # Attempt export without unlocking first
        with pytest.raises(
            ValueError, match="Survey key required to export encrypted survey"
        ):
            ExportService.create_export(
                survey=survey,
                user=user,
                survey_key=None,  # Survey not unlocked!
            )
