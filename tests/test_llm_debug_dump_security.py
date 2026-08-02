"""
Regression tests for the LLM debug dump hardening (security review F7).

Covers the three properties required by the fix:

1. Dumps are written under ``settings.BASE_DIR / "logs" / "llm"`` with mode
   ``0o600`` (and the directory with ``0o700``), never to ``/tmp``.
2. Dumps are gated off in production unless ``LLM_DEBUG_DUMP_INSECURE=1`` is
   also set.
3. The outgoing ``messages`` payload (which contains user prompts) is never
   written to the dump file.
4. Stale dump files older than the retention window are pruned.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
import stat
from unittest import mock

import pytest

from checktick_app.surveys import llm_client
from checktick_app.surveys.llm_client import (
    ConversationalSurveyLLM,
    _write_llm_debug_dump,
)


@pytest.fixture
def dump_dir(settings, tmp_path):
    """Point BASE_DIR/logs/llm at a temp dir so tests don't touch the repo."""
    settings.BASE_DIR = tmp_path
    return tmp_path / "logs" / "llm"


def _set_env(monkeypatch, **kwargs):
    for k in ("LLM_DEBUG_DUMP", "LLM_DEBUG_DUMP_INSECURE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in kwargs.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_dump_disabled_when_env_unset(monkeypatch, dump_dir):
    _set_env(monkeypatch)  # no flags set
    _write_llm_debug_dump({"response": {"x": 1}})
    assert not dump_dir.exists()


def test_dump_written_to_private_dir_in_dev(monkeypatch, dump_dir, settings):
    settings.ENVIRONMENT = "development"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1")

    _write_llm_debug_dump({"response": {"choices": []}})

    files = list(dump_dir.glob("llm_response_*.json"))
    assert len(files) == 1
    # Directory and file must be owner-only.
    assert stat.S_IMODE(dump_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    # Must NOT be written under /tmp.
    assert str(files[0]).startswith(str(dump_dir))


def test_dump_omits_outgoing_messages(monkeypatch, dump_dir, settings):
    """The dump payload must never include the outgoing messages (user prompts)."""
    settings.ENVIRONMENT = "development"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1")

    _write_llm_debug_dump(
        {
            "timestamp": "20260802T120000Z",
            "response": {"choices": [{"message": {"content": "hi"}}]},
        }
    )

    files = list(dump_dir.glob("llm_response_*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())
    assert "messages" not in written
    assert "payload_preview" not in written
    assert written["response"]["choices"][0]["message"]["content"] == "hi"


def test_dump_blocked_in_production_without_insecure_flag(
    monkeypatch, dump_dir, settings
):
    settings.ENVIRONMENT = "production"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1")  # no INSECURE flag

    _write_llm_debug_dump({"response": {"x": 1}})
    assert not dump_dir.exists()


def test_dump_allowed_in_production_with_insecure_flag(monkeypatch, dump_dir, settings):
    settings.ENVIRONMENT = "production"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1", LLM_DEBUG_DUMP_INSECURE="1")

    _write_llm_debug_dump({"response": {"x": 1}})
    files = list(dump_dir.glob("llm_response_*.json"))
    assert len(files) == 1
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600


def test_stale_dumps_are_pruned(monkeypatch, dump_dir, settings):
    settings.ENVIRONMENT = "development"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1")

    dump_dir.mkdir(parents=True, exist_ok=True)
    dump_dir.chmod(0o700)

    # An old file (48h ago) — should be deleted.
    old = dump_dir / "llm_response_old.json"
    old.write_text("{}")
    old_mtime = (datetime.utcnow() - timedelta(hours=48)).timestamp()
    os.utime(old, (old_mtime, old_mtime))

    # A recent file — should survive.
    recent = dump_dir / "llm_response_recent.json"
    recent.write_text("{}")
    recent_mtime = (datetime.utcnow() - timedelta(hours=1)).timestamp()
    os.utime(recent, (recent_mtime, recent_mtime))

    _write_llm_debug_dump({"response": {"x": 1}})

    assert not old.exists()
    assert recent.exists()


def test_chat_method_uses_safe_dump(monkeypatch, settings, tmp_path):
    """End-to-end: ConversationalSurveyLLM.chat routes dumps through the helper."""
    settings.BASE_DIR = tmp_path
    settings.ENVIRONMENT = "development"
    settings.LLM_TEMPERATURE = 0.5
    settings.LLM_MAX_RETRIES = 1
    settings.LLM_MODEL = "test-model"
    _set_env(monkeypatch, LLM_DEBUG_DUMP="1")

    fake_response = mock.Mock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}]
    }
    fake_response.raise_for_status = mock.Mock()

    with mock.patch.object(llm_client.requests, "post", return_value=fake_response):
        client = ConversationalSurveyLLM.__new__(ConversationalSurveyLLM)
        client.endpoint = "http://mock"
        client.api_key = "k"
        client.auth_type = "bearer"
        client.timeout = 5
        client.system_prompt = "sys"
        result = client.chat([{"role": "user", "content": "hi"}])

    assert result == "hello world"
    files = list((tmp_path / "logs" / "llm").glob("llm_response_*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())
    assert "messages" not in written
    assert written["response"]["choices"][0]["message"]["content"] == "hello world"
