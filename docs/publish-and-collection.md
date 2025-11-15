# Publish & Collect Responses

This guide explains how to publish a survey, the different participation modes (Authenticated, Public, Unlisted, Invite Token), and the security protections applied at each step.

## Lifecycle: status and window

- Status: `draft`, `published`, `closed`
  - Draft: builder-only. Participant routes are disabled.
  - Published: participant routes are enabled, subject to visibility rules and time/response limits.
  - Closed: submissions disabled, preview remains read-only.
- Window: optional `Start at` and `End at` datetimes further restrict when a survey is live.
- Capacity: optional `Max responses` caps total accepted responses.

The dashboard shows badges for Status, Visibility, Window, and Total responses, plus simple analytics (Today, Last 7 days).

## Visibility modes (how participants complete a survey)

All participant pages are server-rendered (SSR). The exact URL depends on the visibility you choose:

### Authenticated

- URL: `/surveys/<slug>/take/`
- Requires a logged-in account. Enforced by session auth + CSRF.
- Recommended for surveys that include patient-identifiable data (see below).

### Public

- URL: `/surveys/<slug>/take/`
- Anyone can view and submit without an account. You must confirm “No patient-identifiable data.”
- Recommended: enable CAPTCHA and rate limiting (defaults are already on).

### Unlisted (secret link)

- URL: `/surveys/<slug>/take/unlisted/<unlisted_key>/`
- Link is not discoverable in navigation or the API; only users with the key can access.
- Anyone with the link can submit without an account. You must confirm “No patient-identifiable data.”

### Invite token (one-time codes)

- Flow:
  - Generate tokens from Dashboard → Publish settings → Manage invite tokens
  - Distribute links: `/surveys/<slug>/take/token/<token>/`
  - Each token is one-time-use; after a successful submission it is marked used.
- Optional expiry per token batch. CSV export is available.
- You must confirm “No patient-identifiable data.” if submissions are anonymous.

See also: docs/authentication-and-permissions.md for broader access control.

## Patient-identifiable data safeguard

When using Public, Unlisted, or Invite token modes, publishers must acknowledge that the survey does not collect patient-identifiable data. This is enforced on the server; if your survey collects sensitive demographics, prefer the Authenticated mode so responses are tied to authenticated users and protected accordingly.

Demographic fields are encrypted per-survey; the decryption key is handled server-side and never exposed in public pages or APIs.

## Security protections

- CSRF protection and secure session cookies (production: Secure/HttpOnly)
- Strict Content Security Policy (CSP) via django-csp; static assets served by WhiteNoise
- Rate limiting via django-ratelimit for participant POSTs
- Brute-force login protection via django-axes
- CAPTCHA (hCaptcha) for anonymous submissions when enabled on the survey
- One-time-use Invite tokens, server-validated, with optional expiry
- Publish window and capacity guard (start/end times, max responses)

### hCaptcha configuration

Set these environment variables to enable the widget and server-side verification:

- `HCAPTCHA_SITEKEY`
- `HCAPTCHA_SECRET`

When set and the survey’s “Require CAPTCHA” box is ticked, the participant page renders the hCaptcha widget and submission is validated server-side using `siteverify`.

Our CSP is already configured to allow hCaptcha domains; no inline scripts are used.

## Participant flow and Thank-you page

- While live, the participant route renders the survey form (and CAPTCHA when required)
- **Survey progress tracking**: Participants can save their progress and resume later. See [Survey Progress Tracking](survey-progress-tracking.md) for details on auto-save, progress restoration, and data retention.
- On successful submission, participants are redirected to `/surveys/<slug>/thank-you/`
- Responses count toward the survey's totals and analytics tiles

## Invite tokens (details)

- One-time-use: a token cannot be used to submit more than once
- Optional expiry per token; expired tokens are rejected
- CSV export includes token, created/expiry, used-at, and used-by (if applicable)
- Tokens are not API-browsable and are only visible to survey managers

## Troubleshooting

- “Submission blocked: CAPTCHA required”: ensure both `HCAPTCHA_SITEKEY` and `HCAPTCHA_SECRET` are configured and the widget renders; then retry.
- “Survey not live”: check Status is Published, within Start/End window, and below Max responses.
- “Token invalid or used”: regenerate a fresh token or remove expiry.

## Related docs

- Authentication and permissions
- API reference and protections
- Themes and UI
