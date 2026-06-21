"""
Log exporter for OpenObserve.

Exports log records to OpenObserve via HTTP, supporting structured JSON payloads
with timestamps, severity levels, logger names, and message content.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OpenObserveExporter(logging.Handler):
    """
    Custom log handler that exports to OpenObserve via HTTP POST.

    This handler is DISABLED BY DEFAULT when credentials are not configured.
    It will only send logs when BOTH LOGS_BASE_URL and LOGS_KEY are set.

    For self-hosters using platform logging (Azure, AWS, etc.), this exporter
    can be safely ignored and does not impact application performance.

    Required environment variables:
    - LOGS_BASE_URL: OpenObserve server URL (required for activation)
    - LOGS_KEY or LOGS_ACCESS_KEY: OpenObserve API key/token (required for activation)

    Optional environment variables:
    - LOGS_ORGANISATION: OpenObserve organization name (default: "checktick")
    - LOGS_STREAM_NAME: OpenObserve stream name (default: "prod")
    """

    DEFAULT_BASE_URL = "http://localhost:5080"
    DEFAULT_ORGANISATION = "checktick"
    DEFAULT_STREAM_NAME = "prod"

    def __init__(
        self,
        base_url: Optional[str] = None,
        key: Optional[str] = None,
        organization: Optional[str] = None,
        stream_name: Optional[str] = None,
        enabled: Optional[bool] = True,  # Ignored; auto-determined by credentials
    ):
        """
        Initialize the OpenObserve exporter.

        The exporter is automatically DISABLED when credentials are missing.
        This prevents unnecessary overhead for self-hosters using platform logging.
        """
        super().__init__(logging.ERROR)  # Set level to ERROR by default

        # Auto-determine enabled status based on credentials
        self.enabled = (
            bool(bool(key is not None and base_url is not None))
            and settings.LOGS_KEY is not None
            and settings.LOGS_BASE_URL is not None
        )

        # Only set credentials if enabled
        if self.enabled:
            self.base_url = base_url or settings.LOGS_BASE_URL
            self.key = key or settings.LOGS_KEY or settings.LOGS_ACCESS_KEY
            self.organization = (
                organization or settings.LOGS_ORGANISATION or self.DEFAULT_ORGANISATION
            )
            self.stream_name = stream_name or (
                settings.LOGS_STREAM_NAME or self.DEFAULT_STREAM_NAME
            )
            self.last_send = time.time()
            self.send_interval = 0.5  # seconds between sends
            self._last_error_time = 0.0
            self._error_backoff = 30  # seconds
        else:
            # Silent handler - no overhead when disabled
            logger.debug(f"OpenObserve exporter disabled: missing credentials")

    def make_request(self, record: logging.LogRecord) -> None:
        """Send log record to OpenObserve via HTTP POST. Returns immediately if disabled."""
        if not self.enabled:
            return
        if self._should_skip_record(record):
            return

        now = time.time()
        # Rate limiting: skip if too recent
        if now - self.last_send < self.send_interval:
            return

        try:
            payload = self._create_payload(record)
            url = self._get_endpoint()
            headers = self._get_headers()

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            self._last_error_time = 0
            self.last_send = now

        except Exception as e:
            self._last_error_time = time.time()
            self.last_send = time.time()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"OpenObserve error: {e}")

    def _create_payload(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Create structured JSON payload for OpenObserve."""
        timestamp = int(record.created * 1000)

        log_fields = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "thread": record.thread,
            "threadName": record.threadName,
            "process": record.process,
            "processName": record.processName,
        }

        if record.exc_info:
            import traceback

            log_fields["exception"] = traceback.format_exception(*record.exc_info)

        extra_fields = {}
        if hasattr(record, "__dict__"):
            for key in dir(record):
                if not key.startswith("_") and key not in log_fields:
                    value = getattr(record, key)
                    if isinstance(value, (str, int, float, bool, type(None))):
                        extra_fields[key] = value

        return {
            "timestamp": timestamp,
            "organization": self.organization,
            "stream": self.stream_name,
            "body": {**log_fields, **extra_fields},
        }

    def _get_endpoint(self) -> str:
        """Get the OpenObserve Ingest API endpoint."""
        return f"{self.base_url}/api/{self.organization}/{self.stream_name}/_"

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for the request."""
        auth_header = f"Basic {self.key}"
        return {
            "User-Agent": "CheckTick-Logger/1.0",
            "Content-Type": "application/json",
            "Authorization": auth_header,
            "X-Observation-Accepted-Data-Format": "json",
        }
