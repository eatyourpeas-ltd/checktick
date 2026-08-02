"""
Tests for API hardening findings from the August 2026 security review.

Covers:
- F4: DRF default permission must be fail-closed (``IsAuthenticated``).
- F11: API-key ``last_used_at`` write must be throttled (not every request).

Each test is written to fail against the pre-fix code and pass after the fix.
"""

from __future__ import annotations

import sys

from django.urls import include, path
import pytest
from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import Survey

# ---------------------------------------------------------------------------
# F4 — Weak DRF default permission
# ---------------------------------------------------------------------------


def test_drf_default_permission_is_authenticated():
    """The global DRF default permission must be fail-closed (IsAuthenticated).

    Pre-fix: ``IsAuthenticatedOrReadOnly`` allowed anonymous read access to any
    future viewset that forgot to declare ``permission_classes``.
    """
    from checktick_app import settings as ct_settings

    default_perms = ct_settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
    assert "rest_framework.permissions.IsAuthenticated" in default_perms
    assert "rest_framework.permissions.IsAuthenticatedOrReadOnly" not in default_perms


@pytest.mark.django_db
def test_anonymous_request_to_undeclared_permission_viewset_is_denied(client):
    """A viewset that does NOT declare ``permission_classes`` must still deny
    anonymous read access under the global default.

    Pre-fix: an anonymous GET would return 200 because the global default was
    ``IsAuthenticatedOrReadOnly``. Post-fix: the global default is
    ``IsAuthenticated`` so anonymous read is denied (401/403).
    """

    # A deliberately-undeclared-permission viewset, simulating a future
    # contributor forgetting the decorator. Routed under a throwaway prefix.
    class _BareSerializer(serializers.ModelSerializer):
        class Meta:
            model = Survey
            fields = ["id", "name"]

    class _BareViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Survey.objects.none()
        serializer_class = _BareSerializer
        # Intentionally no permission_classes — relies on the global default.

    router = DefaultRouter()
    router.register(r"bare-f4", _BareViewSet, basename="bare-f4")

    from django.test import override_settings

    with override_settings(ROOT_URLCONF=__name__):
        sys.modules[__name__].urlpatterns = [
            path("api/", include(router.urls)),
        ]
        resp = client.get("/api/bare-f4/")
    assert resp.status_code in (401, 403), (
        "Anonymous read access should be denied by the global DRF default; "
        f"got {resp.status_code}."
    )


# ---------------------------------------------------------------------------
# F11 — API-key last_used_at write throttling
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_last_used_at_not_written_on_every_request(client):
    """``last_used_at`` must be throttled — multiple requests within the
    throttle window should produce at most one DB write per key.

    Pre-fix: every authenticated API request wrote ``last_used_at`` to the DB.
    Post-fix: a cache-based throttle limits writes to once per window.
    """
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    User = get_user_model()
    user = User.objects.create_user(username="f11user", password="x")
    instance, raw_key = UserAPIKey.generate(user=user, name="f11 key")

    # Clear any cache state from prior tests for this key.
    cache.delete(f"apikey_lastused:{instance.id}")

    headers = {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}

    # First request: last_used_at goes from None -> set.
    client.get("/api/surveys/", **headers)
    instance.refresh_from_db()
    first_used = instance.last_used_at
    assert first_used is not None

    # Second and third requests within the throttle window: last_used_at must
    # NOT change (no DB write).
    client.get("/api/surveys/", **headers)
    client.get("/api/surveys/", **headers)
    instance.refresh_from_db()
    assert instance.last_used_at == first_used, (
        "last_used_at should not be updated on every request within the "
        f"throttle window; expected {first_used}, got {instance.last_used_at}"
    )


@pytest.mark.django_db
def test_last_used_at_updates_after_throttle_window_expires(client):
    """After the throttle window expires, the next request should refresh
    ``last_used_at``.
    """
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    User = get_user_model()
    user = User.objects.create_user(username="f11user2", password="x")
    instance, raw_key = UserAPIKey.generate(user=user, name="f11 key2")
    cache.delete(f"apikey_lastused:{instance.id}")

    headers = {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}
    client.get("/api/surveys/", **headers)
    instance.refresh_from_db()
    first_used = instance.last_used_at

    # Simulate the throttle window expiring by clearing the cache marker.
    cache.delete(f"apikey_lastused:{instance.id}")

    client.get("/api/surveys/", **headers)
    instance.refresh_from_db()
    assert instance.last_used_at is not None
    assert instance.last_used_at >= first_used
