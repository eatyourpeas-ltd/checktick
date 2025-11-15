# Survey Progress Tracking

CheckTick includes a survey progress tracking feature that allows users to save their progress while completing surveys and resume later. This feature works with all survey access methods and provides a visual progress bar to help respondents track their completion.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [User Experience](#user-experience)
- [Technical Implementation](#technical-implementation)
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

## Maintenance

### Automatic Cleanup

Progress records are automatically cleaned up to prevent database bloat:

- Records expire after **30 days** from last update
- Very old records (>90 days) are deleted as a safety net
- Cleanup runs via the `cleanup_survey_progress` management command

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

- **Manual save button** for users who want explicit control
- **Multiple save points** for very long surveys
- **Progress synchronization** across devices for authenticated users
- **Offline support** using service workers
- **Progress notifications** ("You're 50% complete!")
- **Configurable expiry** per survey (instead of fixed 30 days)
- **Progress analytics** for survey creators (where users drop off)

---

## Related Documentation

- [Surveys](surveys.md) - Creating and managing surveys
- [Data Governance](data-governance.md) - Data retention and deletion policies
- [Authentication and Permissions](authentication-and-permissions.md) - User access control
- [Self-Hosting Scheduled Tasks](self-hosting-scheduled-tasks.md) - Scheduling cleanup commands

---

**Last Updated**: November 2025
**Feature Version**: 1.0
**Status**: Production Ready
