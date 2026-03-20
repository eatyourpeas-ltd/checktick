"""
TDD tests for UserAPIKey authentication.

Covers:
- Valid key → 200, correct user resolved
- Invalid / unknown key → 401
- Revoked key → 401
- Expired key → 401
- No Authorization header → 401
- Key last_used_at is updated on each authenticated request
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import Survey

TEST_PASSWORD = "x"


User = get_user_model()


def api_key_header(raw_key: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}


@pytest.mark.django_db
class TestAPIKeyAuthentication:
    def setup_user_with_key(self, username="keyuser"):
        user = User.objects.create_user(username=username, password=TEST_PASSWORD)
        instance, raw_key = UserAPIKey.generate(user=user, name="test key")
        return user, instance, raw_key

    def test_valid_key_returns_200_on_surveys_list(self, client):
        user, key_obj, raw_key = self.setup_user_with_key()
        resp = client.get("/api/surveys/", **api_key_header(raw_key))
        assert resp.status_code == 200

    def test_invalid_key_returns_401(self, client):
        resp = client.get("/api/surveys/", **api_key_header("ct_live_invalidkey"))
        assert resp.status_code == 401

    def test_unknown_key_returns_401(self, client):
        # Valid prefix format but not in DB
        raw_key = "ct_live_" + "x" * 54
        resp = client.get("/api/surveys/", **api_key_header(raw_key))
        assert resp.status_code == 401

    def test_revoked_key_returns_401(self, client):
        user, key_obj, raw_key = self.setup_user_with_key("revokeduser")
        key_obj.revoked = True
        key_obj.revoked_at = timezone.now()
        key_obj.save()
        resp = client.get("/api/surveys/", **api_key_header(raw_key))
        assert resp.status_code == 401

    def test_expired_key_returns_401(self, client):
        user, key_obj, raw_key = self.setup_user_with_key("expireduser")
        key_obj.expires_at = timezone.now() - timedelta(hours=1)
        key_obj.save()
        resp = client.get("/api/surveys/", **api_key_header(raw_key))
        assert resp.status_code == 401

    def test_no_auth_header_returns_401(self, client):
        resp = client.get("/api/surveys/")
        assert resp.status_code in (401, 403)

    def test_last_used_at_updated_on_request(self, client):
        user, key_obj, raw_key = self.setup_user_with_key("lastuseuser")
        assert key_obj.last_used_at is None
        client.get("/api/surveys/", **api_key_header(raw_key))
        key_obj.refresh_from_db()
        assert key_obj.last_used_at is not None

    def test_valid_key_resolves_correct_user(self, client):
        user, _, raw_key = self.setup_user_with_key("scopeuser")
        _ = Survey.objects.create(owner=user, name="My Survey", slug="my-survey")
        resp = client.get("/api/surveys/", **api_key_header(raw_key))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "my-survey" in slugs

    def test_key_only_sees_own_surveys(self, client):
        """Cross-user isolation: key holder cannot see another user's surveys."""
        user_a, _, raw_key_a = self.setup_user_with_key("user_a_key")
        user_b = User.objects.create_user(username="user_b_key", password=TEST_PASSWORD)
        Survey.objects.create(owner=user_a, name="A Survey", slug="a-survey")
        Survey.objects.create(owner=user_b, name="B Survey", slug="b-survey")

        resp = client.get("/api/surveys/", **api_key_header(raw_key_a))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "a-survey" in slugs
        assert "b-survey" not in slugs
