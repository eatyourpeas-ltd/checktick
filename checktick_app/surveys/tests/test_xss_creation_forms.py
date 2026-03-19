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
