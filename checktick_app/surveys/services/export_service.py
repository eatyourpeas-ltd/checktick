"""
ExportService - Handles data export, CSV generation, and download management.

Features:
- Generate encrypted CSV exports of survey responses
- Create time-limited download tokens
- Track export audit trail
- Password-protected downloads
"""

from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO
import logging
import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from ..models import DataExport, Survey

User = get_user_model()
logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for creating and managing survey data exports.

    Workflow:
    1. User requests export via API
    2. Service generates CSV from survey responses
    3. Service encrypts CSV with user-provided password
    4. Service creates DataExport record with download token
    5. Service returns download URL (valid for configured days)
    6. User downloads file using token
    7. Service tracks download in audit trail
    """

    # Download token length
    TOKEN_LENGTH = 32

    @classmethod
    @transaction.atomic
    def create_export(
        cls,
        survey: Survey,
        user: User,
        password: str | None = None,
        survey_key: bytes | None = None,
    ) -> DataExport:
        """
        Create a new data export for a survey.

        Args:
            survey: Survey to export data from
            user: User requesting the export
            password: Optional password to encrypt the export file
            survey_key: Survey's KEK (required for encrypted surveys)

        Returns:
            DataExport instance with download token

        Raises:
            ValueError: If survey has no responses, is deleted, or is encrypted without key
        """
        logger.info(f"Creating export for survey {survey.slug} by user {user.username}")
        from ..models import DataExport, SurveyResponse

        # Validate survey state
        if survey.deleted_at:
            logger.warning(
                f"Attempted export of deleted survey {survey.slug} by {user.username}"
            )
            raise ValueError("Cannot export data from deleted survey")

        # Validate survey_key for encrypted surveys
        if survey.requires_whole_response_encryption() and not survey_key:
            logger.error(
                f"Export attempted without survey key for encrypted survey {survey.slug}"
            )
            raise ValueError(
                "Survey key required to export encrypted survey data. "
                "Please unlock the survey first."
            )

        # Count exportable responses (exclude frozen)
        response_count = SurveyResponse.objects.filter(
            survey=survey,
            is_frozen=False,
        ).count()
        frozen_count = SurveyResponse.objects.filter(
            survey=survey,
            is_frozen=True,
        ).count()

        if response_count == 0:
            if frozen_count > 0:
                logger.warning(
                    f"Export blocked: all {frozen_count} responses frozen for survey {survey.slug}"
                )
                raise ValueError(
                    f"All {frozen_count} responses are frozen pending data subject request resolution"
                )
            logger.warning(f"Export blocked: no responses for survey {survey.slug}")
            raise ValueError("Survey has no responses to export")

        logger.info(
            f"Generating CSV for survey {survey.slug}: {response_count} responses, "
            f"{frozen_count} frozen"
        )

        # Generate CSV data (with decryption if survey_key provided)
        csv_data = cls._generate_csv(survey, survey_key)

        # Encrypt export file if password provided
        if password:
            logger.info(f"Encrypting export file for survey {survey.slug}")
            encrypted_data, encryption_key_id = cls._encrypt_csv(csv_data, password)
            is_encrypted = True
            file_data = encrypted_data
        else:
            logger.debug(f"Export file not encrypted for survey {survey.slug}")
            is_encrypted = False
            encryption_key_id = None
            file_data = csv_data.encode("utf-8")

        # Generate secure download token
        download_token = secrets.token_urlsafe(cls.TOKEN_LENGTH)

        # Calculate expiry using configurable setting
        expires_at = timezone.now() + timedelta(
            days=settings.CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS
        )

        # Create DataExport record
        export = DataExport.objects.create(
            survey=survey,
            created_by=user,
            download_token=download_token,
            download_url_expires_at=expires_at,
            response_count=response_count,
            file_size_bytes=len(file_data),
            is_encrypted=is_encrypted,
            encryption_key_id=encryption_key_id,
        )

        logger.info(
            f"Export created successfully: ID={export.id}, survey={survey.slug}, "
            f"size={len(file_data)} bytes, encrypted={is_encrypted}, "
            f"expires={expires_at.isoformat()}"
        )

        # TODO: Store encrypted file in object storage (S3/Azure Blob)
        # For now, we'll regenerate on download (stateless)

        return export

    @classmethod
    def _generate_csv(cls, survey: Survey, survey_key: bytes | None = None) -> str:
        """
        Generate CSV string from survey responses.

        Args:
            survey: Survey to export
            survey_key: Survey's KEK for decrypting responses (required for encrypted surveys)

        Returns:
            CSV string with headers and response data

        Note:
            - For encrypted surveys, survey_key is required to decrypt responses
            - Whole-response encryption surveys store data in enc_answers
            - Legacy surveys store plaintext in answers and encrypted demographics in enc_demographics
            - Question IDs are used as keys in the answers dict
        """
        logger.debug(f"Generating CSV for survey {survey.slug}")
        from ..models import SurveyQuestion, SurveyResponse

        output = StringIO()

        # Get all questions for this survey, ordered
        questions = SurveyQuestion.objects.filter(survey=survey).order_by("order")

        # Create CSV writer
        writer = csv.writer(output)

        # Write header row
        headers = [
            "Response ID",
            "Submitted At",
            "Submitted By",
        ]

        # Add question text as headers (using question ID as reference)
        question_list = list(questions)
        for question in question_list:
            # Use question text for header, will lookup by ID in answers
            headers.append(question.text)

        writer.writerow(headers)

        # Write response rows
        # IMPORTANT: Exclude frozen responses - they are pending data subject request resolution
        responses = SurveyResponse.objects.filter(
            survey=survey,
            is_frozen=False,  # Exclude frozen responses
        ).order_by("submitted_at")

        logger.debug(f"Processing {responses.count()} responses for CSV export")

        for response in responses:
            # Decrypt response if survey uses whole-response encryption
            if survey.requires_whole_response_encryption() and survey_key:
                try:
                    full_response = response.load_complete_response(survey_key)
                    answers_dict = full_response.get("answers", {})
                    logger.debug(
                        f"Decrypted response {response.id} for encrypted survey"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt response {response.id}: {e}",
                        exc_info=True,
                    )
                    # Skip this response if decryption fails
                    continue
            else:
                # Legacy format: answers stored in plaintext
                answers_dict = response.answers or {}

            row = [
                str(response.id),
                response.submitted_at.isoformat() if response.submitted_at else "",
                (
                    response.submitted_by.username
                    if response.submitted_by
                    else "Anonymous"
                ),
            ]

            # Add answer for each question
            # Answers are keyed by question ID or field name
            for question in question_list:
                # Try both question.id and str(question.id) as keys
                answer = (
                    answers_dict.get(str(question.id))
                    or answers_dict.get(question.id)
                    or ""
                )
                row.append(str(answer) if answer else "")

            writer.writerow(row)

        return output.getvalue()

    @classmethod
    def _encrypt_csv(cls, csv_data: str, password: str) -> tuple[bytes, str]:
        """
        Encrypt CSV data with user-provided password using AES-256-GCM.

        Args:
            csv_data: CSV string to encrypt
            password: User-provided password

        Returns:
            Tuple of (encrypted_bytes, encryption_key_id)

        This uses the same encryption utilities as survey data encryption,
        ensuring consistent security across the platform.
        """
        from ..utils import encrypt_sensitive

        logger.debug(f"Encrypting CSV data ({len(csv_data)} bytes)")

        # Encrypt CSV with password (encrypt_sensitive handles KDF internally)
        # Pass password as bytes - encrypt_sensitive will derive key with Scrypt
        encrypted_blob = encrypt_sensitive(
            password.encode("utf-8"), {"csv_content": csv_data}
        )

        # Generate key ID for tracking
        encryption_key_id = f"export-{secrets.token_hex(8)}"

        logger.info(
            f"CSV encrypted: key_id={encryption_key_id}, "
            f"size={len(encrypted_blob)} bytes"
        )

        return encrypted_blob, encryption_key_id

    @classmethod
    def get_download_url(cls, export: DataExport) -> str:
        """
        Generate download URL for an export.

        Args:
            export: DataExport instance

        Returns:
            Absolute URL for downloading the export

        Raises:
            ValueError: If download URL has expired
        """
        if export.is_download_url_expired:
            raise ValueError("Download URL has expired")

        # TODO: Generate actual URL based on site domain
        # For now, return placeholder URL pattern
        return f"/api/surveys/{export.survey_id}/exports/{export.id}/download/{export.download_token}/"

    @classmethod
    @transaction.atomic
    def record_download(cls, export: DataExport) -> None:
        """
        Record that an export was downloaded.

        Args:
            export: DataExport instance
        """
        export.mark_downloaded()

    @classmethod
    def validate_download_token(cls, export: DataExport, token: str) -> bool:
        """
        Validate a download token for an export.

        Args:
            export: DataExport instance
            token: Token to validate

        Returns:
            True if token is valid and not expired
        """
        if export.is_download_url_expired:
            return False

        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(export.download_token, token)

    @classmethod
    def cleanup_expired_exports(cls, days_old: int = 30) -> int:
        """
        Delete expired export records and associated files.

        Args:
            days_old: Delete exports older than this many days

        Returns:
            Number of exports deleted
        """
        from ..models import DataExport

        cutoff_date = timezone.now() - timedelta(days=days_old)

        # Find expired exports
        expired_exports = DataExport.objects.filter(created_at__lt=cutoff_date)

        count = expired_exports.count()

        # TODO: Delete associated files from object storage

        # Delete records
        expired_exports.delete()

        return count
