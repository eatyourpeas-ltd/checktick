---
title: Branching Logic - Technical Guide
category: development
priority: 15
---

Technical documentation for developers implementing or extending branching logic and repeating questions.

## Database Models

### SurveyQuestionCondition Model

The `SurveyQuestionCondition` model stores branching rules:

```python
class SurveyQuestionCondition(models.Model):
    question = models.ForeignKey(SurveyQuestion, related_name="conditions")
    operator = models.CharField(choices=["eq", "neq", "contains", "gt", ...])
    value = models.CharField(blank=True)
    target_question = models.ForeignKey(SurveyQuestion, null=True, blank=True)
    target_group = models.ForeignKey(QuestionGroup, null=True, blank=True)  # section target
    action = models.CharField(choices=["show", "hide", "jump_to", "end_survey"])
    order = models.PositiveIntegerField(default=0)
    description = models.CharField(blank=True)
```

**Action Types:**

- `show` - Reveal a hidden-by-default target question when condition matches (only valid when `target_question.hidden_by_default = True`)
- `hide` - Hide a shown-by-default target question when condition matches (only valid when `target_question.hidden_by_default = False`)
- `jump_to` - Skip forward to target question (or to the first question of `target_group`); forward-only
- `end_survey` - End survey flow

### `hidden_by_default` on SurveyQuestion

`SurveyQuestion.hidden_by_default` (bool, default `False`) declares a question's default visibility on the question itself. This replaces the old implicit model where "hidden by default" was a side-effect of having an incoming `SHOW` condition.

- `SHOW` conditions are only valid against `hidden_by_default = True` targets.
- `HIDE` conditions are only valid against `hidden_by_default = False` targets.
- The data migration backfills `hidden_by_default = True` for any question with an incoming `SHOW` condition, preserving existing behaviour.

### `target_group` (section targets)

The `target_group` FK is re-added in migration `0053` (it was removed in `0031` after being unused). When set, the section resolves to its first question at config-build time (`_build_branching_config`, `branching_data_api`), so the evaluation engine sees a normal `jump_to` with a `target_question`. No new action type, no new participant code path.

**Validation in `clean()`:**

- `target_group` must belong to the same survey as the triggering question.
- `target_group` must not be the source question's group (no-op jump).
- `target_group` must be non-empty (cannot jump to an empty section).
- `SHOW` and `HIDE` cannot target a section — only `jump_to` can.
- `jump_to` target (question or resolved section) must be later in the resolved question order (forward-only).

### CollectionDefinition Model

Collections (groups) can be marked as repeating:

```python
class CollectionDefinition(models.Model):
    survey = models.ForeignKey(Survey, related_name="collections")
    key = models.SlugField()  # unique per survey
    name = models.CharField(max_length=255)
    cardinality = models.CharField(choices=["one", "many"], default="many")
    min_count = models.PositiveIntegerField(default=0)
    max_count = models.PositiveIntegerField(null=True, blank=True)  # Null = unlimited
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children")
```

### CollectionItem Model

Links question groups or child collections to a parent collection:

```python
class CollectionItem(models.Model):
    collection = models.ForeignKey(CollectionDefinition, related_name="items")
    item_type = models.CharField(choices=["group", "collection"])
    group = models.ForeignKey(QuestionGroup, null=True, blank=True)
    child_collection = models.ForeignKey(CollectionDefinition, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
```

**Rules:**

- Exactly one of `group` or `child_collection` must be set
- Collections can be nested one level deep
- `order` determines item order *within the collection definition*

## Relationships

### SurveyQuestion → Conditions

A survey question can have multiple branching conditions:

```python
# Outgoing conditions triggered by this question's answer
outgoing_conditions = question.conditions.all()

# Incoming conditions that point to this question
incoming_conditions = question.incoming_conditions.all()
```

### Collections Hierarchy

```
Survey
 └── CollectionDefinition (max_count=3)
      ├── CollectionItem → Group A
      ├── CollectionItem → Group B
      └── CollectionItem → Child CollectionDefinition
           ├── CollectionItem → Group C
           └── CollectionItem → Group D
```

## Runtime Ordering Contract

To keep authoring and runtime consistent, ordering is derived through a shared pipeline in `checktick_app/surveys/views.py`:

- `_resolved_group_order_ids(survey)`
  - Uses `survey.style["group_order"]` first
  - Filters stale/non-existent IDs
  - Appends remaining groups sorted by name (case-insensitive), then id
- `_order_questions_by_group(survey, questions)`
  - Applies resolved group order
  - Orders questions within each group by `(question.order, id)`
- `_annotate_question_render_sequence(survey, questions)`
  - Annotates `idx`, `group_start`, `group_end`, `has_show_condition`

This same ordering is used by:

- Survey Map API (`branching_data_api`)
- Preview (`/surveys/{slug}/preview/`)
- Live participant routes (`/take/`, `/take/unlisted/...`, `/take/token/...`)

Result: **Survey Map = Preview = Live** for question-group sequence.

## API Endpoints

### Branching Data API

**Endpoint:** `GET /surveys/{slug}/builder/api/branching-data/`

Returns ordered branching structure for visualization:

```json
{
  "questions": [
    {
      "id": "123",
      "text": "Question text",
      "full_text": "Full question text",
      "order": 0,
      "group_name": "Demographics",
      "group_id": "456"
    }
  ],
  "conditions": {
    "123": [
      {
        "operator": "eq",
        "value": "Yes",
        "action": "show",
        "target_question": "789",
        "target_group": null,
        "target_group_name": null,
        "description": "",
        "summary": "equals Yes"
      }
    ]
  },
  "group_repeats": {
    "456": {
      "is_repeated": true,
      "count": 5
    }
  }
}
```

**Implementation:** `checktick_app/surveys/views.py::branching_data_api()`

### Condition Management

**Create:** `POST /surveys/{slug}/builder/questions/{qid}/conditions/create`
**Update:** `POST /surveys/{slug}/builder/questions/{qid}/conditions/{cid}/update`
**Delete:** `POST /surveys/{slug}/builder/questions/{qid}/conditions/{cid}/delete`

Request body for create/update:

```json
{
  "operator": "eq",
  "value": "Yes",
  "action": "jump_to",
  "target_type": "section",
  "target_group": 456,
  "order": 0,
  "description": ""
}
```

For question targets, use `"target_type": "question"` and `"target_question": 789`. For `end_survey`, omit the target fields.

## Builder Route Security

Every Builder view enforces the same security contract:

- `@login_required` — unauthenticated users are redirected to login.
- `require_can_edit` — returns HTTP 403 for non-editors (viewers, outsiders).
- HTTP method restrictions — wrong methods return HTTP 405.
- CSRF tokens on all POST forms.
- No inline JS — all `<script>` tags are external and nonce'd, keeping the Builder CSP-safe.
- XSS sanitisation via `strip_tags` on user-supplied section/question names.
- Tests cover permission (403), XSS, and method (405) cases for each Builder view.

## HTMX Interaction Layer

Section switching and "Add section" use HTMX partial swaps:

- HTMX requests swap the relevant region (rail + main area) without a full reload.
- Non-HTMX requests gracefully degrade to full page loads — the same URL works with JavaScript disabled.
- All JS is external and CSP-compliant (nonce'd), matching the existing `groups-page.js` / `builder-rail.js` pattern. No inline event handlers.

## Branching Visualizer

### Frontend Architecture

**File:** `checktick_app/static/js/branching-visualizer.js`

The visualizer uses HTML5 Canvas to render a git-graph style flow diagram.

**Key Functions:**

```javascript
// Fetch survey structure
async function loadData() {
  const data = await fetch(`/surveys/${slug}/builder/api/branching-data/`);
  questions = data.questions;
  conditions = data.conditions;
  groupRepeats = data.group_repeats;
}

// Render the graph
function drawGraph() {
  // Calculate node positions
  // Draw group background regions
  // Draw connections between nodes
  // Draw nodes and labels
  // Draw repeat badges
}

// Draw a question node
function drawCircleNode(x, y, radius, hasConditions) {
  // Primary color for conditional questions
  // Accent color for regular questions
}

// Draw repeat icon
function drawRepeatIcon(x, y, size, color) {
  // Custom canvas-drawn circular arrow
}
```

**Layout Algorithm:**

1. Calculate vertical positions for questions (40px spacing)
2. Add extra spacing between groups (20px)
3. Track group regions (startY, endY)
4. Draw group backgrounds with alternating shading
5. Draw vertical lines connecting sequential questions
6. Draw bezier curves for branching connections
7. Draw nodes on top
8. Add condition count badges
9. Add repeat badges for groups

### Theme Integration

Colors are extracted from DaisyUI theme:

```javascript
// Try to get colors from DOM elements
const primaryElement = document.querySelector('.btn-primary');
const primaryStyle = getComputedStyle(primaryElement);
colors.primary = primaryStyle.backgroundColor;

// Fallback to CSS variables
const p = styles.getPropertyValue('--p').trim();
if (p) colors.primary = `hsl(${p})`;
```

**Color Usage:**

- `colors.primary` - Conditional questions, badges
- `colors.accent` - Regular questions
- `colors.border` - Connecting lines
- `rgba(59, 130, 246, ...)` - Repeat badges

## Outline

### Condition Syntax

```markdown
## Source Question {source-question}
(mc_single)
- Option A
- Option B
? show when equals "Option A" -> {hidden-question}    # reveal a HIDDEN question
? hide when equals "Option B" -> {shown-question}      # hide a shown question
? when equals "Option A" -> #Target-Section            # jump to a section (default action)
? end  when equals "Option B"                            # end the survey
```

**Syntax Rules:**

- `?` prefix for condition lines
- Optional action keyword: `show`, `hide`, `end` (default is `jump_to` if omitted)
- Format: `? [action] when <operator> <value> -> {target-id}` or `-> #section-name`
- Common operators: `equals`, `not_equals`, `contains`, `greater_than`, `less_than`
- Question targets: `{question-id}`
- Section targets: `#section-name` (resolved to `target_group` at import time, then to the first question at config-build time)
- `HIDDEN` keyword on a question marks it `hidden_by_default = True`

**Validation at import time:**

- `show` targeting a non-`HIDDEN` question → rejected
- `hide` targeting a `HIDDEN` question → rejected
- `show` / `hide` with a `#section` target → rejected (sections are not show/hide-able)
- `jump_to` targeting an earlier question → rejected (forward-only)

### Repeat Syntax

```markdown
# Collection Name
REPEAT

## Question 1
...
```

Or with a limit:

```markdown
# Collection Name
REPEAT-5

## Question 1
...
```

**Implementation:** `checktick_app/surveys/markdown_import.py`

## Survey Runtime Logic

### Condition Evaluation

Client-side branching uses `checktick_app/static/js/branching.js` with config produced by `_build_branching_config(...)`.

Supported actions and behavior:

- `show`: target question is hidden by default (`hidden_by_default = True`), shown when an incoming SHOW condition matches
- `hide`: target question is shown by default (`hidden_by_default = False`), hidden when an incoming HIDE condition matches
- `jump_to`: hides questions between current and target in configured question order (forward only)
- `end_survey`: hides subsequent questions after trigger

`should_show_question` (branching.py) is rewritten around the `hidden_by_default` toggle with symmetric override logic:

```python
if not question.hidden_by_default:
    # Shown by default — check for HIDE overrides
    for condition in incoming_hide_conditions(question):
        if evaluate_condition(condition, answers):
            return False
    return True
else:
    # Hidden by default — check for SHOW overrides
    for condition in incoming_show_conditions(question):
        if evaluate_condition(condition, answers):
            return True
    return False
```

Condition evaluation follows question order from `branching_config.questions`, generated from the same runtime ordering pipeline used by Survey Map, preview, and live routes.

### Collection Instances

Collection definitions remain backend entities for repeat metadata and response structuring.

Important: participant page rendering order is currently driven by the shared question-order pipeline (`group_order` + per-group question order), not by traversing `CollectionItem` trees.

## Testing

### Test Files

- `test_branching_refactor_migration.py` - Migration backfill + skip→hide rename
- `test_branching_engine.py` - Toggle visibility, forward-only validation, `should_show_question`
- `test_builder_hidden_by_default.py` - Builder UI: toggle, constrained action picker, relabel
- `test_builder_conditions_payload.py` - Condition payload serialization, target sections
- `test_outline_new_grammar.py` - Outline HIDDEN flag, action keywords, section targets, rejections
- `test_section_targets.py` - Section target resolution, config build, export round-trip, clean()
- `test_bulk_upload_branching.py` - Markdown import with branching and repeats
- `test_groups_reorder.py` - Group ordering persistence
- `test_groups_repeats.py` - Repeat creation/edit/removal
- `test_collections_models.py` - Collection model constraints
- `test_runtime_ordering_consistency.py` - Survey Map/Preview/Live ordering consistency

### Key Test Scenarios

**Branching + ordering consistency:**

- Survey Map ordering matches Preview ordering
- Survey Map ordering matches live `/take/*` ordering
- Partial/stale `group_order` IDs produce the same fallback order as `/groups/`
- Branching config question order follows runtime ordered question list

Relevant coverage includes:

- `checktick_app/surveys/tests/test_runtime_ordering_consistency.py`
- `checktick_app/surveys/tests/test_groups_reorder.py`
- `checktick_app/surveys/tests/test_xss_survey_take.py`

## Performance Considerations

### Database Queries

The branching data API performs:

- 1 query for questions
- 1 query for conditions (with select_related)
- 1 query for collection items (for repeats)

**Optimization:**

```python
# Prefetch related data for branching visualisation
questions = SurveyQuestion.objects.filter(
    survey=survey
).select_related('group').prefetch_related(
    'conditions',
    'conditions__target_question',
    'conditions__target_group'
)
```

### Frontend Rendering

- Canvas rendering is fast even with 100+ questions
- Debounce resize events (200ms)
- Only redraw when data changes
- Use requestAnimationFrame for smooth updates

## Future Enhancements

Potential improvements to the branching system:

1. **Complex Conditions** - AND/OR logic, multiple values
2. **Condition Groups** - Reusable condition sets
3. **Visual Editor** - Drag-and-drop condition builder
4. **Condition Templates** - Common patterns (e.g., "Other → specify")
5. **Runtime Validation** - Detect unreachable questions
6. **Performance Metrics** - Track which branches are used
7. **Version History** - Track condition changes over time
8. **Branching targets by section** - Implemented. Section targets resolve to the first question at config-build time via the `target_group` FK. See `docs/branching-and-repeats.md` for the user-facing guide.

## Migration Notes

When upgrading from earlier versions:

1. Migration `0052` adds `hidden_by_default` and renames `skip` → `hide`.
2. The migration backfills `hidden_by_default = True` for any question with an incoming `SHOW` condition, preserving existing behaviour.
3. Existing `skip` conditions are renamed to `hide` in place (stored value change).
4. Migration `0053` re-adds `target_group` (removed in `0031`) for section targets.
5. Existing surveys work without changes — the visualizer and engine pick up the new fields automatically.
6. Collections without max_count are unlimited.

## Related Documentation

- [Branching Logic & Repeating Questions](branching-and-repeats.md) - User guide
- [Import Documentation](import.md) - Outline syntax
- [API Documentation](api.md) - REST API reference
- [Collections](collections.md) - Collection system details
