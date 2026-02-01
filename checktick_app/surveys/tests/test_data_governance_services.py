"""
Tests for data governance services: ExportService and RetentionService.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DataRetentionExtension,
    LegalHold,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.services import ExportService, RetentionService

TEST_PASSWORD = "x"


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password=TEST_PASSWORD)


@pytest.fixture
def org(db, user):
    return Organization.objects.create(name="Test Org", owner=user)


@pytest.fixture
def survey(db, user, org):
    return Survey.objects.create(
        owner=user,
        organization=org,
        name="Test Survey",
        slug="test-survey",
    )


@pytest.fixture
def survey_with_responses(db, survey, user):
    """Survey with question group, questions, and responses."""
    # Create question group
    group = QuestionGroup.objects.create(
        name="Demographics",
        owner=user,
    )
    group.surveys.add(survey)

    # Create questions
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Name",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Age",
        type=SurveyQuestion.Types.TEXT,
        order=1,
    )

    # Create responses
    SurveyResponse.objects.create(
        survey=survey,
        answers={"name": "John", "age": "30"},
    )
    SurveyResponse.objects.create(
        survey=survey,
        answers={"name": "Jane", "age": "25"},
    )

    return survey


@pytest.fixture
def closed_survey(db, user, org):
    """Survey that has been closed."""
    survey = Survey.objects.create(
        owner=user,
        organization=org,
        name="Closed Survey",
        slug="closed-survey",
    )
    survey.close_survey(user)
    return survey


# ============================================================================
# ExportService Tests
# ============================================================================


class TestExportService:
    """Test data export service."""

    def test_create_export_generates_token(self, survey_with_responses, user):
        """Creating export should generate download token."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        assert export.download_token is not None
        assert len(export.download_token) > 0
        assert export.survey == survey_with_responses
        assert export.created_by == user

    def test_create_export_sets_expiry(self, survey_with_responses, user):
        """Export should have 7-day expiry by default."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        # Expiry should be ~7 days from now
        expected_expiry = timezone.now() + timedelta(days=7)
        time_diff = abs(
            (export.download_url_expires_at - expected_expiry).total_seconds()
        )
        assert time_diff < 60  # Within 1 minute

    def test_create_export_counts_responses(self, survey_with_responses, user):
        """Export should record correct response count."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        assert export.response_count == 2

    def test_create_export_fails_for_deleted_survey(self, survey, user):
        """Cannot export from deleted survey."""
        survey.soft_delete()

        with pytest.raises(ValueError, match="deleted survey"):
            ExportService.create_export(survey, user)

    def test_create_export_fails_for_no_responses(self, survey, user):
        """Cannot export survey with no responses."""
        with pytest.raises(ValueError, match="no responses"):
            ExportService.create_export(survey, user)

    def test_create_export_with_password_encrypts(self, survey_with_responses, user):
        """Export with password should be encrypted."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(
                survey_with_responses, user, password=TEST_PASSWORD
            )

        assert export.is_encrypted is True
        assert export.encryption_key_id is not None

    def test_create_export_without_password_unencrypted(
        self, survey_with_responses, user
    ):
        """Export without password should not be encrypted."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        assert export.is_encrypted is False
        assert export.encryption_key_id is None

    def test_get_download_url(self, survey_with_responses, user):
        """Should generate download URL from export."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        url = ExportService.get_download_url(export)

        assert export.download_token in url
        assert str(export.id) in url

    def test_get_download_url_fails_for_expired(self, survey_with_responses, user):
        """Should raise error for expired download URL."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        # Set expiry to past
        export.download_url_expires_at = timezone.now() - timedelta(days=1)
        export.save()

        with pytest.raises(ValueError, match="expired"):
            ExportService.get_download_url(export)

    def test_validate_download_token(self, survey_with_responses, user):
        """Should validate download token correctly."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        # Valid token
        assert (
            ExportService.validate_download_token(export, export.download_token) is True
        )

        # Invalid token
        assert ExportService.validate_download_token(export, "wrong-token") is False

    def test_validate_download_token_fails_for_expired(
        self, survey_with_responses, user
    ):
        """Expired exports should fail token validation."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        # Set expiry to past
        export.download_url_expires_at = timezone.now() - timedelta(days=1)
        export.save()

        # Even correct token should fail
        assert (
            ExportService.validate_download_token(export, export.download_token)
            is False
        )

    def test_record_download(self, survey_with_responses, user):
        """Should track download count and timestamp."""
        with patch.object(ExportService, "_generate_csv", return_value="mock,csv"):
            export = ExportService.create_export(survey_with_responses, user)

        assert export.downloaded_at is None
        assert export.download_count == 0

        ExportService.record_download(export)
        export.refresh_from_db()

        assert export.downloaded_at is not None
        assert export.download_count == 1


# ============================================================================
# RetentionService Tests
# ============================================================================


class TestRetentionService:
    """Test retention period management service."""

    def test_calculate_deletion_date(self):
        """Should calculate deletion date correctly."""
        closed_at = timezone.now()

        deletion_date = RetentionService.calculate_deletion_date(closed_at, 6)

        expected = closed_at + timedelta(days=180)  # 6 * 30
        assert deletion_date == expected

    def test_get_surveys_pending_deletion_warning(self, closed_survey):
        """Should find surveys needing deletion warnings."""
        # Set deletion date to 30 days from now
        closed_survey.deletion_date = timezone.now() + timedelta(days=30)
        closed_survey.save()

        surveys = RetentionService.get_surveys_pending_deletion_warning(30)

        assert closed_survey in surveys

    def test_get_surveys_pending_warning_excludes_legal_hold(self, closed_survey, user):
        """Should exclude surveys with active legal holds."""
        # Set deletion date to 7 days from now
        closed_survey.deletion_date = timezone.now() + timedelta(days=7)
        closed_survey.save()

        # Place legal hold
        LegalHold.objects.create(
            survey=closed_survey,
            placed_by=user,
            reason="Investigation",
            authority="Court",
        )

        surveys = RetentionService.get_surveys_pending_deletion_warning(7)

        assert closed_survey not in surveys

    def test_extend_retention_creates_audit_record(self, closed_survey, user):
        """Extending retention should create audit trail."""
        previous_date = closed_survey.deletion_date

        RetentionService.extend_retention(closed_survey, 3, user, "Business need")

        # Should have created extension record
        extensions = DataRetentionExtension.objects.filter(survey=closed_survey)
        assert extensions.count() == 1

        extension = extensions.first()
        assert extension.previous_deletion_date == previous_date
        assert extension.months_extended == 3
        assert extension.reason == "Business need"

    def test_extend_retention_fails_for_unclosed_survey(self, survey, user):
        """Cannot extend retention for unclosed survey."""
        with pytest.raises(ValueError, match="unclosed"):
            RetentionService.extend_retention(survey, 3, user, "Too early")

    def test_extend_retention_fails_beyond_24_months(self, closed_survey, user):
        """Cannot extend beyond 24 months total."""
        # Set to 22 months already
        closed_survey.retention_months = 22
        closed_survey.save()

        with pytest.raises(ValueError, match="24 months"):
            RetentionService.extend_retention(closed_survey, 6, user, "Too much")

    def test_can_survey_be_deleted(self, closed_survey):
        """Should correctly identify if survey can be deleted."""
        can_delete, reason = RetentionService.can_survey_be_deleted(closed_survey)
        assert can_delete is True
        assert reason is None

    def test_can_survey_be_deleted_with_legal_hold(self, closed_survey, user):
        """Survey with legal hold cannot be deleted."""
        LegalHold.objects.create(
            survey=closed_survey,
            placed_by=user,
            reason="Investigation",
            authority="Court",
        )

        can_delete, reason = RetentionService.can_survey_be_deleted(closed_survey)
        assert can_delete is False
        assert "legal hold" in reason

    def test_can_survey_be_deleted_already_deleted(self, survey):
        """Already deleted survey cannot be deleted again."""
        survey.soft_delete()

        can_delete, reason = RetentionService.can_survey_be_deleted(survey)
        assert can_delete is False
        assert "already deleted" in reason

    def test_cancel_soft_deletion(self, survey, user):
        """Should be able to cancel soft deletion."""
        survey.soft_delete()
        assert survey.deleted_at is not None

        RetentionService.cancel_soft_deletion(survey, user)
        survey.refresh_from_db()

        assert survey.deleted_at is None
        assert survey.hard_deletion_date is None

    def test_cancel_soft_deletion_fails_for_undeleted(self, survey, user):
        """Cannot cancel deletion for survey that's not deleted."""
        with pytest.raises(ValueError, match="not deleted"):
            RetentionService.cancel_soft_deletion(survey, user)

    def test_get_retention_extension_history(self, closed_survey, user):
        """Should return all extensions for a survey."""
        # Create multiple extensions
        RetentionService.extend_retention(closed_survey, 3, user, "First")
        RetentionService.extend_retention(closed_survey, 3, user, "Second")

        history = RetentionService.get_retention_extension_history(closed_survey)

        assert len(history) == 2
        # Should be ordered by most recent first
        assert history[0].reason == "Second"
        assert history[1].reason == "First"

    def test_process_automatic_deletions_soft_deletes(self, closed_survey):
        """Should soft delete surveys past their deletion date."""
        # Set deletion date to yesterday
        closed_survey.deletion_date = timezone.now() - timedelta(days=1)
        closed_survey.save()

        stats = RetentionService.process_automatic_deletions()

        assert stats["soft_deleted"] == 1
        assert stats["hard_deleted"] == 0

        closed_survey.refresh_from_db()
        assert closed_survey.deleted_at is not None

    def test_process_automatic_deletions_skips_legal_hold(self, closed_survey, user):
        """Should skip surveys with active legal holds."""
        # Set deletion date to yesterday
        closed_survey.deletion_date = timezone.now() - timedelta(days=1)
        closed_survey.save()

        # Place legal hold
        LegalHold.objects.create(
            survey=closed_survey,
            placed_by=user,
            reason="Investigation",
            authority="Court",
        )

        stats = RetentionService.process_automatic_deletions()

        assert stats["soft_deleted"] == 0
        assert stats["skipped_legal_hold"] == 1

        closed_survey.refresh_from_db()
        assert closed_survey.deleted_at is None


# ============================================================================
# Integration Tests
# ============================================================================


class TestDataGovernanceIntegration:
    """Integration tests for complete data governance workflows."""

    def test_complete_export_workflow(self, survey_with_responses, user):
        """Test complete export from creation to download."""
        # 1. Create export
        with patch.object(
            ExportService, "_generate_csv", return_value="test,data\n1,2"
        ):
            export = ExportService.create_export(survey_with_responses, user)

        # 2. Get download URL
        url = ExportService.get_download_url(export)
        assert url is not None

        # 3. Validate token
        is_valid = ExportService.validate_download_token(export, export.download_token)
        assert is_valid is True

        # 4. Record download
        ExportService.record_download(export)
        export.refresh_from_db()
        assert export.download_count == 1

    def test_complete_retention_workflow(self, closed_survey, user):
        """Test complete retention management workflow."""
        # 1. Survey is closed with default 6-month retention
        assert closed_survey.retention_months == 6
        assert closed_survey.deletion_date is not None

        # 2. Check if can extend
        assert closed_survey.can_extend_retention is True

        # 3. Extend retention
        RetentionService.extend_retention(closed_survey, 6, user, "Need more time")
        closed_survey.refresh_from_db()
        assert closed_survey.retention_months == 12

        # 4. Check extension history
        history = RetentionService.get_retention_extension_history(closed_survey)
        assert len(history) == 1

        # 5. Check deletion eligibility
        can_delete, _ = RetentionService.can_survey_be_deleted(closed_survey)
        assert can_delete is True

    def test_legal_hold_blocks_deletion(self, closed_survey, user):
        """Test that legal hold prevents automatic deletion."""
        # 1. Set survey to be deleted
        closed_survey.deletion_date = timezone.now() - timedelta(days=1)
        closed_survey.save()

        # 2. Place legal hold
        LegalHold.objects.create(
            survey=closed_survey,
            placed_by=user,
            reason="Litigation",
            authority="Court Order #123",
        )

        # 3. Check deletion eligibility
        can_delete, reason = RetentionService.can_survey_be_deleted(closed_survey)
        assert can_delete is False
        assert "legal hold" in reason

        # 4. Automatic deletion should skip it
        stats = RetentionService.process_automatic_deletions()
        assert stats["skipped_legal_hold"] >= 1

        closed_survey.refresh_from_db()
        assert closed_survey.deleted_at is None
