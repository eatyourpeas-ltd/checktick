---
title: Infrastructure Logging
category: self-hosting
priority: 4
---

# Infrastructure Logging (OpenObserve Integration)

This document covers the optional self-hosted logging configuration for CheckTick via OpenObserve.

## Overview

CheckTick includes an optional OpenObserve log exporter that sends ERROR-level logs to an OpenObserve server via HTTP. This feature is **disabled by default** and only activates when explicitly configured via environment variables.

### For Platform Users

If you're hosting CheckTick on Azure, AWS, or another platform with built-in logging (Application Insights, CloudWatch, etc.), this exporter **can be safely ignored**. It has no impact on performance when disabled and does not interfere with platform-native logging.

## Configuration

### Environment Variables

Set the following environment variables to enable the OpenObserve exporter:

#### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `LOGS_BASE_URL` | OpenObserve server URL (with port) | `https://logs.checktick.uk:5080` |
| `LOGS_KEY` | Basic auth credentials (`username:password`) | `USERNAME:HASHED_PASSWORD (find this in the OpenObserve UI)` |

#### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `LOGS_ORGANISATION` | OpenObserve organization name | `checktick` |
| `LOGS_STREAM_NAME` | OpenObserve stream name | `prod` |

**Note**: The `LOGS_KEY` uses Basic authentication with username and password formatted as `username:password`, not a bearer token or API key.

### Automatic Fallback

If environment variables are not set, CheckTick automatically falls back to your hosting platform's default logging behavior (e.g., Azure Application Insights, AWS CloudWatch). No logging is lost—only the optional OpenObserve export is skipped.

## How It Works

### Enabled State

When both `LOGS_BASE_URL` and `LOGS_KEY` are configured:

1. The exporter is **automatically enabled**
2. It captures all **ERROR-level** logs from the root logger
3. Logs are exported to OpenObserve in JSON format
4. The exporter is visible in Django's logging configuration but has minimal overhead

### Disabled State

When credentials are missing:

1. The exporter is **silently disabled**
2. Zero overhead on application performance
3. No network requests are made
4. Logs still go to console and platform-native logging

### Log Payload Structure

Each log record sent to OpenObserve includes:

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

**Security**: Only ERROR-level logs are sent. No PII or patient data is included. Stack traces are sanitized to exclude sensitive context.

## Error Handling

### Automatic Backoff

The exporter implements intelligent error handling:

- **Initial error**: Backs off for 30 seconds before retrying
- **Subsequent errors**: Continue backing off to prevent API flooding
- **Recovery**: On successful send, the backoff counter resets
- **Debug logging**: When `DEBUG` level is enabled for the exporter module, error details are logged locally

### Rate Limiting

To prevent overwhelming the OpenObserve ingest API:

- Minimum **500ms interval** between sends
- If multiple errors occur within this window, they are coalesced
- This ensures consistent throttling regardless of error frequency

### Silent Failures

Network failures or OpenObserve unavailability:

- **Never** raise exceptions to the application
- **Never** block request processing
- Failures are logged at DEBUG level only
- Application continues normally without degradation

## Debugging and Monitoring

### Viewing Logs in OpenObserve

1. Open OpenObserve web UI
2. Navigate to **Logs** section
3. Select appropriate organization and stream
4. Filter by `level=ERROR`
5. Use time range selector for contextual search

### Enabling Debug Logging

To troubleshoot the exporter locally, enable debug logging:

```python
# In checktick_app/settings.py LOGGING configuration
"loggers": {
    "checktick_app.core.log_exporters": {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    },
}
```

### Checking Exporter Status

From Django shell:

```python
from django.conf import settings
from checktick_app.core.log_exporters import OpenObserveExporter

exporter_config = settings.LOGGING["handlers"]["openobserve"]
handler = settings.LOGGING["handlers"]["openobserve"]["class"](**exporter_config)
print(f"Enabled: {handler.enabled}")
print(f"Organization: {handler.organization}")
print(f"Stream: {handler.stream_name}")
print(f"Last Send: {handler.last_send}")
```

### Testing Connectivity

Add a test endpoint to verify log flow:

```python
# checktick_app/views/testing.py
import logging

logger = logging.getLogger(__name__)

def test_logging_endpoint(request):
    """Test endpoint to trigger log export. Staff only."""
    if request.user.is_staff:
        try:
            logger.error("Test OpenObserve log export")
            return HttpResponse("Log test initiated")
        except Exception as e:
            logger.exception(f"Test error: {e}")
            raise
    return HttpResponse("Access denied", status=403)
```

### Connection Testing

Verify the exporter is configured correctly:

```bash
# Check environment variables
echo $LOGS_BASE_URL
echo $LOGS_KEY

# In Django shell
python manage.py shell
>> from django.conf import settings
>> settings.LOGGING["handlers"]["openobserve"]
```

## Deployment Checklist

- [ ] `LOGS_BASE_URL` is set and points to accessible OpenObserve server
- [ ] `LOGS_KEY` is in correct format (username:password for Basic auth)
- [ ] Organization name is correct for the target OpenObserve instance
- [ ] Stream name is appropriate for the environment (prod/test/dev)
- [ ] HTTPS is used in production (TLS enforced by exporter)
- [ ] Network connectivity from application server to OpenObserve verified
- [ ] Logs visible in OpenObserve UI after triggering an error
- [ ] Debug logging disabled in production

## Troubleshooting

### Exporter Not Sending Logs

**Check credentials are set**:
```bash
docker ps | grep checktick
docker exec checktick-app env | grep LOGS
```

**Verify OpenObserve accessibility**:
```bash
curl -u admin@checktick.uk:o2oi_AtVFQgvGfEh1uBMfBBWKzpZ3exvxpAXW \
  -k https://logs.checktick.uk:5080/
```

**Check network connectivity**:
```bash
# From application container
python -c "import requests; r = requests.get('https://logs.checktick.uk:5080', verify=False); print(r.status_code)"
```

### Rate Limiting Issues

If experiencing rate limiting:

1. Verify you're not over-logging at ERROR level
2. Increase `send_interval` in exporter code if needed
3. Check OpenObserve ingest rate limits (typically 1000 req/sec)

### Authentication Failures

If receiving 401/403 errors:

1. Verify `LOGS_KEY` format is `username:password` (not just password)
2. Confirm credentials exist in target OpenObserve instance
3. Check for URL encoding issues in special characters
4. Verify organization has proper write permissions for the stream

### Connection Timeouts

If exporter times out:

1. Check network connectivity between application and OpenObserve
2. Verify firewall rules allow traffic on port 5080
3. Increase timeout in exporter (default 10 seconds)
4. Check for TLS certificate issues (ensure CA is trusted)

## Performance Considerations

### Resource Usage

- **Memory**: Minimal (~1KB per instance)
- **CPU**: Negligible (<1ms per ERROR log)
- **Network**: Low bandwidth (~2KB per log entry with compression)

### Optimization Strategies

1. **Disable when not needed**: Exporter has zero overhead when disabled
2. **Adjust logging levels**: Reduce ERROR logging volume if possible
3. **Batch sends**: For high-volume deployments, consider batching multiple log entries
4. **Async delivery**: For extreme throughput needs, consider async queue-based logging

## Security Considerations

### API Key Handling

- Never hardcode credentials in source code
- Use environment variables or secret management systems
- Keys are transmitted via HTTP Basic Auth (base64-encoded `username:password`)

### Data Protection

- Only ERROR-level logs are transmitted
- No patient-identifiable information is included
- Stack traces are sanitized before transmission
- Custom exception fields must be reviewed for sensitive data

### Network Security

- HTTPS is strongly recommended for production
- TLS certificate verification is enforced (disable only for testing)
- Connection timeout prevents hanging on network issues

## References

- [OpenObserve Documentation](https://openobserve.ai/docs/)
- [OpenObserve Ingest API](https://openobserve.ai/docs/api-documentation/)
- [Django Logging Configuration](https://docs.djangoproject.com/en/stable/topics/logging/)
- [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)
