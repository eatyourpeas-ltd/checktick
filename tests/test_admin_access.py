from django.contrib.auth.models import User
from django.urls import reverse
import pytest


@pytest.mark.django_db
class TestAdminAccess:
    def test_anonymous_user_gets_404(self, client):
        # The Django admin login form is disabled; unauthenticated visitors must
        # receive a 404 so the admin's existence is not advertised.
        resp = client.get(reverse("admin:index"))
        assert resp.status_code == 404

    def test_regular_user_gets_404(self, client):
        # A regular authenticated user (non-superuser) must also receive a 404.
        User.objects.create_user(
            username="u1", email="u1@example.com", password="StrongPass!234"
        )
        client.login(username="u1", password="StrongPass!234")
        resp = client.get(reverse("admin:index"))
        assert resp.status_code == 404

    def test_superuser_can_access_admin(self, client):
        User.objects.create_superuser(
            username="admin", email="admin@example.com", password="StrongPass!234"
        )
        client.login(username="admin", password="StrongPass!234")
        resp = client.get(reverse("admin:index"))
        assert resp.status_code == 200
        assert b"/admin/" in resp.content
