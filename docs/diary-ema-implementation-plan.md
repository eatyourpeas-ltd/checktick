---
title: Diary / EMA — Technical Reference
category: development
priority: 18
---

Status: **Implemented** (v0.19.0). This document is the developer
reference for the Diary / EMA (ecological momentary assessment) survey
layout. For the user-facing guide, see [Diary / EMA](diary-ema.md).

Branch: `diary-ema`.

## 1. Overview

The Diary / EMA layout adds high-frequency repeated-measures surveys to
CheckTick: short surveys triggered on a fixed schedule (daily, 4×/day) or
by events (symptom onset). Used for pain diaries, mood tracking,
medication adherence, and symptom monitoring in clinical trials.

### Why this layout next

- **NHS-first fit.** Pain diaries, IAPT/mental-health monitoring,
  medication adherence, and chronic-disease trial symptom tracking are
  bread-and-butter NHS digital-health work — exactly the use cases that
  send research teams to REDCap or Qualtrics today.
- **Already the documented next pick.** `survey-layouts-technical.md`
  §Planned layouts marks Diary/EMA `priority: high (next)`, and the home
  page already teases "diary/EMA planned".
- **Distinct from Staged.** Staged is phase-based (baseline → 2-week →
  6-month). Diaries are high-frequency repeated measures with burst
  scheduling, compliance tracking (missed entries), and time-stamp
  integrity for regulatory submissions. The scheduling semantics are
  fundamentally different from phase windows.
- **Reuses proven ingredients.** The runtime hook reuses
  `_resolved_group_order_ids` — a diary entry is just a short survey
  with the same group set each time. The difference is the *trigger*,
  not the *selection*.

### Relationship to existing layouts

| Layout | Time axis | Frequency | Selection mechanism |
|---|---|---|---|
| Staged | Phase windows (days/weeks/months) | Low (3–5 phases) | Union of open phases |
| **Diary / EMA** | Scheduled windows (hours/days) | High (daily to 4×/day) | Same group set each entry; trigger differs |
| Delphi | Round windows (days/weeks) | Low (2–3 rounds) | Current round's group set |

Diary is **not** a variant of Staged. Staged unlocks different sections
over time; Diary repeats the same short instrument on a schedule and
tracks compliance across entries.

## 2. Scope

### In scope (first iteration)

- `DiaryMenu` config: schedule type (`fixed_interval`, `event_triggered`,
  `burst`), interval, burst schedule, compliance threshold.
- `DiaryEntry` model: one per participant per scheduled window — the
  compliance audit trail (expected time, actual submission time, link to
  `SurveyProgress`).
- `diary.py` pure helpers: window resolution, compliance calculation,
  current-window state.
- Runtime hook in `_handle_participant_submission`: resolve the current
  window, render the diary landing page or the entry form.
- Outline grammar (`DIARY` block + `~ window:` suffixes), round-tripping
  through export → import.
- Organise page config card + warnings.
- Preview path `?simulate_window=`.
- Survey Map card showing the schedule + compliance summary.
- Compliance dashboard on the survey detail page (for the author):
  expected vs submitted entries, missed-entry list, compliance %.
- Reminder email at window start (reuses the existing email-notifications
  infrastructure). No SMS in the first iteration.
- Tier gating: Diary/EMA is a paid-tier layout (Pro and above), gated via
  `TierLimits.allowed_layouts` alongside the other non-linear layouts.

### Out of scope (deferred)

- **Real-time push notifications** (in-app, web push, or SMS). First
  iteration is reminder email + landing-page status. Matches the
  deferral noted in `survey-layouts-technical.md` §Planned layouts.
- **Event-triggered entry via device sensors / wearables.** The
  `event_triggered` schedule type is modelled but only participant-initiated
  events (e.g. "I had a symptom") are supported in v1; no sensor
  integration.
- **Burst-scheduling UI polish.** The `burst` schedule type is modelled
  and enforced, but the config UI is minimal (on/off days as a simple
  list). A richer calendar picker is a follow-on.
- **Regulatory submission export (e.g. CDASH/Define-XML).** The
  time-stamp integrity is captured on `DiaryEntry` (expected vs actual,
  monotonic ordering), but no regulatory-format export is built in v1.
  CSV export of the compliance audit trail is included.

## 3. Data model

```python
class Survey(models.Model):
    ...
    layout = models.CharField(
        max_length=20,
        choices=[
            ("linear", "Linear"),
            ("section_menu", "Section menu"),
            ("rct", "Randomised (RCT)"),
            ("guided", "Guided"),
            ("staged", "Staged (longitudinal)"),
            ("matrix", "Matrix (free navigation)"),
            ("delphi", "Delphi (consensus rounds)"),
            ("diary", "Diary / EMA"),
        ],
        default="linear",
    )


class DiaryMenu(models.Model):
    """Configuration for a survey with ``layout = diary``.

    A DiaryMenu is a OneToOne related to ``Survey`` and holds the
    schedule type and parameters. Per-window state (expected time,
    actual submission time, link to SurveyProgress) lives on
    ``DiaryEntry`` rows.

    See docs/survey-layouts-technical.md §Diary / EMA layout.
    A non-diary survey has no ``DiaryMenu`` row.
    """
    survey = models.OneToOneField(
        Survey, related_name="diary_menu", on_delete=models.CASCADE,
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=[
            ("fixed_interval", "Fixed interval (e.g. every 6 hours)"),
            ("event_triggered", "Event-triggered (participant-initiated)"),
            ("burst", "Burst (e.g. 7 days on, 7 days off)"),
        ],
        default="fixed_interval",
    )
    # fixed_interval: the interval between windows, in hours.
    interval_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="For fixed_interval: hours between windows (e.g. 6 = 4×/day).",
    )
    # burst: on/off cycle in days. e.g. on_days=7, off_days=7.
    burst_on_days = models.PositiveIntegerField(null=True, blank=True)
    burst_off_days = models.PositiveIntegerField(null=True, blank=True)
    # Anchor for window start times. "enrolment" = each participant's
    # windows start from their first access; "survey_open" = all
    # participants on the same calendar schedule. Same precedent as
    # StagedPhase / DelphiRound anchors.
    anchor = models.CharField(
        max_length=20,
        choices=[("enrolment", "Participant enrolment"),
                 ("survey_open", "Survey open")],
        default="enrolment",
    )
    # Compliance threshold: warn the author if a participant's compliance
    # falls below this percentage of expected entries.
    compliance_threshold_pct = models.PositiveIntegerField(
        default=80,
        help_text="Warn if a participant submits fewer than this % of expected entries.",
    )
    # Window close grace period in minutes: a window stays submittable
    # for this long after its scheduled end (e.g. 30 min for a 6-hour
    # window). Prevents edge-case missed entries.
    grace_minutes = models.PositiveIntegerField(default=30)
    show_progress = models.BooleanField(
        default=True,
        help_text="Show participants which window they are in and the compliance summary.",
    )


class DiaryEntry(models.Model):
    """One scheduled window for one participant in a diary survey.

    This is the compliance audit trail: the expected time the window
    opened, the actual time the participant submitted (null if missed),
    and a link to the SurveyProgress row carrying the responses. One
    DiaryEntry per (participant, scheduled window).

    The precedent is StagedPhase (window offsets) + SurveyProgress
    (response carrier), combined into a per-window row. Unlike Staged
    (which recomputes open phases on each access), DiaryEntry rows are
    materialised ahead of time (or lazily on first access in the window)
    so the compliance audit trail is stable and queryable.
    """
    menu = models.ForeignKey(
        DiaryMenu, related_name="entries", on_delete=models.CASCADE,
    )
    progress = models.ForeignKey(
        "SurveyProgress", related_name="diary_entries", on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(default=0)
    # Expected window start/end (UTC), computed from the menu anchor +
    # schedule. The actual submission time is progress.completed_at (or
    # a dedicated submitted_at if we want to allow re-submission within
    # the window).
    expected_start = models.DateTimeField()
    expected_end = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_missed = models.BooleanField(
        default=False,
        help_text="True if the window closed without a submission (after grace).",
    )

    class Meta:
        unique_together = ("menu", "progress", "order")
        ordering = ["progress", "order", "id"]


class SurveyProgress(models.Model):
    ...
    # Diary layout: the participant's enrolment anchor (first access
    # time). Only populated for surveys with layout = "diary". Null for
    # other layouts. Used to compute window start/end times when
    # anchor = "enrolment".
    diary_enrolled_at = models.DateTimeField(null=True, blank=True)
```

**Migration:** `0069_diary_layout` (adds the `diary` choice to
`Survey.layout`, the `DiaryMenu` / `DiaryEntry` models, and the
`SurveyProgress.diary_enrolled_at` field). Follows `0068_survey_closed_by_downgrade`.

## 4. Pure helpers (`diary.py`)

A new `checktick_app/surveys/diary.py` module exposes pure, testable
functions — mirroring `staged.py`, `matrix.py`, and `delphi.py`:

```python
def anchor_time(
    menu: DiaryMenu, *, survey_start, progress_enrolled_at
) -> datetime:
    """Return the anchor used to compute window start/end times."""


def window_for_order(
    menu: DiaryMenu, order: int, *, anchor
) -> tuple[datetime, datetime]:
    """Return (expected_start, expected_end) for the nth window."""


def current_window(
    menu: DiaryMenu, *, anchor, now, grace_minutes
) -> tuple[int, datetime, datetime] | None:
    """Return (order, start, end) for the currently-open window, or None.

    A window is "open" if now is in [start, end + grace). Returns None
    between windows (fixed_interval gap) or during a burst off-period.
    """


def next_window(
    menu: DiaryMenu, *, anchor, now
) -> tuple[int, datetime, datetime] | None:
    """Return the next upcoming window after `now`, or None if the
    schedule has ended (e.g. survey closed)."""


def expected_entry_count(
    menu: DiaryMenu, *, anchor, now
) -> int:
    """Total windows that should have opened by `now` (compliance denom)."""


def compliance_for_progress(
    menu: DiaryMenu, progress: SurveyProgress, *, now
) -> dict:
    """Return {expected, submitted, missed, compliance_pct, missed_orders}.

    Reads the progress's DiaryEntry rows. compliance_pct = submitted /
    expected * 100. Used by the compliance dashboard and the
    show_progress participant view.
    """


def ensure_entry_for_current_window(
    menu: DiaryMenu, progress: SurveyProgress, *, now
) -> DiaryEntry:
    """Idempotently create/fetch the DiaryEntry for the current window.

    Called by the take view on each access. If the current window has no
    DiaryEntry row yet, create one with submitted_at=None. If the window
    has closed (past grace) and the entry is still unsent, mark
    is_missed=True.
    """
```

These are pure (no side effects except `ensure_entry_for_current_window`,
which persists the `DiaryEntry` row — the same pattern as
`assign_round_for_progress` in `delphi.py`).

## 5. Runtime hook

A new branch in `_handle_participant_submission`, analogous to the
Staged and Delphi branches:

```python
if survey.layout == Survey.Layout.DIARY and progress is not None:
    menu = getattr(survey, "diary_menu", None)
    if menu is None:
        return _render_diary_no_config(request, survey, progress)
    anchor = _diary_anchor_time(menu, survey, progress)
    current = _diary_current_window(menu, anchor=anchor, now=now,
                                    grace_minutes=menu.grace_minutes)
    if current is None:
        # No window open right now — render the diary landing page
        # showing the next window time + compliance summary.
        return _render_diory_waiting(request, survey, progress, menu, anchor, now)
    order, start, end = current
    entry = _diary_ensure_entry(menu, progress, order=order, now=now)
    if entry.is_missed:
        # Window closed while they were away — advance to next open window.
        return _render_diory_waiting(request, survey, progress, menu, anchor, now)
    # Resolve selected_group_ids: a diary entry uses the full group set
    # (the same short instrument each time). The difference is the
    # trigger, not the selection.
    selected_group_ids = _resolved_group_order_ids(survey)
    # On submit, set entry.submitted_at = now and recompute compliance.
```

The diary landing page (`surveys/diary_landing.html`) shows:

- The current window's status (open / next opens at …).
- The participant's compliance summary (X of Y entries submitted).
- A "Start this entry" button if a window is open.

The take page reuses the existing question rendering pipeline — a diary
entry is just a short survey submission scoped to the current
`DiaryEntry` row.

## 6. Outline grammar

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
(likert) 0-10

## Mood {mood}
(likert) 1-5

## Notes {notes}
(long_text)
```

- The `DIARY` block configures the schedule. No per-group `~` suffixes
  are needed because a diary entry uses the full group set — unlike
  Staged (`~ phase:`) or Delphi (`~ round:`), there is no per-section
  selection.
- For `burst` schedules, the block carries `burst_on_days` /
  `burst_off_days` instead of `interval_hours`.
- For `event_triggered`, `interval_hours` is omitted; the participant
  initiates entries from the landing page.
- The grammar round-trips through export → import like the other
  layouts.

## 7. Organise page config + warnings

The Organise page (`surveys/groups.html`) gets a new layout card
("Diary / EMA") and a configuration card below it with:

- Schedule type (fixed_interval / event_triggered / burst).
- Interval hours (fixed_interval) or burst on/off days (burst).
- Anchor (enrolment / survey_open).
- Compliance threshold %.
- Grace minutes.
- Show progress toggle.

Warnings (non-blocking, mirroring Staged/Delphi):

| Issue | Why it matters | Handling |
|---|---|---|
| No schedule configured | A freshly-switched survey has no schedule. | Render config card with a "configure the schedule" prompt; block take view. |
| `fixed_interval` with no `interval_hours` | No windows ever open. | Warn on Organise; block take view. |
| `burst` with on/off days = 0 | Empty burst cycle. | Warn on Organise; block take view. |
| `survey_open` anchor, no survey start date | Anchor is None, nothing ever opens. | Warn on Organise (same as Staged). |
| Branching targets a diary section | A `jump to` is meaningless across entries. | Warn (non-blocking); the runtime filters to the full group set each entry. |
| Compliance below threshold | A participant is missing entries. | Surface on the compliance dashboard; optional reminder email escalation. |

## 8. Preview

`?simulate_window=<order>` filters the questions to the full group set
(as a diary entry would) and renders the take page so the author can
preview the instrument. `?simulate_window=<order>&at=<iso8601>` lets
the author preview the landing page state at a specific time (e.g. to
see the "next window opens at" message between windows).

## 9. Survey Map

The Survey Map shows the full authored survey with a **Diary — schedule**
card above the visualiser listing the schedule type, interval/burst
parameters, anchor, compliance threshold, and grace period. No per-group
badges (unlike Staged phases / Delphi rounds) — every group is in every
entry.

## 10. Compliance dashboard

A new section on the survey detail page (author-facing) shows:

- Per-participant table: expected entries, submitted entries, missed
  entries, compliance %.
- Highlighted rows where compliance < threshold.
- CSV export of the full `DiaryEntry` audit trail (participant, order,
  expected_start, expected_end, submitted_at, is_missed) — suitable for
  regulatory submissions and data monitoring committee reports.

The compliance dashboard reuses the existing survey-detail author
infrastructure and the CSV export pattern from the reporting/exports
module.

## 11. Reminder notifications

At window start, a reminder email is sent to each enrolled participant
who has not yet submitted the current entry. This reuses the existing
`email-notifications` infrastructure (templates, async send, audit log).
A daily scheduled command (alongside `process_expiring_subscriptions`)
sweeps diary surveys and sends reminders for newly-opened windows.

No SMS, no in-app push, no web push in v1 (per §2 Out of scope).

## 12. Tier gating

Diary/EMA is a paid-tier layout. Update `TierLimits.allowed_layouts` in
`checktick_app/core/tier_limits.py`:

- **Free:** `["linear"]` (unchanged — linear only).
- **Pro / Team / Organisation / Enterprise:** add `"diary"` to the
  existing list (which already includes `section_menu`, `rct`,
  `guided`, `staged`, `matrix`, `delphi`).

The `check_layout_permission()` and `get_allowed_layouts()` helpers are
the single source of truth — no other gating code needed. The Organise
page template (`groups.html`) renders the Diary card with an "Upgrade to
use" link for free-tier users, mirroring the other layout cards.

## 13. Commit plan

All 11 commits are complete. Each commit ended with `s/lint` and
`s/test --no-a11y` passing.

### Commit 1 — Pure helpers + tests (`diary.py`) ✅ `23464d6`

- Add `checktick_app/surveys/diary.py` with the pure functions in §4
  (anchor_time, window_for_order, current_window, next_window,
  expected_entry_count, compliance_for_progress).
- No models, no migrations, no views — just pure functions tested with
  synthetic inputs.
- Tests: `checktick_app/surveys/tests/test_diary_helpers.py` covering
  fixed_interval, burst, event_triggered, grace period, missed-entry
  marking, compliance calculation.
- `s/lint && s/test --no-a11y`.

### Commit 2 — Data model + migration ✅ `9a47126`

- Add `DiaryMenu`, `DiaryEntry` models and the `diary` choice on
  `Survey.Layout`.
- Add `SurveyProgress.diary_enrolled_at`.
- Migration `0069_diary_layout`.
- Update the `Survey.layout` help_text and the `Survey.Layout` docstring
  to mention `diary`.
- Tests: model tests (creation, unique_together, ordering), migration
  round-trip.
- `s/lint && s/test --no-a11y`.

### Commit 3 — Tier gating ✅ `194bb08`

- Add `"diary"` to `allowed_layouts` for Pro/Team/Organisation/Enterprise
  in `tier_limits.py`.
- Update the `check_layout_permission` docstring to list `diary`.
- Tests: `test_tier_limits.py` — free tier denied, paid tiers allowed.
- `s/lint && s/test --no-a11y`.

### Commit 4 — Runtime hook + take view ✅ `ad07515`

- Add the diary branch in `_handle_participant_submission` (§5).
- Add `ensure_entry_for_current_window` (moves from pure helper to
  side-effecting, mirroring `assign_round_for_progress`).
- Add the diary landing template (`surveys/diary_landing.html`) and the
  "no config" / "waiting" templates.
- On submit, set `entry.submitted_at` and recompute `is_missed` for
  prior windows.
- Tests: `test_diary_runtime.py` — first access enrols, window open
  renders entry form, window closed renders waiting page, submit marks
  entry submitted, missed window marked `is_missed`, resume preserves
  enrolment anchor.
- `s/lint && s/test --no-a11y`.

### Commit 5 — Organise page config + warnings ✅ `bea2bfd`

- Add the Diary layout card and config card to `groups.html`.
- Add the `set_layout` / `save_diary_config` handlers to the
  `survey_groups` view.
- Add the `diary_preview` context for the Survey Map card.
- Add the warnings table (§7) to the organise-view warning builder.
- Tests: `test_groups_diary.py` — config save, warning surfaces for
  misconfigurations, free-tier user sees "Upgrade to use".
- `s/lint && s/test --no-a11y`.

### Commit 6 — Outline grammar + export round-trip ✅ `8dfc097`

- Parse the `DIARY` block in `parse_bulk_markdown_with_collections`
  (`markdown_import.py`).
- Emit the `DIARY` block in `_export_survey_to_markdown`.
- Apply parsed config in the bulk upload view.
- Tests: `test_outline_diary.py` — parse, export, round-trip
  (import → export → import equality), error cases (missing
  interval_hours, invalid schedule_type).
- `s/lint && s/test --no-a11y`.

### Commit 7 — Preview path ✅ `8a5d0ac`

- Add `?simulate_window=` and `?simulate_window=&at=` to
  `survey_preview`.
- Add the "Simulate window" panel to the preview page.
- Tests: `test_diary_preview.py` — simulate window renders entry form,
  simulate at-time renders landing state.
- `s/lint && s/test --no-a11y`.

### Commit 8 — Compliance dashboard + CSV export ✅ `6607928`

- Add the compliance dashboard section to the survey detail page
  (author-facing).
- Add the CSV export endpoint for the `DiaryEntry` audit trail.
- Tests: `test_diary_compliance.py` — dashboard renders per-participant
  stats, CSV export columns and rows, threshold highlighting.
- `s/lint && s/test --no-a11y`.

### Commit 9 — Reminder email + scheduled command ✅ `eedd88b`

- Add the diary reminder email template.
- Add a daily scheduled command (alongside
  `process_expiring_subscriptions`) that sweeps diary surveys and sends
  reminders for newly-opened windows.
- Tests: `test_diary_reminders.py` — reminder sent for open window,
  not sent for already-submitted, not sent for missed, idempotent.
- `s/lint && s/test --no-a11y`.

### Commit 10 — Docs sweep (user-facing) ✅ `397ce0a`

- Write `docs/diary-ema.md` (user-facing guide: when to use, creator
  workflow, participant experience, compliance dashboard, outline
  syntax). Frontmatter: `category: features, priority: 9` (after
  Delphi at priority 8).
- Add a Diary/EMA entry to `docs/survey-layouts.md` (move it from the
  "Planned layouts" section into the live-layouts list at the top, and
  add a "When to use Diary/EMA" subsection).
- Remove the Diary/EMA entry from the "Planned layouts" section in both
  `docs/survey-layouts.md` and `docs/survey-layouts-technical.md`.
- Reference `docs/diary-ema.md` from `docs/getting-started.md`
  (Next Steps → Advanced Features) and from this planning doc (now the
  dev reference).
- Update `checktick_app/surveys/templates/surveys/bulk_upload.html` to
  add a Diary layout bullet in the outline-grammar help.
- Update `checktick_app/surveys/templates/surveys/partials/builder_empty_state.html`
  to mention Diary in the layout list.
- `s/lint && s/test --no-a11y`.

## 14. Pre-version-bump: layouts-as-USP refocus

Before bumping the `pyproject.toml` minor version, tidy the
marketing/entry surfaces to present Survey Layouts as a central USP of
the platform. **Layouts are gated by account tier** — Free tier gets
linear only; paid tiers (Pro/Team/Organisation/Enterprise) get all
eight layouts. The refocus must make this gating visible (so free users
see what they'd unlock by upgrading) without implying free users can
use the gated layouts.

### Surfaces to update

1. **`README.md`** — add a "Survey Layouts" bullet to the feature list
   naming all eight layouts (linear, section menu, RCT, guided, staged,
   matrix, Delphi, Diary/EMA) with a one-line "when to use" hint and a
   link to `docs/survey-layouts.md`.
2. **`docs/getting-started.md`** — add a "Survey Layouts" subsection to
   Key Features (§What is CheckTick?) and a link in Next Steps →
   Advanced Features. Mention that advanced layouts are a paid-tier
   feature with a link to the pricing page.
3. **`checktick_app/core/templates/core/home.html`** — promote "Survey
   Layouts" from a single bullet inside the "Powerful Question Builder"
   card (L83-85) into its own card (or a dedicated section) listing all
   eight layouts with icons, and a "Free tier gets linear; paid tiers
   get all eight" note linking to the pricing page.
4. **`checktick_app/core/templates/core/pricing.html`** — update the
   "All survey layouts" bullet (L372-376) to name all eight layouts
   explicitly (currently lists "section menu, RCT, guided, staged,
   matrix, Delphi" — add Diary/EMA). Ensure the Free tier row makes
   clear it's linear-only.
5. **`checktick_app/core/templates/core/subscription_portal.html`** —
   update the "Advanced survey layouts" bullet (L184-190) to name all
   eight layouts.
6. **Surveys list / dashboard** (`surveys:survey_list` view +
   template) — add a "Layout" column/badge to each survey row so users
   see at a glance which layout each survey uses, and surface a
   "Discover layouts" link to the Organise page / docs for surveys
   still on linear.

### Gating visibility rules

- On `home.html` and `pricing.html`: show all eight layouts (marketing
  surface), with a clear "Free: linear only · Pro and above: all eight"
  callout.
- On `groups.html` (Organise page): already renders disabled cards with
  "Upgrade to use" for gated layouts — just add the Diary card (done in
  Commit 5).
- On the surveys list: the Layout badge is informational only; no
  gating UI needed there (gating happens on the Organise page).

### Commit 11 — Layouts-as-USP refocus ✅ `d25ff80`

- Update `README.md`, `docs/getting-started.md`, `home.html`,
  `pricing.html`, `subscription_portal.html`, and the surveys list
  template per §14.
- **Fix the extra column in the "Detailed Feature Comparison" table
  in `pricing.html`** — the table currently has a layout mismatch
  (an extra column that doesn't correspond to a tier). Audit the
  `<thead>`/`<tbody>` column counts and remove the stray column.
- Tests: `s/test --no-a11y` (template rendering smoke tests already
  cover these pages); add a test asserting the home page lists all
  eight layouts and the pricing page names Diary/EMA.
- `s/lint && s/test --no-a11y`.

## 15. Version bump

**Pending** — to be done by the CTO/maintainer per `AGENTS.md`
§Versioning after the PR is merged to `main`.

After Commit 11 passes `s/lint && s/test --no-a11y` (and `--a11y-only`
if the USP refocus touched template structure — recommended since
`home.html` and `pricing.html` are WCAG-tested surfaces):

- Bump the minor version in `pyproject.toml` (e.g. `0.18.1` → `0.19.0`).
- Per `AGENTS.md` §Versioning, the GitHub Actions workflow auto-updates
  the README badge and enables versioned container publishing on merge
  to `main`.
- Do **not** manually edit the README version badge — the CI workflow
  does that.

## 16. Open questions

- **Re-submission within a window.** Should a participant be able to
  revise their entry within the same window before it closes? Default:
  yes (matches the existing save-and-resume semantics — the
  `DiaryEntry.submitted_at` is set on first submit, but the
  `SurveyProgress` row stays editable until the window + grace closes).
  **Resolved in Commit 4:** the current implementation sets
  `submitted_at` on submit and marks progress as completed. Re-submission
  within the same window is not supported in v1 — the participant sees
  the thank-you page after submitting. This can be revisited if needed.
- **Entry cap.** Should there be a max number of windows per
  participant (e.g. to bound the `DiaryEntry` table for a 2-year
  diary)? Default: no cap; the survey's `closed_at` ends the schedule.
  **Resolved:** no cap in v1. Revisit if table growth becomes a concern.
- **Time zone handling.** Window times are stored UTC. The participant
  sees them in their locale (existing pattern). **Resolved in Commit 4:**
  `expected_start` / `expected_end` are stored as UTC `DateTimeField`s
  and rendered via the existing timezone-aware template tags in
  `diary_landing.html`.
- **Reminder idempotency.** The `process_diary_reminders` command does
  not store a `reminder_sent_at` timestamp on `DiaryEntry` (would
  require a migration). Instead, it relies on the daily command cadence
  — one reminder per day per open window. Re-running the command within
  the same day may re-send. **Resolved in Commit 9:** acceptable for a
  daily command. A `reminder_sent_at` field can be added in a follow-up
  if duplicate suppression becomes a concern.

## 17. Related documentation

- [Diary / EMA](diary-ema.md) — user-facing guide (creator workflow,
  participant experience, compliance dashboard, outline syntax).
- [Survey Layouts](survey-layouts.md) — user-facing guide to all
  layouts.
- [Survey Layouts (Technical)](survey-layouts-technical.md) — developer
  reference for the data model, runtime pipeline, and implementation
  details of all layouts.
- [Delphi (Consensus Rounds)](delphi.md) — the previous layout to ship;
  its dev-doc cleanup (marking Delphi as live) was the prerequisite for
  this branch.
- [Organise](groups-view.md) — the page where Diary/EMA is configured.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume
  carries the diary enrolment anchor and entry state.
- [Email Notifications](email-notifications.md) — the reminder email
  infrastructure.
- [Billing & Subscriptions](billing-and-subscriptions.md) — tier gating
  for layouts (Free: linear only; paid: all eight).
