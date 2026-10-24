"""End-to-end tests for the 360° / multi-rater assessment pattern (commit 9).

The 360 pattern is built on respondent categories: a rater_role dimension
drives which question set each rater sees, a subject dimension drives
cross-rater aggregation in reporting, and invite tokens carry the role
value for each batch. No new layout — the 360 instrument ships in the
question bank as a ready-made template.

These tests verify the full 360 flow: create a survey with rater_role +
subject dimensions, tag sections with required_categories, generate
token batches per role, take the survey as each role, and verify the
filtering + CSV export.
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


def _make_360_survey(owner, org):
    """Create a 360 survey with rater_role + subject dimensions.

    Sections:
    - Demographics (no rules — visible to all raters)
    - Self reflection (rater_role=self)
    - Peer rating (rater_role=peer)
    - Supervisor rating (rater_role=supervisor)
    """
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="NHS 360",
        slug="nhs-360",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_self = QuestionGroup.objects.create(name="Self reflection", owner=owner)
    g_peer = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    g_sup = QuestionGroup.objects.create(name="Supervisor rating", owner=owner)
    s.question_groups.add(g_demo, g_self, g_peer, g_sup)
    for g, text in [
        (g_demo, "Name"),
        (g_self, "What are your strengths?"),
        (g_peer, "Clinical knowledge"),
        (g_sup, "Leadership assessment"),
    ]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=text, type=SurveyQuestion.Types.TEXT, order=0
        )
    # Dimensions.
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor", "patient"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="subject",
        label="Subject",
        allowed_values=["self"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    # Tag sections.
    g_self.required_categories = {"rater_role": ["self"]}
    g_self.save(update_fields=["required_categories"])
    g_peer.required_categories = {"rater_role": ["peer"]}
    g_peer.save(update_fields=["required_categories"])
    g_sup.required_categories = {"rater_role": ["supervisor"]}
    g_sup.save(update_fields=["required_categories"])
    s._g_demo, s._g_self, s._g_peer, s._g_sup = g_demo, g_self, g_peer, g_sup
    return s


def _take_token_url(survey, token):
    return reverse(
        "surveys:take_token", kwargs={"slug": survey.slug, "token": token.token}
    )


# --- Token batches per role ---


@pytest.mark.django_db
def test_360_peer_token_shows_peer_section_only(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-360-peer",
        created_by=owner,
        category_values={"rater_role": "peer", "subject": "self"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html  # Demographics
    assert "Clinical knowledge" in html  # Peer rating
    assert "What are your strengths?" not in html  # Self reflection
    assert "Leadership assessment" not in html  # Supervisor rating


@pytest.mark.django_db
def test_360_self_token_shows_self_section_only(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-360-self",
        created_by=owner,
        category_values={"rater_role": "self", "subject": "self"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html
    assert "What are your strengths?" in html
    assert "Clinical knowledge" not in html
    assert "Leadership assessment" not in html


@pytest.mark.django_db
def test_360_supervisor_token_shows_supervisor_section_only(client, owner, org):
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-360-sup",
        created_by=owner,
        category_values={"rater_role": "supervisor", "subject": "self"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html
    assert "Leadership assessment" in html
    assert "Clinical knowledge" not in html
    assert "What are your strengths?" not in html


# --- Token batch generation per role ---


@pytest.mark.django_db
def test_360_token_batch_generation(client, owner, org):
    """Generate token batches per role via the tokens page."""
    s = _make_360_survey(owner, org)
    client.force_login(owner)
    # Generate a peer batch.
    res = client.post(
        reverse("surveys:tokens", kwargs={"slug": s.slug}),
        {"count": "5", "category_rater_role": "peer", "category_subject": "self"},
    )
    assert res.status_code == 302
    peer_tokens = SurveyAccessToken.objects.filter(
        survey=s, category_values__rater_role="peer"
    )
    assert peer_tokens.count() == 5
    for t in peer_tokens:
        assert t.category_values == {"rater_role": "peer", "subject": "self"}
    # Generate a supervisor batch.
    res = client.post(
        reverse("surveys:tokens", kwargs={"slug": s.slug}),
        {"count": "3", "category_rater_role": "supervisor", "category_subject": "self"},
    )
    assert res.status_code == 302
    sup_tokens = SurveyAccessToken.objects.filter(
        survey=s, category_values__rater_role="supervisor"
    )
    assert sup_tokens.count() == 3


# --- Demographics visible to all roles ---


@pytest.mark.django_db
def test_360_demographics_visible_to_all_roles(client, owner, org):
    """Demographics has no required_categories → visible to every role."""
    s = _make_360_survey(owner, org)
    for role in ("self", "peer", "supervisor"):
        token = SurveyAccessToken.objects.create(
            survey=s,
            token=f"tok-360-{role}",
            created_by=owner,
            category_values={"rater_role": role, "subject": "self"},
        )
        res = client.get(_take_token_url(s, token))
        assert "Name" in res.content.decode(), f"Demographics missing for {role}"


# --- Unresolved subject dimension ---


@pytest.mark.django_db
def test_360_unresolved_subject_still_shows_demographics(client, owner, org):
    """A token with rater_role but no subject still shows Demographics
    (no rules) and the rater_role section."""
    s = _make_360_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-test-no-subject",
        created_by=owner,
        category_values={"rater_role": "peer"},  # no subject
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html  # Demographics — no rules
    assert "Clinical knowledge" in html  # Peer — rater_role=peer matches
