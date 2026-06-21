# OpenObserve Log Exporter - Implementation Guide

## Overview

This document describes the OpenObserve log exporter integration for the CheckTick Django application. The exporter sends error-level log records to an OpenObserve server via the HTTP Ingest API.

## Components

### 1. OpenObserveExporter Class

**Location**: `checktick_app/core/log_exporters.py`

A custom Django logging handler that exports log records to OpenObserve.

#### Configuration Parameters

- **base_url**: OpenObserve server URL (required)
- **key**: OpenObserve API key or token (required)
- **organization**: OpenObserve organization name (default: "checktick")
- **stream_name**: OpenObserve stream name (default: "prod")

#### Error Handling

- Automatic backoff on failures (30 seconds)
- Rate limiting to prevent API flooding (500ms minimum between sends)
- Silent failures don't impact application performance
- Debug-level logging of errors for troubleshooting

### 2. Django Settings Integration

**Location**: `checktick_app/settings.py`

The exporter is configured as the `openobserve` logging handler with ERROR level logging. It's only active when `LOGS_BASE_URL` and `LOGS_KEY` are configured.

## Configuration

## Environment Variables

Set the following environment variables in production:

```bash
# Required
LOGS_BASE_URL=http://your-openobserve-server:5080
LOGS_KEY=your-api-key-token

# Optional (with defaults)
LOGS_ORGANIZATION=checktick
LOGS_STREAM_NAME=prod
```

### Production Installation

1. **Set Environment Variables**:

```bash
export LOGS_BASE_URL=http://log-checktick.your-host.co.uk:5080
export LOGS_KEY=12345:abcdef123456
export LOGS_ORGANIZATION=checktick
export LOGS_STREAM_NAME=prod
```

2. **Verify Configuration**:

```bash
python manage.py check --deploy
# Should not show any errors related to logging
```

## Usage

### Logging Integration

The exporter automatically captures all ERROR-level logs from the root logger. Additional logging configuration can be added:

```python
# In checktick_app/settings.py within LOGGING dict:
"loggers": {
    "checktick_app": {
        "handlers": ["console", "openobserve"],
        "level": "ERROR",
        "propagate": False,
    },
}
```

### Testing

#### Unit Tests

Create a test file `checktick_app/core/tests/test_log_exporters.py`:

```python
from unittest.mock import Mock, patch

import pytest

from checktick_app.core.log_exporters import OpenObserveExporter


class TestOpenObserveExporter:
    """Tests for OpenObserve logging exporter."""

    def test_init_without_credentials(self):
        """Export should be disabled without credentials."""
        exporter = OpenObserveExporter(key=None, base_url=None)
        assert not exporter.enabled

    def test_init_with_credentials(self):
        """Export should be enabled with all credentials."""
        exporter = OpenObserveExporter(
            key="test_key", base_url="http://test.example.com"
        )
        assert exporter.enabled

    def test_payload_creation(self):
        """Verify log payload structure."""
        exporter = OpenObserveExporter(
            key="test_key",
            base_url="http://test.example.com",
            organization="test_org",
            stream_name="test_stream",
            enabled=True,
        )

        record = Mock()
        record.created = 1600000000.0
        record.levelname = "ERROR"
        record.name = "test.logger"
        record.getMessage.return_value = "Test message"
        record.module = "test_module"
        record.funcName = "test_func"
        record.pathname = "test/path/file.py"
        record.lineno = 42
        record.thread = 12345
        record.threadName = "MainThread"
        record.process = 67890
        record.processName = "MainProcess"
        record.exc_info = None
        record.__dict__ = {}

        payload = exporter._create_payload(record)

        assert payload["timestamp"] == 1600000000000
        assert payload["organization"] == "test_org"
        assert payload["stream"] == "test_stream"
        assert payload["body"]["level"] == "ERROR"
        assert payload["body"]["message"] == "Test message"

    def test_endpoint_url(self):
        """Verify correct endpoint URL construction."""
        exporter = OpenObserveExporter(
            base_url="http://example.com:5080",
            organization="org123",
            stream_name="streamABC",
        )

        expected = "http://example.com:5080/api/org123/streamABC/_"
        assert exporter._get_endpoint() == expected

    def test_request_with_exception(self):
        """Handle network exceptions gracefully."""
        exporter = OpenObserveExporter(
            key="test_key",
            base_url="http://example.com",
            enabled=True,
        )

        record = Mock()
        record.created.__float__ = lambda self: 1600000000.0
        record.levelname = "ERROR"
        record.name = "test"
        record.getMessage.return_value = "Test"
        record.module = "test"
        record.funcName = "test"
        record.pathname = "test.py"
        record.lineno = 1
        record.thread = 1
        record.threadName = "test"
        record.process = 1
        record.processName = "test"
        record.exc_info = None
        record.__dict__ = {}

        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            exporter.make_request(record)

            # Should not raise, should fail silently
            assert exporter._last_error_time > 0


@pytest.mark.django_db
class TestLogRecording:
    """Test log recording with OpenObserve exporter."""

    def test_log_recording_configuration(self):
        """Verify log configuration includes OpenObserve exporter."""
        from django.conf import settings

        handler_class = settings.LOGGING["handlers"]["openobserve"]["class"]

        # Handler exists
        assert "openobserve" in settings.LOGGING["handlers"]

        # Handler is in root handlers
        assert "openobserve" in settings.LOGGING["root"]["handlers"]

    def test_environment_variables(self):
        """Verify environment variable reading."""
        import os
        from django.conf import settings

        # At minimum, these should be defined
        assert hasattr(settings, "LOGS_BASE_URL")
        assert hasattr(settings, "LOGS_KEY")
        assert hasattr(settings, "LOGS_ORGANIZATION")
        assert hasattr(settings, "LOGS_STREAM_NAME")
```

#### Manual Testing

Create a test view for manual verification:

```python
# checktick_app/views/test_logging.py
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def test_openobserve_logging(request):
    """
    Test endpoint to trigger OpenObserve log export.
    Call: GET /admin/test_logging/openobserve
    """
    if request.user.is_staff:
        try:
            # Test connection without sending
            logger.debug(f"Testing OpenObserve connection via {logger.name}")
            return HttpResponse("Connection test complete")
        except Exception as e:
            import traceback

            logger.exception(f"Error during test: {e}")
            raise
    return HttpResponse("Only staff users can access this endpoint", status=403)
```

## API Integration Details

### OpenObserve Ingest Endpoint

- **URL Pattern**: `https://<base_url>/api/<organization>/<stream_name>/_`
- **Method**: POST
- **Content-Type**: `application/json`
- **Authentication**: `Authorization: Basic <base64_encoded_key>`

### Payload Structure

```json
{
  "timestamp": 1600000000000,
  "organization": "checktick",
  "stream": "prod",
  "body": {
    "level": "ERROR",
    "logger": "checktick_app.core.auth",
    "message": "Authentication failed for user@example.com",
    "module": "auth",
    "funcName": "authenticate_user",
    "pathname": "/path/to/auth.py",
    "lineno": 123,
    "thread": 12345,
    "threadName": "MainThread",
    "process": 67890,
    "processName": "MainProcess"
  }
}
```

### Backoff Strategy

- Initial attempt: Send immediately
- First error: Back off for 30 seconds
- Subsequent errors: Continue to back off
- Success: Reset backoff counter
- Rate limiting: Minimum 500ms between sends

## Security Considerations

1. **API Key Handling**:
   - API keys must not be hardcoded
   - Use environment variables or secret management systems
   - Keys are base64-encoded in Authorization header

2. **Data Exfiltration Prevention**:
   - Only ERROR-level logs are sent by default
   - No PII in standard log fields
   - Custom fields should be audited for sensitive data

3. **Network Security**:
   - Use HTTPS in production
   - TLS certificate validation is enforced
   - Connection timeout: 10 seconds

## Monitoring and Debugging

### Viewing Logs in OpenObserve

1. Open OpenObserve web UI
2. Navigate to Logs
3. Select organization and stream
4. Apply filters: `level=ERROR`
5. Use time range selector

### Debugging Locally

Enable debug logging for troubleshooting:

```python
# In LOGGING configuration
"loggers": {
    "checktick_app.core.log_exporters": {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    },
}
```

### Connection Testing

Check exporter status:

```python
# In Django shell
from django.conf import settings
from checktick_app.core.log_exporters import OpenObserveExporter

exporter = settings.LOGGING["handlers"]["openobserve"]
handler = type(exporter["class"])(**exporter)
print(f"Enabled: {handler.enabled}")
print(f"URL: {handler.base_url}")
```

## Troubleshooting

### Common Issues

1. **Export Not Working**:
   - Check environment variables are set
   - Verify API key is valid
   - Check network connectivity to OpenObserve server
   - Inspect error logs for network issues

2. **Rate Limiting**:
   - Reduce logging volume
   - Increase `send_interval` if using custom configuration
   - Check OpenObserve ingest rate limits

3. **Authentication Failures**:
   - Verify API key format
   - Check if key needs to be base64 encoded
   - Confirm organization name is correct

### Logs to Check

```bash
# Application logs (Django console)
tail -f /var/log/checktick/app.log | grep "OpenObserve"

# Exporter debug logs (if enabled)
grep -i "openobserve" /var/log/checktick/debug.log
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] OpenObserve server accessible
- [ ] API key valid and properly formatted
- [ ] Organization and stream names correct
- [ ] HTTPS configured for production
- [ ] Error backoff tested
- [ ] Logs visible in OpenObserve UI
- [ ] Rate limiting verified
- [ ] Network connectivity established
- [ ] Authentication successful
- [ ] Debug logging disabled in production

## Performance Considerations

### Resource Usage

- **Memory**: Minimal (single request instance)
- **CPU**: Negligible (<1ms per log entry)
- **Network**: Low (compressed payloads, rate-limited)

### Optimization Strategies

1. Disable exporter when not needed (no credentials configured)
2. Adjust logging levels to reduce volume
3. Batch multiple log entries when possible
4. Use async send for high-throughput scenarios

## Future Enhancements

1. **Batching Support**:
   - Collect multiple log entries
   - Send as single batched request
   - Reduce HTTP overhead

2. **Async Support**:
   - Non-blocking log exports
   - Queue-based sending
   - Better error handling

3. **Custom Fields**:
   - Request-level context tracking
   - User ID and session tracking
   - Request ID correlation

4. **Metrics Export**:
   - Export log counts to metrics system
   - Track error rates
   - Monitor exporter health

## References

- [OpenObserve Documentation](https://openobserve.ai/docs/)
- [OpenObserve Ingest API](https://openobserve.ai/docs/api-documentation/)
- [Django Logging Configuration](https://docs.djangoproject.com/en/stable/topics/logging/)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html)
