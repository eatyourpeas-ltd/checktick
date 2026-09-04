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

## Static Reference Datasets

Some datasets do not come from an external API — they are static reference
data (ISO 3166 country codes, UK countries). These are defined in
STATIC_DATASETS with metadata and an options builder, and are synced by the
same sync_external_datasets command. There is no network fetch: the command
compares the freshly built options with the stored options and updates only
when they differ, so it is safe to run on every cron cycle.

## ONS Geography Datasets

UK administrative geography datasets (ceremonial counties, local authority
districts, upper tier local authorities, combined authorities, regions of
England) are fetched from the ONS ArcGIS Open Geography Portal. These use
versioned boundary-release service names (e.g. CTYUA_DEC_2023_UK_BUC) — when
ONS publishes a new release, bump the service name and field suffix in
ONS_DATASETS. See docs/self-hosting-datasets.md for the full dataset
catalogue.
"""

import logging
from typing import Any, Callable

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)

# Available dataset keys and display names
# Used for seeding and syncing external API datasets
AVAILABLE_DATASETS = {
    # RCPCH NHS Organisations API
    "hospitals_england_wales": "Hospitals (England & Wales)",
    "nhs_trusts": "NHS Trusts",
    "welsh_lhbs": "Welsh Local Health Boards",
    "london_boroughs": "London Boroughs",
    "nhs_england_regions": "NHS England Regions",
    "paediatric_diabetes_units": "Paediatric Diabetes Units",
    "integrated_care_boards": "Integrated Care Boards (ICBs)",
    # Static reference data (built locally, no network fetch)
    "countries_iso3166": "Countries (ISO 3166-1)",
    "uk_countries": "UK Countries",
    # ONS Open Geography Portal (ArcGIS)
    "uk_counties": "UK Counties (Ceremonial)",
    "local_authorities": "Local Authority Districts",
    "upper_tier_authorities": "Upper Tier Local Authorities",
    "combined_authorities": "Combined Authorities",
    "regions_england": "Regions of England",
}

# ---------------------------------------------------------------------------
# Static reference datasets (no external API — built from local data)
# ---------------------------------------------------------------------------

# GSS codes from the ONS Country register
UK_COUNTRIES_OPTIONS = {
    "E92000001": "England",
    "S92000003": "Scotland",
    "W92000004": "Wales",
    "N92000002": "Northern Ireland",
}


def _build_countries_iso3166_options() -> dict[str, str]:
    """Build {alpha-2 code: country name} from the ISO 3166-1 list.

    Uses the pycountry package (ISO 3166 data maintained by the Debian
    iso-codes project) so no network access is needed at sync time.
    """
    import pycountry  # imported lazily so the app can load without the package

    options = {}
    for country in pycountry.countries:
        # Prefer common_name (e.g. "United Kingdom") over the formal name
        name = getattr(country, "common_name", None) or country.name
        options[country.alpha_2] = name
    return dict(sorted(options.items(), key=lambda item: item[1]))


# Static dataset definitions. Each entry provides the metadata used when
# creating the DataSet record and a callable that builds the options dict.
STATIC_DATASETS: dict[str, dict[str, Any]] = {
    "countries_iso3166": {
        "name": "Countries (ISO 3166-1)",
        "description": (
            "All countries with ISO 3166-1 alpha-2 codes. Keys are the "
            "two-letter ISO codes (e.g. 'GB'), suitable for country of "
            "residence or birth questions. Sourced from the pycountry "
            "package (Debian iso-codes data); no network access required."
        ),
        "reference_url": "https://www.iso.org/iso-3166-country-codes.html",
        "tags": ["administrative", "demographic", "geography"],
        "options_fn": _build_countries_iso3166_options,
    },
    "uk_countries": {
        "name": "UK Countries",
        "description": (
            "The four countries of the United Kingdom, keyed by ONS GSS "
            "codes (e.g. 'E92000001' for England)."
        ),
        "reference_url": "https://www.ons.gov.uk/methodology/geography/ukgeographies",
        "tags": ["administrative", "demographic", "geography", "NHS"],
        "options_fn": lambda: dict(UK_COUNTRIES_OPTIONS),
    },
}


def get_static_dataset_options(dataset_key: str) -> dict[str, str]:
    """Build the options dict for a static reference dataset.

    Args:
        dataset_key: A key in STATIC_DATASETS

    Returns:
        Dictionary of {code: name} pairs

    Raises:
        DatasetFetchError: If the key is unknown or the options builder fails
    """
    definition = STATIC_DATASETS.get(dataset_key)
    if definition is None:
        raise DatasetFetchError(f"Unknown static dataset: {dataset_key}")

    options_fn: Callable[[], dict[str, str]] = definition["options_fn"]
    try:
        options = options_fn()
    except ImportError as e:
        raise DatasetFetchError(
            f"Cannot build '{dataset_key}': missing dependency ({e}). "
            "Install the 'pycountry' package."
        ) from e
    except Exception as e:
        raise DatasetFetchError(
            f"Failed to build options for '{dataset_key}': {e}"
        ) from e

    if not options:
        raise DatasetFetchError(
            f"Options builder for '{dataset_key}' returned no options"
        )
    return options


# ---------------------------------------------------------------------------
# ONS Open Geography Portal datasets (ArcGIS Feature Services)
# ---------------------------------------------------------------------------

# ONS ArcGIS organisation used by the Open Geography Portal
ONS_ARCGIS_BASE_URL = "https://services1.arcgis.com/ESMARspQHYMw9BZ9"

# Service names and attribute fields are pinned to a boundary release (the
# "_DEC_2023_" suffix and the 23-code/nm fields). When ONS publishes a new
# release, bump the service name and field names here. Verify service names
# against https://www.arcgis.com/home (owner: ONS_Geography) if a sync fails.
ONS_DATASETS: dict[str, dict[str, Any]] = {
    "uk_counties": {
        "service": "Counties_and_Unitary_Authorities_December_2023_Boundaries_UK_BUC",
        "code_field": "CTYUA23CD",
        "name_field": "CTYUA23NM",
        "name": "UK Counties (Ceremonial)",
        "description": (
            "Ceremonial counties of the UK (England, Wales, Scotland and "
            "Northern Ireland), keyed by GSS codes. Sourced from the ONS "
            "Open Geography Portal."
        ),
        "reference_url": ("https://www.ons.gov.uk/methodology/geography/ukgeographies"),
        "tags": ["administrative", "geography"],
    },
    "local_authorities": {
        "service": "Local_Authority_Districts_December_2023_Boundaries_UK_BUC",
        "code_field": "LAD23CD",
        "name_field": "LAD23NM",
        "name": "Local Authority Districts",
        "description": (
            "Local authority districts across the UK (English districts and "
            "unitaries, Welsh unitary authorities, Scottish council areas and "
            "Northern Ireland districts), keyed by GSS codes. Sourced from "
            "the ONS Open Geography Portal."
        ),
        "reference_url": ("https://www.ons.gov.uk/methodology/geography/ukgeographies"),
        "tags": ["administrative", "geography"],
    },
    "upper_tier_authorities": {
        "service": "Upper_Tier_Local_Authorities_December_2022_Boundaries_UK_BUC",
        "code_field": "UTLA22CD",
        "name_field": "UTLA22NM",
        "name": "Upper Tier Local Authorities",
        "description": (
            "Upper tier local authorities across the UK (English counties, "
            "unitaries, London and metropolitan boroughs, Scottish council "
            "areas, Welsh unitary authorities and Northern Ireland "
            "districts), keyed by GSS codes. The level used for education, "
            "social care and public health reporting. Sourced from the ONS "
            "Open Geography Portal."
        ),
        "reference_url": ("https://www.ons.gov.uk/methodology/geography/ukgeographies"),
        "tags": ["administrative", "geography"],
    },
    "combined_authorities": {
        "service": "Combined_Authorities_December_2023_Boundaries_EN_BUC",
        "code_field": "CAUTH23CD",
        "name_field": "CAUTH23NM",
        "name": "Combined Authorities",
        "description": (
            "Combined authorities (e.g. Greater Manchester, West Midlands), "
            "keyed by GSS codes. Sourced from the ONS Open Geography Portal."
        ),
        "reference_url": ("https://www.ons.gov.uk/methodology/geography/ukgeographies"),
        "tags": ["administrative", "geography"],
    },
    "regions_england": {
        "service": "Regions_December_2023_Boundaries_EN_BUC",
        "code_field": "RGN23CD",
        "name_field": "RGN23NM",
        "name": "Regions of England",
        "description": (
            "The nine statistical regions of England (ITL1 level), keyed by "
            "GSS codes. Note these differ from the NHS England regions "
            "dataset. Sourced from the ONS Open Geography Portal."
        ),
        "reference_url": ("https://www.ons.gov.uk/methodology/geography/ukgeographies"),
        "tags": ["administrative", "geography", "demographic"],
    },
}

# Optional: Configure custom base URLs for specific datasets
# If not specified, uses EXTERNAL_DATASET_API_URL from settings
DATASET_CONFIGS = {
    **{
        key: {
            "base_url": ONS_ARCGIS_BASE_URL,
            "requires_api_key": False,
        }
        for key in ONS_DATASETS
    }
}


class DatasetFetchError(Exception):
    """Raised when external dataset fetch fails."""

    pass


def get_available_datasets(organization=None, team=None, user=None) -> dict[str, str]:
    """
    Return dictionary of available dataset keys and display names.

    Queries database first for both standard and custom datasets,
    then adds any hardcoded datasets not yet in DB.

    Args:
        organization: Optional organization to include that org's datasets
        team: Optional team to include that team's shared datasets
        user: Optional user to include their personal datasets

    Returns:
        Dict of {key: name} for available datasets
    """
    from .models import DataSet

    datasets = {}

    # Get datasets from database
    # Include: global datasets + org/team-specific + user's personal datasets
    qs = DataSet.objects.filter(is_active=True)

    scope_q = Q(is_global=True)
    if organization:
        scope_q |= Q(organization=organization)
    if team:
        scope_q |= Q(team=team)
    if user is not None and getattr(user, "is_authenticated", False):
        scope_q |= Q(created_by=user, organization__isnull=True, team__isnull=True)
    qs = qs.filter(scope_q)

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
        # ONS Open Geography Portal (ArcGIS Feature Service queries)
        **{
            key: (
                f"/arcgis/rest/services/{cfg['service']}/FeatureServer/0/query"
                "?where=1%3D1&outFields=*&f=json&returnGeometry=false"
            )
            for key, cfg in ONS_DATASETS.items()
        },
    }
    return endpoint_map.get(dataset_key, "")


def _get_base_url_for_dataset(dataset_key: str) -> str:
    """Get the API base URL for a dataset (per-dataset override supported)."""
    config = DATASET_CONFIGS.get(dataset_key, {})
    return config.get("base_url") or _get_api_url()


def _dataset_requires_api_key(dataset_key: str) -> bool:
    """Whether the dataset's API expects the subscription-key header."""
    config = DATASET_CONFIGS.get(dataset_key, {})
    return config.get("requires_api_key", True)


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
    if not isinstance(data, (list, dict)):
        raise DatasetFetchError(
            f"Expected list or dict response for {dataset_key}, got {type(data)}"
        )

    options = {}

    if dataset_key in ONS_DATASETS:
        # Generic ONS ArcGIS Feature Service response:
        # {"features": [{"attributes": {code_field: ..., name_field: ...}}, ...]}
        config = ONS_DATASETS[dataset_key]
        features = data.get("features", []) if isinstance(data, dict) else []
        for feature in features:
            if not isinstance(feature, dict):
                logger.warning("Skipping invalid ONS feature for %s", dataset_key)
                continue
            attrs = feature.get("attributes", {})
            code = attrs.get(config["code_field"])
            name = attrs.get(config["name_field"])
            if code and name:
                options[code] = name
            else:
                logger.warning(
                    "Skipping ONS feature missing fields for %s: %s",
                    dataset_key,
                    attrs,
                )

    elif dataset_key == "hospitals_england_wales":
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

        # SNOMED CT datasets: serve options live from snomed.db, not from the options field
        if dataset.category == "snomed":
            from .snomed_resolver import SnomedUnavailableError, get_options

            try:
                return get_options(dataset)
            except SnomedUnavailableError as exc:
                logger.warning(
                    "SNOMED CT unavailable for dataset '%s': %s", dataset_key, exc
                )
                raise DatasetFetchError(
                    f"SNOMED CT database is not available: {exc}. "
                    "Run 'python manage.py seed_snomed_datasets' after building snomed.db."
                )

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
