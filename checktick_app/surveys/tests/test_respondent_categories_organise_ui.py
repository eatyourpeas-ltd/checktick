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
    assert "No categories yet" in html


@pytest.mark.django_db
def test_categories_card_shows_howto_signposting(client, survey, owner):
    """The card must explain the workflow and label the add-dimension input.

    The original card only said "e.g. rater_role" with no label and no
    steps, which was too ambiguous to follow (see the fix branch for the
    404 + signposting rework).
    """
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    # How-to alert with the four setup steps.
    assert "How to use respondent categories" in html
    assert "Add a category" in html
    assert "Tick which options each section is visible to" in html
    # Link to the in-app outline reference.
    assert 'href="/docs/import/"' in html
    # The add-dimension input is labelled (accessibility) and carries the
    # clearer placeholder.
    assert 'for="add-category-name"' in html
    assert 'id="add-category-name"' in html
    assert "e.g. Rater role" in html
    assert "e.g. rater_role" not in html


@pytest.mark.django_db
def test_resolution_source_options_are_plain_english(client, survey, owner):
    """The category form asks how each respondent is put into a category,
    offers the three workable sources in plain English, and hides the
    profile source (a dead end until profile-based resolution has fields
    to offer)."""
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=[]
    )
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "How is each respondent put into a category?" in html
    assert "I pick it for each batch of invitations" in html
    assert "They pick it themselves in the survey" in html
    assert "CheckTick assigns it at random" in html
    assert "Read from their profile" not in html


@pytest.mark.django_db
def test_dimension_row_shows_display_name_not_raw_key(client, survey, owner):
    """The row is led by the human-facing display name; the underscore key
    is not rendered at all (it remains available in the outline export and
    token CSV headers, where power users need it)."""
    RespondentCategory.objects.create(
        survey=survey, name="rater_role", allowed_values=[]
    )
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    # display_name prettifies the key when no label is set.
    assert "Rater Role" in html
    # The raw underscore key is not shown anywhere on the page.
    assert "rater_role" not in html


@pytest.mark.django_db
def test_existing_profile_source_dimension_stays_savable(client, survey, owner):
    """A profile-source dimension (outline import) keeps its option when
    rendered, so saving the form does not silently flip the source."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=[],
        resolution_source=RespondentCategory.ResolutionSource.PROFILE,
    )
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    html = res.content.decode()
    assert '<option value="profile" selected>' in html


@pytest.mark.django_db
def test_self_select_shows_question_picker_with_choice_questions_only(
    client, survey, owner
):
    """Choosing 'participant answers a survey question' reveals a question
    picker that offers single-choice questions from this survey only."""
    RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a", "clinic_b"],
        resolution_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=survey._g1,
        text="Which site are you from?",
        type=SurveyQuestion.Types.DROPDOWN,
        order=1,
    )
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Which question do they answer?" in html
    assert "Which site are you from?" in html
    # The fixture's free-text questions are not eligible as sources.
    assert "Clinical knowledge" not in html


@pytest.mark.django_db
def test_save_self_select_persists_source_question(client, survey, owner):
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a", "clinic_b"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=survey._g1,
        text="Which site are you from?",
        type=SurveyQuestion.Types.DROPDOWN,
        order=1,
    )
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(cat.id),
            f"resolution_source_{cat.id}": "self_select",
            f"source_question_{cat.id}": str(q.id),
        },
    )
    assert res.status_code == 302
    cat.refresh_from_db()
    assert cat.resolution_source == RespondentCategory.ResolutionSource.SELF_SELECT
    assert cat.source_question_id == q.id


@pytest.mark.django_db
def test_save_self_select_rejects_question_from_other_survey(
    client, survey, owner, org
):
    """A crafted POST naming another survey's question must not store it
    as the self-select source."""
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=[],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    other = Survey.objects.create(
        owner=owner, organization=org, name="Other", slug="other"
    )
    other_q = SurveyQuestion.objects.create(
        survey=other,
        group=None,
        text="Other survey question",
        type=SurveyQuestion.Types.DROPDOWN,
        order=0,
    )
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(cat.id),
            f"resolution_source_{cat.id}": "self_select",
            f"source_question_{cat.id}": str(other_q.id),
        },
    )
    assert res.status_code == 302
    cat.refresh_from_db()
    assert cat.source_question_id is None


# --- Add dimension ----------------------------------------------------


@pytest.mark.django_db
def test_add_dimension_creates_category(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {"action": "add_respondent_category", "category_name": "rater_role"},
    )
    assert res.status_code == 302
    # Regression guard: the redirect must go back to this survey's Organise
    # page, not to /surveys/<dimension-key>/groups/ (which 404s).
    assert res.url == _groups_url(survey)
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
    assert res.url == _groups_url(survey)
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
    assert res.url == _groups_url(survey)
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
