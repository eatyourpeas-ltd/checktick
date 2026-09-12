---
title: Survey Progress Tracking
category: features
priority: 8
---

CheckTick includes a survey progress tracking feature that allows users to save their progress while completing surveys and resume later. This feature works with all survey access methods and provides a visual progress bar to help respondents track their completion.

> **Two layers, three access tiers.** This document describes the
> **auto-save** layer that is already in production, and a planned
> **explicit resume-link** layer. The planned layer behaves differently
> for authenticated, token, and public surveys — see §Resume Model by
> Access Tier. Sections marked **[Planned]** describe work that is
> designed but not yet implemented. See [Survey Layouts](survey-layouts.md)
> for the layout feature that depends on this work.
>
> **Behaviour change for public surveys [Planned].** Today, public and
> unlisted surveys auto-save partial answers server-side (keyed to the
> Django session cookie) for 30 days. The planned layer **removes** this
> default for public surveys: no server-side storage unless the
> participant explicitly clicks "Save and come back later" and accepts a
> resume token. Crash recovery moves to client-side `localStorage` with
> an inactivity timeout. This is more privacy-preserving than the status
> quo and avoids leaving PHI on shared/public computers. See §Public
> Surveys: Client-Side Storage and Crash Recovery.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [User Experience](#user-experience)
- [Technical Implementation](#technical-implementation)
- [Resume Model by Access Tier [Planned]](#resume-model-by-access-tier-planned)
- [Public Surveys: Client-Side Storage and Crash Recovery [Planned]](#public-surveys-client-side-storage-and-crash-recovery-planned)
- [Resume Tokens and Opt-Out Tokens [Planned]](#resume-tokens-and-opt-out-tokens-planned)
- [Email Delivery of Tokens [Planned]](#email-delivery-of-tokens-planned)
- [Resuming Inside Branching, Repeats, and Section Menus [Planned]](#resuming-inside-branching-repeats-and-section-menus-planned)
- [Publication Workflow Toggle [Planned]](#publication-workflow-toggle-planned)
- [Maintenance](#maintenance)
- [Privacy and Security](#privacy-and-security)

---

## Overview

The survey progress tracking feature automatically saves respondents' answers as they fill out surveys, allowing them to:

- See their completion progress in real-time
- Leave a survey and return later without losing their work
- Have their previous answers automatically restored when they return

This feature is particularly useful for:

- **Long surveys** with many questions
- **Complex medical audits** that may take time to complete
- **Multi-session data collection** where respondents need to gather information
- **Mobile users** who may be interrupted while completing surveys

---

## Features

### Visual Progress Bar

A DaisyUI-styled progress bar appears at the top of each survey showing:

- **Completion percentage** (0-100%)
- **Question count** (e.g., "15 of 50 questions answered")
- **Save status** ("Saved", "Saving...", or "Save failed")
- **Last saved timestamp** (e.g., "Last saved: 2 minutes ago")

### Auto-Save

- Progress is automatically saved **3 seconds after the last change**
- Works with all question types (text, multiple choice, dropdowns, etc.)
- Saves in the background via AJAX without interrupting the user
- Shows real-time feedback of save status

### Answer Restoration

When a user returns to an incomplete survey:

- All previously answered questions are automatically filled in
- Works with all question types:
  - Text and number inputs
  - Radio buttons (single choice)
  - Checkboxes (multiple choice)
  - Dropdown selects
  - Likert scales
  - Yes/No questions

### Works with All Access Methods

Progress tracking supports all three ways to access surveys:

1. **Authenticated surveys** - Progress tied to user account (persists across devices)
2. **Unlisted surveys** - Progress tied to browser session
3. **Token-based surveys** - Progress tied to browser session

---

## How It Works

### For Authenticated Users (Logged In)

When a logged-in user starts a survey:

1. A `SurveyProgress` record is created linked to their user account
2. As they answer questions, progress is saved automatically
3. If they leave and return (even from a different device), their answers are restored
4. Progress is deleted when they successfully submit the survey
5. Unused progress records expire after **30 days**

### For Anonymous Users (Unlisted/Token Links)

When an anonymous user accesses a survey via an unlisted link or token:

1. A `SurveyProgress` record is created linked to their browser session
2. Progress is saved as they answer questions
3. If they close the browser and return (same browser), their answers are restored
4. Progress is deleted when they submit the survey
5. Unused progress records expire after **30 days**

> **[Planned] Behaviour change for public surveys.** The above auto-save
> path will be removed for public/unlisted surveys. See §Resume Model by
> Access Tier.

---

## User Experience

### Starting a Survey

When a user first accesses a survey, they see:

```text
┌────────────────────────────────────────────┐
│ Survey Progress                        0%  │
│ ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ │
│ 0 of 25 questions answered                │
└────────────────────────────────────────────┘
```

### Answering Questions

As the user answers questions:

```text
┌────────────────────────────────────────────┐
│ Survey Progress                       40%  │
│ ████████████████▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ │
│ 10 of 25 questions answered    ✓ Saved    │
└────────────────────────────────────────────┘
```

### Returning to a Survey

When a user returns to an incomplete survey:

- The progress bar shows their current completion percentage
- All previously answered questions are automatically filled in
- They can continue from where they left off

### Submitting a Survey

When the user clicks "Submit":

- The survey is validated and saved
- The progress record is automatically deleted
- They're redirected to the thank you page

---

## Technical Implementation

### Database Model

```python
class SurveyProgress(models.Model):
    survey = ForeignKey(Survey)           # Survey being completed
    user = ForeignKey(User, null=True)    # For authenticated users
    session_key = CharField(null=True)     # For anonymous users
    access_token = ForeignKey(SurveyAccessToken, null=True)

    partial_answers = JSONField()          # Saved answers
    current_question_id = IntegerField()
    total_questions = IntegerField()
    answered_count = IntegerField()

    created_at = DateTimeField()
    updated_at = DateTimeField()
    last_question_answered_at = DateTimeField()
    expires_at = DateTimeField()           # Auto-cleanup after 30 days
```

### API Endpoint

Progress is saved via AJAX POST to the same survey submission endpoint:

```http
POST /surveys/{slug}/take/
Content-Type: application/x-www-form-urlencoded

action=save_draft
q_123=Answer1
q_124=Answer2
...
```

**Response:**

```json
{
  "success": true,
  "progress": {
    "percentage": 40,
    "answered": 10,
    "total": 25
  }
}
```

### JavaScript Auto-Save

The auto-save functionality uses debouncing to avoid excessive saves:

1. User changes an answer
2. Timer starts (3 seconds)
3. If another change occurs, timer resets
4. After 3 seconds of no changes, progress is saved
5. Progress bar updates with new percentage

### Constraints

- **One progress record per user per survey** (for authenticated users)
- **One progress record per session per survey** (for anonymous users)
- Prevents duplicate progress records
- Enforced at the database level

---

## Resume Model by Access Tier [Planned]

> **Status: Design.** Not yet implemented. This section replaces the
> earlier single-tier resume design with a three-tier model that matches
> how each survey visibility already authenticates its participants.

The resume mechanism depends on what credential the participant already
has. There are three cases, mirroring `Survey.Visibility`:

| Survey visibility | Credential | Resume mechanism | Server-side progress row? |
|---|---|---|---|
| `authenticated` | User account | Automatic on login (existing `user` FK on `SurveyProgress`) | Yes, auto-created (unchanged) |
| `token` | Access token in URL | Automatic on re-accessing the token link (existing `access_token` FK) | Yes, auto-created (unchanged) |
| `public` / `unlisted` | None | Explicit resume token, opt-in only | **No, unless participant opts in** |

### Authenticated surveys

Unchanged from today. A `SurveyProgress` row is auto-created keyed to
`request.user`. On any subsequent login (including from a new device), the
participant resumes where they left off. No new token, no new route. The
existing `one_progress_per_user_per_survey` unique constraint enforces
one active session per user per survey.

### Token (invite) surveys

Unchanged from today. A `SurveyProgress` row is auto-created keyed to the
`SurveyAccessToken` (via `access_token` FK) and the session. Re-accessing
the token URL resumes the survey. The token itself is the credential —
no separate resume token is needed. The existing
`one_progress_per_session_per_survey` constraint applies.

### Public surveys (no default server storage)

**Behaviour change.** Today, public and unlisted surveys auto-save
partial answers to a `SurveyProgress` row keyed on the Django session
cookie, retained for 30 days. Under the planned layer this default is
**removed** for public surveys:

- No `SurveyProgress` row is created automatically.
- Partial answers live in the participant's browser (`localStorage`)
  for crash recovery only — see §Public Surveys: Client-Side Storage.
- The only server-side persistence is an explicit, opt-in resume token
  issued when the participant clicks "Save and come back later".
- On submit, the resume token (if any) is destroyed and the progress
  row deleted.

Rationale: public surveys have no participant credential, so any
server-side progress row is protected only by the session cookie —
weak, and a retention liability for PHI on shared computers. Moving to
opt-in server storage means partial answers sit on our servers only
when the participant has explicitly chosen to create a link.

### Why a single-tier resume token doesn't fit

The earlier design proposed a `resume_token` for all surveys. That's
redundant for authenticated and token surveys, where the user FK or the
access token already is the credential. Issuing a separate resume token
in those cases adds a second bearer credential for no benefit. The
resume token is therefore scoped to public surveys only.

## Public Surveys: Client-Side Storage and Crash Recovery [Planned]

For public surveys, crash recovery uses the browser, not the server.

### Storage strategy

- **`localStorage`** keyed by survey slug holds the participant's
  in-progress answers and `current_question_id`.
- `localStorage` survives browser crashes, OS crashes, and tab close
  (within the same browser). It does not survive the user clearing
  browser data, which is the desired property for a public computer.
- No `sessionStorage` — it does not survive a tab close, so a browser
  crash that kills the tab loses the answers.
- No server round-trip on every keystroke. Answers are written to
  `localStorage` on the same 3-second debounce the current auto-save
  uses, but the write is local.

### Inactivity timeout

A 30-minute idle timer on the survey page:

- On expiry, `localStorage` is cleared and the page shows
  "Your session has expired — your answers have been cleared from this
  device."
- Any activity (keypress, click, scroll) resets the timer.
- This addresses the public-computer "walked away" scenario regardless
  of where data is stored — the next person who sits down sees an
  expired, cleared page.

### "Exit survey" button

A prominent button (next to "Save and come back later") that immediately
clears `localStorage` and navigates away. This is the user-controlled
escape hatch for shared computers: the participant explicitly abandons
and the device is left clean.

### What this does not cover

- A participant who walks away *without* the tab timing out and a
  malicious actor who inspects `localStorage` via devtools within the
  30-minute window. This is the same risk as any web session on a shared
  device; the inactivity timeout bounds it. We could add a "clear on tab
  blur" but that would defeat crash recovery for legitimate users who
  switch tabs.
- Cross-device resume for public surveys without a token. By design —
  cross-device resume requires a credential, and the resume token is
  that credential, opt-in.

## Resume Tokens and Opt-Out Tokens [Planned]

Two distinct tokens, two distinct lifecycles, both scoped to public
surveys (authenticated and token surveys already have their credential
and already receive an opt-out `receipt_token` on submit where
pseudonymous).

### Resume token (pre-submission, opt-in)

Issued when a public-survey participant clicks "Save and come back
later":

```text
┌──────────────────────────────────────────────────────────┐
│ Save your progress                                       │
│                                                          │
│ Your answers are saved on our servers. Come back any   │
│ time within 30 days using this link:                     │
│                                                          │
│  https://checktick.example/take/resume/<token>   [Copy] │
│                                                          │
│  ⚠ This link is the only way back to your answers.      │
│     If you lose it, we cannot recover your progress.     │
│                                                          │
│  [ ] Email this link to me                               │
│      [ your.email@example.com          ]                │
│      We do not store your email address.                 │
│                                                          │
│  [ Done ]                                                │
└──────────────────────────────────────────────────────────┘
```

- A `SurveyProgress` row is created with a `resume_token` (UUID) and
  the participant's answers. This is the *only* server-side storage
  path for public surveys.
- The token is a bearer credential — anyone with the link can resume.
  Same threat model as the existing unlisted survey URL.
- **Destroyed on submit.** When the participant submits, the progress
  row is deleted and the resume token is invalidated. The token's job
  is done.
- Expires after 30 days (existing retention window).
- Invalid or expired tokens show a neutral "This link has expired"
  page — never reveal whether the token existed.

### Opt-out token (post-submission, opt-in)

After a public-survey participant submits, the thank-you page offers an
opt-out token. This reuses the existing `receipt_token` pattern on
`SurveyResponse`, extended to public surveys on an opt-in basis.

```text
┌──────────────────────────────────────────────────────────┐
│ Thank you for your response.                             │
│                                                          │
│ Your response has been recorded anonymously.             │
│                                                          │
│  [ ] Give me a token so I can request deletion later     │
│                                                          │
│  If you accept a token, your response can be linked to   │
│  you for the purpose of redaction. If you do not, your   │
│  response stays fully anonymous and cannot be redacted.  │
│                                                          │
│  Your token: 8f3c-...-2a1b              [Copy]           │
│                                                          │
│  ⚠ Keep this safe. If you lose it, we cannot identify    │
│     your response to delete it.                          │
│                                                          │
│  [ ] Email this token to me                              │
│      [ your.email@example.com          ]                │
│      We do not store your email address.                 │
└──────────────────────────────────────────────────────────┘
```

- **Opt-in, not default.** The participant chooses whether to accept a
  token. If they decline, the original anonymity promise stands: the
  response cannot be linked to them and cannot be redacted.
- **Extends `receipt_token` to public surveys.** Today
  `generate_receipt_token()` returns `None` for anonymous responses.
  Under the planned layer, it returns a UUID for public surveys *only*
  when the participant opts in at the thank-you page.
- The token is shown once. If the participant navigates away without
  copying it, it cannot be recovered (we don't store it in the session
  beyond the thank-you page).
- Used with the existing `DataSubjectRequest` workflow — the
  participant contacts the controller, provides the token, and the
  controller locates the response via
  `DataSubjectRequest.find_by_receipt_token()`.

### Why two tokens, not one

A single token could in principle serve both resume and opt-out, but
the lifecycles conflict:

- Resume tokens are **destroyed on submit** — their job is done once
  the response exists.
- Opt-out tokens are **created on submit** and persist for the
  response's lifetime.

Keeping them separate keeps each lifecycle simple and lets us destroy
resume tokens aggressively (no long-lived bearer credentials for
in-progress data).

### Model changes

Add the following fields to `SurveyProgress`. Existing fields and
constraints are unchanged.

```python
class SurveyProgress(models.Model):
    ...
    # [Planned] Resume token for public surveys only. Authenticated and
    # token surveys resume via the user FK / access_token FK and do not
    # need this field populated.
    resume_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, null=True, blank=True,
    )

    # [Planned] Explicit lifecycle. Today "in progress" is inferred
    # from the row existing; this makes it queryable and lets the
    # retention job distinguish abandoned from active.
    status = models.CharField(
        choices=["in_progress", "completed", "abandoned"],
        default="in_progress",
    )

    # [Planned] Resume position inside a repeat instance.
    # current_question_id (existing) identifies the question;
    # this identifies *which* instance of a repeating section.
    current_repeat_index = models.PositiveIntegerField(null=True, blank=True)

    # [Planned] Section menu selection. Only populated for surveys with
    # layout = "section_menu" (see docs/survey-layouts.md). Empty list
    # for linear surveys.
    selected_group_ids = models.JSONField(default=list, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
```

Note: there is **no `resume_email` field**. Email addresses for token
delivery are processed transiently and never persisted — see §Email
Delivery of Tokens.

`SurveyResponse.receipt_token` already exists; the change there is to
allow `generate_receipt_token()` to issue tokens for public surveys when
the participant opts in at the thank-you page (currently it returns
`None` for anonymous responses).

`status` transitions:

- `in_progress` → `completed` on successful submission. Today the row is
  *deleted* on submit; under the new model the row is kept with
  `status = "completed"` and `completed_at = now()` for audit, then swept
  by the retention job. **Migration note:** the submit handler changes
  from `progress.delete()` to
  `progress.status = "completed"; progress.completed_at = now(); progress.save()`.
  For public surveys with a resume token, the token is invalidated at
  the same time (the row is kept briefly for audit then swept).
- `in_progress` → `abandoned` after the retention window with no
  `updated_at` activity. The retention job sets this before deletion so
  dashboards can distinguish "never finished" from "in progress".

### Resume route

A new participant-facing route resolves a `resume_token` to a progress
record and continues the survey:

```
GET /take/resume/<uuid:resume_token>/  →  resumes the survey
```

- Only meaningful for public surveys. Authenticated and token surveys
  resume via their existing credentials and do not use this route.
- The token is the only credential. Anyone with the link can resume —
  same threat model as the existing unlisted survey URL. Do not put PHI
  in the URL itself; the UUID is opaque.
- On load, the route re-evaluates branching against stored answers (see
  §Resuming inside branching) and jumps to the first visible question at
  or after `current_question_id`.
- Invalid or expired tokens show a neutral "This link has expired" page
  — never reveal whether the token existed.

### Concurrency

The existing unique constraints (`one_progress_per_user_per_survey`,
`one_progress_per_session_per_survey`) already prevent duplicate rows
for authenticated and token surveys. For public surveys with resume
tokens, the rule is: **one active `in_progress` row per `resume_token`**.
If a participant clicks "Save and come back later" a second time, the
existing row's token is re-shown rather than a new one created — this
avoids two divergent answer sets.

Implementation: the "save and come back later" handler checks for an
existing `in_progress` row by `resume_token` (stored in the participant's
`localStorage` from the first issuance) before creating a new one.

## Email Delivery of Tokens [Planned]

Both resume tokens and opt-out tokens can be emailed to the participant.
The privacy contract is the same for both:

- **The email address is not stored server-side.** No model field, no
  log line, no audit row, no email-queue retention. The address is
  accepted in the POST body, passed straight to the email backend, and
  falls out of scope when the request completes.
- **The email contains only the token URL and the survey name.** No
  answers, no question text, no participant-identifying content beyond
  what the participant themselves typed.
- **The `RedactionFilter` catches emails in logs as a safety net**, but
  per the project's logging rules the sending code must not rely on it
  — the address must never be passed to `logger` at all.
- **Test requirement:** a test that submits an email address for token
  delivery and asserts that no `EmailField`, log line, or audit row
  contains the address after the request completes.

This is a stronger promise than "we encrypt your email" — it's "we never
keep it." It must be reflected in the privacy notice wording (see
§Privacy documentation updates).

## Resuming Inside Branching, Repeats, and Section Menus [Planned]

Resume is straightforward when a survey is linear and has no repeats. It
gets interesting when the saved position is inside a branch or a repeat
instance. This section sets the contract.

### Branching on resume

`current_question_id` is the *last question the participant saw*, not
necessarily the next one to show. On resume:

1. Load stored `partial_answers`.
2. Re-run `should_show_question` (see
   [Branching Technical Guide](branching-technical.md) §Condition
   Evaluation) for `current_question_id` against the stored answers.
3. If still visible, land there.
4. If now hidden (because the participant changed an earlier answer
   before leaving, or because the author edited a condition), advance
   forward through the branching config's question order to the first
   visible question at or after `current_question_id`.
5. If no visible question remains, treat the survey as complete.

This reuses the existing `branching.py` evaluation; no new branching
action is needed. The only new code is the "advance to next visible"
loop, which must follow the same ordering pipeline
(`_resolved_group_order_ids` + `_order_questions_by_group`) used by
Survey Map, preview, and live — preserving the
**Survey Map = Preview = Live** contract.

### Repeats on resume

`current_question_id` identifies the question but not *which instance* of
a repeating section. Add `current_repeat_index` (above). On resume:

- The repeat instance at `current_repeat_index` is rendered with the
  participant's stored answers for that instance.
- If the participant had added fewer instances than
  `current_repeat_index` (e.g. they deleted one before leaving), clamp to
  the highest valid index and land there.
- "Add another" still works after resume; new instances start empty.

### Section menu selection on resume

For surveys with `layout = section_menu` (see
[Survey Layouts](survey-layouts.md)):

- `selected_group_ids` is stored on the progress row when the
  participant confirms their picker selection.
- On resume, the picker is **skipped** — the participant goes straight to
  their next question. A "Change sections" link in the progress bar
  returns them to the picker if needed.
- Changing the selection after answering is allowed but requires
  confirmation, because deselecting a section discards its answers.
- If the author has lowered `max_selected` since the participant saved,
  the resume flow clamps to the new max and prompts the participant to
  drop a section. Edge case, but covered by a test.

### What is logged

Per the project's logging rules (medical application, never log patient
data or request bodies), resume and token-delivery events log only:

- `resume_token` (the UUID, not the answers)
- `status` transition (e.g. `in_progress` resumed)
- `survey_id`
- For email delivery: the fact that an email was sent, the survey_id,
  and the token type (resume / opt-out). **Never the email address.**

Never log `partial_answers`, `selected_group_ids`, the participant's
email address, or any question text. The JSON formatter will catch some
of these but the resume and email-sending code must not pass them to
`logger` at all.

### Migration notes

- Add the new `SurveyProgress` fields as nullable / defaulted so existing
  rows are valid.
- Backfill `status = "in_progress"` for all existing rows.
- Backfill `resume_token` for existing public-survey `in_progress` rows
  so they can be resumed via the new route immediately. (Authenticated
  and token surveys don't need a resume token — they resume via their
  existing credential.)
- The submit handler changes from deleting the row to setting
  `status = "completed"`. Existing tests that assert the row is deleted
  on submit must be updated to assert `status = "completed"` instead.
- The retention job gains a `status = "abandoned"` step before deletion,
  so dashboards can distinguish drop-off from active progress.
- `SurveyResponse.generate_receipt_token()` is extended to issue tokens
  for public surveys when the participant opts in at the thank-you page.
  Existing public-survey responses (already submitted, no token) are not
  backfilled — they remain anonymous as originally promised.
- **Behaviour change for public surveys:** the auto-save path in
  `_get_or_create_progress` and the `save_draft` AJAX handler must skip
  public/unlisted surveys. Existing tests that assert a `SurveyProgress`
  row is created for a public survey must be updated to assert that no
  row is created unless the participant explicitly opts in.

### Privacy documentation updates (follow-up)

These are board-approved DSPT documents and should be updated alongside
the implementation, not in this design doc:

- `docs/privacy-notice.md` §11.3 (Anonymous vs Pseudonymous) and §11.4
  (Receipt Tokens) — add that participants in some public surveys may
  opt to receive a token, and that this is down to the survey creator
  via the publication-workflow toggle. If no token is offered, the
  original anonymity promise stands.
- `docs/compliance/data-subject-request-procedure.md` §9.1 (DSRs Not
  Applicable) — update to reflect that public surveys *may* now issue
  receipt tokens on an opt-in basis, so DSRs *may* be fulfilable for
  those responses. Surveys where the creator disabled the toggle remain
  in the "DSRs not applicable" category.
- `docs/compliance/opt-out.md` — cross-reference the new opt-out token
  for public surveys.

### Test coverage to add

- Resume via token for public-survey participants.
- Authenticated and token surveys resume via existing credentials, no
  resume token issued.
- Public survey does **not** auto-create a `SurveyProgress` row (the
  behaviour change).
- Public survey with explicit "Save and come back later" creates a row
  with a resume token; second click reuses the same token.
- Resume when `current_question_id` is now hidden by branching →
  advances to next visible.
- Resume inside a repeat instance at the correct index.
- Resume a Section menu survey → picker skipped, `selected_group_ids`
  honoured.
- Author lowers `max_selected` → resume clamps and prompts.
- Expired resume token → neutral error page, no information leak.
- Submit destroys the resume token and deletes/marks-completed the
  progress row.
- Opt-out token offered on thank-you page for public surveys when the
  creator has enabled it; not offered when disabled.
- Opt-out token round-trips through `DataSubjectRequest.find_by_receipt_token()`.
- Email delivery of resume and opt-out tokens: address not present in
  any model field, log line, or audit row after the request completes.
- Inactivity timeout clears `localStorage` after 30 min idle.
- "Exit survey" button clears `localStorage` immediately.
- Retention job sets `status = "abandoned"` before deletion.
- No PHI in resume or token-delivery logs.

## Publication Workflow Toggle [Planned]

A per-survey toggle controls whether the opt-out token is offered to
public-survey participants on the thank-you page. See
[Survey Layouts](survey-layouts.md) §Publication workflow toggle for
the full spec. In summary:

- `Survey.allow_response_redaction` (bool, default `True`).
- Set in the publication workflow, alongside visibility and audience.
- When `True` (default), public-survey participants are offered an
  opt-out token after submit. When `False`, no token is offered and the
  original anonymity promise stands.
- Authenticated and token surveys are unaffected — they already issue a
  `receipt_token` where pseudonymous, regardless of this toggle.

---

## Maintenance

### Automatic Cleanup

Progress records are automatically cleaned up to prevent database bloat:

- Records expire after **30 days** from last update
- Very old records (>90 days) are deleted as a safety net
- Cleanup runs via the `cleanup_survey_progress` management command

Under the planned three-tier model, the scope of this command narrows
for public surveys (only explicit resume-token rows exist) but is
unchanged for authenticated and token surveys. The command itself does
not need to change — it already sweeps by `expires_at` — but its docs
should note that public-survey rows are now rare (opt-in only) rather
than the default.

A separate question was raised about cleanup of *unsubmitted* answers.
Under the planned model this is largely moot for public surveys
(nothing server-side unless the participant opted in), and for
authenticated/token surveys the existing `cleanup_survey_progress`
command already handles expired `in_progress` rows. No new command is
needed; the existing one covers all three tiers.

### Running Cleanup Manually

```bash
# Dry run to see what would be deleted
python manage.py cleanup_survey_progress --dry-run --verbose

# Actually delete expired records
python manage.py cleanup_survey_progress
```

### Scheduling Cleanup

Add to your cron or scheduled tasks to run daily:

```bash
# Run at 2 AM daily
0 2 * * * cd /path/to/checktick && python manage.py cleanup_survey_progress
```

Or for Docker deployments:

```bash
0 2 * * * docker compose exec web python manage.py cleanup_survey_progress
```

### Monitoring in Django Admin

Progress records can be viewed and managed in Django Admin:

1. Log in to Django Admin
2. Navigate to **Surveys > Survey progresses**
3. View, filter, and search progress records
4. See which surveys have incomplete responses
5. Manually delete progress if needed

**Admin List View Shows:**

- Survey name and slug
- User (or "anonymous" for session-based)
- Session key (for anonymous users)
- Answered count / Total questions
- Last updated timestamp
- Expiry date

---

## Privacy and Security

### Data Storage

- **Authenticated users**: Progress is tied to their user account
- **Anonymous users**: Progress is tied to their browser session only
- **Session keys**: Django session keys are used (secure, random tokens)
- **Encrypted surveys**: Progress respects existing encryption (demographics remain encrypted)

> **[Planned] Public surveys:** no server-side storage by default; opt-in
> resume token only. See §Resume Model by Access Tier.

### Data Retention

- Progress records automatically expire after **30 days**
- Users can delete their progress by clearing browser data (for session-based)
- Authenticated users' progress is removed when they submit or after 30 days
- No personally identifiable information is stored beyond what's in the answers

### Security Considerations

- **CSRF protection**: All AJAX saves include CSRF tokens
- **Rate limiting**: Uses existing rate limiting (10 requests/minute per IP)
- **Session validation**: Session keys are validated before saving progress
- **Duplicate prevention**: Database constraints prevent duplicate progress records
- **Auto-expiry**: Old progress is automatically deleted

### GDPR Compliance

Progress tracking is GDPR-compliant:

- **Consent**: Implicit consent when user starts survey
- **Right to erasure**: Progress auto-deletes after 30 days
- **Data minimization**: Only saves answered questions
- **Purpose limitation**: Used only for survey completion
- **Storage limitation**: 30-day expiry enforces this

---

## Troubleshooting

### Progress Not Saving

**Check:**

1. Is JavaScript enabled in the browser?
2. Are browser console errors showing?
3. Is the session valid (for anonymous users)?
4. Is CSRF token present in the form?

**Debug:**

- Open browser developer tools → Network tab
- Look for POST requests with `action=save_draft`
- Check the response status and body

### Answers Not Restoring

**Check:**

1. Is the user using the same browser/session?
2. Has the progress record expired (>30 days)?
3. Did the user clear their browser data?
4. Are question IDs matching?

**Debug:**

- Check Django Admin → Survey progresses
- Verify the `partial_answers` JSON contains the answers
- Check browser console for JavaScript errors

### Performance Issues

If auto-save is causing performance issues:

1. Increase the debounce delay (currently 3 seconds)
2. Check database indexes are present
3. Consider adding database query optimization
4. Monitor AJAX request volume

---

## Future Enhancements

Potential improvements for future versions:

- **Multiple save points** for very long surveys
- **Progress synchronization** across devices for authenticated users
  (largely addressed by the resume-link layer above)
- **Offline support** using service workers
- **Progress notifications** ("You're 50% complete!")
- **Configurable expiry** per survey (instead of fixed 30 days)
- **Progress analytics** for survey creators (where users drop off)

---

## Related Documentation

- [Surveys](surveys.md) - Creating and managing surveys
- [Survey Layouts](survey-layouts.md) - Section menu layout, which depends on resume
- [Branching & Repeats](branching-and-repeats.md) - Branching behaviour on resume
- [Branching Technical Guide](branching-technical.md) - `should_show_question`, ordering pipeline
- [Data Governance](data-governance.md) - Data retention and deletion policies
- [Authentication and Permissions](authentication-and-permissions.md) - User access control
- [Self-Hosting Scheduled Tasks](self-hosting-scheduled-tasks.md) - Scheduling cleanup commands

---

**Last Updated**: September 2026
**Feature Version**: 1.2 (auto-save in production; three-tier resume + opt-out tokens in design)
**Status**: Production Ready (auto-save) · In Design (resume + opt-out tokens)
