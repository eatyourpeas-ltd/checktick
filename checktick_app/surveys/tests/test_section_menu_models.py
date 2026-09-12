"""Tests for SectionMenu / SectionMenuItem models (step 4).

Step 4 adds the data model only. The picker page (step 5) and the
configuration card editor (also step 4's UI side, but the model
contract is what matters here) build on top of these.
"""

import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    SectionMenuItem,
    Survey,
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
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
        layout=Survey.Layout.SECTION_MENU,
    )
    return s


@pytest.mark.django_db
def test_section_menu_defaults(survey):
    menu = SectionMenu.objects.create(survey=survey)
    assert menu.prompt_text == "Which sections would you like to complete?"
    assert menu.min_selected == 1
    assert menu.max_selected is None
    assert menu.order_mode == SectionMenu.OrderMode.AUTHORED
    assert menu.show_select_all is False
    assert menu.show_estimated_time is False


@pytest.mark.django_db
def test_section_menu_one_to_one(survey):
    SectionMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        SectionMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_section_menu_item_defaults(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g = QuestionGroup.objects.create(name="G", owner=owner)
    item = SectionMenuItem.objects.create(menu=menu, group=g)
    assert item.is_pickable is True
    assert item.order == 0
    assert item.estimated_minutes is None


@pytest.mark.django_db
def test_section_menu_item_unique_per_menu(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g = QuestionGroup.objects.create(name="G", owner=owner)
    SectionMenuItem.objects.create(menu=menu, group=g)
    with pytest.raises(Exception):
        SectionMenuItem.objects.create(menu=menu, group=g)


@pytest.mark.django_db
def test_section_menu_item_can_be_mandatory(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g = QuestionGroup.objects.create(name="Consent", owner=owner)
    item = SectionMenuItem.objects.create(menu=menu, group=g, is_pickable=False)
    assert item.is_pickable is False


@pytest.mark.django_db
def test_section_menu_item_ordering(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g1 = QuestionGroup.objects.create(name="B", owner=owner)
    g2 = QuestionGroup.objects.create(name="A", owner=owner)
    g3 = QuestionGroup.objects.create(name="C", owner=owner)
    SectionMenuItem.objects.create(menu=menu, group=g1, order=2)
    SectionMenuItem.objects.create(menu=menu, group=g2, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g3, order=3)
    ordered = list(menu.items.all())
    assert [i.group.name for i in ordered] == ["A", "B", "C"]


@pytest.mark.django_db
def test_section_menu_cascade_delete_with_survey(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g = QuestionGroup.objects.create(name="G", owner=owner)
    SectionMenuItem.objects.create(menu=menu, group=g)
    menu_id = menu.id
    item_id = menu.items.first().id
    survey.delete()
    assert not SectionMenu.objects.filter(id=menu_id).exists()
    assert not SectionMenuItem.objects.filter(id=item_id).exists()


@pytest.mark.django_db
def test_section_menu_str(survey):
    menu = SectionMenu.objects.create(survey=survey)
    assert "SectionMenu for S" in str(menu)


@pytest.mark.django_db
def test_section_menu_item_str(survey, owner):
    menu = SectionMenu.objects.create(survey=survey)
    g = QuestionGroup.objects.create(name="Demographics", owner=owner)
    item = SectionMenuItem.objects.create(menu=menu, group=g, is_pickable=False)
    assert "Demographics" in str(item)
    assert "mandatory" in str(item)


@pytest.mark.django_db
def test_linear_survey_has_no_section_menu(owner, org):
    """A linear survey has no SectionMenu row by convention."""
    s = Survey.objects.create(owner=owner, organization=org, name="L", slug="l")
    assert not hasattr(s, "section_menu") or s.section_menu is None
    assert not SectionMenu.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_admin_registration():
    """The models are registered in admin (smoke test via admin.site)."""
    from django.contrib import admin

    assert SectionMenu in admin.site._registry
    assert SectionMenuItem in admin.site._registry
