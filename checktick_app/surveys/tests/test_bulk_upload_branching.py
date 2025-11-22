import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import (
    CollectionDefinition,
    CollectionItem,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)
from checktick_app.surveys.views import _bulk_upload_example_md

TEST_PASSWORD = "x"

BULK_MD = textwrap.dedent(
    """
    # Intro {intro}
    Introduction copy

    ## Accept terms {intro-accept}
    (text)
    ? when equals "No" -> {intro-decline}

    ## Decline reason {intro-decline}
    (text)

    # Follow up {follow-up}
    Next steps

    ## Feedback {follow-up-feedback}
    (text)
    """
).strip()


@pytest.mark.django_db
def test_parse_bulk_markdown_supports_ids_and_branches():
    groups = parse_bulk_markdown(BULK_MD)
    assert len(groups) == 2

    intro = groups[0]
    assert intro["ref"] == "intro"
    assert intro["questions"][0]["ref"] == "intro-accept"
    branches = intro["questions"][0]["branches"]
    # Only one branch parsed now (question branching only)
    assert len(branches) >= 1

    # Check the question branch
    to_question = next((b for b in branches if b["target_ref"] == "intro-decline"), None)
    if to_question:
        assert to_question["target_type"] == "question"
        assert to_question["operator"] == SurveyQuestionCondition.Operator.EQUALS
        assert to_question["value"] == "No"


@pytest.mark.django_db
def test_bulk_upload_creates_branch_conditions(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="Bulk", slug="bulk")

    client.login(username="author", password=TEST_PASSWORD)

    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": BULK_MD},
        follow=False,
    )
    assert response.status_code == 302

    conditions = SurveyQuestionCondition.objects.filter(question__survey=survey)
    # Only one condition now (question-to-question), group branching removed
    assert conditions.count() == 1

    cond_to_question = conditions.filter(target_question__isnull=False).get()
    assert cond_to_question.target_question.text == "Decline reason"
    assert cond_to_question.operator == SurveyQuestionCondition.Operator.EQUALS
    assert cond_to_question.value == "No"
    # Only one condition now after removing group branching
    assert cond_to_question.order == 0


@pytest.mark.django_db
def test_bulk_upload_replaces_existing_content(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="Bulk", slug="bulk")
    other_survey = Survey.objects.create(owner=user, name="Other", slug="other")

    exclusive_group = QuestionGroup.objects.create(name="Exclusive", owner=user)
    shared_group = QuestionGroup.objects.create(name="Shared", owner=user, shared=True)
    multi_use_group = QuestionGroup.objects.create(name="Multi", owner=user)

    survey.question_groups.add(exclusive_group, shared_group, multi_use_group)
    other_survey.question_groups.add(multi_use_group)

    old_question = SurveyQuestion.objects.create(
        survey=survey,
        group=exclusive_group,
        text="Old question",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )

    definition = CollectionDefinition.objects.create(
        survey=survey,
        key="old",
        name="Old collection",
    )
    CollectionItem.objects.create(
        collection=definition,
        item_type=CollectionItem.ItemType.GROUP,
        group=exclusive_group,
        order=0,
    )

    client.login(username="author", password=TEST_PASSWORD)

    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": BULK_MD},
        follow=False,
    )
    assert response.status_code == 302

    survey.refresh_from_db()

    assert not SurveyQuestion.objects.filter(id=old_question.id).exists()
    assert SurveyQuestion.objects.filter(survey=survey).count() == 3

    assert not CollectionDefinition.objects.filter(id=definition.id).exists()
    assert survey.collections.count() == 0

    new_group_names = {g.name for g in survey.question_groups.all()}
    assert new_group_names == {"Intro", "Follow up"}

    assert not QuestionGroup.objects.filter(id=exclusive_group.id).exists()

    refreshed_shared = QuestionGroup.objects.get(id=shared_group.id)
    assert refreshed_shared.shared is True
    assert not refreshed_shared.surveys.filter(id=survey.id).exists()

    refreshed_multi = QuestionGroup.objects.get(id=multi_use_group.id)
    assert refreshed_multi.surveys.filter(id=other_survey.id).exists()
    assert not refreshed_multi.surveys.filter(id=survey.id).exists()


@pytest.mark.django_db
def test_bulk_upload_example_markdown_imports(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="Example", slug="example")

    client.login(username="author", password=TEST_PASSWORD)

    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": _bulk_upload_example_md()},
        follow=False,
    )
    assert response.status_code == 302

    survey.refresh_from_db()
    assert (
        survey.questions.count() == 6
    )  # Updated from 5 to 6 after adding follow-up examples
    assert survey.question_groups.count() == 3
