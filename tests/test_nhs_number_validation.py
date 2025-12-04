"""
Tests for NHS number and postcode validation endpoints.
"""

from unittest.mock import MagicMock, patch

from django.test import Client, override_settings
import pytest


@pytest.fixture
def client():
    return Client()


class TestNHSNumberValidation:
    """Tests for the NHS number HTMX validation endpoint."""

    def test_valid_nhs_number_returns_success(self, client, db):
        """Test that a valid NHS number returns success styling."""
        # 4505577104 is a valid NHS number (passes checksum)
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "4505577104"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" in content
        assert "450 557 7104" in content  # Formatted as 3 3 4

    def test_invalid_nhs_number_returns_error(self, client, db):
        """Test that an invalid NHS number returns error styling."""
        # 1234567890 is an invalid NHS number (fails checksum)
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "1234567890"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-error" in content
        assert "123 456 7890" in content  # Still formatted as 3 3 4

    def test_empty_nhs_number_returns_empty_input(self, client, db):
        """Test that an empty NHS number returns a clean input."""
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": ""},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" not in content
        assert "input-error" not in content
        assert 'placeholder="NHS number"' in content

    def test_nhs_number_with_spaces_is_normalised(self, client, db):
        """Test that NHS numbers with spaces are normalised."""
        # 4505577104 with spaces should still validate
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "450 557 7104"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" in content
        assert "450 557 7104" in content

    def test_short_nhs_number_returns_error(self, client, db):
        """Test that a too-short NHS number returns error."""
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "12345"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-error" in content

    def test_htmx_attributes_preserved_in_response(self, client, db):
        """Test that HTMX attributes are preserved in the response."""
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "4505577104"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'hx-post="/surveys/validate/nhs-number/"' in content
        assert 'hx-trigger="blur, keyup changed delay:500ms"' in content
        assert 'hx-target="closest label"' in content
        assert 'hx-swap="outerHTML"' in content

    def test_valid_nhs_number_shows_checkmark(self, client, db):
        """Test that a valid NHS number shows a checkmark icon."""
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "4505577104"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "text-success" in content
        assert "polyline" in content  # Checkmark SVG

    def test_invalid_nhs_number_shows_x_icon(self, client, db):
        """Test that an invalid NHS number shows an X icon."""
        response = client.post(
            "/surveys/validate/nhs-number/",
            {"nhs_number": "1234567890"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "text-error" in content
        assert '<line x1="18"' in content  # X icon SVG

    def test_get_request_not_allowed(self, client, db):
        """Test that GET requests are not allowed."""
        response = client.get("/surveys/validate/nhs-number/")
        assert response.status_code == 405


class TestPostcodeValidation:
    """Tests for the postcode HTMX validation endpoint."""

    def test_empty_postcode_returns_empty_input(self, client, db):
        """Test that an empty postcode returns a clean input."""
        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": ""},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" not in content
        assert "input-error" not in content
        assert 'placeholder="Post code"' in content

    @override_settings(POSTCODES_API_URL="", POSTCODES_API_KEY="")
    def test_api_not_configured_returns_neutral_styling(self, client, db):
        """Test that when API is not configured, no validation styling is shown."""
        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "SW1A 1AA"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" not in content
        assert "input-error" not in content
        assert "SW1A 1AA" in content

    @override_settings(
        POSTCODES_API_URL="https://api.example.com/postcodes/",
        POSTCODES_API_KEY="test-key",
    )
    @patch("requests.get")
    def test_valid_postcode_returns_success(self, mock_get, client, db):
        """Test that a valid postcode returns success styling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": True}
        mock_get.return_value = mock_response

        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "SW1A 1AA"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" in content
        assert "SW1A 1AA" in content

    @override_settings(
        POSTCODES_API_URL="https://api.example.com/postcodes/",
        POSTCODES_API_KEY="test-key",
    )
    @patch("requests.get")
    def test_invalid_postcode_returns_error(self, mock_get, client, db):
        """Test that an invalid postcode returns error styling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": False}
        mock_get.return_value = mock_response

        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "INVALID"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-error" in content

    @override_settings(
        POSTCODES_API_URL="https://api.example.com/postcodes/",
        POSTCODES_API_KEY="test-key",
    )
    @patch("requests.get")
    def test_api_error_returns_neutral_styling(self, mock_get, client, db):
        """Test that API errors result in neutral styling (no validation shown)."""
        mock_get.side_effect = Exception("API error")

        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "SW1A 1AA"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "input-success" not in content
        assert "input-error" not in content

    @override_settings(
        POSTCODES_API_URL="https://api.example.com/postcodes/",
        POSTCODES_API_KEY="test-key",
    )
    @patch("requests.get")
    def test_postcode_is_uppercased(self, mock_get, client, db):
        """Test that postcodes are converted to uppercase."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": True}
        mock_get.return_value = mock_response

        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "sw1a 1aa"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "SW1A 1AA" in content

    @override_settings(
        POSTCODES_API_URL="https://api.example.com/postcodes/",
        POSTCODES_API_KEY="test-key",
    )
    @patch("requests.get")
    def test_htmx_attributes_preserved_in_postcode_response(self, mock_get, client, db):
        """Test that HTMX attributes are preserved in the postcode response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": True}
        mock_get.return_value = mock_response

        response = client.post(
            "/surveys/validate/postcode/",
            {"post_code": "SW1A 1AA"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'hx-post="/surveys/validate/postcode/"' in content
        assert 'hx-trigger="blur, keyup changed delay:500ms"' in content
        assert 'hx-target="closest label"' in content
        assert 'hx-swap="outerHTML"' in content

    def test_get_request_not_allowed(self, client, db):
        """Test that GET requests are not allowed."""
        response = client.get("/surveys/validate/postcode/")
        assert response.status_code == 405
