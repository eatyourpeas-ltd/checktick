"""
Tests for IMD (Index of Multiple Deprivation) service.
"""

from unittest.mock import MagicMock, patch

from django.test import override_settings

from checktick_app.surveys.services.imd_service import IMDResult, IMDService


class TestIMDResult:
    """Tests for IMDResult dataclass."""

    def test_is_valid_when_has_decile(self):
        result = IMDResult(postcode="SW1A 1AA", imd_decile=5, imd_rank=12345)
        assert result.is_valid is True

    def test_is_not_valid_when_no_decile(self):
        result = IMDResult(postcode="SW1A 1AA", imd_decile=None, imd_rank=None)
        assert result.is_valid is False

    def test_is_not_valid_when_has_error(self):
        result = IMDResult(
            postcode="SW1A 1AA", imd_decile=5, imd_rank=12345, error="Some error"
        )
        assert result.is_valid is False


class TestIMDServiceConfiguration:
    """Tests for IMDService configuration checks."""

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    def test_is_configured_returns_true_when_both_set(self):
        assert IMDService.is_configured() is True

    @override_settings(IMD_API_URL="", IMD_API_KEY="test-key")
    def test_is_configured_returns_false_when_url_empty(self):
        assert IMDService.is_configured() is False

    @override_settings(IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="")
    def test_is_configured_returns_false_when_key_empty(self):
        assert IMDService.is_configured() is False


class TestIMDServiceLookup:
    """Tests for IMDService.lookup_imd method."""

    def test_empty_postcode_returns_error(self):
        result = IMDService.lookup_imd("")
        assert result.is_valid is False
        assert result.error == "Empty postcode"

    def test_whitespace_only_postcode_returns_error(self):
        result = IMDService.lookup_imd("   ")
        assert result.is_valid is False
        assert result.error == "Empty postcode"

    @override_settings(IMD_API_URL="", IMD_API_KEY="")
    def test_returns_error_when_not_configured(self):
        result = IMDService.lookup_imd("SW1A 1AA")
        assert result.is_valid is False
        assert result.error == "IMD API not configured"

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_successful_lookup_returns_decile(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "imd_decile": 7,
            "imd_rank": 15234,
        }
        mock_get.return_value = mock_response

        result = IMDService.lookup_imd("SW1A 1AA")

        assert result.is_valid is True
        assert result.imd_decile == 7
        assert result.imd_rank == 15234
        assert result.error is None

        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://api.example.com/imd"
        assert call_args[1]["params"]["postcode"] == "SW1A1AA"  # Spaces removed
        assert call_args[1]["params"]["quantile"] == 10  # Default decile
        assert call_args[1]["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_lookup_with_quantile_field_name(self, mock_get):
        """Test handling of API responses using 'quantile' instead of 'imd_decile'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quantile": 3,
            "rank": 5000,
        }
        mock_get.return_value = mock_response

        result = IMDService.lookup_imd("E1 6AN")

        assert result.is_valid is True
        assert result.imd_decile == 3
        assert result.imd_rank == 5000

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_404_returns_not_found_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = IMDService.lookup_imd("INVALID")

        assert result.is_valid is False
        assert result.error == "Postcode not found in IMD data"

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_500_returns_api_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = IMDService.lookup_imd("SW1A 1AA")

        assert result.is_valid is False
        assert "API error: 500" in result.error

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_timeout_returns_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.Timeout()

        result = IMDService.lookup_imd("SW1A 1AA")

        assert result.is_valid is False
        assert result.error == "API timeout"

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_request_exception_returns_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        result = IMDService.lookup_imd("SW1A 1AA")

        assert result.is_valid is False
        assert "Request error" in result.error

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_postcode_normalized(self, mock_get):
        """Test that postcodes are normalized (spaces removed, uppercase)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"imd_decile": 5, "imd_rank": 10000}
        mock_get.return_value = mock_response

        # Test with lowercase and spaces
        IMDService.lookup_imd("sw1a  1aa")

        call_args = mock_get.call_args
        assert call_args[1]["params"]["postcode"] == "SW1A1AA"

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_custom_quantile(self, mock_get):
        """Test custom quantile parameter (e.g., quintile)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"quantile": 2}
        mock_get.return_value = mock_response

        _ = IMDService.lookup_imd("SW1A 1AA", quantile=5)

        call_args = mock_get.call_args
        assert call_args[1]["params"]["quantile"] == 5

    @override_settings(
        IMD_API_URL="https://api.example.com/imd", IMD_API_KEY="test-key"
    )
    @patch("checktick_app.surveys.services.imd_service.requests.get")
    def test_response_without_decile_data(self, mock_get):
        """Test handling of responses that don't include decile data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"postcode": "SW1A1AA"}  # No decile
        mock_get.return_value = mock_response

        result = IMDService.lookup_imd("SW1A 1AA")

        assert result.is_valid is False
        assert "No IMD data available" in result.error
