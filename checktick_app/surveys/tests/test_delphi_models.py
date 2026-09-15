"""Tests for the Delphi layout models: Survey.Layout.DELPHI choice,
DelphiMenu, DelphiRound, DelphiRoundFeedback, and the SurveyProgress
delphi_round / delphi_completed_rounds fields.

These verify the data model and migration. The pure helpers
(``delphi.py``) and runtime hook are tested separately.
"""

import pytest

from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    DelphiRoundFeedback,
    Organization,
    Survey,
    SurveyProgress,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="delphi_models@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="delphi-models-s",
        layout=Survey.Layout.DELPHI,
    )


# --- layout choice ---


@pytest.mark.django_db
def test_layout_delphi_choice_exists():
    choices = {value for value, _label in Survey.Layout.choices}
    assert "delphi" in choices
    assert Survey.Layout.DELPHI == "delphi"


@pytest.mark.django_db
def test_layout_delphi_display_label():
    assert Survey.Layout.DELPHI.label == "Delphi (consensus rounds)"


@pytest.mark.django_db
def test_layout_default_is_linear(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="D", slug="d-lin")
    assert s.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_layout_can_be_set_to_delphi(owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="DL", slug="dl", layout=Survey.Layout.DELPHI
    )
    s.refresh_from_db()
    assert s.layout == "delphi"


# --- DelphiMenu model ---


@pytest.mark.django_db
def test_delphi_menu_defaults(survey):
    menu = DelphiMenu.objects.create(survey=survey)
    assert menu.anchor == DelphiMenu.Anchor.ENROLMENT
    assert menu.min_rounds == 2
    assert menu.max_rounds == 3
    assert menu.show_progress is True
    assert menu.allow_revision is True


@pytest.mark.django_db
def test_delphi_menu_one_to_one(survey):
    DelphiMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        DelphiMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_delphi_menu_cascade_delete_with_survey(survey):
    menu = DelphiMenu.objects.create(survey=survey)
    menu_id = menu.id
    survey.delete()
    assert not DelphiMenu.objects.filter(id=menu_id).exists()


@pytest.mark.django_db
def test_delphi_menu_str(survey):
    menu = DelphiMenu.objects.create(survey=survey)
    assert "DelphiMenu for S" in str(menu)


@pytest.mark.django_db
def test_delphi_menu_anchor_choices():
    values = {v for v, _ in DelphiMenu.Anchor.choices}
    assert values == {"enrolment", "survey_open"}


@pytest.mark.django_db
def test_linear_survey_has_no_delphi_menu(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="L", slug="l-nomenu")
    assert not hasattr(s, "delphi_menu") or s.delphi_menu is None
    assert not DelphiMenu.objects.filter(survey=s).exists()


# --- DelphiRound model ---


@pytest.fixture
def menu(survey):
    return DelphiMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_delphi_round_defaults(menu):
    rnd = DelphiRound.objects.create(menu=menu)
    assert rnd.order == 0
    assert rnd.name == "Round 1"
    assert rnd.start_offset_days == 0
    assert rnd.end_offset_days is None
    assert rnd.opened_at is None
    assert rnd.closed_at is None


@pytest.mark.django_db
def test_delphi_round_str(menu):
    rnd = DelphiRound.objects.create(menu=menu, name="Initial", start_offset_days=0)
    assert "Initial" in str(rnd)
    assert "days 0" in str(rnd)


@pytest.mark.django_db
def test_delphi_round_str_with_end(menu):
    rnd = DelphiRound.objects.create(
        menu=menu, name="R2", start_offset_days=7, end_offset_days=14
    )
    assert "days 7–14" in str(rnd)


@pytest.mark.django_db
def test_delphi_round_str_open_ended(menu):
    rnd = DelphiRound.objects.create(menu=menu, name="Open", start_offset_days=0)
    assert "∞" in str(rnd)


@pytest.mark.django_db
def test_delphi_round_cascade_delete_with_menu(menu):
    rnd = DelphiRound.objects.create(menu=menu)
    rnd_id = rnd.id
    menu.delete()
    assert not DelphiRound.objects.filter(id=rnd_id).exists()


@pytest.mark.django_db
def test_delphi_round_unique_together_menu_order(menu):
    DelphiRound.objects.create(menu=menu, order=0)
    with pytest.raises(Exception):
        DelphiRound.objects.create(menu=menu, order=0)


@pytest.mark.django_db
def test_delphi_round_ordering(menu):
    DelphiRound.objects.create(menu=menu, order=2, name="Third")
    DelphiRound.objects.create(menu=menu, order=0, name="First")
    DelphiRound.objects.create(menu=menu, order=1, name="Second")
    rounds = list(DelphiRound.objects.filter(menu=menu))
    assert rounds[0].name == "First"
    assert rounds[1].name == "Second"
    assert rounds[2].name == "Third"


@pytest.mark.django_db
def test_delphi_round_groups_m2m(menu, owner):
    from checktick_app.surveys.models import QuestionGroup

    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    rnd = DelphiRound.objects.create(menu=menu)
    rnd.groups.add(g1, g2)
    assert set(rnd.groups.all()) == {g1, g2}


@pytest.mark.django_db
def test_delphi_round_group_in_multiple_rounds(menu, owner):
    """A group can appear in multiple rounds (e.g. demographics in every round)."""
    from checktick_app.surveys.models import QuestionGroup

    g = QuestionGroup.objects.create(name="Demo", owner=owner)
    r1 = DelphiRound.objects.create(menu=menu, order=0)
    r2 = DelphiRound.objects.create(menu=menu, order=1)
    r1.groups.add(g)
    r2.groups.add(g)
    assert g in r1.groups.all()
    assert g in r2.groups.all()


# --- DelphiRoundFeedback model ---


@pytest.fixture
def round_with_question(menu, survey, owner):
    from checktick_app.surveys.models import QuestionGroup, SurveyQuestion

    g = QuestionGroup.objects.create(name="G", owner=owner)
    survey.question_groups.add(g)
    q = SurveyQuestion.objects.create(
        survey=survey, group=g, text="Rate", type="likert", order=0
    )
    rnd = DelphiRound.objects.create(menu=menu, order=0)
    rnd.groups.add(g)
    return rnd, q


@pytest.mark.django_db
def test_feedback_defaults(round_with_question):
    rnd, q = round_with_question
    fb = DelphiRoundFeedback.objects.create(round=rnd, question=q)
    assert fb.stats_json == {}
    assert fb.theme_markdown == ""
    assert fb.llm_generated is False
    assert fb.llm_model == ""
    assert fb.llm_token_count == 0
    assert fb.llm_success is False
    assert fb.generated_at is not None


@pytest.mark.django_db
def test_feedback_str(round_with_question):
    rnd, q = round_with_question
    fb = DelphiRoundFeedback.objects.create(round=rnd, question=q)
    assert "Rate" in str(fb)


@pytest.mark.django_db
def test_feedback_cascade_delete_with_round(round_with_question):
    rnd, q = round_with_question
    fb = DelphiRoundFeedback.objects.create(round=rnd, question=q)
    fb_id = fb.id
    rnd.delete()
    assert not DelphiRoundFeedback.objects.filter(id=fb_id).exists()


@pytest.mark.django_db
def test_feedback_unique_together_round_question(round_with_question):
    rnd, q = round_with_question
    DelphiRoundFeedback.objects.create(round=rnd, question=q)
    with pytest.raises(Exception):
        DelphiRoundFeedback.objects.create(round=rnd, question=q)


@pytest.mark.django_db
def test_feedback_stats_json_round_trip(round_with_question):
    rnd, q = round_with_question
    stats = {"median": 3.5, "q1": 2.0, "q3": 4.0, "count": 10}
    fb = DelphiRoundFeedback.objects.create(round=rnd, question=q, stats_json=stats)
    fb.refresh_from_db()
    assert fb.stats_json["median"] == 3.5
    assert fb.stats_json["count"] == 10


@pytest.mark.django_db
def test_feedback_llm_fields_populated(round_with_question):
    rnd, q = round_with_question
    fb = DelphiRoundFeedback.objects.create(
        round=rnd,
        question=q,
        stats_json={"count": 5},
        theme_markdown="- Theme A\n- Theme B",
        llm_generated=True,
        llm_model="ollama/llama3",
        llm_token_count=250,
        llm_success=True,
    )
    fb.refresh_from_db()
    assert fb.llm_generated is True
    assert fb.llm_model == "ollama/llama3"
    assert fb.llm_token_count == 250
    assert fb.llm_success is True
    assert "Theme A" in fb.theme_markdown


# --- SurveyProgress fields ---


@pytest.mark.django_db
def test_delphi_round_defaults_to_null(owner, org):
    from django.utils import timezone

    s = Survey.objects.create(owner=owner, organization=org, name="P", slug="p-dp")
    progress = SurveyProgress.objects.create(
        survey=s, user=owner, expires_at=timezone.now()
    )
    assert progress.delphi_round is None
    assert progress.delphi_completed_rounds == []
    assert isinstance(progress.delphi_completed_rounds, list)


@pytest.mark.django_db
def test_delphi_completed_rounds_can_hold_ids(owner, org):
    from django.utils import timezone

    s = Survey.objects.create(owner=owner, organization=org, name="P2", slug="p2-dp")
    progress = SurveyProgress.objects.create(
        survey=s,
        user=owner,
        delphi_completed_rounds=[1, 2],
        expires_at=timezone.now(),
    )
    progress.refresh_from_db()
    assert progress.delphi_completed_rounds == [1, 2]


@pytest.mark.django_db
def test_delphi_round_fk_can_be_set(owner, org):
    from django.utils import timezone

    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="P3",
        slug="p3-dp",
        layout=Survey.Layout.DELPHI,
    )
    menu = DelphiMenu.objects.create(survey=s)
    rnd = DelphiRound.objects.create(menu=menu, order=0)
    progress = SurveyProgress.objects.create(
        survey=s, user=owner, delphi_round=rnd, expires_at=timezone.now()
    )
    progress.refresh_from_db()
    assert progress.delphi_round_id == rnd.id


# --- admin registration ---


@pytest.mark.django_db
def test_admin_registration():
    """The models are registered in admin (smoke test via admin.site)."""
    from django.contrib import admin

    assert DelphiMenu in admin.site._registry
    assert DelphiRound in admin.site._registry
    assert DelphiRoundFeedback in admin.site._registry
