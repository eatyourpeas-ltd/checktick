import json

from django.contrib.auth import get_user_model
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)

User = get_user_model()
TEST_PASSWORD = "test-pass"


@pytest.mark.django_db
class TestUserAPI:
    def auth(self, client, username, password):
        r = client.post(
            "/api/token",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
        )
        assert r.status_code == 200
        return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

    def test_org_admin_can_manage_org_memberships(self, client):
        admin = User.objects.create_user(username="adminx", password=TEST_PASSWORD)
        u2 = User.objects.create_user(username="u2", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI", owner=admin)
        OrganizationMembership.objects.create(
            organization=org, user=admin, role=OrganizationMembership.Role.ADMIN
        )
        hdrs = self.auth(client, "adminx", TEST_PASSWORD)

        # create membership
        r = client.post(
            "/api/org-memberships/",
            data=json.dumps({"organization": org.id, "user": u2.id, "role": "creator"}),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (201, 200)

        # list shows it
        r = client.get("/api/org-memberships/", **hdrs)
        assert any(m["user"] == u2.id for m in r.json())

    def test_non_admin_cannot_manage_org_memberships(self, client):
        owner = User.objects.create_user(username="ownery", password=TEST_PASSWORD)
        User.objects.create_user(username="othery", password=TEST_PASSWORD)  # other
        org = Organization.objects.create(name="OrgAPI2", owner=owner)
        hdrs = self.auth(client, "othery", TEST_PASSWORD)
        r = client.post(
            "/api/org-memberships/",
            data=json.dumps(
                {"organization": org.id, "user": owner.id, "role": "admin"}
            ),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (403, 401)

    def test_survey_creator_can_manage_survey_memberships(self, client):
        creator = User.objects.create_user(username="creatorx", password=TEST_PASSWORD)
        # Set creator to ORGANIZATION tier to enable collaboration
        from checktick_app.core.models import UserProfile

        profile = UserProfile.objects.get(user=creator)
        profile.account_tier = UserProfile.AccountTier.ORGANIZATION
        profile.save()

        viewer = User.objects.create_user(username="viewerx", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI3", owner=creator)
        OrganizationMembership.objects.create(
            organization=org, user=creator, role=OrganizationMembership.Role.CREATOR
        )
        survey = Survey.objects.create(
            owner=creator, organization=org, name="SS", slug="ss"
        )
        hdrs = self.auth(client, "creatorx", TEST_PASSWORD)

        r = client.post(
            "/api/survey-memberships/",
            data=json.dumps({"survey": survey.id, "user": viewer.id, "role": "viewer"}),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (201, 200)
        assert SurveyMembership.objects.filter(survey=survey, user=viewer).exists()

    def test_individual_user_cannot_manage_survey_memberships(self, client):
        """Individual users (without organization) cannot share surveys via API."""
        creator = User.objects.create_user(username="indiv_api", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewer_api", password=TEST_PASSWORD)
        # Create survey without organization (individual user)
        survey = Survey.objects.create(owner=creator, name="IndivSurvey", slug="indiv")
        hdrs = self.auth(client, "indiv_api", TEST_PASSWORD)

        r = client.post(
            "/api/survey-memberships/",
            data=json.dumps({"survey": survey.id, "user": viewer.id, "role": "viewer"}),
            content_type="application/json",
            **hdrs,
        )
        # Should be forbidden - individual users cannot share
        assert r.status_code == 403
        assert not SurveyMembership.objects.filter(survey=survey, user=viewer).exists()

    def test_viewer_cannot_manage_survey_memberships(self, client):
        owner = User.objects.create_user(username="ownerz", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="viewerzz", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI4", owner=owner)
        survey = Survey.objects.create(
            owner=owner, organization=org, name="SZ", slug="sz"
        )
        SurveyMembership.objects.create(
            survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
        )
        hdrs = self.auth(client, "viewerzz", TEST_PASSWORD)
        r = client.post(
            "/api/survey-memberships/",
            data=json.dumps({"survey": survey.id, "user": owner.id, "role": "viewer"}),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (403, 401)

    def test_org_admin_can_create_user_in_org(self, client):
        admin = User.objects.create_user(username="adminc", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI5", owner=admin)
        OrganizationMembership.objects.create(
            organization=org, user=admin, role=OrganizationMembership.Role.ADMIN
        )
        hdrs = self.auth(client, "adminc", TEST_PASSWORD)
        r = client.post(
            f"/api/scoped-users/org/{org.id}/create/",
            data=json.dumps(
                {"username": "neworguser", "password": "example-password-for-tests"}
            ),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (200, 201)
        assert User.objects.filter(username="neworguser").exists()

    def test_creator_can_create_user_in_survey(self, client):
        creator = User.objects.create_user(username="creatorc", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI6", owner=creator)
        OrganizationMembership.objects.create(
            organization=org, user=creator, role=OrganizationMembership.Role.CREATOR
        )
        survey = Survey.objects.create(
            owner=creator, organization=org, name="SC", slug="sc"
        )
        hdrs = self.auth(client, "creatorc", TEST_PASSWORD)
        r = client.post(
            f"/api/scoped-users/survey/{survey.id}/create/",
            data=json.dumps(
                {"username": "newsurveyuser", "password": "example-password-for-tests"}
            ),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (200, 201)
        assert User.objects.filter(username="newsurveyuser").exists()

    def test_individual_user_cannot_create_user_in_survey(self, client):
        """Individual users cannot create users in their surveys (no sharing)."""
        creator = User.objects.create_user(
            username="indiv_create", password=TEST_PASSWORD
        )
        # Create survey without organization
        survey = Survey.objects.create(owner=creator, name="IndivSC", slug="indivsc")
        hdrs = self.auth(client, "indiv_create", TEST_PASSWORD)
        r = client.post(
            f"/api/scoped-users/survey/{survey.id}/create/",
            data=json.dumps(
                {"username": "baduser", "password": "example-password-for-tests"}
            ),
            content_type="application/json",
            **hdrs,
        )
        # Should be forbidden
        assert r.status_code == 403

    def test_viewer_cannot_create_user_in_survey(self, client):
        owner = User.objects.create_user(username="owneru", password=TEST_PASSWORD)
        viewer = User.objects.create_user(username="vieweru", password=TEST_PASSWORD)
        org = Organization.objects.create(name="OrgAPI7", owner=owner)
        survey = Survey.objects.create(
            owner=owner, organization=org, name="SV", slug="sv"
        )
        SurveyMembership.objects.create(
            survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
        )
        hdrs = self.auth(client, "vieweru", TEST_PASSWORD)
        r = client.post(
            f"/api/scoped-users/survey/{survey.id}/create/",
            data=json.dumps(
                {"username": "baduser", "password": "example-password-for-tests"}
            ),
            content_type="application/json",
            **hdrs,
        )
        assert r.status_code in (403, 401)
