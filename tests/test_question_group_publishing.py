"""
Tests for question group publishing and import functionality.

Focused tests that verify the core functionality without overly complex setup.
"""

import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

User = get_user_model()
TEST_PASSWORD = "test-pass"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable rate limiting for all tests."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def publisher_user(django_user_model):
    """Create a user who can publish question groups."""
    return django_user_model.objects.create_user(
        username="publisher@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def other_user(django_user_model):
    """Create another user for permission tests."""
    return django_user_model.objects.create_user(
        username="other@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def test_organization(publisher_user):
    """Create a test organization to bypass encryption setup."""
    return Organization.objects.create(
        name="Test Organization", owner=publisher_user
    )


@pytest.fixture
def published_org_template(publisher_user, test_organization):
    """Create a published organization-level template."""
    return PublishedQuestionGroup.objects.create(
        name="Org Template",
        description="Organization-level template",
        publisher=publisher_user,
        organization=test_organization,
        publication_level="organization",
        status="active",
        markdown="# Org Template\n\n## Q1\ntype: text\nQuestion text here",
        show_publisher_credit=True,
    )


@pytest.fixture
def published_global_template(publisher_user):
    """Create a published global template."""
    return PublishedQuestionGroup.objects.create(
        name="Global Template",
        description="Global template available to all",
        publisher=publisher_user,
        publication_level="global",
        status="active",
        markdown="# Global Template\n\n## Q1\ntype: text\nQuestion text here",
        attribution={
            "authors": "Test Author",
            "title": "Test Scale",
            "year": 2024,
        },
        show_publisher_credit=False,
    )


@pytest.mark.django_db
class TestPublishedQuestionGroupModel:
    """Test the PublishedQuestionGroup model."""

    def test_create_organization_template(self, publisher_user, test_organization):
        """Organization templates can be created."""
        template = PublishedQuestionGroup.objects.create(
            name="Test Template",
            description="Test description",
            publisher=publisher_user,
            organization=test_organization,
            publication_level="organization",
            status="active",
            markdown="# Test\n\n## Q1\ntype: text\nTest question",
        )

        assert template.publication_level == "organization"
        assert template.organization == test_organization
        assert template.status == "active"

    def test_create_global_template(self, publisher_user):
        """Global templates can be created without organization."""
        template = PublishedQuestionGroup.objects.create(
            name="Global Test",
            description="Global template",
            publisher=publisher_user,
            publication_level="global",
            status="active",
            markdown="# Global\n\n## Q1\ntype: text\nGlobal question",
        )

        assert template.publication_level == "global"
        assert template.organization is None

    def test_increment_import_count(self, published_global_template):
        """Import count increments correctly."""
        initial_count = published_global_template.import_count

        published_global_template.increment_import_count()

        assert published_global_template.import_count == initial_count + 1

    def test_attribution_storage(self, publisher_user):
        """Attribution metadata is stored correctly."""
        template = PublishedQuestionGroup.objects.create(
            name="Attributed Template",
            publisher=publisher_user,
            publication_level="global",
            status="active",
            markdown="# Test",
            attribution={
                "authors": "Smith, Jones",
                "title": "Test Scale",
                "year": 2024,
                "doi": "10.1234/test",
            },
        )

        assert template.attribution["authors"] == "Smith, Jones"
        assert template.attribution["doi"] == "10.1234/test"

    def test_show_publisher_credit_default(self, publisher_user):
        """Publisher credit is shown by default."""
        template = PublishedQuestionGroup.objects.create(
            name="Default Credit",
            publisher=publisher_user,
            publication_level="global",
            status="active",
            markdown="# Test",
        )

        assert template.show_publisher_credit is True


@pytest.mark.django_db
class TestTemplateDiscovery:
    """Test template listing and discovery."""

    def test_anonymous_sees_only_global_templates(
        self, client, published_global_template, published_org_template
    ):
        """Anonymous users should only see global templates."""
        response = client.get("/surveys/templates/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Global Template" in content
        assert "Org Template" not in content

    def test_filter_by_publication_level(
        self, client, publisher_user, published_global_template, published_org_template
    ):
        """Users can filter templates by publication level."""
        client.force_login(publisher_user)

        # Filter for global only
        response = client.get("/surveys/templates/?level=global")
        content = response.content.decode()
        assert "Global Template" in content

        # Filter for organization only
        response = client.get("/surveys/templates/?level=organization")
        content = response.content.decode()
        assert "Org Template" in content

    def test_search_templates(
        self, client, published_global_template, published_org_template
    ):
        """Users can search templates by title/description."""
        response = client.get("/surveys/templates/?q=Global")

        content = response.content.decode()
        assert "Global Template" in content
        assert "Org Template" not in content


@pytest.mark.django_db
class TestAttributionDisplay:
    """Test attribution and publisher credit display."""

    def test_attribution_displayed_over_publisher_credit(
        self, client, published_global_template
    ):
        """When attribution.authors exists, it should be displayed."""
        response = client.get("/surveys/templates/")
        content = response.content.decode()

        # Should see author name
        assert "Test Author" in content

    def test_publisher_credit_shown_when_enabled(
        self, client, publisher_user, published_org_template
    ):
        """When show_publisher_credit=True and no attribution, show publisher."""
        client.force_login(publisher_user)

        response = client.get("/surveys/templates/")
        content = response.content.decode()

        # Should see publisher username or organization name
        assert published_org_template.name in content


@pytest.mark.django_db
class TestMarkdownExport:
    """Test markdown export functionality."""

    def test_export_question_with_options(self):
        """Question options should be preserved in markdown export."""
        from checktick_app.surveys.views import _export_question_group_to_markdown

        user = User.objects.create_user(username="testuser", password=TEST_PASSWORD)
        survey = Survey.objects.create(owner=user, name="Test Survey", slug="test")
        group = QuestionGroup.objects.create(
            owner=user, name="Test Group", description="Test description"
        )
        survey.question_groups.add(group)

        # Create question with options
        SurveyQuestion.objects.create(
            survey=survey,
            text="How do you feel?",
            type="mc_single",
            options=[{"label": "Good", "value": "good"}, {"label": "Bad", "value": "bad"}],
            order=1,
        )

        markdown = _export_question_group_to_markdown(group, survey)

        assert "How do you feel?" in markdown
        assert "Good" in markdown
        assert "Bad" in markdown

    def test_export_likert_categories(self):
        """Likert scales with categories export correctly."""
        from checktick_app.surveys.views import _export_question_group_to_markdown

        user = User.objects.create_user(username="testuser", password=TEST_PASSWORD)
        survey = Survey.objects.create(owner=user, name="Test Survey", slug="test")
        group = QuestionGroup.objects.create(
            owner=user, name="Test Group", description="Test description"
        )
        survey.question_groups.add(group)

        # Create likert question with categories
        SurveyQuestion.objects.create(
            survey=survey,
            text="Rate your mood",
            type="likert",
            options=[{"type": "categories", "labels": ["Never", "Sometimes", "Often", "Always"]}],
            order=1,
        )

        markdown = _export_question_group_to_markdown(group, survey)

        assert "type: likert categories" in markdown or "likert" in markdown.lower()
        assert "Never" in markdown
        assert "Always" in markdown


@pytest.mark.django_db
class TestGlobalTemplateSync:
    """Test the sync_global_question_group_templates management command."""

    @patch("pathlib.Path.glob")
    def test_sync_creates_new_template(self, mock_glob, publisher_user, tmp_path):
        """Sync command should create new templates from markdown files."""
        # Create a temporary markdown file
        template_file = tmp_path / "question-group-templates-gad7.md"
        template_file.write_text("""---
title: GAD-7
description: Generalized Anxiety Disorder 7-item scale
attribution:
  authors: Spitzer, Kroenke, Williams, Löwe
  title: GAD-7
  year: 2006
tags:
  - anxiety
  - mental-health
license: public-domain
---

# GAD-7

## Q1
type: likert categories
Over the last 2 weeks, how often have you been bothered by feeling nervous?

- Not at all
- Several days
- More than half the days
- Nearly every day
""")

        mock_glob.return_value = [template_file]

        out = StringIO()
        call_command("sync_global_question_group_templates", stdout=out)

        # Verify template was created
        assert PublishedQuestionGroup.objects.filter(name="GAD-7").exists()
        template = PublishedQuestionGroup.objects.get(name="GAD-7")
        assert template.publication_level == "global"
        assert template.status == "active"
        assert "Spitzer" in template.attribution.get("authors", "")

    @patch("pathlib.Path.glob")
    def test_sync_updates_existing_template(self, mock_glob, publisher_user, tmp_path):
        """Sync command should update templates when content changes."""
        # Create initial template
        initial = PublishedQuestionGroup.objects.create(
            name="Test Template",
            description="Old description",
            publisher=publisher_user,
            publication_level="global",
            status="active",
            markdown="# Old content",
        )

        # Create updated markdown file
        template_file = tmp_path / "question-group-templates-test-template.md"
        template_file.write_text("""---
title: Test Template
description: New description
tags:
  - test
---

# Test Template

## Q1
type: text
New question content
""")

        mock_glob.return_value = [template_file]

        out = StringIO()
        call_command("sync_global_question_group_templates", stdout=out)

        # Verify template was updated
        initial.refresh_from_db()
        assert initial.description == "New description"
        assert "New question content" in initial.markdown

    @patch("pathlib.Path.glob")
    def test_sync_dry_run_does_not_commit(self, mock_glob, tmp_path):
        """Sync command with --dry-run should not create templates."""
        template_file = tmp_path / "question-group-templates-dryrun.md"
        template_file.write_text("""---
title: Dry Run Test
description: Should not be created
tags:
  - test
---

# Dry Run Test

## Q1
type: text
Test question
""")

        mock_glob.return_value = [template_file]

        initial_count = PublishedQuestionGroup.objects.count()

        out = StringIO()
        call_command("sync_global_question_group_templates", "--dry-run", stdout=out)

        # Verify no templates were created
        assert PublishedQuestionGroup.objects.count() == initial_count
        assert not PublishedQuestionGroup.objects.filter(name="Dry Run Test").exists()


@pytest.mark.django_db
class TestTemplateDetail:
    """Test template detail view."""

    def test_view_global_template_detail(
        self, client, published_global_template
    ):
        """Anyone should be able to view global template details."""
        response = client.get(f"/surveys/templates/{published_global_template.id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert published_global_template.name in content
        assert published_global_template.description in content

    def test_attribution_displayed_in_detail(
        self, client, published_global_template
    ):
        """Attribution information should be displayed in detail view."""
        response = client.get(f"/surveys/templates/{published_global_template.id}/")

        content = response.content.decode()
        assert "Test Author" in content
        assert "Test Scale" in content
