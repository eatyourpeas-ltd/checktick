"""
Tests for dataset access control in question groups.

Ensures that:
- Question groups can only access global datasets
- Question groups can access organization-specific datasets
- Question groups cannot access other organization's datasets
- Dataset filtering works correctly
- Proper error handling for invalid dataset access
"""

from django.contrib.auth import get_user_model
import pytest

from checktick_app.surveys.external_datasets import get_available_datasets
from checktick_app.surveys.models import (
    DataSet,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def users(db):
    """Create test users."""
    user1 = User.objects.create_user(
        username="user1",
        email="user1@example.com",
        password=TEST_PASSWORD,
    )
    user2 = User.objects.create_user(
        username="user2",
        email="user2@example.com",
        password=TEST_PASSWORD,
    )
    return {"user1": user1, "user2": user2}


@pytest.fixture
def organizations(db, users):
    """Create test organizations."""
    org1 = Organization.objects.create(
        name="Org 1",
        owner=users["user1"],
    )
    org2 = Organization.objects.create(
        name="Org 2",
        owner=users["user2"],
    )
    return {"org1": org1, "org2": org2}


@pytest.fixture
def datasets(db, organizations):
    """Create test datasets with different scopes."""
    # Global dataset (available to all)
    global_ds = DataSet.objects.create(
        key="global_specialty",
        name="Global Specialty Codes",
        category="nhs_dd",
        source_type="nhs_dd_specialty",
        is_global=True,
        is_active=True,
        options=[
            {"value": "100", "label": "General Surgery"},
            {"value": "101", "label": "Urology"},
        ],
    )

    # Org1-specific dataset
    org1_ds = DataSet.objects.create(
        key="org1_custom",
        name="Org 1 Custom List",
        category="user_created",
        source_type="custom",
        is_global=False,
        organization=organizations["org1"],
        is_active=True,
        options=[
            {"value": "A", "label": "Option A"},
            {"value": "B", "label": "Option B"},
        ],
    )

    # Org2-specific dataset
    org2_ds = DataSet.objects.create(
        key="org2_custom",
        name="Org 2 Custom List",
        category="user_created",
        source_type="custom",
        is_global=False,
        organization=organizations["org2"],
        is_active=True,
        options=[
            {"value": "X", "label": "Option X"},
            {"value": "Y", "label": "Option Y"},
        ],
    )

    # Inactive dataset (should not appear)
    inactive_ds = DataSet.objects.create(
        key="inactive_dataset",
        name="Inactive Dataset",
        category="user_created",
        source_type="custom",
        is_global=True,
        is_active=False,
        options=[],
    )

    return {
        "global": global_ds,
        "org1": org1_ds,
        "org2": org2_ds,
        "inactive": inactive_ds,
    }


@pytest.mark.django_db
class TestDatasetAccessControl:
    """Test dataset access control for question groups."""

    def test_global_datasets_available_to_all_orgs(self, datasets, organizations):
        """Global datasets should be available to all organizations."""
        org1_datasets = get_available_datasets(organization=organizations["org1"])
        org2_datasets = get_available_datasets(organization=organizations["org2"])

        # Both orgs should see the global dataset
        assert "global_specialty" in org1_datasets
        assert "global_specialty" in org2_datasets
        assert org1_datasets["global_specialty"] == "Global Specialty Codes"

    def test_org_specific_datasets_only_visible_to_owner(self, datasets, organizations):
        """Organization-specific datasets should only be visible to their owner."""
        org1_datasets = get_available_datasets(organization=organizations["org1"])
        org2_datasets = get_available_datasets(organization=organizations["org2"])

        # Org1 should see its own custom dataset
        assert "org1_custom" in org1_datasets
        assert org1_datasets["org1_custom"] == "Org 1 Custom List"

        # Org1 should NOT see org2's dataset
        assert "org2_custom" not in org1_datasets

        # Org2 should see its own custom dataset
        assert "org2_custom" in org2_datasets
        assert org2_datasets["org2_custom"] == "Org 2 Custom List"

        # Org2 should NOT see org1's dataset
        assert "org1_custom" not in org2_datasets

    def test_inactive_datasets_not_visible(self, datasets, organizations):
        """Inactive datasets should not appear in available datasets."""
        org_datasets = get_available_datasets(organization=organizations["org1"])
        no_org_datasets = get_available_datasets(organization=None)

        assert "inactive_dataset" not in org_datasets
        assert "inactive_dataset" not in no_org_datasets

    def test_no_org_context_shows_only_global(self, datasets):
        """When no organization is provided, only global datasets should be shown."""
        datasets_list = get_available_datasets(organization=None)

        assert "global_specialty" in datasets_list
        assert "org1_custom" not in datasets_list
        assert "org2_custom" not in datasets_list

    def test_question_can_link_to_global_dataset(self, datasets, users, organizations):
        """Questions should be able to link to global datasets."""
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-1",
        )
        group = QuestionGroup.objects.create(
            name="Test Group",
            owner=users["user1"],
        )
        survey.question_groups.add(group)

        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["global"],
            order=1,
        )

        assert question.dataset == datasets["global"]
        assert question.dataset.key == "global_specialty"

    def test_question_can_link_to_org_dataset(self, datasets, users, organizations):
        """Questions should be able to link to their organization's datasets."""
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-2",
        )
        group = QuestionGroup.objects.create(
            name="Test Group",
            owner=users["user1"],
        )
        survey.question_groups.add(group)

        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Select option",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["org1"],
            order=1,
        )

        assert question.dataset == datasets["org1"]
        assert question.dataset.key == "org1_custom"

    def test_question_cannot_link_to_other_org_dataset(
        self, datasets, users, organizations
    ):
        """Questions should not be linked to other organization's datasets (soft enforcement)."""
        # NOTE: Database allows this at FK level, but view logic should prevent it
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-3",
        )
        group = QuestionGroup.objects.create(
            name="Test Group",
            owner=users["user1"],
        )
        survey.question_groups.add(group)

        # At model level, this is allowed (FK constraint), but the view should filter it out
        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Select option",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["org2"],  # Wrong org!
            order=1,
        )

        # The question was created with the wrong dataset
        # But when fetching datasets for the survey's org, it won't find org2's dataset
        available = get_available_datasets(organization=survey.organization)
        assert question.dataset.key not in available

    def test_dataset_field_optional(self, users, organizations):
        """Dataset field should be optional for questions."""
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-4",
        )
        group = QuestionGroup.objects.create(
            name="Test Group",
            owner=users["user1"],
        )
        survey.question_groups.add(group)

        # Question without dataset should work fine
        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Enter text",
            type=SurveyQuestion.Types.TEXT,
            order=1,
        )

        assert question.dataset is None

    def test_dataset_link_survives_options_update(self, datasets, users, organizations):
        """Dataset link should persist even when options are manually edited."""
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-5",
        )
        group = QuestionGroup.objects.create(
            name="Test Group",
            owner=users["user1"],
        )
        survey.question_groups.add(group)

        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["global"],
            order=1,
        )

        # Manually override options
        question.options = [{"value": "custom", "label": "Custom Option"}]
        question.save()

        # Dataset link should still exist
        question.refresh_from_db()
        assert question.dataset == datasets["global"]
        assert question.options == [{"value": "custom", "label": "Custom Option"}]


@pytest.mark.django_db
class TestQuestionViewAccessControl:
    """Test that question creation/editing views enforce dataset access control."""

    def test_builder_question_create_with_valid_global_dataset(
        self, client, users, organizations, datasets
    ):
        """Creating a question with a global dataset should succeed."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-1",
        )

        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/create",
            {
                "text": "Select specialty",
                "type": "dropdown",
                "prefilled_dataset": "global_specialty",
                "options": "",  # Will be populated from dataset
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.dataset == datasets["global"]
        assert question.dataset.key == "global_specialty"

    def test_builder_question_create_with_valid_org_dataset(
        self, client, users, organizations, datasets
    ):
        """Creating a question with own org's dataset should succeed."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-2",
        )

        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/create",
            {
                "text": "Select option",
                "type": "dropdown",
                "prefilled_dataset": "org1_custom",
                "options": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.dataset == datasets["org1"]

    def test_builder_question_create_with_other_org_dataset_ignored(
        self, client, users, organizations, datasets
    ):
        """Attempting to use another org's dataset should result in no dataset link."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-3",
        )

        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/create",
            {
                "text": "Select option",
                "type": "dropdown",
                "prefilled_dataset": "org2_custom",  # Wrong org!
                "options": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        # Dataset should be None because org2_custom is not accessible
        assert question.dataset is None

    def test_builder_question_create_with_invalid_dataset_key(
        self, client, users, organizations
    ):
        """Using a non-existent dataset key should result in no dataset link."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-4",
        )

        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/create",
            {
                "text": "Select option",
                "type": "dropdown",
                "prefilled_dataset": "nonexistent_dataset",
                "options": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.dataset is None

    def test_builder_question_edit_can_change_dataset(
        self, client, users, organizations, datasets
    ):
        """Editing a question should allow changing its linked dataset."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-5",
        )

        # Create question with global dataset
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Select option",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["global"],
            order=1,
        )

        # Edit to use org1's dataset
        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/{question.id}/edit",
            {
                "text": "Select custom option",
                "type": "dropdown",
                "prefilled_dataset": "org1_custom",
                "options": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question.refresh_from_db()
        assert question.dataset == datasets["org1"]

    def test_builder_question_edit_can_remove_dataset(
        self, client, users, organizations, datasets
    ):
        """Editing a question should allow removing its dataset link."""
        client.force_login(users["user1"])
        survey = Survey.objects.create(
            owner=users["user1"],
            organization=organizations["org1"],
            name="Test Survey",
            slug="test-survey-view-6",
        )

        # Create question with dataset
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Select option",
            type=SurveyQuestion.Types.DROPDOWN,
            dataset=datasets["global"],
            order=1,
        )

        # Edit without specifying dataset
        response = client.post(
            f"/surveys/{survey.slug}/builder/questions/{question.id}/edit",
            {
                "text": "Select option",
                "type": "dropdown",
                "options": "Manual Option 1\nManual Option 2",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question.refresh_from_db()
        assert question.dataset is None
