"""Tests for the Delphi inter-round feedback rendering and endpoints.

Covers:
- Content block body_md substitution from DelphiRoundFeedback cache
- The 'Generate feedback' POST endpoint (delphi_generate_feedback)
- The 'Download comments' GET endpoint (delphi_download_comments)
- The _render_delphi_feedback_body helper
- The _previous_round_for_survey helper
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.delphi import _previous_round_for_survey
from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    DelphiRoundFeedback,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="delphi_fb@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def delphi_survey(owner, org):
    """A Delphi survey with two rounds and questions."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Delphi FB",
        slug="delphi-fb",
        layout=Survey.Layout.DELPHI,
    )
    g_r1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g_r2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    s.question_groups.add(g_r1, g_r2)
    q_likert = SurveyQuestion.objects.create(
        survey=s,
        group=g_r1,
        text="Rate",
        type=SurveyQuestion.Types.LIKERT,
        order=0,
    )
    q_text = SurveyQuestion.objects.create(
        survey=s,
        group=g_r1,
        text="Explain",
        type=SurveyQuestion.Types.LONG_TEXT,
        order=1,
    )
    q_feedback = SurveyQuestion.objects.create(
        survey=s,
        group=g_r2,
        text="Feedback",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        order=0,
        options={
            "heading": "Inter-round feedback",
            "body_md": "Authored placeholder.",
            "is_delphi_feedback": True,
        },
    )
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(g_r1)
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(g_r2)
    s._g_r1, s._g_r2 = g_r1, g_r2
    s._q_likert, s._q_text, s._q_feedback = q_likert, q_text, q_feedback
    s._r1, s._r2 = r1, r2
    s._menu = menu
    return s


# --- _previous_round_for_survey ---


@pytest.mark.django_db
def test_previous_round_none_when_no_closed_rounds(delphi_survey):
    """No round has closed_at set → returns None."""
    assert _previous_round_for_survey(delphi_survey) is None


@pytest.mark.django_db
def test_previous_round_returns_most_recently_closed(delphi_survey):
    """Returns the most recently closed round (highest order with closed_at)."""
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()
    result = _previous_round_for_survey(delphi_survey)
    assert result == delphi_survey._r1


@pytest.mark.django_db
def test_previous_round_returns_highest_order_when_multiple_closed(
    delphi_survey, owner, org
):
    """When multiple rounds are closed, returns the one with the highest order."""
    delphi_survey._r1.closed_at = timezone.now() - timedelta(days=10)
    delphi_survey._r1.save()
    delphi_survey._r2.closed_at = timezone.now()
    delphi_survey._r2.save()
    result = _previous_round_for_survey(delphi_survey)
    assert result == delphi_survey._r2


@pytest.mark.django_db
def test_previous_round_none_when_no_menu(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="NoMenu",
        slug="no-menu",
        layout=Survey.Layout.DELPHI,
    )
    assert _previous_round_for_survey(s) is None


# --- _render_delphi_feedback_body ---


def test_render_feedback_likert():
    """Likert stats render as median/IQR/distribution."""
    from checktick_app.surveys.views import _render_delphi_feedback_body

    class FakeFeedback:
        stats_json = {
            "question_type": "likert",
            "count": 10,
            "median": 3.5,
            "q1": 2.0,
            "q3": 4.0,
            "distribution": {"3": 4, "4": 3, "5": 3},
        }
        llm_generated = False
        theme_markdown = ""

    body = _render_delphi_feedback_body(FakeFeedback())
    assert "Median" in body
    assert "3.5" in body
    assert "IQR" in body
    assert "2.0" in body
    assert "4.0" in body
    assert "Distribution" in body
    assert "3: 4" in body


def test_render_feedback_yesno():
    from checktick_app.surveys.views import _render_delphi_feedback_body

    class FakeFeedback:
        stats_json = {
            "question_type": "yesno",
            "count": 5,
            "yes_count": 3,
            "no_count": 2,
            "dont_know_count": 0,
            "yes_pct": 60.0,
        }
        llm_generated = False
        theme_markdown = ""

    body = _render_delphi_feedback_body(FakeFeedback())
    assert "Yes" in body
    assert "3" in body
    assert "60" in body
    assert "No" in body


def test_render_feedback_text_with_llm():
    from checktick_app.surveys.views import _render_delphi_feedback_body

    class FakeFeedback:
        stats_json = {"question_type": "text", "count": 3}
        llm_generated = True
        theme_markdown = "- Theme A\n- Theme B"

    body = _render_delphi_feedback_body(FakeFeedback())
    assert "Theme A" in body
    assert "Theme B" in body


def test_render_feedback_text_without_llm():
    from checktick_app.surveys.views import _render_delphi_feedback_body

    class FakeFeedback:
        stats_json = {"question_type": "text", "count": 3}
        llm_generated = False
        theme_markdown = ""

    body = _render_delphi_feedback_body(FakeFeedback())
    assert "Download the comments" in body


def test_render_feedback_no_responses():
    from checktick_app.surveys.views import _render_delphi_feedback_body

    class FakeFeedback:
        stats_json = {"question_type": "likert", "count": 0}
        llm_generated = False
        theme_markdown = ""

    body = _render_delphi_feedback_body(FakeFeedback())
    assert "No responses" in body


def test_render_feedback_summary_empty():
    from checktick_app.surveys.views import _render_delphi_feedback_summary

    body = _render_delphi_feedback_summary([])
    assert "No inter-round feedback" in body


def test_render_feedback_summary_multiple():
    from checktick_app.surveys.views import _render_delphi_feedback_summary

    class FakeQuestion:
        def __init__(self, text):
            self.text = text

    class FakeFeedback:
        def __init__(self, q_text, stats):
            self.question = FakeQuestion(q_text)
            self.stats_json = stats
            self.llm_generated = False
            self.theme_markdown = ""

    rows = [
        FakeFeedback(
            "Rate",
            {
                "question_type": "likert",
                "count": 5,
                "median": 3.5,
                "q1": 2.0,
                "q3": 4.0,
            },
        ),
        FakeFeedback(
            "Agree?",
            {
                "question_type": "yesno",
                "count": 3,
                "yes_count": 2,
                "no_count": 1,
                "dont_know_count": 0,
                "yes_pct": 66.7,
            },
        ),
    ]
    body = _render_delphi_feedback_summary(rows)
    assert "### Rate" in body
    assert "### Agree?" in body
    assert "Median" in body
    assert "Yes" in body


# --- delphi_generate_feedback endpoint ---


@pytest.mark.django_db
def test_generate_feedback_quantitative_only(client, delphi_survey, owner):
    """Generate feedback without LLM — only quantitative stats cached."""
    # Add responses to round 1's questions.
    for val in [3, 4, 5, 2, 3]:
        SurveyResponse.objects.create(
            survey=delphi_survey,
            answers={str(delphi_survey._q_likert.id): val},
        )
    # Close round 1.
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()

    client.force_login(owner)
    url = reverse(
        "surveys:delphi_generate_feedback", kwargs={"slug": delphi_survey.slug}
    )
    res = client.post(url, {"round_id": str(delphi_survey._r1.id)})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["llm_used"] is False
    # Feedback rows created.
    feedback = list(DelphiRoundFeedback.objects.filter(round=delphi_survey._r1))
    assert len(feedback) >= 1
    # The likert question should have stats.
    likert_fb = next(f for f in feedback if f.question_id == delphi_survey._q_likert.id)
    assert likert_fb.stats_json["count"] == 5
    assert likert_fb.llm_generated is False


@pytest.mark.django_db
def test_generate_feedback_requires_closed_round(client, delphi_survey, owner):
    """Cannot generate feedback for an open round."""
    client.force_login(owner)
    url = reverse(
        "surveys:delphi_generate_feedback", kwargs={"slug": delphi_survey.slug}
    )
    res = client.post(url, {"round_id": str(delphi_survey._r1.id)})
    assert res.status_code == 400
    assert "Close the round" in res.json()["error"]


@pytest.mark.django_db
def test_generate_feedback_not_delphi_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-fb",
    )
    client.force_login(owner)
    url = reverse("surveys:delphi_generate_feedback", kwargs={"slug": s.slug})
    res = client.post(url, {"round_id": "1"})
    assert res.status_code == 400


@pytest.mark.django_db
def test_generate_feedback_invalid_round_id(client, delphi_survey, owner):
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()
    client.force_login(owner)
    url = reverse(
        "surveys:delphi_generate_feedback", kwargs={"slug": delphi_survey.slug}
    )
    res = client.post(url, {"round_id": "99999"})
    assert res.status_code == 404


@pytest.mark.django_db
def test_generate_feedback_replaces_existing(client, delphi_survey, owner):
    """Regenerating feedback deletes old rows and creates new ones."""
    SurveyResponse.objects.create(
        survey=delphi_survey, answers={str(delphi_survey._q_likert.id): 3}
    )
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()

    client.force_login(owner)
    url = reverse(
        "surveys:delphi_generate_feedback", kwargs={"slug": delphi_survey.slug}
    )
    # First generation.
    client.post(url, {"round_id": str(delphi_survey._r1.id)})
    assert DelphiRoundFeedback.objects.filter(round=delphi_survey._r1).count() >= 1
    # Add more responses.
    SurveyResponse.objects.create(
        survey=delphi_survey, answers={str(delphi_survey._q_likert.id): 5}
    )
    # Second generation.
    client.post(url, {"round_id": str(delphi_survey._r1.id)})
    feedback = DelphiRoundFeedback.objects.get(
        round=delphi_survey._r1, question=delphi_survey._q_likert
    )
    assert feedback.stats_json["count"] == 2


# --- delphi_download_comments endpoint ---


@pytest.mark.django_db
def test_download_comments_returns_csv(client, delphi_survey, owner):
    """Download comments returns a CSV with the free-text responses."""
    SurveyResponse.objects.create(
        survey=delphi_survey, answers={str(delphi_survey._q_text.id): "First comment"}
    )
    SurveyResponse.objects.create(
        survey=delphi_survey, answers={str(delphi_survey._q_text.id): "Second comment"}
    )
    client.force_login(owner)
    url = reverse(
        "surveys:delphi_download_comments", kwargs={"slug": delphi_survey.slug}
    )
    res = client.get(url, {"round_id": str(delphi_survey._r1.id)})
    assert res.status_code == 200
    assert res["Content-Type"] == "text/csv"
    assert "attachment" in res["Content-Disposition"]
    body = res.content.decode()
    assert "question,response" in body
    assert "Explain" in body
    assert "First comment" in body
    assert "Second comment" in body


@pytest.mark.django_db
def test_download_comments_not_delphi_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-dl",
    )
    client.force_login(owner)
    url = reverse("surveys:delphi_download_comments", kwargs={"slug": s.slug})
    res = client.get(url, {"round_id": "1"})
    assert res.status_code == 400


@pytest.mark.django_db
def test_download_comments_invalid_round_id(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse(
        "surveys:delphi_download_comments", kwargs={"slug": delphi_survey.slug}
    )
    res = client.get(url, {"round_id": "99999"})
    assert res.status_code == 404


@pytest.mark.django_db
def test_download_comments_empty_round(client, delphi_survey, owner):
    """A round with no text questions returns a header-only CSV."""
    # Create a round with only a likert question.
    g = QuestionGroup.objects.create(name="QuantOnly", owner=owner)
    delphi_survey.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=delphi_survey,
        group=g,
        text="Rate",
        type=SurveyQuestion.Types.LIKERT,
        order=0,
    )
    rnd = DelphiRound.objects.create(
        menu=delphi_survey._menu,
        order=2,
        name="Quant",
        start_offset_days=14,
        end_offset_days=21,
    )
    rnd.groups.add(g)
    client.force_login(owner)
    url = reverse(
        "surveys:delphi_download_comments", kwargs={"slug": delphi_survey.slug}
    )
    res = client.get(url, {"round_id": str(rnd.id)})
    assert res.status_code == 200
    body = res.content.decode()
    # Header only, no data rows.
    lines = body.strip().split("\n")
    assert lines[0] == "question,response"
    assert len(lines) == 1


# --- content block body_md substitution ---


@pytest.mark.django_db
def test_content_block_substitutes_feedback_body(client, delphi_survey, owner):
    """A content block marked as delphi feedback renders the cached stats."""
    # Create feedback for round 1 (the previous round).
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()
    DelphiRoundFeedback.objects.create(
        round=delphi_survey._r1,
        question=delphi_survey._q_likert,
        stats_json={
            "question_type": "likert",
            "count": 5,
            "median": 3.5,
            "q1": 2.0,
            "q3": 4.0,
        },
    )
    # Preview the survey (round 2's groups, which contains the feedback block).
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    res = client.get(url, {"simulate_round": str(delphi_survey._r2.id)})
    assert res.status_code == 200
    html = res.content.decode()
    # The content block should show the feedback summary, not the authored placeholder.
    assert "Median" in html
    assert "3.5" in html
    assert "Authored placeholder." not in html


@pytest.mark.django_db
def test_content_block_without_feedback_flag_not_substituted(
    client, delphi_survey, owner
):
    """A content block not marked as feedback renders its authored body."""
    # Remove the feedback flag.
    delphi_survey._q_feedback.options = {
        "heading": "Info",
        "body_md": "Authored content.",
        "is_delphi_feedback": False,
    }
    delphi_survey._q_feedback.save()
    delphi_survey._r1.closed_at = timezone.now()
    delphi_survey._r1.save()
    DelphiRoundFeedback.objects.create(
        round=delphi_survey._r1,
        question=delphi_survey._q_likert,
        stats_json={"question_type": "likert", "count": 5, "median": 3.5},
    )
    # Preview the survey (round 2's groups).
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    res = client.get(url, {"simulate_round": str(delphi_survey._r2.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "Authored content." in html
