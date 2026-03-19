"""
XSS tests for the public-facing survey completion forms.

These tests verify that user-controlled data (survey metadata, question text,
question options, branching condition values, and participant-submitted partial
answers) is always safely encoded in the rendered HTML and never injected raw
into the page.

Surfaces tested:
  - GET /surveys/<slug>/take/               (Visibility.PUBLIC)
  - GET /surveys/<slug>/take/unlisted/<key>/ (Visibility.UNLISTED)
  - GET /surveys/<slug>/take/token/<token>/  (Visibility.TOKEN)

Encoding guarantees verified:
  1. Survey name / description reflected via Django's default auto-escaping.
  2. Question text and option labels/values (displayed in form inputs and labels).
  3. data-branching-config attribute — JSON serialised & auto-escaped so none of
     the raw payload characters break out of the HTML attribute.
  4. Saved partial answers — reflected via Django's json_script filter, which
     encodes <, >, &, ' as Unicode escape sequences inside the JSON payload.
  5. Question group names shown as <legend> text — additionally stripped of HTML
     tags server-side before storage.
"""

from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    Survey,
    SurveyAccessToken,
    SurveyProgress,
    SurveyQuestion,
    SurveyQuestionCondition,
)

# Common XSS payloads that cover the most common injection patterns.
SCRIPT_TAG = "<script>alert('xss')</script>"
SCRIPT_BREAK_OUT = "</script><script>alert(1)</script>"
ATTR_BREAK_OUT = '" onmouseover="alert(1)" data-x="'
SINGLE_QUOTE_BREAK = "' onmouseover='alert(1)' x='"

# The raw <script> opening tag must never appear verbatim in safe HTML.
RAW_SCRIPT_OPEN = b"<script>alert"
# The escaped form that proves Django did encode the payload.
ESCAPED_LT = b"&lt;"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable django-ratelimit for all tests in this module."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="xss_owner@example.com", password="securepass"
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="XSS Test Org", owner=owner)


@pytest.fixture
def public_survey(owner, org):
    """A live PUBLIC survey whose metadata contain XSS payloads."""
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name=f"Test Survey {SCRIPT_TAG}",
        description=f"A description {SCRIPT_TAG}",
        slug="xss-public-test",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )


@pytest.fixture
def public_survey_with_questions(public_survey):
    """PUBLIC survey with several question types, each carrying XSS payloads."""
    SurveyQuestion.objects.create(
        survey=public_survey,
        text=f"What is {SCRIPT_TAG}?",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=public_survey,
        text="Pick one",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[
            {"value": SCRIPT_TAG, "label": SCRIPT_TAG},
            {"value": "safe", "label": "Safe option"},
        ],
        required=False,
        order=1,
    )
    SurveyQuestion.objects.create(
        survey=public_survey,
        text="Pick many",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_MULTI,
        options=[
            {"value": ATTR_BREAK_OUT, "label": ATTR_BREAK_OUT},
        ],
        required=False,
        order=2,
    )
    SurveyQuestion.objects.create(
        survey=public_survey,
        text="Dropdown",
        type=SurveyQuestion.Types.DROPDOWN,
        options=[
            {"value": SCRIPT_BREAK_OUT, "label": SCRIPT_BREAK_OUT},
        ],
        required=False,
        order=3,
    )
    return public_survey


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_no_raw_xss(content: bytes, payload: str = SCRIPT_TAG) -> None:
    """Assert that the raw XSS payload does not appear verbatim in HTML output."""
    # The opening <script> of the payload must not appear raw.
    assert (
        b"<script>alert" not in content
    ), "Raw <script>alert found in response — XSS payload not escaped"
    # </script> from break-out payload must not appear raw either.
    assert (
        b"</script><script>" not in content
    ), "Script break-out sequence found in response"


def _assert_xss_escaped(content: bytes) -> None:
    """Assert that at least the escaped form of < is present (proving encoding ran)."""
    assert (
        ESCAPED_LT in content or b"\\u003C" in content or b"&lt;" in content
    ), "Expected to find HTML-escaped characters but found neither &lt; nor \\u003C"


# ===========================================================================
# 1. Survey metadata (name & description)
# ===========================================================================


@pytest.mark.django_db
def test_survey_name_xss_escaped_on_take_page(client, public_survey):
    """Survey name containing <script> must be HTML-escaped, not injected raw."""
    resp = client.get(reverse("surveys:take", kwargs={"slug": public_survey.slug}))
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    # The escaped form should be present (the name IS shown on the page).
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_survey_description_xss_escaped_on_take_page(client, public_survey):
    """Survey description containing <script> must be HTML-escaped."""
    resp = client.get(reverse("surveys:take", kwargs={"slug": public_survey.slug}))
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)


# ===========================================================================
# 2. Question text and options
# ===========================================================================


@pytest.mark.django_db
def test_question_text_xss_escaped(client, public_survey_with_questions):
    """Question text with XSS payload must be escaped in the rendered form."""
    resp = client.get(
        reverse("surveys:take", kwargs={"slug": public_survey_with_questions.slug})
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_mc_option_value_xss_escaped_in_radio_input(
    client, public_survey_with_questions
):
    """
    Multiple-choice option values are rendered as the value= attribute of
    <input type="radio">. A payload like <script>... must appear as &lt;script&gt;,
    not raw, so it cannot be used as an attribute injection.
    """
    resp = client.get(
        reverse("surveys:take", kwargs={"slug": public_survey_with_questions.slug})
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    # Confirm the escaped label IS present (the option is being rendered).
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_mc_option_attr_break_out_escaped(client, public_survey_with_questions):
    """
    An option value designed to break out of an HTML attribute
    (e.g. '" onmouseover="...') must be escaped so the double-quote appears
    as &quot; and cannot close the value="" attribute.
    """
    resp = client.get(
        reverse("surveys:take", kwargs={"slug": public_survey_with_questions.slug})
    )
    assert resp.status_code == 200
    # Raw unescaped double-quote followed by space+on... would be the break-out.
    assert (
        b'" onmouseover="' not in resp.content
    ), "Attribute break-out sequence found in response"


@pytest.mark.django_db
def test_dropdown_option_xss_escaped(client, public_survey_with_questions):
    """Dropdown <option> values and labels with </script> must be escaped."""
    resp = client.get(
        reverse("surveys:take", kwargs={"slug": public_survey_with_questions.slug})
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)


# ===========================================================================
# 3. Question group names rendered as <legend> in the form
# ===========================================================================


@pytest.mark.django_db
def test_question_group_name_xss_escaped_in_fieldset(client, owner, org):
    """
    Group names with XSS payloads must appear escaped in the survey form.
    They are also stripped of HTML tags server-side when created (defence-in-depth),
    but this test checks the rendering layer.
    """
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(
        name=SCRIPT_TAG,
        description=f"Group desc {SCRIPT_TAG}",
        owner=owner,
    )
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Group XSS Survey",
        slug="group-xss-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Q1",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)


# ===========================================================================
# 4. data-branching-config HTML attribute
# ===========================================================================


@pytest.mark.django_db
def test_branching_config_condition_value_escaped_in_attribute(client, owner, org):
    """
    Branching condition values containing double-quotes or </script> sequences
    must not break out of the data-branching-config="..." attribute.

    The JSON is URL-safe-escaped by Django auto-escaping: " → &quot;
    so the attribute boundary cannot be crossed.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Branching XSS Survey",
        slug="branching-xss-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q1 = SurveyQuestion.objects.create(
        survey=survey,
        text="Q1",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}],
        required=False,
        order=0,
    )
    q2 = SurveyQuestion.objects.create(
        survey=survey,
        text="Q2",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=1,
    )
    # Condition value containing both a double-quote and a </script> sequence.
    SurveyQuestionCondition.objects.create(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value=f'yes" onmouseover="evil {SCRIPT_BREAK_OUT}',
        target_question=q2,
        action=SurveyQuestionCondition.Action.SHOW,
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The raw double-quote break-out must not appear.
    assert (
        b'" onmouseover="evil' not in resp.content
    ), "Attribute break-out via condition value found in branching-config"
    # The </script><script> break-out must not appear raw.
    assert (
        b"</script><script>" not in resp.content
    ), "Script break-out sequence found in branching-config"


# ===========================================================================
# 5. Saved partial answers reflected via json_script
# ===========================================================================


@pytest.mark.django_db
def test_saved_answers_xss_encoded_via_json_script(client, owner, org):
    """
    Partial answers stored in SurveyProgress (from a previous visit) are
    reflected back via Django's json_script filter.  That filter encodes
    <, >, &, ' as Unicode escape sequences (\\u003C etc.), so the payload
    can never be treated as HTML by the browser.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Progress XSS Survey",
        slug="progress-xss-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    # Seed a progress record with an XSS payload as a stored partial answer.
    client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    session_key = client.session.session_key
    assert session_key, "Session was not created on first visit"

    SurveyProgress.objects.filter(survey=survey, session_key=session_key).update(
        partial_answers={str(q.id): SCRIPT_TAG},
        answered_count=1,
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The raw <script> tag must not appear in the response.
    assert (
        RAW_SCRIPT_OPEN not in resp.content
    ), "Raw XSS payload found in saved_answers output — json_script not applied"
    # Django's json_script encodes < as \\u003C inside the JSON element.
    assert (
        b"\\u003C" in resp.content or b"\\u003c" in resp.content
    ), "Expected json_script Unicode-escaped output not found for < character"


@pytest.mark.django_db
def test_saved_answers_double_quote_encoded_via_json_script(client, owner, org):
    """
    Double-quotes in saved answers must be JSON-string-escaped (as \") inside
    the <script type="application/json"> element — they cannot terminate
    the JSON string and inject additional keys or break out of the script element.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Progress DQuote Survey",
        slug="progress-dquote-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    session_key = client.session.session_key

    # Payload that could act as JSON injection if not encoded.
    SurveyProgress.objects.filter(survey=survey, session_key=session_key).update(
        partial_answers={str(q.id): '", "injected": "value'},
        answered_count=1,
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The literal injection key must not appear as a separate JSON key.
    assert (
        b'"injected"' not in resp.content
    ), "JSON injection via saved_answers double-quote not encoded"


# ===========================================================================
# 6. Unlisted survey route
# ===========================================================================


@pytest.mark.django_db
def test_unlisted_survey_escapes_xss_in_name(client, owner, org):
    """The unlisted (secret-link) take route also escapes XSS in survey metadata."""
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name=f"Unlisted {SCRIPT_TAG}",
        slug="unlisted-xss",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.UNLISTED,
        unlisted_key="supersecretkey",
    )

    resp = client.get(
        reverse(
            "surveys:take_unlisted",
            kwargs={"slug": survey.slug, "key": survey.unlisted_key},
        )
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_unlisted_survey_escapes_question_text(client, owner, org):
    """Unlisted-route question text with XSS payload must be escaped."""
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Unlisted Q XSS",
        slug="unlisted-q-xss",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.UNLISTED,
        unlisted_key="anotherkey123",
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text=SCRIPT_TAG,
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    resp = client.get(
        reverse(
            "surveys:take_unlisted",
            kwargs={"slug": survey.slug, "key": survey.unlisted_key},
        )
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    assert b"&lt;script&gt;" in resp.content


# ===========================================================================
# 7. Token-based survey route
# ===========================================================================


@pytest.mark.django_db
def test_token_survey_escapes_xss_in_name(client, owner, org):
    """The token-invite take route escapes XSS in survey name."""
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name=f"Token Survey {SCRIPT_TAG}",
        slug="token-xss",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    token_obj = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-abc-123",
        created_by=owner,
        expires_at=timezone.now() + timedelta(days=1),
    )

    resp = client.get(
        reverse(
            "surveys:take_token",
            kwargs={"slug": survey.slug, "token": token_obj.token},
        )
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_token_survey_escapes_question_options(client, owner, org):
    """Token-route question options with XSS payloads must be escaped."""
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Token Q Opts XSS",
        slug="token-q-xss",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text="Choose one",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[{"value": SCRIPT_TAG, "label": SCRIPT_TAG}],
        required=False,
        order=0,
    )
    token_obj = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-xyz-999",
        created_by=owner,
        expires_at=timezone.now() + timedelta(days=1),
    )

    resp = client.get(
        reverse(
            "surveys:take_token",
            kwargs={"slug": survey.slug, "token": token_obj.token},
        )
    )
    assert resp.status_code == 200
    _assert_no_raw_xss(resp.content)


# ===========================================================================
# 8. Closed page does not reflect URL query parameter
# ===========================================================================


@pytest.mark.django_db
def test_closed_page_does_not_reflect_reason_param(client, owner, org):
    """
    The survey closed page accepts a ?reason= query parameter but uses it only
    for conditional logic ({% if reason == '...' %}).  An arbitrary value
    such as a script tag must never be echoed back into the page.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Closed XSS Survey",
        slug="closed-xss-survey",
        status=Survey.Status.CLOSED,
        visibility=Survey.Visibility.PUBLIC,
    )

    url = reverse("surveys:closed", kwargs={"slug": survey.slug})
    resp = client.get(f"{url}?reason={SCRIPT_TAG}")
    assert resp.status_code == 200
    # The payload must not appear raw in the page.
    assert (
        RAW_SCRIPT_OPEN not in resp.content
    ), "XSS payload from ?reason= parameter was reflected into the page"


# ===========================================================================
# 9. POST — submitted answers stored safely, not echoed in same response
# ===========================================================================


@pytest.mark.django_db
def test_post_submission_redirects_without_echoing_answers(client, owner, org):
    """
    On a valid POST submission the view redirects to the thank-you page.
    Submitted answer content (including XSS payloads) is never echoed back
    in the same HTTP response — it is stored in the database only.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Submit XSS Survey",
        slug="submit-xss-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": SCRIPT_TAG},
    )
    # Must redirect to thank-you, not re-render the form with the payload.
    assert resp.status_code == 302
    assert "thank" in resp["Location"] or survey.slug in resp["Location"]


@pytest.mark.django_db
def test_thank_you_page_does_not_echo_submitted_answers(client, owner, org):
    """
    The thank-you page must not reflect any submitted answer data.
    It should only contain a generic confirmation message.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Thankyou XSS Survey",
        slug="ty-xss-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": SCRIPT_TAG},
    )

    resp = client.get(reverse("surveys:thank_you", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert RAW_SCRIPT_OPEN not in resp.content
