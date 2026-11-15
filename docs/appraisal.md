---
title: Appraisal Workflow
category: appraisal
priority: 1
---

# Appraisal Workflow

CheckTick supports GMC-style multi-source feedback (360° appraisal) for organisations that run structured appraisal cycles — hospital appraisal departments, designated bodies, and their Responsible Officers.

The workflow is built on the same principles as everything else in CheckTick: responses are encrypted at rest, access is controlled by roles, and every sensitive action is logged. What appraisal adds is a governance structure around those primitives — one survey per doctor per appraisal cycle, feedback from patients, colleagues and the doctor themselves, and a report that only the appraiser can release.

## For the Responsible Officer and the organisation

### What you get

Each appraisee has **one survey per appraisal cycle**, created by their appraiser from your organisation's instrument. Feedback is gathered from three populations in a single survey:

- **Patients** — anonymous, via an unlisted QR code or link. No login, no token.
- **Colleagues** — pseudonymous, via single-use invitation tokens you approve.
- **The appraisee themselves** — a self-assessment on the same items as the colleague questionnaire, so the report can compare self-rating against how others rate them, item by item.

Because every appraisee in a cycle answers the same instrument, the results are comparable and defensible. The released report is a **structured, versioned snapshot** — generated at release, never silently changed. If something needs correcting, a new version is created and linked to the old one.

### Encryption and key custody

Every appraisal survey encrypts responses at rest. The survey's encryption key is wrapped with your **organisation master key** — not with any individual's credentials. This is deliberate:

- The **appraisee cannot read or alter the results**. That is a property of the key custody, not a promise in a policy document.
- If an **appraiser leaves or changes role**, you (as RO) recover the survey with the organisation key and re-wrap it for the incoming appraiser. No data is orphaned.
- The organisation master key is generated automatically the first time it is needed, and every use of it for recovery is audit-logged.

### Governance: who can see what

Access is controlled by roles, and the appraisal workflow uses them precisely:

| Role | What they can do |
|---|---|
| **Responsible Officer** (organisation owner/admin) | Portfolio oversight of every appraisal in the organisation; co-signs exception reviews; recovers surveys via the organisation key |
| **Appraiser** (survey owner) | Reads the aggregate results (after unlocking), releases the report, raises exception reviews |
| **Appraisee** (distributor) | Generates invitation tokens and QR codes, sees completion counts (how many responses arrived — never their content), distributes the survey |

The appraisee's role is deliberately scoped: they are the subject of the feedback, so they have no path to the responses — not a hidden one, not a settings toggle. The encryption key custody makes "the appraisee cannot see the results" a fact of the system.

### Unmasking a rater: two-party control

Colleague responses are pseudonymous — the system knows which invitation token produced which response, but **nothing in the reporting ever shows that linkage**. In the rare case where a response indicates a serious risk (patient safety, fitness to practise) and the rater needs to be identified, the workflow requires two people:

1. The **appraiser raises an exception review**, stating which response and why.
2. The **Responsible Officer co-signs** it. The appraiser cannot approve their own request, even if they hold organisation admin rights.

Only when the RO has co-signed is the linkage visible — and only to the appraiser and the RO. The appraisee never sees that an exception review happened; the released report records only that one occurred, never its content. Every step — the request, the co-signature, and each view of the disclosed linkage — is written to the audit trail.

Because the RO and appraiser are rarely in the same room, the workflow notifies by email: the RO is told when a review awaits their co-signature (the reason is not included in the email — they read it after signing in), and the appraiser is told of the decision.

### Logging

Every sensitive action is audit-logged: survey creation, token batch generation, survey unlocks, results views, report releases, exception reviews and their co-signatures, and views of a disclosed rater linkage. The logs record who did what and when — never response content, and never the reason a rater was unmasked.

### Getting started

1. As organisation owner or admin, open **Appraisals** and **adopt an instrument** from the Question Bank library (for example the 360° GMC Patient Feedback Questionnaire). You can amend your organisation's copy afterwards if you need to.
2. Appraisers create an appraisal from their caseload: pick the appraisee, the instrument, and the cycle year. The survey is created, encrypted, and the appraisee is added as its distributor.
3. The appraiser publishes the survey, generates the invitation tokens (colleagues, and the appraisee's self-assessment token) and the patient QR code, and the appraisee distributes them.
4. When responses reach the minimum threshold, the appraiser unlocks the survey, reviews the aggregate — including the self-versus-others comparison — and releases the report to the appraisee.

Appraisal is an **Organisation tier** offering. Seats are the clinicians involved — the RO, appraisers and appraisees. Patients and colleague raters are respondents: they use no seats.

## For the appraisee

Your appraisal survey gathers feedback about your practice from patients, colleagues and your own self-assessment — and CheckTick is designed so that the process is fair and confidential.

**What you do.** Your appraiser creates your survey and adds you as its **distributor**. From the Surveys page you will see it under "Distributing": you can generate the invitation tokens and QR codes, send them to your colleagues and patients, and watch the completion counts rise. When your appraiser releases your report, you can view it — exactly as released, including how your own self-assessment compares with everyone else's ratings.

**What you cannot do — and why that protects you.** You cannot read the individual responses, and you cannot alter them. The survey belongs to your appraiser and is encrypted with your organisation's key; you hold no key to it. That means the feedback in your report is what your colleagues and patients actually said — nobody can edit it, and neither can you. If a response ever indicates a serious risk and your appraiser needs to identify which colleague gave it, that can only happen with your Responsible Officer's explicit co-signature, and the whole exchange is audit-logged. You will never be asked to approve or witness it.

**Your self-assessment.** You will receive a single-use token to complete your own ratings on the same items your colleagues rate. Your answers are compared with theirs in the released report — often the most useful part of the appraisal, because it shows where your view of your practice differs from the view of those you work with and treat.

**Your data.** Responses are encrypted at rest, stored on UK servers, and covered by the platform's data governance: retention policies, data subject rights (every response can be linked to a receipt token for redaction requests), and full audit logging.

## Related documentation

- [Surveys: the Distributor role](surveys.md#distributors-and-the-distributing-group)
- [Publish and collect: distributor access to the tokens page](publish-and-collection.md#distributor-access-to-the-tokens-page)
- [Reporting: appraisal reports](reporting-and-exports.md#appraisal-reports)
- [Encryption for users: appraisal surveys and the organisation key](encryption-for-users.md#appraisal-surveys-and-the-organisation-key)
- [Billing: appraisal on the Organisation tier](billing-and-subscriptions.md#appraisal-organisation-tier)
