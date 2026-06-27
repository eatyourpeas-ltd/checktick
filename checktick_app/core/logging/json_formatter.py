import json
import logging

from django.utils import timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": timezone.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "remote_addr": getattr(record, "remote_addr", None),
            "project": getattr(record, "project", None),
            "service": getattr(record, "service", None),
            "environment": getattr(record, "environment", None),
            "module": record.module,
            "funcName": record.funcName,
            "file": record.filename,
            "line": record.lineno,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, sort_keys=True, ensure_ascii=False)
