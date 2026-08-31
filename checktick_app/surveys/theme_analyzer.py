"""
Theme analysis service for free-text survey responses.

Per ``docs/reporting-and-exports.md`` (Summary Report → LLM Theme Analysis),
the LLM theme feature is:

- **Opt-in**: a "Summarise themes" button per text question, never automatic.
- **Unlock-gated**: only decrypted content is ever sent to the LLM.
- **Per-question**: bounded token volume, one question at a time.
- **Non-persistent**: session-scoped only — never written back into enc_answers.
- **Sanitised** through ``sanitize_markdown()`` before rendering.
- **Graceful degradation**: if Ollama is unavailable or the user's tier does
  not include LLM features, the caller falls back to plain collation.

This module is the only place that constructs an LLM prompt from response
content. It exposes a single function — :func:`summarise_themes` — which the
view layer calls after the unlock gate and tier check have already passed.

Audit logging is the caller's responsibility (the view records metadata only:
question id, response count, token count, model name, success/failure,
duration). This module never logs the free-text input or the LLM output
verbatim, per the medical-app logging rules in ``AGENTS.md``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings

from .llm_client import ConversationalSurveyLLM

logger = logging.getLogger(__name__)


# System prompt for theme analysis. Kept inline because it is short and
# specific to this feature; the survey-generator and translation prompts live
# in their respective docs and are loaded from there. The summary output is
# always sanitised through ``sanitize_markdown()`` before being returned to
# the view, so even if the model emits HTML or script it is stripped.
_THEME_SYSTEM_PROMPT = """You are a healthcare survey analyst. You will receive a list of free-text responses to a single survey question.

Your task:
1. Identify the recurring themes in the responses.
2. Summarise each theme in one or two short bullet points.
3. Do NOT quote respondents verbatim. Paraphrase only.
4. Do NOT include names, postcodes, clinician identifiers, or any other identifiable content. If a theme depends on identifiable content, describe it generically (e.g. "concerns about a specific clinician" rather than naming the clinician).
5. Return plain markdown — a short intro line, then a bulleted list of themes. No code fences, no HTML, no scripts.
6. If there are too few responses to identify themes, say so briefly.

Keep the summary under 200 words."""


def summarise_themes(
    question_text: str,
    responses: list[str],
    *,
    llm_client: ConversationalSurveyLLM | None = None,
    max_tokens: int = 800,
) -> dict[str, Any]:
    """Summarise the themes in a list of free-text responses.

    Args:
        question_text: The question text (for context; never logged).
        responses: List of decrypted free-text responses (already truncated
            upstream by the caller).
        llm_client: Optional injected client (used by tests to mock Ollama).
            If ``None``, a real :class:`ConversationalSurveyLLM` is constructed.
        max_tokens: Cap on the response length.

    Returns:
        A dict with keys: ``summary`` (sanitised markdown), ``token_count``
        (best-effort estimate of input tokens, for audit metadata only),
        ``model_name``, ``duration_ms``, ``success`` (bool), ``error`` (str).
        On any failure (LLM disabled, unreachable, empty input) ``success``
        is False and ``summary`` is empty — the caller renders a graceful
        degradation message instead.

    Security notes:
        - This function receives DECRYPTED free text. It must only be called
          after the view has verified the unlock gate and the user's tier.
        - The LLM input is constructed here and never logged. The returned
          summary is sanitised before being returned.
        - The ``token_count`` is a rough estimate (len/4) for audit metadata;
          it is not used for billing or rate limiting.
    """
    started = time.monotonic()

    # Filter empty/whitespace-only responses defensively — the caller should
    # already have done this, but the LLM cost is real and we don't want to
    # send an empty prompt.
    non_empty = [r for r in responses if r and r.strip()]
    if not non_empty:
        return {
            "summary": "",
            "token_count": 0,
            "model_name": "",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "success": False,
            "error": "No responses to summarise.",
        }

    # Rough token estimate for audit metadata (not for billing). 4 chars/token
    # is a coarse English approximation; the audit log records this number
    # only, never the input text.
    joined = "\n".join(non_empty)
    token_estimate = max(1, len(joined) // 4)

    if not getattr(settings, "LLM_ENABLED", False):
        return {
            "summary": "",
            "token_count": token_estimate,
            "model_name": "",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "success": False,
            "error": "LLM features are disabled on this instance.",
        }

    try:
        client = llm_client if llm_client is not None else ConversationalSurveyLLM()
    except Exception as exc:
        logger.warning("LLM client unavailable for theme analysis: %s", exc)
        return {
            "summary": "",
            "token_count": token_estimate,
            "model_name": "",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "success": False,
            "error": "LLM client could not be initialised.",
        }

    user_prompt = (
        f"Question: {question_text}\n\n"
        f"Responses ({len(non_empty)} total):\n{joined}\n\n"
        "Summarise the recurring themes."
    )
    conversation = [{"role": "user", "content": user_prompt}]

    try:
        raw = client.chat_with_custom_system_prompt(
            _THEME_SYSTEM_PROMPT,
            conversation,
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning("LLM theme request failed: %s", exc)
        return {
            "summary": "",
            "token_count": token_estimate,
            "model_name": getattr(settings, "LLM_MODEL", ""),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "success": False,
            "error": "LLM request failed.",
        }

    duration_ms = int((time.monotonic() - started) * 1000)

    if not raw or not raw.strip():
        return {
            "summary": "",
            "token_count": token_estimate,
            "model_name": getattr(settings, "LLM_MODEL", ""),
            "duration_ms": duration_ms,
            "success": False,
            "error": "LLM returned an empty response.",
        }

    # Sanitise through the existing pipeline before returning to the view.
    sanitised = ConversationalSurveyLLM.sanitize_markdown(raw)

    return {
        "summary": sanitised,
        "token_count": token_estimate,
        "model_name": getattr(settings, "LLM_MODEL", ""),
        "duration_ms": duration_ms,
        "success": True,
        "error": "",
    }
