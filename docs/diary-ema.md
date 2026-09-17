---
title: Diary / EMA (Ecological Momentary Assessment)
category: features
priority: 9
---

The Diary / EMA layout adds high-frequency repeated-measures surveys to
CheckTick: short surveys triggered on a fixed schedule (daily, 4×/day) or
by events (symptom onset). Used for pain diaries, mood tracking,
medication adherence, and symptom monitoring in clinical trials.

This guide covers the creator workflow and the participant experience.
For the technical data model and runtime pipeline, see
[Survey Layouts (Technical)](survey-layouts-technical.md).

## When to use Diary / EMA

- **Pain diaries** — daily or multiple-times-daily pain ratings over
  a study period.
- **Mood tracking** — IAPT/mental-health monitoring with repeated
  PHQ-9 or GAD-7 administrations.
- **Medication adherence** — daily check-ins confirming medication
  was taken, with optional side-effect reporting.
- **Symptom monitoring in clinical trials** — high-frequency symptom
  tracking with compliance tracking for regulatory submissions.

Diary / EMA is different from [Staged](survey-layouts.md#staged-longitudinal)
(which is phase-based: baseline → 2-week → 6-month). Diaries are
high-frequency repeated measures with burst scheduling, compliance
tracking (missed entries), and time-stamp integrity for regulatory
submissions. The scheduling semantics are fundamentally different from
phase windows.

## Creator workflow

### 1. Build your sections

Build your survey sections in the [Builder](builder.md) as you would
for any survey. A diary survey typically has a single section with a
small number of questions — the "instrument" that the participant
completes each time a window opens.

### 2. Switch to the Diary layout

Go to the [Organise](groups-view.md) page
(`/surveys/<slug>/groups/`). In the **Survey layout** section at the
top, click **Use this layout** on the Diary (EMA) card.

A configuration card appears below the layout picker.

### 3. Configure the schedule

The configuration card has:

- **Schedule type** — how diary windows are scheduled:
  - *Fixed interval* — windows open at regular intervals (e.g. every 6
    hours = 4×/day). Set the interval in hours.
  - *Event-triggered* — no scheduled windows. The participant
    initiates entries from the landing page (e.g. "I had a symptom").
    Compliance is not schedule-tracked.
  - *Burst* — cycles of on-days (daily entries) followed by off-days
    (no entries). Set the on-days and off-days (e.g. 7 days on, 7 days
    off).
- **Window times measured from** — *Participant enrolment* (each
  participant's windows start from their first access) or *Survey open
  date* (all participants on the same calendar schedule). Use *Survey
  open date* when you want everyone on the same schedule.
- **Compliance threshold (%)** — warn on the compliance dashboard if
  a participant submits fewer than this percentage of expected entries.
- **Grace period (minutes)** — a window stays submittable for this
  many minutes after its scheduled end. Prevents edge-case missed
  entries when the participant is a few minutes late.
- **Show participants their compliance summary** — displays the
  compliance stats on the diary landing page.

Click **Save configuration** when done.

### 4. Publish and run

1. [Publish](publish-and-collection.md) the survey as you would for
   any survey.
2. Participants access the survey and are enrolled automatically on
   first access (their enrolment time becomes the anchor for window
   calculations, if using the enrolment anchor).
3. Each time a window opens, the participant sees the diary landing
   page with a "Start this entry" button. They complete the short
   instrument and submit.
4. If no window is open, the participant sees a "No diary window open
   right now" page with the next window time.

### 5. Monitor compliance

The survey [dashboard](surveys.md) shows a **Diary Compliance** table
with per-participant stats:

- **Expected** — how many entries should have been submitted by now.
- **Submitted** — how many entries the participant has completed.
- **Missed** — how many windows closed without a submission.
- **Compliance** — submitted / expected × 100.

Rows below the compliance threshold are highlighted. Click **Export
CSV** to download the full `DiaryEntry` audit trail (participant,
window order, expected start/end, submitted at, missed) — suitable
for regulatory submissions and data monitoring committee reports.

## Participant experience

### First access

When a participant first accesses a diary survey:

1. Their enrolment time is recorded (used as the anchor for window
   calculations when the anchor is set to *Participant enrolment*).
2. The diary landing page shows the current window status and a
   "Start this entry" button (if a window is open).

### Between windows

When no window is open (e.g. between fixed-interval windows, or during
a burst off-period):

1. The participant sees a "No diary window open right now" page.
2. The next window time is shown if available.
3. Their progress is preserved so resume works when the next window
   opens.

### Completing an entry

1. The participant clicks "Start this entry" on the landing page.
2. The entry form renders — all sections in the survey (a diary entry
   uses the full group set each time).
3. The participant completes the questions and submits.
4. The entry is marked as submitted with a timestamp.
5. The participant is redirected to the thank-you page.

### Save and resume

Save-and-resume works as it does for any survey. The participant's
enrolment anchor is preserved across resume. If the window has closed
while they were away, the entry is marked as missed on their next
access.

### Reminder emails

When a new window opens, participants who have not yet submitted
receive a reminder email containing the survey name, a link to the
survey, and the window end time. No survey content or answers are
included in the email. Reminders are sent by a daily scheduled
command (`process_diary_reminders`).

## Outline syntax

The Diary layout can be configured directly in the [Outline / bulk
upload](import.md) text editor using a `DIARY` block. The grammar is
optional (the Organise page UI is the primary config path) but useful
for the AI builder and power users.

```text
DIARY
  schedule: fixed_interval
  interval_hours: 6
  anchor: enrolment
  compliance_threshold: 80
  grace_minutes: 30
  show_progress: true

# Daily check-in {daily-check-in}
## Pain level {pain}
(likert) 1-5

## Mood {mood}
(likert) 1-5

## Notes {notes}
(long_text)
```

- The `DIARY` block configures the schedule. No per-group `~` suffixes
  are needed because a diary entry uses the full group set.
- For `burst` schedules, use `burst_on_days` and `burst_off_days`
  instead of `interval_hours`.
- For `event_triggered`, omit `interval_hours`; the participant
  initiates entries from the landing page.
- The grammar round-trips through export → import like the other
  layouts.

## Preview

On the [preview](survey-layouts.md) page, a **Diary / EMA preview**
panel shows the schedule type, anchor, and interval/burst config so
you can verify the schedule at a glance. The preview renders all
questions (a diary entry uses the full group set).

## Survey Map

The Survey Map shows the full authored survey. No per-group badges
(unlike Staged phases / Delphi rounds) — every group is in every
entry.

## Warnings

The Organise page surfaces non-blocking warnings for common
misconfigurations:

- **Fixed interval with no interval set** — enter the hours between
  windows (e.g. 6 for 4×/day).
- **Burst with no on-days** — enter the number of on-days in each
  cycle.
- **Survey open anchor with no start date** — set a start date or
  switch the anchor to *Participant enrolment*.
- **Branching targets a diary section** — branching across diary
  entries has no effect.

## Related documentation

- [Survey Layouts](survey-layouts.md) — overview of all layouts.
- [Survey Layouts (Technical)](survey-layouts-technical.md) — developer
  reference for the data model, runtime pipeline, and implementation
  details.
- [Organise](groups-view.md) — the page where Diary / EMA is
  configured.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume
  carries the diary enrolment anchor and entry state.
- [Email Notifications](email-notifications.md) — the reminder email
  infrastructure.
- [Billing & Subscriptions](billing-and-subscriptions.md) — Diary / EMA
  is a paid-tier layout (Pro and above).
