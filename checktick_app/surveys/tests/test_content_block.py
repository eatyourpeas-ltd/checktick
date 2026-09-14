"""Tests for the content_block question type — model and validation.

See docs/survey-layouts-technical.md §Content blocks.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import pytest

from checktick_app.surveys.models import Survey, SurveyQuestion


@pytest.mark.django_db
def test_content_block_type_exists():
    """The CONTENT_BLOCK choice is present on SurveyQuestion.Types."""
    assert "content_block" in dict(SurveyQuestion.Types.choices).keys()
    assert SurveyQuestion.Types.CONTENT_BLOCK == "content_block"


@pytest.mark.django_db
def test_content_block_clean_rejects_required_true():
    """A content_block with required=True must fail validation."""
    User = get_user_model()
    user = User.objects.create_user(username="author", password="x")
    survey = Survey.objects.create(owner=user, name="CB", slug="cb")
    q = SurveyQuestion(
        survey=survey,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Hello"},
        required=True,
    )
    with pytest.raises(ValidationError) as exc:
        q.clean()
    assert "required" in exc.value.message_dict


@pytest.mark.django_db
def test_content_block_clean_accepts_required_false():
    """A content_block with required=False passes validation."""
    User = get_user_model()
    user = User.objects.create_user(username="author2", password="x")
    survey = Survey.objects.create(owner=user, name="CB2", slug="cb2")
    q = SurveyQuestion(
        survey=survey,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Hello"},
        required=False,
    )
    q.clean()  # should not raise


@pytest.mark.django_db
def test_content_block_default_required_is_false():
    """A newly created content_block question defaults to required=False."""
    User = get_user_model()
    user = User.objects.create_user(username="author3", password="x")
    survey = Survey.objects.create(owner=user, name="CB3", slug="cb3")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Intro",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Welcome"},
    )
    assert q.required is False
