"""
Comprehensive tests for question creation through the webapp builder.

These tests cover the webapp endpoints for creating questions, ensuring they
handle all question types correctly, validate inputs, and support features
like follow-up text inputs.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion

TEST_PASSWORD = "testpass123"


@pytest.mark.django_db
class TestWebappQuestionCreation:
    """Test suite for creating questions through the webapp builder."""

    def setup_survey(self, client):
        """Create a user and survey for testing."""
        user = User.objects.create_user(username="testuser", password=TEST_PASSWORD)
        survey = Survey.objects.create(owner=user, name="Test Survey", slug="test")
        client.force_login(user)
        return user, survey

    # === Basic Question Type Creation Tests ===

    def test_create_text_question(self, client):
        """Test creating a basic text question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "What is your name?",
                "type": "text",
                "text_format": "free",
                "required": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Question created." in response.content

        questions = SurveyQuestion.objects.filter(survey=survey)
        assert questions.count() == 1
        question = questions.first()
        assert question.text == "What is your name?"
        assert question.type == SurveyQuestion.Types.TEXT
        assert question.required is True
        assert question.options == [{"type": "text", "format": "free"}]

    def test_create_text_question_with_number_format(self, client):
        """Test creating a text question with number format."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

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
        assert question.type == SurveyQuestion.Types.TEXT
        assert question.options == [{"type": "text", "format": "number"}]
        assert question.required is False  # Default when not specified

    def test_create_mc_single_question(self, client):
        """Test creating a multiple choice (single) question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "What is your favorite color?",
                "type": "mc_single",
                "options": "Red\nBlue\nGreen\n",
                "required": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE
        assert len(question.options) == 3
        assert question.options[0] == {"label": "Red", "value": "Red"}
        assert question.options[1] == {"label": "Blue", "value": "Blue"}
        assert question.options[2] == {"label": "Green", "value": "Green"}
        assert question.required is True

    def test_create_mc_multi_question(self, client):
        """Test creating a multiple choice (multiple) question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Select all that apply",
                "type": "mc_multi",
                "options": "Option A\nOption B\nOption C",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.MULTIPLE_CHOICE_MULTI
        assert len(question.options) == 3
        assert question.options[0] == {"label": "Option A", "value": "Option A"}

    def test_create_dropdown_question(self, client):
        """Test creating a dropdown question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Select your country",
                "type": "dropdown",
                "options": "USA\nUK\nCanada",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.DROPDOWN
        assert len(question.options) == 3
        assert question.options[0] == {"label": "USA", "value": "USA"}

    def test_create_yesno_question(self, client):
        """Test creating a yes/no question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Do you agree?",
                "type": "yesno",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.YESNO
        # Webapp creates yes/no with label/value structure
        assert len(question.options) == 2
        assert question.options[0] == {"label": "Yes", "value": "yes"}
        assert question.options[1] == {"label": "No", "value": "no"}

    def test_create_likert_question(self, client):
        """Test creating a Likert scale question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Rate your satisfaction",
                "type": "likert",
                "likert_mode": "categories",
                "likert_categories": "1\n2\n3\n4\n5",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.LIKERT
        assert question.options == ["1", "2", "3", "4", "5"]

    def test_create_likert_categories_radio(self, client):
        """Likert categories with render=radio stores the render mode."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Agreement",
                "type": "likert",
                "likert_mode": "categories",
                "likert_categories": "Disagree\nNeutral\nAgree",
                "likert_render": "radio",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.LIKERT
        assert question.options == [
            {
                "type": "categories",
                "labels": ["Disagree", "Neutral", "Agree"],
                "render": "radio",
            }
        ]

    def test_create_likert_number_radio(self, client):
        """Likert number scale with render=radio stores the render mode."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Satisfaction 1-5",
                "type": "likert",
                "likert_mode": "number",
                "likert_min": "1",
                "likert_max": "5",
                "likert_render": "radio",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.LIKERT
        assert question.options[0]["type"] == "number-scale"
        assert question.options[0]["render"] == "radio"
        assert question.options[0]["min"] == 1
        assert question.options[0]["max"] == 5

    def test_create_likert_categories_slider_omits_render(self, client):
        """Slider is the default — no render key should be stored."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Agreement",
                "type": "likert",
                "likert_mode": "categories",
                "likert_categories": "Disagree\nNeutral\nAgree",
                "likert_render": "slider",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        # Slider default: plain list of strings, no render key
        assert question.options == ["Disagree", "Neutral", "Agree"]

    def test_create_orderable_question(self, client):
        """Test creating an orderable list question."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Rank these in order",
                "type": "orderable",
                "options": "First\nSecond\nThird",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.ORDERABLE
        assert len(question.options) == 3
        assert question.options[0] == {"label": "First", "value": "First"}

    # === Follow-up Text Feature Tests ===

    def test_create_mc_single_with_followup_text(self, client):
        """Test creating MC single question with follow-up text input."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "How did you hear about us?",
                "type": "mc_single",
                "options": "Friend\nSocial Media\nOther",
                "option_2_followup": "on",  # 'Other' is index 2
                "option_2_followup_label": "Please specify",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.type == SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE
        assert len(question.options) == 3
        assert "followup_text" not in question.options[0]
        assert "followup_text" not in question.options[1]
        assert "followup_text" in question.options[2]
        assert question.options[2]["followup_text"]["enabled"] is True
        assert question.options[2]["followup_text"]["label"] == "Please specify"

    def test_create_mc_multi_with_multiple_followups(self, client):
        """Test creating MC multi question with multiple follow-up inputs."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Select all symptoms",
                "type": "mc_multi",
                "options": "Headache\nFever\nOther",
                "option_1_followup": "on",  # Fever
                "option_1_followup_label": "Temperature",
                "option_2_followup": "on",  # Other
                "option_2_followup_label": "Describe",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert len(question.options) == 3
        assert "followup_text" not in question.options[0]
        assert question.options[1]["followup_text"]["enabled"] is True
        assert question.options[1]["followup_text"]["label"] == "Temperature"
        assert question.options[2]["followup_text"]["enabled"] is True
        assert question.options[2]["followup_text"]["label"] == "Describe"

    def test_create_dropdown_with_followup(self, client):
        """Test creating dropdown question with follow-up text."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Employment status",
                "type": "dropdown",
                "options": "Employed\nSelf-employed\nUnemployed",
                "option_1_followup": "on",  # Self-employed
                "option_1_followup_label": "Job title",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert "followup_text" in question.options[1]
        assert question.options[1]["followup_text"]["enabled"] is True
        assert question.options[1]["followup_text"]["label"] == "Job title"

    def test_create_yesno_with_followup_on_yes(self, client):
        """Test creating yes/no question with follow-up on yes."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Do you have allergies?",
                "type": "yesno",
                "yesno_yes_followup": "on",
                "yesno_yes_followup_label": "List allergies",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert "followup_text" in question.options[0]
        assert question.options[0]["followup_text"]["enabled"] is True
        assert question.options[0]["followup_text"]["label"] == "List allergies"
        assert "followup_text" not in question.options[1]

    def test_create_orderable_with_followup(self, client):
        """Test creating orderable question with follow-up text."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Rank priorities",
                "type": "orderable",
                "options": "Cost\nQuality\nOther",
                "option_2_followup": "on",  # Other
                "option_2_followup_label": "Specify",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert "followup_text" in question.options[2]
        assert question.options[2]["followup_text"]["enabled"] is True

    # === Question Groups Tests ===

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

    def test_create_multiple_questions_in_different_groups(self, client):
        """Test creating questions in different groups."""
        user, survey = self.setup_survey(client)
        group1 = QuestionGroup.objects.create(name="Group 1", owner=user)
        group2 = QuestionGroup.objects.create(name="Group 2", owner=user)
        survey.question_groups.add(group1, group2)

        url1 = reverse(
            "surveys:builder_group_question_create",
            kwargs={"slug": survey.slug, "gid": group1.id},
        )
        url2 = reverse(
            "surveys:builder_group_question_create",
            kwargs={"slug": survey.slug, "gid": group2.id},
        )

        client.post(
            url1,
            {"text": "Question 1", "type": "text", "text_format": "free"},
            HTTP_HX_REQUEST="true",
        )
        client.post(
            url2,
            {"text": "Question 2", "type": "text", "text_format": "free"},
            HTTP_HX_REQUEST="true",
        )

        questions = SurveyQuestion.objects.filter(survey=survey).order_by("id")
        assert questions.count() == 2
        assert questions[0].group_id == group1.id
        assert questions[1].group_id == group2.id

    # === Question Ordering Tests ===

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

    # === Backward Compatibility Tests ===

    def test_create_with_string_array_options(self, client):
        """Test creating question with simple string array options (backward compat)."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Choose one",
                "type": "mc_single",
                "options": "Option 1\nOption 2\nOption 3",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        # Webapp creates label/value format
        assert len(question.options) == 3
        assert question.options[0] == {"label": "Option 1", "value": "Option 1"}
        assert question.options[1] == {"label": "Option 2", "value": "Option 2"}
        assert question.options[2] == {"label": "Option 3", "value": "Option 3"}

    # === Edge Cases and Validation Tests ===

    def test_create_question_with_empty_text(self, client):
        """Test creating a question with empty text defaults to 'Untitled'."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "",
                "type": "text",
                "text_format": "free",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        assert question.text == "Untitled"

    def test_create_question_whitespace_trimmed_from_options(self, client):
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
        # Empty lines should be filtered out
        assert len(question.options) == 3
        # Webapp creates label/value format
        assert question.options[0]["label"] == "Option 1"
        assert question.options[1]["label"] == "Option 2"
        assert question.options[2]["label"] == "Option 3"

    # === Permission Tests ===

    def test_unauthenticated_cannot_create_question(self, client):
        """Test that unauthenticated users cannot create questions."""
        user = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        survey = Survey.objects.create(owner=user, name="Test", slug="test")
        # Don't log in
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {"text": "Question", "type": "text", "text_format": "free"},
            HTTP_HX_REQUEST="true",
        )

        # Should redirect to login or return 403
        assert response.status_code in [302, 403]
        assert SurveyQuestion.objects.filter(survey=survey).count() == 0

    def test_user_without_permission_cannot_create_question(self, client):
        """Test that users without edit permission cannot create questions."""
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        other_user = User.objects.create_user(username="other", password=TEST_PASSWORD)
        survey = Survey.objects.create(owner=owner, name="Test", slug="test")

        client.force_login(other_user)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {"text": "Question", "type": "text", "text_format": "free"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 403
        assert SurveyQuestion.objects.filter(survey=survey).count() == 0

    # === Response Format Tests ===

    def test_create_returns_questions_list(self, client):
        """Test that create returns the questions list partial."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {"text": "Test Question", "type": "text", "text_format": "free"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        html = response.content.decode()
        # Should contain success message
        assert "Question created." in html
        # Should contain the question text
        assert "Test Question" in html

    def test_create_includes_builder_payload_for_javascript(self, client):
        """Test that created question includes builder payload metadata."""
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

        response = client.post(
            url,
            {
                "text": "Test Question",
                "type": "mc_single",
                "options": "Option 1\nOption 2",
                "option_0_followup": "on",
                "option_0_followup_label": "Why?",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        question = SurveyQuestion.objects.get(survey=survey)
        html = response.content.decode()

        # Should have a script tag with question data
        script_id = f"question-data-{question.id}"
        assert script_id in html

        # Verify the question was created with followup
        assert "followup_text" in question.options[0]
        assert question.options[0]["followup_text"]["label"] == "Why?"
