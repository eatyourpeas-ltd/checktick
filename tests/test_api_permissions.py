from django.contrib.auth import get_user_model
import pytest

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import Organization, OrganizationMembership, Survey

User = get_user_model()


def make_key(user) -> str:
    _, raw_key = UserAPIKey.generate(user=user, name="test")
    return raw_key


@pytest.mark.django_db
class TestAPIPermissions:
    def get_auth_header(self, user) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {make_key(user)}"}

    def setup_users(self):
        owner = User.objects.create_user(username="owner")
        admin = User.objects.create_user(username="admin")
        creator = User.objects.create_user(username="creator")
        viewer = User.objects.create_user(username="viewer")
        anon = None
        return owner, admin, creator, viewer, anon

    def setup_data(self):
        owner, admin, creator, viewer, _ = self.setup_users()
        org = Organization.objects.create(name="Org1", owner=owner)
        OrganizationMembership.objects.create(
            organization=org, user=admin, role=OrganizationMembership.Role.ADMIN
        )
        OrganizationMembership.objects.create(
            organization=org, user=creator, role=OrganizationMembership.Role.CREATOR
        )
        OrganizationMembership.objects.create(
            organization=org, user=viewer, role=OrganizationMembership.Role.VIEWER
        )
        s1 = Survey.objects.create(owner=owner, organization=org, name="S1", slug="s1")
        s2 = Survey.objects.create(
            owner=creator, organization=org, name="S2", slug="s2"
        )
        s3 = Survey.objects.create(owner=viewer, organization=org, name="S3", slug="s3")
        return owner, admin, creator, viewer, org, [s1, s2, s3]

    def test_list_visibility(self, client):
        owner, admin, creator, viewer, org, surveys = self.setup_data()
        url = "/api/surveys/"

        # owner sees own surveys only
        hdrs = self.get_auth_header(owner)
        resp = client.get(url, **hdrs)
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert slugs == {"s1"}

        # admin sees all org surveys (s1,s2,s3)
        hdrs = self.get_auth_header(admin)
        resp = client.get(url, **hdrs)
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert slugs == {"s1", "s2", "s3"}

        # creator sees only their own (s2)
        hdrs = self.get_auth_header(creator)
        resp = client.get(url, **hdrs)
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert slugs == {"s2"}

        # viewer sees only their own (s3)
        hdrs = self.get_auth_header(viewer)
        resp = client.get(url, **hdrs)
        assert resp.status_code == 200
        slugs = {s["slug"] for s in resp.json()}
        assert slugs == {"s3"}

        # anonymous is not allowed
        resp = client.get(url)
        assert resp.status_code in (401, 403)

    def test_retrieve_permissions(self, client):
        owner, admin, creator, viewer, org, surveys = self.setup_data()
        s1, s2, s3 = surveys
        url_s2 = f"/api/surveys/{s2.id}/"

        # anonymous cannot retrieve
        resp = client.get(url_s2)
        assert resp.status_code in (401, 403)

        # Organization owner CAN fetch s2 (org owners can view all org surveys)
        hdrs = self.get_auth_header(owner)
        resp = client.get(url_s2, **hdrs)
        assert resp.status_code == 200

        # admin can fetch any org survey
        hdrs = self.get_auth_header(admin)
        resp = client.get(url_s2, **hdrs)
        assert resp.status_code == 200

        # creator can fetch their own
        hdrs = self.get_auth_header(creator)
        resp = client.get(url_s2, **hdrs)
        assert resp.status_code == 200

        # viewer cannot fetch creator's survey (not their own)
        hdrs = self.get_auth_header(viewer)
        resp = client.get(url_s2, **hdrs)
        assert resp.status_code == 403
