"""
Security tests for LLM survey generator feature.

Tests critical security requirements:
1. Only authenticated users with edit permission can access LLM features
2. LLM cannot create/modify/delete surveys (read-only operations)
3. LLM sessions are isolated per user
4. AJAX endpoints properly validate permissions
5. Markdown sanitization prevents injection
6. Access control for org admins, creators, and individual account holders only
"""

from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
import pytest

from checktick_app.surveys.llm_client import ConversationalSurveyLLM
from checktick_app.surveys.models import (
    LLMConversationSession,
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
)

TEST_PASSWORD = "secure-test-password"


@pytest.fixture
def users(db):
    """Create test users with different roles."""
    org_owner = User.objects.create_user(username="org_owner", password=TEST_PASSWORD)
    org_admin = User.objects.create_user(username="org_admin", password=TEST_PASSWORD)
    org_member = User.objects.create_user(username="org_member", password=TEST_PASSWORD)
    survey_creator = User.objects.create_user(
        username="creator", password=TEST_PASSWORD
    )
    individual_user = User.objects.create_user(
        username="individual", password=TEST_PASSWORD
    )
    outsider = User.objects.create_user(username="outsider", password=TEST_PASSWORD)

    return {
        "org_owner": org_owner,
        "org_admin": org_admin,
        "org_member": org_member,
        "survey_creator": survey_creator,
        "individual_user": individual_user,
        "outsider": outsider,
    }


@pytest.fixture
def org(db, users):
    """Create organization with memberships."""
    org = Organization.objects.create(
        name="Test Healthcare Org", owner=users["org_owner"]
    )

    # Add admin
    OrganizationMembership.objects.create(
        organization=org,
        user=users["org_admin"],
        role=OrganizationMembership.Role.ADMIN,
    )

    # Add regular member (should NOT have LLM access)
    OrganizationMembership.objects.create(
        organization=org,
        user=users["org_member"],
        role=OrganizationMembership.Role.VIEWER,
    )

    return org


@pytest.fixture
def org_survey(db, users, org):
    """Create organization survey."""
    return Survey.objects.create(
        owner=users["survey_creator"],
        organization=org,
        name="Org Patient Satisfaction Survey",
        slug="org-patient-survey",
    )


@pytest.fixture
def individual_survey(db, users):
    """Create individual user survey (no organization)."""
    return Survey.objects.create(
        owner=users["individual_user"],
        organization=None,
        name="Individual Research Survey",
        slug="individual-survey",
    )


# =============================================================================
# Test Authentication & Authorization
# =============================================================================


class TestLLMAccessControl:
    """Test who can access LLM features."""

    @pytest.mark.django_db
    def test_anonymous_cannot_access_bulk_upload(self, client, org_survey):
        """Anonymous users cannot access bulk upload page."""
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})
        resp = client.get(url)
        assert resp.status_code in (302, 401, 403)  # Redirect to login or forbidden

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_anonymous_cannot_create_llm_session(self, client, org_survey):
        """Anonymous users cannot create LLM sessions."""
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})
        resp = client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        assert resp.status_code in (302, 401, 403)

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_outsider_cannot_access_org_survey(self, client, users, org_survey):
        """Users outside organization cannot access LLM for org survey."""
        client.force_login(users["outsider"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Should be blocked by require_can_edit
        resp = client.get(url)
        assert resp.status_code in (403, 404)

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_org_member_cannot_use_llm(self, client, users, org_survey):
        """Regular org members (non-admins, non-creators) cannot use LLM."""
        client.force_login(users["org_member"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Member doesn't have edit permission
        resp = client.get(url)
        assert resp.status_code in (403, 404)

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_org_admin_can_access_llm(self, client, users, org_survey):
        """Org admins can access LLM features."""
        client.force_login(users["org_admin"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        resp = client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_survey_creator_can_access_llm(self, client, users, org_survey):
        """Survey creators can access LLM features."""
        client.force_login(users["survey_creator"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        resp = client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_individual_user_can_access_own_survey_llm(
        self, client, users, individual_survey
    ):
        """Individual account holders can use LLM on their own surveys."""
        client.force_login(users["individual_user"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": individual_survey.slug})

        resp = client.get(url)
        assert resp.status_code == 200


# =============================================================================
# Test LLM Cannot Modify Surveys
# =============================================================================


class TestLLMReadOnlyOperations:
    """Test that LLM operations are read-only and cannot modify surveys."""

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_llm_session_creation_does_not_modify_survey(
        self, client, users, org_survey
    ):
        """Creating LLM session does not modify survey structure."""
        client.force_login(users["survey_creator"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Record initial state
        initial_question_count = org_survey.questions.count()
        initial_group_count = org_survey.question_groups.count()

        # Create LLM session
        resp = client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["status"] == "success"

        # Verify survey unchanged
        org_survey.refresh_from_db()
        assert org_survey.questions.count() == initial_question_count
        assert org_survey.question_groups.count() == initial_group_count

    @pytest.mark.django_db
    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_llm_send_message_does_not_modify_survey(
        self, client, users, org_survey, monkeypatch
    ):
        """Sending LLM message does not create/modify survey questions."""
        client.force_login(users["survey_creator"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Create session first
        client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        # Mock LLM response
        def mock_chat(conversation_history, temperature=None):
            return """I will help you create a patient survey.

```markdown
# Patient Demographics {demo}

## Age {age}*
(text number)

## Gender {gender}
(mc_single)
- Male
- Female
- Other
```"""

        monkeypatch.setattr(
            ConversationalSurveyLLM,
            "chat",
            lambda self, history, temp=None: mock_chat(history, temp),
        )

        # Record initial state
        initial_question_count = org_survey.questions.count()
        initial_group_count = org_survey.question_groups.count()

        # Send message
        resp = client.post(
            url,
            data={
                "action": "send_message",
                "message": "Create a patient demographics survey",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["status"] == "success"
        assert "markdown" in data
        assert data["markdown_valid"] is True

        # Verify survey still unchanged - LLM only generates markdown, does not create questions
        org_survey.refresh_from_db()
        assert org_survey.questions.count() == initial_question_count
        assert org_survey.question_groups.count() == initial_group_count

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_llm_cannot_delete_existing_questions(self, client, users, org_survey):
        """LLM operations cannot delete existing survey questions."""
        client.force_login(users["survey_creator"])

        # Create existing question group
        group = QuestionGroup.objects.create(
            name="Existing Group",
            description="Should not be deleted by LLM",
            owner=users["survey_creator"],
        )
        org_survey.question_groups.add(group)

        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Create LLM session and send message
        client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        # Verify existing group still exists
        assert QuestionGroup.objects.filter(id=group.id).exists()
        assert org_survey.question_groups.filter(id=group.id).exists()


# =============================================================================
# Test Session Isolation
# =============================================================================


class TestLLMSessionIsolation:
    """Test that LLM sessions are properly isolated per user."""

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_sessions_isolated_by_user(self, client, users, org_survey):
        """Each user gets their own isolated LLM session."""
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Creator creates session
        client.force_login(users["survey_creator"])
        resp1 = client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        data1 = json.loads(resp1.content)
        session_id_1 = data1["session_id"]

        # Admin creates session
        client.force_login(users["org_admin"])
        resp2 = client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        data2 = json.loads(resp2.content)
        session_id_2 = data2["session_id"]

        # Sessions should be different
        assert session_id_1 != session_id_2

        # Each user session should belong to them
        session1 = LLMConversationSession.objects.get(id=session_id_1)
        session2 = LLMConversationSession.objects.get(id=session_id_2)

        assert session1.user == users["survey_creator"]
        assert session2.user == users["org_admin"]

    @pytest.mark.django_db
    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_user_cannot_access_another_users_session(
        self, client, users, org_survey, monkeypatch
    ):
        """User cannot send messages to another user session."""
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Mock LLM
        monkeypatch.setattr(
            ConversationalSurveyLLM,
            "chat",
            lambda self, history, temp=None: "Test response",
        )

        # Creator creates session and sends message
        client.force_login(users["survey_creator"])
        client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        resp = client.post(
            url,
            data={"action": "send_message", "message": "Creator message"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert resp.status_code == 200

        # Admin logs in and tries to send message (should get their own session requirement)
        client.force_login(users["org_admin"])
        resp = client.post(
            url,
            data={
                "action": "send_message",
                "message": "Admin trying to use creator session",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should fail because admin does not have active session
        data = json.loads(resp.content)
        assert data["status"] == "error"
        assert "No active session" in data["message"]


# =============================================================================
# Test Markdown Sanitization
# =============================================================================


class TestMarkdownSanitization:
    """Test that LLM-generated markdown is properly sanitized."""

    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_sanitize_removes_urls(self):
        """Sanitization removes URLs from markdown."""
        llm = ConversationalSurveyLLM()

        markdown = """# Survey {s1}
Visit https://malicious.com for more info
## Question {q1}
Check out http://phishing.site"""

        sanitized = llm.sanitize_markdown(markdown)
        assert "https://" not in sanitized
        assert "http://" not in sanitized
        assert "malicious.com" not in sanitized

    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_sanitize_removes_html_tags(self):
        """Sanitization removes HTML/script tags."""
        llm = ConversationalSurveyLLM()

        markdown = """# Survey {s1}
<script>alert('xss')</script>
## Question {q1}
<img src=x onerror=alert(1)>"""

        sanitized = llm.sanitize_markdown(markdown)
        assert "<script>" not in sanitized
        assert "<img" not in sanitized
        assert "onerror" not in sanitized

    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_sanitize_removes_code_execution_patterns(self):
        """Sanitization removes potential code execution patterns."""
        llm = ConversationalSurveyLLM()

        markdown = """# Survey {s1}
```python
import os
os.system('rm -rf /')
```
$(dangerous)
window.location='evil.com'
"""

        sanitized = llm.sanitize_markdown(markdown)
        assert "import" not in sanitized
        assert "$(" not in sanitized
        assert "window." not in sanitized

    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_extract_markdown_from_code_block(self):
        """LLM client correctly extracts markdown from code blocks."""
        llm = ConversationalSurveyLLM()

        response = """Here's your survey:

```markdown
# Patient Info {info}
## Age {age}
(text number)
```

Let me know if you need changes!"""

        markdown = llm.extract_markdown(response)
        assert markdown is not None
        assert "# Patient Info" in markdown
        assert "Here's your survey" not in markdown
        assert "Let me know" not in markdown

    @override_settings(
        LLM_ENABLED=True,
        LLM_URL="http://test",
        LLM_API_KEY="test",
        LLM_AUTH_TYPE="bearer",
    )
    def test_extract_markdown_handles_pure_markdown(self):
        """LLM client handles responses that are pure markdown."""
        llm = ConversationalSurveyLLM()

        response = """# Patient Demographics {demo}
## Age {age}*
(text number)"""

        markdown = llm.extract_markdown(response)
        assert markdown is not None
        assert "# Patient Demographics" in markdown


# =============================================================================
# Test LLM Feature Toggle
# =============================================================================


class TestLLMFeatureToggle:
    """Test that LLM feature respects LLM_ENABLED setting."""

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=False)
    def test_llm_disabled_blocks_session_creation(self, client, users, org_survey):
        """When LLM_ENABLED=False, session creation is blocked."""
        client.force_login(users["org_admin"])
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        resp = client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data["status"] == "error"
        assert "not available" in data["message"].lower()

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=False)
    def test_llm_disabled_blocks_send_message(self, client, users, org_survey):
        """When LLM_ENABLED=False, sending messages is blocked."""
        client.login(username="creator", password=TEST_PASSWORD)
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        resp = client.post(
            url,
            data={"action": "send_message", "message": "test"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data["status"] == "error"

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=False)
    def test_bulk_upload_still_works_when_llm_disabled(self, client, users, org_survey):
        """Regular bulk upload functionality works even when LLM is disabled."""
        client.login(username="creator", password=TEST_PASSWORD)
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Regular bulk upload with markdown should still work
        markdown = """# Test Group {test}
## Test Question {q1}
(text)"""

        resp = client.post(url, data={"markdown": markdown})

        # Should redirect to dashboard on success
        assert resp.status_code == 302
        assert org_survey.questions.count() > 0


# =============================================================================
# Test AJAX Endpoint Security
# =============================================================================


class TestAJAXEndpointSecurity:
    """Test AJAX endpoints require proper headers and authentication."""

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_ajax_endpoints_require_xhr_header(self, client, users, org_survey):
        """LLM AJAX endpoints require X-Requested-With header."""
        client.login(username="creator", password=TEST_PASSWORD)
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Try without AJAX header (should be treated as regular POST)
        resp = client.post(url, data={"action": "new_session"})

        # Without markdown field, should fail as bulk upload
        assert resp.status_code == 200  # Renders form with error
        assert b"error" in resp.content or "error" in str(resp.content).lower()

    @pytest.mark.django_db
    @override_settings(LLM_ENABLED=True)
    def test_empty_message_rejected(self, client, users, org_survey):
        """Empty messages are rejected."""
        client.login(username="creator", password=TEST_PASSWORD)
        url = reverse("surveys:bulk_upload", kwargs={"slug": org_survey.slug})

        # Create session
        client.post(
            url, data={"action": "new_session"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        # Try to send empty message
        resp = client.post(
            url,
            data={"action": "send_message", "message": "   "},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data["status"] == "error"
        assert "empty" in data["message"].lower()
