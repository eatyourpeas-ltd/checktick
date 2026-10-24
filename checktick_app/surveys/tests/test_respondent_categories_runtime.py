"""Tests for the respondent categories runtime hook (commit 3).

Category-based visibility is a static pre-step filter, not a branching
rule. When a survey has RespondentCategory rows, the take view resolves
the participant's category values (commit 2) and drops any group whose
``required_categories`` don't match the resolved values before
``_order_questions_by_group`` renders. The filter composes with
``selected_group_ids`` set by the other layouts (section_menu / rct /
matrix / staged / delphi).

Group-level only in this release (see Resolved decisions 4).
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


def _take_token_url(survey, token):
    return reverse(
        "surveys:take_token", kwargs={"slug": survey.slug, "token": token.token}
    )


def _make_360_survey(owner, org, *, visibility=Survey.Visibility.TOKEN):
    """A published 360 survey with a rater_role category (token-resolved).

    Sections:
    - Demographics (no rules — visible to all raters)
    - Peer rating (rater_role in [peer])
    - Self reflection (rater_role in [self])
    """
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="360 Survey",
        slug="360-survey",
        status=Survey.Status.PUBLISHED,
        visibility=visibility,
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
        allowed_values=["self", "peer", "supervisor", "patient"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    g_peer.required_categories = {"rater_role": ["peer"]}
    g_peer.save(update_fields=["required_categories"])
    g_self.required_categories = {"rater_role": ["self"]}
    g_self.save(update_fields=["required_categories"])
    s._g_demo = g_demo
    s._g_peer = g_peer
    s._g_self = g_self
    return s


# --- No categories: no-op --------------------------------------------


@pytest.mark.django_db
def test_no_categories_renders_all_sections(client, owner, org):
    """A survey with no RespondentCategory rows renders all sections."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    g1 = QuestionGroup.objects.create(name="Section A", owner=owner)
    g2 = QuestionGroup.objects.create(name="Section B", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Q2", type=SurveyQuestion.Types.TEXT, order=0
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-plain",
        created_by=owner,
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Q1" in html
    assert "Q2" in html


# --- Token-resolved category: peer rater ------------------------------


@pytest.mark.django_db
def test_peer_token_shows_peer_section_only(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (no rules) and Peer rating (rater_role=peer) are visible.
    assert "Age" in html
    assert "Clinical knowledge" in html
    # Self reflection (rater_role=self) is hidden.
    assert "What went well" not in html


@pytest.mark.django_db
def test_self_token_shows_self_section_only(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-self",
        created_by=owner,
        category_values={"rater_role": "self"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "What went well" in html
    assert "Clinical knowledge" not in html


# --- Unresolved dimension hides gated sections -----------------------


@pytest.mark.django_db
def test_unresolved_dimension_hides_gated_sections(client, owner, org):
    """A token without the dimension's value leaves it unresolved, so
    sections requiring that dimension are hidden (but unruled sections
    still show)."""
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-empty",
        created_by=owner,
        category_values={},  # no rater_role
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (no rules) is visible.
    assert "Age" in html
    # Both gated sections are hidden (rater_role unresolved).
    assert "Clinical knowledge" not in html
    assert "What went well" not in html


# --- Composition with section_menu -----------------------------------


@pytest.mark.django_db
def test_compose_with_section_menu(client, owner, org):
    """A section_menu + categories survey shows the picker first, then
    filters the chosen sections by category."""
    s = _make_360_survey(owner, org)
    s.layout = Survey.Layout.SECTION_MENU
    s.save(update_fields=["layout"])
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-peer-sm",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    url = _take_token_url(s, token)
    # First access: picker renders (no selection yet).
    res = client.get(url)
    assert res.status_code == 200
    # After selecting Demographics + Self reflection, the category filter
    # drops Self reflection (rater_role=peer, not self) and keeps
    # Demographics (no rules). Peer rating was not selected so it's
    # already out.
    res2 = client.post(
        url,
        {
            "action": "select_sections",
            "selected_groups": [s._g_demo.id, s._g_self.id],
        },
        follow=True,
    )
    assert res2.status_code == 200
    html2 = res2.content.decode()
    assert "Age" in html2  # Demographics — selected + no category rule
    assert "What went well" not in html2  # Self — selected but rater_role=peer


# --- Composition with RCT --------------------------------------------


@pytest.mark.django_db
def test_compose_with_rct(client, owner, org):
    """An RCT + categories survey resolves the arm (system-assigned
    dimension) and the token-borne dimension independently."""
    from checktick_app.surveys.models import RandomisedArm, RandomisedMenu

    s = _make_360_survey(owner, org)
    s.layout = Survey.Layout.RCT
    s.save(update_fields=["layout"])
    menu = RandomisedMenu.objects.create(survey=s, seed=7)
    arm = RandomisedArm.objects.create(menu=menu, name="Arm A", order=1)
    arm.groups.add(s._g_demo, s._g_peer)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-peer-rct",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    # The arm includes Demographics + Peer rating; the category filter
    # (rater_role=peer) keeps both (Demographics has no rule, Peer
    # requires peer). Self reflection is not in the arm anyway.
    assert "Age" in html
    assert "Clinical knowledge" in html
    assert "What went well" not in html


# --- Resume preserves filtered set -----------------------------------


@pytest.mark.django_db
def test_resume_preserves_filtered_set(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-peer-resume",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    url = _take_token_url(s, token)
    client.get(url)
    # Second access (resume) — same filtered set.
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "Clinical knowledge" in html
    assert "What went well" not in html


# --- Section with rules visible to multiple values -------------------


@pytest.mark.django_db
def test_section_visible_to_multiple_values(client, owner, org):
    """A section with required_categories {rater_role: [peer, supervisor]}
    is visible to both peer and supervisor raters."""
    s = _make_360_survey(owner, org)
    s._g_peer.required_categories = {"rater_role": ["peer", "supervisor"]}
    s._g_peer.save(update_fields=["required_categories"])
    # Peer token.
    token_peer = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-peer-multi",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    res = client.get(_take_token_url(s, token_peer))
    assert "Clinical knowledge" in res.content.decode()
    # Supervisor token.
    token_sup = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sup-multi",
        created_by=owner,
        category_values={"rater_role": "supervisor"},
    )
    res2 = client.get(_take_token_url(s, token_sup))
    assert "Clinical knowledge" in res2.content.decode()
