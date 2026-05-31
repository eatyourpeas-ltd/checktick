---
title: Data Governance Implementation
category: None
---

This guide is for **developers** implementing or modifying data governance features in CheckTick. It covers models, APIs, services, commands, and testing.

---

## 1. Architecture Overview

### 1.1 Components

```text
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                       │
│  (Survey Dashboard, Download Modal, Retention Warnings)     │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                         Views / API                         │
│  (data_export, retention_extension, legal_hold, etc.)      │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                         Services                            │
│  (ExportService, RetentionService, AuditService)           │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                         Models                              │
│  (Survey, DataExport, RetentionPolicy, LegalHold)          │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                    Background Tasks                         │
│  (Deletion warnings, Auto-deletion, Backup purging)        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

**Data Export:**

```text
User clicks "Download Data"
  → DownloadDisclaimerModal (React component)
  → POST /api/surveys/{id}/export/ (creates DataExport)
  → ExportService.generate_export()
  → Encrypt CSV, create ZIP
  → Return signed URL (15-minute expiry)
  → AuditService.log_download()
  → Email notification to org admins
```

**Retention Extension:**

```text
User receives warning email
  → Clicks "Extend Retention"
  → ExtensionForm (React component)
  → POST /api/surveys/{id}/extend-retention/
  → RetentionService.extend_retention()
  → Update deletion_date
  → Schedule new warnings
  → AuditService.log_extension()
```

**Automatic Deletion:**

```text
Celery periodic task (daily)
  → RetentionService.check_expired_surveys()
  → For each expired survey:
    → Soft delete (mark deleted_at)
    → Schedule hard deletion (30 days)
    → Email organization owner
  → Celery task (30 days later)
    → RetentionService.hard_delete_survey()
    → Delete responses, files, PIDs
    → Purge backups (call backup API)
    → AuditService.log_deletion()
```

---

## 2. Database Models

### 2.1 Survey Model Extensions

Add fields to existing `Survey` model:

```python
# checktick_app/surveys/models.py

from django.db import models
from django.utils import timezone
from datetime import timedelta

class Survey(models.Model):
    # ... existing fields ...

    # Survey Closure
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='closed_surveys'
    )

    # Retention
    retention_months = models.IntegerField(default=6)  # 6-24
    deletion_date = models.DateTimeField(null=True, blank=True)

    # Soft Deletion
    deleted_at = models.DateTimeField(null=True, blank=True)
    hard_deletion_date = models.DateTimeField(null=True, blank=True)

    # Ownership
    transferred_from = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferred_surveys'
    )
    transferred_at = models.DateTimeField(null=True, blank=True)

    def close_survey(self, user):
        """Close survey and start retention period."""
        self.is_closed = True
        self.closed_at = timezone.now()
        self.closed_by = user
        self.deletion_date = self.closed_at + timedelta(days=self.retention_months * 30)
        self.save()

        # Schedule warnings
        from .tasks import schedule_deletion_warnings
        schedule_deletion_warnings.delay(self.id)

    def extend_retention(self, months, user, reason):
        """Extend retention period (max 24 months total)."""
        from django.core.exceptions import ValidationError

        # Calculate total retention
        months_since_closure = (timezone.now() - self.closed_at).days // 30
        total_months = months_since_closure + months

        if total_months > 24:
            raise ValidationError("Cannot exceed 24 months total retention")

        self.deletion_date = self.closed_at + timedelta(days=total_months * 30)
        self.save()

        # Log extension
        DataRetentionExtension.objects.create(
            survey=self,
            extended_by=user,
            months_added=months,
            reason=reason,
            new_deletion_date=self.deletion_date
        )

        # Reschedule warnings
        from .tasks import schedule_deletion_warnings
        schedule_deletion_warnings.delay(self.id)

    def soft_delete(self):
        """Soft delete survey (30-day grace period)."""
        self.deleted_at = timezone.now()
        self.hard_deletion_date = self.deleted_at + timedelta(days=30)
        self.save()

        # Schedule hard deletion
        from .tasks import schedule_hard_deletion
        schedule_hard_deletion.apply_async(
            args=[self.id],
            eta=self.hard_deletion_date
        )

    def hard_delete(self):
        """Permanently delete survey data."""
        # Delete responses
        self.responses.all().delete()

        # Delete exports
        self.data_exports.all().delete()

        # Purge backups (external API call)
        from .services import BackupService
        BackupService.purge_survey_backups(self.id)

        # Keep audit trail summary
        AuditLog.objects.create(
            action='HARD_DELETE',
            survey_id=self.id,
            survey_name=self.name,
            timestamp=timezone.now()
        )

        # Delete survey
        self.delete()

    @property
    def days_until_deletion(self):
        """Days remaining until automatic deletion."""
        if not self.deletion_date or self.deleted_at:
            return None
        delta = self.deletion_date - timezone.now()
        return max(0, delta.days)

    @property
    def can_extend_retention(self):
        """Check if retention can be extended."""
        if not self.closed_at:
            return False
        months_since_closure = (timezone.now() - self.closed_at).days // 30
        return months_since_closure < 24
```

### 2.2 DataExport Model

```python
# checktick_app/surveys/models.py

import uuid
from django.core.signing import Signer

class DataExport(models.Model):
    """Track data exports for audit trail."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='data_exports')

    # User who downloaded
    exported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    exported_at = models.DateTimeField(auto_now_add=True)

    # Attestation
    full_name = models.CharField(max_length=255)
    purpose = models.TextField()
    ip_address = models.GenericIPAddressField()

    # File details
    file_path = models.CharField(max_length=512)  # S3 path or local path
    file_size = models.BigIntegerField()  # bytes
    password = models.CharField(max_length=128)  # hashed

    # Download link
    download_token = models.CharField(max_length=64, unique=True)
    download_expires_at = models.DateTimeField()
    download_completed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    response_count = models.IntegerField()
    encrypted_fields = models.JSONField(default=list)  # List of encrypted field names

    class Meta:
        ordering = ['-exported_at']
        indexes = [
            models.Index(fields=['survey', '-exported_at']),
            models.Index(fields=['exported_by', '-exported_at']),
            models.Index(fields=['download_token']),
        ]

    def generate_download_token(self):
        """Generate single-use download token."""
        signer = Signer()
        token = signer.sign(f"{self.id}:{timezone.now().timestamp()}")
        self.download_token = token
        self.download_expires_at = timezone.now() + timedelta(minutes=15)
        self.save()
        return token

    def is_download_valid(self):
        """Check if download link is still valid."""
        if self.download_completed_at:
            return False  # Already used
        if timezone.now() > self.download_expires_at:
            return False  # Expired
        return True

    def mark_downloaded(self):
        """Mark download as completed."""
        self.download_completed_at = timezone.now()
        self.save()
```

### 2.3 LegalHold Model

```python
# checktick_app/surveys/models.py

class LegalHold(models.Model):
    """Legal holds prevent automatic deletion."""

    survey = models.OneToOneField(Survey, on_delete=models.CASCADE, related_name='legal_hold')

    # Hold details
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='applied_holds')
    applied_at = models.DateTimeField(auto_now_add=True)

    reason = models.TextField()
    reference = models.CharField(max_length=255)  # Case number, investigation ID
    requesting_party = models.CharField(max_length=255)  # Who requested
    expected_duration_months = models.IntegerField()

    # Review
    review_date = models.DateField()
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reviewed_holds'
    )

    # Removal
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='removed_holds'
    )
    removal_reason = models.TextField(blank=True)

    # Retention freeze tracking
    retention_frozen_at = models.DateTimeField(auto_now_add=True)
    remaining_retention_days = models.IntegerField()  # Days left when frozen

    class Meta:
        ordering = ['-applied_at']

    def remove_hold(self, user, reason):
        """Remove legal hold and resume retention."""
        self.removed_at = timezone.now()
        self.removed_by = user
        self.removal_reason = reason
        self.save()

        # Resume retention period
        self.survey.deletion_date = timezone.now() + timedelta(days=self.remaining_retention_days)
        self.survey.save()

        # Reschedule warnings
        from .tasks import schedule_deletion_warnings
        schedule_deletion_warnings.delay(self.survey.id)
```

### 2.4 DataCustodian Model

```python
# checktick_app/surveys/models.py

class DataCustodian(models.Model):
    """Users with download-only access to specific surveys."""

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='data_custodians')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custodian_surveys')

    # Assignment
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_custodians'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    justification = models.TextField()

    # Acknowledgment
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Removal
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='removed_custodians'
    )

    class Meta:
        unique_together = [['survey', 'user']]
        ordering = ['-assigned_at']

    def is_active(self):
        """Check if custodian assignment is active."""
        return self.acknowledged_at is not None and self.removed_at is None
```

### 2.5 DataRetentionExtension Model

```python
# checktick_app/surveys/models.py

class DataRetentionExtension(models.Model):
    """Audit trail for retention extensions."""

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='retention_extensions')
    extended_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    extended_at = models.DateTimeField(auto_now_add=True)

    months_added = models.IntegerField()
    reason = models.TextField()

    previous_deletion_date = models.DateTimeField()
    new_deletion_date = models.DateTimeField()

    class Meta:
        ordering = ['-extended_at']
```

---

## 3. Permissions

### 3.1 Add DATA_CUSTODIAN Role

```python
# checktick_app/core/models.py (or wherever roles are defined)

class UserRole(models.TextChoices):
    VIEWER = 'VIEWER', 'Viewer'
    EDITOR = 'EDITOR', 'Editor'
    CREATOR = 'CREATOR', 'Creator'
    DATA_CUSTODIAN = 'DATA_CUSTODIAN', 'Data Custodian'  # NEW
    ORGANIZATION_OWNER = 'ORGANIZATION_OWNER', 'Organization Owner'
    SYSTEM_ADMIN = 'SYSTEM_ADMIN', 'System Administrator'
```

### 3.2 Permission Checker

```python
# checktick_app/surveys/permissions.py

class DataGovernancePermissions:
    """Check data governance permissions."""

    @staticmethod
    def can_download_data(user, survey):
        """Check if user can download survey data."""
        # Survey must be closed
        if not survey.is_closed:
            return False

        # Survey must not be deleted
        if survey.deleted_at:
            return False

        # System admins can always download
        if user.is_superuser:
            return True

        # Survey creator can download
        if survey.created_by == user:
            return True

        # Organization owner can download
        if survey.organization and survey.organization.owner == user:
            return True

        # Data custodian can download (if active)
        custodian = DataCustodian.objects.filter(
            survey=survey,
            user=user,
            removed_at__isnull=True
        ).first()
        if custodian and custodian.is_active():
            return True

        return False

    @staticmethod
    def can_extend_retention(user, survey):
        """Check if user can extend retention period."""
        # Survey must be closed
        if not survey.is_closed:
            return False

        # Must be within 24-month limit
        if not survey.can_extend_retention:
            return False

        # Survey creator can extend
        if survey.created_by == user:
            return True

        # Organization owner can extend
        if survey.organization and survey.organization.owner == user:
            return True

        return False

    @staticmethod
    def can_apply_legal_hold(user, survey):
        """Check if user can apply legal hold."""
        # Only organization owners
        if survey.organization and survey.organization.owner == user:
            return True

        # Or system admins
        if user.is_superuser:
            return True

        return False

    @staticmethod
    def can_assign_data_custodian(user, survey):
        """Check if user can assign data custodians."""
        # Survey creator can assign
        if survey.created_by == user:
            return True

        # Organization owner can assign
        if survey.organization and survey.organization.owner == user:
            return True

        return False
```

---

## 4. Services

### 4.1 ExportService

```python
# checktick_app/surveys/services/export_service.py

import csv
import zipfile
import io
import secrets
from cryptography.fernet import Fernet
from django.core.files.storage import default_storage
from django.utils import timezone

class ExportService:
    """Handle data export generation."""

    @staticmethod
    def generate_export(survey, user, full_name, purpose, ip_address):
        """Generate encrypted export file."""
        # Create export record
        export = DataExport.objects.create(
            survey=survey,
            exported_by=user,
            full_name=full_name,
            purpose=purpose,
            ip_address=ip_address,
            response_count=survey.responses.count()
        )

        # Generate password
        password = secrets.token_urlsafe(16)
        export.password = make_password(password)  # Hash for storage

        # Create CSV
        csv_data = ExportService._create_csv(survey)

        # Encrypt CSV
        encrypted_csv = ExportService._encrypt_data(csv_data, survey.encryption_key)

        # Create metadata
        metadata = ExportService._create_metadata(survey, export, user)

        # Create README
        readme = ExportService._create_readme(survey)

        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('survey_data.csv', encrypted_csv)
            zip_file.writestr('metadata.json', metadata)
            zip_file.writestr('README.txt', readme)

        # Encrypt ZIP with password
        encrypted_zip = ExportService._password_protect_zip(zip_buffer.getvalue(), password)

        # Save to storage
        file_path = f"exports/{survey.id}/{export.id}.zip"
        default_storage.save(file_path, io.BytesIO(encrypted_zip))

        export.file_path = file_path
        export.file_size = len(encrypted_zip)
        export.save()

        # Generate download token
        token = export.generate_download_token()

        # Send audit email
        from .tasks import send_download_notification
        send_download_notification.delay(export.id)

        return export, password

    @staticmethod
    def _create_csv(survey):
        """Generate CSV from survey responses."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        headers = ['response_id', 'submitted_at', 'user_id', 'status']
        for question in survey.questions.all():
            headers.append(question.slug)
        writer.writerow(headers)

        # Data rows
        for response in survey.responses.all():
            row = [
                response.id,
                response.submitted_at.isoformat(),
                response.user_id or '',
                response.status
            ]
            for question in survey.questions.all():
                answer = response.answers.filter(question=question).first()
                row.append(answer.value if answer else '')
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def _encrypt_data(data, key):
        """Encrypt data with Fernet."""
        fernet = Fernet(key.encode())
        return fernet.encrypt(data.encode())

    @staticmethod
    def _password_protect_zip(zip_data, password):
        """Password-protect ZIP file."""
        # Use pyminizip or similar library
        # Implementation depends on chosen library
        pass

    @staticmethod
    def _create_metadata(survey, export, user):
        """Create metadata JSON."""
        import json
        metadata = {
            'survey_id': str(survey.id),
            'survey_name': survey.name,
            'export_id': str(export.id),
            'exported_by': user.email,
            'exported_at': export.exported_at.isoformat(),
            'response_count': export.response_count,
            'census_version': '1.0.0',  # From settings
        }
        return json.dumps(metadata, indent=2)

    @staticmethod
    def _create_readme(survey):
        """Create README.txt."""
        return f"""
CheckTick Data Export
==================

Survey: {survey.name}
Export Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

FILES
-----
survey_data.csv - Encrypted survey responses
metadata.json - Export information
README.txt - This file

DATA FORMAT
-----------
The CSV file contains one row per response with the following columns:
- response_id: Unique identifier for this response
- submitted_at: Date and time response was submitted (ISO 8601)
- user_id: Anonymized user identifier (if applicable)
- status: Response status (complete, partial, etc.)
- [question_slug]: One column per survey question

SECURITY
--------
1. Store this file securely on an encrypted device
2. Delete when no longer needed
3. Do not share without authorization
4. Report any data breaches immediately

For more information, see the CheckTick Data Security Guide.
"""
```

### 4.2 RetentionService

```python
# checktick_app/surveys/services/retention_service.py

from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

class RetentionService:
    """Handle retention and deletion operations."""

    @staticmethod
    def check_expired_surveys():
        """Find and soft-delete expired surveys (runs daily)."""
        expired = Survey.objects.filter(
            is_closed=True,
            deletion_date__lte=timezone.now(),
            deleted_at__isnull=True,
            legal_hold__isnull=True  # Exclude surveys with legal holds
        )

        for survey in expired:
            RetentionService.soft_delete_survey(survey)

    @staticmethod
    def soft_delete_survey(survey):
        """Soft delete a survey."""
        survey.soft_delete()

        # Log deletion
        AuditLog.objects.create(
            action='SOFT_DELETE',
            survey=survey,
            timestamp=timezone.now(),
            details={'retention_expired': True}
        )

        # Notify organization owner
        from .tasks import send_deletion_notification
        send_deletion_notification.delay(survey.id, 'soft')

    @staticmethod
    def hard_delete_survey(survey):
        """Hard delete a survey (runs after 30-day grace period)."""
        survey.hard_delete()

    @staticmethod
    def send_deletion_warnings():
        """Send warnings for upcoming deletions (runs daily)."""
        now = timezone.now()

        # 1-month warning
        one_month = Survey.objects.filter(
            is_closed=True,
            deletion_date__lte=now + timedelta(days=30),
            deletion_date__gt=now + timedelta(days=29),
            deleted_at__isnull=True,
            legal_hold__isnull=True
        )
        for survey in one_month:
            RetentionService._send_warning(survey, '1_month')

        # 1-week warning
        one_week = Survey.objects.filter(
            is_closed=True,
            deletion_date__lte=now + timedelta(days=7),
            deletion_date__gt=now + timedelta(days=6),
            deleted_at__isnull=True,
            legal_hold__isnull=True
        )
        for survey in one_week:
            RetentionService._send_warning(survey, '1_week')

        # 1-day warning
        one_day = Survey.objects.filter(
            is_closed=True,
            deletion_date__lte=now + timedelta(days=1),
            deletion_date__gt=now,
            deleted_at__isnull=True,
            legal_hold__isnull=True
        )
        for survey in one_day:
            RetentionService._send_warning(survey, '1_day')

    @staticmethod
    def _send_warning(survey, warning_type):
        """Send deletion warning email."""
        from .tasks import send_retention_warning
        send_retention_warning.delay(survey.id, warning_type)
```

---

## 5. API Endpoints

### 5.1 Data Export

```python
# checktick_app/surveys/views/api.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_survey_data(request, survey_id):
    """Generate and download survey data export."""
    survey = get_object_or_404(Survey, id=survey_id)

    # Check permissions
    if not DataGovernancePermissions.can_download_data(request.user, survey):
        return Response(
            {'error': 'You do not have permission to download this survey data'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Validate attestation
    full_name = request.data.get('full_name')
    purpose = request.data.get('purpose')
    attestation_accepted = request.data.get('attestation_accepted')

    if not all([full_name, purpose, attestation_accepted]):
        return Response(
            {'error': 'Full name, purpose, and attestation required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Generate export
    ip_address = request.META.get('REMOTE_ADDR')
    export, password = ExportService.generate_export(
        survey, request.user, full_name, purpose, ip_address
    )

    # Return download link and password
    download_url = reverse('download_export', args=[export.download_token])
    return Response({
        'download_url': request.build_absolute_uri(download_url),
        'password': password,
        'expires_at': export.download_expires_at.isoformat(),
        'message': 'Save the password securely. It will not be shown again.'
    })

@api_view(['GET'])
def download_export(request, token):
    """Download export file using single-use token."""
    export = get_object_or_404(DataExport, download_token=token)

    # Validate token
    if not export.is_download_valid():
        return Response(
            {'error': 'Download link has expired or been used'},
            status=status.HTTP_410_GONE
        )

    # Mark as downloaded
    export.mark_downloaded()

    # Stream file
    file_path = export.file_path
    response = FileResponse(default_storage.open(file_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="survey_data_{export.survey.id}.zip"'
    return response
```

### 5.2 Retention Extension

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extend_retention(request, survey_id):
    """Extend survey retention period."""
    survey = get_object_or_404(Survey, id=survey_id)

    # Check permissions
    if not DataGovernancePermissions.can_extend_retention(request.user, survey):
        return Response(
            {'error': 'You do not have permission to extend retention'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Validate input
    months = request.data.get('months')
    reason = request.data.get('reason')

    if not months or not reason:
        return Response(
            {'error': 'Months and reason required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        months = int(months)
        if months < 1 or months > 12:
            raise ValueError("Months must be between 1 and 12")
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Extend retention
    try:
        survey.extend_retention(months, request.user, reason)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'new_deletion_date': survey.deletion_date.isoformat(),
        'days_remaining': survey.days_until_deletion
    })
```

---

## 6. Background Tasks (Celery)

```python
# checktick_app/surveys/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

@shared_task
def schedule_deletion_warnings(survey_id):
    """Schedule deletion warning emails."""
    RetentionService.send_deletion_warnings()

@shared_task
def send_retention_warning(survey_id, warning_type):
    """Send retention warning email."""
    survey = Survey.objects.get(id=survey_id)

    # Determine recipients
    recipients = [survey.created_by.email]
    if survey.organization:
        recipients.append(survey.organization.owner.email)

    # Render email
    subject = f"Survey data will be deleted in {warning_type.replace('_', ' ')}"
    message = render_to_string('emails/retention_warning.html', {
        'survey': survey,
        'warning_type': warning_type,
        'days_remaining': survey.days_until_deletion
    })

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)

@shared_task
def send_download_notification(export_id):
    """Notify org admins of data download."""
    export = DataExport.objects.get(id=export_id)
    survey = export.survey

    if survey.organization:
        recipients = [survey.organization.owner.email]
        subject = f"Data downloaded from survey: {survey.name}"
        message = render_to_string('emails/download_notification.html', {
            'export': export,
            'survey': survey
        })
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)

@shared_task
def daily_retention_check():
    """Daily task to check for expired surveys."""
    RetentionService.check_expired_surveys()
    RetentionService.send_deletion_warnings()

@shared_task
def schedule_hard_deletion(survey_id):
    """Hard delete survey after 30-day grace period."""
    survey = Survey.objects.get(id=survey_id)
    RetentionService.hard_delete_survey(survey)
```

**Celery Beat Schedule:**

```python
# checktick_app/settings.py

CELERY_BEAT_SCHEDULE = {
    'daily-retention-check': {
        'task': 'checktick_app.surveys.tasks.daily_retention_check',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

---

## 7. Testing

### 7.1 Model Tests

```python
# checktick_app/surveys/tests/test_data_governance.py

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from checktick_app.surveys.models import Survey, DataExport, LegalHold

class SurveyRetentionTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(name="Test Survey")
        self.user = User.objects.create_user('test@example.com')

    def test_close_survey_sets_deletion_date(self):
        """Closing survey should set deletion date to 6 months."""
        self.survey.close_survey(self.user)

        expected_date = timezone.now() + timedelta(days=180)
        self.assertAlmostEqual(
            self.survey.deletion_date.timestamp(),
            expected_date.timestamp(),
            delta=60  # Allow 1 minute difference
        )

    def test_extend_retention_updates_deletion_date(self):
        """Extending retention should update deletion date."""
        self.survey.close_survey(self.user)
        original_date = self.survey.deletion_date

        self.survey.extend_retention(3, self.user, "Need more time")

        expected_date = original_date + timedelta(days=90)
        self.assertAlmostEqual(
            self.survey.deletion_date.timestamp(),
            expected_date.timestamp(),
            delta=60
        )

    def test_cannot_extend_beyond_24_months(self):
        """Extending retention beyond 24 months should raise error."""
        self.survey.close_survey(self.user)
        self.survey.closed_at = timezone.now() - timedelta(days=365 * 2)  # 2 years ago
        self.survey.save()

        with self.assertRaises(ValidationError):
            self.survey.extend_retention(6, self.user, "Too late")

    def test_legal_hold_prevents_deletion(self):
        """Survey with legal hold should not be soft deleted."""
        self.survey.close_survey(self.user)
        self.survey.deletion_date = timezone.now() - timedelta(days=1)  # Expired
        self.survey.save()

        # Apply legal hold
        LegalHold.objects.create(
            survey=self.survey,
            applied_by=self.user,
            reason="Litigation",
            reference="CASE-123",
            requesting_party="Legal",
            expected_duration_months=12,
            review_date=timezone.now().date() + timedelta(days=180),
            remaining_retention_days=0
        )

        # Should not be in expired list
        expired = RetentionService.check_expired_surveys()
        self.assertNotIn(self.survey, expired)
```

### 7.2 Permission Tests

```python
class DataGovernancePermissionTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user('creator@example.com')
        self.org_owner = User.objects.create_user('owner@example.com')
        self.custodian = User.objects.create_user('custodian@example.com')
        self.viewer = User.objects.create_user('viewer@example.com')

        self.organization = Organization.objects.create(owner=self.org_owner)
        self.survey = Survey.objects.create(
            name="Test",
            created_by=self.creator,
            organization=self.organization
        )
        self.survey.close_survey(self.creator)

        DataCustodian.objects.create(
            survey=self.survey,
            user=self.custodian,
            assigned_by=self.creator,
            justification="Test",
            acknowledged_at=timezone.now()
        )

    def test_creator_can_download(self):
        self.assertTrue(
            DataGovernancePermissions.can_download_data(self.creator, self.survey)
        )

    def test_org_owner_can_download(self):
        self.assertTrue(
            DataGovernancePermissions.can_download_data(self.org_owner, self.survey)
        )

    def test_custodian_can_download(self):
        self.assertTrue(
            DataGovernancePermissions.can_download_data(self.custodian, self.survey)
        )

    def test_viewer_cannot_download(self):
        self.assertFalse(
            DataGovernancePermissions.can_download_data(self.viewer, self.survey)
        )

    def test_custodian_cannot_extend_retention(self):
        self.assertFalse(
            DataGovernancePermissions.can_extend_retention(self.custodian, self.survey)
        )

    def test_only_org_owner_can_apply_legal_hold(self):
        self.assertTrue(
            DataGovernancePermissions.can_apply_legal_hold(self.org_owner, self.survey)
        )
        self.assertFalse(
            DataGovernancePermissions.can_apply_legal_hold(self.creator, self.survey)
        )
```

---

## 8. Management Commands

```python
# checktick_app/surveys/management/commands/check_retention.py

from django.core.management.base import BaseCommand
from checktick_app.surveys.services import RetentionService

class Command(BaseCommand):
    help = 'Check for expired surveys and send warnings'

    def handle(self, *args, **options):
        self.stdout.write('Checking for expired surveys...')
        RetentionService.check_expired_surveys()

        self.stdout.write('Sending deletion warnings...')
        RetentionService.send_deletion_warnings()

        self.stdout.write(self.style.SUCCESS('Retention check complete'))
```

**Usage:**

```bash
python manage.py check_retention
```

---

## 9. Frontend Components

### 9.1 Download Disclaimer Modal

```tsx
// checktick_app/static/src/components/DownloadDisclaimerModal.tsx

import React, { useState } from 'react';

interface Props {
  surveyId: string;
  surveyName: string;
  onClose: () => void;
}

export const DownloadDisclaimerModal: React.FC<Props> = ({ surveyId, surveyName, onClose }) => {
  const [fullName, setFullName] = useState('');
  const [purpose, setPurpose] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);

    const response = await fetch(`/api/surveys/${surveyId}/export/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: fullName,
        purpose: purpose,
        attestation_accepted: accepted
      })
    });

    if (response.ok) {
      const data = await response.json();
      // Show download link and password
      showDownloadInfo(data.download_url, data.password);
    }

    setLoading(false);
  };

  return (
    <div className="modal">
      <h2>Download Survey Data: {surveyName}</h2>

      <div className="disclaimer">
        <p>By downloading this data, you confirm that you will:</p>
        <ul>
          <li>✓ Store data on a secure, encrypted device</li>
          <li>✓ Comply with your organization's data protection policies</li>
          <li>✓ Take responsibility for the security of this data</li>
          <li>✓ Delete data when no longer needed</li>
          <li>✓ Report any data breaches immediately</li>
        </ul>
      </div>

      <input
        type="text"
        placeholder="Your full name"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
      />

      <textarea
        placeholder="Purpose of download (required)"
        value={purpose}
        onChange={(e) => setPurpose(e.target.value)}
      />

      <label>
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
        />
        I understand and accept these responsibilities
      </label>

      <button onClick={handleSubmit} disabled={!accepted || loading}>
        {loading ? 'Generating...' : 'Download Data'}
      </button>
      <button onClick={onClose}>Cancel</button>
    </div>
  );
};
```

---

## 10. Configuration

### 10.1 Settings

```python
# checktick_app/settings.py

# Data Governance
DATA_GOVERNANCE = {
    'DEFAULT_RETENTION_MONTHS': 6,
    'MAXIMUM_RETENTION_MONTHS': 24,
    'SOFT_DELETE_GRACE_PERIOD_DAYS': 30,
    'DOWNLOAD_LINK_EXPIRY_MINUTES': 15,
    'LEGAL_HOLD_REVIEW_MONTHS': 6,
}

# Export settings
DATA_EXPORT_STORAGE = 'django.core.files.storage.FileSystemStorage'  # Or S3
DATA_EXPORT_PATH = 'exports/'
```

### 10.2 Environment Variables

```bash
# .env

# Encryption key for CSV data (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SURVEY_ENCRYPTION_KEY=your-fernet-key-here

# Backup API (for purging backups on deletion)
BACKUP_API_URL=https://backup-service.example.com
BACKUP_API_KEY=your-backup-api-key
```

---

## 11. Database Migrations

```python
# checktick_app/surveys/migrations/0XXX_add_data_governance.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('surveys', '0XXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='survey',
            name='is_closed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='survey',
            name='closed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        # ... (add all other fields from models above)

        migrations.CreateModel(
            name='DataExport',
            fields=[
                # ... (fields from DataExport model)
            ],
        ),

        migrations.CreateModel(
            name='LegalHold',
            fields=[
                # ... (fields from LegalHold model)
            ],
        ),

        migrations.CreateModel(
            name='DataCustodian',
            fields=[
                # ... (fields from DataCustodian model)
            ],
        ),
    ]
```

---

## 12. Deployment Checklist

- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser if needed: `python manage.py createsuperuser`
- [ ] Configure Celery beat schedule
- [ ] Set up encryption keys in environment variables
- [ ] Configure backup API credentials
- [ ] Test email notifications
- [ ] Verify file storage (local or S3)
- [ ] Set up monitoring for Celery tasks
- [ ] Test retention workflow end-to-end
- [ ] Review data protection policy placeholders
- [ ] Train organization owners on features
- [ ] Document incident response procedures

---

## 13. Monitoring and Logging

### 13.1 Metrics to Track

- Number of surveys nearing deletion (by warning level)
- Data exports per day/week
- Retention extensions per survey
- Legal holds active/removed
- Soft/hard deletions per week
- Failed Celery tasks
- Download link expiries vs. completions

### 13.2 Alerts

Set up alerts for:
- Celery task failures (retention checks, deletions)
- Unusual number of data exports (potential breach)
- Legal hold reviews overdue
- Failed backup purges
- Email delivery failures (warnings)

---

## 14. Further Resources

- [Django Models Documentation](https://docs.djangoproject.com/en/stable/topics/db/models/)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html)
- [Cryptography Library (Fernet)](https://cryptography.io/en/latest/fernet/)
- [GDPR Compliance Guide](https://ico.org.uk/for-organisations/)
- [CheckTick API Documentation](/docs/api/)

---

**This implementation guide is living documentation.** Update it as features are added or changed.
