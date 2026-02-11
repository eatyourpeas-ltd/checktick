---
title: Email Notifications
category: configuration
priority: 4
---

CheckTick includes a comprehensive email notification system with customizable templates, granular user preferences, and two-level theming support.

## Overview

The email system provides:

- **Welcome emails** on user signup
- **Password change notifications** for security
- **Survey creation/deletion confirmations** (optional)
- **Team and survey invitations** (future)
- **Error and critical alerts** (future, for logging integration)
- **Markdown-based templates** with platform and survey-level branding
- **Granular user preferences** controllable via profile page

## Quick Start

### 1. Configure Email Backend

Email settings are configured via environment variables. **The email backend is automatically selected based on your `DEBUG` setting:**

- **`DEBUG=True`** (development): Emails are printed to the console
- **`DEBUG=False`** (production): Emails are sent via SMTP (Mailgun)

You can override this behavior by explicitly setting `EMAIL_BACKEND` in your `.env` file.

**Development setup (.env):**

```bash
# DEBUG=True automatically uses console backend
DEBUG=True
DEFAULT_FROM_EMAIL=noreply@checktick.local
```

**Production setup (.env):**

```bash
# DEBUG=False automatically uses SMTP backend
DEBUG=False
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
SERVER_EMAIL=server@yourdomain.com

# SMTP settings (required for production)
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@mg.yourdomain.com
EMAIL_HOST_PASSWORD=your-mailgun-smtp-password
EMAIL_TIMEOUT=10
```

**Override email backend (optional):**

If you want to force a specific backend regardless of `DEBUG`, add to `.env`:

```bash
# Force console output even in production (for testing)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Force SMTP even in development
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# Use file-based backend (emails saved to files)
EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend
EMAIL_FILE_PATH=/tmp/app-emails
```

### 2. Set Up SMTP Provider (Production)

CheckTick supports **any SMTP email service**. Below are configuration examples for popular providers.

#### Mailgun (Recommended)

1. Create a free [Mailgun account](https://www.mailgun.com/)
2. Verify your sending domain (or use Mailgun's sandbox domain for testing)
3. Get SMTP credentials from Mailgun dashboard:
   - Navigate to **Sending** → **Domain Settings** → **SMTP Credentials**
   - Use `smtp.mailgun.org` as host, port `587`
   - Username format: `postmaster@mg.yourdomain.com`
4. Add credentials to your `.env` file:

```bash
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@mg.yourdomain.com
EMAIL_HOST_PASSWORD=your-mailgun-smtp-password
```

#### Gmail

For Gmail, you need to use an [App Password](https://support.google.com/accounts/answer/185833):

```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
```

**Note:** Regular Gmail passwords won't work. You must generate an App Password in your Google Account settings.

#### SendGrid

1. Get your [SendGrid API key](https://app.sendgrid.com/settings/api_keys)
2. Configure `.env`:

```bash
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
```

**Note:** The username is literally `apikey`, not your SendGrid username.

#### Amazon SES

1. Set up [Amazon SES SMTP credentials](https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html)
2. Configure `.env` (replace region as needed):

```bash
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-ses-smtp-username
EMAIL_HOST_PASSWORD=your-ses-smtp-password
```

#### Other SMTP Providers

Any SMTP service will work. You just need:

- `EMAIL_HOST` - SMTP server hostname
- `EMAIL_PORT` - Usually `587` (TLS), `465` (SSL), or `25` (plain)
- `EMAIL_USE_TLS` - Set to `True` for port 587
- `EMAIL_HOST_USER` - Your SMTP username
- `EMAIL_HOST_PASSWORD` - Your SMTP password

### 3. Run Migration

The email preferences model needs to be migrated to your database:

```bash
# With Docker
docker compose exec web python manage.py migrate

# Without Docker
python manage.py migrate
```

### 4. Test Email Sending

Start your development server and create a new user account. With the console backend, you'll see the welcome email printed in the terminal:

```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: Welcome to CheckTick!
From: noreply@checktick.local
To: newuser@example.com
Date: Sat, 04 Oct 2025 10:30:00 -0000
Message-ID: <...>

Welcome to CheckTick!

Hi newuser@example.com,

Thank you for signing up for CheckTick! We're excited to have you on board.
...
```

## User Email Preferences

Users have granular control over which emails they receive. Preferences are managed via the profile page at `/profile`.

### Available Preferences

| Preference | Description | Default |
|------------|-------------|---------|
| **Welcome emails** | Sent when a new account is created | ✅ Enabled |
| **Password change notifications** | Security alerts when password is changed | ✅ Enabled |
| **Survey created confirmations** | Notification when you create a survey | ❌ Disabled |
| **Survey deleted confirmations** | Notification when you delete a survey | ❌ Disabled |
| **Survey published notifications** | Alert when your survey is published | ❌ Disabled |
| **Team invitations** | Invites to join organisations | ✅ Enabled |
| **Survey invitations** | Invites to collaborate on surveys | ✅ Enabled |
| **Error notifications** | System errors affecting you (future) | ✅ Enabled |
| **Critical alerts** | Critical system issues (future) | ✅ Enabled |

### Managing Preferences

1. Log in to CheckTick
2. Navigate to your **Profile** page (click your avatar → Profile)
3. Scroll to **Email Notification Preferences** section
4. Toggle checkboxes for desired notifications
5. Click **Save Email Preferences**

Changes take effect immediately.

## Email Templates

All email content is stored as Markdown templates in `checktick_app/templates/emails/`. This makes them easy to customize and maintain.

### Template Structure

Each email has two components:

1. **Markdown content** (`.md` file) - The email body with variables
2. **HTML wrapper** (`base_email.html`) - Responsive email template with branding

### Available Templates

| Template | Purpose | Variables |
|----------|---------|-----------|
| `welcome.md` | Welcome new users | `user.username`, `brand_title`, `site_url` |
| `password_changed.md` | Security notification | `user.username`, `user.email`, `brand_title` |
| `survey_created.md` | Survey creation confirmation | `user.username`, `survey.title`, `survey.slug`, `survey.state` |
| `survey_deleted.md` | Survey deletion confirmation | `user.username`, `survey_name`, `survey_slug` |

### Customizing Templates

To customize an email template:

1. Open the `.md` file in `checktick_app/templates/emails/`
2. Edit the content using Markdown syntax
3. Use template variables (e.g., `{{ user.username }}`) for personalization
4. Restart your web server to apply changes

**Example (welcome.md):**

```markdown
## Welcome to {{ brand_title }}!

Hi **{{ user.username }}**,

Thank you for signing up! Here's how to get started:

### Getting Started

- Create your first survey
- Invite team members
- Explore our documentation at {{ site_url }}/docs/

Need help? Contact us anytime.

Welcome aboard!
The {{ brand_title }} Team
```

### Email Styling

The base HTML template (`base_email.html`) applies:

- **Responsive design** - Works on desktop and mobile
- **Platform branding** - Uses colors and fonts from SiteBranding model
- **Email client compatibility** - Inline CSS for broad support
- **Professional styling** - Buttons, code blocks, lists, blockquotes

## Two-Level Theming

CheckTick supports theming at both platform and survey levels.

### Platform-Level Theming

Used for account-related emails (welcome, password change, survey deleted):

- **Brand title** from `SiteBranding.title` or Django `settings.SITE_NAME`
- **Primary color** from `SiteBranding.primary_color` or settings default
- **Fonts** from `SiteBranding.font_heading` and `SiteBranding.font_body`
- **Logo** from `SiteBranding.icon_url` (optional)

Configure via `/profile` (superusers only) under "Project theme and brand".

### Survey-Level Theming

Used for survey-specific emails (survey created):

- **Inherits platform defaults** as baseline
- **Overrides** from `Survey.style` field if customized
- Allows per-survey branding for white-label use cases

Example: A research organisation can create multiple surveys with different branding for different departments.

## Developer Guide

### Sending Emails Programmatically

The email utility module provides functions for all email types.

#### Import the functions

```python
from checktick_app.core.email_utils import (
    send_welcome_email,
    send_password_change_email,
    send_survey_created_email,
    send_survey_deleted_email,
)
```

#### Send welcome email

```python
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='alice@example.com')

send_welcome_email(user)
```

#### Send password change notification

```python
send_password_change_email(user)
```

#### Send survey created email

```python
from checktick_app.surveys.models import Survey

survey = Survey.objects.get(slug='my-survey')
send_survey_created_email(user, survey)
```

#### Send survey deleted email

```python
survey_name = survey.title
survey_slug = survey.slug
survey.delete()

send_survey_deleted_email(user, survey_name, survey_slug)
```

### Respecting User Preferences

All email functions automatically check `UserEmailPreferences` before sending:

```python
def send_welcome_email(user):
    """Send a welcome email to a new user."""
    from checktick_app.core.models import UserEmailPreferences

    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_welcome_email:
        logger.info(f"Welcome email skipped for {user.username} (user preference)")
        return

    # Continue sending email...
```

You don't need to check preferences manually - just call the send function.

### Email Function Signatures

```python
def send_branded_email(
    to_email: str,
    subject: str,
    markdown_template: str,
    context: dict,
    from_email: str | None = None,
    brand_override: dict | None = None,
) -> bool:
    """
    Send a branded email using a markdown template.

    Returns True if email sent successfully, False otherwise.
    """

def send_welcome_email(user) -> bool:
    """Send welcome email with platform branding."""

def send_password_change_email(user) -> bool:
    """Send password change notification with platform branding."""

def send_survey_created_email(user, survey) -> bool:
    """Send survey created confirmation with survey branding."""

def send_survey_deleted_email(user, survey_name: str, survey_slug: str) -> bool:
    """Send survey deleted confirmation with platform branding."""
```

### Creating New Email Templates

1. **Create Markdown template:**

```bash
touch checktick_app/templates/emails/my_new_email.md
```

2. **Write content with variables:**

```markdown
## {{ subject_line }}

Hi **{{ user.username }}**,

Your custom message here with {{ variables }}.

Best regards,
The {{ brand_title }} Team
```

3. **Create send function in `email_utils.py`:**

```python
def send_my_custom_email(user, custom_data):
    """Send a custom email."""
    from checktick_app.core.models import UserEmailPreferences

    # Check user preferences (create new preference field if needed)
    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_my_custom_email:
        logger.info(f"Custom email skipped for {user.username} (user preference)")
        return False

    # Get branding
    brand = get_platform_branding()

    # Build context
    context = {
        "user": user,
        "custom_data": custom_data,
        "brand_title": brand["title"],
        "site_url": settings.SITE_URL,
    }

    # Send email
    return send_branded_email(
        to_email=user.email,
        subject=f"Custom Subject - {brand['title']}",
        markdown_template="emails/my_new_email.md",
        context=context,
        brand_override=brand,
    )
```

4. **Add preference to model (if needed):**

If you want user control, add a field to `UserEmailPreferences`:

```python
class UserEmailPreferences(models.Model):
    # ... existing fields ...

    send_my_custom_email = models.BooleanField(
        default=True,
        help_text="Receive custom notification emails",
    )
```

Then create and run a migration.

## Integration Points

### Signup Flow

Welcome emails are sent when a user signs up. To integrate:

**In `checktick_app/core/views.py` (or your signup view):**

```python
from .email_utils import send_welcome_email

def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Send welcome email
            send_welcome_email(user)

            return redirect("dashboard")
    # ... rest of view
```

### Password Change

For password changes, use Django signals or override the password change view:

**Option 1: Using signals (recommended)**

Create `checktick_app/core/signals.py`:

```python
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .email_utils import send_password_change_email

# Note: Django doesn't have a built-in password_changed signal
# You may need to create a custom signal or override the view
```

**Option 2: Override password change view**

```python
from django.contrib.auth.views import PasswordChangeView
from .email_utils import send_password_change_email

class CustomPasswordChangeView(PasswordChangeView):
    def form_valid(self, form):
        response = super().form_valid(form)
        send_password_change_email(self.request.user)
        return response
```

### Survey CRUD Operations

**Survey creation (in `checktick_app/surveys/views.py`):**

```python
from checktick_app.core.email_utils import send_survey_created_email

def create_survey(request):
    # ... survey creation logic ...

    survey = form.save()
    send_survey_created_email(request.user, survey)

    return redirect("survey_detail", slug=survey.slug)
```

**Survey deletion:**

```python
from checktick_app.core.email_utils import send_survey_deleted_email

def delete_survey(request, slug):
    survey = get_object_or_404(Survey, slug=slug)

    # Capture details before deletion
    survey_name = survey.title
    survey_slug = survey.slug

    survey.delete()

    # Send notification
    send_survey_deleted_email(request.user, survey_name, survey_slug)

    return redirect("dashboard")
```

## Troubleshooting

### Emails not sending

**Check backend configuration:**

```bash
# In Django shell
python manage.py shell

>>> from django.conf import settings
>>> print(settings.EMAIL_BACKEND)
django.core.mail.backends.console.EmailBackend  # Should print your backend
```

**Test email sending:**

```python
from django.core.mail import send_mail

send_mail(
    "Test Subject",
    "Test message body.",
    "from@example.com",
    ["to@example.com"],
    fail_silently=False,
)
```

### Console backend shows nothing

Make sure you're watching the correct terminal where `runserver` or `docker compose logs -f web` is running.

### SMTP authentication errors

- Verify `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are correct
- Check Mailgun dashboard for valid SMTP credentials
- Ensure domain is verified in Mailgun
- Try sandbox domain for testing: `sandbox123.mailgun.org`

### User not receiving emails

1. Check user's email preferences in profile
2. Verify user's email address is valid
3. Check spam/junk folder
4. Review Django logs for sending errors
5. Verify Mailgun sending quota (free tier has limits)

### Template variables not rendering

- Ensure variable names match those passed in context
- Check for typos: `{{ user.username }}` not `{{ user.name }}`
- Verify context is passed to `send_branded_email()`

### Branding not applied

1. Check `SiteBranding` model exists: `python manage.py shell` → `from checktick_app.core.models import SiteBranding`
2. Verify branding configured in profile (superuser only)
3. Check `settings.SITE_NAME` and `settings.PRIMARY_COLOR` fallbacks

## Future Enhancements

The email system is designed to support future features:

### Logging Integration

The `UserEmailPreferences` model includes fields for future logging notifications:

- `notify_on_error` - Receive error notifications
- `notify_on_critical` - Receive critical alerts

When the logging system is implemented, these will control error/alert emails.

### Batch Email Capabilities

Future updates may include:

- Bulk email sending for survey invitations
- Email scheduling for reminders
- Digest emails (daily/weekly summaries)

### Advanced Templates

Planned template improvements:

- HTML email editor in admin
- Template versioning
- A/B testing for email content
- Personalization based on user activity

## Related Documentation

- [Getting Started](getting-started.md) - Initial setup guide
- [User Management](user-management.md) - Managing users and permissions
- [Branding and Theme Settings](branding-and-theme-settings.md) - Customizing appearance
- [Authentication and Permissions](authentication-and-permissions.md) - Security concepts

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review [GitHub issues](https://github.com/eatyourpeas/checktick/issues)
3. Consult [Mailgun documentation](https://documentation.mailgun.com/)
4. Open a new issue with email logs and configuration (redact credentials!)
