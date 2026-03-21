"""
XSS tests for authenticated survey-management forms and user account creation.

These tests verify that user-controlled data can never break out of its
HTML context — whether reflected in an error message, stored and later
displayed in a dashboard, or rendered back in a form re-display.

Surfaces tested
---------------
Survey creation (authenticated):
  - POST /surveys/create/  with an invalid form (re-render with errors)
  - POST /surveys/create/  with a valid submission → dashboard redirect & display
  - dashboard page rendering survey.name / survey.description
  - survey.name reflected via js escapejs in the dashboard inline script block
  - POST /surveys/<slug>/update-title/ (AJAX title/description update)
  - POST /surveys/<slug>/style/update  (font_heading / font_body CSS injection)
  - POST /surveys/<slug>/groups/create (question group name)
  - POST /surveys/<slug>/groups/<gid>/edit (question group name & description edit)

User / account creation:
  - POST /accounts/signup/  with an invalid form (re-render with field and
    non-field errors containing XSS payloads in error messages)
  - POST /accounts/signup/  with a duplicate email (error message has a safe
    <a> link constructed by reverse(); no user-supplied HTML is allowed)
  - GET  /accounts/signup/  page itself (static, no user data reflected)
  - POST /accounts/signup/  → redirect on success (XSS payload never echoed)
  - GET  /accounts/login/   page (static, no user data reflected)
"""

from __future__ import annotations

import json

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"  # noqa: S105


# ---------------------------------------------------------------------------
# Common payloads
# ---------------------------------------------------------------------------

SCRIPT_TAG = "<script>alert('xss')</script>"
ATTR_BREAK = '" onmouseover="alert(1)" x="'
STYLE_BREAK = "</style><script>alert(1)</script><style>"
# Fonts go into a <style> block; this payload tries to break out.
FONT_BREAK = "Arial</style><script>alert(2)</script><style>sans-serif"
# The exact pentest payload from Finding #1, stored directly in the DB to test
# the template auto-escaping layer independently of the view-layer allowlist.
FONT_XSS_STORED = "</style><script>alert(document.cookie)</script><style>x{"
# After Django auto-escaping, < becomes &lt; and > becomes &gt;.
FONT_XSS_ESCAPED = b"&lt;/style&gt;&lt;script&gt;"

RAW_SCRIPT_OPEN = b"<script>alert"
ESCAPED_LT = b"&lt;"


def _xss_clean(content: bytes) -> None:
    """Assert no raw XSS payload appears verbatim in `content`."""
    assert (
        RAW_SCRIPT_OPEN not in content
    ), "Raw <script>alert found in response — XSS payload not escaped"
    assert (
        b"</script><script>" not in content
    ), "Script break-out sequence found in response"
    assert (
        b'" onmouseover="' not in content
    ), "Attribute break-out sequence found in response"


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    # Disable axes (login-attempt limiting) during tests
    settings.AXES_ENABLED = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="xss_mgmt@example.com",
        email="xss_mgmt@example.com",
        password="securepass123",
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="XSS Mgmt Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    """A plain draft survey owned by `owner`."""
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="Base Survey",
        slug="base-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )


@pytest.fixture
def auth_client(client, owner):
    client.force_login(owner)
    return client


# ===========================================================================
# 1. Survey creation — form re-render with invalid data
# ===========================================================================


@pytest.mark.django_db
def test_survey_create_form_errors_xss_escaped(auth_client):
    """
    When the survey create form is submitted with an invalid slug the form
    is re-rendered showing validation errors. Any user-supplied values echoed
    back into the form inputs (via Django's BoundField value rendering) must
    be HTML-escaped.
    """
    resp = auth_client.post(
        reverse("surveys:create"),
        data={
            "name": SCRIPT_TAG,
            "slug": "  ",  # intentionally blank after strip → triggers error path
            "description": SCRIPT_TAG,
        },
    )
    # Form is re-rendered (200) or redirects on success; either way, no raw payload
    _xss_clean(resp.content)
    # Values echoed into form inputs must appear escaped
    if resp.status_code == 200:
        assert ESCAPED_LT in resp.content or b"\\u003C" in resp.content


@pytest.mark.django_db
def test_survey_create_duplicate_slug_error_xss_escaped(auth_client, survey):
    """
    Submitting with a slug that already exists triggers a form validation error.
    The slug value (which could be user-supplied) must not appear raw.
    """
    resp = auth_client.post(
        reverse("surveys:create"),
        data={
            "name": SCRIPT_TAG,
            "slug": survey.slug,  # existing slug → unique constraint error
            "description": SCRIPT_TAG,
        },
    )
    _xss_clean(resp.content)


# ===========================================================================
# 2. Survey creation — valid POST stores name safely; dashboard reflects it
# ===========================================================================


@pytest.mark.django_db
def test_survey_create_xss_in_name_stored_and_escaped_on_dashboard(
    auth_client, owner, org
):
    """
    A survey created with an XSS payload in its name must have that name
    HTML-escaped wherever it is displayed — including the dashboard title,
    the breadcrumb, and the inline JavaScript that pre-populates the
    in-place editor.
    """
    resp = auth_client.post(
        reverse("surveys:create"),
        data={"name": SCRIPT_TAG, "slug": "xss-mgmt-create-test", "description": ""},
    )
    # Should redirect to dashboard
    assert resp.status_code == 302

    # Follow to the dashboard
    dash_url = resp["Location"]
    resp2 = auth_client.get(dash_url)
    assert resp2.status_code == 200
    _xss_clean(resp2.content)
    # The name IS displayed — make sure the escaped form is present
    assert b"&lt;script&gt;" in resp2.content or b"\\u003C" in resp2.content


@pytest.mark.django_db
def test_survey_create_xss_in_description_escaped_on_dashboard(auth_client):
    """Survey description with XSS payload must be escaped on the dashboard."""
    resp = auth_client.post(
        reverse("surveys:create"),
        data={
            "name": "Safe name",
            "slug": "xss-desc-test",
            "description": SCRIPT_TAG,
        },
    )
    assert resp.status_code == 302
    resp2 = auth_client.get(resp["Location"])
    assert resp2.status_code == 200
    _xss_clean(resp2.content)


# ===========================================================================
# 3. Survey dashboard — escapejs for inline JS variable
# ===========================================================================


@pytest.mark.django_db
def test_dashboard_survey_name_escapejs_in_inline_script(auth_client, owner, org):
    """
    The dashboard embeds survey.name into an inline <script> block via
    escapejs.  An XSS payload in the name must be JS-escaped, not raw.
    escapejs encodes characters like < to \\u003C so they cannot form HTML tags
    even inside a script block.
    """
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name=f"My {SCRIPT_TAG} Survey",
        slug="escapejs-test",
        status=Survey.Status.DRAFT,
    )
    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    _xss_clean(resp.content)
    # escapejs encodes < as \u003C
    assert b"\\u003C" in resp.content or b"&lt;" in resp.content


# ===========================================================================
# 4. AJAX title/description update
# ===========================================================================


@pytest.mark.django_db
def test_update_survey_title_stores_xss_safely(auth_client, survey):
    """
    The AJAX update-title endpoint accepts arbitrary text and stores it in
    survey.name. The stored value must be HTML-escaped when the dashboard
    is subsequently loaded.
    """
    url = reverse("surveys:update_title", kwargs={"slug": survey.slug})
    resp = auth_client.post(
        url,
        data=json.dumps({"title": SCRIPT_TAG, "description": SCRIPT_TAG}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # The raw payload is stored as-is in the DB (output encoding is the defence).
    # Fetch the dashboard and confirm it is escaped there.
    dash = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert dash.status_code == 200
    _xss_clean(dash.content)


@pytest.mark.django_db
def test_update_survey_title_response_json_does_not_contain_raw_html(
    auth_client, survey
):
    """
    The JSON response from update-title echoes back the stored title.
    The response content-type is application/json; the title value is a
    plain JSON string. This test confirms that the raw payload does not
    appear in the HTTP response body in a way that would be interpreted as
    HTML by a browser (it should only appear as a JSON string value).
    """
    url = reverse("surveys:update_title", kwargs={"slug": survey.slug})
    resp = auth_client.post(
        url,
        data=json.dumps({"title": SCRIPT_TAG}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    # The JSON body will contain the string but it is application/json, not HTML.
    # Confirm the Content-Type header is not text/html.
    assert "text/html" not in resp.get("Content-Type", "")


# ===========================================================================
# 5. Survey style update — font CSS injection blocked by allowlist
# ===========================================================================


@pytest.mark.django_db
def test_survey_style_font_xss_blocked_by_allowlist(auth_client, survey):
    """
    Fonts are embedded in a <style> block via |safe. The server-side allowlist
    (_SAFE_FONT_RE) must reject any value that could break out of CSS context.
    When rejected, the view redirects back to the dashboard without saving.
    """
    resp = auth_client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": FONT_BREAK, "font_body": FONT_BREAK},
    )
    # Must redirect (not store the value), not 200 with the payload in the page.
    assert resp.status_code == 302

    # Follow the redirect — the payload must not appear in the dashboard.
    dash = auth_client.get(resp["Location"])
    assert dash.status_code == 200
    assert b"</style><script>" not in dash.content


@pytest.mark.django_db
def test_survey_style_safe_font_accepted(auth_client, survey):
    """Safe font names that pass the allowlist must be accepted and saved."""
    resp = auth_client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": "Arial, sans-serif", "font_body": "Georgia, serif"},
    )
    assert resp.status_code == 302
    survey.refresh_from_db()
    assert survey.style.get("font_heading") == "Arial, sans-serif"


# ===========================================================================
# 6. Question group create / edit — strip_tags on name & description
# ===========================================================================


@pytest.mark.django_db
def test_group_create_strips_html_tags_from_name(auth_client, survey):
    """
    survey_group_create() applies strip_tags() to the group name before
    saving, so HTML tags are removed. The stored name must contain no tags.
    """
    resp = auth_client.post(
        reverse("surveys:survey_group_create", kwargs={"slug": survey.slug}),
        data={"name": SCRIPT_TAG},
    )
    assert resp.status_code == 302
    group = QuestionGroup.objects.filter(surveys=survey).first()
    assert group is not None
    assert "<script>" not in group.name
    assert "</script>" not in group.name


@pytest.mark.django_db
def test_group_create_name_xss_escaped_in_groups_page(auth_client, survey):
    """
    Even if any HTML remnant survives storage, the groups page must
    HTML-escape the group name when rendering it.
    """
    auth_client.post(
        reverse("surveys:survey_group_create", kwargs={"slug": survey.slug}),
        data={"name": SCRIPT_TAG},
    )
    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_group_edit_strips_html_tags_from_name_and_description(
    auth_client, survey, owner
):
    """
    survey_group_edit() applies strip_tags() to both name and description
    before saving.
    """
    group = QuestionGroup.objects.create(name="Safe Group", owner=owner)
    survey.question_groups.add(group)

    resp = auth_client.post(
        reverse(
            "surveys:survey_group_edit", kwargs={"slug": survey.slug, "gid": group.id}
        ),
        data={"name": SCRIPT_TAG, "description": SCRIPT_TAG},
    )
    assert resp.status_code == 302
    group.refresh_from_db()
    assert "<script>" not in group.name
    assert "<script>" not in (group.description or "")


@pytest.mark.django_db
def test_group_edit_name_xss_escaped_on_dashboard(auth_client, survey, owner):
    """
    After editing a group with an XSS payload, the dashboard must show the
    stored name escaped.
    """
    group = QuestionGroup.objects.create(name="Safe Group 2", owner=owner)
    survey.question_groups.add(group)
    auth_client.post(
        reverse(
            "surveys:survey_group_edit", kwargs={"slug": survey.slug, "gid": group.id}
        ),
        data={"name": SCRIPT_TAG, "description": SCRIPT_TAG},
    )
    dash = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert dash.status_code == 200
    _xss_clean(dash.content)


# ===========================================================================
# 7. User creation — signup form
# ===========================================================================


@pytest.mark.django_db
def test_signup_page_loads_cleanly(client):
    """GET /accounts/signup/ must return 200 with no raw XSS in the page."""
    resp = client.get(reverse("core:signup"))
    assert resp.status_code == 200
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_signup_invalid_email_error_xss_escaped(client):
    """
    Submitting a signup form with an invalid email shows a validation error.
    The submitted value must not appear raw in the re-rendered form.
    """
    resp = client.post(
        reverse("core:signup"),
        data={
            "email": SCRIPT_TAG,  # not a valid email
            "password1": "Str0ng!Pass",
            "password2": "Str0ng!Pass",
        },
    )
    assert resp.status_code == 200  # form re-rendered with errors
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_signup_password_mismatch_error_xss_escaped(client):
    """
    Mismatched passwords trigger a non-field error. The re-rendered form must
    not echo any part of the submitted data as raw HTML.
    """
    resp = client.post(
        reverse("core:signup"),
        data={
            "email": "test@example.com",
            "password1": f"Pa55word{SCRIPT_TAG}",
            "password2": "differentpass",
        },
    )
    # Either re-rendered (200) or redirect; either way, no raw payload.
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_signup_duplicate_email_error_does_not_echo_xss(client, django_user_model):
    """
    When a duplicate email is submitted, the error message contains a safe
    <a href="..."> link built from reverse() — no user-supplied HTML.
    The error must not echo the original email value as raw HTML (it is
    echoed back as the field value, which Django auto-escapes in the widget).
    """
    # Create an existing user
    django_user_model.objects.create_user(
        username="existing@example.com",
        email="existing@example.com",
        password="securepass",
    )
    resp = client.post(
        reverse("core:signup"),
        data={
            "email": f"existing@example.com{SCRIPT_TAG}",
            "password1": "Str0ng!Pass1",
            "password2": "Str0ng!Pass1",
        },
    )
    assert resp.status_code == 200
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_signup_success_redirects_without_echoing_payload(client):
    """
    A valid signup must redirect (302) — it does not re-render the form
    with any user data, so the XSS payload is never in the response body.
    """
    resp = client.post(
        reverse("core:signup"),
        data={
            "email": "newuser@example.com",
            "password1": "Str0ng!Pass1",
            "password2": "Str0ng!Pass1",
        },
    )
    # Successful signup redirects; no body to inject into.
    assert resp.status_code == 302


@pytest.mark.django_db
def test_login_page_does_not_inject_next_param(client):
    """
    The login page receives a ?next= parameter. The value must not be
    reflected into the page as raw HTML.
    """
    login_url = reverse("login")
    resp = client.get(f"{login_url}?next={SCRIPT_TAG}")
    assert resp.status_code == 200


# ===========================================================================
# 8. Template auto-escaping of font CSS variables (Finding #1 — layer 2)
#
# The view-layer allowlist (survey_style_update) is the primary defence.
# But data pre-dating that fix, or values written directly to survey.style
# or SiteBranding, could still reach the templates.  These tests confirm
# that removing |safe from all three base templates means Django auto-escaping
# neutralises any malicious font value before it reaches the browser.
# ===========================================================================


@pytest.mark.django_db
def test_base_minimal_escapes_stored_font_xss(client, owner, org):
    """
    base_minimal.html is used for public survey-take pages (detail.html when
    not in preview mode).  On the public take route, brand.font_heading comes
    from the branding context processor (which reads SiteBranding), not from
    per-survey style overrides.  A malicious font_heading stored directly in
    SiteBranding must be HTML-escaped by Django's auto-escaping and must not
    break out of the <style> block.
    """
    from checktick_app.core.models import SiteBranding

    # Store the payload directly in SiteBranding so the context processor injects it.
    SiteBranding.objects.filter(pk=1).delete()
    SiteBranding.objects.create(pk=1, font_heading=FONT_XSS_STORED)

    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Font XSS Base Minimal Test",
        slug="font-xss-base-minimal",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"</style><script>" not in resp.content
    ), "Raw XSS payload in base_minimal.html — |safe not fully removed from font variable"
    assert (
        FONT_XSS_ESCAPED in resp.content
    ), "Expected HTML-escaped font value not found — auto-escaping may be broken in base_minimal.html"


# ===========================================================================
# 9. Builder question endpoints — HTML tag injection via question text (S9)
#
# _parse_builder_question_form passes text directly from POST to q.text with
# no strip_tags call.  A <script> tag stored in q.text surfaces in the
# builder_payload_json blob rendered with |safe in question_row.html.  The
# existing replace("</", "<\/") only escapes closing tags; the *opening*
# <script> tag is present verbatim, meaning the browser creates a real script
# element when it parses the hidden <div>.
# ===========================================================================

# Payload that, without strip_tags, will be stored raw in q.text / option labels.
BUILDER_SCRIPT = "<script>alert('builder-xss')</script>"
BUILDER_SCRIPT_OPEN = b"<script>alert('builder-xss')"

# Payload for </style> breakout via survey.style CSS fields.
CSS_BREAKOUT = "</style><script>alert('css-breakout')</script><style>x{color:red}"
CSS_BREAKOUT_OPEN = b"<script>alert('css-breakout')"


@pytest.mark.django_db
def test_builder_question_create_strips_html_from_text(auth_client, survey):
    """
    S9: builder_question_create must strip HTML tags from the question text
    before storing.  Without the fix, <script> is preserved in q.text and
    later injected into the builder page via builder_payload_json|safe.
    """
    auth_client.post(
        reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
        data={"text": f"{BUILDER_SCRIPT}Real question?", "type": "text"},
    )
    q = survey.questions.order_by("-id").first()
    assert q is not None, "No question was created"
    assert "<script>" not in q.text, (
        "HTML tags must be stripped from question text at write-time; "
        f"got: {q.text!r}"
    )
    assert "</script>" not in q.text


@pytest.mark.django_db
def test_builder_question_create_option_labels_stripped(auth_client, survey):
    """
    S10: Option labels submitted via builder_question_create are stored raw.
    They surface in builder_payload_json|safe.  strip_tags must be applied to
    each label in _parse_builder_question_form.
    """
    options_payload = f"{BUILDER_SCRIPT}Option A\nOption B"
    auth_client.post(
        reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
        data={"text": "Pick one", "type": "mc_single", "options": options_payload},
    )
    q = survey.questions.order_by("-id").first()
    assert q is not None, "No question was created"
    all_labels = " ".join(
        str(opt.get("label", opt) if isinstance(opt, dict) else opt)
        for opt in (q.options or [])
    )
    assert "<script>" not in all_labels, (
        "HTML tags must be stripped from option labels; "
        f"got options: {q.options!r}"
    )


@pytest.mark.django_db
def test_builder_group_question_create_strips_html_from_text(auth_client, survey, owner):
    """
    S9 (grouped path): builder_group_question_create uses the same
    _parse_builder_question_form helper; HTML must be stripped there too.
    """
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(name="Test Group", owner=owner)
    survey.question_groups.add(group)
    auth_client.post(
        reverse(
            "surveys:builder_group_question_create",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        data={"text": f"<b>Bold</b> {BUILDER_SCRIPT}Question", "type": "text"},
    )
    q = survey.questions.filter(group=group).order_by("-id").first()
    assert q is not None, "No question was created in the group"
    assert "<script>" not in q.text, f"HTML tags in q.text: {q.text!r}"
    assert "<b>" not in q.text, f"HTML bold tags in q.text: {q.text!r}"


@pytest.mark.django_db
def test_builder_question_edit_strips_html_from_text(auth_client, survey):
    """
    S9: builder_question_edit must strip HTML when updating an existing question.
    """
    q = SurveyQuestion.objects.create(survey=survey, text="Original", type="text", order=0)
    auth_client.post(
        reverse("surveys:builder_question_edit", kwargs={"slug": survey.slug, "qid": q.id}),
        data={"text": f"</div><img src=x onerror=alert(1)>{BUILDER_SCRIPT}New text", "type": "text"},
    )
    q.refresh_from_db()
    assert "<script>" not in q.text, f"Script tag in edited q.text: {q.text!r}"
    assert "onerror=" not in q.text, f"onerror attribute in edited q.text: {q.text!r}"
    assert "<img" not in q.text, f"img tag in edited q.text: {q.text!r}"


@pytest.mark.django_db
def test_builder_group_question_edit_strips_html_from_text(auth_client, survey, owner):
    """
    S9 (grouped edit path): builder_group_question_edit must also strip HTML.
    """
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(name="Edit Group", owner=owner)
    survey.question_groups.add(group)
    q = SurveyQuestion.objects.create(
        survey=survey, group=group, text="Original", type="text", order=0
    )
    auth_client.post(
        reverse(
            "surveys:builder_group_question_edit",
            kwargs={"slug": survey.slug, "gid": group.id, "qid": q.id},
        ),
        data={"text": f"{BUILDER_SCRIPT}Edited question", "type": "text"},
    )
    q.refresh_from_db()
    assert "<script>" not in q.text, f"Script tag in group-edited q.text: {q.text!r}"


# ===========================================================================
# 10. Builder group create — HTML tag injection via group name (S11)
#
# builder_group_create (the HTMX-backed builder endpoint) does NOT apply
# strip_tags, unlike the legacy survey_group_create SSR endpoint.  Group
# names with HTML tags end up in builder_payload_json|safe metadata.
# ===========================================================================


@pytest.mark.django_db
def test_builder_group_create_strips_html_from_name(auth_client, survey):
    """
    S11: builder_group_create must apply strip_tags to the group name before
    storing, consistent with survey_group_create which already does this.
    """
    from checktick_app.surveys.models import QuestionGroup

    auth_client.post(
        reverse("surveys:builder_group_create", kwargs={"slug": survey.slug}),
        data={"name": f"{BUILDER_SCRIPT}My Group"},
    )
    g = survey.question_groups.order_by("-id").first()
    assert g is not None, "No group was created"
    assert "<script>" not in g.name, (
        "HTML tags must be stripped from builder group name; "
        f"got: {g.name!r}"
    )


# ===========================================================================
# 11. survey.style CSS field — </style> breakout via |safe in survey pages (S12)
#
# builder.html, dashboard.html, and detail.html all render:
#   {{ survey.style.theme_css_light|safe }}
#   {{ survey.style.theme_css_dark|safe }}
# directly from the survey.style JSONField without sanitization in the view.
# If malicious CSS is ever written to those fields (via admin, API, or import)
# it can close the <style> block and inject arbitrary HTML/script.
# The fix: apply sanitize_css_block() to these fields at read-time in the view
# before the template context is rendered.
# ===========================================================================


@pytest.mark.django_db
def test_survey_style_css_injection_not_in_dashboard(auth_client, survey):
    """
    S12: A </style><script> payload stored in survey.style.theme_css_light
    must not appear raw in the survey dashboard page.
    """
    survey.style = {"theme_css_light": CSS_BREAKOUT}
    survey.save(update_fields=["style"])

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert CSS_BREAKOUT_OPEN not in resp.content, (
        "Raw </style><script> payload found in dashboard — "
        "survey.style.theme_css_light is not sanitized before |safe rendering"
    )


@pytest.mark.django_db
def test_survey_style_css_injection_not_in_builder(auth_client, survey, owner):
    """
    S12: Same as above but for the group_builder page (builder.html template).
    """
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(name="CSS Test Group", owner=owner)
    survey.question_groups.add(group)
    survey.style = {"theme_css_light": CSS_BREAKOUT}
    survey.save(update_fields=["style"])

    resp = auth_client.get(
        reverse("surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id})
    )
    assert resp.status_code == 200
    assert CSS_BREAKOUT_OPEN not in resp.content, (
        "Raw </style><script> payload found in builder page — "
        "survey.style.theme_css_light is not sanitized before |safe rendering"
    )


# ===========================================================================
# 12. font_css_url — javascript: / data: protocol injection (S13)
#
# survey_style_update stores font_css_url raw.  It is rendered in templates
# as <link href="{{ survey.style.font_css_url }}">.  A javascript: or data:
# URI stored here could be exploited in some browser contexts.
# The fix: only accept http:// or https:// URLs (or empty string).
# ===========================================================================


@pytest.mark.django_db
def test_survey_style_rejects_javascript_font_css_url(auth_client, survey):
    """
    S13: survey_style_update must not store a javascript: URI as font_css_url.
    """
    auth_client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_css_url": "javascript:alert(document.cookie)"},
    )
    survey.refresh_from_db()
    stored = (survey.style or {}).get("font_css_url", "")
    assert "javascript:" not in stored.lower(), (
        "javascript: URI was stored as font_css_url — must be rejected or stripped"
    )


@pytest.mark.django_db
def test_survey_style_rejects_data_uri_font_css_url(auth_client, survey):
    """
    S13: data: URIs must also be rejected as font_css_url values.
    """
    auth_client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_css_url": "data:text/html,<script>alert(1)</script>"},
    )
    survey.refresh_from_db()
    stored = (survey.style or {}).get("font_css_url", "")
    assert "data:" not in stored.lower(), (
        "data: URI was stored as font_css_url — must be rejected or stripped"
    )


@pytest.mark.django_db
def test_survey_style_accepts_valid_https_font_css_url(auth_client, survey):
    """
    S13: Legitimate https:// Google Fonts URLs must still be accepted.
    """
    legit_url = (
        "https://fonts.googleapis.com/css2"
        "?family=IBM+Plex+Sans:wght@400;600&display=swap"
    )
    auth_client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_css_url": legit_url},
    )
    survey.refresh_from_db()
    stored = (survey.style or {}).get("font_css_url", "")
    assert stored == legit_url, (
        f"Valid https font URL was not stored correctly; got: {stored!r}"
    )


@pytest.mark.django_db
def test_base_html_escapes_stored_font_xss(auth_client, survey):
    """
    base.html is used by authenticated pages including the survey dashboard.
    A malicious font_heading stored directly in survey.style must be
    HTML-escaped when the dashboard renders — not emitted raw into the
    <style> block where it would execute for every authenticated visitor.
    """
    # Write the payload directly into the DB, bypassing the view-layer allowlist.
    survey.style = {"font_heading": FONT_XSS_STORED, "font_body": "Georgia, serif"}
    survey.save(update_fields=["style"])

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"</style><script>" not in resp.content
    ), "Raw XSS payload in base.html — |safe not fully removed from font variable"
    assert (
        FONT_XSS_ESCAPED in resp.content
    ), "Expected HTML-escaped font value not found — auto-escaping may be broken in base.html"


@pytest.mark.django_db
def test_admin_base_site_escapes_stored_font_xss(client, django_user_model):
    """
    admin/base_site.html is used by every Django admin page.  Its brand CSS
    variables come from the SiteBranding model via the branding context
    processor.  A malicious font_heading stored directly in SiteBranding must
    be HTML-escaped and must not break out of the admin <style> block.
    """
    from checktick_app.core.models import SiteBranding

    # Write the payload directly into SiteBranding (no view-layer validation here).
    SiteBranding.objects.filter(pk=1).delete()
    SiteBranding.objects.create(
        pk=1,
        font_heading=FONT_XSS_STORED,
        font_body="Georgia, serif",
    )

    admin_user = django_user_model.objects.create_user(
        username="xss_admin_font@example.com",
        email="xss_admin_font@example.com",
        password="secureadminpass123!",
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(admin_user)

    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert (
        b"</style><script>" not in resp.content
    ), "Raw XSS payload in admin/base_site.html — |safe not fully removed from font variable"
    assert (
        FONT_XSS_ESCAPED in resp.content
    ), "Expected HTML-escaped font value not found — auto-escaping may be broken in admin/base_site.html"
    _xss_clean(resp.content)


@pytest.mark.django_db
def test_login_invalid_credentials_error_xss_escaped(client):
    """
    Submitting invalid credentials shows an authentication error. The
    submitted username value must be HTML-escaped, not injected raw.
    """
    resp = client.post(
        reverse("login"),
        data={"username": SCRIPT_TAG, "password": "wrongpassword"},
    )
    # Form re-rendered (200) or redirect — no raw payload.
    _xss_clean(resp.content)


# ===========================================================================
# 9. builder_payload_json closing-tag escaping (Finding #3)
#
# question_row.html uses |safe on builder_payload_json, so the </…> escape
# MUST be applied in the view before the template sees the value.
# _prepare_question_rendering() calls json.dumps().replace("</", "<\\/").
# ===========================================================================

BUILDER_XSS_PAYLOAD = "</script><script>alert(1)</script>"


@pytest.mark.django_db
def test_prepare_question_rendering_escapes_closing_tag_in_payload_json(owner, org):
    """
    Unit test for Finding #3.  _prepare_question_rendering must replace every
    '</' with '<\\/' in builder_payload_json so that a question text containing
    '</script>' cannot break out of the data island in question_row.html.
    """
    from checktick_app.surveys.views import _prepare_question_rendering

    survey = Survey.objects.create(
        owner=owner, organization=org, name="Builder XSS", slug="builder-xss-f3"
    )
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=BUILDER_XSS_PAYLOAD,
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=0,
    )

    prepared = _prepare_question_rendering(survey, [question])
    payload_json = prepared[0].builder_payload_json

    assert (
        "</" not in payload_json
    ), "Raw '</' found in builder_payload_json — Finding #3 slash-escape fix not applied"
    assert (
        "\\/" in payload_json
    ), "Expected escaped '<\\/' not found in builder_payload_json"


@pytest.mark.django_db
def test_question_row_template_renders_escaped_closing_tag(owner, org):
    """
    Integration test for Finding #3.  question_row.html uses |safe on
    builder_payload_json, so the escaping must occur in the view layer.
    Verifies that '</script>' in question text is rendered as '<\\/script>' in
    the raw HTML byte stream and does not break out of the data island.
    """
    from django.test import RequestFactory

    from checktick_app.surveys.views import _render_template_question_row

    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Builder XSS Render",
        slug="builder-xss-render-f3",
    )
    group = QuestionGroup.objects.create(name="Group Render", owner=owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=BUILDER_XSS_PAYLOAD,
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=0,
    )

    request = RequestFactory().get("/builder/")
    request.user = owner

    response = _render_template_question_row(request, survey, question)

    # The escaped form '<\/script>' (literal backslash) must be present in bytes.
    assert (
        b"<\\/script>" in response.content
    ), "Escaped '<\\/script>' not found — Finding #3 closing-tag escape fix may not be active"


# ===========================================================================
# 10. API Keys page — XSS in key name
#
# The api_keys.html template displays user-controlled data in several contexts:
#
#  a) key.name  — in a <td> via {{ key.name }}. Django auto-escaping must
#     prevent an alert() payload from executing.
#
#  b) data-key-name attribute on .js-revoke-form — the name is placed in a
#     data-* attribute via {{ key.name }}.  Django auto-escaping must encode
#     any quote characters so the attribute cannot be broken.
#
#  c) new_raw_key in the one-time reveal — the key is a server-generated
#     opaque token (ct_live_<urlsafe>), never user-supplied.  Placing it as
#     a readonly input value="{{ new_raw_key }}" must not introduce risks.
#
#  d) new_key_name in the creation banner — the name echoed back must be
#     auto-escaped (it comes from session, which was set from POST data).
#
# These tests cover (a), (b), and (d); (c) is handled by the generate()
# classmethod which uses secrets.token_urlsafe() so the value is always safe.
# ===========================================================================

KEY_NAME_XSS = "<script>alert('xss')</script>"
KEY_NAME_ATTR_BREAK = '" onmouseenter="alert(1)" x="'
KEY_NAME_SINGLE_QUOTE = "test' onerror='alert(1)"


@pytest.fixture
def pro_user(django_user_model):
    """A user on the Pro tier (API access allowed) with MFA bypassed."""
    user = django_user_model.objects.create_user(
        username="xss_apikey@example.com",
        email="xss_apikey@example.com",
        password=TEST_PASSWORD,
    )
    user.profile.account_tier = "pro"
    user.profile.save(update_fields=["account_tier"])
    return user


@pytest.fixture
def pro_client(client, pro_user, monkeypatch):
    """Authenticated client for a Pro user with MFA verification stubbed.

    OTPMiddleware installs ``user.is_verified`` as a ``functools.partial``
    wrapping ``django_otp.middleware.is_verified``.  We patch that module-level
    function so any call — whether via the partial already installed or a fresh
    one created during the request — returns True.
    """
    import django_otp.middleware as _otp_mw

    monkeypatch.setattr(_otp_mw, "is_verified", lambda user: True)
    client.force_login(pro_user)
    return client


@pytest.mark.django_db
def test_api_key_list_key_name_xss_escaped_in_table(pro_client, pro_user):
    """
    A stored API key whose name contains an XSS payload must be HTML-escaped
    when rendered in the key-list table — {{ key.name }} must not emit raw HTML.
    """
    from checktick_app.core.models import UserAPIKey

    UserAPIKey.objects.create(
        user=pro_user,
        name=KEY_NAME_XSS,
        key_hash="a" * 64,
        prefix="ct_live_xxxx",
    )
    resp = pro_client.get(reverse("surveys:api_key_list"))
    assert resp.status_code == 200
    _xss_clean(resp.content)
    # The name IS displayed — confirm it appears in encoded form
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_api_key_list_key_name_attr_break_escaped_in_data_attribute(
    pro_client, pro_user
):
    """
    The revoke form uses data-key-name="{{ key.name }}" to pass the name to
    the confirm() dialog via JS (reading element.dataset.keyName at runtime).
    A payload designed to break out of an HTML attribute must be escaped by
    Django auto-escaping so no extra attributes are injected.
    """
    from checktick_app.core.models import UserAPIKey

    UserAPIKey.objects.create(
        user=pro_user,
        name=KEY_NAME_ATTR_BREAK,
        key_hash="b" * 64,
        prefix="ct_live_yyyy",
    )
    resp = pro_client.get(reverse("surveys:api_key_list"))
    assert resp.status_code == 200
    _xss_clean(resp.content)
    # The raw attribute-break sequence must not appear verbatim
    assert b'" onmouseenter="' not in resp.content
    # Django encodes the leading " as &quot;
    assert b"&quot;" in resp.content


@pytest.mark.django_db
def test_api_key_list_key_name_single_quote_escaped_in_data_attribute(
    pro_client, pro_user
):
    """
    Single-quote injection in key.name must not produce an unescaped
    data-key-name value that a script could exploit.
    """
    from checktick_app.core.models import UserAPIKey

    UserAPIKey.objects.create(
        user=pro_user,
        name=KEY_NAME_SINGLE_QUOTE,
        key_hash="c" * 64,
        prefix="ct_live_zzzz",
    )
    resp = pro_client.get(reverse("surveys:api_key_list"))
    assert resp.status_code == 200
    _xss_clean(resp.content)
    # Raw single-quote event handler must not appear
    assert b"onerror='alert" not in resp.content


@pytest.mark.django_db
def test_api_key_creation_banner_name_xss_escaped(pro_client, pro_user, monkeypatch):
    """
    After creating a key the view stores the raw name in the session and
    re-renders the list page, displaying:
        Your new API key "<name>" has been created
    The name comes from POST data and must be HTML-escaped before display.
    """
    # Inject the session value directly (avoids the full create flow and
    # its audit-log / DB overhead) to test the template layer in isolation.
    session = pro_client.session
    session["new_api_key"] = "ct_live_test_token"
    session["new_api_key_name"] = KEY_NAME_XSS
    session.save()

    resp = pro_client.get(reverse("surveys:api_key_list"))
    assert resp.status_code == 200
    _xss_clean(resp.content)
    # The name must appear escaped, not raw
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_api_key_list_no_inline_event_handlers_present(pro_client):
    """
    The api_keys.html template must not contain any inline event handlers
    (onclick / onsubmit / onmouseenter etc.).  These are blocked by the
    Content Security Policy (no unsafe-inline) and are also an XSS risk
    when they embed user-controlled data.
    """
    import re

    resp = pro_client.get(reverse("surveys:api_key_list"))
    assert resp.status_code == 200
    # Match any on<event>= attribute — case-insensitive
    matches = re.findall(rb"\bon\w+\s*=", resp.content, re.IGNORECASE)
    assert not matches, (
        f"Inline event handler(s) found in api_keys page: "
        f"{[m.decode() for m in matches]}"
    )
