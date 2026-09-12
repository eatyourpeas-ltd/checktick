"""Tests for the section menu picker page + selection filter (step 5).

Step 5 wires up the participant-facing picker:
- When layout=section_menu and no selection is stored, the take view
  renders the picker template instead of the question list.
- POST action=select_sections stores the chosen (+ mandatory) group IDs
  on SurveyProgress.selected_group_ids and re-renders with the filtered
  question list.
- _resolved_group_order_ids filters by selected_group_ids.
- On resume (selected_group_ids populated), the picker is skipped.
- action=change_sections clears the selection and returns to the picker.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    SectionMenuItem,
    Survey,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable rate limiting for all tests in this module."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def section_menu_survey(owner, org):
    """A published section_menu survey with 3 sections + a configured menu.

    Demographics: mandatory
    Medical: pickable
    Lifestyle: pickable
    """
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Menu Survey",
        slug="menu-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.SECTION_MENU,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Medical", owner=owner)
    g3 = QuestionGroup.objects.create(name="Lifestyle", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Condition", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="Exercise", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = SectionMenu.objects.create(survey=s, min_selected=1, max_selected=2)
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, is_pickable=True, order=2)
    SectionMenuItem.objects.create(menu=menu, group=g3, is_pickable=True, order=3)
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- _resolved_group_order_ids filter ---


@pytest.mark.django_db
def test_resolved_group_order_ids_filters_by_selection(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="S", slug="s-filter")
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    g3 = QuestionGroup.objects.create(name="C", owner=owner)
    s.question_groups.add(g1, g2, g3)
    from checktick_app.surveys.views import _resolved_group_order_ids

    full = _resolved_group_order_ids(s)
    assert set(full) == {g1.id, g2.id, g3.id}
    filtered = _resolved_group_order_ids(s, [g2.id, g3.id])
    assert filtered == [g2.id, g3.id]
    # Order preserved from authored order
    assert g2.id in filtered and g1.id not in filtered


@pytest.mark.django_db
def test_resolved_group_order_ids_none_selection_returns_all(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="S", slug="s-none")
    g = QuestionGroup.objects.create(name="A", owner=owner)
    s.question_groups.add(g)
    from checktick_app.surveys.views import _resolved_group_order_ids

    assert _resolved_group_order_ids(s, None) == [g.id]


# --- Picker rendering ---


@pytest.mark.django_db
def test_picker_renders_when_no_selection(client, section_menu_survey, participant):
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Choose sections" in html or "section-picker" in html
    # Mandatory section shown as included
    assert "Demographics" in html
    # Pickable sections shown as checkboxes
    assert "Medical" in html
    assert "Lifestyle" in html


@pytest.mark.django_db
def test_picker_skipped_when_selection_exists(client, section_menu_survey, participant):
    """On resume (selected_group_ids populated), go straight to questions."""
    SurveyProgress.objects.create(
        survey=section_menu_survey,
        user=participant,
        selected_group_ids=[section_menu_survey._g1.id, section_menu_survey._g2.id],
        total_questions=section_menu_survey.questions.count(),
        expires_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        + __import__("datetime").timedelta(days=30),
    )
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # Question text from selected sections appears
    assert "Age" in html  # g1 (mandatory, always included)
    assert "Condition" in html  # g2 (selected)
    # Non-selected section's question does NOT appear
    assert "Exercise" not in html  # g3 (not selected)
    # Picker not shown
    assert "section-picker-form" not in html


# --- select_sections POST ---


@pytest.mark.django_db
def test_select_sections_stores_selection(client, section_menu_survey, participant):
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.post(
        url,
        {
            "action": "select_sections",
            "selected_groups": [str(section_menu_survey._g2.id)],
        },
    )
    assert res.status_code == 302
    progress = SurveyProgress.objects.get(survey=section_menu_survey, user=participant)
    # Mandatory g1 unioned in
    assert section_menu_survey._g1.id in progress.selected_group_ids
    assert section_menu_survey._g2.id in progress.selected_group_ids
    # g3 not selected
    assert section_menu_survey._g3.id not in progress.selected_group_ids


@pytest.mark.django_db
def test_select_sections_below_min_errors(client, section_menu_survey, participant):
    """min_selected=1, selecting 0 pickable sections should error."""
    section_menu_survey.section_menu.min_selected = 1
    section_menu_survey.section_menu.save(update_fields=["min_selected"])
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.post(
        url, {"action": "select_sections", "selected_groups": []}, follow=True
    )
    assert res.status_code == 200
    # Validation failed: selected_group_ids must NOT be set (picker re-renders).
    progress = SurveyProgress.objects.filter(
        survey=section_menu_survey, user=participant
    ).first()
    assert progress is not None
    assert progress.selected_group_ids == []
    messages = list(res.context["messages"])
    assert any("at least" in str(m) for m in messages)


@pytest.mark.django_db
def test_select_sections_above_max_errors(client, section_menu_survey, participant):
    """max_selected=2, selecting 3 pickable (only 2 exist) — select both, that's ok.
    Set max=1 and select 2 to trigger the error."""
    section_menu_survey.section_menu.max_selected = 1
    section_menu_survey.section_menu.save(update_fields=["max_selected"])
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.post(
        url,
        {
            "action": "select_sections",
            "selected_groups": [
                str(section_menu_survey._g2.id),
                str(section_menu_survey._g3.id),
            ],
        },
        follow=True,
    )
    assert res.status_code == 200
    messages = list(res.context["messages"])
    assert any("at most" in str(m) for m in messages)


@pytest.mark.django_db
def test_select_sections_then_renders_filtered_questions(
    client, section_menu_survey, participant
):
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    # POST selection
    client.post(
        url,
        {
            "action": "select_sections",
            "selected_groups": [str(section_menu_survey._g3.id)],
        },
    )
    # GET should now show filtered questions
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html  # mandatory g1
    assert "Exercise" in html  # selected g3
    assert "Condition" not in html  # g2 not selected


@pytest.mark.django_db
def test_change_sections_clears_selection(client, section_menu_survey, participant):
    """action=change_sections clears selected_group_ids and returns to picker."""
    from datetime import timedelta

    from django.utils import timezone

    SurveyProgress.objects.create(
        survey=section_menu_survey,
        user=participant,
        selected_group_ids=[section_menu_survey._g1.id, section_menu_survey._g2.id],
        total_questions=section_menu_survey.questions.count(),
        expires_at=timezone.now() + timedelta(days=30),
    )
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.post(url, {"action": "change_sections"}, follow=True)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=section_menu_survey, user=participant)
    assert progress.selected_group_ids == []
    # Picker re-rendered
    html = res.content.decode()
    assert "section-picker-form" in html


@pytest.mark.django_db
def test_linear_survey_never_shows_picker(client, owner, org, participant):
    """A linear survey never renders the picker, even with weird state."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-s",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT
    )
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "section-picker-form" not in html
    assert "Q" in html


@pytest.mark.django_db
def test_select_sections_participant_order_mode(
    client, section_menu_survey, participant
):
    """order_mode=participant preserves tick order for pickable sections."""
    section_menu_survey.section_menu.order_mode = "participant"
    section_menu_survey.section_menu.save(update_fields=["order_mode"])
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    # Tick g3 before g2
    res = client.post(
        url,
        {
            "action": "select_sections",
            "selected_groups": [
                str(section_menu_survey._g3.id),
                str(section_menu_survey._g2.id),
            ],
        },
    )
    assert res.status_code == 302
    progress = SurveyProgress.objects.get(survey=section_menu_survey, user=participant)
    ids = progress.selected_group_ids
    # Mandatory (g1) first, then pickable in tick order (g3, g2)
    assert ids[0] == section_menu_survey._g1.id
    assert ids[1] == section_menu_survey._g3.id
    assert ids[2] == section_menu_survey._g2.id


@pytest.mark.django_db
def test_change_sections_link_in_progress_bar(client, section_menu_survey, participant):
    """The detail page shows a 'Change sections' link for section_menu surveys."""
    from datetime import timedelta

    from django.utils import timezone

    SurveyProgress.objects.create(
        survey=section_menu_survey,
        user=participant,
        selected_group_ids=[section_menu_survey._g1.id, section_menu_survey._g2.id],
        total_questions=section_menu_survey.questions.count(),
        expires_at=timezone.now() + timedelta(days=30),
    )
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": section_menu_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Change sections" in html
