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
    action = models.CharField(choices=["show", "jump_to", "skip", "end_survey"])
    order = models.PositiveIntegerField(default=0)
    description = models.CharField(blank=True)
```

**Action Types:**

- `show` - Display target question when condition matches (hidden by default)
- `jump_to` - Skip forward to target question
- `skip` - Hide target question when condition matches
- `end_survey` - End survey flow

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
  "target_question": 456,
  "order": 0,
  "description": ""
}
```

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
? when equals "Option A" -> {target-question}
? when equals "Option B" -> {another-target}
```

**Syntax Rules:**

- `? when` prefix for condition lines
- Format: `? when <operator> <value> -> {target-id}`
- Common operators: `equals`, `not_equals`, `contains`, `greater_than`, `less_than`
- Targets can be question IDs (or group IDs during import, resolved to the first question in that group)

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

- `show`: target question is hidden by default, shown when an incoming SHOW condition matches
- `jump_to`: hides questions between current and target in configured question order
- `skip`: hides the target question when condition matches
- `end_survey`: hides subsequent questions after trigger

Condition evaluation follows question order from `branching_config.questions`, generated from the same runtime ordering pipeline used by Survey Map, preview, and live routes.

### Collection Instances

Collection definitions remain backend entities for repeat metadata and response structuring.

Important: participant page rendering order is currently driven by the shared question-order pipeline (`group_order` + per-group question order), not by traversing `CollectionItem` trees.

## Testing

### Test Files

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
    'conditions__target_question'
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

## Migration Notes

When upgrading from earlier versions:

1. Run migrations to add new fields
2. Existing surveys work without changes
3. Branching visualizer appears automatically
4. No data migration needed for conditions
5. Collections without max_count are unlimited

## Related Documentation

- [Branching Logic & Repeating Questions](branching-and-repeats.md) - User guide
- [Import Documentation](import.md) - Outline syntax
- [API Documentation](api.md) - REST API reference
- [Collections](collections.md) - Collection system details
