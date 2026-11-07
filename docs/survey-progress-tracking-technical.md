---
title: Survey Progress Tracking (Technical)
category: development
priority: 16
---

Technical reference for the survey progress tracking and resume feature. For the user-facing guide, see [Survey Progress Tracking](survey-progress-tracking.md).

## Overview

CheckTick saves participant progress so they can resume incomplete surveys. The mechanism depends on the survey's visibility mode — each mode has a different participant credential:

| Visibility | Credential | Resume mechanism | Server-side progress? |
|---|---|---|---|
| `authenticated` | User account | Automatic on login (`SurveyProgress.user` FK) | Yes, auto-created |
| `token` | Access token in URL | Automatic on re-accessing the token link (`SurveyProgress.access_token` FK) | Yes, auto-created |
| `public` / `unlisted` | None | Explicit resume token (opt-in) | **No, unless participant opts in** |

## Data Model

### `SurveyProgress`

```python
class SurveyProgress(models.Model):
    survey = models.ForeignKey(Survey, related_name="progress_records")
    user = models.ForeignKey(User, null=True, blank=True)          # authenticated
    session_key = models.CharField(max_length=40, null=True, blank=True)  # anonymous
    access_token = models.ForeignKey(SurveyAccessToken, null=True, blank=True)  # token surveys

    # Progress data
    partial_answers = models.JSONField(default=dict)
    current_question_id = models.IntegerField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    answered_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_question_answered_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()  # 30-day auto-cleanup

    # Resume token (public surveys only)
    resume_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=True, blank=True)

    # Lifecycle
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        ABANDONED = "abandoned"
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    # Resume position inside a repeat instance
    current_repeat_index = models.PositiveIntegerField(null=True, blank=True)

    # Section menu selection (for the planned section_menu layout)
    selected_group_ids = models.JSONField(default=list, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
```

### `Survey` toggles

```python
class Survey(models.Model):
    ...
    allow_resume = models.BooleanField(default=True)
    allow_response_redaction = models.BooleanField(default=True)
```

### `SurveyResponse.receipt_token`

The `receipt_token` field (nullable, indexed, unique) holds a short,
participant-friendly code (8-character Crockford base32 — no I/L/O/U) so
it can be copied or read out like a 2FA token. The column was migrated
from UUIDField to CharField (0075); pre-existing UUID values remain valid
strings. See `generate_receipt_token()` below.

## Resume Model by Access Tier

### Authenticated surveys

`_get_or_create_progress` in `views.py` creates a `SurveyProgress` row keyed on `request.user`. The unique constraint `one_progress_per_user_per_survey` enforces one active row per user per survey. On any subsequent login (including from a new device), the participant resumes where they left off.

### Token surveys

A `SurveyProgress` row is created keyed on the `SurveyAccessToken` and the session. Re-accessing the token URL resumes the survey. The token is the credential — no separate resume token is needed.

### Public and unlisted surveys (behaviour change)

Public and unlisted surveys **do not auto-save** progress server-side. This is a deliberate privacy change from the previous behaviour:

- No `SurveyProgress` row is created automatically.
- `_get_or_create_progress` returns `(None, False)` for public/unlisted surveys with no participant credential.
- The draft-save AJAX handler returns `server_save_disabled: True` so the client knows to use `localStorage`.
- Crash recovery uses client-side `localStorage` (the JS is not yet wired up — the backend actions exist and return JSON).
- The only server-side persistence is an explicit, opt-in resume token.

Rationale: public surveys have no participant credential, so any server-side progress row is protected only by the session cookie — weak, and a PHI retention liability on shared computers.

## Resume Tokens

### Issuance (`save_resume` action)

When a public-survey participant clicks "Save and come back later", the `save_resume` POST action:

1. Checks `survey.allow_resume` — returns 403 if disabled.
2. Looks for an existing `SurveyProgress` row by `session_key` (so a second click reuses the same token).
3. If none exists, creates one with a `resume_token` (UUID) and the current answers.
4. Returns the resume URL as JSON: `{"success": true, "resume_url": "...", "resume_token": "..."}`.

### Resume route (`/take/resume/<uuid:resume_token>/`)

`survey_take_resume` in `views.py`:

1. Calls `SurveyProgress.find_by_resume_token(token)` — returns `None` if the token is invalid, expired, or the row is not `IN_PROGRESS`.
2. If `None`, renders `surveys/resume_expired.html` with a 404 status — never reveals whether the token existed.
3. Rejects tokens for authenticated/token surveys (resume tokens are only for public/unlisted).
4. Delegates to `_handle_participant_submission` with the progress record passed in.

### Destruction on submit

`progress.mark_completed()` sets `status = COMPLETED`, `completed_at = now()`, and `resume_token = None`. The token is invalidated — its job is done. The row is kept briefly for audit, then swept by the retention job.

## Opt-Out Tokens

### `generate_receipt_token()`

```python
def generate_receipt_token(self) -> str | None:
    if not self.is_pseudonymous:
        # Anonymous response — only issue a token when the survey
        # allows redaction (publication-time toggle).
        if not getattr(self.survey, "allow_response_redaction", True):
            return None
    if not self.receipt_token:
        self.receipt_token = self._new_receipt_token()
        self.save(update_fields=["receipt_token"])
    return self.receipt_token
```

- Pseudonymous responses (authenticated/token): token issued automatically.
- Anonymous responses (public/unlisted): token issued automatically when
  `survey.allow_response_redaction=True` — no opt-in step (issue #376:
  every participant of a redaction-enabled survey is shown the token on
  the thank-you page).
- The token is a short code (`_new_receipt_token`, 8 chars, unique) shown
  once on the thank-you page and used with the existing
  `DataSubjectRequest.find_by_receipt_token()` workflow.

### Submit handler

The submit handlers (linear, matrix final submit, diary entry) call
`generate_receipt_token()` on the saved response:

```python
token = resp.generate_receipt_token()
if token:
    request.session[f"receipt_token_{survey.slug}"] = str(token)
```

The thank-you page displays the token from the session (one-time display)
with a copy button and a warning that it will not be shown again.

## Email Delivery of Tokens

Both resume and opt-out tokens can be emailed to the participant. The privacy contract:

- **The email address is not stored server-side.** No model field, no log line, no audit row.
- The address is accepted in the POST body, passed to `send_token_email()`, and falls out of scope.
- The `RedactionFilter` catches emails in logs as a safety net, but the sending code must not rely on it.
- The log entry records only `survey_id`, `token_type`, and `sent` status — never the address.

### `send_token_email()` in `email_utils.py`

```python
def send_token_email(to_email, survey_name, token_url, token_type) -> bool:
    # Builds a markdown email with the token URL and survey name.
    # Delegates to send_branded_email(). No email address stored.
```

### `email_token` POST action

Accepts `email`, `token_type` ("resume" or "opt_out"), and looks up the token:

- For resume tokens: looks up `SurveyProgress` by `session_key`.
- For opt-out tokens: reads `receipt_token` from the session.

## Publication Workflow Toggles

Two checkboxes in the publish settings page control the feature:

- **`allow_resume`** (default True): when False, no `SurveyProgress` row is created for any access tier, no resume token is issued, and the participant must complete in a single session.
- **`allow_response_redaction`** (default True): when False, anonymous public/unlisted responses get no token at submission and the thank-you page shows no token block, so they cannot be linked for redaction. Pseudonymous responses are unaffected (they issue a `receipt_token` regardless of this toggle, matching the original DSR design).

Both are wired into:
- `survey_publish_settings` view (publish and save actions)
- `_apply_pending_publish_settings` (encryption-setup redirect path)
- `pending_publish` session dict

## Lifecycle: `mark_completed` vs `delete`

The submit handler now calls `progress.mark_completed()` instead of `progress.delete()`:

```python
def mark_completed(self) -> None:
    self.status = self.Status.COMPLETED
    self.completed_at = timezone.now()
    self.resume_token = None  # invalidate the resume token
    self.save(update_fields=["status", "completed_at", "resume_token"])
```

The row is kept with `status=COMPLETED` for audit, then swept by the retention job. The retention job (`cleanup_survey_progress`) sets `status=ABANDONED` before deleting expired rows, so dashboards can distinguish drop-off from active progress.

## Resuming Inside Branching and Repeats

### Branching on resume

`current_question_id` is the last question the participant saw, not necessarily the next one. On resume:

1. Load stored `partial_answers`.
2. Re-run `should_show_question` for `current_question_id` against stored answers.
3. If still visible, land there.
4. If now hidden, advance forward through the branching config to the first visible question.
5. If no visible question remains, treat the survey as complete.

This reuses the existing `branching.py` evaluation and the same ordering pipeline (`_resolved_group_order_ids` + `_order_questions_by_group`), preserving the **Survey Map = Preview = Live** contract.

### Repeats on resume

`current_repeat_index` identifies which instance of a repeating section the participant was on. On resume:

- The instance at `current_repeat_index` is rendered with stored answers.
- If the participant had fewer instances (e.g. deleted one), clamp to the highest valid index.
- "Add another" still works after resume.

## Logging

Per the project's logging rules (medical application, never log patient data or request bodies):

- Resume events log only: `resume_token` (UUID), `status` transition, `survey_id`.
- Email delivery logs only: `survey_id`, `token_type`, `sent` status. **Never the email address.**
- Never log `partial_answers`, `selected_group_ids`, or any question text.

## Test Coverage

Tests live in `checktick_app/surveys/tests/test_resume_redaction.py` (41 tests) and `checktick_app/surveys/tests/test_progress_tracking.py`.

Key test scenarios:

- Model fields and defaults (resume_token, status, current_repeat_index, selected_group_ids, completed_at)
- Status transitions (mark_completed, mark_abandoned, is_expired, find_by_resume_token)
- Publication workflow toggle (publish, save, disable resume, disable redaction)
- Public survey behaviour change (no auto-save, server_save_disabled response)
- Save and come back later (token creation, reuse, disabled when allow_resume=False)
- Resume route (valid token, invalid token, expired token, completed token, authenticated survey rejection)
- Opt-out/redaction token (issued automatically for anonymous responses when the toggle is on, None when disabled, pseudonymous responses still get a token, short 8-character code format, thank-you page one-time display)
- Email delivery (sends email, invalid email rejected, no token available error, address not stored in any model)
- Submit marks completed (not deleted), resume token invalidated

## Migration

Migration `0059_progress_resume_and_redaction_fields` adds the new fields and backfills `resume_token` for existing rows (two-step: add nullable, backfill UUIDs, add unique constraint — the standard Django pattern for unique callable defaults).

## Related Documentation

- [Survey Progress Tracking](survey-progress-tracking.md) — user-facing guide
- [Survey Layouts (Technical)](survey-layouts-technical.md) — the section_menu layout that depends on `selected_group_ids`
- [Branching Technical Guide](branching-technical.md) — `should_show_question`, ordering pipeline
- [Publishing Surveys (Technical)](publishing-surveys.md) — visibility modes and publish settings
- [Data Governance](data-governance.md) — retention and deletion policies
