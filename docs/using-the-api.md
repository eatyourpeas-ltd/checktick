---
title: Using the API
category: api
priority: 2
---

This guide provides comprehensive documentation for creating and managing surveys via the API, including all supported question types, JSON structure, and advanced features.

## Account Tier Limits

**Important:** The API enforces tier-based limits for survey creation and collaboration. See the [API Reference](api.md#account-tier-limits) for complete details.

**Quick summary:**

- **FREE tier**: 3 surveys max, no collaborators
- **PRO tier**: Unlimited surveys, up to 10 editors per survey (no viewers)
- **ORGANISATION tier**: Unlimited surveys and collaborators, viewer role available
- **ENTERPRISE tier**: All ORGANISATION features plus custom branding and SSO

API requests that exceed tier limits will return `403 Forbidden` errors with upgrade guidance.

## Question Types

CheckTick supports the following question types when creating surveys via the API:

### Text (`text`)

Free-text input for short or long answers.

```json
{
  "text": "What is your feedback?",
  "type": "text",
  "order": 1
}
```

**Optional fields:**

- `required` (boolean): Whether the question must be answered
- `help_text` (string): Additional guidance shown to respondents

### Number (`number`)

Numeric input only.

```json
{
  "text": "What is your age?",
  "type": "number",
  "order": 2
}
```

### Multiple Choice - Single Select (`mc_single`)

Radio button selection - respondents can choose only one option.

**Simple format:**

```json
{
  "text": "What is your favorite color?",
  "type": "mc_single",
  "options": ["Red", "Blue", "Green", "Other"],
  "order": 3
}
```

**Rich format with follow-up text:**

```json
{
  "text": "What is your favorite color?",
  "type": "mc_single",
  "options": [
    {"label": "Red", "value": "red"},
    {"label": "Blue", "value": "blue"},
    {"label": "Green", "value": "green"},
    {
      "label": "Other",
      "value": "other",
      "followup_text": {
        "enabled": true,
        "label": "Please specify your favorite color"
      }
    }
  ],
  "order": 3
}
```

### Multiple Choice - Multi Select (`mc_multi`)

Checkbox selection - respondents can choose multiple options.

**Simple format:**

```json
{
  "text": "Which languages do you speak?",
  "type": "mc_multi",
  "options": ["English", "Spanish", "French", "German", "Other"],
  "order": 4
}
```

**Rich format with follow-up text:**

```json
{
  "text": "Which languages do you speak?",
  "type": "mc_multi",
  "options": [
    {"label": "English", "value": "english"},
    {"label": "Spanish", "value": "spanish"},
    {"label": "French", "value": "french"},
    {
      "label": "Other",
      "value": "other",
      "followup_text": {
        "enabled": true,
        "label": "Please specify which other languages"
      }
    }
  ],
  "order": 4
}
```

### Dropdown (`dropdown`)

Select dropdown - single selection from a list.

**Simple format:**

```json
{
  "text": "Select your country",
  "type": "dropdown",
  "options": ["USA", "UK", "Canada", "Australia", "Other"],
  "order": 5
}
```

**Rich format with follow-up text:**

```json
{
  "text": "Select your country",
  "type": "dropdown",
  "options": [
    {"label": "USA", "value": "usa"},
    {"label": "UK", "value": "uk"},
    {
      "label": "Other",
      "value": "other",
      "followup_text": {
        "enabled": true,
        "label": "Please specify your country"
      }
    }
  ],
  "order": 5
}
```

### Yes/No (`yesno`)

Boolean choice presented as Yes/No radio buttons.

**Simple format:**

```json
{
  "text": "Do you have any concerns?",
  "type": "yesno",
  "order": 6
}
```

**Rich format with follow-up text:**

```json
{
  "text": "Do you have any concerns?",
  "type": "yesno",
  "options": [
    {
      "label": "Yes",
      "value": "yes",
      "followup_text": {
        "enabled": true,
        "label": "Please describe your concerns"
      }
    },
    {"label": "No", "value": "no"}
  ],
  "order": 6
}
```

### Likert Scale (`likert`)

Numeric or categorical scale rating.

**Numeric scale:**

```json
{
  "text": "How satisfied are you?",
  "type": "likert",
  "options": {
    "min": 1,
    "max": 5,
    "min_label": "Very Dissatisfied",
    "max_label": "Very Satisfied"
  },
  "order": 7
}
```

**Categorical scale:**

```json
{
  "text": "How often do you exercise?",
  "type": "likert",
  "options": ["Never", "Rarely", "Sometimes", "Often", "Always"],
  "order": 8
}
```

### Orderable List (`orderable`)

Drag-and-drop list where respondents rank options.

**Simple format:**

```json
{
  "text": "Rank these features by importance",
  "type": "orderable",
  "options": ["Speed", "Reliability", "Cost", "Support"],
  "order": 9
}
```

**Rich format with follow-up text:**

```json
{
  "text": "Rank these features by importance",
  "type": "orderable",
  "options": [
    {"label": "Speed", "value": "speed"},
    {"label": "Reliability", "value": "reliability"},
    {"label": "Cost", "value": "cost"},
    {
      "label": "Other",
      "value": "other",
      "followup_text": {
        "enabled": true,
        "label": "What other feature is important to you?"
      }
    }
  ],
  "order": 9
}
```

### Image Choice (`image`)

Visual selection where respondents choose from image options.

```json
{
  "text": "Select your preferred design",
  "type": "image",
  "options": [
    {"label": "Design A", "value": "design_a", "image_url": "/static/images/design_a.png"},
    {"label": "Design B", "value": "design_b", "image_url": "/static/images/design_b.png"}
  ],
  "order": 10
}
```

## Follow-up Text Inputs

For certain question types, you can configure **follow-up text inputs** that appear conditionally based on the respondent's answer. This is useful when you need additional detail for specific options.

### Supported Question Types

Follow-up text inputs are supported for:

- `mc_single` (Multiple choice - single select)
- `mc_multi` (Multiple choice - multi select)
- `dropdown`
- `orderable`
- `yesno`

### Configuration Format

To enable a follow-up text input for a specific option, use the rich object format and add a `followup_text` property:

```json
{
  "label": "Option label",
  "value": "option_value",
  "followup_text": {
    "enabled": true,
    "label": "Custom prompt for the follow-up input"
  }
}
```

### Response Data Format

When a survey response includes follow-up text, the answers will contain both the main answer and follow-up fields:

```json
{
  "q_123": "other",
  "q_123_followup_2": "I prefer a custom solution that fits my specific needs"
}
```

Follow-up fields use the naming pattern:

- `q_{question_id}_followup_{option_index}` for multiple choice, dropdown, and orderable questions
- `q_{question_id}_followup_{yes|no}` for Yes/No questions

### Example: Multiple Choice with Follow-up

```json
{
  "text": "How did you hear about us?",
  "type": "mc_single",
  "options": [
    {"label": "Social Media", "value": "social"},
    {"label": "Friend/Colleague", "value": "referral"},
    {"label": "Search Engine", "value": "search"},
    {
      "label": "Other",
      "value": "other",
      "followup_text": {
        "enabled": true,
        "label": "Please tell us how you heard about us"
      }
    }
  ],
  "order": 1
}
```

If a respondent selects "Other" and types "Industry conference", the response data will be:

```json
{
  "q_42": "other",
  "q_42_followup_3": "Industry conference"
}
```

## Common JSON Keys

All question types support these common fields:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `text` | string | Yes | The question text shown to respondents |
| `type` | string | Yes | Question type (see above) |
| `order` | integer | Yes | Display order within the group |
| `required` | boolean | No | Whether the question must be answered (default: false) |
| `help_text` | string | No | Additional guidance or instructions |
| `options` | array/object | Varies | Required for mc_single, mc_multi, dropdown, orderable, likert, image |

### Options Field Format

The `options` field can be:

1. **Array of strings** (simple format):
   ```json
   ["Option 1", "Option 2", "Option 3"]
   ```

2. **Array of objects** (rich format with follow-up support):
   ```json
   [
     {"label": "Option 1", "value": "opt1"},
     {"label": "Option 2", "value": "opt2", "followup_text": {"enabled": true, "label": "Please explain"}}
   ]
   ```

3. **Object with scale properties** (for likert numeric scales):
   ```json
   {
     "min": 1,
     "max": 5,
     "min_label": "Strongly Disagree",
     "max_label": "Strongly Agree"
   }
   ```

## Complete Example: Seeding a Survey

Here's a complete example of seeding a survey with multiple question types:

```json
[
  {
    "text": "What is your name?",
    "type": "text",
    "required": true,
    "order": 1
  },
  {
    "text": "What is your age?",
    "type": "number",
    "order": 2
  },
  {
    "text": "Do you have any dietary restrictions?",
    "type": "yesno",
    "options": [
      {
        "label": "Yes",
        "value": "yes",
        "followup_text": {
          "enabled": true,
          "label": "Please describe your dietary restrictions"
        }
      },
      {"label": "No", "value": "no"}
    ],
    "order": 3
  },
  {
    "text": "Which of these apply to you?",
    "type": "mc_multi",
    "options": [
      {"label": "Student", "value": "student"},
      {"label": "Employed", "value": "employed"},
      {"label": "Retired", "value": "retired"},
      {
        "label": "Other",
        "value": "other",
        "followup_text": {
          "enabled": true,
          "label": "Please specify"
        }
      }
    ],
    "order": 4
  },
  {
    "text": "How satisfied are you with our service?",
    "type": "likert",
    "options": {
      "min": 1,
      "max": 5,
      "min_label": "Very Dissatisfied",
      "max_label": "Very Satisfied"
    },
    "order": 5
  }
]
```

## API Endpoint

To seed questions for a survey, use the seed endpoint:

```
POST /api/surveys/{survey_id}/seed/
```

**Authentication:** Requires JWT token and ownership or organisation ADMIN role.

**Request body:** JSON array of question objects (as shown in examples above).

**Response:** Returns the created questions with their assigned IDs.

## Best Practices

1. **Use the rich format** when you need follow-up text inputs or want explicit control over option values
2. **Use the simple format** for straightforward questions without follow-up inputs
3. **Set appropriate `order` values** to control the sequence of questions
4. **Use `required: true`** sparingly - only for essential questions
5. **Provide clear `help_text`** for complex questions
6. **Test follow-up logic** to ensure conditional inputs appear correctly

## See Also

- [Getting Started with the API](getting-started-api.md) - Authentication and basic API usage
- [Surveys](surveys.md) - Creating surveys via the web interface

## Managing Datasets via the API

The DataSet API allows you to create, manage, and share reusable dropdown option lists across your organisation. This is useful for standardized lists like NHS specialty codes, trust names, or custom organisational lists.

### Endpoints

- `GET /api/datasets-v2/` - List available datasets
- `GET /api/datasets-v2/{key}/` - Retrieve specific dataset
- `POST /api/datasets-v2/` - Create new dataset
- `PATCH /api/datasets-v2/{key}/` - Update dataset
- `DELETE /api/datasets-v2/{key}/` - Delete dataset (soft delete)

### Permissions

- **VIEWER**: Can list and retrieve datasets (read-only)
- **CREATOR/ADMIN**: Can create, update, and delete organisation datasets
- **NHS DD datasets**: Read-only for all users (cannot be modified)

### List Datasets

Get all datasets you have access to (global + organisation-specific):

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-domain.com/api/datasets-v2/
```

Response:

```json
[
  {
    "key": "nhs_specialty",
    "name": "NHS Specialty Codes",
    "category": "nhs_dd",
    "is_global": true,
    "is_editable": false,
    "options": ["100", "101", "102", "..."],
    "organisation": null
  },
  {
    "key": "my_custom_list",
    "name": "My Custom List",
    "category": "user_created",
    "is_global": false,
    "is_editable": true,
    "organisation": 1,
    "organisation_name": "My Organisation"
  }
]
```

### Retrieve Dataset

Get details of a specific dataset:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-domain.com/api/datasets-v2/nhs_specialty/
```

### Create Dataset

Create a new dataset for your organisation (requires ADMIN or CREATOR role):

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "hospital_departments",
    "name": "Hospital Departments",
    "description": "List of departments in our hospital",
    "options": [
      "Emergency Department",
      "Cardiology",
      "Orthopedics",
      "Pediatrics"
    ],
    "organisation": 1
  }' \
  https://your-domain.com/api/datasets-v2/
```

**Required fields:**

- `key`: Unique identifier (lowercase, hyphens/underscores only)
- `name`: Display name
- `options`: Array of option strings
- `organisation`: Your organisation ID

**Optional fields:**

- `description`: Additional details about the dataset
- `format_pattern`: Display format (e.g., "CODE - NAME")
- `reference_url`: Source reference URL

Response:

```json
{
  "key": "hospital_departments",
  "name": "Hospital Departments",
  "category": "user_created",
  "source_type": "manual",
  "is_custom": true,
  "is_global": false,
  "organisation": 1,
  "organisation_name": "My Organisation",
  "options": ["Emergency Department", "Cardiology", "Orthopedics", "Pediatrics"],
  "created_by": 5,
  "created_by_username": "admin_user",
  "version": 1,
  "is_active": true,
  "is_editable": true
}
```

### Update Dataset

Update options or metadata (requires ADMIN or CREATOR role in the dataset's organisation):

```bash
curl -X PATCH \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hospital Departments (Updated)",
    "options": [
      "Emergency Department",
      "Cardiology",
      "Orthopedics",
      "Pediatrics",
      "Neurology"
    ]
  }' \
  https://your-domain.com/api/datasets-v2/hospital_departments/
```

**Note:** The version field is automatically incremented on each update.

### Delete Dataset

Soft-delete a dataset (sets `is_active=False`):

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-domain.com/api/datasets-v2/hospital_departments/
```

**Important:** NHS DD datasets cannot be deleted.

### Using Datasets in Questions

Once you've created a dataset, reference it in dropdown questions using the `prefilled_dataset` field:

```json
{
  "text": "Select your department",
  "type": "dropdown",
  "prefilled_dataset": "hospital_departments",
  "order": 1
}
```

The question will automatically use the options from the dataset. If you customize the options in the question, the link to the dataset is preserved but the question uses its local options.

### Access Control

- **Global datasets** (`is_global=true`): Visible to all users and organisations
- **Organisation datasets** (`is_global=false`): Only visible to members of that organisation
- **NHS DD datasets** (`category=nhs_dd`): Read-only, cannot be modified or deleted
- Cross-organisation access is blocked - users cannot see or modify other organisations' datasets

### Dataset Best Practices

1. **Use clear, descriptive keys** like `nhs_specialty_codes` instead of `list1`
2. **Keep options up to date** - update datasets rather than hardcoding options in questions
3. **Create organisation-wide lists** for commonly used options across multiple surveys
4. **Don't modify NHS DD datasets** - create custom versions if you need variations
5. **Use the `description` field** to document the purpose and source of custom lists
6. **Version control** is automatic - the API increments the version number on each update
