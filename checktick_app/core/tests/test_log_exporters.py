import logging
import unittest
from unittest.mock import MagicMock, patch

from django.test import override_settings

from checktick_app.core.log_exporters import OpenObserveExporter


class TestOpenObserveExporter(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://test-oo:5080"
        self.key = "test-key"
        self.org = "test-org"
        self.stream = "test-stream"

    def create_exporter(self, **kwargs):
        return OpenObserveExporter(
            base_url=kwargs.get("base_url", self.base_url),
            key=kwargs.get("key", self.key),
            organization=kwargs.get("organization", self.org),
            stream_name=kwargs.get("stream", self.stream),
        )

    def test_disabled_without_credentials(self):
        """Exporter should be disabled if no credentials are provided."""
        with override_settings(LOGS_KEY=None, LOGS_BASE_URL=None):
            exporter = OpenObserveExporter(base_url=None, key=None)
            self.assertFalse(exporter.enabled)

    def test_enabled_with_credentials(self):
        """Exporter should be enabled when credentials are provided."""
        exporter = self.create_exporter()
        self.assertTrue(exporter.enabled)

    def test_payload_structure(self):
        """Verify that the created payload has the correct structure and fields."""
        exporter = self.create_exporter()

        # Create a standard log record
        logger = logging.getLogger("test_logger")
        record = logger.makeRecord(
            "test_logger",
            logging.ERROR,
            "test_path",
            10,
            "Test error message",
            None,
            None,
        )

        # Add custom attributes to simulate the LoggingContextMiddleware
        record.user_id = "user-123"
        record.request_id = "req-456"
        record.remote_addr = "1.2.3.4"

        payload = exporter._create_payload(record)

        self.assertIn("timestamp", payload)
        self.assertEqual(payload["organization"], self.org)
        self.assertEqual(payload["stream"], self.stream)

        body = payload["body"]
        self.assertEqual(body["message"], "Test error message")
        self.assertEqual(body["level"], "ERROR")
        self.assertEqual(body["logger"], "test_logger")
        # Check that our contextual fields are captured
        self.assertEqual(body["user_id"], "user-123")
        self.assertEqual(body["request_id"], "req-456")
        self.assertEqual(body["remote_addr"], "1.2.3.4")

    def test_exception_payload(self):
        """Verify that exceptions are correctly formatted in the payload."""
        exporter = self.create_exporter()

        try:
            raise ValueError("Something went wrong")
        except ValueError:
            import sys

            record = logging.getLogger("test").makeRecord(
                "test",
                logging.ERROR,
                "test_path",
                10,
                "An error occurred",
                None,
                sys.exc_info(),
            )

        payload = exporter._create_payload(record)
        self.assertIn("exception", payload["body"])
        self.assertTrue(
            any(
                "ValueError: Something went wrong" in line
                for line in payload["body"]["exception"]
            )
        )

    @patch("requests.post")
    def test_successful_emission(self, mock_post):
        """Verify that emit makes a valid HTTP request."""
        mock_post.return_value.status_code = 200

        exporter = self.create_exporter()
        logger = logging.getLogger("test")
        record = logger.makeRecord(
            "test", logging.ERROR, "test_path", 10, "Error!", None, None
        )

        # Trigger the request
        # We call make_request directly because emit() uses it
        exporter.make_request(record)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], f"{self.base_url}/api/{self.org}/{self.stream}/_")
        self.assertEqual(kwargs["headers"]["Authorization"].startswith("Basic "), True)
        self.assertIn("body", kwargs["json"])

    @patch("requests.post")
    def test_error_handling_and_backoff(self, mock_post):
        """Verify that HTTP errors trigger backoff."""
        # Mock a 500 error
        mock_post.return_value.raise_for_status.side_effect = Exception("Server Error")

        exporter = self.create_exporter()
        logger = logging.getLogger("test")
        record = logger.makeRecord(
            "test", logging.ERROR, "test_path", 10, "Error!", None, None
        )

        # First attempt fails
        exporter.make_request(record)

        self.assertGreater(exporter._last_error_time, 0)

        # Second attempt should be skipped due to backoff
        mock_post.reset_mock()
        exporter.make_request(record)
        mock_post.assert_not_called()

    def test_level_filtering(self):
        """Verify that logs below the set level are skipped."""
        exporter = self.create_exporter()
        exporter.level = logging.ERROR

        # Create an INFO record
        logger = logging.getLogger("test")
        record = logger.makeRecord(
            "test", logging.INFO, "test_path", 10, "Info message", None, None
        )

        self.assertTrue(exporter._should_skip_record(record))

        # Create an ERROR record
        record_err = logger.makeRecord(
            "test", logging.ERROR, "test_path", 10, "Error message", None, None
        )
        self.assertFalse(exporter._should_skip_record(record_err))

    @patch("requests.post")
    def test_rate_limiting(self, mock_post):
        """Verify that logs are skipped if sent too frequently."""
        mock_post.return_value.status_code = 200
        exporter = self.create_exporter()
        exporter.send_interval = 1.0  # 1 second

        logger = logging.getLogger("test")
        record = logger.makeRecord(
            "test", logging.ERROR, "test_path", 10, "Msg", None, None
        )

        # First request goes through
        exporter.make_request(record)
        self.assertEqual(mock_post.call_count, 1)

        # Immediate second request should be rate-limited
        exporter.make_request(record)
        self.assertEqual(mock_post.call_count, 1)
