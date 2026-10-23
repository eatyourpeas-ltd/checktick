"""Tests for respondent categories preview + Survey Map (commit 5).

Preview: ``?simulate_category=<dim>:<value>,<dim>:<value>`` filters the
preview to what a participant with those category values would see.
Survey Map: shows category dimensions and per-section required_categories
annotations.
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


def _make_categorised_survey(owner, org):
    """A survey with a rater_role category and two gated sections."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Cat Survey",
        slug="cat-survey",
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_peer = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    g_self = QuestionGroup.objects.create(name="Self reflection", owner=owner)
    s.question_groups.add(g_demo, g_peer, g_self)
    SurveyQuestion.objects.create(
        survey=s, group=g_demo, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_peer,
        text="Clinical knowledge",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_self,
        text="What went well",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    g_peer.required_categories = {"rater_role": ["peer"]}
    g_peer.save(update_fields=["required_categories"])
    g_self.required_categories = {"rater_role": ["self"]}
    g_self.save(update_fields=["required_categories"])
    s._g_demo, s._g_peer, s._g_self = g_demo, g_peer, g_self
    return s


# --- Preview: simulate category --------------------------------------


@pytest.mark.django_db
def test_preview_shows_simulate_category_panel(client, owner, org):
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate category" in html
    assert "rater_role" in html or "Rater role" in html


@pytest.mark.django_db
def test_preview_no_categories_no_simulate_panel(client, owner, org):
    """A survey with no RespondentCategory rows has no simulate panel."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain",
    )
    g = QuestionGroup.objects.create(name="G1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate category" not in html


@pytest.mark.django_db
def test_preview_simulate_peer_shows_peer_section(client, owner, org):
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": s.slug}),
        {"simulate_category": "rater_role:peer"},
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html  # Demographics — no rules
    assert "Clinical knowledge" in html  # Peer — rater_role=peer
    assert "What went well" not in html  # Self — rater_role=self


@pytest.mark.django_db
def test_preview_simulate_self_shows_self_section(client, owner, org):
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": s.slug}),
        {"simulate_category": "rater_role:self"},
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "What went well" in html
    assert "Clinical knowledge" not in html


@pytest.mark.django_db
def test_preview_simulate_no_value_shows_all_unruled(client, owner, org):
    """Without simulate_category, the preview shows all sections (no
    category filter applied in preview without a real participant)."""
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # Without simulation, all sections show (no filter applied).
    assert "Age" in html
    assert "Clinical knowledge" in html
    assert "What went well" in html


# --- Survey Map -------------------------------------------------------


@pytest.mark.django_db
def test_survey_map_shows_categories(client, owner, org):
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Respondent categories" in html
    assert "rater_role" in html or "Rater role" in html
    assert "self" in html
    assert "peer" in html


@pytest.mark.django_db
def test_survey_map_shows_section_visibility(client, owner, org):
    s = _make_categorised_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Section visibility" in html
    # Peer rating has required_categories rater_role: [peer].
    assert "Peer rating" in html
    assert "rater_role" in html
    # Demographics has no rules — visible to all.
    assert "Demographics" in html
    assert "visible to all" in html


@pytest.mark.django_db
def test_survey_map_no_categories_no_section(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain-map",
    )
    g = QuestionGroup.objects.create(name="G1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Respondent categories" not in html
