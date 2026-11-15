"""Typed option follow-ups — a Yes/No question shown when an option is
selected (GMC 360 professional-role follow-up).

Extends the existing option follow-up mechanism (a free-text box per
option) with a ``type`` on ``followup_text``: ``"text"`` (default) or
``"yesno"``. The input name convention (``q_{id}_followup_{idx}``) is
unchanged, so the submission collector stores the answer with no new
plumbing; the renderer picks the widget by type.
"""

from __future__ import annotations

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import (
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.views import (
    _export_survey_to_markdown,
    _option_followup_label,
    create_default_section,
)

PASSWORD = "x"

MARKDOWN = """# Professional role {role}

## Your professional role:* {prof-role}
(mc_single)
- Doctor
  + If you are a doctor, are you in a training grade? (yesno)
- Registered Nurse
- Other
  + Please specify
"""


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


def _make_survey_with_question(django_user_model, options=None):
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username="fu@example.com", password=PASSWORD
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.PRO, email_confirmed=True
    )
    user._state.fields_cache.pop("profile", None)
    survey = Survey.objects.create(
        owner=user,
        name="FU Survey",
        slug="fu-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = create_default_section(survey, user)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Your professional role:",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=options
        or [
            {
                "label": "Doctor",
                "value": "Doctor",
                "followup_text": {
                    "enabled": True,
                    "label": "If you are a doctor, are you in a training grade?",
                    "type": "yesno",
                },
            },
            {"label": "Registered Nurse", "value": "Registered Nurse"},
            {
                "label": "Other",
                "value": "Other",
                "followup_text": {
                    "enabled": True,
                    "label": "Please specify",
                    "type": "text",
                },
            },
        ],
    )
    return user, survey, question


@pytest.mark.django_db
def test_markdown_import_parses_yesno_followup_type():
    parsed = parse_bulk_markdown(MARKDOWN)
    question = parsed[0]["questions"][0]
    doctor = next(o for o in question["final_options"] if o.get("label") == "Doctor")
    other = next(o for o in question["final_options"] if o.get("label") == "Other")
    assert doctor["followup_text"]["type"] == "yesno"
    assert doctor["followup_text"]["label"] == (
        "If you are a doctor, are you in a training grade?"
    )
    assert other["followup_text"]["type"] == "text"


@pytest.mark.django_db
def test_live_render_shows_yesno_radios(client, django_user_model):
    user, survey, question = _make_survey_with_question(django_user_model)
    client.force_login(user)
    resp = client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    html = resp.content.decode()
    # The Yes/No radios render with the existing follow-up input name.
    assert 'name="q_%d_followup_0" value="yes"' % question.id in html
    assert 'name="q_%d_followup_0" value="no"' % question.id in html
    # The text follow-up (Other) still renders as a text input.
    assert 'name="q_%d_followup_2"' % question.id in html
    assert 'type="text"' in html


@pytest.mark.django_db
def test_submission_stores_yesno_followup(client, django_user_model):
    user, survey, question = _make_survey_with_question(django_user_model)
    # The owner is blocked from taking their own survey — submit as an
    # anonymous respondent (the survey is public).
    from django.test import Client

    anon = Client()
    resp = anon.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        {
            f"q_{question.id}": "Doctor",
            f"q_{question.id}_followup_0": "yes",
        },
    )
    assert resp.status_code in (200, 302)
    response = SurveyResponse.objects.filter(survey=survey).latest("submitted_at")
    assert response.answers[str(question.id)] == "Doctor"
    # The existing collector stores the typed follow-up unchanged.
    assert response.answers[f"{question.id}_followup"] == {"0": "yes"}


@pytest.mark.django_db
def test_export_round_trips_yesno_type(django_user_model):
    _user, survey, _question = _make_survey_with_question(django_user_model)
    markdown = _export_survey_to_markdown(survey)
    assert "+ If you are a doctor, are you in a training grade? (yesno)" in markdown
    assert "+ Please specify" in markdown  # text type emits no marker

    # Round-trip: re-import restores the typed follow-up.
    parsed = parse_bulk_markdown(markdown)
    doctor = next(
        o
        for o in parsed[0]["questions"][0]["final_options"]
        if o.get("label") == "Doctor"
    )
    assert doctor["followup_text"]["type"] == "yesno"


@pytest.mark.django_db
def test_option_followup_label_includes_type_marker(django_user_model):
    _user, _survey, question = _make_survey_with_question(django_user_model)
    doctor = question.options[0]
    other = question.options[2]
    assert _option_followup_label(doctor) == (
        "If you are a doctor, are you in a training grade? (yesno)"
    )
    assert _option_followup_label(other) == "Please specify"


@pytest.mark.django_db
def test_builder_form_parses_followup_type(django_user_model):
    """The builder form's per-option type selector persists into
    followup_text.type."""
    from checktick_app.surveys.views import _parse_builder_question_form

    _user, _survey, _question = _make_survey_with_question(django_user_model)
    data = {
        "text": "Your professional role:",
        "type": "mc_single",
        "options": "Doctor\nRegistered Nurse",
        "option_0_followup": "on",
        "option_0_followup_label": "In a training grade?",
        "option_0_followup_type": "yesno",
        "option_1_followup": "on",
        "option_1_followup_label": "Please specify",
        "option_1_followup_type": "text",
    }
    parsed = _parse_builder_question_form(data)
    assert parsed["options"][0]["followup_text"]["type"] == "yesno"
    assert parsed["options"][1]["followup_text"]["type"] == "text"


@pytest.mark.django_db
def test_markdown_import_parses_required_marker():
    parsed = parse_bulk_markdown("""# Role {role}

## Your professional role:* {prof}
(mc_single)
- Doctor
  + If you are a doctor, are you in a training grade? (yesno, required)
- Other
  + Please specify (required)
""")
    options = parsed[0]["questions"][0]["final_options"]
    doctor = next(o for o in options if o.get("label") == "Doctor")
    other = next(o for o in options if o.get("label") == "Other")
    assert doctor["followup_text"]["type"] == "yesno"
    assert doctor["followup_text"]["required"] is True
    assert other["followup_text"]["type"] == "text"
    assert other["followup_text"]["required"] is True
    # A label that genuinely ends with bracketed text is preserved.
    parsed2 = parse_bulk_markdown("""# Q {q}

## Pick {pick}
(mc_single)
- Option A
  + See appendix (see page 12)
""")
    opt_a = parsed2[0]["questions"][0]["final_options"][0]
    assert opt_a["followup_text"]["label"] == "See appendix (see page 12)"
    assert opt_a["followup_text"]["type"] == "text"


@pytest.mark.django_db
def test_export_round_trips_required_marker(django_user_model):
    _user, survey, _question = _make_survey_with_question(django_user_model)
    # Mark the Doctor follow-up required.
    question = SurveyQuestion.objects.get(survey=survey)
    doctor = question.options[0]
    doctor["followup_text"]["required"] = True
    question.options = question.options
    question.save(update_fields=["options"])
    question.refresh_from_db()

    markdown = _export_survey_to_markdown(survey)
    assert (
        "+ If you are a doctor, are you in a training grade? (yesno, required)"
        in markdown
    )
    parsed = parse_bulk_markdown(markdown)
    doc_opt = next(
        o
        for o in parsed[0]["questions"][0]["final_options"]
        if o.get("label") == "Doctor"
    )
    assert doc_opt["followup_text"]["type"] == "yesno"
    assert doc_opt["followup_text"]["required"] is True


@pytest.mark.django_db
def test_required_followup_blocks_submission(client, django_user_model):
    """Selecting the option without answering a required follow-up is
    refused; answering it passes."""
    user, survey, question = _make_survey_with_question(django_user_model)
    doctor = question.options[0]
    doctor["followup_text"]["required"] = True
    question.save(update_fields=["options"])

    from django.test import Client

    anon = Client()
    # Missing follow-up answer → refused.
    resp = anon.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        {f"q_{question.id}": "Doctor"},
    )
    assert resp.status_code in (200, 302)
    assert not SurveyResponse.objects.filter(survey=survey).exists()

    # Answered → accepted.
    resp = anon.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        {
            f"q_{question.id}": "Doctor",
            f"q_{question.id}_followup_0": "no",
        },
    )
    assert resp.status_code in (200, 302)
    response = SurveyResponse.objects.filter(survey=survey).latest("submitted_at")
    assert response.answers[f"{question.id}_followup"] == {"0": "no"}


@pytest.mark.django_db
def test_required_followup_not_enforced_when_option_unselected(
    client, django_user_model
):
    user, survey, question = _make_survey_with_question(django_user_model)
    doctor = question.options[0]
    doctor["followup_text"]["required"] = True
    question.save(update_fields=["options"])

    from django.test import Client

    anon = Client()
    resp = anon.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        {f"q_{question.id}": "Registered Nurse"},
    )
    assert resp.status_code in (200, 302)
    assert SurveyResponse.objects.filter(survey=survey).exists()


@pytest.mark.django_db
def test_builder_form_parses_required_flag(django_user_model):
    from checktick_app.surveys.views import _parse_builder_question_form

    _user, _survey, _question = _make_survey_with_question(django_user_model)
    data = {
        "text": "Role",
        "type": "mc_single",
        "options": "Doctor\nOther",
        "option_0_followup": "on",
        "option_0_followup_label": "In a training grade?",
        "option_0_followup_type": "yesno",
        "option_0_followup_required": "on",
        "option_1_followup": "on",
        "option_1_followup_label": "Please specify",
    }
    parsed = _parse_builder_question_form(data)
    assert parsed["options"][0]["followup_text"]["required"] is True
    assert parsed["options"][1]["followup_text"]["required"] is False
