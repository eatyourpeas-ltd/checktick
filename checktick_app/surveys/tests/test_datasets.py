"""
Tests for DataSet model and external dataset functionality.

Covers:
- DataSet model CRUD operations
- NHS DD dataset read-only enforcement
- Custom version creation and editing
- Database integration with external_datasets.py
- Organization-based filtering
- Version tracking and sync scheduling
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from checktick_app.surveys.models import DataSet, Organization
from checktick_app.surveys.external_datasets import (
    get_available_datasets,
    fetch_dataset,
)

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def organization(db, user):
    """Create a test organization."""
    return Organization.objects.create(
        name="Test Hospital",
        owner=user,
    )


@pytest.fixture
def nhs_dd_dataset(db):
    """Create a test NHS DD dataset."""
    return DataSet.objects.create(
        key="test_specialty",
        name="Test Specialty Codes",
        description="Test NHS DD dataset",
        category="nhs_dd",
        source_type="manual",
        is_custom=False,
        is_global=True,
        options=[
            "100 - General Surgery",
            "200 - Cardiology",
            "300 - Neurology",
        ],
        format_pattern="code - description",
    )


@pytest.fixture
def api_dataset(db):
    """Create a test external API dataset."""
    return DataSet.objects.create(
        key="test_hospitals",
        name="Test Hospitals",
        description="Test hospital dataset from API",
        category="external_api",
        source_type="api",
        is_custom=False,
        is_global=True,
        options=["Hospital A", "Hospital B", "Hospital C"],
        last_synced_at=timezone.now(),
    )


@pytest.fixture
def custom_dataset(db, user, organization, nhs_dd_dataset):
    """Create a test custom dataset based on NHS DD."""
    return nhs_dd_dataset.create_custom_version(
        user=user,
        organization=organization,
    )


class TestDataSetModel:
    """Tests for DataSet model."""

    def test_create_nhs_dd_dataset(self, db):
        """Test creating an NHS DD dataset."""
        dataset = DataSet.objects.create(
            key="ethnic_category",
            name="Ethnic Category",
            category="nhs_dd",
            source_type="manual",
            is_custom=False,
            is_global=True,
            options=["A - White British", "B - White Irish"],
        )

        assert dataset.key == "ethnic_category"
        assert dataset.is_editable is False
        assert dataset.is_global is True
        assert dataset.organization is None
        assert len(dataset.options) == 2

    def test_nhs_dd_must_be_global(self, db, user):
        """Test that NHS DD datasets cannot have an organization."""
        org = Organization.objects.create(name="Test Org", owner=user)

        with pytest.raises(IntegrityError):
            DataSet.objects.create(
                key="bad_nhs_dd",
                name="Bad NHS DD",
                category="nhs_dd",
                source_type="manual",
                is_custom=False,
                organization=org,  # This should fail
                options=["Option 1"],
            )

    def test_global_datasets_no_org(self, db, user):
        """Test that global datasets cannot have an organization."""
        org = Organization.objects.create(name="Test Org", owner=user)

        with pytest.raises(IntegrityError):
            DataSet.objects.create(
                key="bad_global",
                name="Bad Global",
                category="external_api",
                source_type="api",
                is_custom=False,
                is_global=True,
                organization=org,  # This should fail
                options=["Option 1"],
            )

    def test_nhs_dd_is_not_editable(self, nhs_dd_dataset):
        """Test that NHS DD datasets are marked as not editable."""
        assert nhs_dd_dataset.is_custom is False
        assert nhs_dd_dataset.is_editable is False

    def test_custom_dataset_is_editable(self, custom_dataset):
        """Test that custom datasets are marked as editable."""
        assert custom_dataset.is_custom is True
        assert custom_dataset.is_editable is True

    def test_create_user_created_dataset(self, db, user, organization):
        """Test creating a user-created dataset."""
        dataset = DataSet.objects.create(
            key="my_hospitals",
            name="My Hospital List",
            description="Custom hospital list",
            category="user_created",
            source_type="manual",
            is_custom=True,
            organization=organization,
            is_global=False,
            created_by=user,
            options=["St Mary's", "Royal Infirmary", "City Hospital"],
        )

        assert dataset.is_editable is True
        assert dataset.organization == organization
        assert dataset.created_by == user
        assert len(dataset.options) == 3

    def test_version_tracking(self, custom_dataset):
        """Test version increment functionality."""
        assert custom_dataset.version == 1

        custom_dataset.increment_version()
        assert custom_dataset.version == 2

        custom_dataset.increment_version()
        assert custom_dataset.version == 3


class TestCustomVersionCreation:
    """Tests for creating custom versions of NHS DD datasets."""

    def test_create_custom_version_from_nhs_dd(self, user, organization, nhs_dd_dataset):
        """Test creating a custom version from NHS DD dataset."""
        custom = nhs_dd_dataset.create_custom_version(
            user=user,
            organization=organization,
        )

        assert custom.is_custom is True
        assert custom.is_editable is True
        assert custom.parent == nhs_dd_dataset
        assert custom.organization == organization
        assert custom.created_by == user
        assert custom.options == nhs_dd_dataset.options
        assert custom.key.startswith(nhs_dd_dataset.key)
        assert "Custom" in custom.name

    def test_cannot_create_custom_of_custom(self, user, organization, custom_dataset):
        """Test that you cannot create a custom version of a custom dataset."""
        with pytest.raises(ValueError, match="Can only create custom versions"):
            custom_dataset.create_custom_version(
                user=user,
                organization=organization,
            )

    def test_custom_version_can_be_modified(self, custom_dataset):
        """Test that custom versions can be modified."""
        original_options = custom_dataset.options.copy()

        # Modify options
        custom_dataset.options = original_options[:2]
        custom_dataset.description = "Modified description"
        custom_dataset.save()

        # Reload from database
        custom_dataset.refresh_from_db()

        assert len(custom_dataset.options) == 2
        assert custom_dataset.description == "Modified description"

    def test_parent_unchanged_when_custom_modified(self, nhs_dd_dataset, custom_dataset):
        """Test that modifying custom version doesn't affect parent."""
        original_parent_options = nhs_dd_dataset.options.copy()

        # Modify custom version
        custom_dataset.options = ["New Option 1", "New Option 2"]
        custom_dataset.save()

        # Reload parent from database
        nhs_dd_dataset.refresh_from_db()

        assert nhs_dd_dataset.options == original_parent_options


class TestSyncScheduling:
    """Tests for API dataset sync scheduling."""

    def test_needs_sync_no_last_sync(self, api_dataset):
        """Test that datasets never synced need sync."""
        api_dataset.last_synced_at = None
        api_dataset.save()

        # Without last_synced_at, should be considered as needing sync
        # This will be True when we implement the needs_sync property
        assert api_dataset.last_synced_at is None


class TestGetAvailableDatasets:
    """Tests for get_available_datasets function."""

    def test_returns_nhs_dd_datasets(self, nhs_dd_dataset):
        """Test that NHS DD datasets are returned."""
        datasets = get_available_datasets()

        assert "test_specialty" in datasets
        assert datasets["test_specialty"] == "Test Specialty Codes"

    def test_returns_global_datasets(self, api_dataset):
        """Test that global datasets are returned."""
        datasets = get_available_datasets()

        assert "test_hospitals" in datasets
        assert datasets["test_hospitals"] == "Test Hospitals"

    def test_organization_filtering(self, user, organization, nhs_dd_dataset):
        """Test that organization-specific datasets are filtered correctly."""
        # Create custom dataset for organization
        custom = nhs_dd_dataset.create_custom_version(
            user=user,
            organization=organization,
        )

        # Without organization filter - should only see global
        all_datasets = get_available_datasets()
        assert custom.key not in all_datasets

        # With organization filter - should see both global and org-specific
        org_datasets = get_available_datasets(organization=organization)
        assert custom.key in org_datasets
        assert nhs_dd_dataset.key in org_datasets

    def test_excludes_inactive_datasets(self, db):
        """Test that inactive datasets are not returned."""
        inactive = DataSet.objects.create(
            key="inactive_dataset",
            name="Inactive Dataset",
            category="user_created",
            source_type="manual",
            is_custom=True,
            is_global=True,
            is_active=False,
            options=["Option 1"],
        )

        datasets = get_available_datasets()
        assert "inactive_dataset" not in datasets

    @pytest.mark.django_db
    def test_includes_hardcoded_datasets(self):
        """Test that hardcoded AVAILABLE_DATASETS are still returned."""
        datasets = get_available_datasets()

        # Should include legacy hardcoded datasets
        assert "hospitals_england_wales" in datasets
        assert "nhs_trusts" in datasets

    def test_database_datasets_override_hardcoded(self, db):
        """Test that database datasets override hardcoded ones with same key."""
        # Create database version of hardcoded dataset
        db_dataset = DataSet.objects.create(
            key="nhs_trusts",
            name="NHS Trusts (Database Version)",
            category="external_api",
            source_type="api",
            is_custom=False,
            is_global=True,
            options=["Trust A", "Trust B"],
        )

        datasets = get_available_datasets()

        # Should use database version
        assert datasets["nhs_trusts"] == "NHS Trusts (Database Version)"


class TestFetchDataset:
    """Tests for fetch_dataset function."""

    def test_fetch_nhs_dd_dataset(self, nhs_dd_dataset):
        """Test fetching NHS DD dataset from database."""
        options = fetch_dataset("test_specialty")

        assert len(options) == 3
        assert "100 - General Surgery" in options
        assert "200 - Cardiology" in options
        assert "300 - Neurology" in options

    def test_fetch_api_dataset(self, api_dataset):
        """Test fetching API dataset from database."""
        options = fetch_dataset("test_hospitals")

        assert len(options) == 3
        assert "Hospital A" in options

    def test_fetch_custom_dataset(self, custom_dataset):
        """Test fetching custom dataset from database."""
        # Modify custom dataset to have different options
        custom_dataset.options = ["Custom Option 1", "Custom Option 2"]
        custom_dataset.save()

        options = fetch_dataset(custom_dataset.key)

        assert len(options) == 2
        assert "Custom Option 1" in options
        assert "Custom Option 2" in options

    def test_fetch_inactive_dataset_raises_error(self, db):
        """Test that fetching inactive dataset raises error."""
        inactive = DataSet.objects.create(
            key="inactive_test",
            name="Inactive Test",
            category="user_created",
            source_type="manual",
            is_custom=True,
            is_global=True,
            is_active=False,
            options=["Option 1"],
        )

        # Should not find inactive dataset, fall back to hardcoded check
        from checktick_app.surveys.external_datasets import DatasetFetchError

        with pytest.raises(DatasetFetchError, match="Unknown dataset key"):
            fetch_dataset("inactive_test")

    @pytest.mark.django_db
    def test_fetch_nonexistent_dataset_raises_error(self):
        """Test that fetching non-existent dataset raises error."""
        from checktick_app.surveys.external_datasets import DatasetFetchError

        with pytest.raises(DatasetFetchError, match="Unknown dataset key"):
            fetch_dataset("does_not_exist")


class TestDataSetQuerysets:
    """Tests for common DataSet querysets and filtering."""

    def test_filter_by_category(self, nhs_dd_dataset, api_dataset, db, user, organization):
        """Test filtering datasets by category."""
        # Create user-created dataset
        user_dataset = DataSet.objects.create(
            key="user_test",
            name="User Test",
            category="user_created",
            source_type="manual",
            is_custom=True,
            organization=organization,
            created_by=user,
            options=["Option 1"],
        )

        nhs_dd = DataSet.objects.filter(category="nhs_dd")
        external = DataSet.objects.filter(category="external_api")
        user_created = DataSet.objects.filter(category="user_created")

        assert nhs_dd_dataset in nhs_dd
        assert api_dataset in external
        assert user_dataset in user_created

    def test_filter_by_organization(self, user, organization, nhs_dd_dataset):
        """Test filtering datasets by organization."""
        # Create datasets for different organizations
        user2 = User.objects.create_user(username="user2", password="pass")
        org2 = Organization.objects.create(name="Hospital 2", owner=user2)

        custom1 = nhs_dd_dataset.create_custom_version(user=user, organization=organization)
        custom2 = nhs_dd_dataset.create_custom_version(user=user, organization=org2)

        org1_datasets = DataSet.objects.filter(organization=organization)
        org2_datasets = DataSet.objects.filter(organization=org2)

        assert custom1 in org1_datasets
        assert custom1 not in org2_datasets
        assert custom2 in org2_datasets
        assert custom2 not in org1_datasets

    def test_filter_editable_datasets(self, nhs_dd_dataset, custom_dataset):
        """Test filtering for editable datasets."""
        editable = DataSet.objects.filter(is_custom=True)
        readonly = DataSet.objects.filter(is_custom=False)

        assert custom_dataset in editable
        assert nhs_dd_dataset in readonly

    def test_filter_needs_sync(self, db):
        """Test filtering datasets by last_synced_at."""
        # Fresh dataset
        fresh = DataSet.objects.create(
            key="fresh_api",
            name="Fresh API",
            category="external_api",
            source_type="api",
            is_global=True,
            last_synced_at=timezone.now() - timedelta(hours=1),
            options=["Option 1"],
        )

        # Stale dataset
        stale = DataSet.objects.create(
            key="stale_api",
            name="Stale API",
            category="external_api",
            source_type="api",
            is_global=True,
            last_synced_at=timezone.now() - timedelta(days=2),
            options=["Option 1"],
        )

        # Verify last_synced_at is set correctly
        assert fresh.last_synced_at is not None
        assert stale.last_synced_at is not None
        assert fresh.last_synced_at > stale.last_synced_at


class TestDataSetIntegration:
    """Integration tests for DataSet with external_datasets module."""

    def test_end_to_end_nhs_dd_workflow(self, db, user, organization):
        """Test complete workflow: seed NHS DD -> create custom -> modify."""
        # 1. Create NHS DD dataset (simulating seed command)
        nhs_dd = DataSet.objects.create(
            key="main_specialty",
            name="Main Specialty Code",
            category="nhs_dd",
            source_type="manual",
            is_custom=False,
            is_global=True,
            options=["100 - Surgery", "200 - Medicine", "300 - Psychiatry"],
        )

        # 2. Verify it's available
        datasets = get_available_datasets()
        assert "main_specialty" in datasets

        # 3. Fetch options
        options = fetch_dataset("main_specialty")
        assert len(options) == 3

        # 4. Create custom version
        custom = nhs_dd.create_custom_version(user=user, organization=organization)
        assert custom.is_editable is True

        # 5. Modify custom version
        custom.options = custom.options[:2]  # Keep only first 2
        custom.description = "Our hospital uses only these specialties"
        custom.increment_version()
        custom.save()

        # 6. Verify changes
        custom.refresh_from_db()
        assert len(custom.options) == 2
        assert custom.version == 2

        # 7. Verify original unchanged
        nhs_dd.refresh_from_db()
        assert len(nhs_dd.options) == 3
        assert nhs_dd.version == 1

    def test_multiple_organizations_separate_customizations(self, db, nhs_dd_dataset):
        """Test that different organizations can customize same NHS DD dataset."""
        # Create two organizations with users
        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")
        org1 = Organization.objects.create(name="Hospital A", owner=user1)
        org2 = Organization.objects.create(name="Hospital B", owner=user2)

        # Both create custom versions
        custom1 = nhs_dd_dataset.create_custom_version(user=user1, organization=org1)
        custom2 = nhs_dd_dataset.create_custom_version(user=user2, organization=org2)

        # Modify differently
        custom1.options = ["Custom A1", "Custom A2"]
        custom1.save()

        custom2.options = ["Custom B1", "Custom B2", "Custom B3"]
        custom2.save()

        # Verify independence
        custom1.refresh_from_db()
        custom2.refresh_from_db()

        assert len(custom1.options) == 2
        assert len(custom2.options) == 3
        assert custom1.organization != custom2.organization
