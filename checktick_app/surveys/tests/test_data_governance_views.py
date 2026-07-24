"""
Tests for data governance views: exports, dashboard integration, and download security.

These tests verify the complete data governance workflow including:
- Export creation and download functionality
- Encryption handling for patient data surveys
- Permission enforcement for export operations
- Retention period tracking and display
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import DataExport, Survey
from checktick_app.surveys.services import ExportService

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def closed_survey(db, user):
    """Create a closed survey with responses."""
    survey = Survey.objects.create(
        name="Test Survey",
        slug="test-survey",
        owner=user,
        status=Survey.Status.PUBLISHED,
    )
    # Close the survey to enable data export
    survey.close_survey(user)
    return survey


@pytest.fixture
def open_survey(db, user):
    """Create an open (published) survey."""
    return Survey.objects.create(
        name="Open Survey",
        slug="open-survey",
        owner=user,
        status=Survey.Status.PUBLISHED,
    )


@pytest.fixture
def other_user(db):
    """Create another user (not owner of surveys)."""
    return User.objects.create_user(
        username="other_user",
        email="other@example.com",
        password=TEST_PASSWORD,
    )


# ========== Dashboard Integration Tests ==========


@pytest.mark.django_db
class TestDashboardDataGovernanceWidget:
    """Test that the data governance widget appears correctly on dashboard."""

    def test_dashboard_shows_export_button_for_closed_survey(
        self, client, user, closed_survey
    ):
        """Export button should appear on dashboard when survey is closed."""
        client.force_login(user)
        url = reverse("surveys:dashboard", kwargs={"slug": closed_survey.slug})
        response = client.get(url)

        assert response.status_code == 200
        assert "Data Governance" in response.content.decode()
        assert "Download Survey Data" in response.content.decode()
        assert "Closed" in response.content.decode()

    def test_dashboard_hides_export_button_for_open_survey(
        self, client, user, open_survey
    ):
        """Export button should NOT appear when survey is still open."""
        client.force_login(user)
        url = reverse("surveys:dashboard", kwargs={"slug": open_survey.slug})
        response = client.get(url)

        assert response.status_code == 200
        # Data governance section should not appear for open surveys
        assert "Download Survey Data" not in response.content.decode()

    def test_dashboard_hides_export_button_for_unauthorized_user(
        self, client, other_user, closed_survey
    ):
        """Export button should not appear for users without export permission."""
        client.force_login(other_user)
        url = reverse("surveys:dashboard", kwargs={"slug": closed_survey.slug})

        # Other user doesn't have access to view this survey at all
        response = client.get(url)
        assert response.status_code == 403

    def test_dashboard_shows_retention_info(self, client, user, closed_survey):
        """Dashboard should show retention period and deletion date."""
        client.force_login(user)
        url = reverse("surveys:dashboard", kwargs={"slug": closed_survey.slug})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Retention Period" in content
        assert f"{closed_survey.retention_months}" in content
        if closed_survey.deletion_date:
            assert "Deletion scheduled" in content


# ========== Export Creation View Tests ==========


@pytest.mark.django_db
class TestSurveyExportCreateView:
    """Test the export disclaimer/creation view."""

    def test_export_create_requires_login(self, client, closed_survey):
        """Export creation should require authentication."""
        url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        response = client.get(url)

        assert response.status_code == 302  # Redirect to login
        assert "/accounts/login/" in response.url

    def test_export_create_requires_permission(self, client, other_user, closed_survey):
        """Export creation should require export permission."""
        client.force_login(other_user)
        url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        response = client.get(url)

        assert response.status_code == 403  # Permission denied

    def test_export_create_accessible_by_owner(self, client, user, closed_survey):
        """Survey owner should be able to access export creation."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "Create Data Export" in response.content.decode()

    def test_export_create_post_creates_export(self, client, user, closed_survey):
        """POSTing to export create should create a DataExport record."""
        # Add a response to the survey so export has data
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={},
        )

        client.force_login(user)
        url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        response = client.post(
            url,
            {
                "full_name": "Test User",
                "purpose": "Research analysis",
                "attestation_accepted": True,
            },
        )

        # Should redirect to download page
        assert response.status_code == 302

        # Should have created an export
        export = DataExport.objects.filter(survey=closed_survey).first()
        assert export is not None
        assert export.created_by == user

    def test_export_create_requires_attestation(self, client, user, closed_survey):
        """Export creation should require attestation acceptance."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        response = client.post(
            url,
            {
                "full_name": "Test User",
                "purpose": "Research",
                "attestation_accepted": False,  # Not accepted
            },
        )

        # Should show form error
        assert response.status_code == 200
        assert DataExport.objects.filter(survey=closed_survey).count() == 0


# ========== Export Download View Tests ==========


@pytest.mark.django_db
class TestSurveyExportDownloadView:
    """Test the export download page view."""

    @pytest.fixture
    def export_with_token(self, closed_survey, user):
        """Create an export with a download token."""
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={},
        )

        export = ExportService.create_export(
            survey=closed_survey,
            user=user,
            password=None,
        )
        return export

    def test_download_page_requires_login(self, client, export_with_token):
        """Download page should require authentication."""
        url = reverse(
            "surveys:survey_export_download",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
            },
        )
        response = client.get(url)

        assert response.status_code == 302  # Redirect to login

    def test_download_page_requires_permission(
        self, client, other_user, export_with_token
    ):
        """Download page should require export permission."""
        client.force_login(other_user)
        url = reverse(
            "surveys:survey_export_download",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
            },
        )
        response = client.get(url)

        assert response.status_code == 403

    def test_download_page_shows_link(self, client, user, export_with_token):
        """Download page should show the download link with token."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_download",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
            },
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "download" in response.content.decode().lower()
        assert export_with_token.download_token in response.content.decode()

    def test_download_page_shows_expiry_warning(self, client, user, export_with_token):
        """Download page should warn about token expiry."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_download",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
            },
        )
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode().lower()
        assert "expires" in content or "valid" in content


# ========== Export File Download Tests ==========


@pytest.mark.django_db
class TestSurveyExportFileView:
    """Test the actual file download view with token validation."""

    @pytest.fixture
    def export_with_token(self, closed_survey, user):
        """Create an export with a download token."""
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={"question_1": "answer_1"},
        )

        export = ExportService.create_export(
            survey=closed_survey,
            user=user,
            password=None,
        )
        return export

    def test_file_download_requires_valid_token(self, client, user, export_with_token):
        """File download should require a valid token."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": "invalid-token",
            },
        )
        response = client.get(url)

        # Should redirect to dashboard with error (user-friendly approach)
        assert response.status_code == 302
        assert response.url == f"/surveys/{export_with_token.survey.slug}/dashboard/"

    def test_file_download_with_valid_token(self, client, user, export_with_token):
        """File download should work with valid token."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        # Should return CSV file
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

    def test_file_download_marks_as_downloaded(self, client, user, export_with_token):
        """Downloading should mark export as downloaded."""
        assert export_with_token.downloaded_at is None

        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        assert response.status_code == 200

        # Refresh from DB
        export_with_token.refresh_from_db()
        assert export_with_token.downloaded_at is not None

    def test_file_download_rejects_expired_token(self, client, user, export_with_token):
        """File download should reject expired tokens."""
        # Expire the token
        export_with_token.download_url_expires_at = timezone.now() - timezone.timedelta(
            minutes=1
        )
        export_with_token.save()

        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        # Should redirect to dashboard with error (user-friendly approach)
        assert response.status_code == 302
        assert response.url == f"/surveys/{export_with_token.survey.slug}/dashboard/"

    def test_file_download_contains_correct_data(self, client, user, export_with_token):
        """Downloaded file should contain the survey data."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        assert response.status_code == 200

        # Check content contains CSV data
        content = response.content.decode()

        # Should be CSV with headers
        assert "Submitted At" in content or "submitted_at" in content
        # Should contain the username
        assert user.username in content
        # Should have CSV structure (commas and line breaks)
        assert "," in content and "\n" in content


# ========== Export File Download Security Lockdown ==========


@pytest.mark.django_db
class TestSurveyExportFileSecurity:
    """
    Security lockdown for the sensitive-data export file route.

    This route serves a CSV of patient/survey responses, so the tests here
    lock down the guarantees that must hold even if the URL is leaked:
      - anonymous users cannot download (login required)
      - a valid token for one survey cannot be replayed against another
      - a wrong slug + valid export_id yields 404 (no IDOR leakage)
      - the download page renders an href that actually resolves (no 404 bug)
      - the token comparison is constant-time (no timing oracle)
    """

    @pytest.fixture
    def export_with_token(self, closed_survey, user):
        """Create an export with a download token."""
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={"question_1": "answer_1"},
        )
        return ExportService.create_export(
            survey=closed_survey,
            user=user,
            password=None,
        )

    @pytest.fixture
    def other_survey_export(self, user):
        """A second, independent survey + export owned by the same user."""
        survey = Survey.objects.create(
            name="Other Survey",
            slug="other-survey",
            owner=user,
            status=Survey.Status.PUBLISHED,
        )
        survey.close_survey(user)

        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={"q": "a"},
        )
        return ExportService.create_export(survey=survey, user=user, password=None)

    def test_file_download_requires_login(self, client, export_with_token):
        """Anonymous requests must not receive the CSV; login is required."""
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        # @login_required redirects to login; never 200 with CSV body.
        assert response.status_code == 302
        assert "login" in response.url
        assert response["Content-Type"] != "text/csv"

    def test_file_download_rejects_non_owner_with_valid_token(
        self, client, other_user, export_with_token
    ):
        """
        A non-owner holding a valid (e.g. leaked) token must still be denied.

        The token is a second factor, not a replacement for authorisation.
        Only the survey owner (or their seniors: org owner, org admins,
        active data custodians) may download exported survey data. This is
        the core security property for a sensitive-data export route.
        """
        client.force_login(other_user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        assert response.status_code == 403
        assert response["Content-Type"] != "text/csv"

    def test_file_download_rejects_cross_survey_token_reuse(
        self, client, user, export_with_token, other_survey_export
    ):
        """A token from survey A must not grant access to survey B's export."""
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": other_survey_export.survey.slug,
                "export_id": other_survey_export.id,
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        # Token mismatch -> redirect to dashboard, never the CSV.
        assert response.status_code == 302
        assert response.url == f"/surveys/{other_survey_export.survey.slug}/dashboard/"
        assert response["Content-Type"] != "text/csv"

    def test_file_download_wrong_slug_yields_404(
        self, client, user, export_with_token, other_survey_export
    ):
        """
        A valid export_id paired with the wrong slug must 404.

        The view filters by `survey=survey`, so an export_id that exists but
        belongs to a different survey is treated as not found — preventing
        IDOR-style enumeration of export IDs across surveys.
        """
        client.force_login(user)
        url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": other_survey_export.survey.slug,
                "export_id": export_with_token.id,  # belongs to a different survey
                "token": export_with_token.download_token,
            },
        )
        response = client.get(url)

        assert response.status_code == 404
        assert response["Content-Type"] != "text/csv"

    def test_download_page_href_resolves_without_404(
        self, client, user, export_with_token
    ):
        """
        The href rendered on the download page must actually resolve.

        Regression test for the bug where ExportService.get_download_url()
        hand-built a /api/surveys/... URL that no route matched, causing the
        "Download Export" button to 404. We follow the rendered href and
        assert a 200 CSV response.
        """
        client.force_login(user)
        page_url = reverse(
            "surveys:survey_export_download",
            kwargs={
                "slug": export_with_token.survey.slug,
                "export_id": export_with_token.id,
            },
        )
        page = client.get(page_url)
        assert page.status_code == 200

        # Pull the href out of the "Download Export" anchor. The anchor
        # contains an SVG before the text and the page also has breadcrumb
        # links, so we target the href that contains the file-route segment
        # `/download/` (unique to the survey_export_file route).
        import re

        page_html = page.content.decode()
        href_match = re.search(r'href="([^"]*/download/[^"]+)"', page_html)
        assert href_match is not None, "Download Export href not found on page"
        href = href_match.group(1).replace("&amp;", "&")

        # The href must be the route-reversed URL (not the old /api/... path).
        assert href.startswith("/surveys/")
        assert "/api/surveys/" not in href

        # Following the href must yield the CSV, not a 404.
        download = client.get(href)
        assert download.status_code == 200
        assert download["Content-Type"] == "text/csv"
        assert "attachment" in download["Content-Disposition"]

    def test_token_comparison_is_constant_time(self, export_with_token):
        """
        Token validation must use secrets.compare_digest (constant-time),
        not `==`, to avoid a timing oracle on the download token.
        """
        import inspect

        src = inspect.getsource(ExportService.validate_download_token)
        assert "compare_digest" in src
        # No raw equality comparison against the token anywhere in the body.
        # (Allow `==` only inside docstrings/strings by checking the AST-free
        # heuristic: compare_digest must be the comparison mechanism.)
        assert "download_token ==" not in src
        assert "== token" not in src
        assert "== export.download_token" not in src

    def test_platform_admin_cannot_download_survey_data(
        self, client, closed_survey, user
    ):
        """
        Platform Admins (superusers) must NOT be able to download survey data.

        This is a deliberate security boundary: CheckTick staff and platform
        operators must not be able to read patient/respondent data. The
        permission helper `can_export_survey_data` returns False for a
        platform admin who does not independently hold an in-survey role
        (owner / org owner / org admin / active data custodian), and the
        export file view enforces this even when a valid token is present.
        """
        from checktick_app.surveys.models import SurveyResponse
        from checktick_app.surveys.permissions import can_export_survey_data

        # Create a response + export owned by `user` (not the platform admin).
        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={"q": "a"},
        )
        export = ExportService.create_export(
            survey=closed_survey, user=user, password=None
        )

        # Platform admin who has no relationship to this survey.
        platform_admin = User.objects.create_user(
            username="platform-admin",
            email="platform-admin@example.com",
            password=TEST_PASSWORD,
            is_superuser=True,
            is_staff=True,
        )

        # 1. Permission helper must deny.
        assert can_export_survey_data(platform_admin, closed_survey) is False

        # 2. The download page (which calls require_can_export_survey_data)
        #    must deny with 403.
        client.force_login(platform_admin)
        download_page_url = reverse(
            "surveys:survey_export_download",
            kwargs={"slug": closed_survey.slug, "export_id": export.id},
        )
        assert client.get(download_page_url).status_code == 403

        # 3. The file download route must deny even with a valid token.
        file_url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": closed_survey.slug,
                "export_id": export.id,
                "token": export.download_token,
            },
        )
        response = client.get(file_url)
        assert response.status_code == 403
        assert response["Content-Type"] != "text/csv"

    def test_platform_admin_who_is_also_owner_can_download(
        self, client, closed_survey, user
    ):
        """
        A Platform Admin who is *also* the survey owner can download.

        The exclusion is based on role, not user identity: a platform admin
        who independently holds an in-survey role (here: survey owner) is
        granted access through that role. This guards against an over-broad
        denial that would lock owners out of their own surveys after being
        granted platform admin status.
        """
        from checktick_app.surveys.models import SurveyResponse
        from checktick_app.surveys.permissions import can_export_survey_data

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={"q": "a"},
        )
        export = ExportService.create_export(
            survey=closed_survey, user=user, password=None
        )

        # Promote the survey owner to platform admin.
        user.is_superuser = True
        user.is_staff = True
        user.save()

        # Permission helper grants via the owner branch, not the platform-admin
        # branch (there is no platform-admin branch).
        assert can_export_survey_data(user, closed_survey) is True

        client.force_login(user)
        file_url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": closed_survey.slug,
                "export_id": export.id,
                "token": export.download_token,
            },
        )
        response = client.get(file_url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"


# ========== Survey Close Integration Test ==========


@pytest.mark.django_db
class TestSurveyCloseIntegration:
    """Test that closing a survey triggers retention period correctly."""

    def test_closing_survey_sets_retention_fields(self, client, user, open_survey):
        """Closing survey should set closed_at and deletion_date."""
        assert open_survey.closed_at is None
        assert open_survey.deletion_date is None

        client.force_login(user)
        url = reverse("surveys:publish_settings", kwargs={"slug": open_survey.slug})

        # Submit close action
        response = client.post(
            url,
            {
                "action": "close",
            },
        )

        # Should redirect to dashboard
        assert response.status_code == 302

        # Refresh survey
        open_survey.refresh_from_db()

        # Should have set retention fields
        assert open_survey.status == Survey.Status.CLOSED
        assert open_survey.closed_at is not None
        assert open_survey.deletion_date is not None
        assert open_survey.retention_months == 6  # Default

    def test_closing_survey_shows_success_message(self, client, user, open_survey):
        """Closing survey should show retention information in success message."""
        client.force_login(user)
        url = reverse("surveys:publish_settings", kwargs={"slug": open_survey.slug})

        response = client.post(url, {"action": "close"}, follow=True)

        assert response.status_code == 200
        messages = list(response.context["messages"])
        assert len(messages) > 0
        assert "6 months" in str(messages[0])  # Shows retention period


# ========== Permission Enforcement Tests ==========


@pytest.mark.django_db
class TestExportPermissionEnforcement:
    """Test that export routes properly enforce permissions."""

    def test_export_routes_blocked_for_non_owners(
        self, client, other_user, closed_survey
    ):
        """All export routes should be blocked for unauthorized users."""
        client.force_login(other_user)

        # Create export
        create_url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        assert client.get(create_url).status_code == 403

        # Create export (need to create one first as owner)
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=closed_survey.owner,
            submitted_at=timezone.now(),
            answers={},
        )
        export = ExportService.create_export(
            survey=closed_survey,
            user=closed_survey.owner,
            password=None,
        )

        download_url = reverse(
            "surveys:survey_export_download",
            kwargs={"slug": closed_survey.slug, "export_id": export.id},
        )
        assert client.get(download_url).status_code == 403

        # Download file - the token is a second factor, NOT a replacement
        # for authorisation. A non-owner with a valid (leaked) token must
        # still be denied: only the survey owner (or their seniors — org
        # owner, org admins, active data custodians) may download exports.
        file_url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": closed_survey.slug,
                "export_id": export.id,
                "token": export.download_token,
            },
        )
        # Valid token + no permission = 403, never the CSV.
        assert client.get(file_url).status_code == 403

    def test_export_routes_allowed_for_owner(self, client, user, closed_survey):
        """Survey owner should have access to all export routes."""
        from checktick_app.surveys.models import SurveyResponse

        SurveyResponse.objects.create(
            survey=closed_survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            answers={},
        )

        client.force_login(user)

        # Create export
        create_url = reverse(
            "surveys:survey_export_create", kwargs={"slug": closed_survey.slug}
        )
        assert client.get(create_url).status_code == 200

        # Create an export
        export = ExportService.create_export(
            survey=closed_survey,
            user=user,
            password=None,
        )

        # View export download page
        download_url = reverse(
            "surveys:survey_export_download",
            kwargs={"slug": closed_survey.slug, "export_id": export.id},
        )
        assert client.get(download_url).status_code == 200

        # Download file
        file_url = reverse(
            "surveys:survey_export_file",
            kwargs={
                "slug": closed_survey.slug,
                "export_id": export.id,
                "token": export.download_token,
            },
        )
        assert client.get(file_url).status_code == 200
