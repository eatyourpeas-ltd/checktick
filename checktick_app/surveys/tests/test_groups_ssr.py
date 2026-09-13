from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)


def _setup_survey_with_groups(owner, layout=Survey.Layout.LINEAR, n_groups=2):
    """Create a survey with the given layout and n question groups."""
    org = Organization.objects.create(name="Org", owner=owner)
    survey = Survey.objects.create(
        owner=owner, organization=org, name="S", slug=f"s-{layout}-{owner.username}"
    )
    survey.layout = layout
    survey.save(update_fields=["layout"])
    groups = []
    for i in range(n_groups):
        g = QuestionGroup.objects.create(name=f"G{i + 1}", owner=owner)
        survey.question_groups.add(g)
        groups.append(g)
    return survey, groups


@pytest.mark.django_db
@pytest.mark.parametrize(
    "layout",
    [Survey.Layout.LINEAR, Survey.Layout.SECTION_MENU, Survey.Layout.RCT],
)
def test_groups_page_has_sections_heading(client, layout):
    """The Organise page must have a 'Sections' heading so the page reads as
    two clear parts: layout (survey-wide) and sections (multi-section ops)."""
    owner = User.objects.create_user(username=f"heading-{layout}", password="x")
    survey, _ = _setup_survey_with_groups(owner, layout=layout, n_groups=2)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert 'id="sections-heading"' in html
    # The heading text "Sections" should be present (translatable label)
    assert "Sections" in html


@pytest.mark.django_db
def test_groups_page_intro_frames_purpose(client):
    """The intro should frame the page's purpose (survey-wide settings +
    Question Bank), not just list operations."""
    owner = User.objects.create_user(username="intro-owner", password="x")
    survey, _ = _setup_survey_with_groups(owner, layout=Survey.Layout.LINEAR)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Question Bank" in html
    assert "survey-wide" in html or "survey-wide settings" in html


@pytest.mark.django_db
def test_groups_page_share_button_not_publish(client):
    """The toolbar button should say 'Publish to Question Bank' (qualified by
    'to Question Bank' so it doesn't clash with publishing the survey).
    There should be no per-row 'Publish' or 'Share' button."""
    owner = User.objects.create_user(username="share-btn-owner", password="x")
    survey, groups = _setup_survey_with_groups(owner, layout=Survey.Layout.LINEAR)
    # Need a question so the group is publishable
    SurveyQuestion.objects.create(
        survey=survey, group=groups[0], text="Q1", type=SurveyQuestion.Types.TEXT
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # The toolbar button should be present and disabled by default
    assert 'id="publish-to-bank-btn"' in html
    assert "Publish to Question Bank" in html
    # The old per-row "Publish as template" title should not appear
    assert "Publish as template" not in html
    # The old per-row "Share" button should not appear
    assert ">Share<" not in html


@pytest.mark.django_db
def test_groups_page_repeat_tip_near_sections(client):
    """The repeat tip ('Select one section...') should appear inside the
    Sections area, not above the layout picker."""
    owner = User.objects.create_user(username="tip-owner", password="x")
    survey, _ = _setup_survey_with_groups(owner, layout=Survey.Layout.LINEAR)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # The repeat tip text should be present
    assert "Select one section to repeat" in html
    # It should appear AFTER the sections-heading, not before the layout picker
    sections_pos = html.find('id="sections-heading"')
    tip_pos = html.find("Select one section to repeat")
    assert sections_pos > -1 and tip_pos > -1
    assert tip_pos > sections_pos, "Repeat tip should be inside the Sections area"


@pytest.mark.django_db
def test_groups_page_sections_signpost(client):
    """The Sections area should have a signpost explaining it's for
    multi-section operations, with a Builder link for single-section work."""
    owner = User.objects.create_user(username="signpost-owner", password="x")
    survey, _ = _setup_survey_with_groups(owner, layout=Survey.Layout.LINEAR)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Multi-section operations" in html


@pytest.mark.django_db
def test_groups_page_renders_with_counts(client):
    # Setup org, survey, owner
    owner = User.objects.create_user(username="owner", password="x")
    org = Organization.objects.create(name="Org", owner=owner)
    survey = Survey.objects.create(owner=owner, organization=org, name="S", slug="s")
    # Create groups and attach questions to count
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    survey.question_groups.add(g1, g2)
    # Create minimal questions linked to survey and groups
    SurveyQuestion.objects.create(
        survey=survey, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT
    )
    SurveyQuestion.objects.create(
        survey=survey, group=g1, text="Q2", type=SurveyQuestion.Types.TEXT
    )
    SurveyQuestion.objects.create(
        survey=survey, group=g2, text="Q3", type=SurveyQuestion.Types.TEXT
    )

    # Owner should see the groups page with counts 2 and 1
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "2 question" in html
    assert "1 question" in html
    # Ensure drag handle present for editor
    assert "drag-handle" in html
