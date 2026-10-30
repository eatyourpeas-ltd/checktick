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


# --- Helper: |default fallback (issue #351) ---


def test_helper_default_renders_when_unresolved():
    """``{{dim|default:text}}`` renders the default when the dimension is
    known but unresolved (issue #351)."""
    out = _substitute_category_placeholders(
        "Feedback for {{subject|default:your colleague}}", {}, {"subject"}
    )
    assert out == "Feedback for your colleague"


def test_helper_default_ignored_when_resolved():
    """A resolved value always wins over the default."""
    out = _substitute_category_placeholders(
        "Feedback for {{subject|default:your colleague}}",
        {"subject": "Dr Jane Smith"},
        {"subject"},
    )
    assert out == "Feedback for Dr Jane Smith"


def test_helper_default_empty_value_falls_back():
    """An empty-string value counts as unresolved → the default renders."""
    out = _substitute_category_placeholders(
        "For {{subject|default:your colleague}}", {"subject": ""}, {"subject"}
    )
    assert out == "For your colleague"


def test_helper_default_not_applied_to_unknown_dimension():
    """The default must not mask a typo: an unknown dimension stays literal,
    ``|default:`` segment included (issue #351)."""
    out = _substitute_category_placeholders(
        "For {{subjekt|default:your colleague}}",
        {"subject": "Dr Jane Smith"},
        {"subject"},
    )
    assert out == "For {{subjekt|default:your colleague}}"


def test_helper_default_as_rendered_on_body_path():
    """The ``escape_values=True`` (body_md) path substitutes the default
    as-rendered: by substitution time markdown has already escaped and
    sanitised it with the surrounding body (``&`` → ``&amp;``), so it is
    never re-escaped — that would double-encode to ``&amp;amp;``. Values
    are still escaped (test_helper_escape_values_entity_encodes): they
    are participant data, not authored source text."""
    rendered = "Hi {{subject|default:Tom &amp; Jerry}}"
    out = _substitute_category_placeholders(
        rendered, {}, {"subject"}, escape_values=True
    )
    assert out == "Hi Tom &amp; Jerry"


def test_helper_default_empty_renders_empty():
    """``{{dim|default:}}`` (empty fallback) renders empty — same as no
    default (unresolved = not shown)."""
    out = _substitute_category_placeholders("For {{subject|default:}}", {}, {"subject"})
    assert out == "For "


def test_helper_default_literal_when_no_map():
    """category_values=None (builder path) leaves the default syntax
    exactly as typed — no substitution at all."""
    text = "For {{subject|default:your colleague}}"
    assert _substitute_category_placeholders(text, None, {"subject"}) == text


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
def test_unresolved_dimension_renders_default(client, owner, org):
    """A token batch with no subject value shows the block's ``|default:``
    fallback instead of an empty heading (issue #351)."""
    s = _make_survey(
        owner,
        org,
        heading="360° feedback for {{subject|default:your colleague}}",
        subtitle="You are rating {{subject|default:your colleague}}",
        body_md="Thank you for rating {{subject|default:your colleague}} in this round.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-default",
        created_by=owner,
        category_values={},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for your colleague" in html
    assert "You are rating your colleague" in html
    assert "Thank you for rating your colleague in this round." in html
    assert "{{subject|default:" not in html


@pytest.mark.django_db
def test_resolved_value_beats_default(client, owner, org):
    """When the dimension resolves, the value wins and the default never
    leaks into the render."""
    s = _make_survey(
        owner,
        org,
        heading="360° feedback for {{subject|default:your colleague}}",
        subtitle="You are rating {{subject|default:your colleague}}",
        body_md="Thank you for rating {{subject|default:your colleague}} in this round.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-default-resolved",
        created_by=owner,
        category_values={"subject": "Dr Jane Smith"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for Dr Jane Smith" in html
    assert "your colleague" not in html


@pytest.mark.django_db
def test_unknown_dim_with_default_left_literal(client, owner, org):
    """A typo'd dimension stays literal on the live path even with a
    ``|default:`` — the default must not mask the error (issue #351)."""
    s = _make_survey(
        owner,
        org,
        heading="Feedback for {{subjekt|default:your colleague}}",
        subtitle="Static subtitle",
        body_md="Thanks for taking part.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-default-typo",
        created_by=owner,
        category_values={"subject": "Dr Jane Smith"},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "{{subjekt|default:your colleague}}" in html
    # The default never renders as substituted text — only as the literal
    # placeholder the author must catch in preview.
    assert "Feedback for your colleague" not in html
    assert "Dr Jane Smith" not in html


@pytest.mark.django_db
def test_live_default_is_escaped(client, owner, org):
    """The default text is author-entered and flows into rendered HTML —
    on the heading path the template auto-escapes it (issue #351)."""
    s = _make_survey(
        owner,
        org,
        heading='Feedback for {{subject|default:Dr <b>"Smith"</b> & Co}}',
        subtitle="Static subtitle",
        body_md="Thanks for taking part.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-default-esc",
        created_by=owner,
        category_values={},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Feedback for Dr &lt;b&gt;&quot;Smith&quot;&lt;/b&gt; &amp; Co" in html
    assert 'Dr <b>"Smith"</b> & Co' not in html


@pytest.mark.django_db
def test_live_default_body_path_no_double_escape(client, owner, org):
    """On the body_md path the default renders as-authored: markdown has
    already escaped it (``&`` → ``&amp;``) when the body was rendered, so
    the placeholder substitutes it as-rendered — never double-encoded
    (issue #351)."""
    s = _make_survey(
        owner,
        org,
        heading="Welcome",
        subtitle="Static subtitle",
        body_md="Thank you for rating {{subject|default:Tom & Jerry}} in this round.",
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-default-body",
        created_by=owner,
        category_values={},
    )
    res = client.get(_take_token_url(s, token))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Thank you for rating Tom &amp; Jerry in this round." in html
    assert "Tom &amp;amp; Jerry" not in html
    assert "{{subject|default:" not in html


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


# --- Preview path (commit 2) ---


@pytest.mark.django_db
def test_preview_simulate_substitutes_placeholders(client, owner, org):
    """The simulate panel is the documented way to see substituted values:
    ?simulate_category= drives substitution on the preview path."""
    s = _make_survey(owner, org)
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": s.slug}),
        {"simulate_category": "subject:Dr Jane Smith"},
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for Dr Jane Smith" in html
    assert "You are rating Dr Jane Smith" in html
    assert "Thank you for rating Dr Jane Smith in this round." in html
    assert "{{subject}}" not in html


@pytest.mark.django_db
def test_preview_without_simulate_renders_empty(client, owner, org):
    """Without simulated values the preview behaves like the live path:
    known-but-unresolved placeholders render empty (issue #349 edge case 3)."""
    s = _make_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "{{subject}}" not in html
    assert "360° feedback for " in html


@pytest.mark.django_db
def test_preview_unresolved_renders_default(client, owner, org):
    """Without simulated values the preview shows the block's ``|default:``
    fallback, never a bare placeholder (issue #351) — same semantics as the
    live path."""
    s = _make_survey(
        owner,
        org,
        heading="360° feedback for {{subject|default:your colleague}}",
        subtitle="You are rating {{subject|default:your colleague}}",
        body_md="Thank you for rating {{subject|default:your colleague}} in this round.",
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for your colleague" in html
    assert "You are rating your colleague" in html
    assert "Thank you for rating your colleague in this round." in html
    assert "{{subject|default:" not in html
    # A default-carrying placeholder still triggers the Simulate category
    # hint (the same regex powers has_placeholders).
    assert "category placeholders" in html


@pytest.mark.django_db
def test_preview_simulate_overrides_default(client, owner, org):
    """A simulated value wins over the ``|default:`` fallback, so the author
    can see both renderings from the Simulate category panel (issue #351)."""
    s = _make_survey(
        owner,
        org,
        heading="360° feedback for {{subject|default:your colleague}}",
        subtitle="You are rating {{subject|default:your colleague}}",
        body_md="Thank you for rating {{subject|default:your colleague}} in this round.",
    )
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": s.slug}),
        {"simulate_category": "subject:Dr Jane Smith"},
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "360° feedback for Dr Jane Smith" in html
    assert "your colleague" not in html


@pytest.mark.django_db
def test_preview_shows_placeholder_hint(client, owner, org):
    """When a content block carries a placeholder, the Simulate category
    panel explains how to see it substituted."""
    s = _make_survey(owner, org)
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate category" in html
    assert "category placeholders" in html


@pytest.mark.django_db
def test_preview_no_hint_without_placeholders(client, owner, org):
    """No placeholder in any content block → no hint."""
    s = _make_survey(
        owner,
        org,
        heading="Welcome",
        subtitle="Static subtitle",
        body_md="Thanks for taking part.",
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate category" in html
    assert "category placeholders" not in html


# --- Thank-you echo (commit 3) ---


def _submit_via_token(client, survey, token, answer="Excellent"):
    """Walk the take flow: GET (creates progress + resolves categories),
    then POST the single text answer. Returns the POST response."""
    url = _take_token_url(survey, token)
    assert client.get(url).status_code == 200
    text_q = survey.questions.filter(type=SurveyQuestion.Types.TEXT).first()
    return client.post(url, {f"q_{text_q.id}": answer})


@pytest.mark.django_db
def test_thank_you_echoes_resolved_categories(client, owner, org):
    """After submitting, the thank-you page echoes the resolved values (the
    rater's own context) next to the receipt token — one-time display."""
    s = _make_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-thanks",
        created_by=owner,
        category_values={"subject": "Dr Jane Smith"},
    )
    res = _submit_via_token(client, s, token)
    assert res.status_code == 302
    assert "/thank-you/" in res.url

    res = client.get(reverse("surveys:thank_you", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Subject: Dr Jane Smith" in html

    # One-time display — a second visit does not echo again.
    res = client.get(reverse("surveys:thank_you", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    assert "Dr Jane Smith" not in res.content.decode()


@pytest.mark.django_db
def test_thank_you_echo_is_escaped(client, owner, org):
    """The echoed values are author-entered category values — the badges
    must be auto-escaped."""
    s = _make_survey(owner, org)
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-sub-thanks-esc",
        created_by=owner,
        category_values={"subject": 'Dr <b>"Smith"</b>'},
    )
    res = _submit_via_token(client, s, token)
    assert res.status_code == 302
    res = client.get(reverse("surveys:thank_you", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Subject: Dr &lt;b&gt;&quot;Smith&quot;&lt;/b&gt;" in html
    assert 'Dr <b>"Smith"</b>' not in html


@pytest.mark.django_db
def test_thank_you_no_echo_without_submission(client, owner, org):
    """A direct GET of the thank-you page (no submission in this session)
    shows no category echo."""
    s = _make_survey(owner, org)
    res = client.get(reverse("surveys:thank_you", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Your response was recorded with the following details" not in html
    assert "Dr Jane Smith" not in html
