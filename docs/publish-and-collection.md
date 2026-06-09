---
title: Publish & Collect Responses
category: features
priority: 7
---

# Publish & Collect Responses

When you're ready to share your survey, CheckTick offers multiple ways to publish it based on your security needs and audience. This guide helps you choose the right approach for your survey.

## Getting Started

From your survey dashboard, click **Publish Settings** to configure:

- **When it's available**: Set start and end dates (optional)
- **How many responses**: Set a maximum number of responses (optional)
- **Who can access it**: Choose a visibility mode (see below)
- **Security features**: Enable CAPTCHA for anonymous surveys

## Question Order, Preview, and Live Publication

Question-group order is now consistent across authoring and participant views.

- The **Survey Map** on the `/groups/` page is the source of truth for display sequence.
- Group order comes from `survey.style.group_order` (set when users reorder groups), with a safe fallback for missing/stale IDs:
  1. groups explicitly listed in `group_order`
  2. any remaining groups sorted by name (A→Z)
- **Preview** (`/surveys/{slug}/preview/`) and **live survey routes** (`/take/`, `/take/unlisted/...`, `/take/token/...`) use the same runtime ordering and branching configuration.
- Publishing does **not** reshuffle questions/groups; publication uses the current authored structure.

## Choosing a Visibility Mode

CheckTick provides four ways to share your survey, from most secure to most open:

### 1. Authenticated Users (Most Secure)

**Best for:** Healthcare surveys, research studies, internal assessments

**How it works:**

- Only people with CheckTick accounts can access your survey
- Participants must log in before completing
- You can invite specific people by email, or allow any authenticated user
- Perfect for surveys with patient-identifiable or sensitive data

**Two access options:**

**Invite-Only Mode** (default):

- Paste email addresses into the invitation box (one per line)
- Outlook contact format is supported: `John Smith <user@example.com>`
- System checks if each person has a CheckTick account:
  - **Existing users** get a direct link to the survey
  - **New users** get a signup link that redirects to the survey after registration
- Track who was invited and who completed the survey
- Resend invitations from the dashboard if needed

**Self-Service Mode**:

- Check "Allow any authenticated user to access"
- Any logged-in user can access the survey
- No invitation required, but users still need an account
- Good for public surveys that need accountability

### 2. Anonymous with Invite Codes

**Best for:** Controlled distribution without requiring accounts

**How it works:**

- Generate unique one-time codes for each participant
- Share links like: `/surveys/your-survey/take/token/ABC123/`
- Each code works only once
- Participants don't need to create an account
- You can set expiry dates and export usage data

**When to use:**

- You want to control who can access the survey
- You don't need to know participants' identities
- You want to track individual completion without accounts

**Note:** Must confirm that your survey doesn't collect patient-identifiable data.

### 3. Unlisted (Secret Link)

**Best for:** Semi-private surveys with known audience

**How it works:**

- Get a secret link like: `/surveys/your-survey/take/unlisted/secret-key/`
- Anyone with the link can complete the survey
- Link is not discoverable on your site or through the API
- No account required

**When to use:**

- Sharing with a specific group (e.g., email list, internal team)
- You trust recipients not to share the link publicly
- You don't need to track individual access

**Note:** Must confirm that your survey doesn't collect patient-identifiable data.

### 4. Public (Fully Open)

**Best for:** General feedback, public surveys, anonymous data collection

**How it works:**

- Survey is openly accessible at: `/surveys/your-survey/take/`
- Anyone can complete it without an account
- Recommended to enable CAPTCHA to prevent spam
- Rate limiting is automatically enabled

**When to use:**

- Public feedback forms
- Anonymous surveys where you want maximum participation
- Non-sensitive data collection

**Note:** Must confirm that your survey doesn't collect patient-identifiable data.

## Publishing Multiple Languages

If you've created translations of your survey, you can publish them independently or together.

### How language versions work

- Each translation has its own publication status (draft or published)
- Translations share the same visibility settings as the original survey
- When published, each language is accessible at the same URL - the system detects the user's browser language or allows manual language selection

### Publishing translations

From the Publish Settings page:

1. **Published translations** section shows live versions:
   - View published translations
   - Each has a view link to the live survey
   - Cannot unpublish once live

2. **Draft translations** section shows unpublished versions:
   - Review draft translations using preview links
   - Check "Publish together" to publish multiple languages at once
   - Click "Publish selected translations" to make them live

### Important before publishing translations

**Always have a native speaker review AI-generated translations**, preferably:

- A healthcare professional who speaks the target language
- Someone familiar with medical terminology in that language
- Someone from the target cultural community

**Check for:**

- Medical terminology accuracy
- Cultural appropriateness of questions
- Proper formality level for healthcare context
- Correct translation of technical terms
- Appropriate phrasing for sensitive topics

**Testing:**

- Use the preview link to test the complete survey flow
- Have team members review the translation
- Consider pilot testing with a small group of native speakers

### Language selection for respondents

When multiple languages are published:

- The survey detects the user's browser language preference
- A language selector appears if multiple languages are available
- Respondents can switch languages during survey completion
- Progress is maintained when switching languages

For details on creating translations, see [Multi-language surveys](/docs/surveys/#multi-language-surveys).

## Protecting Patient Data

When your survey collects patient-identifiable information:

✅ **Use Authenticated visibility mode**

- Links responses to verified user accounts
- Provides full audit trail
- Enables proper data governance
- Meets healthcare compliance requirements

❌ **Don't use** Public, Unlisted, or Anonymous Invite Codes

- These modes require confirmation that no patient data is collected
- System enforces this protection when publishing

All demographic fields are automatically encrypted. The encryption keys are managed server-side and never exposed in public pages.

## Managing Your Published Survey

### Survey Status

- **Draft**: Only visible to you while building
- **Published**: Live and accepting responses
- **Closed**: No longer accepting responses, but you can still view data

### Time Windows

Set optional start and end dates to automatically control when your survey is available. The dashboard shows clear status badges so you always know if your survey is live.

### Response Limits

Set a maximum number of responses. When reached, the survey automatically closes to new submissions.

### Tracking Progress

Your dashboard shows:

- Current status and visibility mode
- Total responses received
- Today's responses
- Last 7 days activity
- Time remaining (if end date is set)

### QR Codes

CheckTick can generate QR codes for your survey links, making it easy to share surveys in printed materials, posters, or presentations.

**QR codes in email invitations:**

When sending invitations (Authenticated or Token modes), you can include a QR code in each email:

1. In the Publish Settings, look for the "Include QR code in invitation emails" checkbox
2. This is enabled by default
3. Each recipient gets a unique QR code linking to their survey access

**QR codes on the dashboard:**

For Public and Unlisted surveys, a QR button appears next to the "Copy Survey Link" button:

1. Click the QR icon to view the QR code
2. Download it as a PNG file
3. Use it in posters, handouts, or presentations

**QR codes for individual tokens:**

On the Invite Tokens management page, each token has a QR button:

1. Click the QR icon to view the code for that specific token
2. Download and print for individual distribution
3. Each QR code is unique to that token

**QR codes for authenticated invites:**

On the Invitations page, pending invitations show a QR button:

1. Click to view the QR code for that invitation
2. Useful for giving to participants in person
3. Reminds them to log in with the invited email address

**Best practices:**

- Test the QR code works before printing
- Include a short URL alongside the QR for accessibility
- Ensure sufficient size (at least 2cm × 2cm for reliable scanning)
- Use high contrast printing

### Managing Invitations (Authenticated & Token modes)

From your dashboard:

- View pending invitations
- See who has completed the survey
- Resend invitations to non-responders
- Export invitation data to CSV

## Participant Experience

### Progress Saving

Participants can save their progress and resume later. This is especially helpful for longer surveys. See [Survey Progress Tracking](/docs/survey-progress-tracking/) for details.

### Completion

After submitting, participants see a customizable thank-you page. You can include:

- Confirmation message
- Next steps
- Contact information
- Custom branding

## Security Features

CheckTick includes enterprise-grade security:

- **CSRF protection** on all forms
- **Rate limiting** to prevent abuse
- **CAPTCHA support** (hCaptcha) for anonymous surveys
- **Brute-force protection** on login attempts
- **Encrypted data storage** for sensitive information
- **One-time invite codes** that can't be reused
- **Secure session handling** in production

## Quick Start Guide

**For maximum security (healthcare/research):**

1. Choose **Authenticated** visibility
2. Leave "Allow any authenticated user" **unchecked**
3. Paste email addresses to invite
4. Publish!

**For controlled anonymous surveys:**

1. Choose **Anonymous with Invite Codes**
2. Generate codes for your participants
3. Confirm no patient data collected
4. Enable CAPTCHA
5. Publish!

**For public feedback:**

1. Choose **Public** visibility
2. Confirm no patient data collected
3. Enable CAPTCHA
4. Set end date if needed
5. Publish!

## Troubleshooting

**"Survey not live"**

- Check status is **Published** (not Draft or Closed)
- Verify you're within the start/end date window
- Check if maximum responses has been reached

**"Need to log in" (Authenticated mode)**

- This is correct! Participants need accounts for authenticated surveys
- New users will be prompted to create an account
- Invitation emails include clear instructions

**"Invalid or used token"**

- Tokens can only be used once
- Generate a new token for the participant
- Check if the token has expired

**"Groups appear in different order in preview vs live"**

- Preview and live now share the same ordering pipeline.
- Recheck the order in **Groups** (Survey Map reflects runtime order).
- If order still looks wrong after major edits (clone/import/translation), save group order again from `/groups/` to refresh `group_order` state.

**"CAPTCHA failed"**

- Ensure CAPTCHA is properly configured (see technical docs)
- Participant may need to try again
- Check browser isn't blocking the CAPTCHA widget

## Related Documentation

- [Survey Progress Tracking](/docs/survey-progress-tracking/) - Auto-save and resume functionality
- [Authentication and Permissions](/docs/authentication-and-permissions/) - User access control
- [Branding & Theme Settings](/docs/branding-and-theme-settings/) - Customize the look of your surveys
- [Publishing Surveys (Technical)](/docs/publishing-surveys/) - API and technical details
