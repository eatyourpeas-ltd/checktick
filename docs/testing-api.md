---
title: Testing API
category: testing
priority: 2
---

This document provides guidance on testing the CheckTick API, including patterns, best practices, and examples from the existing test suite.

## Overview

The CheckTick API is tested using pytest with Django's test client. Tests verify that API endpoints work correctly, handle edge cases, validate inputs, and return appropriate responses.

## Test Location

API tests are located in:
- `/tests/test_api_*.py` - General API tests
- `/checktick_app/api/tests/` - App-specific API tests

## Running API Tests

### Parallel Execution (Recommended)

CheckTick uses `pytest-xdist` for parallel test execution, which significantly speeds up test runs:

```bash
# Run all tests in parallel (recommended - ~14x faster)
docker compose exec web pytest -n auto

# Run all API tests in parallel
docker compose exec web pytest tests/test_api_*.py -n auto
```

The `-n auto` flag automatically detects available CPU cores and distributes tests across them. Each worker gets its own database, ensuring test isolation.

### Sequential Execution

```bash
# Run all API tests
docker compose exec web pytest tests/test_api_*.py

# Run specific test file
docker compose exec web pytest tests/test_api_questions_and_groups.py

# Run with verbose output
docker compose exec web pytest tests/test_api_questions_and_groups.py -v

# Run specific test
docker compose exec web pytest tests/test_api_questions_and_groups.py::TestAPIQuestionsAndGroups::test_seed_text_question
```

## Test Structure

### Basic Test Class Pattern

```python
import pytest
import json
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestMyAPIEndpoint:
    """Test suite for my API endpoint."""

    @pytest.fixture
    def setup_test_data(self, client):
        """Create test data needed for tests."""
        user = User.objects.create_user(username="testuser", password="testpass")
        # ... create other test data

        # Get JWT token
        resp = client.post(
            "/api/token",
            data=json.dumps({"username": "testuser", "password": "testpass"}),
            content_type="application/json",
        )
        token = resp.json()["access"]
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        return user, headers

    def test_endpoint_success(self, client, setup_test_data):
        """Test successful API call."""
        user, headers = setup_test_data

        response = client.post(
            "/api/my-endpoint/",
            data=json.dumps({"key": "value"}),
            content_type="application/json",
            **headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "expected_value"
```

## Authentication and Permissions

CheckTick uses JWT authentication for API requests. Tests should:

1. Create a test user
2. Obtain a JWT token via `/api/token`
3. Include the token in request headers

### Example: JWT Authentication Setup

```python
# Get token
resp = client.post(
    "/api/token",
    data=json.dumps({"username": "testuser", "password": "testpass"}),
    content_type="application/json",
)
token = resp.json()["access"]
headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

# Use in requests
response = client.post("/api/endpoint/", **headers)
```

**Note:** Authentication and permission tests are covered in:
- `tests/test_api_permissions.py`
- `tests/test_api_access_controls.py`
- `tests/test_jwt_auth.py`

Refer to these files for examples of testing authentication flows, permission levels, and access control.

## Question and Question Group API Tests

The `/tests/test_api_questions_and_groups.py` file demonstrates comprehensive API testing patterns.

### Testing Question Creation (Seeding)

The seed endpoint (`POST /api/surveys/{id}/seed/`) accepts JSON payloads to create questions.

#### Example: Basic Question Types

```python
def test_seed_text_question(self, client, setup_basic_survey):
    """Test seeding a basic text question."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [
        {
            "type": "text",
            "text": "What is your name?",
            "required": True,
            "options": [{"type": "text", "format": "free"}]
        }
    ]

    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        **headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "questions" in data
    assert len(data["questions"]) == 1

    question = SurveyQuestion.objects.get(survey=survey)
    assert question.text == "What is your name?"
    assert question.type == SurveyQuestion.Types.TEXT
    assert question.required is True
```

#### Valid Question Types

The API validates question types against these allowed values:
- `text` - Text input
- `mc_single` - Multiple choice (single selection)
- `mc_multi` - Multiple choice (multiple selections)
- `dropdown` - Dropdown selection
- `yesno` - Yes/No question
- `likert` - Likert scale
- `orderable` - Orderable list
- `image` - Image choice
- `template_patient` - Patient template
- `template_professional` - Professional template

### Testing Follow-up Text Feature

Questions can have follow-up text inputs on specific options:

```python
def test_seed_mc_single_with_followup(self, client, setup_basic_survey):
    """Test MC question with follow-up text on one option."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [
        {
            "type": "mc_single",
            "text": "How did you hear about us?",
            "options": [
                "Friend",
                "Social Media",
                {"text": "Other", "has_followup": True, "followup_label": "Please specify"}
            ]
        }
    ]

    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    # Last option should have followup
    assert question.options[2]["has_followup"] is True
    assert question.options[2]["followup_label"] == "Please specify"
```

### Testing API Validation

Test that the API properly validates inputs and returns helpful error messages:

```python
def test_validation_invalid_question_type(self, client, setup_basic_survey):
    """Test that invalid question types return 400 error."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [{"type": "invalid_type", "text": "Test"}]

    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data
    assert "valid_types" in data
    # Should list all valid types
    assert "text" in data["valid_types"]
    assert "mc_single" in data["valid_types"]
```

### Testing Warning vs Error Behavior

The API distinguishes between critical errors (which prevent creation) and warnings (which allow creation but notify the user):

```python
def test_validation_warning_missing_text(self, client, setup_basic_survey):
    """Test that missing text returns warning but succeeds."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [{"type": "text"}]  # Missing text field

    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    # Should succeed with warning
    assert response.status_code == 200
    data = response.json()
    assert "warnings" in data

    # Question created with default text
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.text == "Untitled"
```

### Testing Question Groups

```python
def test_seed_with_multiple_question_groups(self, client, setup_basic_survey):
    """Test seeding questions with group assignments."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [
        {
            "type": "text",
            "text": "Name",
            "group": "Demographics"
        },
        {
            "type": "text",
            "text": "Age",
            "group": "Demographics"
        },
        {
            "type": "text",
            "text": "Feedback",
            "group": "Comments"
        }
    ]

    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    assert response.status_code == 200

    # Should create 2 groups
    groups = QuestionGroup.objects.filter(owner=user)
    assert groups.count() == 2

    # Questions assigned to correct groups
    demo_group = groups.get(name="Demographics")
    assert SurveyQuestion.objects.filter(group=demo_group).count() == 2
```

## Testing Response Formats

Always verify:
1. HTTP status code
2. Response structure
3. Data types
4. Required fields

```python
def test_response_format(self, client, setup_basic_survey):
    """Verify API response structure."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [{"type": "text", "text": "Test"}]
    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert isinstance(data, dict)
    assert "questions" in data
    assert isinstance(data["questions"], list)

    # Check question data
    question_data = data["questions"][0]
    assert "id" in question_data
    assert "text" in question_data
    assert "type" in question_data
    assert isinstance(question_data["id"], int)
```

## Edge Cases and Error Handling

Test boundary conditions and error scenarios:

```python
def test_seed_empty_payload(self, client, setup_basic_survey):
    """Test seeding with empty payload."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    response = client.post(url, data=json.dumps([]),
                          content_type="application/json", **headers)

    # Should handle gracefully
    assert response.status_code in [200, 400]
    assert SurveyQuestion.objects.filter(survey=survey).count() == 0

def test_seed_malformed_json(self, client, setup_basic_survey):
    """Test handling of malformed JSON."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    response = client.post(url, data="{invalid json}",
                          content_type="application/json", **headers)

    assert response.status_code == 400
```

## Best Practices

### 1. Use Fixtures for Setup

Create reusable fixtures for common setup:

```python
@pytest.fixture
def setup_basic_survey(self, client):
    """Create user, survey, and auth headers."""
    user = User.objects.create_user(username="testuser", password="testpass")
    survey = Survey.objects.create(owner=user, name="Test", slug="test")

    resp = client.post("/api/token",
                      data=json.dumps({"username": "testuser", "password": "testpass"}),
                      content_type="application/json")
    token = resp.json()["access"]
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    return user, survey, headers
```

### 2. Test One Thing Per Test

Keep tests focused:

```python
# Good - tests one specific behavior
def test_required_question_validation(self, client):
    """Test that required field is properly validated."""
    # ... test only required field validation

# Avoid - tests multiple behaviors
def test_everything(self, client):
    """Test question creation and editing and deletion."""
    # ... too much in one test
```

### 3. Use Descriptive Test Names

```python
# Good
def test_seed_mc_single_with_followup_text(self, client):

# Avoid
def test_mc(self, client):
```

### 4. Test Both Success and Failure Paths

```python
def test_create_question_success(self, client):
    """Test successful question creation."""
    # ... test happy path

def test_create_question_invalid_type(self, client):
    """Test question creation with invalid type fails."""
    # ... test error case
```

### 5. Assert Database State

Don't just check the API response - verify the database:

```python
response = client.post(url, data=json.dumps(payload), **headers)
assert response.status_code == 200

# Also verify database
question = SurveyQuestion.objects.get(survey=survey)
assert question.text == "Expected text"
assert question.type == SurveyQuestion.Types.TEXT
```

### 6. Clean Test Data

Use `@pytest.mark.django_db` to ensure database cleanup:

```python
@pytest.mark.django_db
class TestMyAPI:
    """Tests with automatic database cleanup."""

    def test_something(self, client):
        # Database changes rolled back after test
        pass
```

## Common Patterns

### Testing All Valid Values

```python
def test_validation_all_valid_types_accepted(self, client, setup_basic_survey):
    """Test that all valid question types are accepted."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    valid_types = ["text", "mc_single", "mc_multi", "dropdown",
                   "yesno", "likert", "orderable", "image",
                   "template_patient", "template_professional"]

    for qtype in valid_types:
        payload = [{"type": qtype, "text": f"Test {qtype}"}]
        response = client.post(url, data=json.dumps(payload),
                              content_type="application/json", **headers)
        assert response.status_code == 200, f"Failed for type: {qtype}"

        # Clean up for next iteration
        SurveyQuestion.objects.filter(survey=survey).delete()
```

### Testing Multiple Items

```python
def test_seed_multiple_questions(self, client, setup_basic_survey):
    """Test seeding multiple questions in one request."""
    user, survey, headers = setup_basic_survey
    url = f"/api/surveys/{survey.id}/seed/"

    payload = [
        {"type": "text", "text": "Question 1"},
        {"type": "mc_single", "text": "Question 2", "options": ["A", "B"]},
        {"type": "yesno", "text": "Question 3"}
    ]

    response = client.post(url, data=json.dumps(payload),
                          content_type="application/json", **headers)

    assert response.status_code == 200
    assert SurveyQuestion.objects.filter(survey=survey).count() == 3
```

## Troubleshooting

### Test Fails with 401 Unauthorized

- Check JWT token is correctly obtained and included in headers
- Verify user exists and credentials are correct
- Ensure token hasn't expired (use fresh token for each test)

### Test Fails with 403 Forbidden

- Verify user has required permissions
- Check survey ownership
- See permission tests for examples

### JSON Decode Errors

- Ensure `content_type="application/json"` is set
- Use `json.dumps()` for payload
- Check response has JSON content before calling `.json()`

## Reference Tests

For comprehensive examples, see:
- `tests/test_api_questions_and_groups.py` - 35 tests covering questions/groups API
- `tests/test_api_permissions.py` - Permission and access control patterns
- `tests/test_user_api.py` - User management API patterns
- `/checktick_app/api/tests/test_publish_and_metrics_api.py` - Publishing and metrics patterns
