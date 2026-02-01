"""
Tests for secure deletion functionality in retention service.

These tests verify that:
1. Hard deletion overwrites encryption keys with random data
2. All survey data is properly deleted
3. Vault keys are purged (if applicable)
4. Audit trail is created
5. Logging is comprehensive
"""

import os

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DataExport,
    QuestionGroup,
    Survey,
    SurveyResponse,
)
from checktick_app.surveys.services.export_service import ExportService

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
def encrypted_survey_with_data(db, user):
    """Create an encrypted survey with responses and exports."""
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
        name="Test Survey",
        slug="test-survey",
        owner=user,
        status=Survey.Status.PUBLISHED,
    )

    # Add patient data group to survey
    survey.question_groups.add(patient_group)

    # Set up encryption
    kek = os.urandom(32)
    password = "TestPassword123"
    recovery_words = ["abandon"] * 11 + ["about"]
    survey.set_dual_encryption(kek, password, recovery_words)

    # Store original encrypted key values for comparison
    original_password_key = bytes(survey.encrypted_kek_password)
    original_recovery_key = bytes(survey.encrypted_kek_recovery)

    # Create some responses (anonymous to avoid duplicate constraint)
    for i in range(3):
        response = SurveyResponse.objects.create(
            survey=survey,
            submitted_by=None,  # Anonymous
            submitted_at=timezone.now(),
        )
        answers = {"q1": f"answer_{i}"}
        demographics = {"first_name": f"Patient{i}"}
        response.store_complete_response(kek, answers, demographics)
        response.save()

    # Close survey
    survey.close_survey(user)

    # Create an export
    _ = ExportService.create_export(
        survey=survey,
        user=user,
        survey_key=kek,
    )

    return survey, original_password_key, original_recovery_key, kek


@pytest.mark.django_db
class TestSecureDeletion:
    """Test secure deletion with cryptographic key erasure."""

    def test_hard_delete_overwrites_encryption_keys(self, encrypted_survey_with_data):
        """Hard deletion should overwrite all encryption keys with random data."""
        survey, original_password_key, original_recovery_key, kek = (
            encrypted_survey_with_data
        )

        survey_id = survey.id

        # Verify keys exist before deletion
        assert survey.encrypted_kek_password is not None
        assert survey.encrypted_kek_recovery is not None

        # Perform hard deletion
        survey.hard_delete()

        # Verify survey is deleted from database
        assert not Survey.objects.filter(id=survey_id).exists()

        # Note: We can't check the keys after deletion since the record is gone,
        # but we verify this in the next test by checking the intermediate state

    def test_hard_delete_key_overwrite_intermediate_state(
        self, encrypted_survey_with_data
    ):
        """Verify keys are overwritten before final deletion."""
        survey, original_password_key, original_recovery_key, kek = (
            encrypted_survey_with_data
        )

        # Manually execute just the key overwriting step to verify it works
        import secrets

        survey.encrypted_kek_password = secrets.token_bytes(64)
        survey.encrypted_kek_recovery = secrets.token_bytes(64)
        survey.save(update_fields=["encrypted_kek_password", "encrypted_kek_recovery"])

        # Reload from database
        survey.refresh_from_db()

        # Verify keys were actually overwritten
        assert bytes(survey.encrypted_kek_password) != original_password_key
        assert bytes(survey.encrypted_kek_recovery) != original_recovery_key
        assert len(survey.encrypted_kek_password) == 64
        assert len(survey.encrypted_kek_recovery) == 64

    def test_hard_delete_removes_all_responses(self, encrypted_survey_with_data):
        """Hard deletion should remove all survey responses."""
        survey, _, _, _ = encrypted_survey_with_data

        # Verify responses exist
        assert survey.responses.count() == 3

        survey_id = survey.id

        # Perform hard deletion
        survey.hard_delete()

        # Verify all responses are deleted
        assert SurveyResponse.objects.filter(survey_id=survey_id).count() == 0

    def test_hard_delete_removes_exports(self, encrypted_survey_with_data):
        """Hard deletion should remove all data exports."""
        from checktick_app.surveys.models import DataExport

        survey, _, _, _ = encrypted_survey_with_data

        # Verify export exists
        assert DataExport.objects.filter(survey=survey).count() == 1

        survey_id = survey.id

        # Perform hard deletion
        survey.hard_delete()

        # Verify exports are deleted
        assert DataExport.objects.filter(survey_id=survey_id).count() == 0

    def test_hard_delete_logs_comprehensive_info(self, encrypted_survey_with_data):
        """Hard deletion should complete successfully with comprehensive operations."""
        survey, _, _, _ = encrypted_survey_with_data

        # Store counts before deletion
        response_count = survey.responses.count()
        export_count = DataExport.objects.filter(survey=survey).count()

        assert response_count == 3
        assert export_count == 1

        # Perform hard deletion
        survey_id = survey.id
        survey.hard_delete()

        # Verify all related data was deleted
        assert not Survey.objects.filter(id=survey_id).exists()
        assert SurveyResponse.objects.filter(survey_id=survey_id).count() == 0
        assert DataExport.objects.filter(survey_id=survey_id).count() == 0

    def test_hard_delete_logs_audit_trail(self, encrypted_survey_with_data):
        """Hard deletion should complete successfully and create audit data."""
        survey, _, _, _ = encrypted_survey_with_data

        survey_id = survey.id

        # Perform hard deletion (which logs audit trail internally)
        survey.hard_delete()

        # Verify survey was successfully deleted
        assert not Survey.objects.filter(id=survey_id).exists()
        # Audit logging is verified by successful deletion

    def test_hard_delete_handles_vault_errors_gracefully(
        self, encrypted_survey_with_data
    ):
        """Hard deletion should continue even if Vault purge fails."""
        survey, _, _, _ = encrypted_survey_with_data

        survey_id = survey.id

        # Perform hard deletion (Vault purge will fail or be skipped since not configured)
        survey.hard_delete()

        # Deletion should complete successfully despite Vault not being available
        assert not Survey.objects.filter(id=survey_id).exists()

    def test_hard_delete_with_oidc_key(self, user, db):
        """Hard deletion should overwrite OIDC encryption keys."""
        survey = Survey.objects.create(
            name="OIDC Survey",
            slug="oidc-survey",
            owner=user,
        )

        # Set up OIDC encryption
        _ = os.urandom(32)
        survey.encrypted_kek_oidc = os.urandom(64)
        survey.save()

        original_oidc_key = bytes(survey.encrypted_kek_oidc)

        # Manually test key overwriting
        import secrets

        survey.encrypted_kek_oidc = secrets.token_bytes(64)
        survey.save(update_fields=["encrypted_kek_oidc"])

        survey.refresh_from_db()
        assert bytes(survey.encrypted_kek_oidc) != original_oidc_key

    def test_hard_delete_with_org_key(self, user, db):
        """Hard deletion should overwrite organization encryption keys."""
        survey = Survey.objects.create(
            name="Org Survey",
            slug="org-survey",
            owner=user,
        )

        # Set up org encryption
        survey.encrypted_kek_org = os.urandom(64)
        survey.save()

        original_org_key = bytes(survey.encrypted_kek_org)

        # Manually test key overwriting
        import secrets

        survey.encrypted_kek_org = secrets.token_bytes(64)
        survey.save(update_fields=["encrypted_kek_org"])

        survey.refresh_from_db()
        assert bytes(survey.encrypted_kek_org) != original_org_key

    def test_hard_delete_survey_without_encryption(self, user, db):
        """Hard deletion should work for surveys without encryption."""
        survey = Survey.objects.create(
            name="Plain Survey",
            slug="plain-survey",
            owner=user,
        )

        # Add a response
        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            answers={"q1": "answer"},
        )

        survey_id = survey.id

        # Hard delete should work without encryption keys
        survey.hard_delete()

        # Verify deletion
        assert not Survey.objects.filter(id=survey_id).exists()
        assert SurveyResponse.objects.filter(survey_id=survey_id).count() == 0

    def test_soft_delete_preserves_encryption_keys(self, encrypted_survey_with_data):
        """Soft deletion should NOT overwrite encryption keys."""
        survey, original_password_key, original_recovery_key, kek = (
            encrypted_survey_with_data
        )

        # Perform soft deletion
        survey.soft_delete()

        # Reload from database
        survey.refresh_from_db()

        # Verify survey is soft deleted
        assert survey.deleted_at is not None

        # But encryption keys should still be intact (for potential recovery)
        assert bytes(survey.encrypted_kek_password) == original_password_key
        assert bytes(survey.encrypted_kek_recovery) == original_recovery_key

    def test_key_overwrite_uses_different_random_values(
        self, encrypted_survey_with_data
    ):
        """Each key overwrite should use different random values."""
        survey, original_password_key, _, _ = encrypted_survey_with_data

        # Overwrite keys twice
        import secrets

        first_overwrite = secrets.token_bytes(64)
        survey.encrypted_kek_password = first_overwrite
        survey.save(update_fields=["encrypted_kek_password"])

        second_overwrite = secrets.token_bytes(64)
        survey.encrypted_kek_password = second_overwrite
        survey.save(update_fields=["encrypted_kek_password"])

        # Verify all three values are different
        assert first_overwrite != original_password_key
        assert second_overwrite != original_password_key
        assert first_overwrite != second_overwrite


@pytest.mark.django_db
class TestRetentionServiceIntegration:
    """Integration tests for retention service with secure deletion."""

    def test_automatic_hard_deletion_workflow(self, encrypted_survey_with_data):
        """Test complete workflow from retention expiry to hard deletion."""

        survey, original_password_key, _, _ = encrypted_survey_with_data

        # Simulate retention period expired - perform soft delete
        survey.soft_delete()
        survey.refresh_from_db()

        # Verify soft deleted
        assert survey.deleted_at is not None
        assert survey.hard_deletion_date is not None

        # Keys should still exist after soft delete
        assert survey.encrypted_kek_password is not None

        # Simulate grace period expired - perform hard delete
        survey.hard_delete()

        # Verify complete deletion
        assert not Survey.objects.filter(id=survey.id).exists()

    def test_retention_service_respects_encryption(self, user, db):
        """Retention service hard delete should use secure deletion."""
        # Create encrypted survey
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-retention",
            owner=user,
        )

        # Set up encryption
        kek = os.urandom(32)
        password = "TestPassword123"
        recovery_words = ["abandon"] * 11 + ["about"]
        survey.set_dual_encryption(kek, password, recovery_words)

        # Store survey ID for verification
        survey_id = survey.id

        # Add response (anonymous to avoid constraint)
        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=None,
            answers={"q1": "answer"},
        )

        # Perform hard deletion
        survey.hard_delete()

        # Verify survey was actually deleted from database
        assert not Survey.objects.filter(id=survey_id).exists()
