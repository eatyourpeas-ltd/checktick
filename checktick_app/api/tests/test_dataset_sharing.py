"""
Tests for dataset sharing and customization features.

Tests cover:
- Creating custom versions from global datasets
- Publishing datasets globally
- Tag-based filtering and search
- Permissions and constraints
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


class TestCreateCustomVersion:
    """Test creating custom versions from global datasets."""

    def test_admin_can_create_custom_version(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """ADMIN can create custom version of global dataset."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/",
            {"name": "My Custom Version"},
        )

        assert response.status_code == 201
        assert "key" in response.data
        assert response.data["name"] == "My Custom Version"
        assert response.data["parent"] == global_dataset.key
        assert response.data["parent_name"] == global_dataset.name
        assert response.data["is_custom"] is True
        assert response.data["is_global"] is False
        assert response.data["options"] == global_dataset.options
        assert response.data["tags"] == global_dataset.tags

    def test_creator_can_create_custom_version(
        self, api_client, creator_user, org_creator_membership, global_dataset
    ):
        """CREATOR can create custom version of global dataset."""
        api_client.force_authenticate(user=creator_user)

        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/", {}
        )

        assert response.status_code == 201
        assert response.data["parent"] == global_dataset.key
        # Default name includes "(Custom)"
        assert "(Custom)" in response.data["name"]

    def test_member_cannot_create_custom_version(
        self, api_client, member_user, org_member_membership, global_dataset
    ):
        """VIEWER role cannot create custom versions."""
        api_client.force_authenticate(user=member_user)

        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/", {}
        )

        # Forbidden - VIEWER role is read-only
        assert response.status_code == 403

    def test_cannot_create_custom_from_non_global(
        self, api_client, admin_user, org_admin_membership, org_dataset
    ):
        """Cannot create custom version from non-global dataset."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(
            f"/api/datasets/{org_dataset.key}/create-custom/", {}
        )

        assert response.status_code == 400
        assert "global" in response.data["error"].lower()

    def test_custom_version_is_editable(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Custom versions can be edited."""
        api_client.force_authenticate(user=admin_user)

        # Create custom version
        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/", {}
        )
        custom_key = response.data["key"]

        # Edit it
        response = api_client.patch(
            f"/api/datasets/{custom_key}/",
            {"options": {"opt_1": "Modified Option 1", "opt_2": "Modified Option 2"}},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["options"] == {
            "opt_1": "Modified Option 1",
            "opt_2": "Modified Option 2",
        }

    def test_specify_organization(
        self, api_client, admin_user, org_admin_membership, global_dataset, organization
    ):
        """Can specify which organization owns the custom version."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/",
            {"organization": organization.id},
        )

        assert response.status_code == 201
        assert response.data["organization"] == organization.id


class TestPublishDataset:
    """Test publishing datasets globally."""

    def test_admin_can_publish_org_dataset(
        self, api_client, admin_user, org_admin_membership, org_dataset
    ):
        """ADMIN can publish organization dataset globally."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        assert response.status_code == 200
        assert response.data["is_global"] is True
        assert response.data["published_at"] is not None
        # Organization retained for attribution
        assert response.data["organization"] == org_dataset.organization.id

    def test_creator_can_publish_org_dataset(
        self, api_client, creator_user, org_creator_membership, org_dataset
    ):
        """CREATOR can publish organization dataset globally."""
        api_client.force_authenticate(user=creator_user)

        response = api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        assert response.status_code == 200
        assert response.data["is_global"] is True

    def test_member_cannot_publish(
        self, api_client, member_user, org_member_membership, org_dataset
    ):
        """MEMBER cannot publish - needs ADMIN/CREATOR role."""
        api_client.force_authenticate(user=member_user)

        response = api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        assert response.status_code == 403

    def test_cannot_publish_already_global(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Cannot publish dataset that's already global."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(f"/api/datasets/{global_dataset.key}/publish/")

        assert response.status_code == 400
        assert "already published" in response.data["error"].lower()

    def test_published_dataset_visible_to_all(
        self, api_client, admin_user, org_admin_membership, org_dataset, db
    ):
        """Published datasets are visible to all authenticated users."""
        # Publish the dataset
        api_client.force_authenticate(user=admin_user)
        api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        # Create a different user not in the organization
        other_user = User.objects.create_user(username="other", password=TEST_PASSWORD)
        api_client.force_authenticate(user=other_user)

        # Should be able to see the published dataset
        response = api_client.get("/api/datasets/")
        assert response.status_code == 200

        dataset_keys = [d["key"] for d in response.data]
        assert org_dataset.key in dataset_keys

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


class TestDatasetDeletion:
    """Test deletion constraints for published datasets."""

    def test_can_delete_unpublished_org_dataset(
        self, api_client, admin_user, org_admin_membership, org_dataset
    ):
        """Can delete unpublished organization dataset."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(f"/api/datasets/{org_dataset.key}/")
        assert response.status_code == 204

        # Verify soft delete
        org_dataset.refresh_from_db()
        assert org_dataset.is_active is False

    def test_cannot_delete_published_with_dependents(
        self,
        api_client,
        admin_user,
        org_admin_membership,
        org_dataset,
        db,
    ):
        """Cannot delete published dataset if others have created custom versions."""
        api_client.force_authenticate(user=admin_user)

        # Publish the dataset
        api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        # Create a different organization and user
        other_user = User.objects.create_user(
            username="other_user", password=TEST_PASSWORD
        )
        other_org = Organization.objects.create(name="Other Org", owner=other_user)
        OrganizationMembership.objects.create(
            organization=other_org,
            user=other_user,
            role=OrganizationMembership.Role.ADMIN,
        )

        # Other user creates a custom version
        api_client.force_authenticate(user=other_user)
        api_client.post(
            f"/api/datasets/{org_dataset.key}/create-custom/",
            {"name": "Dependent Custom", "organization": other_org.id},
        )

        # Try to delete - should fail
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/datasets/{org_dataset.key}/")

        assert response.status_code == 400
        assert "custom versions" in response.data["error"].lower()

    def test_can_delete_published_without_dependents(
        self, api_client, admin_user, org_admin_membership, org_dataset
    ):
        """Can delete published dataset if no one else is using it."""
        api_client.force_authenticate(user=admin_user)

        # Publish the dataset
        api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        # Delete it (no dependents)
        response = api_client.delete(f"/api/datasets/{org_dataset.key}/")
        assert response.status_code == 204


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
        """Published datasets remain editable by original organization."""
        api_client.force_authenticate(user=admin_user)

        # Publish
        api_client.post(f"/api/datasets/{org_dataset.key}/publish/")

        # Still editable by org members
        response = api_client.get(f"/api/datasets/{org_dataset.key}/")
        assert response.data["is_editable"] is True

        # Also editable by creator in same org
        api_client.force_authenticate(user=creator_user)
        response = api_client.get(f"/api/datasets/{org_dataset.key}/")
        assert response.data["is_editable"] is True

    def test_is_editable_field_for_custom_version(
        self, api_client, admin_user, org_admin_membership, global_dataset
    ):
        """Custom versions are editable by creating user's organization."""
        api_client.force_authenticate(user=admin_user)

        # Create custom version
        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/", {}
        )
        custom_key = response.data["key"]

        # Should be editable
        response = api_client.get(f"/api/datasets/{custom_key}/")
        assert response.data["is_editable"] is True


@pytest.mark.django_db
class TestIndividualUserDatasets:
    """Test dataset operations for individual users (without organizations)."""

    def test_individual_user_can_create_dataset(self, api_client, db):
        """Individual users can create datasets without organization."""
        # Create user without any organization
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/datasets/",
            {
                "name": "My Personal List",
                "description": "My personal dataset",
            },
            format="json",
        )

        if response.status_code != 201:
            print(f"Error response: {response.status_code}, {response.data}")
        assert response.status_code == 201
        assert response.data["name"] == "My Personal List"
        assert response.data["organization"] is None
        assert response.data["created_by_username"] == user.username
        assert response.data["is_global"] is False

    def test_individual_user_can_view_own_dataset(self, api_client, db):
        """Individual users can view their own datasets."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        # Create dataset
        response = api_client.post(
            "/api/datasets/",
            {"name": "My List", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]

        # View dataset
        response = api_client.get(f"/api/datasets/{dataset_key}/")
        assert response.status_code == 200
        assert response.data["name"] == "My List"

    def test_individual_user_can_edit_own_dataset(self, api_client, db):
        """Individual users can edit their own datasets."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        # Create dataset
        response = api_client.post(
            "/api/datasets/",
            {"name": "Original", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]

        # Edit dataset
        response = api_client.patch(
            f"/api/datasets/{dataset_key}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["name"] == "Updated Name"

    def test_individual_user_cannot_edit_others_dataset(self, api_client, db):
        """Individual users cannot edit datasets created by others."""
        user1 = User.objects.create_user(username="user1", password=TEST_PASSWORD)
        user2 = User.objects.create_user(username="user2", password=TEST_PASSWORD)

        # User1 creates dataset
        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/datasets/",
            {"name": "User1 List", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]

        # User2 tries to edit - should get 404 (can't even see it)
        api_client.force_authenticate(user=user2)
        response = api_client.patch(
            f"/api/datasets/{dataset_key}/",
            {"name": "Hacked"},
            format="json",
        )
        assert (
            response.status_code == 404
        )  # Can't see unpublished datasets from other users

    def test_individual_user_can_publish_own_dataset(self, api_client, db):
        """Individual users can publish their own datasets globally."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        # Create dataset
        response = api_client.post(
            "/api/datasets/",
            {"name": "Great List", "description": "Useful data", "tags": ["public"]},
            format="json",
        )
        dataset_key = response.data["key"]

        # Publish it
        response = api_client.post(f"/api/datasets/{dataset_key}/publish/")
        assert response.status_code == 200
        assert response.data["is_global"] is True
        assert response.data["published_at"] is not None

    def test_individual_user_cannot_publish_others_dataset(self, api_client, db):
        """Individual users cannot publish datasets created by others."""
        user1 = User.objects.create_user(username="user1", password=TEST_PASSWORD)
        user2 = User.objects.create_user(username="user2", password=TEST_PASSWORD)

        # User1 creates dataset
        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/datasets/",
            {"name": "User1 List", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]

        # User2 tries to publish - should get 404 (can't see unpublished)
        api_client.force_authenticate(user=user2)
        response = api_client.post(f"/api/datasets/{dataset_key}/publish/")
        assert (
            response.status_code == 404
        )  # Can't see unpublished datasets from other users

    def test_individual_user_can_create_custom_version(self, api_client, db):
        """Individual users can create custom versions from global datasets."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)

        # Create a published global dataset
        creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
        global_dataset = DataSet.objects.create(
            key="global-list",
            name="Global List",
            category="user_created",
            source_type="manual",
            is_custom=True,
            is_global=True,
            created_by=creator,
        )

        # Individual user creates custom version
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/datasets/{global_dataset.key}/create-custom/",
            {"name": "My Custom Version"},
            format="json",
        )

        assert response.status_code == 201  # Create operation returns 201
        assert response.data["name"] == "My Custom Version"
        assert response.data["parent"] == "global-list"
        assert response.data["organization"] is None
        assert response.data["created_by_username"] == user.username

    def test_individual_user_can_delete_own_dataset(self, api_client, db):
        """Individual users can delete their own unpublished datasets."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        # Create dataset
        response = api_client.post(
            "/api/datasets/",
            {"name": "Temporary List", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]

        # Delete it
        response = api_client.delete(f"/api/datasets/{dataset_key}/")
        assert response.status_code == 204

    def test_individual_user_cannot_delete_published_with_dependents(
        self, api_client, db
    ):
        """Individual users cannot delete published datasets with dependents."""
        user1 = User.objects.create_user(username="user1", password=TEST_PASSWORD)
        user2 = User.objects.create_user(username="user2", password=TEST_PASSWORD)

        # User1 creates and publishes dataset
        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/datasets/",
            {"name": "Popular List", "description": "Test"},
            format="json",
        )
        dataset_key = response.data["key"]
        api_client.post(f"/api/datasets/{dataset_key}/publish/")

        # User2 creates custom version
        api_client.force_authenticate(user=user2)
        api_client.post(f"/api/datasets/{dataset_key}/create-custom/", {})

        # User1 tries to delete - should fail
        api_client.force_authenticate(user=user1)
        response = api_client.delete(f"/api/datasets/{dataset_key}/")
        assert response.status_code == 400
        assert "custom versions" in response.data["error"]

    def test_individual_datasets_appear_in_list(self, api_client, db):
        """Individual user datasets appear in user's dataset list."""
        user = User.objects.create_user(username="individual", password=TEST_PASSWORD)
        api_client.force_authenticate(user=user)

        # Create dataset
        api_client.post(
            "/api/datasets/",
            {"name": "My List", "description": "Test"},
            format="json",
        )

        # List datasets
        response = api_client.get("/api/datasets/")
        assert response.status_code == 200

        # Find our dataset
        my_datasets = [d for d in response.data if d["name"] == "My List"]
        assert len(my_datasets) == 1
        assert my_datasets[0]["organization"] is None

    def test_individual_published_datasets_visible_to_all(self, api_client, db):
        """Published individual datasets are visible to all authenticated users."""
        user1 = User.objects.create_user(username="user1", password=TEST_PASSWORD)
        user2 = User.objects.create_user(username="user2", password=TEST_PASSWORD)

        # User1 creates and publishes dataset
        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/datasets/",
            {"name": "Public List", "description": "For everyone"},
            format="json",
        )
        dataset_key = response.data["key"]
        api_client.post(f"/api/datasets/{dataset_key}/publish/")

        # User2 can see it
        api_client.force_authenticate(user=user2)
        response = api_client.get("/api/datasets/")
        public_datasets = [d for d in response.data if d["name"] == "Public List"]
        assert len(public_datasets) == 1

    def test_individual_unpublished_datasets_private(self, api_client, db):
        """Unpublished individual datasets are private to creator."""
        user1 = User.objects.create_user(username="user1", password=TEST_PASSWORD)
        user2 = User.objects.create_user(username="user2", password=TEST_PASSWORD)

        # User1 creates private dataset
        api_client.force_authenticate(user=user1)
        response = api_client.post(
            "/api/datasets/",
            {"name": "Private List", "description": "Just for me"},
            format="json",
        )
        dataset_key = response.data["key"]

        # User2 cannot see it in list
        api_client.force_authenticate(user=user2)
        response = api_client.get("/api/datasets/")
        private_datasets = [d for d in response.data if d["name"] == "Private List"]
        assert len(private_datasets) == 0

        # User2 cannot access directly
        response = api_client.get(f"/api/datasets/{dataset_key}/")
        assert response.status_code == 404
