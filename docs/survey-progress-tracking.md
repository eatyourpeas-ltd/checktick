---
title: Survey Progress Tracking
category: features
priority: 8
---

CheckTick saves your progress automatically as you fill out a survey, so you can leave and come back without losing your work. How this works depends on how the survey creator has published the survey.

## How Progress Saving Works

### Authenticated surveys (login required)

If the survey requires you to log in, your progress is saved to your account automatically. You can leave the survey, come back on a different device, log in, and continue where you left off. No special link is needed — just return to the survey URL.

### Invite token surveys (one-time codes)

If you accessed the survey via a unique invite link, your progress is saved automatically while you use that link. If you close the browser and return to the same link (in the same browser), your answers are restored. You don't need a separate resume link — the invite link itself is your way back.

### Public and unlisted surveys (open links)

For public surveys, CheckTick does **not** save your answers to its servers automatically. This protects your privacy — there is no account or token linking you to your partial answers, so nothing is stored on a shared or public computer unless you choose to save it.

Instead:

- **Crash recovery** uses your browser's local storage. If your browser crashes or you accidentally close the tab, your answers are still there when you reopen the survey in the same browser. This data never leaves your device.
- **Save and come back later** is an explicit choice. If you want to save your progress on CheckTick's servers so you can resume from a different device or after clearing your browser data, click the **"Save and come back later"** button. You'll receive a unique resume link that is valid for 30 days. Your answers are stored against that link and deleted when you submit the survey.

> **Privacy note:** The resume link is the only way back to your saved answers. If you lose it, we cannot recover your progress. Anyone with the link can resume your survey, so keep it private.

## The Progress Bar

A progress bar appears at the top of each survey showing:

- **Completion percentage** (0–100%)
- **Question count** (e.g., "15 of 50 questions answered")
- **Save status** ("Saved", "Saving…", or "Save failed")
- **Last saved timestamp** (e.g., "Last saved: 2 minutes ago")

For public surveys where server-side saving is not active, the progress bar shows your local progress (from browser storage) but does not show a "last saved to server" timestamp.

## Save and Come Back Later (Public Surveys)

If you're completing a public survey and want to save your progress to come back later — perhaps on a different device — click **"Save and come back later"**.

You'll see:

- A unique **resume link** (e.g., `https://checktick.uk/take/resume/abc123…`)
- A warning that this link is the only way back to your answers
- An option to **email the link to yourself**

### Emailing the link

If you choose to email the link to yourself:

- CheckTick sends the email immediately and does **not** store your email address on its servers
- The email contains only the resume link and the survey name — no answers, no question text
- You will not receive any further emails from CheckTick about this survey

### When you return

When you click the resume link, your saved answers are restored and you continue where you left off. The link is valid for 30 days from when you created it, or until you submit the survey (whichever comes first). After you submit, the link stops working.

## Opt-Out Tokens (After Submission)

After you submit a public survey, you may be offered an **opt-out token** on the thank-you page. This is a unique code that lets you request deletion of your response later.

### How it works

1. After submitting, you see a checkbox: "Give me a token so I can request deletion later"
2. If you tick it, a token is generated and shown once
3. Copy the token and keep it safe — it will not be shown again
4. You can also choose to email the token to yourself (same privacy contract as the resume link: your email address is not stored)
5. If you later want your response deleted, contact the survey creator and give them the token

### If you're not offered a token

The survey creator may have disabled opt-out tokens for this survey. In that case, your response is fully anonymous and cannot be linked to you for redaction. This is the original anonymity promise: if no token is offered, your response cannot be identified for deletion.

### If you lose your token

If you lose your opt-out token, we cannot identify your response to delete it. There is no way to recover a lost token — this is the trade-off for the privacy of not collecting your identity.

## Privacy and Data Retention

### Progress records

- Authenticated and token survey progress is deleted when you submit, or expires after 30 days if unused
- Public survey resume tokens expire after 30 days and are deleted on submission
- No progress data is retained beyond these periods

### Opt-out tokens

- Opt-out tokens persist for as long as the survey retains your response (the survey's retention period, typically 6 months after closure)
- The token is a UUID stored on your response record — it does not contain any personal information
- If you submit without opting in, no token is stored and your response is fully anonymous

### Email addresses

- Email addresses provided for token delivery are **never stored** on CheckTick's servers
- The address is used to send the email immediately and then discarded
- No log entries, audit records, or database fields retain the address

## Troubleshooting

### My progress isn't saving

- **Authenticated survey:** Make sure you're logged in. Progress is tied to your account.
- **Token survey:** Make sure you're using the same invite link. Progress is tied to the link.
- **Public survey:** Progress is saved to your browser, not to CheckTick. If you cleared your browser data or are using a different browser, your local progress is gone. Use "Save and come back later" to save server-side.

### My resume link doesn't work

- The link may have expired (30-day limit)
- You may have already submitted the survey — links are destroyed on submission
- Check that you copied the full link

### I lost my opt-out token

Unfortunately, lost tokens cannot be recovered. Without the token, we cannot identify your response for deletion. This is a deliberate privacy trade-off: the token is the only link between you and your response.

## Related Documentation

- [Publish & Collect Responses](publish-and-collection.md) — how survey visibility affects progress saving
- [Survey Progress Tracking (Technical)](survey-progress-tracking-technical.md) — developer reference
- [Data Governance](data-governance.md) — data retention and deletion policies
- [Privacy Notice](privacy-notice.md) — your privacy rights as a survey respondent
