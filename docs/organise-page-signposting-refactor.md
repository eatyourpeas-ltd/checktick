# Organise page: signposting refactor (working note)

Not a published doc — a guide for a small follow-up PR that resolves the
Organise page's mild identity problem.

## Implementation status

**Implemented (language + framing approach):** the sub-nav approach
originally prescribed below was reconsidered and dropped. The page is not
tall enough for most surveys (linear is the majority) to warrant jump
links, and a sub-nav would add chrome without value. The real problem
was language, not navigation. What shipped:

- Renamed the per-section "Publish" button to "Share" (title: "Share to
  Question Bank") — aligns with the destination page's "Share section as
  template" heading and the established "Question Bank" concept, and
  avoids clashing with publishing the survey itself
  (`Survey.Status.PUBLISHED`).
- Rewrote the intro to frame the page's purpose (survey-wide settings +
  Question Bank) instead of listing operations.
- Added a single "Sections" heading above the section list to mark the
  boundary between the layout half and the section-operations half.
- Fixed broken breadcrumbs on the section publish page
  (`question_group_publish.html`): the "Sections" crumb linked to a
  non-existent `/surveys/groups/` URL; now links to the survey-specific
  Organise page. The `question_group.name` reference (context variable
  didn't exist — view passes `group`) was fixed, and the final crumb now
  says "Share" instead of "Publish".

## Original analysis (preserved for context)

## The problem

The Organise page (`/surveys/<slug>/groups/`, `groups.html`, view
`survey_groups`) does two related but distinct things:

1. **Shape decisions** (top of page) — the layout picker (Linear / Section
   menu / RCT) and the per-layout config cards (Section menu settings, RCT
   arms). These are survey-level: "what kind of survey is this?"
2. **Bulk section operations** (below) — reorder, multi-section repeats,
   publish sections as templates. These are section-level: "arrange the
   sections I have."

The division is correct — the Builder handles single-section /
single-question editing; the Organise page handles multi-section and
survey-shape decisions. Both belong in the "organise" bucket. The problem
is **discoverability**: the page doesn't tell you it has two halves, and a
tall RCT config card (arms + per-section checkboxes) can push the section
operations below the fold with no signal they're there.

## What to avoid

- **Splitting into separate routes** (`/sections/`, `/publish/`). Loses the
  "one place to organise" property; the layout config genuinely belongs
  above the section list (pick a shape, then arrange within it). The Survey
  Map is already its own route and that's the right call for the visualiser,
  but layout + section ops are best on one page.
- **Abstracting into partials as the primary fix.** Partials
  (`_layout_picker.html`, `_rct_config.html`, `_bulk_sections.html`) would
  help maintainability — `groups.html` is long — but they're a refactor,
  not an identity fix. Do them if the template is hard to work with, but
  they don't change the user-facing identity.

## What to do (1–2 commits)

### Commit 1: sticky sub-nav + section headings + one-line intro

Add a one-line intro at the top of the Organise page that frames the two
halves, and a sticky in-page anchor sub-nav that lets the user jump
between them. Wrap the existing section operations in a `<section>` with
its own heading ("Sections") so the page reads as two clear parts.

**Files:** `groups.html` only (no view changes — the sections already
exist, just need wrapping + an anchor nav).

**Template structure:**

```html
<!-- After the page title, before the layout picker -->
<p class="text-sm text-base-content/70 mb-4">
  {% trans 'Choose your survey layout, then arrange sections, repeats, and publication below.' %}
</p>

<!-- Sticky sub-nav (daisyUI menu-sm or tabs) -->
<nav class="sticky top-0 z-10 bg-base-100/95 backdrop-blur border-b border-base-200 py-2 mb-4">
  <ul class="menu menu-horizontal menu-sm gap-1">
    <li><a href="#layout" class="active">{% trans 'Layout' %}</a></li>
    <li><a href="#sections">{% trans 'Sections' %}</a></li>
    <li><a href="#publish">{% trans 'Publish sections' %}</a></li>
    <li><a href="{{ survey.slug }}/survey-map/">{% trans 'Survey Map' %}</a></li>
  </ul>
</nav>

<!-- Existing layout picker section, wrapped -->
<section id="layout" class="..."> ... </section>

<!-- Existing section operations, wrapped in a new <section id="sections"> -->
<section id="sections" class="...">
  <h2 class="...">{% trans 'Sections' %}</h2>
  ... existing reorder / repeat / publish-as-template content ...
</section>
```

**JS for active-tab highlighting:** a small `IntersectionObserver` (or
scroll listener) that toggles `.active` on the sub-nav links as the user
scrolls between `#layout`, `#sections`, `#publish`. ~15 lines of vanilla
JS in `groups-page.js` (already loaded on this page). No new dependency.

**No view changes.** The context already has everything the template needs.

### Commit 2 (optional): extract partials

If `groups.html` is hard to maintain after commit 1, extract:

- `surveys/partials/_layout_picker.html` — the three layout cards.
- `surveys/partials/_section_menu_config.html` — the Section menu config card.
- `surveys/partials/_rct_config.html` — the RCT config card + warnings.
- `surveys/partials/_bulk_sections.html` — the section list + repeat +
  publish-as-template UI.

`groups.html` becomes ~30 lines of `{% include %}` calls. Pure
maintainability; no user-facing change. Skip if the template is still
readable after commit 1.

## What not to do in this PR

- Don't move the Survey Map into the Organise page — it's correctly its own
  route; the sub-nav links to it externally.
- Don't change the Builder — it handles single-section / single-question
  editing and that division is sound.
- Don't add new features — this is IA only. The RCT config card is tall but
  functional; the sub-nav makes it discoverable without changing its
  content.

## Tests

- A test that asserts the sub-nav renders with Layout / Sections /
  Publish / Survey Map links for a linear survey, a section_menu survey,
  and an RCT survey.
- A test that `#sections` anchor exists and is reachable.
- No new view tests — the sections already render; this only adds wrapping
  + nav.
