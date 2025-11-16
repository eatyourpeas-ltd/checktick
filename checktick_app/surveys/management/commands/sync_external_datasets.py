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
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import requests

from checktick_app.surveys.external_datasets import (
    AVAILABLE_DATASETS,
    DatasetFetchError,
    _get_api_key,
    _get_api_url,
    _get_endpoint_for_dataset,
    _transform_response_to_options,
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
                    # Update existing
                    old_count = len(dataset_obj.options)
                    dataset_obj.options = options
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
                    # Create new
                    dataset_obj = DataSet.objects.create(
                        key=key,
                        name=name,
                        description="External dataset from RCPCH NHS Organisations API",
                        category="rcpch",
                        source_type="api",
                        is_custom=False,
                        is_global=True,
                        options=options,
                        external_api_endpoint=_get_endpoint_for_dataset(key),
                        external_api_url=_get_api_url(),
                        sync_frequency_hours=24,
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
        api_url = _get_api_url()
        api_key = _get_api_key()
        endpoint = _get_endpoint_for_dataset(dataset_key)

        if not endpoint:
            raise DatasetFetchError(
                f"No endpoint configured for dataset: {dataset_key}"
            )

        url = f"{api_url}{endpoint}"
        logger.info(f"Fetching dataset from: {url}")

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

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
