"""Tests for the respondent categories Organise page UI (commit 4).

Covers the categories configuration card: add/edit/remove dimensions,
the section visibility table (required_categories per group), and the
sync-on-visit behaviour.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


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
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g2,
        text="Clinical knowledge",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    s._g1, s._g2 = g1, g2
    return s


def _groups_url(survey):
    return reverse("surveys:groups", kwargs={"slug": survey.slug})


# --- Card visibility --------------------------------------------------


@pytest.mark.django_db
def test_categories_card_shown_when_can_edit(client, survey, owner):
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Respondent categories" in html


@pytest.mark.django_db
def test_categories_card_shows_empty_state(client, survey, owner):
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    html = res.content.decode()
    assert "No category dimensions yet" in html


# --- Add dimension ----------------------------------------------------


@pytest.mark.django_db
def test_add_dimension_creates_category(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {"action": "add_respondent_category", "category_name": "rater_role"},
    )
    assert res.status_code == 302
    cat = RespondentCategory.objects.get(survey=survey, name="rater_role")
    assert cat.label == "rater_role"
    assert cat.allowed_values == []
    assert cat.resolution_source == RespondentCategory.ResolutionSource.TOKEN


@pytest.mark.django_db
def test_add_dimension_slugifies_name(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {"action": "add_respondent_category", "category_name": "Rater Role"},
    )
    assert res.status_code == 302
    assert RespondentCategory.objects.filter(survey=survey, name="rater_role").exists()


@pytest.mark.django_db
def test_add_dimension_unique_name(client, survey, owner):
    client.force_login(owner)
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=[]
    )
    res = client.post(
        _groups_url(survey),
        {"action": "add_respondent_category", "category_name": "rater_role"},
    )
    assert res.status_code == 302
    # The second one gets a suffix.
    assert RespondentCategory.objects.filter(
        survey=survey, name="rater_role_2"
    ).exists()


@pytest.mark.django_db
def test_add_dimension_empty_name_rejected(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {"action": "add_respondent_category", "category_name": ""},
    )
    assert res.status_code == 302
    assert not RespondentCategory.objects.filter(survey=survey).exists()


# --- Save dimension ---------------------------------------------------


@pytest.mark.django_db
def test_save_dimension_updates_fields(client, survey, owner):
    client.force_login(owner)
    cat = RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=[]
    )
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(cat.id),
            f"label_{cat.id}": "Rater role",
            f"allowed_values_{cat.id}": "self, peer, supervisor, patient",
            f"resolution_source_{cat.id}": "token",
        },
    )
    assert res.status_code == 302
    cat.refresh_from_db()
    assert cat.label == "Rater role"
    assert cat.allowed_values == ["self", "peer", "supervisor", "patient"]
    assert cat.resolution_source == RespondentCategory.ResolutionSource.TOKEN


@pytest.mark.django_db
def test_save_dimension_changes_resolution_source(client, survey, owner):
    client.force_login(owner)
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a", "clinic_b"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(cat.id),
            f"label_{cat.id}": "Site",
            f"allowed_values_{cat.id}": "clinic_a, clinic_b",
            f"resolution_source_{cat.id}": "self_select",
        },
    )
    assert res.status_code == 302
    cat.refresh_from_db()
    assert cat.resolution_source == RespondentCategory.ResolutionSource.SELF_SELECT


# --- Remove dimension -------------------------------------------------


@pytest.mark.django_db
def test_remove_dimension_deletes_category(client, survey, owner):
    client.force_login(owner)
    cat = RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=["peer"]
    )
    res = client.post(
        _groups_url(survey),
        {"action": "remove_respondent_category", "category_id": str(cat.id)},
    )
    assert res.status_code == 302
    assert not RespondentCategory.objects.filter(id=cat.id).exists()


# --- Save group required_categories -----------------------------------


@pytest.mark.django_db
def test_save_group_categories(client, survey, owner):
    client.force_login(owner)
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_group_categories",
            f"group_{survey._g2.id}_cat_{cat.id}": ["peer", "supervisor"],
        },
    )
    assert res.status_code == 302
    survey._g2.refresh_from_db()
    assert survey._g2.required_categories == {"rater_role": ["peer", "supervisor"]}
    # g1 has no rules — empty dict.
    survey._g1.refresh_from_db()
    assert survey._g1.required_categories == {}


@pytest.mark.django_db
def test_save_group_categories_empty_means_visible_to_all(client, survey, owner):
    client.force_login(owner)
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    # No checkboxes ticked for any group → empty rules → visible to all.
    res = client.post(
        _groups_url(survey),
        {"action": "save_group_categories"},
    )
    assert res.status_code == 302
    survey._g1.refresh_from_db()
    survey._g2.refresh_from_db()
    assert survey._g1.required_categories == {}
    assert survey._g2.required_categories == {}


# --- Sync on visit ----------------------------------------------------


@pytest.mark.django_db
def test_organise_page_shows_existing_categories(client, survey, owner):
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "rater_role" in html
    assert "Rater role" in html
    assert "self, peer, supervisor" in html


@pytest.mark.django_db
def test_organise_page_shows_section_visibility_table(client, survey, owner):
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    survey._g2.required_categories = {"rater_role": ["peer"]}
    survey._g2.save(update_fields=["required_categories"])
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Section visibility" in html
    assert "Peer rating" in html
