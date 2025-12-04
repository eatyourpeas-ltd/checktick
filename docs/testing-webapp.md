---
title: Testing Web Application
category: testing
priority: 1
---

This document provides guidance on testing the CheckTick webapp, including patterns for testing views, forms, question builder functionality, and HTMX interactions.

## Overview

The CheckTick webapp is tested using pytest with Django's test client. Tests verify that web pages render correctly, forms work as expected, permissions are enforced, and interactive features function properly.

## Test Location

Webapp tests are organized by app:

- `/checktick_app/surveys/tests/` - Survey-related webapp tests
  - `test_builder_question_creation.py` - Question creation via builder (23 tests)
  - `test_builder_editing.py` - Question editing functionality
  - `test_permissions.py` - Access control and permissions
  - `test_groups_reorder.py` - Question group reordering
  - `test_anonymous_access.py` - Anonymous user behavior
  - `/test_followup_import.py` - Bulk markdown import with follow-ups and required fields (10 tests)
  - And more...
- `/checktick_app/core/tests/` - Core app tests
- `/tests/` - General integration tests

## Running Webapp Tests

### Parallel Execution (Recommended)

CheckTick uses `pytest-xdist` for parallel test execution, which significantly speeds up test runs:

```bash
# Run all tests in parallel (recommended - ~14x faster)
docker compose exec web pytest -n auto

# Run all tests in parallel with quiet output
docker compose exec web pytest -n auto -q

# Run specific test file in parallel
docker compose exec web pytest checktick_app/surveys/tests/ -n auto
```

The `-n auto` flag automatically detects available CPU cores and distributes tests across them. This reduces full test suite runtime from ~12-15 minutes to under 1 minute.

### Sequential Execution

```bash
# Run all webapp tests for surveys app
docker compose exec web pytest checktick_app/surveys/tests/

# Run specific test file
docker compose exec web pytest checktick_app/surveys/tests/test_builder_question_creation.py

# Run with verbose output
docker compose exec web pytest checktick_app/surveys/tests/test_builder_question_creation.py -v

# Run specific test class or test
docker compose exec web pytest checktick_app/surveys/tests/test_builder_question_creation.py::TestWebappQuestionCreation
docker compose exec web pytest checktick_app/surveys/tests/test_builder_question_creation.py::TestWebappQuestionCreation::test_create_text_question
```

## Test Structure

### Basic Test Class Pattern

```python
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from checktick_app.surveys.models import Survey, SurveyQuestion

@pytest.mark.django_db
class TestMyView:
    """Test suite for my view."""

    def setup_survey(self, client):
        """Create test user and survey, log in user."""
        user = User.objects.create_user(username="testuser", password="testpass")
        survey = Survey.objects.create(owner=user, name="Test", slug="test")
        client.force_login(user)
        return user, survey

    def test_view_renders(self, client):
        """Test that view renders successfully."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:survey_detail", kwargs={"slug": survey.slug})

        response = client.get(url)

        assert response.status_code == 200
        assert "Test" in response.content.decode()
```

## Authentication and Permissions

Webapp tests use Django's authentication system. Tests should:

1. Create test users with appropriate permissions
2. Use `client.force_login(user)` to authenticate
3. Test both authenticated and unauthenticated access

### Example: Authentication Setup

```python
def test_authenticated_access(self, client):
    """Test that authenticated users can access the page."""
    user = User.objects.create_user(username="user", password="pass")
    survey = Survey.objects.create(owner=user, name="Test", slug="test")

    # Log in the user
    client.force_login(user)

    url = reverse("surveys:survey_detail", kwargs={"slug": survey.slug})
    response = client.get(url)

    assert response.status_code == 200

def test_unauthenticated_redirects(self, client):
    """Test that unauthenticated users are redirected."""
    user = User.objects.create_user(username="user", password="pass")
    survey = Survey.objects.create(owner=user, name="Test", slug="test")

    # Don't log in
    url = reverse("surveys:survey_detail", kwargs={"slug": survey.slug})
    response = client.get(url)

    # Should redirect to login
    assert response.status_code == 302
```

**Note:** Permission tests are extensively covered in:

- `checktick_app/surveys/tests/test_permissions.py` - Survey access permissions
- `checktick_app/surveys/tests/test_question_conditions_permissions.py` - Condition editing permissions
- `checktick_app/surveys/tests/test_anonymous_access.py` - Anonymous user access

Refer to these files for examples of testing role-based permissions, ownership checks, and access control.

## Question Creation Tests

The question builder allows creating questions through web forms. Tests verify all question types work correctly.

### Testing Basic Question Types

```python
def test_create_text_question(self, client):
    """Test creating a basic text question."""
    user = User.objects.create_user(username="testuser", password="testpass")
    survey = Survey.objects.create(owner=user, name="Test Survey", slug="test")
    client.force_login(user)

    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "What is your name?",
            "type": "text",
            "text_format": "free",
            "required": "on",
        },
        HTTP_HX_REQUEST="true",  # HTMX request header
    )

    assert response.status_code == 200
    assert b"Question created." in response.content

    # Verify database
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.text == "What is your name?"
    assert question.type == SurveyQuestion.Types.TEXT
    assert question.required is True
    assert question.options == [{"type": "text", "format": "free"}]
```

### Testing Multiple Choice Questions

Multiple choice questions require options:

```python
def test_create_mc_single_question(self, client):
    """Test creating a multiple choice (single) question."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "What is your favorite color?",
            "type": "mc_single",
            "options": "Red\nBlue\nGreen\n",  # Newline-separated
            "required": "on",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.type == SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE

    # Webapp creates options with label/value structure
    assert len(question.options) == 3
    assert question.options[0] == {"label": "Red", "value": "Red"}
    assert question.options[1] == {"label": "Blue", "value": "Blue"}
    assert question.options[2] == {"label": "Green", "value": "Green"}
```

### Testing Follow-up Text Inputs

The webapp uses a different format than the API for follow-up text:

```python
def test_create_mc_single_with_followup_text(self, client):
    """Test creating MC question with follow-up text input."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "How did you hear about us?",
            "type": "mc_single",
            "options": "Friend\nSocial Media\nOther",
            # Follow-up on option index 2 ("Other")
            "option_2_followup": "on",
            "option_2_followup_label": "Please specify",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)

    # First two options have no follow-up
    assert "followup_text" not in question.options[0]
    assert "followup_text" not in question.options[1]

    # Third option has follow-up
    assert "followup_text" in question.options[2]
    assert question.options[2]["followup_text"]["enabled"] is True
    assert question.options[2]["followup_text"]["label"] == "Please specify"
```

### Testing Yes/No Follow-ups

Yes/No questions use a different format for follow-ups:

```python
def test_create_yesno_with_followup_on_yes(self, client):
    """Test creating yes/no question with follow-up on yes."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "Do you have allergies?",
            "type": "yesno",
            "yesno_yes_followup": "on",  # Note the different format
            "yesno_yes_followup_label": "List allergies",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)

    # "Yes" option (index 0) has follow-up
    assert "followup_text" in question.options[0]
    assert question.options[0]["followup_text"]["enabled"] is True
    assert question.options[0]["followup_text"]["label"] == "List allergies"

    # "No" option (index 1) does not
    assert "followup_text" not in question.options[1]
```

### Testing Likert Scale Questions

Likert scales can use numeric ranges or categories:

```python
def test_create_likert_numeric_scale(self, client):
    """Test creating Likert with numeric scale."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "Rate your satisfaction",
            "type": "likert",
            "likert_mode": "number",
            "likert_min": "1",
            "likert_max": "5",
            "likert_left_label": "Not satisfied",
            "likert_right_label": "Very satisfied",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.options[0]["type"] == "number-scale"
    assert question.options[0]["min"] == 1
    assert question.options[0]["max"] == 5

def test_create_likert_categories(self, client):
    """Test creating Likert with categories."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "How do you feel?",
            "type": "likert",
            "likert_mode": "categories",
            "likert_categories": "1\n2\n3\n4\n5",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.options == ["1", "2", "3", "4", "5"]
```

## Testing Question Groups

Questions can be created within groups:

```python
def test_create_question_in_group(self, client):
    """Test creating a question within a specific group."""
    user, survey = self.setup_survey(client)
    group = QuestionGroup.objects.create(name="Demographics", owner=user)
    survey.question_groups.add(group)

    url = reverse(
        "surveys:builder_group_question_create",
        kwargs={"slug": survey.slug, "gid": group.id},
    )

    response = client.post(
        url,
        {
            "text": "What is your age?",
            "type": "text",
            "text_format": "number",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.group_id == group.id
    assert question.text == "What is your age?"
```

## Testing HTMX Interactions

Many views use HTMX for dynamic updates. Include the `HTTP_HX_REQUEST` header:

```python
def test_htmx_response(self, client):
    """Test HTMX partial response."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {"text": "Test", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",  # This header is important!
    )

    assert response.status_code == 200
    html = response.content.decode()

    # Should return partial HTML, not full page
    assert "Question created." in html
    assert "<!DOCTYPE html>" not in html  # Not a full page
```

## Testing Permissions and Access Control

### Owner Can Edit

```python
def test_owner_can_create_question(self, client):
    """Test that survey owner can create questions."""
    user = User.objects.create_user(username="owner", password="pass")
    survey = Survey.objects.create(owner=user, name="Test", slug="test")
    client.force_login(user)

    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    response = client.post(
        url,
        {"text": "Test", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert SurveyQuestion.objects.filter(survey=survey).exists()
```

### Non-Owner Cannot Edit

```python
def test_non_owner_cannot_create_question(self, client):
    """Test that non-owners cannot create questions."""
    owner = User.objects.create_user(username="owner", password="pass")
    other_user = User.objects.create_user(username="other", password="pass")
    survey = Survey.objects.create(owner=owner, name="Test", slug="test")

    client.force_login(other_user)  # Log in as different user

    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    response = client.post(
        url,
        {"text": "Test", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 403  # Forbidden
    assert SurveyQuestion.objects.filter(survey=survey).count() == 0
```

### Unauthenticated Users Redirected

```python
def test_unauthenticated_cannot_create_question(self, client):
    """Test that unauthenticated users are redirected."""
    user = User.objects.create_user(username="owner", password="pass")
    survey = Survey.objects.create(owner=user, name="Test", slug="test")
    # Don't log in

    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    response = client.post(
        url,
        {"text": "Test", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",
    )

    # Should redirect to login or return 403
    assert response.status_code in [302, 403]
    assert SurveyQuestion.objects.filter(survey=survey).count() == 0
```

## Testing Form Validation

### Edge Cases

```python
def test_create_question_with_empty_text(self, client):
    """Test creating a question with empty text defaults to 'Untitled'."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "",  # Empty text
            "type": "text",
            "text_format": "free",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.text == "Untitled"  # Default value

def test_whitespace_trimmed_from_options(self, client):
    """Test that whitespace is trimmed from options."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "Choose",
            "type": "mc_single",
            "options": "  Option 1  \n  Option 2  \n  \n  Option 3  ",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    # Empty lines filtered out, whitespace trimmed
    assert len(question.options) == 3
    assert question.options[0]["label"] == "Option 1"
    assert question.options[1]["label"] == "Option 2"
    assert question.options[2]["label"] == "Option 3"
```

## Testing Bulk Markdown Import

Text Entry allows users to create surveys from text format. Tests verify that the parser correctly handles group and question syntax, follow-up questions, required fields, IDs, and collections.

### Text Entry Test Files

- `/test_followup_import.py` - Comprehensive markdown import tests (10 tests)

### Running Text Entry Tests

```bash
# Run all Text Entry tests
docker compose exec web pytest test_followup_import.py -v

# Run specific test
docker compose exec web pytest test_followup_import.py::test_followup_import_parses_successfully
```

### Test Fixtures

The test suite uses markdown fixtures to simulate real-world survey markdown:

```python
@pytest.fixture
def test_markdown():
    """Sample markdown with follow-up questions across different question types."""
    return """
# Employment Survey {employment}
Questions about employment status

## Employment status* {employment-status}
What is your current employment status?
(mc_single)
- Employed full-time
- Employed part-time
  + Please specify your hours per week
- Self-employed
  + What type of business?
"""
```

### Testing Markdown Parsing

#### Basic Parse Success

```python
def test_followup_import_parses_successfully(test_markdown):
    """Test that markdown with follow-ups parses without errors."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    assert parsed is not None
    assert "groups" in parsed
    assert len(parsed["groups"]) == 1
```

#### Group Structure

```python
def test_followup_import_creates_correct_group_structure(test_markdown):
    """Test that groups are created with correct metadata."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    groups = parsed.get("groups", [])
    assert len(groups) == 1

    employment_group = groups[0]
    assert employment_group["title"] == "Employment Survey"
    assert employment_group["ref"] == "employment"
    assert employment_group["description"] == "Questions about employment status"
```

#### Question with Follow-ups

```python
def test_followup_mc_single_option_structure(test_markdown):
    """Test that mc_single options with follow-ups have correct structure."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    employment_group = parsed["groups"][0]
    employment_q = employment_group["questions"][0]

    # Check question metadata
    assert employment_q["title"] == "Employment status"
    assert employment_q["ref"] == "employment-status"
    assert employment_q["type"] == "mc_single"
    assert employment_q["required"] is True  # Asterisk notation

    # Check options with follow-ups
    options = employment_q["options"]
    assert len(options) == 6

    # Option with follow-up
    part_time = options[1]
    assert part_time["label"] == "Employed part-time"
    assert part_time.get("followup_text") is not None
    assert part_time["followup_text"]["enabled"] is True
    assert part_time["followup_text"]["label"] == "Please specify your hours per week"

    # Option without follow-up
    full_time = options[0]
    assert full_time["label"] == "Employed full-time"
    assert full_time.get("followup_text") is None
```

### Testing Required Fields

```python
def test_required_field_parsing(test_markdown_required):
    """Test that asterisks in question titles are parsed as required flag."""
    parsed = parse_bulk_markdown_with_collections(test_markdown_required)

    questions = parsed["groups"][0]["questions"]

    # Question with asterisk: "## Full name* {contact-name}"
    name_q = questions[0]
    assert name_q["title"] == "Full name"  # Asterisk stripped
    assert name_q["required"] is True

    # Question without asterisk
    phone_q = questions[2]
    assert phone_q["title"] == "Phone number"
    assert phone_q["required"] is False
```

### Testing Required + Follow-up Combined

```python
def test_required_with_followup_combined(test_markdown):
    """Test that required fields work correctly with follow-up questions."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    employment_q = parsed["groups"][0]["questions"][0]

    # Should be both required and have follow-ups
    assert employment_q["required"] is True
    assert employment_q["options"][1]["followup_text"]["enabled"] is True
```

### Testing Asterisk with ID

```python
def test_required_asterisk_with_id(test_markdown):
    """Test asterisk notation before curly brace IDs."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    # Format: "## Employment status* {employment-status}"
    question = parsed["groups"][0]["questions"][0]

    assert question["title"] == "Employment status"  # Asterisk stripped
    assert question["ref"] == "employment-status"  # ID preserved
    assert question["required"] is True  # Flag set
```

### Testing Different Question Types with Follow-ups

The test suite covers follow-ups on multiple question types:

- **mc_single** (single choice) - Follow-up text inputs on specific options
- **mc_multi** (multiple choice) - Follow-ups on selected options
- **dropdown** - Follow-ups on dropdown selections
- **yesno** - Follow-ups on yes/no answers

```python
def test_followup_mc_multi_option_structure(test_markdown):
    """Test mc_multi options with follow-ups."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    skills_q = parsed["groups"][0]["questions"][1]
    assert skills_q["type"] == "mc_multi"

    python_option = skills_q["options"][0]
    assert python_option["label"] == "Python"
    assert python_option["followup_text"]["label"] == "Years of experience?"
```

### Testing Data Structure API Compatibility

```python
def test_followup_data_structure_matches_api_format(test_markdown):
    """Test that parsed data matches expected API format."""
    parsed = parse_bulk_markdown_with_collections(test_markdown)

    question = parsed["groups"][0]["questions"][0]
    option_with_followup = question["options"][1]

    # Should match webapp format: {enabled: bool, label: str}
    assert "followup_text" in option_with_followup
    assert isinstance(option_with_followup["followup_text"], dict)
    assert "enabled" in option_with_followup["followup_text"]
    assert "label" in option_with_followup["followup_text"]
    assert option_with_followup["followup_text"]["enabled"] is True
```

### Key Test Patterns for Text Entry

1. **Parse Validation**: Verify markdown parses without errors
2. **Structure Verification**: Check groups, questions, and options are created correctly
3. **Metadata Preservation**: Ensure IDs, titles, descriptions are extracted properly
4. **Feature Flags**: Test required fields (asterisk), follow-ups (indented +), types
5. **Format Compatibility**: Ensure parsed data matches expected structure for database creation
6. **Edge Cases**: Test asterisk before/after IDs, multiple follow-ups, missing types

### Reference Implementation

For complete test examples, see `/test_followup_import.py` which includes:

- 2 comprehensive markdown fixtures
- 10 tests covering parsing, structure, follow-ups, and required fields
- Tests for all major question types with follow-up support
- Validation of data format compatibility with the webapp

## Testing Question Ordering

```python
def test_new_questions_get_incremental_order(self, client):
    """Test that new questions are assigned incremental order values."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    for i in range(3):
        client.post(
            url,
            {
                "text": f"Question {i + 1}",
                "type": "text",
                "text_format": "free",
            },
            HTTP_HX_REQUEST="true",
        )

    questions = SurveyQuestion.objects.filter(survey=survey).order_by("order")
    assert questions.count() == 3
    assert questions[0].order == 1
    assert questions[1].order == 2
    assert questions[2].order == 3
```

## Testing Response Content

### Success Messages

```python
def test_create_returns_success_message(self, client):
    """Test that create returns success message in response."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {"text": "Test Question", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "Question created." in html
    assert "Test Question" in html
```

### Script Payloads for JavaScript

```python
def test_create_includes_builder_payload(self, client):
    """Test that response includes data payload for JavaScript."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {"text": "Test", "type": "text", "text_format": "free"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    html = response.content.decode()

    # Should have a script tag with question data
    script_id = f"question-data-{question.id}"
    assert script_id in html
```

## Best Practices

### 1. Use URL Reverse Lookups

Always use `reverse()` instead of hardcoding URLs:

```python
# Good
url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

# Avoid
url = f"/surveys/{survey.slug}/builder/question/create/"
```

### 2. Test Database Changes

Don't just check HTTP responses - verify database state:

```python
response = client.post(url, data)
assert response.status_code == 200

# Also check database
question = SurveyQuestion.objects.get(survey=survey)
assert question.text == "Expected"
```

### 3. Test Both GET and POST

```python
def test_form_displays(self, client):
    """Test that form page displays."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:some_form", kwargs={"slug": survey.slug})

    response = client.get(url)
    assert response.status_code == 200
    assert "form" in response.context

def test_form_submission(self, client):
    """Test form submission."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:some_form", kwargs={"slug": survey.slug})

    response = client.post(url, {"field": "value"})
    assert response.status_code == 302  # Redirect after success
```

### 4. Use `force_login()` for Authenticated Tests

```python
# Good - faster, more direct
client.force_login(user)

# Avoid - slower, indirect
client.login(username="user", password="pass")
```

### 5. Clean Test Names

```python
# Good
def test_owner_can_edit_question(self, client):

# Avoid
def test_edit(self, client):
```

## Common Patterns

### Testing All Question Types

```python
@pytest.mark.parametrize("qtype,extra_data", [
    ("text", {"text_format": "free"}),
    ("mc_single", {"options": "A\nB\nC"}),
    ("mc_multi", {"options": "A\nB\nC"}),
    ("dropdown", {"options": "A\nB\nC"}),
    ("yesno", {}),
    ("orderable", {"options": "A\nB\nC"}),
])
def test_create_all_question_types(self, client, qtype, extra_data):
    """Test creating all valid question types."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    data = {"text": f"Test {qtype}", "type": qtype}
    data.update(extra_data)

    response = client.post(url, data, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
```

### Testing Context Data

```python
def test_view_context(self, client):
    """Test that view provides correct context."""
    user, survey = self.setup_survey(client)
    url = reverse("surveys:survey_detail", kwargs={"slug": survey.slug})

    response = client.get(url)

    assert response.status_code == 200
    assert "survey" in response.context
    assert response.context["survey"] == survey
    assert "questions" in response.context
```

## Differences from API Testing

| Aspect | API Tests | Webapp Tests |
|--------|-----------|--------------|
| Authentication | JWT tokens in headers | `client.force_login()` |
| Request format | JSON with `content_type` | Form data (dict) |
| Headers | `HTTP_AUTHORIZATION` | `HTTP_HX_REQUEST` for HTMX |
| Response | JSON data | HTML content |
| Options format | Simple arrays/objects | `{label, value}` structure |
| Follow-up format | `has_followup`, `followup_label` | `followup_text: {enabled, label}` |
| Follow-up keys | In options array | `option_N_followup` form fields |

## Troubleshooting

### Test Fails with 302 Redirect

- User not logged in - use `client.force_login(user)`
- Check if view requires authentication

### Test Fails with 403 Forbidden

- User lacks permissions - check ownership/roles
- See permission test files for examples

### HTMX Response Differs

- Ensure `HTTP_HX_REQUEST="true"` header is included
- HTMX responses return partials, not full pages

### Options Format Different Than Expected

- Webapp creates `{label, value}` structure
- API uses simpler formats
- Follow-up text structure differs between webapp and API

## Reference Tests

For comprehensive examples, see:

- `checktick_app/surveys/tests/test_builder_question_creation.py` - 23 tests covering question creation
- `checktick_app/surveys/tests/test_builder_editing.py` - Question editing and copying
- `checktick_app/surveys/tests/test_permissions.py` - Permission patterns
- `checktick_app/surveys/tests/test_groups_reorder.py` - HTMX interactions and reordering
- `checktick_app/surveys/tests/test_anonymous_access.py` - Anonymous user handling
- `/test_followup_import.py` - Bulk markdown import with follow-ups and required fields (10 tests)
