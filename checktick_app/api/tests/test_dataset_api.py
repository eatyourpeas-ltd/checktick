"""
Tests for external dataset API endpoints.

These tests verify authentication, permissions, and response formats
for the dataset endpoints using the database-first architecture.

Permission Model (F8, security review August 2026):
- ALL dataset endpoints require authentication (session or API key)
- There is NO anonymous access to any dataset endpoint
- Anonymous survey respondents never call this API: dataset options are
  rendered server-side into the survey page
- Datasets are reference data that authenticated users can access

Architecture:
- Datasets are stored in the DataSet model
- External API datasets are synced via sync_external_datasets command
- These tests use database fixtures, not external API mocks
"""

from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import DataSet

User = get_user_model()
TEST_PASSWORD = "x"


def auth_hdr(user) -> dict:
    """Build an API key auth header for the given user."""
    _, raw_key = UserAPIKey.generate(user=user, name="test")
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}


@pytest.fixture
def authenticated_user(django_user_model):
    """Create and return an authenticated user."""
    return django_user_model.objects.create_user(
        username="testuser", password=TEST_PASSWORD
    )


@pytest.fixture
def api_client():
    """Return a fresh API client."""
    return APIClient()


@pytest.fixture(autouse=True)
def seed_test_datasets(db):
    """Seed external datasets in database for all tests."""
    # Create hospitals dataset
    DataSet.objects.create(
        key="hospitals_england_wales",
        name="Hospitals (England & Wales)",
        description="Test dataset for hospitals",
        category="rcpch",
        source_type="api",
        is_custom=False,
        is_global=True,
        options=[
            "ADDENBROOKE'S HOSPITAL (RGT01)",
            "AIREDALE GENERAL HOSPITAL (RCF22)",
            "ALDER HEY CHILDREN'S HOSPITAL (RBS25)",
        ],
        sync_frequency_hours=24,
    )

    # Create NHS trusts dataset
    DataSet.objects.create(
        key="nhs_trusts",
        name="NHS Trusts",
        description="Test dataset for NHS trusts",
        category="rcpch",
        source_type="api",
        is_custom=False,
        is_global=True,
        options=[
            "AIREDALE NHS FOUNDATION TRUST (RCF)",
            "ALDER HEY CHILDREN'S NHS FOUNDATION TRUST (RBS)",
        ],
        sync_frequency_hours=24,
    )

    # Create Welsh LHBs dataset
    DataSet.objects.create(
        key="welsh_lhbs",
        name="Welsh Local Health Boards",
        description="Test dataset for Welsh LHBs",
        category="rcpch",
        source_type="api",
        is_custom=False,
        is_global=True,
        options=[
            "Swansea Bay University Health Board (7A3)",
            "  CHILD DEVELOPMENT UNIT (7A3LW)",
            "  MORRISTON HOSPITAL (7A3C7)",
            "  NEATH PORT TALBOT HOSPITAL (7A3CJ)",
            "Cardiff and Vale University Health Board (7A4)",
            "  UNIVERSITY HOSPITAL OF WALES (7A4BV)",
        ],
        sync_frequency_hours=24,
    )

    # Create other datasets (minimal) to match AVAILABLE_DATASETS count
    for key, name in [
        ("london_boroughs", "London Boroughs"),
        ("nhs_england_regions", "NHS England Regions"),
        ("paediatric_diabetes_units", "Paediatric Diabetes Units"),
        ("integrated_care_boards", "Integrated Care Boards (ICBs)"),
    ]:
        DataSet.objects.create(
            key=key,
            name=name,
            category="rcpch",
            source_type="api",
            is_custom=False,
            is_global=True,
            options=[f"Test {name} Option 1", f"Test {name} Option 2"],
            sync_frequency_hours=24,
        )

    # Static reference datasets (synced from local data, not an API)
    for key, name in [
        ("countries_iso3166", "Countries (ISO 3166-1)"),
        ("uk_countries", "UK Countries"),
    ]:
        DataSet.objects.create(
            key=key,
            name=name,
            category="reference",
            source_type="manual",
            is_custom=False,
            is_global=True,
            options=[f"Test {name} Option 1", f"Test {name} Option 2"],
        )

    # ONS geography datasets (synced from the ONS ArcGIS API)
    for key, name in [
        ("uk_counties", "UK Counties (Ceremonial)"),
        ("local_authorities", "Local Authority Districts"),
        ("upper_tier_authorities", "Upper Tier Local Authorities"),
        ("combined_authorities", "Combined Authorities"),
        ("regions_england", "Regions of England"),
    ]:
        DataSet.objects.create(
            key=key,
            name=name,
            category="reference",
            source_type="api",
            is_custom=False,
            is_global=True,
            options=[f"Test {name} Option 1", f"Test {name} Option 2"],
            sync_frequency_hours=720,
        )


# ============================================================================
# Authentication Tests
# ============================================================================


@pytest.mark.django_db
def test_list_datasets_requires_authentication(client):
    """Anonymous users cannot list datasets (requires authentication)."""
    resp = client.get("/api/datasets/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_get_dataset_requires_authentication(client):
    """F8 regression: anonymous users cannot retrieve datasets.

    Dataset options for public surveys are rendered server-side, so the
    API has no anonymous callers. Even global datasets require auth.
    """
    resp = client.get("/api/datasets/hospitals_england_wales/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_available_tags_requires_authentication(client):
    """F8 regression: anonymous users cannot access available-tags."""
    resp = client.get("/api/datasets/available-tags/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_get_non_global_dataset_denied_for_anonymous(client, authenticated_user):
    """F8 regression: anonymous retrieval of a non-global dataset is denied."""
    DataSet.objects.create(
        key="private_dataset",
        name="Private Dataset",
        category="user_created",
        source_type="manual",
        is_custom=True,
        is_global=False,
        created_by=authenticated_user,
        options=["Option A", "Option B"],
    )
    resp = client.get("/api/datasets/private_dataset/")
    assert resp.status_code in (401, 403, 404)


@pytest.mark.django_db
def test_list_datasets_authenticated_allowed(client, authenticated_user):
    """Authenticated users can list all available datasets."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/", **hdrs)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.django_db
def test_get_dataset_authenticated_allowed(client, authenticated_user):
    """Authenticated users can get specific dataset."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/hospitals_england_wales/", **hdrs)

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "hospitals_england_wales"


# ============================================================================
# List Datasets Tests
# ============================================================================


@pytest.mark.django_db
def test_list_datasets_returns_all_datasets(client, authenticated_user):
    """List endpoint returns all available datasets."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/", **hdrs)

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 14  # All seeded datasets (7 RCPCH + 2 static + 5 ONS)


@pytest.mark.django_db
def test_list_datasets_response_structure(client, authenticated_user):
    """List datasets returns correctly structured response."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/", **hdrs)

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0

    # Check first dataset structure
    dataset = data[0]
    assert "key" in dataset
    assert "name" in dataset
    assert isinstance(dataset["key"], str)
    assert isinstance(dataset["name"], str)


# ============================================================================
# Get Dataset Tests - Success Cases
# ============================================================================


@pytest.mark.django_db
def test_get_dataset_returns_options_from_database(client, authenticated_user):
    """Get dataset endpoint returns options from database."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/hospitals_england_wales/", **hdrs)

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "hospitals_england_wales"
    assert "options" in data
    assert len(data["options"]) == 3
    # Verify format from database
    assert "ADDENBROOKE'S HOSPITAL (RGT01)" in data["options"]
    assert "AIREDALE GENERAL HOSPITAL (RCF22)" in data["options"]
    assert "ALDER HEY CHILDREN'S HOSPITAL (RBS25)" in data["options"]


@pytest.mark.django_db
def test_get_dataset_handles_hierarchical_options(client, authenticated_user):
    """Get dataset handles hierarchical options (e.g., Welsh LHBs with nested orgs)."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/welsh_lhbs/", **hdrs)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["options"]) == 6
    assert "Swansea Bay University Health Board (7A3)" in data["options"]
    assert "  MORRISTON HOSPITAL (7A3C7)" in data["options"]  # Indented


@pytest.mark.django_db
def test_get_dataset_different_dataset_types(client, authenticated_user):
    """Different dataset types return correct data."""
    hdrs = auth_hdr(authenticated_user)

    # Test NHS trusts
    resp = client.get("/api/datasets/nhs_trusts/", **hdrs)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["options"]) == 2
    assert "AIREDALE NHS FOUNDATION TRUST (RCF)" in data["options"]


@pytest.mark.django_db
def test_get_dataset_response_structure(client, authenticated_user):
    """Get dataset returns correctly structured response."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/nhs_trusts/", **hdrs)

    data = resp.json()
    assert isinstance(data, dict)
    assert "key" in data
    assert "options" in data
    assert data["key"] == "nhs_trusts"
    assert isinstance(data["options"], list)
    # All options should be strings
    for option in data["options"]:
        assert isinstance(option, str)


# ============================================================================
# Get Dataset Tests - Error Cases
# ============================================================================


@pytest.mark.django_db
def test_get_dataset_invalid_key_returns_404(client, authenticated_user):
    """Invalid dataset key returns 404."""
    hdrs = auth_hdr(authenticated_user)
    resp = client.get("/api/datasets/invalid_key_that_does_not_exist/", **hdrs)

    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data


@pytest.mark.django_db
def test_get_dataset_not_found_returns_404(client, authenticated_user):
    """Dataset key not in database returns 404."""
    hdrs = auth_hdr(authenticated_user)

    # Delete all datasets to simulate not found
    DataSet.objects.all().delete()

    resp = client.get("/api/datasets/hospitals_england_wales/", **hdrs)
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data


# ============================================================================
# API Client Tests (force_authenticate)
# ============================================================================


@pytest.mark.django_db
def test_list_datasets_with_force_authenticate(api_client, authenticated_user):
    """Test list datasets using APIClient with force_authenticate."""
    api_client.force_authenticate(authenticated_user)
    resp = api_client.get("/api/datasets/")

    assert resp.status_code == 200
    assert isinstance(resp.data, list)


@pytest.mark.django_db
def test_get_dataset_with_force_authenticate(api_client, authenticated_user):
    """Test get dataset using APIClient with force_authenticate."""
    api_client.force_authenticate(authenticated_user)
    resp = api_client.get("/api/datasets/nhs_trusts/")

    assert resp.status_code == 200
    assert "options" in resp.data
    assert len(resp.data["options"]) == 2


# ============================================================================
# Inactive Dataset Tests
# ============================================================================


@pytest.mark.django_db
def test_inactive_datasets_not_returned(client, authenticated_user):
    """Inactive datasets are not returned in list or get endpoints."""
    # Create an inactive dataset
    DataSet.objects.create(
        key="inactive_dataset",
        name="Inactive Dataset",
        category="rcpch",
        source_type="api",
        is_custom=False,
        is_global=True,
        is_active=False,  # Inactive
        options=["Should not appear"],
    )

    hdrs = auth_hdr(authenticated_user)

    # Should not appear in list
    resp_list = client.get("/api/datasets/", **hdrs)
    dataset_keys = [d["key"] for d in resp_list.json()]
    assert "inactive_dataset" not in dataset_keys

    # Should return 404 when trying to get directly (inactive = not found)
    resp_get = client.get("/api/datasets/inactive_dataset/", **hdrs)
    assert resp_get.status_code == 404
