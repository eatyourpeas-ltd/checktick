"""
Tests for the ALLOWED_HOSTS_EXTRA settings mechanism.

The web Deployment (k8s/web.yaml) sets an ALLOWED_HOSTS env entry that
intentionally overrides the ConfigMaps with the IN-CLUSTER hosts only
(pod IP + service names) so kubelet httpGet probes pass. Public domains are
therefore APPENDED by settings.py from ALLOWED_HOSTS_EXTRA, which the local
config overlay (checktick-config-local ConfigMap) owns. This keeps
re-applying the web manifest from ever 400-ing the public site.

Follows the import/reload pattern from test_settings_hardening.py.
"""

from __future__ import annotations

import importlib
import sys

MOD_NAME = "checktick_app.settings"


def _import_settings():
    if MOD_NAME in sys.modules:
        del sys.modules[MOD_NAME]
    return importlib.import_module(MOD_NAME)


def test_extra_appends_without_replacing_base(monkeypatch):
    """ALLOWED_HOSTS_EXTRA appends the public domains to the base list
    without replacing the in-cluster hosts the Deployment provides."""
    monkeypatch.setenv("ALLOWED_HOSTS", "10.0.0.5,checktick-web,localhost")
    monkeypatch.setenv("ALLOWED_HOSTS_EXTRA", "checktick.uk,www.checktick.uk")

    try:
        mod = _import_settings()
        # The in-cluster hosts survive — probes depend on them.
        # (Exact list equality below also proves the public domains are
        # present — substring-style `in` checks on domain strings trip
        # CodeQL's py/incomplete-url-substring-sanitization.)
        assert "10.0.0.5" in mod.ALLOWED_HOSTS
        assert "checktick-web" in mod.ALLOWED_HOSTS
        assert "localhost" in mod.ALLOWED_HOSTS
        # Order: base first, extras appended.
        assert mod.ALLOWED_HOSTS[:3] == ["10.0.0.5", "checktick-web", "localhost"]
        assert mod.ALLOWED_HOSTS[3:] == ["checktick.uk", "www.checktick.uk"]
    finally:
        if MOD_NAME in sys.modules:
            del sys.modules[MOD_NAME]


def test_extra_unset_leaves_allowed_hosts_alone(monkeypatch):
    """No ALLOWED_HOSTS_EXTRA → ALLOWED_HOSTS is exactly the base list."""
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.delenv("ALLOWED_HOSTS_EXTRA", raising=False)

    try:
        mod = _import_settings()
        assert mod.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
    finally:
        if MOD_NAME in sys.modules:
            del sys.modules[MOD_NAME]


def test_extra_strips_whitespace_and_empty_segments(monkeypatch):
    """Messy comma lists (spaces, empty segments) must not inject an empty
    string — Django treats '' in ALLOWED_HOSTS as match-anything."""
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost")
    monkeypatch.setenv("ALLOWED_HOSTS_EXTRA", " checktick.uk ,, , ,www.checktick.uk,")

    try:
        mod = _import_settings()
        assert mod.ALLOWED_HOSTS == ["localhost", "checktick.uk", "www.checktick.uk"]
        assert "" not in mod.ALLOWED_HOSTS
    finally:
        if MOD_NAME in sys.modules:
            del sys.modules[MOD_NAME]
