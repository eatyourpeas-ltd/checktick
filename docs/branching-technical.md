---
title: Branching Logic - Technical Guide
category: api
priority: 15
---

Technical documentation for developers implementing or extending branching logic and repeating questions.

## Database Models

### Condition Model

The `Condition` model stores branching logic rules:

```python
class Condition(models.Model):
    question = models.ForeignKey(Question)  # The question this condition applies to
    source_question = models.ForeignKey(Question)  # The question being checked
    expected_value = models.CharField()  # The answer that triggers this condition
    action = models.CharField(choices=ACTION_CHOICES)  # What to do when matched
    target_question = models.ForeignKey(Question, null=True)  # Where to jump/skip to
    order = models.IntegerField()  # Evaluation order for multiple conditions
```

**Action Types:**
- `SHOW` - Display the next question
- `JUMP_TO` - Skip ahead to target_question
- `SKIP` - Hide the next question
- `END_SURVEY` - Complete the survey

### CollectionDefinition Model

Collections (groups) can be marked as repeating:

```python
class CollectionDefinition(models.Model):
    survey = models.ForeignKey(Survey)
    name = models.CharField()
    order = models.IntegerField()
    max_count = models.IntegerField(null=True, blank=True)  # Null = unlimited
    parent = models.ForeignKey('self', null=True)  # For nested collections
```

### CollectionItem Model

Links questions or collections to their parent collection:

```python
class CollectionItem(models.Model):
    collection = models.ForeignKey(CollectionDefinition)
    question = models.ForeignKey(Question, null=True)
    nested_collection = models.ForeignKey(CollectionDefinition, null=True)
    order = models.IntegerField()
```

**Rules:**
- Either `question` or `nested_collection` must be set (not both)
- Collections can be nested one level deep
- Order determines the display sequence

## Relationships

### Question → Conditions

A question can have multiple conditions checked against it:

```python
# Conditions that check this question's answer
source_conditions = question.source_conditions.all()

# Conditions that control whether this question appears
target_conditions = question.condition_set.all()
```

### Collections Hierarchy

```
Survey
 └── CollectionDefinition (max_count=3)
      ├── CollectionItem → Question 1
      ├── CollectionItem → Question 2
      └── CollectionItem → Nested CollectionDefinition
           ├── CollectionItem → Question 3
           └── CollectionItem → Question 4
```

## API Endpoints

### Branching Data API

**Endpoint:** `GET /surveys/{slug}/builder/api/branching-data/`

Returns complete branching structure for visualization:

```json
{
  "questions": [
    {
      "id": "123",
      "text": "Question text",
      "order": 0,
      "group_name": "Demographics",
      "group_id": "456"
    }
  ],
  "conditions": {
    "123": [
      {
        "source_question_text": "Previous question",
        "expected_value": "Yes",
        "action": "SHOW",
        "target_question": "789",
        "summary": "When 'Previous question' = 'Yes': Show next question"
      }
    ]
  },
  "group_repeats": {
    "456": {
      "is_repeated": true,
      "count": 5  // or null for unlimited
    }
  }
}
```

**Implementation:** `checktick_app/surveys/views.py::branching_data_api()`

### Condition Management

**Create:** `POST /surveys/{slug}/builder/question/{qid}/conditions/`
**Update:** `PUT /surveys/{slug}/builder/question/{qid}/conditions/{cid}/`
**Delete:** `DELETE /surveys/{slug}/builder/question/{qid}/conditions/{cid}/`

Request body for create/update:

```json
{
  "source_question": 123,
  "expected_value": "Yes",
  "action": "JUMP_TO",
  "target_question": 456
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

## Text Entry (Bulk Import)

### Condition Syntax

```markdown
## Source Question
(mc_single)
- Option A
- Option B
-> Option A : {target-question-name}
-> Option B : SKIP
```

**Syntax Rules:**
- `->` prefix for condition lines
- Format: `-> [value] : [action]`
- Actions:
  - `{question-name}` - Jump to question
  - `SKIP` - Skip next question
  - `END` - End survey
  - Default (no action) - Show next

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

When rendering a survey, conditions are evaluated in order:

```python
def should_show_question(question, user_responses):
    conditions = question.condition_set.all().order_by('order')

    for condition in conditions:
        source_value = user_responses.get(condition.source_question.id)

        if source_value == condition.expected_value:
            if condition.action == 'SHOW':
                return True
            elif condition.action == 'JUMP_TO':
                return condition.target_question
            elif condition.action == 'SKIP':
                return False
            elif condition.action == 'END_SURVEY':
                return 'END'

    return True  # Default: show question
```

### Collection Instances

When a user adds a repeat instance:

```python
# Create new response instance
instance = ResponseInstance.objects.create(
    response=response,
    collection=collection_definition,
    instance_number=collection_definition.get_next_instance_number(response)
)

# Copy questions for this instance
for item in collection_definition.collectionitem_set.all():
    if item.question:
        QuestionResponse.objects.create(
            response=response,
            question=item.question,
            collection_instance=instance
        )
```

## Testing

### Test Files

- `test_bulk_upload_branching.py` - Markdown import with conditions
- `test_conditions.py` - Condition model and evaluation
- `test_collections.py` - Repeating groups

### Key Test Scenarios

**Branching:**
- Condition creation via API
- Multiple conditions on one question
- Invalid target questions
- Circular dependencies
- Conditions across groups

**Repeats:**
- Unlimited repeats
- Limited repeats (reaching max)
- Nested collections
- Collection ordering
- Response instance creation

### Example Test

```python
def test_condition_evaluation():
    # Create survey with branching
    q1 = Question.objects.create(text="Trigger question", type="mc_single")
    q2 = Question.objects.create(text="Target question", type="text")

    Condition.objects.create(
        question=q2,
        source_question=q1,
        expected_value="Yes",
        action="SHOW"
    )

    # Test evaluation
    response = {"q1": "Yes"}
    assert should_show_question(q2, response) == True

    response = {"q1": "No"}
    assert should_show_question(q2, response) == False
```

## Performance Considerations

### Database Queries

The branching data API performs:
- 1 query for questions
- 1 query for conditions (with select_related)
- 1 query for collection items (for repeats)

**Optimization:**

```python
# Prefetch related data
questions = Question.objects.filter(
    survey=survey
).select_related('group').prefetch_related(
    Prefetch('condition_set',
             queryset=Condition.objects.select_related('source_question'))
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
- [Import Documentation](import.md) - Text Entry syntax
- [API Documentation](api.md) - REST API reference
- [Collections](collections.md) - Collection system details
