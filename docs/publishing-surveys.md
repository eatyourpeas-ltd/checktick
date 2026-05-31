---
title: Publishing Surveys (Technical)
category: development
priority: 15
---

# Publishing Surveys (Technical Reference)

This document provides technical details about survey publishing, visibility modes, URLs, and security protections. For a user-friendly guide, see [Publish & Collect Responses](/docs/publish-and-collection/).

## Lifecycle: Status and Window

### Status States

- **draft**: Builder-only. Participant routes return 404.
- **published**: Participant routes enabled, subject to visibility rules and time/response limits.
- **closed**: Submissions disabled, preview remains read-only.

### Time Window

Optional `start_at` and `end_at` datetime fields further restrict when a survey is live:

```python
survey.start_at = timezone.now()  # Survey becomes live at this time
survey.end_at = timezone.now() + timedelta(days=30)  # Survey closes at this time
```

### Response Capacity

Optional `max_responses` integer field caps total accepted responses:

```python
survey.max_responses = 100  # Survey closes after 100 responses
```

The dashboard displays badges for Status, Visibility, Window, and Total responses, plus analytics tiles (Today, Last 7 days).

## Visibility Modes (Technical)

All participant pages are server-rendered (SSR). The exact URL and access control depends on the visibility mode:

### Authenticated

**URL:** `/surveys/<slug>/take/`

**Access Control:**
- Requires logged-in user account
- Enforced by Django session authentication + CSRF
- Two modes controlled by `allow_any_authenticated` field:
  - **Invite-only** (`allow_any_authenticated=False`): Requires `SurveyAccessToken` with `for_authenticated=True` and matching email
  - **Self-service** (`allow_any_authenticated=True`): Any authenticated user can access

**Database Schema:**
```python
class Survey(models.Model):
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.DRAFT,
    )
    allow_any_authenticated = models.BooleanField(
        default=False,
        help_text="Allow any authenticated user to access (not just invited users)"
    )

class SurveyAccessToken(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    for_authenticated = models.BooleanField(
        default=False,
        help_text="True if this token is for authenticated user invitation"
    )
    note = models.TextField(blank=True)  # Format: "Invited: email@domain.com"
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
```

**Invitation Flow:**
1. Survey creator enters email addresses (one per line, supports Outlook format)
2. System checks `User.objects.filter(email=email).exists()`
3. Creates `SurveyAccessToken` with `for_authenticated=True`, `note=f"Invited: {email}"`
4. Sends appropriate email:
   - Existing users: Direct link to survey (`send_authenticated_survey_invite_existing_user`)
   - New users: Signup link with redirect (`send_authenticated_survey_invite_new_user`)

**View Logic:**
```python
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take(request, slug):
    survey = get_object_or_404(Survey, slug=slug)

    if survey.visibility == Survey.Visibility.AUTHENTICATED:
        if not request.user.is_authenticated:
            messages.info(request, "Please sign in to take this survey.")
            return redirect("/accounts/login/?next=" + request.path)

        if not survey.allow_any_authenticated:
            # Check for invitation
            token = SurveyAccessToken.objects.filter(
                survey=survey,
                for_authenticated=True,
                note__icontains=f"Invited: {request.user.email}"
            ).first()

            if not token:
                messages.error(request, "You must be invited to access this survey.")
                return redirect("surveys:dashboard")

    return _handle_participant_submission(request, survey, token_obj=None)
```

**Recommended for:** Surveys that collect patient-identifiable or sensitive data.

### Public

**URL:** `/surveys/<slug>/take/`

**Access Control:**
- No authentication required
- Anyone can view and submit
- Must confirm "No patient-identifiable data" at publish time
- Server enforces `no_patient_data_ack=True`

**Protections:**
- CAPTCHA support (hCaptcha)
- Rate limiting via `django-ratelimit`
- CSRF protection

**View Logic:**
```python
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take(request, slug):
    survey = get_object_or_404(Survey, slug=slug)

    if request.method == "POST" and not request.user.is_authenticated and survey.captcha_required:
        if not _verify_captcha(request):
            messages.error(request, "CAPTCHA verification failed.")
            return redirect("surveys:take", slug=slug)

    return _handle_participant_submission(request, survey, token_obj=None)
```

### Unlisted (Secret Link)

**URL:** `/surveys/<slug>/take/unlisted/<unlisted_key>/`

**Access Control:**
- Link not discoverable in navigation or API
- No authentication required
- Must know the secret `unlisted_key`
- Must confirm "No patient-identifiable data" at publish time

**Key Generation:**
```python
import secrets
survey.unlisted_key = secrets.token_urlsafe(24)
survey.save()
```

**View Logic:**
```python
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take_unlisted(request, slug, key):
    survey = get_object_or_404(Survey, slug=slug)

    if survey.visibility != Survey.Visibility.UNLISTED:
        raise Http404()

    if survey.unlisted_key != key:
        raise Http404()

    return _handle_participant_submission(request, survey, token_obj=None)
```

### Invite Token (One-time Codes)

**URL:** `/surveys/<slug>/take/token/<token>/`

**Access Control:**
- Token-based access
- No authentication required (anonymous)
- One-time-use (marked used after submission)
- Optional expiry per token
- Must confirm "No patient-identifiable data" at publish time

**Token Structure:**
```python
class SurveyAccessToken(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.TextField(blank=True)
    for_authenticated = models.BooleanField(default=False)

    def is_valid(self):
        if self.used_at:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
```

**Token Generation:**
```python
import secrets

token = SurveyAccessToken(
    survey=survey,
    token=secrets.token_urlsafe(24),
    created_by=request.user,
    expires_at=end_at if end_at else None,
    note=f"Invited: {email_address}",
    for_authenticated=False,
)
token.save()
```

**View Logic:**
```python
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take_token(request, slug, token):
    survey = get_object_or_404(Survey, slug=slug)

    if survey.visibility != Survey.Visibility.TOKEN:
        raise Http404()

    token_obj = get_object_or_404(SurveyAccessToken, token=token, survey=survey)

    if not token_obj.is_valid():
        messages.error(request, "This invitation link is invalid or has already been used.")
        return redirect("surveys:closed", slug=slug)

    return _handle_participant_submission(request, survey, token_obj=token_obj)
```

**Export:**
CSV export includes: token, created_at, expires_at, used_at, used_by, note

## Patient-Identifiable Data Safeguard

When using Public, Unlisted, or Invite Token modes, publishers must acknowledge that the survey does not collect patient-identifiable data:

```python
# Enforced server-side
if visibility in [Survey.Visibility.PUBLIC, Survey.Visibility.UNLISTED, Survey.Visibility.TOKEN]:
    if not no_patient_data_ack:
        messages.error(request, "You must confirm no patient data is collected.")
        return redirect("surveys:publish_settings", slug=slug)
```

If your survey collects sensitive demographics, use the **Authenticated** mode so responses are tied to authenticated users and protected accordingly.

**Encryption:** All demographic fields are encrypted per-survey. The decryption key is handled server-side and never exposed in public pages or APIs.

## Security Protections

### CSRF Protection

All forms include CSRF tokens. Session cookies set with `Secure` and `HttpOnly` flags in production:

```python
# settings.py
SESSION_COOKIE_SECURE = True  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
CSRF_COOKIE_SECURE = True
```

### Content Security Policy (CSP)

Strict CSP via `django-csp`:

```python
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com")
CSP_FRAME_SRC = ("https://hcaptcha.com", "https://*.hcaptcha.com")
CSP_STYLE_SRC = ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com")
CSP_CONNECT_SRC = ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com")
```

Static assets served by WhiteNoise with compression and caching.

### Rate Limiting

Applied to participant submission endpoints:

```python
@ratelimit(key="ip", rate="10/m", block=True)
def survey_take(request, slug):
    # ...
```

### Brute-Force Protection

Login attempts protected by `django-axes`:

```python
# settings.py
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"
```

### CAPTCHA (hCaptcha)

**Configuration:**

Set environment variables:
```bash
HCAPTCHA_SITEKEY=your_site_key
HCAPTCHA_SECRET=your_secret_key
```

**Server-side Verification:**
```python
def _verify_captcha(request):
    response = request.POST.get("h-captcha-response")
    if not response:
        return False

    data = {
        "secret": settings.HCAPTCHA_SECRET,
        "response": response,
    }

    verify_response = requests.post(
        "https://hcaptcha.com/siteverify",
        data=data,
    )

    result = verify_response.json()
    return result.get("success", False)
```

**Template:**
```html
{% if survey.captcha_required and not user.is_authenticated %}
    <div class="h-captcha" data-sitekey="{{ HCAPTCHA_SITEKEY }}"></div>
{% endif %}
```

### One-Time Tokens

Tokens are validated and marked used server-side:

```python
def _handle_participant_submission(request, survey, token_obj):
    if request.method == "POST":
        # ... process response ...

        if token_obj and not token_obj.used_at:
            token_obj.used_at = timezone.now()
            if request.user.is_authenticated:
                token_obj.used_by = request.user
            token_obj.save()
```

### Publish Window and Capacity

Guards enforce start/end times and max responses:

```python
def is_live(self):
    from django.utils import timezone
    now = timezone.now()

    if self.status != Survey.Status.PUBLISHED:
        return False

    if self.start_at and self.start_at > now:
        return False

    if self.end_at and now > self.end_at:
        return False

    if self.max_responses and hasattr(self, "responses"):
        if self.responses.count() >= self.max_responses:
            return False

    return True
```

## Email Templates

### Authenticated User Invitations

**Existing users** (`templates/emails/survey_invite_authenticated.md`):
```markdown
# You're invited to complete a survey

Hello,

You've been invited to complete: **{{ survey_name }}**

[Complete Survey]({{ survey_link }})

{% if end_date %}**Please complete by:** {{ end_date }}{% endif %}
```

**New users** (`templates/emails/survey_invite_authenticated_new.md`):
```markdown
# You're invited to join CheckTick and complete a survey

Hello,

You've been invited to complete: **{{ survey_name }}**

[Create Account and Access Survey]({{ signup_link }})
```

**Signup URL format:**
```
/signup/?next=/surveys/{slug}/take/&email={email}
```

### Anonymous Token Invitations

**Standard token** (`templates/emails/survey_invite.md`):
```markdown
# You're invited to complete a survey

Hello,

You've been invited to complete: **{{ survey_name }}**

[Complete Survey]({{ survey_link }})

This is a one-time link. After you complete the survey, the link will no longer work.
```

**Token URL format:**
```
/surveys/{slug}/take/token/{token}/
```

## API Reference

See [API Documentation](/docs/api/) for endpoint details.

**Key endpoints:**
- `POST /api/surveys/{slug}/publish/` - Publish a survey
- `GET /api/surveys/{slug}/tokens/` - List tokens
- `POST /api/surveys/{slug}/tokens/` - Generate tokens
- `GET /api/surveys/{slug}/responses/` - List responses (requires permissions)

## Troubleshooting

### "Submission blocked: CAPTCHA required"

1. Verify environment variables are set:
   ```bash
   echo $HCAPTCHA_SITEKEY
   echo $HCAPTCHA_SECRET
   ```

2. Check CSP allows hCaptcha domains

3. Verify widget renders in browser console

4. Test with curl:
   ```bash
   curl -X POST https://hcaptcha.com/siteverify \
     -d "secret=YOUR_SECRET" \
     -d "response=TEST_RESPONSE"
   ```

### "Survey not live"

Check in Django shell:
```python
from checktick_app.surveys.models import Survey
survey = Survey.objects.get(slug="your-slug")

print(f"Status: {survey.status}")
print(f"Start: {survey.start_at}")
print(f"End: {survey.end_at}")
print(f"Max responses: {survey.max_responses}")
print(f"Current responses: {survey.responses.count()}")
print(f"Is live: {survey.is_live()}")
```

### "Token invalid or used"

Check token status:
```python
from checktick_app.surveys.models import SurveyAccessToken
token = SurveyAccessToken.objects.get(token="your-token")

print(f"Used at: {token.used_at}")
print(f"Expires at: {token.expires_at}")
print(f"Is valid: {token.is_valid()}")
```

## Related Documentation

- [Publish & Collect Responses](/docs/publish-and-collection/) - User-friendly guide
- [Authentication and Permissions](/docs/authentication-and-permissions/) - Access control
- [API Reference](/docs/api/) - API endpoints and protections
- [Survey Progress Tracking](/docs/survey-progress-tracking/) - Auto-save functionality
