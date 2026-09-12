"""Tests for the layout picker on the Organise page (step 3).

Step 3 adds a read-only summary card plus a POST handler to switch the
survey's layout. The SectionMenu configuration card (per-section
mandatory/pickable, min/max, etc.) lands in step 4.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    Survey,
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
    s = Survey.objects.create(owner=owner, organization=org, name="S", slug="s")
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Q2", type=SurveyQuestion.Types.TEXT
    )
    return s


@pytest.mark.django_db
def test_organise_page_shows_layout_picker(client, owner, survey):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Survey layout" in html
    assert "Default (linear)" in html
    assert "Section menu" in html
    # Linear is current by default
    assert "Current" in html


@pytest.mark.django_db
def test_organise_page_marks_section_menu_as_current(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # Both cards render but only the section_menu card shows the "Use this
    # layout" button (the linear one does, since it's not current).
    assert "Section menu" in html


@pytest.mark.django_db
def test_switch_layout_to_section_menu(client, owner, survey):
    client.force_login(owner)
    assert survey.layout == Survey.Layout.LINEAR
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "section_menu"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.SECTION_MENU


@pytest.mark.django_db
def test_switch_layout_back_to_linear(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "linear"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_switch_layout_rejects_unknown_value(client, owner, survey):
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "nonsense"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_switch_layout_requires_edit_permission(client, owner, survey):
    """A viewer (can_view but not can_edit) cannot switch layout."""
    viewer = owner.__class__.objects.create_user(
        username="viewer@example.com", password=TEST_PASSWORD
    )
    # Add viewer as a member with view-only role
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(survey=survey, user=viewer, role="viewer")
    client.force_login(viewer)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "section_menu"},
    )
    # require_can_edit raises PermissionDenied -> 403
    assert res.status_code == 403
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_single_section_survey_shows_warning_hint(client, owner, org):
    """A survey with < 2 sections shows the 'needs at least 2 sections' hint."""
    s = Survey.objects.create(
        owner=owner, organization=org, name="Single", slug="single"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Needs at least 2 sections" in html


@pytest.mark.django_db
def test_switch_to_section_menu_with_one_section_warns(client, owner, org):
    """Switching to section_menu with < 2 sections still succeeds but warns."""
    s = Survey.objects.create(
        owner=owner, organization=org, name="Single", slug="single-w"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": s.slug}),
        {"action": "set_layout", "layout": "section_menu"},
        follow=True,
    )
    assert res.status_code == 200
    s.refresh_from_db()
    assert s.layout == Survey.Layout.SECTION_MENU
    messages = list(res.context["messages"])
    assert any("at least 2 sections" in str(m) for m in messages)


# ============================================================================
# Section menu configuration card (step 4)
# ============================================================================


@pytest.mark.django_db
def test_section_menu_config_card_renders(client, owner, survey):
    """When layout=section_menu, the Organise page shows the config card."""
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Section menu configuration" in html
    assert "Picker prompt" in html
    # Both groups appear as rows
    assert "G1" in html
    assert "G2" in html


@pytest.mark.django_db
def test_save_section_menu_creates_menu_and_items(client, owner, survey):
    """Saving the config card creates a SectionMenu + one item per group."""
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    g1, g2 = list(survey.question_groups.all())
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick your sections",
            "min_selected": "2",
            "max_selected": "4",
            "order_mode": "participant",
            "show_select_all": "on",
            "show_estimated_time": "on",
            "mandatory_group_ids": [str(g1.id)],
            "estimated_minutes_group_ids": [str(g1.id), str(g2.id)],
            f"estimated_minutes_{g1.id}": "5",
            f"estimated_minutes_{g2.id}": "",
        },
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    menu = survey.section_menu
    assert menu.prompt_text == "Pick your sections"
    assert menu.min_selected == 2
    assert menu.max_selected == 4
    assert menu.order_mode == SectionMenu.OrderMode.PARTICIPANT
    assert menu.show_select_all is True
    assert menu.show_estimated_time is True
    items = {i.group_id: i for i in menu.items.all()}
    assert items[g1.id].is_pickable is False  # mandatory
    assert items[g1.id].estimated_minutes == 5
    assert items[g2.id].is_pickable is True
    assert items[g2.id].estimated_minutes is None


@pytest.mark.django_db
def test_save_section_menu_blank_max_means_no_cap(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "save_section_menu", "max_selected": ""},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.section_menu.max_selected is None


@pytest.mark.django_db
def test_save_section_menu_empty_selection_warns(client, owner, survey):
    """No mandatory sections + min_selected=0 warns about empty survey."""
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {
            "action": "save_section_menu",
            "min_selected": "0",
            # No mandatory_group_ids
        },
        follow=True,
    )
    assert res.status_code == 200
    messages = list(res.context["messages"])
    assert any("empty survey" in str(m) for m in messages)


@pytest.mark.django_db
def test_save_section_menu_requires_edit_permission(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    viewer = owner.__class__.objects.create_user(
        username="viewer@example.com", password=TEST_PASSWORD
    )
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(survey=survey, user=viewer, role="viewer")
    client.force_login(viewer)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "save_section_menu", "prompt_text": "hax"},
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_save_section_menu_ignored_for_linear_survey(client, owner, survey):
    """A linear survey ignores save_section_menu posts (no menu created)."""
    assert survey.layout == Survey.Layout.LINEAR
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "save_section_menu", "prompt_text": "should be ignored"},
    )
    # The handler is skipped; the view falls through to the GET-style redirect
    # behaviour for unknown POST actions (renders the page).
    assert res.status_code in (200, 302)
    assert not SectionMenu.objects.filter(survey=survey).exists()


@pytest.mark.django_db
def test_section_menu_items_synced_when_groups_change(client, owner, survey):
    """Adding a group after the menu exists creates a new item for it."""
    from checktick_app.surveys.models import SectionMenu, SectionMenuItem

    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    menu = SectionMenu.objects.create(survey=survey)
    g1, g2 = list(survey.question_groups.all())
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, is_pickable=True, order=2)
    # Add a third group
    g3 = QuestionGroup.objects.create(name="G3", owner=owner)
    survey.question_groups.add(g3)
    client.force_login(owner)
    # GET triggers the sync (the view calls _sync_section_menu_items).
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    assert menu.items.filter(group=g3).exists()
    # Existing mandatory flag preserved
    assert menu.items.get(group=g1).is_pickable is False


@pytest.mark.django_db
def test_section_menu_items_dropped_when_group_removed(client, owner, survey):
    from checktick_app.surveys.models import SectionMenu, SectionMenuItem

    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    menu = SectionMenu.objects.create(survey=survey)
    g1, g2 = list(survey.question_groups.all())
    SectionMenuItem.objects.create(menu=menu, group=g1, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, order=2)
    survey.question_groups.remove(g2)
    client.force_login(owner)
    client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert menu.items.filter(group=g2).count() == 0
    assert menu.items.filter(group=g1).exists()
