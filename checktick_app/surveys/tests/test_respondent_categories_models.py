"""Tests for RespondentCategory / RespondentAssignment models + the
category_values field on SurveyAccessToken + the required_categories
fields on QuestionGroup and SurveyQuestion (commit 1 of respondent
categories).

The resolution logic (commit 2) and runtime hook (commit 3) build on top
of these.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentAssignment,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
    )


# --- RespondentCategory -------------------------------------------------


@pytest.mark.django_db
def test_respondent_category_defaults(survey):
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor", "patient"],
    )
    assert cat.resolution_source == RespondentCategory.ResolutionSource.TOKEN
    assert cat.label == ""
    assert cat.source_question is None
    assert cat.profile_field == ""
    assert cat.order == 0


@pytest.mark.django_db
def test_respondent_category_unique_per_survey(survey):
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=["peer"]
    )
    with pytest.raises(Exception):
        RespondentCategory.objects.create(
            survey=survey, name="rater_role", allowed_values=["supervisor"]
        )


@pytest.mark.django_db
def test_respondent_category_same_name_different_survey(survey, owner, org):
    """The same dimension name is allowed across different surveys."""
    other = Survey.objects.create(
        owner=owner, organization=org, name="Other", slug="other"
    )
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=["peer"]
    )
    # No collision — different survey.
    RespondentCategory.objects.create(
        survey=other, name="rater_role", allowed_values=["supervisor"]
    )


@pytest.mark.django_db
def test_respondent_category_cascade_delete_with_survey(survey):
    cat = RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=["peer"]
    )
    cat_id = cat.id
    survey.delete()
    assert not RespondentCategory.objects.filter(id=cat_id).exists()


@pytest.mark.django_db
def test_respondent_category_ordering(survey):
    RespondentCategory.objects.create(
        survey=survey, name="site", allowed_values=[], order=2
    )
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=[], order=1
    )
    RespondentCategory.objects.create(
        survey=survey, name="cohort", allowed_values=[], order=3
    )
    ordered = list(survey.respondent_categories.all())
    assert [c.name for c in ordered] == ["rater_role", "site", "cohort"]


@pytest.mark.django_db
def test_respondent_category_str(survey):
    cat = RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=["peer"]
    )
    assert "rater_role" in str(cat)
    assert "S" in str(cat)


# --- RespondentAssignment -----------------------------------------------


@pytest.fixture
def rater_role_category(survey):
    return RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor", "patient"],
    )


@pytest.fixture
def progress(survey):
    return SurveyProgress.objects.create(
        survey=survey,
        expires_at=timezone.now() + timedelta(days=30),
    )


@pytest.mark.django_db
def test_respondent_assignment_defaults(progress, rater_role_category):
    assignment = RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    assert assignment.value == "peer"


@pytest.mark.django_db
def test_respondent_assignment_unique_per_progress_and_category(
    progress, rater_role_category
):
    RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    with pytest.raises(Exception):
        RespondentAssignment.objects.create(
            progress=progress, category=rater_role_category, value="supervisor"
        )


@pytest.mark.django_db
def test_respondent_assignment_multiple_dimensions(
    progress, rater_role_category, survey
):
    """A progress record can have one assignment per dimension."""
    subject_cat = RespondentCategory.objects.create(
        survey=survey,
        name="subject",
        allowed_values=["self"],
        resolution_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    RespondentAssignment.objects.create(
        progress=progress, category=subject_cat, value="self"
    )
    assert progress.category_assignments.count() == 2


@pytest.mark.django_db
def test_respondent_assignment_cascade_delete_with_progress(
    progress, rater_role_category
):
    assignment = RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    assignment_id = assignment.id
    progress.delete()
    assert not RespondentAssignment.objects.filter(id=assignment_id).exists()


@pytest.mark.django_db
def test_respondent_assignment_cascade_delete_with_category(
    progress, rater_role_category
):
    assignment = RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    assignment_id = assignment.id
    rater_role_category.delete()
    assert not RespondentAssignment.objects.filter(id=assignment_id).exists()


@pytest.mark.django_db
def test_respondent_assignment_str(progress, rater_role_category):
    assignment = RespondentAssignment.objects.create(
        progress=progress, category=rater_role_category, value="peer"
    )
    s = str(assignment)
    assert "rater_role" in s
    assert "peer" in s


# --- SurveyAccessToken.category_values ---------------------------------


@pytest.fixture
def access_token(survey, owner):
    return SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-abc",
        created_by=owner,
    )


@pytest.mark.django_db
def test_access_token_category_values_default_empty(access_token):
    assert access_token.category_values == {}


@pytest.mark.django_db
def test_access_token_category_values_stores_dim_map(survey, owner):
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    token.refresh_from_db()
    assert token.category_values == {"rater_role": "peer"}


# --- QuestionGroup.required_categories ---------------------------------


@pytest.fixture
def group(owner):
    return QuestionGroup.objects.create(name="G1", owner=owner)


@pytest.mark.django_db
def test_question_group_required_categories_default_empty(group):
    assert group.required_categories == {}


@pytest.mark.django_db
def test_question_group_required_categories_stores_rules(group):
    group.required_categories = {"rater_role": ["peer", "supervisor"]}
    group.save()
    group.refresh_from_db()
    assert group.required_categories == {"rater_role": ["peer", "supervisor"]}


# --- SurveyQuestion.required_categories --------------------------------


@pytest.fixture
def question(survey):
    return SurveyQuestion.objects.create(
        survey=survey,
        text="Q1",
        type=SurveyQuestion.Types.TEXT,
    )


@pytest.mark.django_db
def test_survey_question_required_categories_default_empty(question):
    assert question.required_categories == {}


@pytest.mark.django_db
def test_survey_question_required_categories_stores_rules(question):
    question.required_categories = {"rater_role": ["self"]}
    question.save()
    question.refresh_from_db()
    assert question.required_categories == {"rater_role": ["self"]}


# --- No-op for surveys without categories ------------------------------


@pytest.mark.django_db
def test_survey_without_categories_has_no_respondent_categories(survey):
    assert survey.respondent_categories.count() == 0
