"""
Tests for Question Group Template API endpoints.

Tests cover:
- Listing templates with permission filtering
- Retrieving template details
- Publishing question groups via API
- Permission checks for all operations
"""

from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

User = get_user_model()
TEST_PASSWORD = "test-pass-123"


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def user1(django_user_model):
    """Create first test user."""
    return django_user_model.objects.create_user(
        username="user1@example.com",
        email="user1@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def user2(django_user_model):
    """Create second test user."""
    return django_user_model.objects.create_user(
        username="user2@example.com",
        email="user2@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def admin_user(django_user_model):
    """Create admin/superuser for global publications."""
    return django_user_model.objects.create_user(
        username="admin@example.com",
        email="admin@example.com",
        password=TEST_PASSWORD,
        is_superuser=True,
        is_staff=True,
    )


@pytest.fixture
def org1(user1):
    """Create organization 1."""
    org = Organization.objects.create(name="Organization 1", owner=user1)
    OrganizationMembership.objects.create(
        user=user1, organization=org, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.fixture
def org2(user2):
    """Create organization 2."""
    org = Organization.objects.create(name="Organization 2", owner=user2)
    OrganizationMembership.objects.create(
        user=user2, organization=org, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.fixture
def global_template(user1):
    """Create a global published template."""
    return PublishedQuestionGroup.objects.create(
        publisher=user1,
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        name="Global PHQ-9",
        description="Patient Health Questionnaire",
        markdown="# PHQ-9\n\n## Question 1\n(text)",
        tags=["depression", "screening"],
        language="en",
        status=PublishedQuestionGroup.Status.ACTIVE,
    )


@pytest.fixture
def org1_template(user1, org1):
    """Create an organization-level template for org1."""
    return PublishedQuestionGroup.objects.create(
        publisher=user1,
        organization=org1,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
        name="Org1 Template",
        description="Organization specific template",
        markdown="# Org Template\n\n## Question 1\n(text)",
        tags=["custom"],
        language="en",
        status=PublishedQuestionGroup.Status.ACTIVE,
    )


@pytest.fixture
def org2_template(user2, org2):
    """Create an organization-level template for org2."""
    return PublishedQuestionGroup.objects.create(
        publisher=user2,
        organization=org2,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
        name="Org2 Template",
        description="Another organization template",
        markdown="# Org2 Template\n\n## Question 1\n(text)",
        tags=["custom"],
        language="en",
        status=PublishedQuestionGroup.Status.ACTIVE,
    )


@pytest.mark.django_db
class TestTemplateListAPI:
    """Test listing templates via API."""

    def test_unauthenticated_access_denied(self, api_client, global_template):
        """Unauthenticated users cannot access the API."""
        response = api_client.get("/api/question-group-templates/")
        assert response.status_code == 401

    def test_user_sees_global_templates(self, api_client, user1, global_template):
        """Authenticated users can see global templates."""
        api_client.force_authenticate(user=user1)
        response = api_client.get("/api/question-group-templates/")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Global PHQ-9"

    def test_user_sees_own_org_templates(self, api_client, user1, org1, org1_template):
        """Users see templates from their own organization."""
        api_client.force_authenticate(user=user1)
        response = api_client.get("/api/question-group-templates/")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Org1 Template"

    def test_user_does_not_see_other_org_templates(
        self, api_client, user1, org1, org2_template
    ):
        """Users cannot see templates from other organizations."""
        api_client.force_authenticate(user=user1)
        response = api_client.get("/api/question-group-templates/")

        assert response.status_code == 200
        assert len(response.data) == 0

    def test_user_sees_global_and_own_org_templates(
        self, api_client, user1, org1, global_template, org1_template
    ):
        """Users see both global and their org templates."""
        api_client.force_authenticate(user=user1)
        response = api_client.get("/api/question-group-templates/")

        assert response.status_code == 200
        assert len(response.data) == 2
        names = {t["name"] for t in response.data}
        assert names == {"Global PHQ-9", "Org1 Template"}

    def test_filter_by_publication_level(
        self, api_client, user1, org1, global_template, org1_template
    ):
        """Can filter templates by publication level."""
        api_client.force_authenticate(user=user1)

        # Filter for global only
        response = api_client.get(
            "/api/question-group-templates/?publication_level=global"
        )
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Global PHQ-9"

    def test_filter_by_language(self, api_client, user1, global_template):
        """Can filter templates by language."""
        # Create a Welsh template
        PublishedQuestionGroup.objects.create(
            publisher=user1,
            publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
            name="Welsh Template",
            description="Welsh version",
            markdown="# Welsh\n\n## Question\n(text)",
            language="cy",
            status=PublishedQuestionGroup.Status.ACTIVE,
        )

        api_client.force_authenticate(user=user1)

        # Filter for Welsh
        response = api_client.get("/api/question-group-templates/?language=cy")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["language"] == "cy"

    def test_search_in_name_and_description(self, api_client, user1, global_template):
        """Can search templates by name and description."""
        api_client.force_authenticate(user=user1)

        # Search for "PHQ"
        response = api_client.get("/api/question-group-templates/?search=PHQ")
        assert response.status_code == 200
        assert len(response.data) == 1

        # Search for "Patient"
        response = api_client.get("/api/question-group-templates/?search=Patient")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_filter_by_tags(self, api_client, user1, global_template):
        """Can filter templates by tags."""
        api_client.force_authenticate(user=user1)

        response = api_client.get("/api/question-group-templates/?tags=depression")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_ordering(self, api_client, user1, global_template):
        """Can order templates by different fields."""
        # Create another template
        PublishedQuestionGroup.objects.create(
            publisher=user1,
            publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
            name="AAA First",
            description="Should appear first alphabetically",
            markdown="# AAA\n\n## Question\n(text)",
            status=PublishedQuestionGroup.Status.ACTIVE,
        )

        api_client.force_authenticate(user=user1)

        # Order by name
        response = api_client.get("/api/question-group-templates/?ordering=name")
        assert response.status_code == 200
        assert response.data[0]["name"] == "AAA First"


@pytest.mark.django_db
class TestTemplateRetrieveAPI:
    """Test retrieving individual template details."""

    def test_retrieve_global_template(self, api_client, user1, global_template):
        """Users can retrieve global template details."""
        api_client.force_authenticate(user=user1)
        response = api_client.get(
            f"/api/question-group-templates/{global_template.id}/"
        )

        assert response.status_code == 200
        assert response.data["name"] == "Global PHQ-9"
        assert response.data["markdown"] is not None
        assert "publisher_username" in response.data

    def test_retrieve_own_org_template(self, api_client, user1, org1, org1_template):
        """Users can retrieve their own org templates."""
        api_client.force_authenticate(user=user1)
        response = api_client.get(f"/api/question-group-templates/{org1_template.id}/")

        assert response.status_code == 200
        assert response.data["name"] == "Org1 Template"

    def test_cannot_retrieve_other_org_template(
        self, api_client, user1, org1, org2_template
    ):
        """Users cannot retrieve templates from other orgs."""
        api_client.force_authenticate(user=user1)
        response = api_client.get(f"/api/question-group-templates/{org2_template.id}/")

        assert response.status_code == 404

    def test_can_delete_field(self, api_client, user1, global_template):
        """Response includes can_delete field."""
        api_client.force_authenticate(user=user1)
        response = api_client.get(
            f"/api/question-group-templates/{global_template.id}/"
        )

        assert response.status_code == 200
        assert response.data["can_delete"] is True

    def test_can_delete_false_for_other_user(self, api_client, user2, global_template):
        """can_delete is False for templates published by others."""
        api_client.force_authenticate(user=user2)
        response = api_client.get(
            f"/api/question-group-templates/{global_template.id}/"
        )

        assert response.status_code == 200
        assert response.data["can_delete"] is False


@pytest.mark.django_db
class TestPublishQuestionGroupAPI:
    """Test publishing question groups via API."""

    def test_publish_org_level_template(self, api_client, user1, org1):
        """Organization admins can publish templates at org level."""
        # Create survey and question group
        survey = Survey.objects.create(
            owner=user1,
            name="Test Survey",
            slug="test-survey",
            organization=org1,
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Test question?",
            type="text",
            order=1,
        )

        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "My Published Template",
                "description": "Test description",
                "publication_level": "organization",
                "organization_id": org1.id,
                "language": "en",
                "tags": ["test"],
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["name"] == "My Published Template"
        assert response.data["publication_level"] == "organization"

        # Verify template was created
        template = PublishedQuestionGroup.objects.get(name="My Published Template")
        assert template.publisher == user1
        assert template.organization == org1

    def test_cannot_publish_without_permission(self, api_client, user2, user1, org1):
        """Users cannot publish templates from surveys they don't own."""
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)

        api_client.force_authenticate(user=user2)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Unauthorized",
                "publication_level": "organization",
                "organization_id": org1.id,
            },
            format="json",
        )

        assert response.status_code == 403

    def test_cannot_publish_imported_group(
        self, api_client, user1, org1, global_template
    ):
        """Cannot publish question groups that were imported from templates."""
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(
            name="Imported Group", imported_from=global_template, owner=user1
        )
        survey.question_groups.add(group)

        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Should Fail",
                "publication_level": "organization",
                "organization_id": org1.id,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "copyright" in response.data["error"].lower()

    def test_global_publication_requires_superuser(self, api_client, user1, org1):
        """Only superusers can publish global templates."""
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Test?",
            type="text",
            order=1,
        )

        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Global Template",
                "publication_level": "global",
            },
            format="json",
        )

        assert response.status_code == 403
        assert "administrator" in response.data["error"].lower()

    def test_admin_can_publish_global(self, api_client, admin_user, user1, org1):
        """Superusers can publish global templates."""
        survey = Survey.objects.create(
            owner=admin_user, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=admin_user)
        survey.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Test?",
            type="text",
            order=1,
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Global Template",
                "description": "Admin published",
                "publication_level": "global",
                "language": "en",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["publication_level"] == "global"

    def test_required_fields_validation(self, api_client, user1):
        """Publishing requires all mandatory fields."""
        api_client.force_authenticate(user=user1)

        # Missing question_group_id
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {"name": "Test"},
            format="json",
        )
        assert response.status_code == 400
        assert "question_group_id" in response.data["error"]

        # Non-existent question_group_id
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {"question_group_id": 999},
            format="json",
        )
        assert response.status_code == 404

    def test_org_level_requires_organization_id(self, api_client, user1, org1):
        """Organization-level publication requires organization_id."""
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey"
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)

        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Test",
                "publication_level": "organization",
                # Missing organization_id
            },
            format="json",
        )

        assert response.status_code == 400
        assert "organization_id" in response.data["error"]

    def test_must_be_org_admin_to_publish(self, api_client, user1, user2, org1):
        """Must be ADMIN in organization to publish at org level."""
        # user2 is not a member of org1
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)

        api_client.force_authenticate(user=user2)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Test",
                "publication_level": "organization",
                "organization_id": org1.id,
            },
            format="json",
        )

        assert response.status_code == 403
        # User doesn't have access to the survey, so permission check fails first
        assert "permission" in response.data["error"].lower()

    def test_attribution_preserved(self, api_client, user1, org1):
        """Attribution data is preserved when publishing."""
        survey = Survey.objects.create(
            owner=user1, name="Test Survey", slug="test-survey", organization=org1
        )
        group = QuestionGroup.objects.create(name="Test Group", owner=user1)
        survey.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Test?",
            type="text",
            order=1,
        )

        api_client.force_authenticate(user1)
        response = api_client.post(
            "/api/question-group-templates/publish/",
            {
                "question_group_id": group.id,
                "name": "Attributed Template",
                "description": "With attribution",
                "publication_level": "organization",
                "organization_id": org1.id,
                "attribution": {
                    "authors": "John Doe, Jane Smith",
                    "citation": "Doe et al. 2023",
                    "doi": "10.1234/example",
                },
                "show_publisher_credit": False,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["attribution"]["authors"] == "John Doe, Jane Smith"
        assert response.data["show_publisher_credit"] is False
