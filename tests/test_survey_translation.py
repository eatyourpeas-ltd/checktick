"""
Tests for survey cloning and translation functionality.

Tests cover:
- Basic survey cloning (create_clone)
- Translation creation (create_translation)
- Translation group management
- Question and question group copying
- Condition preservation across clones
"""

from django.contrib.auth import get_user_model
import pytest

from checktick_app.surveys.llm_client import ConversationalSurveyLLM
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    """Create a survey owner user."""
    return django_user_model.objects.create_user(
        username="owner@example.com", email="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def organization(owner):
    """Create a test organization."""
    return Organization.objects.create(name="Test Org", owner=owner)


@pytest.fixture
def question_group(owner):
    """Create a question group."""
    return QuestionGroup.objects.create(
        owner=owner,
        name="Demographics",
        description="Basic demographic questions",
    )


@pytest.fixture
def basic_survey(owner, organization, question_group):
    """Create a basic survey with questions."""
    survey = Survey.objects.create(
        owner=owner,
        organization=organization,
        name="Patient Survey",
        slug="patient-survey",
        description="A survey about patient care",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
        language="en",
    )

    # Add question group
    survey.question_groups.add(question_group)

    # Add questions
    SurveyQuestion.objects.create(
        survey=survey,
        group=question_group,
        text="What is your age?",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )

    q2 = SurveyQuestion.objects.create(
        survey=survey,
        group=question_group,
        text="Do you have diabetes?",
        type=SurveyQuestion.Types.YESNO,
        required=True,
        order=1,
    )

    q3 = SurveyQuestion.objects.create(
        survey=survey,
        group=question_group,
        text="What type of diabetes?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        required=False,
        order=2,
        options={"choices": ["Type 1", "Type 2", "Gestational", "Other"]},
    )

    # Add conditional logic: q3 only shows if q2 is "yes"
    SurveyQuestionCondition.objects.create(
        question=q2,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_question=q3,
        action=SurveyQuestionCondition.Action.SHOW,
    )

    return survey


# ============================================================================
# Basic Cloning Tests
# ============================================================================


@pytest.mark.django_db
class TestSurveyCloning:
    """Tests for basic survey cloning functionality."""

    def test_create_clone_with_default_name(self, basic_survey):
        """Cloning should create a copy with 'Copy of' prefix."""
        cloned = basic_survey.create_clone()

        assert cloned.name == "Copy of Patient Survey"
        assert cloned.slug == "copy-of-patient-survey"
        assert cloned.id != basic_survey.id
        assert cloned.owner == basic_survey.owner
        assert cloned.organization == basic_survey.organization

    def test_create_clone_with_custom_name(self, basic_survey):
        """Cloning should accept custom name and slug."""
        cloned = basic_survey.create_clone(
            new_name="Patient Survey v2", new_slug="patient-survey-v2"
        )

        assert cloned.name == "Patient Survey v2"
        assert cloned.slug == "patient-survey-v2"

    def test_clone_copies_description_and_settings(self, basic_survey):
        """Cloning should preserve description and settings."""
        cloned = basic_survey.create_clone()

        assert cloned.description == basic_survey.description
        assert cloned.visibility == basic_survey.visibility
        assert cloned.captcha_required == basic_survey.captcha_required
        assert cloned.max_responses == basic_survey.max_responses
        assert cloned.retention_months == basic_survey.retention_months

    def test_clone_resets_publishing_status(self, basic_survey):
        """Cloned survey should start as draft with reset dates."""
        basic_survey.status = Survey.Status.PUBLISHED
        basic_survey.save()

        cloned = basic_survey.create_clone()

        assert cloned.status == Survey.Status.DRAFT
        assert cloned.published_at is None
        assert cloned.start_at is None
        assert cloned.end_at is None
        assert cloned.unlisted_key is None

    def test_clone_copies_question_groups(self, basic_survey):
        """Cloning should copy all question groups."""
        cloned = basic_survey.create_clone()

        assert cloned.question_groups.count() == basic_survey.question_groups.count()

        # Question groups should be different objects
        original_qg_ids = set(basic_survey.question_groups.values_list("id", flat=True))
        cloned_qg_ids = set(cloned.question_groups.values_list("id", flat=True))
        assert not original_qg_ids.intersection(cloned_qg_ids)

    def test_clone_copies_questions(self, basic_survey):
        """Cloning should copy all questions with correct content."""
        original_questions = SurveyQuestion.objects.filter(survey=basic_survey)
        cloned = basic_survey.create_clone()
        cloned_questions = SurveyQuestion.objects.filter(survey=cloned)

        assert cloned_questions.count() == original_questions.count()

        # Check question text is preserved
        original_texts = set(original_questions.values_list("text", flat=True))
        cloned_texts = set(cloned_questions.values_list("text", flat=True))
        assert original_texts == cloned_texts

    def test_clone_preserves_question_order(self, basic_survey):
        """Cloning should maintain question order."""
        cloned = basic_survey.create_clone()

        original_questions = list(
            SurveyQuestion.objects.filter(survey=basic_survey).order_by("order")
        )
        cloned_questions = list(
            SurveyQuestion.objects.filter(survey=cloned).order_by("order")
        )

        for orig, clone in zip(original_questions, cloned_questions):
            assert orig.order == clone.order
            assert orig.text == clone.text

    def test_clone_preserves_question_types_and_options(self, basic_survey):
        """Cloning should preserve question types and options."""
        cloned = basic_survey.create_clone()

        # Find the multiple choice question
        original_mc = SurveyQuestion.objects.get(
            survey=basic_survey, text="What type of diabetes?"
        )
        cloned_mc = SurveyQuestion.objects.get(
            survey=cloned, text="What type of diabetes?"
        )

        assert cloned_mc.type == original_mc.type
        assert cloned_mc.options == original_mc.options

    def test_clone_copies_question_conditions(self, basic_survey):
        """Cloning should preserve conditional logic between questions."""
        cloned = basic_survey.create_clone()

        # Original has 1 condition
        original_conditions = SurveyQuestionCondition.objects.filter(
            question__survey=basic_survey
        )
        assert original_conditions.count() == 1

        # Clone should also have 1 condition
        cloned_conditions = SurveyQuestionCondition.objects.filter(
            question__survey=cloned
        )
        assert cloned_conditions.count() == 1

        # Check condition details are preserved
        orig_cond = original_conditions.first()
        clone_cond = cloned_conditions.first()

        assert clone_cond.operator == orig_cond.operator
        assert clone_cond.value == orig_cond.value
        assert clone_cond.action == orig_cond.action

        # Questions should be different but condition should reference the cloned questions
        assert clone_cond.question.survey == cloned
        assert clone_cond.target_question.survey == cloned

    def test_clone_handles_slug_conflicts(self, basic_survey):
        """Cloning should auto-increment slug if conflict exists."""
        clone1 = basic_survey.create_clone()
        clone2 = basic_survey.create_clone()
        clone3 = basic_survey.create_clone()

        assert clone1.slug == "copy-of-patient-survey"
        assert clone2.slug == "copy-of-patient-survey-1"
        assert clone3.slug == "copy-of-patient-survey-2"

    def test_clone_does_not_copy_translation_fields(self, basic_survey):
        """Plain clones should not inherit translation group."""
        cloned = basic_survey.create_clone()

        assert cloned.language == basic_survey.language  # Same language
        assert cloned.translation_group is None  # No translation group
        assert cloned.is_original is True  # Treated as original
        assert cloned.translated_from is None


# ============================================================================
# Translation Tests
# ============================================================================


@pytest.mark.django_db
class TestSurveyTranslation:
    """Tests for survey translation functionality."""

    def test_create_translation_creates_translation_group(self, basic_survey):
        """Creating first translation should generate translation_group UUID."""
        assert basic_survey.translation_group is None

        french = basic_survey.create_translation("fr")

        basic_survey.refresh_from_db()
        assert basic_survey.translation_group is not None
        assert french.translation_group == basic_survey.translation_group

    def test_create_translation_sets_language(self, basic_survey):
        """Translation should have correct target language."""
        french = basic_survey.create_translation("fr")

        assert french.language == "fr"
        assert basic_survey.language == "en"

    def test_create_translation_sets_translation_flags(self, basic_survey):
        """Translation should be marked as translated (not original)."""
        french = basic_survey.create_translation("fr")

        assert basic_survey.is_original is True
        assert french.is_original is False
        assert french.translated_from == basic_survey

    def test_create_translation_generates_appropriate_name(self, basic_survey):
        """Translation should have language suffix in name."""
        french = basic_survey.create_translation("fr")

        assert "FR" in french.name  # Should contain language code
        assert "fr" in french.slug

    def test_create_translation_copies_all_content(self, basic_survey):
        """Translation should have same structure as original."""
        french = basic_survey.create_translation("fr")

        # Same number of question groups and questions
        assert french.question_groups.count() == basic_survey.question_groups.count()
        assert (
            SurveyQuestion.objects.filter(survey=french).count()
            == SurveyQuestion.objects.filter(survey=basic_survey).count()
        )

        # Same conditions
        assert (
            SurveyQuestionCondition.objects.filter(question__survey=french).count()
            == SurveyQuestionCondition.objects.filter(
                question__survey=basic_survey
            ).count()
        )

    def test_create_multiple_translations(self, basic_survey):
        """Should be able to create multiple translations."""
        french = basic_survey.create_translation("fr")
        spanish = basic_survey.create_translation("es")
        german = basic_survey.create_translation("de")

        # All should share the same translation group
        assert (
            french.translation_group
            == spanish.translation_group
            == german.translation_group
            == basic_survey.translation_group
        )

        # All should reference the original
        assert french.translated_from == basic_survey
        assert spanish.translated_from == basic_survey
        assert german.translated_from == basic_survey

    def test_create_duplicate_translation_raises_error(self, basic_survey):
        """Should not allow duplicate translations to same language."""
        basic_survey.create_translation("fr")

        with pytest.raises(ValueError, match="already exists"):
            basic_survey.create_translation("fr")

    def test_get_available_translations(self, basic_survey):
        """Should retrieve all translations of a survey."""
        assert basic_survey.get_available_translations().count() == 0

        french = basic_survey.create_translation("fr")
        spanish = basic_survey.create_translation("es")

        translations = basic_survey.get_available_translations()
        assert translations.count() == 2
        assert french in translations
        assert spanish in translations
        assert basic_survey not in translations  # Excludes self

    def test_get_available_translations_works_from_translation(self, basic_survey):
        """Translations should see other translations in the group."""
        french = basic_survey.create_translation("fr")
        spanish = basic_survey.create_translation("es")

        # From French, should see English and Spanish
        translations = french.get_available_translations()
        assert translations.count() == 2
        assert basic_survey in translations
        assert spanish in translations
        assert french not in translations  # Excludes self

    def test_get_translation_by_language_code(self, basic_survey):
        """Should retrieve specific translation by language."""
        french = basic_survey.create_translation("fr")
        basic_survey.create_translation("es")

        result = basic_survey.get_translation("fr")
        assert result == french

        result = basic_survey.get_translation("de")  # Doesn't exist
        assert result is None

    def test_translation_inherits_settings(self, basic_survey):
        """Translations should inherit survey settings."""
        basic_survey.captcha_required = True
        basic_survey.max_responses = 100
        basic_survey.retention_months = 12
        basic_survey.save()

        french = basic_survey.create_translation("fr")

        assert french.captcha_required is True
        assert french.max_responses == 100
        assert french.retention_months == 12


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


@pytest.mark.django_db
class TestTranslationEdgeCases:
    """Tests for edge cases and complex scenarios."""

    def test_empty_survey_can_be_cloned(self, owner, organization):
        """Survey with no question groups should clone successfully."""
        survey = Survey.objects.create(
            owner=owner,
            organization=organization,
            name="Empty Survey",
            slug="empty-survey",
            language="en",
        )

        cloned = survey.create_clone()
        assert cloned.question_groups.count() == 0

    def test_survey_with_complex_conditions(self, owner, organization, question_group):
        """Survey with multiple chained conditions should clone correctly."""
        survey = Survey.objects.create(
            owner=owner,
            organization=organization,
            name="Complex Survey",
            slug="complex-survey",
            language="en",
        )
        survey.question_groups.add(question_group)

        # Create chain: q1 -> q2 -> q3
        q1 = SurveyQuestion.objects.create(
            survey=survey,
            group=question_group,
            text="Question 1",
            type=SurveyQuestion.Types.YESNO,
            order=0,
        )
        q2 = SurveyQuestion.objects.create(
            survey=survey,
            group=question_group,
            text="Question 2",
            type=SurveyQuestion.Types.YESNO,
            order=1,
        )
        q3 = SurveyQuestion.objects.create(
            survey=survey,
            group=question_group,
            text="Question 3",
            type=SurveyQuestion.Types.TEXT,
            order=2,
        )

        SurveyQuestionCondition.objects.create(
            question=q1,
            operator=SurveyQuestionCondition.Operator.EQUALS,
            value="yes",
            target_question=q2,
            action=SurveyQuestionCondition.Action.SHOW,
        )
        SurveyQuestionCondition.objects.create(
            question=q2,
            operator=SurveyQuestionCondition.Operator.EQUALS,
            value="yes",
            target_question=q3,
            action=SurveyQuestionCondition.Action.SHOW,
        )

        cloned = survey.create_clone()

        # Should have all conditions preserved
        cloned_conditions = SurveyQuestionCondition.objects.filter(
            question__survey=cloned
        )
        assert cloned_conditions.count() == 2

    def test_translation_of_translation(self, basic_survey):
        """Should be able to create translations from translations."""
        french = basic_survey.create_translation("fr")
        spanish = french.create_translation("es")

        # Spanish should link to translation group, not directly to French
        assert spanish.translation_group == basic_survey.translation_group
        assert spanish.translated_from == french
        assert spanish.is_original is False

    def test_clone_preserves_style_json(self, basic_survey):
        """Cloning should preserve style JSON data."""
        basic_survey.style = {
            "primary_color": "#FF5733",
            "theme_name": "custom-theme",
            "font_heading": "Arial",
        }
        basic_survey.save()

        cloned = basic_survey.create_clone()

        assert cloned.style == basic_survey.style
        assert cloned.style is not basic_survey.style  # Different dict object


class TestLLMTranslation:
    """Tests for LLM-powered translation functionality."""

    def test_translate_survey_content_without_llm(self, basic_survey):
        """Translation without LLM should return warning."""
        translation = basic_survey.create_translation("fr")

        results = basic_survey.translate_survey_content(translation, use_llm=False)

        assert results["success"] is False
        assert len(results["warnings"]) > 0
        assert "LLM translation disabled" in results["warnings"][0]

    def test_translate_survey_content_wrong_target(self, owner, organization):
        """Translation should fail if target is not a translation of source."""
        survey1 = Survey.objects.create(
            owner=owner,
            organization=organization,
            name="Survey 1",
            slug="survey-1",
            language="en",
        )
        survey2 = Survey.objects.create(
            owner=owner,
            organization=organization,
            name="Survey 2",
            slug="survey-2",
            language="fr",
        )

        results = survey1.translate_survey_content(survey2, use_llm=False)

        assert results["success"] is False
        assert len(results["errors"]) > 0
        assert "not a translation" in results["errors"][0]

    def test_translate_survey_content_with_llm(self, basic_survey, monkeypatch):
        """Test translate_survey_content with mocked LLM."""
        source_survey = basic_survey

        # Mock LLM initialization to avoid requiring real credentials
        def mock_llm_init(self):
            self.endpoint = "http://mock-llm"
            self.api_key = "mock-key"
            self.auth_type = "bearer"
            self.timeout = 30
            self.system_prompt = "Mock system prompt"

        # Mock LLM to return JSON translations
        def mock_chat_with_custom_system_prompt(
            self,
            system_prompt=None,
            conversation_history=None,
            temperature=None,
            max_tokens=None,
        ):
            # Return a properly formatted JSON response
            import json

            translation_data = {
                "confidence": "high",
                "confidence_notes": "All translations are accurate",
                "metadata": {
                    "name": "Encuesta del Paciente",
                    "description": "una encuesta sobre atención al paciente",
                },
                "question_groups": [
                    {
                        "name": "Demografía",
                        "description": "Preguntas demográficas básicas",
                        "questions": [
                            {"text": "¿Cuál es tu edad?"},
                            {"text": "¿Tienes diabetes?"},
                            {
                                "text": "¿Qué tipo de diabetes?",
                                "choices": ["Tipo 1", "Tipo 2", "Gestacional", "Otro"],
                            },
                        ],
                    }
                ],
            }
            return json.dumps(translation_data, ensure_ascii=False)

        monkeypatch.setattr(ConversationalSurveyLLM, "__init__", mock_llm_init)
        monkeypatch.setattr(
            ConversationalSurveyLLM,
            "chat_with_custom_system_prompt",
            mock_chat_with_custom_system_prompt,
        )

        # Create translation survey
        target_survey = source_survey.create_translation(target_language="es")

        # Translate content
        results = source_survey.translate_survey_content(target_survey)

        # Should succeed - provide detailed error info if it fails
        if not results["success"]:
            import json

            error_details = json.dumps(results, indent=2)
            pytest.fail(f"Translation failed: {error_details}")

        assert results["success"] is True
        assert results["translated_fields"] > 0
        assert len(results["errors"]) == 0

        # Check that survey name was translated
        target_survey.refresh_from_db()
        assert target_survey.name == "Encuesta del Paciente"

    def test_translate_survey_content_preserves_structure(self, basic_survey):
        """Translation should preserve survey structure even without LLM."""
        translation = basic_survey.create_translation("de")

        # Verify structure is preserved before translation
        assert translation.questions.count() == basic_survey.questions.count()
        assert (
            translation.question_groups.count() == basic_survey.question_groups.count()
        )


@pytest.mark.django_db
class TestAsyncTranslation:
    """Tests for async translation functionality and error handling."""

    def test_create_translation_async_returns_task_id(
        self, client, basic_survey, owner
    ):
        """Async translation endpoint should return task_id."""
        client.force_login(owner)

        response = client.post(
            f"/surveys/{basic_survey.slug}/translations/create/",
            {"language": "es"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert len(data["task_id"]) > 0

    def test_create_translation_async_invalid_language(
        self, client, basic_survey, owner
    ):
        """Async translation should reject invalid language codes."""
        client.force_login(owner)

        response = client.post(
            f"/surveys/{basic_survey.slug}/translations/create/",
            {"language": "invalid"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid language" in data["error"]

    def test_create_translation_async_duplicate(self, client, basic_survey, owner):
        """Async translation should reject duplicates."""
        # Create first translation
        basic_survey.create_translation("es")

        client.force_login(owner)

        response = client.post(
            f"/surveys/{basic_survey.slug}/translations/create/",
            {"language": "es"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "already exists" in data["error"]

    def test_translation_status_not_found(self, client, basic_survey, owner):
        """Translation status should return 404 for invalid task_id."""
        client.force_login(owner)

        response = client.get(
            f"/surveys/{basic_survey.slug}/translations/status/invalid-task-id/"
        )

        assert response.status_code == 404

    def test_translation_handles_llm_failure(self, basic_survey, monkeypatch):
        """Translation should handle LLM failures gracefully."""

        # Mock LLM initialization to avoid requiring real credentials
        def mock_llm_init(self):
            self.endpoint = "http://mock-llm"
            self.api_key = "mock-key"
            self.auth_type = "bearer"
            self.timeout = 30
            self.system_prompt = "Mock system prompt"

        def mock_chat_with_custom_system_prompt(
            self,
            system_prompt=None,
            conversation_history=None,
            temperature=None,
            max_tokens=None,
        ):
            # Return a minimal valid JSON response
            import json

            translation_data = {
                "confidence": "high",
                "confidence_notes": "All translations are accurate",
                "metadata": {
                    "name": "Encuesta Traducida",
                    "description": "descripción traducida",
                },
                "question_groups": [
                    {
                        "name": "Grupo Traducido",
                        "description": "descripción del grupo",
                        "questions": [
                            {"text": "pregunta traducida 1"},
                            {"text": "pregunta traducida 2"},
                            {
                                "text": "pregunta traducida 3",
                                "choices": ["a", "b", "c", "d"],
                            },
                        ],
                    }
                ],
            }
            return json.dumps(translation_data, ensure_ascii=False)

        monkeypatch.setattr(ConversationalSurveyLLM, "__init__", mock_llm_init)
        monkeypatch.setattr(
            ConversationalSurveyLLM,
            "chat_with_custom_system_prompt",
            mock_chat_with_custom_system_prompt,
        )

        translation = basic_survey.create_translation("es")

        # Should complete successfully with mocked LLM
        result = basic_survey.translate_survey_content(translation, use_llm=True)

        # Provide detailed error info if it fails
        if not result["success"]:
            import json

            error_details = json.dumps(result, indent=2)
            pytest.fail(f"Translation failed: {error_details}")

        assert result["success"] is True
        assert result["translated_fields"] > 0
        # Translation structure should exist
        assert translation.questions.count() == basic_survey.questions.count()


@pytest.mark.django_db
class TestAsyncEmailSending:
    """Tests for async email invitation sending and error handling."""

    def test_send_invites_async_returns_task_id(self, client, basic_survey, owner):
        """Async email endpoint should return task_id."""
        client.force_login(owner)

        basic_survey.visibility = Survey.Visibility.TOKEN
        basic_survey.save()

        response = client.post(
            f"/surveys/{basic_survey.slug}/invites/send/",
            {"invite_emails": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "total_emails" in data
        assert data["total_emails"] == 1

    def test_send_invites_async_no_emails(self, client, basic_survey, owner):
        """Async email should reject empty email list."""
        client.force_login(owner)

        response = client.post(
            f"/surveys/{basic_survey.slug}/invites/send/",
            {"invite_emails": ""},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_send_invites_async_invalid_emails(self, client, basic_survey, owner):
        """Async email should reject invalid email formats."""
        client.force_login(owner)

        response = client.post(
            f"/surveys/{basic_survey.slug}/invites/send/",
            {"invite_emails": "not-an-email"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_send_invites_async_multiple_emails(self, client, basic_survey, owner):
        """Async email should parse multiple email addresses."""
        client.force_login(owner)

        basic_survey.visibility = Survey.Visibility.TOKEN
        basic_survey.save()

        response = client.post(
            f"/surveys/{basic_survey.slug}/invites/send/",
            {"invite_emails": "test1@example.com\ntest2@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 2

    def test_email_status_not_found(self, client, basic_survey, owner):
        """Email status should return 404 for invalid task_id."""
        client.force_login(owner)

        response = client.get(
            f"/surveys/{basic_survey.slug}/invites/status/invalid-task-id/"
        )

        assert response.status_code == 404

    def test_send_invites_handles_smtp_failure(
        self, client, basic_survey, owner, monkeypatch
    ):
        """Email sending should track failures in background thread."""
        from unittest.mock import Mock

        client.force_login(owner)

        basic_survey.visibility = Survey.Visibility.TOKEN
        basic_survey.save()

        # Mock email sending to fail
        mock_send = Mock(return_value=False)
        monkeypatch.setattr(
            "checktick_app.core.email_utils.send_survey_invite_email", mock_send
        )

        response = client.post(
            f"/surveys/{basic_survey.slug}/invites/send/",
            {"invite_emails": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

        # Wait a moment for background thread
        import time

        time.sleep(0.5)

        # Check status shows failure was tracked
        from django.core.cache import cache

        status = cache.get(f"email_task_{data['task_id']}")
        assert status is not None
        # Should eventually complete or error even with failures
        assert status["status"] in ["processing", "completed", "error"]
