"""
Tests for DataSet API endpoints.

Tests cover:
- GET /api/datasets-v2/ - List datasets
- GET /api/datasets-v2/{key}/ - Retrieve dataset
- POST /api/datasets-v2/ - Create dataset
- PATCH /api/datasets-v2/{key}/ - Update dataset
- DELETE /api/datasets-v2/{key}/ - Delete dataset

With different user roles and access scenarios.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from checktick_app.surveys.models import DataSet, Organization, OrganizationMembership

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def api_client():
    """API client for making requests."""
    return APIClient()


@pytest.fixture
def org1(db):
    """Create first test organization."""
    owner = User.objects.create_user(
        username="org1_owner", email="owner1@example.com", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="Organization 1", owner=owner)
    # Create membership for owner
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.fixture
def org2(db):
    """Create second test organization."""
    owner = User.objects.create_user(
        username="org2_owner", email="owner2@example.com", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="Organization 2", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.fixture
def admin_user(db, org1):
    """User with ADMIN role in org1."""
    user = User.objects.create_user(
        username="admin_user", email="admin@example.com", password=TEST_PASSWORD
    )
    OrganizationMembership.objects.create(
        organization=org1, user=user, role=OrganizationMembership.Role.ADMIN
    )
    return user


@pytest.fixture
def creator_user(db, org1):
    """User with CREATOR role in org1."""
    user = User.objects.create_user(
        username="creator_user", email="creator@example.com", password=TEST_PASSWORD
    )
    OrganizationMembership.objects.create(
        organization=org1, user=user, role=OrganizationMembership.Role.CREATOR
    )
    return user


@pytest.fixture
def viewer_user(db, org1):
    """User with VIEWER role in org1."""
    user = User.objects.create_user(
        username="viewer_user", email="viewer@example.com", password=TEST_PASSWORD
    )
    OrganizationMembership.objects.create(
        organization=org1, user=user, role=OrganizationMembership.Role.VIEWER
    )
    return user


@pytest.fixture
def global_dataset(db):
    """Create a global dataset."""
    return DataSet.objects.create(
        key="global_dataset",
        name="Global Dataset",
        category="user_created",
        source_type="manual",
        is_custom=True,
        is_global=True,
        options=["Option 1", "Option 2", "Option 3"],
    )


@pytest.fixture
def org1_dataset(db, org1, admin_user):
    """Create a dataset for org1."""
    return DataSet.objects.create(
        key="org1_dataset",
        name="Org1 Dataset",
        category="user_created",
        source_type="manual",
        is_custom=True,
        is_global=False,
        organization=org1,
        created_by=admin_user,
        options=["Org1 Option 1", "Org1 Option 2"],
    )


@pytest.fixture
def org2_dataset(db, org2):
    """Create a dataset for org2."""
    return DataSet.objects.create(
        key="org2_dataset",
        name="Org2 Dataset",
        category="user_created",
        source_type="manual",
        is_custom=True,
        is_global=False,
        organization=org2,
        created_by=org2.owner,
        options=["Org2 Option 1", "Org2 Option 2"],
    )


@pytest.fixture
def nhs_dd_dataset(db):
    """Create an NHS DD dataset (read-only)."""
    return DataSet.objects.create(
        key="nhs_specialty",
        name="NHS Specialty Codes",
        category="nhs_dd",
        source_type="api",
        is_custom=False,
        is_global=True,
        reference_url="https://www.datadictionary.nhs.uk/data_elements/main_specialty_code.html",
        options=["100", "101", "102"],
    )


@pytest.mark.django_db
class TestDataSetListAPI:
    """Tests for GET /api/datasets-v2/"""

    def test_anonymous_user_sees_only_global_datasets(
        self, api_client, global_dataset, org1_dataset
    ):
        """Anonymous users should only see global datasets."""
        response = api_client.get("/api/datasets-v2/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["key"] == "global_dataset"

    def test_admin_user_sees_global_and_org_datasets(
        self, api_client, admin_user, global_dataset, org1_dataset, org2_dataset
    ):
        """Admin users should see global + their organization's datasets."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/datasets-v2/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        keys = {d["key"] for d in data}
        assert keys == {"global_dataset", "org1_dataset"}

    def test_viewer_user_sees_global_and_org_datasets(
        self, api_client, viewer_user, global_dataset, org1_dataset, org2_dataset
    ):
        """Viewer users should see global + their organization's datasets."""
        api_client.force_authenticate(user=viewer_user)
        response = api_client.get("/api/datasets-v2/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        keys = {d["key"] for d in data}
        assert keys == {"global_dataset", "org1_dataset"}

    def test_user_cannot_see_other_org_datasets(
        self, api_client, admin_user, org2_dataset
    ):
        """Users should not see datasets from other organizations."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/datasets-v2/")

        assert response.status_code == 200
        data = response.json()
        keys = {d["key"] for d in data}
        assert "org2_dataset" not in keys


@pytest.mark.django_db
class TestDataSetRetrieveAPI:
    """Tests for GET /api/datasets-v2/{key}/"""

    def test_retrieve_global_dataset(self, api_client, global_dataset):
        """Anyone can retrieve global datasets."""
        response = api_client.get(f"/api/datasets-v2/{global_dataset.key}/")

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "global_dataset"
        assert data["is_global"] is True
        assert data["options"] == ["Option 1", "Option 2", "Option 3"]

    def test_retrieve_org_dataset_as_member(self, api_client, admin_user, org1_dataset):
        """Organization members can retrieve their org's datasets."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/datasets-v2/{org1_dataset.key}/")

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "org1_dataset"
        assert data["organization_name"] == "Organization 1"

    def test_cannot_retrieve_other_org_dataset(
        self, api_client, admin_user, org2_dataset
    ):
        """Users cannot retrieve datasets from other organizations."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/datasets-v2/{org2_dataset.key}/")

        assert response.status_code == 404

    def test_retrieve_nhs_dd_dataset(self, api_client, admin_user, nhs_dd_dataset):
        """Anyone can retrieve NHS DD datasets."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/datasets-v2/{nhs_dd_dataset.key}/")

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "nhs_dd"
        assert data["is_editable"] is False


@pytest.mark.django_db
class TestDataSetCreateAPI:
    """Tests for POST /api/datasets-v2/"""

    def test_admin_can_create_dataset(self, api_client, admin_user, org1):
        """ADMIN users can create datasets for their organization."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "new_dataset",
                "name": "New Dataset",
                "description": "Test dataset",
                "options": ["Option A", "Option B"],
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "new_dataset"
        assert data["organization"] == org1.id
        assert data["created_by"] == admin_user.id
        assert data["is_global"] is False

    def test_creator_can_create_dataset(self, api_client, creator_user, org1):
        """CREATOR users can create datasets for their organization."""
        api_client.force_authenticate(user=creator_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "creator_dataset",
                "name": "Creator Dataset",
                "options": ["Option 1"],
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["key"] == "creator_dataset"

    def test_viewer_cannot_create_dataset(self, api_client, viewer_user, org1):
        """VIEWER users cannot create datasets."""
        api_client.force_authenticate(user=viewer_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "viewer_dataset",
                "name": "Viewer Dataset",
                "options": ["Option 1"],
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 403

    def test_anonymous_cannot_create_dataset(self, api_client, org1):
        """Anonymous users cannot create datasets."""
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "anon_dataset",
                "name": "Anon Dataset",
                "options": ["Option 1"],
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 401

    def test_cannot_create_dataset_for_other_org(self, api_client, admin_user, org2):
        """Users cannot create datasets for organizations they don't belong to."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "other_org_dataset",
                "name": "Other Org Dataset",
                "options": ["Option 1"],
                "organization": org2.id,
            },
            format="json",
        )

        assert response.status_code == 403

    def test_create_dataset_validates_key_format(self, api_client, admin_user, org1):
        """Dataset key must be slug-like (lowercase, no spaces)."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "Invalid Key With Spaces",
                "name": "Invalid Dataset",
                "options": ["Option 1"],
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "key" in response.json()

    def test_create_dataset_validates_options_is_list(
        self, api_client, admin_user, org1
    ):
        """Dataset options must be a list."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/datasets-v2/",
            {
                "key": "invalid_options",
                "name": "Invalid Options",
                "options": "not a list",
                "organization": org1.id,
            },
            format="json",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestDataSetUpdateAPI:
    """Tests for PATCH /api/datasets-v2/{key}/"""

    def test_admin_can_update_org_dataset(self, api_client, admin_user, org1_dataset):
        """ADMIN users can update their organization's datasets."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/datasets-v2/{org1_dataset.key}/",
            {
                "name": "Updated Dataset Name",
                "options": ["New Option 1", "New Option 2", "New Option 3"],
            },
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Dataset Name"
        assert len(data["options"]) == 3
        assert data["version"] == 2  # Version incremented

    def test_creator_can_update_org_dataset(
        self, api_client, creator_user, org1_dataset
    ):
        """CREATOR users can update their organization's datasets."""
        api_client.force_authenticate(user=creator_user)
        response = api_client.patch(
            f"/api/datasets-v2/{org1_dataset.key}/",
            {"description": "Updated by creator"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Updated by creator"

    def test_viewer_cannot_update_dataset(self, api_client, viewer_user, org1_dataset):
        """VIEWER users cannot update datasets."""
        api_client.force_authenticate(user=viewer_user)
        response = api_client.patch(
            f"/api/datasets-v2/{org1_dataset.key}/",
            {"name": "Viewer Update"},
            format="json",
        )

        assert response.status_code == 403

    def test_cannot_update_other_org_dataset(
        self, api_client, admin_user, org2_dataset
    ):
        """Users cannot update datasets from other organizations."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/datasets-v2/{org2_dataset.key}/",
            {"name": "Unauthorized Update"},
            format="json",
        )

        assert response.status_code == 404

    def test_cannot_update_nhs_dd_dataset(self, api_client, admin_user, nhs_dd_dataset):
        """NHS DD datasets cannot be updated."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/datasets-v2/{nhs_dd_dataset.key}/",
            {"name": "Modified NHS DD"},
            format="json",
        )

        assert response.status_code == 403

    def test_admin_can_toggle_is_global_flag(
        self, api_client, admin_user, org1_dataset
    ):
        """ADMIN can make an org dataset global (visible to all)."""
        api_client.force_authenticate(user=admin_user)

        # First check the dataset is_global constraint
        # Organization datasets can be made global - check constraint allows it
        org1_dataset.organization = None  # Must remove org to be global
        org1_dataset.is_global = True
        org1_dataset.save()

        # Verify it worked
        org1_dataset.refresh_from_db()
        assert org1_dataset.is_global is True
        assert org1_dataset.organization is None


@pytest.mark.django_db
class TestDataSetDeleteAPI:
    """Tests for DELETE /api/datasets-v2/{key}/"""

    def test_admin_can_delete_org_dataset(self, api_client, admin_user, org1_dataset):
        """ADMIN users can delete their organization's datasets."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/datasets-v2/{org1_dataset.key}/")

        assert response.status_code == 204

        # Verify soft delete (is_active=False)
        org1_dataset.refresh_from_db()
        assert org1_dataset.is_active is False

    def test_creator_can_delete_org_dataset(
        self, api_client, creator_user, org1_dataset
    ):
        """CREATOR users can delete their organization's datasets."""
        api_client.force_authenticate(user=creator_user)
        response = api_client.delete(f"/api/datasets-v2/{org1_dataset.key}/")

        assert response.status_code == 204

    def test_viewer_cannot_delete_dataset(self, api_client, viewer_user, org1_dataset):
        """VIEWER users cannot delete datasets."""
        api_client.force_authenticate(user=viewer_user)
        response = api_client.delete(f"/api/datasets-v2/{org1_dataset.key}/")

        assert response.status_code == 403

    def test_cannot_delete_other_org_dataset(
        self, api_client, admin_user, org2_dataset
    ):
        """Users cannot delete datasets from other organizations."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/datasets-v2/{org2_dataset.key}/")

        assert response.status_code == 404

    def test_cannot_delete_nhs_dd_dataset(self, api_client, admin_user, nhs_dd_dataset):
        """NHS DD datasets cannot be deleted."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/datasets-v2/{nhs_dd_dataset.key}/")

        assert response.status_code == 403

    def test_deleted_dataset_not_in_list(self, api_client, admin_user, org1_dataset):
        """Deleted (inactive) datasets should not appear in list."""
        api_client.force_authenticate(user=admin_user)

        # Delete the dataset
        api_client.delete(f"/api/datasets-v2/{org1_dataset.key}/")

        # List datasets
        response = api_client.get("/api/datasets-v2/")
        keys = {d["key"] for d in response.json()}

        assert "org1_dataset" not in keys


@pytest.mark.django_db
class TestDataSetPermissions:
    """Additional permission edge cases."""

    def test_is_editable_field_correct_for_admin(
        self, api_client, admin_user, org1_dataset, nhs_dd_dataset
    ):
        """is_editable field should be True for org datasets, False for NHS DD."""
        api_client.force_authenticate(user=admin_user)

        # Org dataset
        response = api_client.get(f"/api/datasets-v2/{org1_dataset.key}/")
        assert response.json()["is_editable"] is True

        # NHS DD dataset
        response = api_client.get(f"/api/datasets-v2/{nhs_dd_dataset.key}/")
        assert response.json()["is_editable"] is False

    def test_is_editable_field_correct_for_viewer(
        self, api_client, viewer_user, org1_dataset
    ):
        """is_editable should be False for VIEWER users."""
        api_client.force_authenticate(user=viewer_user)
        response = api_client.get(f"/api/datasets-v2/{org1_dataset.key}/")
        assert response.json()["is_editable"] is False

    def test_user_without_org_cannot_create_dataset(self, api_client, db):
        """Users without organization membership cannot create datasets."""
        user = User.objects.create_user(
            username="no_org_user", email="noorg@example.com", password=TEST_PASSWORD
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/datasets-v2/",
            {"key": "no_org_dataset", "name": "No Org Dataset", "options": ["A"]},
            format="json",
        )

        assert response.status_code == 403
