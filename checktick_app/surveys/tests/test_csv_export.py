"""
Tests for CSV export functionality.
"""

from django.test import TestCase

from checktick_app.surveys.views import _format_answer_for_export


class TestFormatAnswerForExport:
    """Tests for the _format_answer_for_export helper function."""

    # Text questions
    def test_text_answer(self):
        result = _format_answer_for_export("Hello world", "text")
        assert result == "Hello world"

    def test_empty_text_answer(self):
        result = _format_answer_for_export("", "text")
        assert result == ""

    def test_none_answer(self):
        result = _format_answer_for_export(None, "text")
        assert result == ""

    # Yes/No questions
    def test_yesno_yes(self):
        result = _format_answer_for_export("yes", "yesno")
        assert result == "yes"

    def test_yesno_no(self):
        result = _format_answer_for_export("no", "yesno")
        assert result == "no"

    # Single choice questions
    def test_mc_single_answer(self):
        result = _format_answer_for_export("Option A", "mc_single")
        assert result == "Option A"

    def test_dropdown_answer(self):
        result = _format_answer_for_export("Selected item", "dropdown")
        assert result == "Selected item"

    def test_likert_answer(self):
        result = _format_answer_for_export("4", "likert")
        assert result == "4"

    # Multi-choice questions
    def test_mc_multi_single_selection(self):
        result = _format_answer_for_export(["Option A"], "mc_multi")
        assert result == "Option A"

    def test_mc_multi_multiple_selections(self):
        result = _format_answer_for_export(
            ["Option A", "Option B", "Option C"], "mc_multi"
        )
        assert result == "Option A; Option B; Option C"

    def test_mc_multi_empty_list(self):
        result = _format_answer_for_export([], "mc_multi")
        assert result == ""

    # Orderable questions
    def test_orderable_list(self):
        result = _format_answer_for_export(["First", "Second", "Third"], "orderable")
        assert result == "First; Second; Third"

    def test_orderable_single_item(self):
        result = _format_answer_for_export(["Only item"], "orderable")
        assert result == "Only item"

    # Template questions
    def test_template_patient_with_fields(self):
        answer = {
            "template": "patient_details_encrypted",
            "fields": ["first_name", "date_of_birth"],
        }
        result = _format_answer_for_export(answer, "template_patient")
        assert result == "first_name, date_of_birth"

    def test_template_patient_empty_fields(self):
        answer = {"template": "patient_details_encrypted", "fields": []}
        result = _format_answer_for_export(answer, "template_patient")
        assert result == ""

    def test_template_professional_with_fields(self):
        answer = {
            "template": "professional_details",
            "fields": ["job_title", "employing_trust"],
        }
        result = _format_answer_for_export(answer, "template_professional")
        assert result == "job_title, employing_trust"

    # Edge cases
    def test_list_for_single_choice_question(self):
        """Handle edge case where single-choice answer is unexpectedly a list."""
        result = _format_answer_for_export(["Unexpected", "List"], "mc_single")
        assert result == "Unexpected; List"

    def test_dict_for_text_question(self):
        """Handle edge case where text answer is unexpectedly a dict."""
        result = _format_answer_for_export({"key": "value"}, "text")
        assert '{"key": "value"}' in result

    def test_numeric_answer(self):
        """Handle numeric answers."""
        result = _format_answer_for_export(42, "text")
        assert result == "42"

    def test_boolean_answer(self):
        """Handle boolean answers."""
        result = _format_answer_for_export(True, "yesno")
        assert result == "True"

    def test_image_choice_answer(self):
        """Image choice should work like single choice."""
        result = _format_answer_for_export("image_1", "image")
        assert result == "image_1"


class TestCSVExportIntegration(TestCase):
    """Integration tests for CSV export functionality."""

    def test_export_requires_authentication(self):
        """Export endpoint should require login for existing surveys."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "x"  # noqa: S105
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-export-survey",
            owner=user,
        )

        from django.test import Client

        client = Client()
        response = client.get(f"/surveys/{survey.slug}/export.csv")
        # Should redirect to login
        assert response.status_code == 302
        assert "/login" in response.url or "/accounts/login" in response.url

    def test_export_requires_ownership(self):
        """Export endpoint should only allow survey owner."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "testpass123"  # noqa: S105
        User = get_user_model()
        owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
        _ = User.objects.create_user(username="other_user", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-export-perm",
            owner=owner,
        )

        from django.test import Client

        client = Client()
        client.login(username="other_user", password=TEST_PASSWORD)
        response = client.get(f"/surveys/{survey.slug}/export.csv")
        # Should return 404 (owner filter in queryset)
        assert response.status_code == 404

    def test_export_requires_unlock(self):
        """Export endpoint should require survey to be unlocked."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "testpass123"  # noqa: S105
        User = get_user_model()
        owner = User.objects.create_user(username="owner2", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-export-unlock",
            owner=owner,
        )

        from django.test import Client

        client = Client()
        client.login(username="owner2", password=TEST_PASSWORD)
        response = client.get(f"/surveys/{survey.slug}/export.csv")
        # Should redirect to unlock page
        assert response.status_code == 302
        assert "unlock" in response.url


class TestDashboardIntegration(TestCase):
    """Integration tests for dashboard functionality."""

    def test_dashboard_requires_authentication(self):
        """Dashboard endpoint should require login."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "x"  # noqa: S105
        User = get_user_model()
        user = User.objects.create_user(username="dashuser", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-dash-auth",
            owner=user,
        )

        from django.test import Client

        client = Client()
        response = client.get(f"/surveys/{survey.slug}/dashboard/")
        # Should redirect to login
        assert response.status_code == 302
        assert "/login" in response.url or "/accounts/login" in response.url

    def test_dashboard_requires_view_permission(self):
        """Dashboard endpoint should check view permissions."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "testpass123"  # noqa: S105
        User = get_user_model()
        owner = User.objects.create_user(username="dashowner", password=TEST_PASSWORD)
        _ = User.objects.create_user(username="dashother", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-dash-perm",
            owner=owner,
        )

        from django.test import Client

        client = Client()
        client.login(username="dashother", password=TEST_PASSWORD)
        response = client.get(f"/surveys/{survey.slug}/dashboard/")
        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_dashboard_accessible_by_owner(self):
        """Dashboard endpoint should be accessible by survey owner."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        TEST_PASSWORD = "testpass123"  # noqa: S105
        User = get_user_model()
        owner = User.objects.create_user(username="dashowner2", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-dash-owner",
            owner=owner,
        )

        from django.test import Client

        client = Client()
        client.login(username="dashowner2", password=TEST_PASSWORD)
        response = client.get(f"/surveys/{survey.slug}/dashboard/")
        # Should return 200 OK
        assert response.status_code == 200

    def test_dashboard_accessible_with_view_membership(self):
        """Dashboard endpoint should be accessible by users with view membership."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey, SurveyMembership

        TEST_PASSWORD = "testpass123"  # noqa: S105
        User = get_user_model()
        owner = User.objects.create_user(username="dashowner3", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="dashviewer", password=TEST_PASSWORD)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-dash-viewer",
            owner=owner,
        )
        SurveyMembership.objects.create(
            user=viewer,
            survey=survey,
            role=SurveyMembership.Role.VIEWER,
        )

        from django.test import Client

        client = Client()
        client.login(username="dashviewer", password=TEST_PASSWORD)
        response = client.get(f"/surveys/{survey.slug}/dashboard/")
        # Should return 200 OK
        assert response.status_code == 200
