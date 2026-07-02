"""
Accessibility tests using Playwright + axe-core.

These tests verify WCAG 2.2 AA accessibility across key pages.
Run with: pytest tests/test_accessibility.py -v

For parallel execution with xdist:
    pytest tests/test_accessibility.py -v -n auto

Note: These tests require playwright to be installed:
    poetry add --group dev pytest-playwright axe-playwright-python
    playwright install chromium
"""

from django.contrib.auth.models import User
import pytest

from checktick_app.surveys.models import Organization, Survey, SurveyQuestion

# Skip all tests if playwright is not available
try:
    from axe_playwright_python.sync_playwright import Axe

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Axe = None

# Mark all tests in this module
pytestmark = [
    pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"),
    pytest.mark.accessibility,
]

TEST_PASSWORD = "testpass123!"  # nosec: test password
WCAG_22_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


# Use pytest-playwright's built-in page fixture (xdist compatible)
# No custom browser fixture needed - pytest-playwright handles it


@pytest.fixture
def axe():
    """Create an Axe instance."""
    return Axe()


# Known accessibility issues that need to be fixed
# Each issue should have a tracking reference or comment
# When issues are fixed, remove them from this dict
KNOWN_ISSUES = {
    # Add known issues here as they're discovered
    # Example: "rule-id": "Description of why this is accepted/tracked",
}


def run_axe_test(page, axe, url):
    """Run axe accessibility tests on a URL."""
    page.goto(url)
    page.wait_for_load_state("networkidle")

    results = axe.run(
        page,
        context=None,
        options={
            "runOnly": {
                "type": "tag",
                "values": WCAG_22_AA_TAGS,
            }
        },
    )
    return results


def assert_no_violations(results, context_name="page", allow_known=True):
    """Assert that there are no accessibility violations.

    Args:
        results: The axe-core results object
        context_name: A name for the page being tested (for error messages)
        allow_known: If True, skip violations listed in KNOWN_ISSUES
    """
    response = results.response if hasattr(results, "response") else results
    violations = response.get("violations", [])

    # Separate known and unknown violations
    unknown_violations = []
    known_violations = []

    for v in violations:
        if allow_known and v["id"] in KNOWN_ISSUES:
            known_violations.append(v)
        else:
            unknown_violations.append(v)

    # Report known issues as warnings
    if known_violations:
        for v in known_violations:
            print(f"\n⚠️  Known issue skipped: {v['id']} - {KNOWN_ISSUES[v['id']]}")

    # Fail only on unknown violations
    if unknown_violations:
        messages = []
        for v in unknown_violations:
            nodes = v.get("nodes", [])
            node_count = len(nodes)
            messages.append(
                f"\n  - {v['id']}: {v['description']} "
                f"({v['impact']} impact, {node_count} occurrences)"
            )
            for node in nodes[:3]:
                target = node.get("target", ["unknown"])[0]
                messages.append(f"      → {target}")
            if node_count > 3:
                messages.append(f"      ... and {node_count - 3} more")

        violation_summary = "".join(messages)
        pytest.fail(
            f"Accessibility violations found on {context_name}:{violation_summary}"
        )


def login_user(page, live_server, username, password):
    """Log in a user via the browser."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


# =============================================================================
# Public Page Tests (No Database Required)
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestPublicPageAccessibility:
    """Test accessibility of public pages."""

    def test_home_page_accessibility(self, page, axe, live_server):
        """Test that the home page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/")
        assert_no_violations(results, "home page")

    def test_login_page_accessibility(self, page, axe, live_server):
        """Test that the login page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/accounts/login/")
        assert_no_violations(results, "login page")

    def test_signup_page_accessibility(self, page, axe, live_server):
        """Test that the signup page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/signup/")
        assert_no_violations(results, "signup page")

    def test_docs_page_accessibility(self, page, axe, live_server):
        """Test that the documentation index page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/docs/")
        assert_no_violations(results, "docs index page")

    def test_docs_content_page_accessibility(self, page, axe, live_server):
        """Test that a documentation content page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/docs/getting-started/")
        assert_no_violations(results, "docs content page")


# =============================================================================
# Survey Form Tests (Primary Respondent Experience)
# =============================================================================


@pytest.fixture
def published_survey(db):
    """Create a published survey with various question types."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password=TEST_PASSWORD,
    )
    org = Organization.objects.create(name="Test Org", owner=user)
    survey = Survey.objects.create(
        owner=user,
        organization=org,
        name="Accessibility Test Survey",
        slug="a11y-test-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )

    # Create various question types to test accessibility
    question_types = [
        ("text", "What is your name?"),
        ("text", "Please describe your experience"),
        ("mc_single", "Select your preference"),
        ("mc_multi", "Select all that apply"),
        ("dropdown", "Choose from the dropdown"),
        ("yesno", "Is this a yes/no question?"),
    ]
    for i, (qtype, text) in enumerate(question_types):
        q = SurveyQuestion.objects.create(
            survey=survey,
            type=qtype,
            text=text,
            order=i,
        )
        if qtype in ("mc_single", "mc_multi", "dropdown"):
            q.options = ["Option 1", "Option 2", "Option 3"]
            q.save()

    return survey, user


@pytest.mark.django_db(transaction=True)
class TestSurveyFormAccessibility:
    """Test accessibility of survey forms - the primary respondent experience."""

    def test_survey_form_accessibility(self, page, axe, live_server, published_survey):
        """Test that survey forms meet WCAG 2.2 AA standards."""
        survey, _ = published_survey
        results = run_axe_test(page, axe, f"{live_server.url}/surveys/{survey.slug}/")
        assert_no_violations(results, "survey form")

    def test_survey_form_with_validation_errors(
        self, page, axe, live_server, published_survey
    ):
        """Test accessibility when validation errors are displayed."""
        survey, _ = published_survey
        url = f"{live_server.url}/surveys/{survey.slug}/"
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Try to submit the form to trigger validation errors
        submit_button = page.locator('button[type="submit"]')
        if submit_button.count() > 0:
            submit_button.click()
            page.wait_for_load_state("networkidle")

            results = axe.run(
                page,
                context=None,
                options={
                    "runOnly": {
                        "type": "tag",
                        "values": WCAG_22_AA_TAGS,
                    }
                },
            )
            assert_no_violations(results, "survey form with validation errors")


# =============================================================================
# Authenticated Page Tests
# =============================================================================


@pytest.fixture
def user_with_survey(db):
    """Create a user with a survey for authenticated tests."""
    user = User.objects.create_user(
        username="authuser",
        email="auth@example.com",
        password=TEST_PASSWORD,
    )
    org = Organization.objects.create(name="Auth Test Org", owner=user)
    survey = Survey.objects.create(
        owner=user,
        organization=org,
        name="Test Survey",
        slug="auth-test-survey",
    )
    SurveyQuestion.objects.create(
        survey=survey,
        type="text",
        text="Test question",
        order=0,
    )
    return user, survey


@pytest.mark.django_db(transaction=True)
class TestAuthenticatedPageAccessibility:
    """Test accessibility of authenticated pages."""

    def test_survey_list_accessibility(self, page, axe, live_server, user_with_survey):
        """Test that survey list page meets WCAG 2.2 AA standards."""
        user, _ = user_with_survey
        login_user(page, live_server, user.username, TEST_PASSWORD)
        results = run_axe_test(page, axe, f"{live_server.url}/surveys/")
        assert_no_violations(results, "survey list page")

    def test_survey_dashboard_accessibility(
        self, page, axe, live_server, user_with_survey
    ):
        """Test that survey dashboard meets WCAG 2.2 AA standards."""
        user, survey = user_with_survey
        login_user(page, live_server, user.username, TEST_PASSWORD)
        results = run_axe_test(
            page, axe, f"{live_server.url}/surveys/{survey.slug}/dashboard/"
        )
        assert_no_violations(results, "survey dashboard")

    def test_profile_page_accessibility(self, page, axe, live_server, user_with_survey):
        """Test that user profile page meets WCAG 2.2 AA standards."""
        user, _ = user_with_survey
        login_user(page, live_server, user.username, TEST_PASSWORD)
        results = run_axe_test(page, axe, f"{live_server.url}/profile")
        assert_no_violations(results, "profile page")

    def test_question_builder_accessibility(
        self, page, axe, live_server, user_with_survey
    ):
        """Test that question builder (groups) page meets WCAG 2.2 AA standards."""
        user, survey = user_with_survey
        login_user(page, live_server, user.username, TEST_PASSWORD)
        results = run_axe_test(
            page, axe, f"{live_server.url}/surveys/{survey.slug}/groups/"
        )
        assert_no_violations(results, "question builder")


@pytest.mark.django_db(transaction=True)
class TestPublicMarketingPages:
    """Test accessibility of public marketing/info pages."""

    def test_pricing_page_accessibility(self, page, axe, live_server):
        """Test that pricing page meets WCAG 2.2 AA standards."""
        results = run_axe_test(page, axe, f"{live_server.url}/pricing")
        assert_no_violations(results, "pricing page")


# =============================================================================
# Platform Admin Tests (Requires superuser)
# =============================================================================


@pytest.fixture
def superuser(db):
    """Create a superuser for admin tests."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password=TEST_PASSWORD,
    )


@pytest.mark.django_db(transaction=True)
class TestPlatformAdminAccessibility:
    """Test accessibility of platform admin pages."""

    def test_platform_admin_dashboard_accessibility(
        self, page, axe, live_server, superuser
    ):
        """Test that platform admin dashboard meets WCAG 2.2 AA standards."""
        login_user(page, live_server, superuser.username, TEST_PASSWORD)
        results = run_axe_test(page, axe, f"{live_server.url}/platform-admin/")
        assert_no_violations(results, "platform admin dashboard")
