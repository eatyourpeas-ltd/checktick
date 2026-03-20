"""
Cross-organisation security tests: verify API keys are properly scoped and prevent
cross-organisation data leakage.
"""

from django.contrib.auth import get_user_model
import pytest

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import Organization, OrganizationMembership, Survey

User = get_user_model()


def make_api_key(user) -> str:
    """Create a UserAPIKey for a user and return the raw key."""
    _, raw_key = UserAPIKey.generate(user=user, name="test key")
    return raw_key


def auth_header(raw_key: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}
    """Build authorization header with JWT token."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
class TestCrossOrganizationSecurity:
    """Verify API keys are properly scoped to prevent cross-organization access."""

    def test_user_cannot_list_other_org_surveys(self, client):
        """Key holder should not see surveys from organizations they don't belong to."""
        # Org A
        owner_a = User.objects.create_user(username="owner_a")
        org_a = Organization.objects.create(name="Org A", owner=owner_a)
        Survey.objects.create(
            owner=owner_a, organization=org_a, name="Survey A", slug="survey-a"
        )

        # Org B
        owner_b = User.objects.create_user(username="owner_b")
        org_b = Organization.objects.create(name="Org B", owner=owner_b)
        Survey.objects.create(
            owner=owner_b, organization=org_b, name="Survey B", slug="survey-b"
        )

        # Owner A uses their API key to list surveys
        key_a = make_api_key(owner_a)
        resp = client.get("/api/surveys/", **auth_header(key_a))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "survey-a" in slugs
        assert "survey-b" not in slugs  # Should NOT see Org B's survey

        # Owner B uses their API key to list surveys
        key_b = make_api_key(owner_b)
        resp = client.get("/api/surveys/", **auth_header(key_b))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "survey-b" in slugs
        assert "survey-a" not in slugs  # Should NOT see Org A's survey

    def test_user_cannot_retrieve_other_org_survey(self, client):
        """User should get 403 when trying to retrieve survey from another org."""
        # Org A
        owner_a = User.objects.create_user(username="owner_a2")
        org_a = Organization.objects.create(name="Org A2", owner=owner_a)
        survey_a = Survey.objects.create(
            owner=owner_a, organization=org_a, name="Survey A2", slug="survey-a2"
        )

        # Org B
        owner_b = User.objects.create_user(username="owner_b2")
        Organization.objects.create(name="Org B2", owner=owner_b)

        key_b = make_api_key(owner_b)
        resp = client.get(f"/api/surveys/{survey_a.id}/", **auth_header(key_b))
        assert resp.status_code == 403  # Forbidden, not 404

    def test_user_cannot_update_other_org_survey(self, client):
        """PATCH is not available (read-only API) — update must be blocked."""
        import json

        # Org A
        owner_a = User.objects.create_user(username="owner_a3")
        org_a = Organization.objects.create(name="Org A3", owner=owner_a)
        survey_a = Survey.objects.create(
            owner=owner_a, organization=org_a, name="Survey A3", slug="survey-a3"
        )

        # Org B
        owner_b = User.objects.create_user(username="owner_b3")
        Organization.objects.create(name="Org B3", owner=owner_b)

        key_b = make_api_key(owner_b)
        resp = client.patch(
            f"/api/surveys/{survey_a.id}/",
            data=json.dumps({"description": "Malicious update"}),
            content_type="application/json",
            **auth_header(key_b),
        )
        # 403 if auth fails before routing; 405 because endpoint is read-only
        assert resp.status_code in (403, 405)

        # Verify survey was not modified
        survey_a.refresh_from_db()
        assert survey_a.description != "Malicious update"

    def test_org_admin_cannot_access_other_org_surveys(self, client):
        """Org admin in one org should not access surveys in a different org."""
        # Org A with admin
        owner_a = User.objects.create_user(username="owner_a5")
        admin_a = User.objects.create_user(username="admin_a5")
        org_a = Organization.objects.create(name="Org A5", owner=owner_a)
        OrganizationMembership.objects.create(
            organization=org_a, user=admin_a, role=OrganizationMembership.Role.ADMIN
        )
        survey_a = Survey.objects.create(
            owner=owner_a, organization=org_a, name="Survey A5", slug="survey-a5"
        )

        # Org B with admin
        owner_b = User.objects.create_user(username="owner_b5")
        admin_b = User.objects.create_user(username="admin_b5")
        org_b = Organization.objects.create(name="Org B5", owner=owner_b)
        OrganizationMembership.objects.create(
            organization=org_b, user=admin_b, role=OrganizationMembership.Role.ADMIN
        )

        key_admin_b = make_api_key(admin_b)
        resp = client.get(f"/api/surveys/{survey_a.id}/", **auth_header(key_admin_b))
        assert resp.status_code == 403

        resp = client.get("/api/surveys/", **auth_header(key_admin_b))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "survey-a5" not in slugs

    def test_api_key_user_identity_properly_scoped(self, client):
        """API key is scoped to exactly the issuing user."""
        user1 = User.objects.create_user(username="user1")
        user2 = User.objects.create_user(username="user2")

        # Create survey for user1
        survey1 = Survey.objects.create(
            owner=user1, name="User 1 Survey", slug="user1-survey"
        )

        # User2 uses their own API key
        key2 = make_api_key(user2)

        # User2 tries to access user1's survey (no org involved)
        resp = client.get(f"/api/surveys/{survey1.id}/", **auth_header(key2))
        assert resp.status_code == 403

        # User2 lists surveys - should not see user1's
        resp = client.get("/api/surveys/", **auth_header(key2))
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert "user1-survey" not in slugs
