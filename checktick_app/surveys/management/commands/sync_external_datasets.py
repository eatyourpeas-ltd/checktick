"""
Management command to sync external API datasets into the database.

This command fetches datasets from external APIs (e.g., RCPCH NHS Organisations API)
and stores them in the DataSet model. This allows:
- Faster access (no API call on every request)
- Offline availability
- Visibility in the web UI
- Ability to create custom versions

The sync process:
1. Fetches data from external API
2. Transforms it to option strings
3. Updates or creates DataSet records
4. Updates last_synced_at timestamp

Usage:
    python manage.py sync_external_datasets
    python manage.py sync_external_datasets --dataset hospitals_england_wales
    python manage.py sync_external_datasets --force  # Sync even if not due

Static reference datasets (countries_iso3166, uk_countries, uk_counties) are
synced by the same command: their options are built from local data (e.g.
pycountry for ISO 3166) and records are updated only when options change.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import requests

from checktick_app.surveys.external_datasets import (
    AVAILABLE_DATASETS,
    ONS_DATASETS,
    STATIC_DATASETS,
    DatasetFetchError,
    _dataset_requires_api_key,
    _get_api_key,
    _get_base_url_for_dataset,
    _get_endpoint_for_dataset,
    _transform_response_to_options,
    get_static_dataset_options,
)
from checktick_app.surveys.models import DataSet

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync external API datasets into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            type=str,
            help="Sync only this specific dataset key (e.g., hospitals_england_wales)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force sync even if not due based on sync_frequency_hours",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be synced without actually syncing",
        )

    def handle(self, *args, **options):
        dataset_key = options.get("dataset")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Determine which datasets to sync
        if dataset_key:
            if dataset_key not in AVAILABLE_DATASETS:
                raise CommandError(f"Unknown dataset key: {dataset_key}")
            datasets_to_sync = {dataset_key: AVAILABLE_DATASETS[dataset_key]}
        else:
            datasets_to_sync = AVAILABLE_DATASETS

        self.stdout.write(f"Found {len(datasets_to_sync)} external datasets to process")

        synced_count = 0
        skipped_count = 0
        error_count = 0

        for key, name in datasets_to_sync.items():
            try:
                if key in STATIC_DATASETS:
                    self._sync_static_dataset(key, name, dry_run=dry_run, force=force)
                    synced_count += 1
                    continue

                # Check if dataset exists in DB
                dataset_obj = DataSet.objects.filter(key=key).first()

                # Check if sync is needed
                if dataset_obj and not force and not dataset_obj.needs_sync:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⏭️  Skipping '{name}' - not due for sync "
                            f"(last synced: {dataset_obj.last_synced_at})"
                        )
                    )
                    skipped_count += 1
                    continue

                self.stdout.write(f"🔄 Syncing '{name}' ({key})...")

                # Fetch from external API
                options = self._fetch_from_api(key)

                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   Would sync {len(options)} options for '{name}'"
                        )
                    )
                    synced_count += 1
                    continue

                # Update or create dataset
                if dataset_obj:
                    # Update existing; also heal sharing flags in case the
                    # record was created by an older version of this command
                    # without is_global set (a non-global dataset with no
                    # owner is invisible to the API).
                    old_count = len(dataset_obj.options)
                    dataset_obj.options = options
                    dataset_obj.is_global = True
                    dataset_obj.is_custom = False
                    dataset_obj.last_synced_at = timezone.now()
                    dataset_obj.version += 1
                    dataset_obj.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Updated '{name}': {old_count} → {len(options)} options "
                            f"(version {dataset_obj.version})"
                        )
                    )
                else:
                    # Create new with source-appropriate metadata
                    dataset_obj = DataSet.objects.create(
                        key=key,
                        name=name,
                        is_custom=False,
                        is_global=True,
                        **self._get_creation_metadata(key),
                        options=options,
                        external_api_endpoint=_get_endpoint_for_dataset(key),
                        external_api_url=_get_base_url_for_dataset(key),
                        last_synced_at=timezone.now(),
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Created '{name}': {len(options)} options"
                        )
                    )

                synced_count += 1

            except DatasetFetchError as e:
                self.stderr.write(self.style.ERROR(f"❌ Failed to sync '{name}': {e}"))
                error_count += 1
                logger.error(f"Failed to sync dataset {key}: {e}")

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"❌ Unexpected error syncing '{name}': {e}")
                )
                error_count += 1
                logger.exception(f"Unexpected error syncing dataset {key}")

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY RUN COMPLETE"))
        else:
            self.stdout.write(self.style.SUCCESS("SYNC COMPLETE"))

        self.stdout.write(f"  Synced: {synced_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"  Errors: {error_count}"))
        else:
            self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write("=" * 60)

        if error_count > 0:
            raise CommandError(f"{error_count} dataset(s) failed to sync")

    def _sync_static_dataset(
        self, dataset_key: str, name: str, dry_run: bool, force: bool
    ) -> None:
        """Sync a static reference dataset (no network fetch).

        Options are built from local data and compared against the stored
        options; the record is only updated when they differ (or --force).
        """
        definition = STATIC_DATASETS[dataset_key]
        options = get_static_dataset_options(dataset_key)
        dataset_obj = DataSet.objects.filter(key=dataset_key).first()

        if dry_run:
            action = "update" if dataset_obj else "create"
            self.stdout.write(
                self.style.SUCCESS(
                    f"   Would {action} '{name}' with {len(options)} options"
                )
            )
            return

        if dataset_obj:
            if not force and dataset_obj.options == options:
                self.stdout.write(
                    self.style.WARNING(f"⏭️  Skipping '{name}' - options unchanged")
                )
                return

            old_count = len(dataset_obj.options)
            dataset_obj.options = options
            dataset_obj.is_global = True
            dataset_obj.is_custom = False
            dataset_obj.last_synced_at = timezone.now()
            dataset_obj.version += 1
            dataset_obj.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Updated '{name}': {old_count} → {len(options)} options "
                    f"(version {dataset_obj.version})"
                )
            )
        else:
            DataSet.objects.create(
                key=dataset_key,
                name=definition["name"],
                description=definition["description"],
                category="reference",
                source_type="manual",
                reference_url=definition["reference_url"],
                is_custom=False,
                is_global=True,
                options=options,
                tags=definition["tags"],
                last_synced_at=timezone.now(),
            )
            self.stdout.write(
                self.style.SUCCESS(f"✅ Created '{name}': {len(options)} options")
            )

    def _get_creation_metadata(self, dataset_key: str) -> dict:
        """Creation kwargs (description, category, tags, sync frequency) for a
        new API-sourced dataset, based on which source it comes from."""
        if dataset_key in ONS_DATASETS:
            config = ONS_DATASETS[dataset_key]
            return {
                "description": config["description"],
                "category": "reference",
                "source_type": "api",
                "reference_url": config["reference_url"],
                "tags": config["tags"],
                "sync_frequency_hours": 720,  # monthly
            }
        return {
            "description": "External dataset from RCPCH NHS Organisations API",
            "category": "rcpch",
            "source_type": "api",
            "sync_frequency_hours": 24,
        }

    def _fetch_from_api(self, dataset_key: str) -> dict[str, str]:
        """
        Fetch dataset from external API and transform to option dictionary.

        Args:
            dataset_key: The dataset key to fetch

        Returns:
            Dictionary of {code: name} option pairs

        Raises:
            DatasetFetchError: If fetch or transformation fails
        """
        api_url = _get_base_url_for_dataset(dataset_key)
        endpoint = _get_endpoint_for_dataset(dataset_key)

        if not endpoint:
            raise DatasetFetchError(
                f"No endpoint configured for dataset: {dataset_key}"
            )

        url = f"{api_url}{endpoint}"
        logger.info(f"Fetching dataset from: {url}")

        headers = {}
        if _dataset_requires_api_key(dataset_key):
            api_key = _get_api_key()
            if api_key:
                headers["Ocp-Apim-Subscription-Key"] = f"{api_key}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Transform API response to option strings
            options = _transform_response_to_options(dataset_key, data)

            return options

        except requests.RequestException as e:
            raise DatasetFetchError(f"API request failed: {str(e)}") from e
        except (KeyError, ValueError, TypeError) as e:
            raise DatasetFetchError(f"Failed to parse response: {str(e)}") from e
