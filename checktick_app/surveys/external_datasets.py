"""
External dataset service for fetching prefilled dropdown options.

This module provides a service layer for fetching datasets stored in the database.
External API datasets (e.g., hospitals, NHS trusts) are synced into the DataSet model
via the sync_external_datasets management command.

## Architecture

Datasets are stored in the DataSet model and synced periodically:
- fetch_dataset() reads from database
- sync_external_datasets command creates and updates from external APIs
- No more session/cache storage - database is the single source of truth

## Setup

1. Run sync command to create datasets and populate data:
   python manage.py sync_external_datasets

2. Schedule periodic sync (e.g., daily cron):
   0 2 * * * cd /app && python manage.py sync_external_datasets

## Adding New Datasets

To add a new external API dataset:

1. Add entry to AVAILABLE_DATASETS with key and display name
2. Add endpoint mapping in _get_endpoint_for_dataset()
3. Add transformer function in _transform_response_to_options()
4. Run sync_external_datasets to create record and populate data

See docs/prefilled-datasets-setup.md for detailed examples.
"""

import logging
from typing import Any

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)

# Available dataset keys and display names
# Used for seeding and syncing external API datasets
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
        qs = qs.filter(Q(is_global=True) | Q(organization=organization))
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


def _transform_response_to_options(dataset_key: str, data: Any) -> dict[str, str]:
    """
    Transform API response to dictionary of code: name pairs.

    Each dataset type has its own transformation logic based on the API response structure.
    Returns a dictionary with codes as keys and names as values for two-column display.

    Args:
        dataset_key: The dataset key
        data: The raw API response data (usually a list of dicts)

    Returns:
        Dictionary of {code: name} for dropdown display with two-column layout

    Raises:
        DatasetFetchError: If data format is invalid
    """
    if not isinstance(data, list):
        raise DatasetFetchError(
            f"Expected list response for {dataset_key}, got {type(data)}"
        )

    options = {}

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
            options[item["ods_code"]] = item["name"]

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
            options[item["ods_code"]] = item["name"]

    elif dataset_key == "welsh_lhbs":
        # Format: {"ods_code": "7A3", "name": "Swansea Bay...", "organisations": [...]}
        # Flatten to include both LHB and its organisations
        for lhb in data:
            if not isinstance(lhb, dict) or "name" not in lhb or "ods_code" not in lhb:
                logger.warning(f"Skipping invalid LHB item: {lhb}")
                continue

            # Add the LHB itself
            options[lhb["ods_code"]] = lhb["name"]

            # Add organisations within the LHB
            if "organisations" in lhb and isinstance(lhb["organisations"], list):
                for org in lhb["organisations"]:
                    if isinstance(org, dict) and "name" in org and "ods_code" in org:
                        # Prefix nested org names with "  " to show hierarchy
                        options[org["ods_code"]] = f"  {org['name']}"

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
            options[item["gss_code"]] = item["name"]

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
            options[item["region_code"]] = item["name"]

    elif dataset_key == "paediatric_diabetes_units":
        # Format: {"pz_code": "PZ215", "primary_organisation": {"name": "...", "ods_code": "..."}, ...}
        for item in data:
            if not isinstance(item, dict) or "pz_code" not in item:
                logger.warning(
                    f"Skipping invalid paediatric diabetes unit item: {item}"
                )
                continue

            # Try to get name and code from primary_organisation, fall back to parent
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
                options[code] = name
            else:
                # Fallback to just the PZ code if no name found
                options[code] = f"PDU {code}"

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
            options[item["ods_code"]] = item["name"]

    if not options:
        raise DatasetFetchError(f"No valid options found in response for {dataset_key}")

    return options


def fetch_dataset(dataset_key: str) -> dict[str, str]:
    """
    Fetch dataset options from database.

    For API datasets that need syncing, logs a warning but returns current data.
    Use the sync_external_datasets management command to update API datasets.

    Priority order:
    1. Database (primary source for all datasets)
    2. Legacy cache fallback (deprecated, for backward compatibility only)

    Args:
        dataset_key: The key identifying which dataset to fetch

    Returns:
        Dictionary of {code: name} pairs (all datasets use this format)

    Raises:
        DatasetFetchError: If dataset key is invalid or not found
    """
    from .models import DataSet

    # Try database first (primary source)
    try:
        dataset = DataSet.objects.get(key=dataset_key, is_active=True)

        # If it's an API dataset that needs syncing, log a warning
        if dataset.source_type == "api" and dataset.needs_sync:
            logger.warning(
                f"Dataset '{dataset_key}' needs sync. "
                f"Run 'python manage.py sync_external_datasets --dataset {dataset_key}' to update."
            )

        # Return current options (even if sync is needed)
        return dataset.options

    except DataSet.DoesNotExist:
        # Dataset not in database
        logger.error(f"Dataset '{dataset_key}' not found in database")
        raise DatasetFetchError(
            f"Dataset '{dataset_key}' not found. "
            f"Run 'python manage.py sync_external_datasets' to initialize external datasets."
        )


def clear_dataset_cache(dataset_key: str | None = None) -> None:
    """
    Clear cached dataset(s) - DEPRECATED.

    Datasets are now stored in the database, not cache.
    Use sync_external_datasets management command to refresh data.

    Args:
        dataset_key: Ignored (for backward compatibility)
    """
    logger.warning(
        "clear_dataset_cache() is deprecated. "
        "Use 'python manage.py sync_external_datasets' to refresh datasets."
    )
