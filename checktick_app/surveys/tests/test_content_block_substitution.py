"""Tests for ``{{<dimension>}}`` placeholder substitution in content blocks
(commit 1 of content block category substitution, issue #349).

The live take path substitutes content block heading / subtitle / body_md
placeholders with the participant's resolved respondent-category values
(token-borne values via ``_resolve_categories_for_progress``). See
docs/content-block-category-substitution-implementation-plan.md
§Substitution contract.
"""

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    DelphiRoundFeedback,
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyQuestion,
)
from checktick_app.surveys.views import (
    _annotate_question_render_sequence,
    _substitute_category_placeholders,
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


def _make_survey(
    owner,
    org,
    *,
    heading="360° feedback for {{subject}}",
    subtitle="You are rating {{subject}}",
    body_md="Thank you for rating {{subject}} in this round.",
):
    """A published token-visibility survey with a ``subject`` category
    dimension (roster of clinician names) and an intro content block
    carrying ``{{subject}}`` placeholders."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="360 Substitution",
        slug="360-substitution",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    g_intro = QuestionGroup.objects.create(name="Intro", owner=owner)
    g_questions = QuestionGroup.objects.create(name="Questions", owner=owner)
    s.question_groups.add(g_intro, g_questions)
    SurveyQuestion.objects.create(
        survey=s,
        group=g_intro,
        text="Introduction",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"heading": heading, "subtitle": subtitle, "body_md": body_md},
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_questions,
        text="Clinical knowledge",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="subject",
        label="Subject",
        allowed_values=["Dr Jane Smith", "Dr John Doe"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    return s


def _take_token_url(survey, token):
    return reverse(
        "surveys:take_token", kwargs={"slug": survey.slug, "token": token.token}
    )


# --- Helper (pure function) ---


def test_helper_none_map_returns_text_unchanged():
    """category_values=None means no substitution (builder detail path)."""
    text = "Feedback for {{subject}}"
    assert _substitute_category_placeholders(text, None, {"subject"}) == text


def test_helper_unknown_dimension_left_literal():
    """A typo like {{subjekt}} renders visibly so the author catches it."""
    out = _substitute_category_placeholders(
        "For {{subjekt}}", {"subject": "Dr Jane Smith"}, {"subject"}
    )
    assert out == "For {{subjekt}}"


def test_helper_unresolved_known_dimension_empty():
    """Known but unresolved → empty string (unresolved = not shown)."""
    out = _substitute_category_placeholders("For {{subject}}", {}, {"subject"})
    assert out == "For "


def test_helper_resolved_value_substituted():
    out = _substitute_category_placeholders(
        "For {{subject}}", {"subject": "Dr Jane Smith"}, {"subject"}
    )
    assert out == "For Dr Jane Smith"


def test_helper_escape_values_entity_encodes():
    out = _substitute_category_placeholders(
        "Hi {{subject}}",
        {"subject": '<b>&"'},
        {"subject"},
        escape_values=True,
    )
    assert out == "Hi &lt;b&gt;&amp;&quot;"


def test_helper_no_escape_by_default():
    """Plain-text fields substitute the raw value (template auto-escapes)."""
    out = _substitute_category_placeholders(
        "Hi {{subject}}", {"subject": "<b>"}, {"subject"}
    )
    assert out == "Hi <b>"


# --- Live take path (walkthrough) ---


@pytest.mark.django_db
def test_walkthrough_token_substitutes_subject(client, owner, org):
    """Author defines the roster → content block with {{subject}} → token
    batch → rater takes the survey → heading/subtitle/body show the
    clinician's name."""
    s = _make_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-walkthrough",
        created_by=owner,
        category_values={"subject": "Dr Jane Smith"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for Dr Jane Smith" in html
    assert "You are rating Dr Jane Smith" in html
    assert "Thank you for rating Dr Jane Smith in this round." in html
    assert "{{subject}}" not in html


@pytest.mark.django_db
def test_unresolved_dimension_renders_empty(client, owner, org):
    """A token whose batch carries no subject value → the placeholder
    renders empty, never as a bare {{subject}}."""
    s = _make_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-unresolved",
        created_by=owner,
        category_values={},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "{{subject}}" not in html
    assert "360° feedback for " in html
    assert "Thank you for rating  in this round." in html


@pytest.mark.django_db
def test_unknown_placeholder_left_literal_on_live_path(client, owner, org):
    """A typo'd dimension is not defined on the survey → left literal so
    the author catches it in preview before publishing."""
    s = _make_survey(
        owner,
        org,
        heading="Feedback for {{subjekt}}",
        subtitle="Static subtitle",
        body_md="Thanks for taking part.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-typo",
        created_by=owner,
        category_values={"subject": "Dr Jane Smith"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "{{subjekt}}" in html
    assert "Dr Jane Smith" not in html


@pytest.mark.django_db
def test_substituted_value_is_html_escaped(client, owner, org):
    """The substituted value is author-entered and flows into markdown-
    rendered HTML — it must be entity-escaped on every path (issue #349
    privacy notes)."""
    s = _make_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-escape",
        created_by=owner,
        category_values={"subject": 'Dr <b>"Smith"</b> & Co'},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    escaped = "Dr &lt;b&gt;&quot;Smith&quot;&lt;/b&gt; &amp; Co"
    # Heading/subtitle (template auto-escape) and body (escape() at
    # substitution) both entity-encode the value.
    assert html.count(escaped) >= 3
    assert 'Dr <b>"Smith"</b> & Co' not in html


@pytest.mark.django_db
def test_none_map_leaves_placeholders_literal(owner, org):
    """category_values=None means no substitution — the builder detail path
    (survey_detail) passes no map, so the author sees the raw placeholder
    exactly as typed."""
    s = _make_survey(owner, org)
    q = s.questions.filter(type=SurveyQuestion.Types.CONTENT_BLOCK).first()
    qs = _annotate_question_render_sequence(s, [q], None)
    assert qs[0].content_block_heading == "360° feedback for {{subject}}"
    assert qs[0].content_block_subtitle == "You are rating {{subject}}"
    assert "{{subject}}" in str(qs[0].content_block_html)


# --- Delphi inter-round feedback (issue #349 edge case 1) ---


@pytest.mark.django_db
def test_delphi_feedback_body_not_substituted(owner, org):
    """Substitution applies to author-written text only: the heading is
    substituted, the system-generated feedback body is not."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Delphi Sub",
        slug="delphi-sub",
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
    q_feedback = SurveyQuestion.objects.create(
        survey=s,
        group=g_r2,
        text="Feedback",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        order=0,
        options={
            "heading": "Feedback for {{subject}}",
            "body_md": "Authored {{subject}} body.",
            "is_delphi_feedback": True,
        },
    )
    RespondentCategory.objects.create(
        survey=s,
        name="subject",
        allowed_values=["Dr Jane Smith"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(g_r1)
    r1.closed_at = timezone.now()
    r1.save()
    DelphiRoundFeedback.objects.create(
        round=r1,
        question=q_likert,
        stats_json={"question_type": "likert", "count": 5, "median": 3.5},
    )

    qs = _annotate_question_render_sequence(
        s, [q_likert, q_feedback], {"subject": "Dr Jane Smith"}
    )
    fb = qs[1]
    # Author-written heading substitutes.
    assert fb.content_block_heading == "Feedback for Dr Jane Smith"
    # The generated feedback body is system-produced — never substituted.
    body_html = str(fb.content_block_html)
    assert "Dr Jane Smith" not in body_html
    assert "{{subject}}" not in body_html
