---
title: Text Entry
category: features
priority: 4
---

The survey builder supports multiple ways to create survey content: Text Entry (importing from text format) and detailed follow-up question configuration. This is convenient when:

- You already have the survey designed in a document and prefer to import the structure instead of dragging and dropping questions in the visual builder.
- You want to lay out complex flows with repeatable sections or branching logic before wiring the final details in the UI.
- You need fine-grained control over follow-up text inputs for specific options.

> **New:** You can also create surveys using our [AI-Assisted Survey Generator](/docs/ai-survey-generator/), which helps you design surveys through natural conversation instead of writing markdown manually.

This document covers:

- [Bulk survey import](#bulk-survey-import) - Complete markdown syntax for importing surveys
- [Follow-up questions](#follow-up-questions) - Adding conditional text inputs to question options
- [Repeats](#repeats-nested-repeatable-sections) - Creating nested, repeatable sections

For more details on repeats, see [Repeats (Nested, Repeatable Sections)](/docs/collections/).

## Bulk survey import

This document captures the grammar the importer recognises and the conventions that keep identifiers stable when you later edit the survey.

## Authoring overview

Place the Markdown in the **Import questions** form for the survey you are editing. When you confirm the import, the system removes all existing question groups and questions owned by that survey and replaces them with the imported content. Collections, repeat groups, and branching conditions are created automatically. You can refine question copy, options, and wiring inside the builder after the import.

A minimal survey looks like this:

```markdown
# Group title
Group description

## Question title
Question description
(type)
```

Spacing is flexible, but keep the relative order (heading → optional description → type). Blank lines are ignored.

## Group headings

- Use `# <group title>` for each group.
- The first non-empty line after the heading (if it is not a question heading or type declaration) becomes the group description.
- Optionally append a stable identifier by placing it in curly braces at the end of the heading: `# Group title {group-id}`. The importer slugifies the identifier and keeps it unique.

## Question headings

- Use `## <question title>` inside a group.
- The next non-empty line that is not a type declaration becomes the question description.
- Declare the question type on a dedicated line wrapped in parentheses: `(text)`, `(mc_single)`, etc.
- Append a stable identifier with curly braces just like groups: `## Question {question-id}`.
- **Mark a question as required** by adding an asterisk `*` after the question title (before the ID if present): `## Question title* {question-id}`.

### Supported question types

| Type name | Description |
| --- | --- |
| `text` | Free-text short answer |
| `text number` | Numeric input validation |
| `mc_single` | Multiple choice (single answer) |
| `mc_multi` | Multiple choice (multiple answers) |
| `dropdown` | Select menu |
| `orderable` | Rank the provided items |
| `yesno` | Yes/No toggle |
| `image` | Image choice |
| `likert categories` | Likert scale with category labels (one per `-` line) |
| `likert number` | Likert scale defined by number range |

### Options and Likert metadata

- For option-based questions, supply each option on its own line starting with `-` (hyphen + space).
- **Follow-up text inputs**: To add a follow-up text field for any option, add an indented line starting with `+` (plus + space) immediately after the option. The text after `+` becomes the label for the follow-up input field that appears when the participant selects that option.
- For `likert number`, add key-value metadata lines after the type:
  - `min: 1`
  - `max: 5`
  - Optional `left:` and `right:` labels.

**Example with follow-up text:**

```markdown
## Employment status
(mc_single)
- Employed full-time
- Employed part-time
  + Please specify your hours per week
- Self-employed
  + What type of business?
- Unemployed
  + Are you actively seeking employment?
- Student
- Retired
```

**Follow-up guidelines:**

- Follow-up lines must start with `+` and be indented (at least 2 spaces or a tab)
- The text after `+` becomes the label for the follow-up input field
- Works with `mc_single`, `mc_multi`, `dropdown`, `orderable`, and `yesno` question types
- For `yesno` questions, you can optionally provide 2 options (for Yes and No) with follow-up labels
- Not all options need follow-ups—only add them where additional context is needed
- Follow-up responses are stored alongside the selected option in the survey response

## Follow-up questions

Follow-up text inputs allow you to conditionally show additional text fields based on respondents' answers. This is useful when you need more detail for specific options (e.g., "If you selected 'Other', please explain").

### Compatible question types

Follow-up text inputs work with:

- Multiple choice — single (`mc_single`)
- Multiple choice — multiple (`mc_multi`)
- Dropdown (`dropdown`)
- Yes/No (`yesno`)
- Orderable list (`orderable`)

### Configuration methods

You can add follow-up text inputs in three ways:

1. **Text Entry** (this document) - Use the `+` syntax shown above
2. **Visual builder** - Check "Enable follow-up text" for each option in the question editor
3. **API** - Include `followup_text` in the options structure

### How it works for respondents

When a respondent selects an option that has follow-up text enabled:

- A text input field appears with your custom label
- The field is hidden if they select a different option
- For multiple-choice questions with multiple selections, they see follow-up fields for each selected option that has it enabled

### Visual indicator

Questions with follow-up inputs configured show a badge in the question card listing which options have follow-up text. This helps you quickly identify questions with this feature when managing your survey.

### Data structure

Options with follow-up text are stored as:

```json
{
  "label": "Employed part-time",
  "value": "Employed part-time",
  "followup_text": {
    "enabled": true,
    "label": "Please specify your hours per week"
  }
}
```

For complete implementation details and examples, see [Branching Logic & Repeating Questions](/docs/branching-and-repeats/).

## Required questions

Mark a question as required by adding an asterisk `*` immediately after the question title. Required questions must be answered before participants can submit the form.

**Example:**

```markdown
## Age* {patient-age}
Age in years
(text number)

## Email address*
Please provide your email
(text)

## Consent to participate* {consent}
(yesno)
```

**Guidelines:**

- Place the asterisk directly after the question title, before any identifier in curly braces
- Works with all question types
- Required questions are validated on form submission
- The asterisk will appear in red in the preview

## Preview Viewer

Text Entry also has a real-time preview viewer. As you enter text the view renders it below - this is helpful because a unique identifier for each question and question-group automatically renders in the preview. This is needed if you choose to use the branching notation (see below).

## Additional Function

You may not want to use this function and Text Entry works without it. You may simply want to convert a Word document to text format and import the questions wholesale - you can add function for repeat questions (such as patients) or conditional branching in the Question Builder afterwards. But if you wish to use advanced features during import, it is possible to use the notation described below for some questions or groups to be iterative or show conditionally depending on answers that users give. This is detailed below.

### Repeatable collections

You can mark a group as repeatable so respondents can add multiple entries (e.g., visits, household members). Place `REPEAT` on the line immediately above the group heading.

```markdown
REPEAT-5
# Patient details

> REPEAT
> # Visit
> ...
```

Guidelines:

- `REPEAT` allows unlimited repeats; `REPEAT-5` limits the maximum to five entries; `REPEAT-1` means one allowed.
- Use `>` to indicate nested collections and repeat the `REPEAT` marker at the same depth as the child group heading.
- Nesting is limited to one level (parent → child). Deeper levels are ignored.
- Groups without a preceding `REPEAT` line become normal, non-collection groups.

### Conditional branching

Branching rules let you jump respondents to other questions or groups based on their answers. They follow this pattern, placed under the `(type)` line:

```markdown
? when <operator> <value> -> {target-id}
```

Example:

```markdown
# Intro {intro}
## Consent {intro-consent}
(text)
? when equals "Yes" -> {follow-up}
? when equals "No" -> {intro-exit}
```

Notes:

- Operators match the in-app condition builder: `equals`, `not_equals`, `contains`, `greater_than`, `greater_equal`, `less_than`, `exists`, and their `not_` variants.
- Values may be quoted. Operators like `exists` do not take a value.
- The target in curly braces can reference a group ID (jump to that group) or a question ID (jump directly to the question).
- IDs are normalised to lowercase slugs; ensure each ID is unique across all groups and questions.

## Error handling and validation

Text Entry provides comprehensive error detection and reporting at two levels:

### Live preview (immediate feedback)

As you type your Markdown in the import form, the **live structure preview** on the right side of the page parses your content in real-time and displays:

- The hierarchical structure of groups and questions
- Extracted IDs with color-coded badges (groups in purple, questions in teal)
- Question types and branching rules
- Repeat collection indicators
- **Required field markers** (red asterisks)
- **Warnings** for issues like questions appearing before group headings

This live preview uses the same parsing logic as the backend, so you'll catch most formatting issues—incorrect notation, missing indentation, malformed branching rules, etc.—**before you even submit the form**. The preview updates instantly as you edit, making it easy to iterate and fix problems.

### Backend validation (on submit)

When you click "Create survey", the backend parser performs a complete validation pass and will reject the import if any errors are found. The system checks for:

- **Empty markdown**: The document must contain at least one group and question
- **Questions before groups**: Questions must be declared inside a group (after a `#` heading)
- **Missing question types**: Every question must have a type declaration in parentheses
- **Invalid branch syntax**: Branching rules must include `when`, a valid operator, and a target ID in curly braces
- **Invalid operators**: Only recognised operators (equals, contains, greater_than, etc.) are allowed
- **Missing branch targets**: Branch rules must reference a valid group or question ID
- **Empty target IDs**: IDs in curly braces cannot be empty
- **Collection syntax errors**: REPEAT markers and nested collections must follow correct indentation patterns

If validation fails, the import form redisplays with:

- Your original Markdown content preserved in the textarea
- A **prominent error alert** at the top of the page describing exactly what went wrong and which line number (when applicable)
- The live preview still active so you can see the structure

This two-layer validation approach ensures that formatting and syntax errors are caught early (in the live preview) while data integrity issues are prevented by the backend before any database changes occur.

## Workflow tips

1. Draft the structure in Markdown using a familiar editor or export from a specification document.
2. Paste the text into the Text Entry form and review the live preview to confirm IDs, repeat badges, and branch targets look correct.
3. When ready, choose **Create survey**, acknowledge the overwrite warning, and import. The importer recreates question groups, questions, branching conditions, and collections.
4. Use the visual builder to fine-tune wording, add advanced logic, or connect the imported sections with additional navigation rules.

## Troubleshooting

- **Missing (type)**: Every question must declare a type on the line immediately after the description. The importer fails with a helpful error referencing the question title.
- **Unknown IDs**: Branch targets must refer to an existing group or question ID. Check the live preview to confirm spelling.
- **Duplicate IDs**: If two headings share the same curly-brace ID, the importer automatically de-duplicates by appending `-2`, `-3`, etc. Prefer choosing distinct IDs yourself for clarity.
- **Collections without groups**: A `REPEAT` marker must be followed by a valid group heading at the same nesting level.

Refer back to this guide whenever you need to import surveys in bulk or explain the syntax to collaborators.
