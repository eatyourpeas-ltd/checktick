"""
Hosting provider API integration for fetching container logs.

This service integrates with hosting provider APIs (e.g., Northflank, Railway,
Render, Fly.io) to retrieve application logs for the Platform Admin dashboard.
Only accessible to superusers.

The implementation uses a generic interface that can be adapted for different
hosting providers by setting appropriate environment variables.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone
import requests

logger = logging.getLogger(__name__)


@dataclass
class HostingConfig:
    """Configuration for hosting provider API."""

    api_token: str
    api_base_url: str
    project_id: str
    service_id: str

    @classmethod
    def from_settings(cls) -> Optional["HostingConfig"]:
        """Create config from Django settings."""
        token = getattr(settings, "HOSTING_API_TOKEN", "")
        base_url = getattr(
            settings, "HOSTING_API_BASE_URL", "https://api.northflank.com/v1"
        )
        project = getattr(settings, "HOSTING_PROJECT_ID", "")
        service = getattr(settings, "HOSTING_SERVICE_ID", "")

        if not all([token, project, service]):
            return None
        return cls(
            api_token=token,
            api_base_url=base_url,
            project_id=project,
            service_id=service,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token and self.project_id and self.service_id)


@dataclass
class LogEntry:
    """Represents a single log entry."""

    timestamp: datetime
    level: str
    message: str
    source: str = "hosting"
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class HostingLogsService:
    """
    Service for fetching logs from hosting provider APIs.

    Supports multiple hosting providers through configuration:
    - Northflank: Set HOSTING_API_BASE_URL to https://api.northflank.com/v1
    - Railway: Set HOSTING_API_BASE_URL to https://backboard.railway.app
    - Render: Set HOSTING_API_BASE_URL to https://api.render.com/v1
    - Custom: Set HOSTING_API_BASE_URL to your provider's API endpoint

    The logs endpoint pattern is: {base_url}/projects/{project_id}/services/{service_id}/logs
    Adjust HOSTING_LOGS_ENDPOINT_PATTERN in settings for different providers.
    """

    def __init__(self, config: Optional[HostingConfig] = None):
        self.config = config or HostingConfig.from_settings()

    @property
    def is_available(self) -> bool:
        """Check if hosting logs integration is configured."""
        return self.config is not None and self.config.is_configured

    def _get_headers(self) -> dict:
        """Get API headers with authentication."""
        return {
            "Authorization": f"Bearer {self.config.api_token}",
            "Content-Type": "application/json",
        }

    def _get_logs_url(self) -> str:
        """Build the logs endpoint URL based on configuration."""
        pattern = getattr(
            settings,
            "HOSTING_LOGS_ENDPOINT_PATTERN",
            "{base_url}/projects/{project_id}/services/{service_id}/logs",
        )
        return pattern.format(
            base_url=self.config.api_base_url.rstrip("/"),
            project_id=self.config.project_id,
            service_id=self.config.service_id,
        )

    def fetch_logs(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        log_type: str = "all",
    ) -> tuple[list[LogEntry], Optional[str]]:
        """
        Fetch logs from hosting provider API.

        Args:
            since: Start time for logs (default: last 24 hours)
            until: End time for logs (default: now)
            limit: Maximum number of log entries to return
            log_type: Filter by log type - 'all', 'error', 'warn', 'info'

        Returns:
            Tuple of (list of LogEntry objects, error message if any)
        """
        if not self.is_available:
            return [], "Hosting logs API is not configured"

        # Default to last 24 hours
        if since is None:
            since = timezone.now() - timezone.timedelta(hours=24)
        if until is None:
            until = timezone.now()

        try:
            url = self._get_logs_url()

            params = {
                "startTime": since.isoformat(),
                "endTime": until.isoformat(),
                "limit": min(limit, 500),  # API max is usually 500
            }

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                logger.error("Hosting API authentication failed")
                return [], "Authentication failed - check API token"

            if response.status_code == 404:
                logger.error("Hosting project or service not found")
                return [], "Project or service not found"

            if response.status_code != 200:
                logger.error(f"Hosting API error: {response.status_code}")
                return [], f"API error: {response.status_code}"

            data = response.json()
            # Handle different response formats from various providers
            logs_data = data.get("logs", data.get("data", data.get("entries", [])))
            logs = self._parse_logs(logs_data, log_type)

            return logs, None

        except requests.exceptions.Timeout:
            logger.error("Hosting API timeout")
            return [], "Request timed out"
        except requests.exceptions.RequestException as e:
            logger.error(f"Hosting API request failed: {e}")
            return [], f"Request failed: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error fetching hosting logs")
            return [], f"Unexpected error: {str(e)}"

    def _parse_logs(self, raw_logs: list, log_type: str) -> list[LogEntry]:
        """Parse raw log data into LogEntry objects."""
        entries = []

        for log in raw_logs:
            try:
                # Support various log formats from different providers
                timestamp = log.get(
                    "timestamp", log.get("time", log.get("created_at", ""))
                )
                message = log.get("message", log.get("log", log.get("text", "")))
                level = self._detect_log_level(message, log.get("level", "INFO"))

                # Filter by log type if specified
                if log_type != "all":
                    if log_type == "error" and level not in ("ERROR", "CRITICAL"):
                        continue
                    elif log_type == "warn" and level not in (
                        "WARNING",
                        "ERROR",
                        "CRITICAL",
                    ):
                        continue

                # Parse timestamp
                if isinstance(timestamp, str):
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        dt = timezone.now()
                else:
                    dt = timezone.now()

                entries.append(
                    LogEntry(
                        timestamp=dt,
                        level=level,
                        message=message,
                        source="hosting",
                        metadata=log.get("metadata", {}),
                    )
                )

            except Exception as e:
                logger.warning(f"Failed to parse log entry: {e}")
                continue

        return entries

    def _detect_log_level(self, message: str, default: str = "INFO") -> str:
        """Detect log level from message content."""
        message_upper = message.upper()

        if any(x in message_upper for x in ["ERROR", "EXCEPTION", "TRACEBACK"]):
            return "ERROR"
        elif any(x in message_upper for x in ["CRITICAL", "FATAL"]):
            return "CRITICAL"
        elif any(x in message_upper for x in ["WARN", "WARNING"]):
            return "WARNING"
        elif "DEBUG" in message_upper:
            return "DEBUG"

        return default.upper()

    def test_connection(self) -> tuple[bool, str]:
        """Test the hosting provider API connection."""
        if not self.is_available:
            return False, "Hosting logs API is not configured"

        try:
            # Test with a simple project info request
            url = f"{self.config.api_base_url.rstrip('/')}/projects/{self.config.project_id}"
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                return True, "Connection successful"
            elif response.status_code == 401:
                return False, "Invalid API token"
            elif response.status_code == 404:
                return False, "Project not found"
            else:
                return False, f"API returned status {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {str(e)}"


def get_hosting_logs_service() -> HostingLogsService:
    """Get a configured hosting logs service instance."""
    return HostingLogsService()
