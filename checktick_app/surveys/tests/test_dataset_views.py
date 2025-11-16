"""
Tests for dataset web UI views.

Covers:
- Dataset list view with filtering
- Dataset detail view
- Dataset create view with permissions
- Dataset edit view with permissions
- Dataset delete view with permissions
- Access control for different roles
"""

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import DataSet, Organization, OrganizationMembership

TEST_PASSWORD = "x"


@pytest.fixture
def users(db):
    """Create test users with different roles."""
    admin = User.objects.create_user(username="admin", password=TEST_PASSWORD)
    creator = User.objects.create_user(username="creator", password=TEST_PASSWORD)
    viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
    outsider = User.objects.create_user(username="outsider", password=TEST_PASSWORD)
    return admin, creator, viewer, outsider


@pytest.fixture
def org1(db, users):
    """Create organization 1 with memberships."""
    admin, creator, viewer, outsider = users
    org = Organization.objects.create(name="Org 1", owner=admin)
    OrganizationMembership.objects.create(
        organization=org, user=admin, role=OrganizationMembership.Role.ADMIN
    )
    OrganizationMembership.objects.create(
        organization=org, user=creator, role=OrganizationMembership.Role.CREATOR
    )
    OrganizationMembership.objects.create(
        organization=org, user=viewer, role=OrganizationMembership.Role.VIEWER
    )
    return org


@pytest.fixture
def org2(db, users):
    """Create organization 2 with no memberships for main users."""
    admin, creator, viewer, outsider = users
    org = Organization.objects.create(name="Org 2", owner=outsider)
    OrganizationMembership.objects.create(
        organization=org, user=outsider, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.fixture
def global_dataset(db):
    """Create a global NHS DD dataset."""
    return DataSet.objects.create(
        key="nhs_specialty",
        name="NHS Specialty Codes",
        category="nhs_dd",
        source_type="manual",
        is_custom=False,
        is_global=True,
        options=["100 - Surgery", "200 - Medicine"],
    )


@pytest.fixture
def org1_dataset(db, org1, users):
    """Create a dataset for org1."""
    admin, creator, viewer, outsider = users
    return DataSet.objects.create(
        key="org1_custom_list",
        name="Org 1 Custom List",
        category="user_created",
        source_type="manual",
        is_custom=True,
        organization=org1,
        created_by=creator,
        options={"opt_a": "Option A", "opt_b": "Option B", "opt_c": "Option C"},
    )


@pytest.fixture
def org2_dataset(db, org2, users):
    """Create a dataset for org2."""
    admin, creator, viewer, outsider = users
    return DataSet.objects.create(
        key="org2_custom_list",
        name="Org 2 Custom List",
        category="user_created",
        source_type="manual",
        is_custom=True,
        organization=org2,
        created_by=outsider,
        options=["Option X", "Option Y"],
    )


# ==============================================================================
# Dataset List View Tests
# ==============================================================================


@pytest.mark.django_db
def test_dataset_list_requires_login(client):
    """Test that dataset list requires authentication."""
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_dataset_list_shows_global_datasets(
    client, users, org1, global_dataset, org1_dataset
):
    """Test that all users can see global datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    dataset_ids = [d.id for d in res.context["page_obj"].object_list]
    assert global_dataset.id in dataset_ids


@pytest.mark.django_db
def test_dataset_list_shows_org_datasets(
    client, users, org1, global_dataset, org1_dataset, org2_dataset
):
    """Test that users see datasets from their organizations."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    dataset_ids = [d.id for d in res.context["page_obj"].object_list]
    assert global_dataset.id in dataset_ids
    assert org1_dataset.id in dataset_ids
    assert org2_dataset.id not in dataset_ids  # Different org


@pytest.mark.django_db
def test_dataset_list_hides_other_org_datasets(
    client, users, org1, org2, org1_dataset, org2_dataset
):
    """Test that users cannot see datasets from other organizations."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)  # Member of org1 only
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    dataset_ids = [d.id for d in res.context["page_obj"].object_list]
    assert org1_dataset.id in dataset_ids
    assert org2_dataset.id not in dataset_ids


@pytest.mark.django_db
def test_dataset_list_category_filter(
    client, users, org1, global_dataset, org1_dataset
):
    """Test filtering datasets by category."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(reverse("surveys:dataset_list") + "?category=nhs_dd")
    assert res.status_code == 200
    dataset_ids = [d.id for d in res.context["page_obj"].object_list]
    assert global_dataset.id in dataset_ids
    assert org1_dataset.id not in dataset_ids  # Different category


@pytest.mark.django_db
def test_dataset_list_org_filter(client, users, org1, global_dataset, org1_dataset):
    """Test filtering datasets by organization shows org datasets AND global datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(reverse("surveys:dataset_list") + f"?organization={org1.id}")
    assert res.status_code == 200
    dataset_ids = [d.id for d in res.context["page_obj"].object_list]
    assert org1_dataset.id in dataset_ids  # Org's custom dataset
    assert global_dataset.id in dataset_ids  # Global datasets also available


@pytest.mark.django_db
def test_dataset_list_can_create_flag_admin(client, users, org1):
    """Test that ADMIN users see can_create flag as True."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    assert res.context["can_create"] is True


@pytest.mark.django_db
def test_dataset_list_can_create_flag_creator(client, users, org1):
    """Test that CREATOR users see can_create flag as True."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    assert res.context["can_create"] is True


@pytest.mark.django_db
def test_dataset_list_can_create_flag_viewer(client, users, org1):
    """Test that VIEWER users cannot create datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(reverse("surveys:dataset_list"))
    assert res.status_code == 200
    assert res.context["can_create"] is False


# ==============================================================================
# Dataset Detail View Tests
# ==============================================================================


@pytest.mark.django_db
def test_dataset_detail_requires_login(client, org1_dataset):
    """Test that dataset detail requires authentication."""
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_dataset_detail_shows_dataset(client, users, org1, org1_dataset):
    """Test that dataset detail shows dataset information."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200
    assert res.context["dataset"].id == org1_dataset.id
    assert "Option A" in str(res.content)


@pytest.mark.django_db
def test_dataset_detail_blocks_other_org(client, users, org2_dataset):
    """Test that users cannot view datasets from other organizations."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)  # Member of org1, not org2
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org2_dataset.id})
    )
    assert res.status_code == 404


@pytest.mark.django_db
def test_dataset_detail_can_edit_flag_admin(client, users, org1, org1_dataset):
    """Test that ADMIN users can edit org datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200
    assert res.context["can_edit"] is True


@pytest.mark.django_db
def test_dataset_detail_can_edit_flag_creator(client, users, org1, org1_dataset):
    """Test that CREATOR users can edit org datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200
    assert res.context["can_edit"] is True


@pytest.mark.django_db
def test_dataset_detail_can_edit_flag_viewer(client, users, org1, org1_dataset):
    """Test that VIEWER users cannot edit org datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200
    assert res.context["can_edit"] is False


@pytest.mark.django_db
def test_dataset_detail_cannot_edit_nhs_dd(client, users, org1, global_dataset):
    """Test that NHS DD datasets cannot be edited even by admins."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(
        reverse("surveys:dataset_detail", kwargs={"dataset_id": global_dataset.id})
    )
    assert res.status_code == 200
    assert res.context["can_edit"] is False


# ==============================================================================
# Dataset Create View Tests
# ==============================================================================


@pytest.mark.django_db
def test_dataset_create_requires_login(client):
    """Test that dataset create requires authentication."""
    res = client.get(reverse("surveys:dataset_create"))
    assert res.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_dataset_create_blocks_viewer(client, users, org1):
    """Test that VIEWER users cannot access create form."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(reverse("surveys:dataset_create"))
    assert res.status_code == 403


@pytest.mark.django_db
def test_dataset_create_allows_admin(client, users, org1):
    """Test that ADMIN users can access create form."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(reverse("surveys:dataset_create"))
    assert res.status_code == 200
    assert "Create Dataset" in str(res.content)


@pytest.mark.django_db
def test_dataset_create_allows_creator(client, users, org1):
    """Test that CREATOR users can access create form."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(reverse("surveys:dataset_create"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_dataset_create_post_success(client, users, org1):
    """Test creating a dataset via POST."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "key": "my_test_dataset",
        "name": "My Test Dataset",
        "description": "Test description",
        "category": "user_created",
        "source_type": "manual",
        "organization": org1.id,
        "options": "Option 1\nOption 2\nOption 3",
        "format_pattern": "simple",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 302  # Redirect on success

    # Verify dataset was created
    dataset = DataSet.objects.get(key="my_test_dataset")
    assert dataset.name == "My Test Dataset"
    assert dataset.organization == org1
    assert dataset.created_by == creator
    assert len(dataset.options) == 3


@pytest.mark.django_db
def test_dataset_create_post_missing_key(client, users, org1):
    """Test creating dataset without key auto-generates one."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "name": "My Test Dataset",
        "organization": org1.id,
        "options": "Option 1\nOption 2",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 302  # Redirects on success
    # Key was auto-generated from name
    assert DataSet.objects.filter(name="My Test Dataset").exists()


@pytest.mark.django_db
def test_dataset_create_post_invalid_key(client, users, org1):
    """Test creating dataset with invalid key auto-generates a valid one."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "key": "Invalid Key!",
        "name": "My Test Dataset",
        "organization": org1.id,
        "options": "Option 1\nOption 2",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 200  # Stays on form with error
    assert "lowercase alphanumeric" in str(res.content) or "simpler name" in str(
        res.content
    )


@pytest.mark.django_db
def test_dataset_create_post_duplicate_key(client, users, org1, org1_dataset):
    """Test creating dataset with duplicate key auto-generates unique key."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "key": org1_dataset.key,
        "name": "Duplicate Key Dataset",
        "organization": org1.id,
        "options": "Option 1\nOption 2",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 302  # Redirects on success
    # Dataset created with unique key (timestamp appended)
    assert DataSet.objects.filter(name="Duplicate Key Dataset").exists()


@pytest.mark.django_db
def test_dataset_create_post_no_options(client, users, org1):
    """Test creating dataset without options fails."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "key": "empty_dataset",
        "name": "Empty Dataset",
        "organization": org1.id,
        "options": "",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 200
    assert "At least one option is required" in str(res.content)


@pytest.mark.django_db
def test_dataset_create_post_wrong_org(client, users, org1, org2):
    """Test creating dataset for org where user has no permission fails."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)  # Member of org1 only
    data = {
        "key": "test_dataset",
        "name": "Test Dataset",
        "organization": org2.id,  # Not a member
        "options": "Option 1\nOption 2",
    }
    res = client.post(reverse("surveys:dataset_create"), data=data)
    assert res.status_code == 200
    assert "don&#x27;t have permission" in str(res.content)


# ==============================================================================
# Dataset Edit View Tests
# ==============================================================================


@pytest.mark.django_db
def test_dataset_edit_requires_login(client, org1_dataset):
    """Test that dataset edit requires authentication."""
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_dataset_edit_blocks_viewer(client, users, org1, org1_dataset):
    """Test that VIEWER users cannot edit datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_dataset_edit_allows_admin(client, users, org1, org1_dataset):
    """Test that ADMIN users can edit datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200
    assert "Edit Dataset" in str(res.content)


@pytest.mark.django_db
def test_dataset_edit_allows_creator(client, users, org1, org1_dataset):
    """Test that CREATOR users can edit datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_dataset_edit_blocks_nhs_dd(client, users, org1, global_dataset):
    """Test that NHS DD datasets cannot be edited."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": global_dataset.id})
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_dataset_edit_post_success(client, users, org1, org1_dataset):
    """Test editing a dataset via POST."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    original_version = org1_dataset.version
    data = {
        "name": "Updated Dataset Name",
        "description": "Updated description",
        "options": "New Option 1\nNew Option 2",
        "format_pattern": "updated",
    }
    res = client.post(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id}),
        data=data,
    )
    assert res.status_code == 302  # Redirect on success

    # Verify dataset was updated
    org1_dataset.refresh_from_db()
    assert org1_dataset.name == "Updated Dataset Name"
    assert org1_dataset.description == "Updated description"
    assert len(org1_dataset.options) == 2
    assert org1_dataset.version == original_version + 1


@pytest.mark.django_db
def test_dataset_edit_post_missing_name(client, users, org1, org1_dataset):
    """Test editing dataset without name fails."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    data = {
        "name": "",
        "options": "Option 1\nOption 2",
    }
    res = client.post(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org1_dataset.id}),
        data=data,
    )
    assert res.status_code == 200
    assert "Name is required" in str(res.content)


@pytest.mark.django_db
def test_dataset_edit_blocks_other_org(client, users, org2_dataset):
    """Test that users cannot edit datasets from other organizations."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)  # Member of org1, not org2
    res = client.get(
        reverse("surveys:dataset_edit", kwargs={"dataset_id": org2_dataset.id})
    )
    assert res.status_code == 404


# ==============================================================================
# Dataset Delete View Tests
# ==============================================================================


@pytest.mark.django_db
def test_dataset_delete_requires_login(client, org1_dataset):
    """Test that dataset delete requires authentication."""
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_dataset_delete_requires_post(client, users, org1, org1_dataset):
    """Test that dataset delete requires POST method."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.get(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 405  # Method not allowed


@pytest.mark.django_db
def test_dataset_delete_blocks_viewer(client, users, org1, org1_dataset):
    """Test that VIEWER users cannot delete datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(viewer)
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_dataset_delete_allows_admin(client, users, org1, org1_dataset):
    """Test that ADMIN users can delete datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 302  # Redirect on success

    # Verify soft delete
    org1_dataset.refresh_from_db()
    assert org1_dataset.is_active is False


@pytest.mark.django_db
def test_dataset_delete_allows_creator(client, users, org1, org1_dataset):
    """Test that CREATOR users can delete datasets."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org1_dataset.id})
    )
    assert res.status_code == 302

    org1_dataset.refresh_from_db()
    assert org1_dataset.is_active is False


@pytest.mark.django_db
def test_dataset_delete_blocks_nhs_dd(client, users, org1, global_dataset):
    """Test that NHS DD datasets cannot be deleted."""
    admin, creator, viewer, outsider = users
    client.force_login(admin)
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": global_dataset.id})
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_dataset_delete_blocks_other_org(client, users, org2_dataset):
    """Test that users cannot delete datasets from other organizations."""
    admin, creator, viewer, outsider = users
    client.force_login(creator)  # Member of org1, not org2
    res = client.post(
        reverse("surveys:dataset_delete", kwargs={"dataset_id": org2_dataset.id})
    )
    assert res.status_code == 404
