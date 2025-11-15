"""
External dataset service for fetching prefilled dropdown options.

This module provides a service layer for fetching datasets from external APIs
(e.g., hospitals, NHS trusts) with caching to minimize external calls.

## Adding New Datasets

To add a new dataset:

1. Add entry to AVAILABLE_DATASETS with key and display name
2. Add endpoint mapping in _get_endpoint_for_dataset()
3. Add transformer function in _transform_response_to_options()
4. Optionally configure custom base URL via DATASET_CONFIGS if different from default

See docs/adding-external-datasets.md for detailed examples.
"""

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
import requests

logger = logging.getLogger(__name__)

# Cache timeout: 24 hours for relatively stable datasets like hospital lists
DATASET_CACHE_TIMEOUT = 60 * 60 * 24

# Available dataset keys and display names
AVAILABLE_DATASETS = {
    "hospitals_england_wales": "Hospitals (England & Wales)",
    "nhs_trusts": "NHS Trusts",
    "welsh_lhbs": "Welsh Local Health Boards",
    "london_boroughs": "London Boroughs",
    "nhs_england_regions": "NHS England Regions",
    "paediatric_diabetes_units": "Paediatric Diabetes Units",
    "integrated_care_boards": "Integrated Care Boards (ICBs)",
}

# Optional: Configure custom base URLs for specific datasets
# If not specified, uses EXTERNAL_DATASET_API_URL from settings
DATASET_CONFIGS = {
    # Example for datasets from different APIs:
    # "custom_dataset": {
    #     "base_url": "https://different-api.example.com",
    #     "endpoint": "/custom/endpoint/",
    #     "api_key_setting": "CUSTOM_API_KEY",  # Optional
    # }
}


class DatasetFetchError(Exception):
    """Raised when external dataset fetch fails."""

    pass


def get_available_datasets(organization=None) -> dict[str, str]:
    """
    Return dictionary of available dataset keys and display names.

    Queries database first for both standard and custom datasets,
    then adds any hardcoded datasets not yet in DB.

    Args:
        organization: Optional organization to filter custom datasets

    Returns:
        Dict of {key: name} for available datasets
    """
    from .models import DataSet

    datasets = {}

    # Get datasets from database
    # Include: global datasets + org-specific datasets (if org provided)
    qs = DataSet.objects.filter(is_active=True)

    if organization:
        # Global datasets OR org-specific datasets
        qs = qs.filter(
            Q(is_global=True) | Q(organization=organization)
        )
    else:
        # Only global datasets if no org context
        qs = qs.filter(is_global=True)

    for dataset in qs:
        datasets[dataset.key] = dataset.name

    # Add hardcoded datasets that aren't in DB yet (backward compatibility)
    for key, name in AVAILABLE_DATASETS.items():
        if key not in datasets:
            datasets[key] = name

    return datasets


def _get_api_url() -> str:
    """Get the external dataset API base URL from settings."""
    return getattr(
        settings,
        "EXTERNAL_DATASET_API_URL",
        "https://api.rcpch.ac.uk",
    )


def _get_api_key() -> str:
    """Get the external dataset API key from settings."""
    return getattr(settings, "EXTERNAL_DATASET_API_KEY", "")


def _get_endpoint_for_dataset(dataset_key: str) -> str:
    """
    Map dataset keys to API endpoints.

    Args:
        dataset_key: The dataset key

    Returns:
        API endpoint path (with trailing slash)
    """
    endpoint_map = {
        # RCPCH NHS Organisations API
        "hospitals_england_wales": "/organisations/limited/",
        "nhs_trusts": "/trusts/",
        "welsh_lhbs": "/local_health_boards/",
        "london_boroughs": "/london_boroughs/",
        "nhs_england_regions": "/nhs_england_regions/",
        "paediatric_diabetes_units": "/paediatric_diabetes_units/",
        "integrated_care_boards": "/integrated_care_boards/",
    }
    return endpoint_map.get(dataset_key, "")


def _transform_response_to_options(dataset_key: str, data: Any) -> list[str]:
    """
    Transform API response to list of option strings.

    Each dataset type has its own transformation logic based on the API response structure.

    Args:
        dataset_key: The dataset key
        data: The raw API response data (usually a list of dicts)

    Returns:
        List of formatted option strings for dropdown display

    Raises:
        DatasetFetchError: If data format is invalid
    """
    if not isinstance(data, list):
        raise DatasetFetchError(
            f"Expected list response for {dataset_key}, got {type(data)}"
        )

    options = []

    if dataset_key == "hospitals_england_wales":
        # Format: {"ods_code": "RGT01", "name": "ADDENBROOKE'S HOSPITAL"}
        for item in data:
            if (
                not isinstance(item, dict)
                or "name" not in item
                or "ods_code" not in item
            ):
                logger.warning(f"Skipping invalid hospital item: {item}")
                continue
            options.append(f"{item['name']} ({item['ods_code']})")

    elif dataset_key == "nhs_trusts":
        # Format: {"ods_code": "RCF", "name": "AIREDALE NHS FOUNDATION TRUST", ...}
        for item in data:
            if (
                not isinstance(item, dict)
                or "name" not in item
                or "ods_code" not in item
            ):
                logger.warning(f"Skipping invalid trust item: {item}")
                continue
            options.append(f"{item['name']} ({item['ods_code']})")

    elif dataset_key == "welsh_lhbs":
        # Format: {"ods_code": "7A3", "name": "Swansea Bay...", "organisations": [...]}
        # Flatten to include both LHB and its organisations
        for lhb in data:
            if not isinstance(lhb, dict) or "name" not in lhb or "ods_code" not in lhb:
                logger.warning(f"Skipping invalid LHB item: {lhb}")
                continue

            # Add the LHB itself
            options.append(f"{lhb['name']} ({lhb['ods_code']})")

            # Add organisations within the LHB (indented for hierarchy)
            if "organisations" in lhb and isinstance(lhb["organisations"], list):
                for org in lhb["organisations"]:
                    if isinstance(org, dict) and "name" in org and "ods_code" in org:
                        options.append(f"  {org['name']} ({org['ods_code']})")

    elif dataset_key == "london_boroughs":
        # Format: {"name": "Westminster", "gss_code": "E09000033", ...}
        for item in data:
            if (
                not isinstance(item, dict)
                or "name" not in item
                or "gss_code" not in item
            ):
                logger.warning(f"Skipping invalid London borough item: {item}")
                continue
            options.append(f"{item['name']} ({item['gss_code']})")

    elif dataset_key == "nhs_england_regions":
        # Format: {"region_code": "Y58", "name": "South West", ...}
        for item in data:
            if (
                not isinstance(item, dict)
                or "name" not in item
                or "region_code" not in item
            ):
                logger.warning(f"Skipping invalid NHS England region item: {item}")
                continue
            options.append(f"{item['name']} ({item['region_code']})")

    elif dataset_key == "paediatric_diabetes_units":
        # Format: {"pz_code": "PZ215", "primary_organisation": {"name": "...", "ods_code": "..."}, ...}
        for item in data:
            if not isinstance(item, dict) or "pz_code" not in item:
                logger.warning(
                    f"Skipping invalid paediatric diabetes unit item: {item}"
                )
                continue

            # Try to get name from primary_organisation, fall back to parent
            name = None
            code = item["pz_code"]

            if "primary_organisation" in item and isinstance(
                item["primary_organisation"], dict
            ):
                primary = item["primary_organisation"]
                if "name" in primary:
                    name = primary["name"]
                    if "ods_code" in primary:
                        code = primary["ods_code"]
            elif "parent" in item and isinstance(item["parent"], dict):
                parent = item["parent"]
                if "name" in parent:
                    name = parent["name"]
                    if "ods_code" in parent:
                        code = parent["ods_code"]

            if name:
                options.append(f"{name} ({code})")
            else:
                # Fallback to just the PZ code if no name found
                options.append(f"PDU {code}")

    elif dataset_key == "integrated_care_boards":
        # Format: {"ods_code": "QOX", "name": "NHS Bath and North East Somerset...", ...}
        for item in data:
            if (
                not isinstance(item, dict)
                or "name" not in item
                or "ods_code" not in item
            ):
                logger.warning(f"Skipping invalid ICB item: {item}")
                continue
            options.append(f"{item['name']} ({item['ods_code']})")

    if not options:
        raise DatasetFetchError(f"No valid options found in response for {dataset_key}")

    return options


def fetch_dataset(dataset_key: str) -> list[str]:
    """
    Fetch dataset options from database or external API with caching.

    Priority order:
    1. Database (for custom and stored datasets)
    2. Django cache (for external API datasets)
    3. External API (if not cached)

    Args:
        dataset_key: The key identifying which dataset to fetch

    Returns:
        List of option strings

    Raises:
        DatasetFetchError: If dataset key is invalid or fetch fails
    """
    from .models import DataSet

    # Try database first
    try:
        dataset = DataSet.objects.get(key=dataset_key, is_active=True)

        # If it's an API dataset that needs syncing, trigger async sync (don't wait)
        if dataset.source_type == "api" and dataset.needs_sync:
            # TODO: Trigger async sync task here when Celery is set up
            # sync_dataset.delay(dataset.id)
            logger.info(f"Dataset {dataset_key} needs sync (will implement async sync)")

        return dataset.options

    except DataSet.DoesNotExist:
        # Fall back to legacy behavior for datasets not yet in DB
        pass

    # Legacy path for hardcoded datasets
    if dataset_key not in AVAILABLE_DATASETS:
        raise DatasetFetchError(f"Unknown dataset key: {dataset_key}")

    # Check cache first
    cache_key = f"external_dataset:{dataset_key}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Returning cached dataset: {dataset_key}")
        return cached_data

    # Fetch from external API
    try:
        api_url = _get_api_url()
        api_key = _get_api_key()
        endpoint = _get_endpoint_for_dataset(dataset_key)

        if not endpoint:
            raise DatasetFetchError(
                f"No endpoint configured for dataset: {dataset_key}"
            )

        url = f"{api_url}{endpoint}"
        logger.info(f"Fetching dataset from external API: {dataset_key} from {url}")

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Transform API response to option strings
        options = _transform_response_to_options(dataset_key, data)

        # Cache the result
        cache.set(cache_key, options, DATASET_CACHE_TIMEOUT)
        logger.info(f"Cached {len(options)} options for dataset: {dataset_key}")

        return options

    except requests.RequestException as e:
        logger.error(f"Failed to fetch dataset {dataset_key}: {e}")
        raise DatasetFetchError(f"Failed to fetch dataset: {str(e)}") from e
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Failed to parse dataset {dataset_key}: {e}")
        raise DatasetFetchError(f"Failed to parse dataset: {str(e)}") from e


def clear_dataset_cache(dataset_key: str | None = None) -> None:
    """
    Clear cached dataset(s).

    Args:
        dataset_key: If provided, clear only this dataset. Otherwise clear all.
    """
    if dataset_key:
        cache_key = f"external_dataset:{dataset_key}"
        cache.delete(cache_key)
        logger.info(f"Cleared cache for dataset: {dataset_key}")
    else:
        for key in AVAILABLE_DATASETS:
            cache_key = f"external_dataset:{key}"
            cache.delete(cache_key)
        logger.info("Cleared all dataset caches")
