"""
Tests for dataset sharing features (read-only API surface).

Tests cover:
- Tag-based filtering and search
- Published dataset visibility
- Dataset model methods
- Read-only permissions (is_editable, can_publish fields)

Note: Tests for write operations (create-custom, publish, delete) have been
removed as the API is now read-only. Those operations are web app only.
"""

from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient

from checktick_app.surveys.models import DataSet, Organization, OrganizationMembership

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="admin", password=TEST_PASSWORD)


@pytest.fixture
def creator_user(db):
    return User.objects.create_user(username="creator", password=TEST_PASSWORD)


@pytest.fixture
def member_user(db):
    return User.objects.create_user(username="member", password=TEST_PASSWORD)


@pytest.fixture
def organization(db, admin_user):
    return Organization.objects.create(name="Test Org", owner=admin_user)


@pytest.fixture
def org_admin_membership(db, organization, admin_user):
    return OrganizationMembership.objects.create(
        organization=organization,
        user=admin_user,
        role=OrganizationMembership.Role.ADMIN,
    )


@pytest.fixture
def org_creator_membership(db, organization, creator_user):
    return OrganizationMembership.objects.create(
        organization=organization,
        user=creator_user,
        role=OrganizationMembership.Role.CREATOR,
    )


@pytest.fixture
def org_member_membership(db, organization, member_user):
    return OrganizationMembership.objects.create(
        organization=organization,
        user=member_user,
        role=OrganizationMembership.Role.VIEWER,
    )


@pytest.fixture
def global_dataset(db):
    """NHS DD global dataset."""
    return DataSet.objects.create(
        key="test_global",
        name="Test Global Dataset",
        description="A global test dataset",
        category="nhs_dd",
        source_type="api",
        is_custom=False,
        is_global=True,
        options=["Option 1", "Option 2", "Option 3"],
        tags=["medical", "NHS", "test"],
    )


@pytest.fixture
def org_dataset(db, organization, admin_user):
    """Organization-owned dataset."""
    return DataSet.objects.create(
        key="org_dataset",
        name="Org Dataset",
        description="Organization dataset",
        category="user_created",
        source_type="manual",
        is_custom=True,
        is_global=False,
        organization=organization,
        created_by=admin_user,
        options=["Org Option 1", "Org Option 2"],
        tags=["custom", "org"],
    )


class TestPublishFields:
    """Test read-only fields related to publish state."""

    def test_can_publish_field_shows_correctly(
        self, api_client, admin_user, org_admin_membership, org_dataset, global_dataset
    ):
        """can_publish field shows correct permission."""
        api_client.force_authenticate(user=admin_user)

        # Org dataset - can publish
        response = api_client.get(f"/api/datasets/{org_dataset.key}/")
        assert response.data["can_publish"] is True

        # Global dataset - cannot publish (already global)
        response = api_client.get(f"/api/datasets/{global_dataset.key}/")
        assert response.data["can_publish"] is False


class TestTagFiltering:
    """Test tag-based filtering and search."""

    def test_filter_by_single_tag(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Can filter datasets by single tag."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get("/api/datasets/?tags=medical")

        assert response.status_code == 200
        assert len(response.data) >= 1
        assert global_dataset.key in [d["key"] for d in response.data]

    def test_filter_by_multiple_tags(
        self, api_client, admin_user, org_admin_membership, global_dataset, org_dataset
    ):
        """Can filter datasets by multiple tags (AND logic)."""
        api_client.force_authenticate(user=admin_user)

        # Should match global_dataset (has both 'medical' and 'NHS')
        response = api_client.get("/api/datasets/?tags=medical,NHS")

        assert response.status_code == 200
        dataset_keys = [d["key"] for d in response.data]
        assert global_dataset.key in dataset_keys
        # org_dataset doesn't have both tags
        assert org_dataset.key not in dataset_keys

    def test_search_by_name(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Can search datasets by name."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get("/api/datasets/?search=Global")

        assert response.status_code == 200
        assert len(response.data) >= 1
        assert global_dataset.key in [d["key"] for d in response.data]

    def test_search_by_description(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Can search datasets by description."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get("/api/datasets/?search=global test")

        assert response.status_code == 200
        assert global_dataset.key in [d["key"] for d in response.data]

    def test_filter_by_category(
        self, api_client, admin_user, org_admin_membership, global_dataset, org_dataset
    ):
        """Can filter datasets by category."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get("/api/datasets/?category=nhs_dd")

        assert response.status_code == 200
        dataset_keys = [d["key"] for d in response.data]
        assert global_dataset.key in dataset_keys
        assert org_dataset.key not in dataset_keys

    def test_combine_filters(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Can combine multiple filters."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            "/api/datasets/?tags=medical&search=Global&category=nhs_dd"
        )

        assert response.status_code == 200
        assert global_dataset.key in [d["key"] for d in response.data]

    def test_available_tags_endpoint(
        self, api_client, admin_user, org_admin_membership, global_dataset, org_dataset
    ):
        """Available tags endpoint returns tag counts."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get("/api/datasets/available-tags/")

        assert response.status_code == 200
        assert "tags" in response.data
        assert len(response.data["tags"]) > 0

        # Check structure
        first_tag = response.data["tags"][0]
        assert "tag" in first_tag
        assert "count" in first_tag

        # Verify some expected tags
        tag_names = [t["tag"] for t in response.data["tags"]]
        assert "medical" in tag_names
        assert "custom" in tag_names


class TestDataSetModel:
    """Test DataSet model methods."""

    def test_create_custom_version_method(
        self, db, global_dataset, organization, admin_user
    ):
        """Test create_custom_version model method."""
        custom = global_dataset.create_custom_version(
            user=admin_user, organization=organization, custom_name="My Custom"
        )

        assert custom.parent == global_dataset
        assert custom.name == "My Custom"
        assert custom.is_custom is True
        assert custom.is_global is False
        assert custom.organization == organization
        assert custom.options == global_dataset.options
        assert custom.tags == global_dataset.tags

    def test_create_custom_version_default_name(
        self, db, global_dataset, organization, admin_user
    ):
        """Test create_custom_version with default name."""
        custom = global_dataset.create_custom_version(
            user=admin_user, organization=organization
        )

        assert f"{global_dataset.name} (Custom)" == custom.name

    def test_create_custom_version_only_from_global(
        self, db, org_dataset, organization, admin_user
    ):
        """Cannot create custom version from non-global dataset."""
        with pytest.raises(ValueError, match="global"):
            org_dataset.create_custom_version(
                user=admin_user, organization=organization
            )

    def test_publish_method(self, db, org_dataset):
        """Test publish model method."""
        assert org_dataset.is_global is False
        assert org_dataset.published_at is None

        org_dataset.publish()

        assert org_dataset.is_global is True
        assert org_dataset.published_at is not None
        # Organization retained
        assert org_dataset.organization is not None

    def test_publish_already_global_raises_error(self, db, global_dataset):
        """Cannot publish already-global dataset."""
        with pytest.raises(ValueError, match="already published"):
            global_dataset.publish()

    def test_publish_requires_organization(self, db):
        """Individual user datasets can now be published without organization."""
        user = User.objects.create_user(username="testuser", password=TEST_PASSWORD)
        dataset = DataSet.objects.create(
            key="no_org",
            name="No Org",
            category="user_created",
            is_global=False,
            is_custom=True,
            options=[],
            created_by=user,
        )

        # Should succeed now - individual users can publish
        dataset.publish()
        assert dataset.is_global is True
        assert dataset.published_at is not None


class TestPermissions:
    """Test permission logic for new features."""

    def test_is_editable_field_for_published(
        self,
        api_client,
        admin_user,
        org_admin_membership,
        org_dataset,
        creator_user,
        org_creator_membership,
    ):
        """Org datasets are editable by admin and creator."""
        api_client.force_authenticate(user=admin_user)

        # Editable by org admin
        response = api_client.get(f"/api/datasets/{org_dataset.key}/")
        assert response.data["is_editable"] is True

        # Also editable by creator in same org
        api_client.force_authenticate(user=creator_user)
        response = api_client.get(f"/api/datasets/{org_dataset.key}/")
        assert response.data["is_editable"] is True
