# UX Observations – Pentest Feedback

> Scratch file for tracking UX issues raised in pentest. Remove before next release.

---

## 1. Survey Dashboard – Building a Survey (3-option signposting)

### Current behaviour

`dashboard.html` already contains two alert banners that mention the 3 ways to build a survey
(Question Builder, Text Entry, AI Assistant):

- `alert-info` when the survey has **no questions** ("Get started by adding questions")
- `alert-warning` when the survey **has questions** ("Edit your questions")

Both present the 3 routes as prose hyperlinks inside a single-line alert. The pentester
did not notice them — alerts/banners are frequently skimmed over or treated as
informational noise rather than actionable navigation.

### What needs to change

Replace **both** alerts (has_questions and not has_questions) with a **3-card grid**
that makes each building option a distinct, visually scannable action card. The same
card UI should appear regardless of whether questions already exist (with wording
adjusted: "Build" vs "Edit").

Suggested card layout (DaisyUI `card` inside a `grid grid-cols-3`):

| Card | Icon | Title | Sub-text | Link |
|------|------|-------|----------|------|
| Visual Builder | builder icon | "Question Builder" | "Click to add or edit questions visually" | `/surveys/<slug>/groups/` |
| Text Editor | document icon | "Text Entry" | "Write questions in markdown or paste from docs" | `/surveys/<slug>/bulk-upload/?tab=manual` |
| AI Assistant | sparkle icon | "AI Assistant" | "Describe your survey and let the AI draft it" | `/surveys/<slug>/bulk-upload/?tab=ai` |

The card grid should appear **directly below the stat row** (today/7-day/trend stats),
before the style panel, and be always visible — not only when questions are absent.

---

## 2. Navbar label for the shared question group library

### The real issue

The problem isn't that "Question Groups" means two different things — it's a
correct noun for both the sections inside a survey *and* the shared importable
collections. The issue is that the navbar label gives no signal that it points
to a **shared, browsable pool** that users can import from, rather than their
own survey sections.

Question groups range from formally validated clinical instruments (PHQ-9, GAD-7)
to informal sets shared by users or organisations for reuse. Both are question
groups — the navbar leads to where those shared ones live.

### Decision

Rename the top navbar item from **"Question Groups"** to **"Question Bank"**.

- The noun *question group* stays correct everywhere it describes the concept.
- "Question Bank" names the shared pool/destination — familiar to clinical and
  academic audiences, implies something you draw from rather than just view.
- Headings and descriptions on the Question Bank page and inside survey pages
  can continue to use "question group" as the noun.

### Scope of changes

- `base.html` — both mobile dropdown and desktop menu items
- `published_templates_list.html` — page title, breadcrumb, h1
- `groups.html` — reference from empty state and collapsed strip updated

---

## 3. Datasets page – lack of purpose statement

### Current behaviour

`dataset_list.html` has a heading "Datasets" and a Create/Request button, but no
explanation of what datasets *are for* or how they relate to surveys.

### What needs to change

Add a short explainer callout beneath the heading:

> "Datasets are standardised choice lists that power **dropdown questions** in the
> survey builder. For example, the NHS Data Dictionary provides Ethnic Category codes
> and Treatment Function Codes — import one and it becomes available in any dropdown
> question without manual data entry."

---

## 4. Question Groups vs Questions – hierarchy not clear inside a survey

### Current behaviour

The `groups.html` page has a useful paragraph about what Question Groups are, but there
is no visual representation of the two-level hierarchy (Group → Questions inside it).
New users are unsure whether they should be adding "groups" or "questions" first.

### What needs to change

Add a compact visual hierarchy explainer (collapsible `<details>` so it hides for
returning users) on `groups.html`, showing:

```
This survey
 └── Question Group (e.g. "Demographics")
      ├── Question: What is your name?
      └── Question: Date of birth?
 └── Question Group (e.g. "Clinical")
      └── Question: Chief complaint?
```

Also add a link from this page directly to the Template Library:
"Want a ready-made group? Browse the Template Library →"

---

## 5. Published Question Group Templates – import journey is unclear

### Current behaviour

Importing a template from the library takes users to a confirmation page, but there is
nothing on the survey dashboard or groups page that prompts users to *discover* the
library as a starting point.

### What needs to change

On the `groups.html` page (when the survey has zero groups) add an empty-state prompt:

> "No groups yet. Start from scratch or [browse the Template Library] to import
> ready-made question sets."
