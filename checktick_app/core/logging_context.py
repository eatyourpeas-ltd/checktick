from __future__ import annotations

import contextvars
import logging
from typing import Optional

# Thread-safe context variables for request identity
# Using contextvars for async compatibility (though Django is primarily sync)
ctx_user_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "user_id", default=None
)
ctx_remote_addr: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "remote_addr", default=None
)
ctx_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


class LoggingContextFilter(logging.Filter):
    """
    Django logging filter that injects request context into every log record.
    This satisfies NCSC traceability requirements for identity and source.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = ctx_user_id.get()
        record.remote_addr = ctx_remote_addr.get()
        record.request_id = ctx_request_id.get()
        return True
