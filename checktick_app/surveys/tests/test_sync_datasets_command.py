"""
Tests for sync_external_datasets management command.

Tests successful sync, API errors, dataset creation/updates, and idempotency.
"""

from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from checktick_app.surveys.models import DataSet

# Mock API responses for each dataset type
MOCK_RESPONSES = {
    "hospitals_england_wales": [
        {"name": "ADDENBROOKE'S HOSPITAL", "ods_code": "RGT01"},
        {"name": "ST THOMAS' HOSPITAL", "ods_code": "RJ7"},
    ],
    "nhs_trusts": [
        {"name": "AIREDALE NHS FOUNDATION TRUST", "ods_code": "RCF"},
        {"name": "BARTS HEALTH NHS TRUST", "ods_code": "R1H"},
    ],
    "welsh_lhbs": [
        {
            "name": "Swansea Bay University Health Board",
            "ods_code": "7A3",
            "organisations": [
                {"name": "Morriston Hospital", "ods_code": "RW6C1"},
            ],
        }
    ],
    "london_boroughs": [
        {"name": "Westminster", "gss_code": "E09000033"},
        {"name": "Camden", "gss_code": "E09000007"},
    ],
    "nhs_england_regions": [
        {"region_code": "Y58", "name": "South West"},
        {"region_code": "Y56", "name": "London"},
    ],
    "paediatric_diabetes_units": [
        {
            "pz_code": "PZ215",
            "primary_organisation": {
                "name": "Great Ormond Street Hospital",
                "ods_code": "RP401",
            },
        }
    ],
    "integrated_care_boards": [
        {"name": "NHS Norfolk and Waveney ICB", "ods_code": "QMM"},
        {"name": "NHS Frimley ICB", "ods_code": "QNQ"},
    ],
}


class SyncExternalDatasetsCommandTests(TestCase):
    """Test the sync_external_datasets management command."""

    def setUp(self):
        """Create test data."""
        # Create a test dataset that exists but hasn't been synced
        self.existing_dataset = DataSet.objects.create(
            key="hospitals_england_wales",
            name="Hospitals (England & Wales)",
            description="Test dataset",
            category="rcpch",
            source_type="api",
            is_custom=False,
            is_global=True,
            options=[],  # Empty, needs sync
            sync_frequency_hours=24,
            last_synced_at=None,
        )

    def _mock_api_response(self, dataset_key):
        """Helper to create mock API response for a specific dataset."""
        mock_response = Mock()
        mock_response.json.return_value = MOCK_RESPONSES.get(dataset_key, [])
        mock_response.raise_for_status = Mock()
        return mock_response

    def _patch_requests_get(self, mock_get):
        """Configure mock to return appropriate response based on URL."""

        def side_effect(url, *args, **kwargs):
            # Determine dataset type from URL
            if "local_health_boards" in url.lower():
                return self._mock_api_response("welsh_lhbs")
            elif "trusts" in url.lower():
                return self._mock_api_response("nhs_trusts")
            elif "london" in url.lower() or "boroughs" in url.lower():
                return self._mock_api_response("london_boroughs")
            elif "nhs_england_regions" in url.lower() or "regions" in url.lower():
                return self._mock_api_response("nhs_england_regions")
            elif (
                "paediatric_diabetes_units" in url.lower() or "pz_codes" in url.lower()
            ):
                return self._mock_api_response("paediatric_diabetes_units")
            elif "integrated_care_boards" in url.lower() or "icb" in url.lower():
                return self._mock_api_response("integrated_care_boards")
            else:
                # Default to hospitals
                return self._mock_api_response("hospitals_england_wales")

        mock_get.side_effect = side_effect

    def test_command_runs_successfully(self):
        """Test that the command runs without errors when API succeeds."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            out = StringIO()
            call_command("sync_external_datasets", stdout=out)

            output = out.getvalue()
            self.assertIn("SYNC COMPLETE", output)
            self.assertIn("Synced: 7", output)  # All 7 available datasets

    def test_dry_run_mode_makes_no_changes(self):
        """Test that dry-run mode doesn't actually sync data."""
        initial_options = self.existing_dataset.options.copy()

        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            out = StringIO()
            call_command("sync_external_datasets", "--dry-run", stdout=out)

            output = out.getvalue()
            self.assertIn("DRY RUN", output)
            self.assertIn("Would sync", output)

            # Verify no changes were made
            self.existing_dataset.refresh_from_db()
            self.assertEqual(self.existing_dataset.options, initial_options)
            self.assertIsNone(self.existing_dataset.last_synced_at)

    def test_creates_new_dataset_if_not_exists(self):
        """Test that new datasets are created if they don't exist."""
        # Delete the existing dataset
        DataSet.objects.all().delete()

        self.assertEqual(DataSet.objects.count(), 0)

        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            call_command("sync_external_datasets", stdout=StringIO())

            # Should have created 7 datasets (all in AVAILABLE_DATASETS)
            self.assertEqual(DataSet.objects.count(), 7)

            # Check one was created correctly
            dataset = DataSet.objects.get(key="hospitals_england_wales")
            self.assertEqual(dataset.category, "rcpch")
            self.assertEqual(dataset.source_type, "api")
            self.assertTrue(dataset.is_global)
            self.assertFalse(dataset.is_custom)
            self.assertIsNotNone(dataset.last_synced_at)
            # Options should now be a dictionary with 2 entries
            self.assertIsInstance(dataset.options, dict)
            self.assertEqual(len(dataset.options), 2)
            self.assertIn("RGT01", dataset.options)
            self.assertEqual(dataset.options["RGT01"], "ADDENBROOKE'S HOSPITAL")

    def test_updates_existing_dataset(self):
        """Test that existing datasets are updated with new data."""
        # Set initial data
        self.existing_dataset.options = {"OLD01": "Old Hospital"}
        self.existing_dataset.version = 1
        self.existing_dataset.save()

        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [
                {"name": "New Hospital A", "ods_code": "ABC123"},
                {"name": "New Hospital B", "ods_code": "DEF456"},
            ]
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                stdout=StringIO(),
            )

            self.existing_dataset.refresh_from_db()
            # Options should now be a dictionary
            self.assertIsInstance(self.existing_dataset.options, dict)
            self.assertEqual(len(self.existing_dataset.options), 2)
            self.assertIn("ABC123", self.existing_dataset.options)
            self.assertEqual(self.existing_dataset.options["ABC123"], "New Hospital A")
            self.assertIn("DEF456", self.existing_dataset.options)
            self.assertEqual(self.existing_dataset.options["DEF456"], "New Hospital B")
            self.assertEqual(self.existing_dataset.version, 2)  # Version incremented
            self.assertIsNotNone(self.existing_dataset.last_synced_at)

    def test_updates_last_synced_timestamp(self):
        """Test that last_synced_at is updated on successful sync."""
        self.assertIsNone(self.existing_dataset.last_synced_at)

        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            before = timezone.now()
            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                stdout=StringIO(),
            )
            after = timezone.now()

            self.existing_dataset.refresh_from_db()
            self.assertIsNotNone(self.existing_dataset.last_synced_at)
            self.assertGreaterEqual(self.existing_dataset.last_synced_at, before)
            self.assertLessEqual(self.existing_dataset.last_synced_at, after)

    def test_skips_recently_synced_datasets(self):
        """Test that datasets recently synced are skipped unless --force."""
        # Mark existing dataset as recently synced
        self.existing_dataset.last_synced_at = timezone.now()
        self.existing_dataset.save()

        # Create all other datasets and mark them as recently synced too
        for key in [
            "nhs_trusts",
            "welsh_lhbs",
            "london_boroughs",
            "nhs_england_regions",
            "paediatric_diabetes_units",
            "integrated_care_boards",
        ]:
            DataSet.objects.create(
                key=key,
                name=key.replace("_", " ").title(),
                category="rcpch",
                source_type="api",
                is_global=True,
                is_custom=False,
                sync_frequency_hours=24,
                last_synced_at=timezone.now(),
                options=[],
            )

        out = StringIO()
        call_command("sync_external_datasets", stdout=out)

        output = out.getvalue()
        self.assertIn("Skipping", output)
        self.assertIn("not due for sync", output)
        self.assertIn("Skipped: 7", output)

    def test_force_flag_bypasses_sync_frequency(self):
        """Test that --force flag syncs even recently synced datasets."""
        # Mark as recently synced
        self.existing_dataset.last_synced_at = timezone.now()
        self.existing_dataset.options = {"OLD_CODE": "Old data"}
        self.existing_dataset.save()

        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            out = StringIO()
            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                "--force",
                stdout=out,
            )

            output = out.getvalue()
            self.assertIn("Syncing", output)
            self.assertNotIn("Skipping", output)

            self.existing_dataset.refresh_from_db()
            # Options are now a dict: {code: name}
            self.assertIn("RGT01", self.existing_dataset.options)
            self.assertEqual(
                self.existing_dataset.options["RGT01"], "ADDENBROOKE'S HOSPITAL"
            )

    def test_single_dataset_flag(self):
        """Test syncing only a specific dataset."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            out = StringIO()
            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                stdout=out,
            )

            output = out.getvalue()
            self.assertIn("Found 1 external datasets", output)
            self.assertIn("Synced: 1", output)

            # Only one API call should be made
            self.assertEqual(mock_get.call_count, 1)

    def test_invalid_dataset_key_raises_error(self):
        """Test that invalid dataset key raises CommandError."""
        with self.assertRaises(CommandError) as context:
            call_command(
                "sync_external_datasets",
                "--dataset",
                "invalid_dataset_key",
                stdout=StringIO(),
            )

        self.assertIn("Unknown dataset key", str(context.exception))

    def test_api_error_is_handled(self):
        """Test that API errors are caught and reported."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            # Simulate API error
            mock_get.side_effect = Exception("API connection failed")

            out = StringIO()
            err = StringIO()

            with self.assertRaises(CommandError) as context:
                call_command(
                    "sync_external_datasets",
                    "--dataset",
                    "hospitals_england_wales",
                    stdout=out,
                    stderr=err,
                )

            error_output = err.getvalue()
            self.assertIn("Unexpected error", error_output)
            self.assertIn("failed to sync", str(context.exception))

    def test_malformed_api_response_is_handled(self):
        """Test that malformed API responses are caught."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            # Return invalid data (not a list)
            mock_response = Mock()
            mock_response.json.return_value = {"error": "Not a list"}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            err = StringIO()

            with self.assertRaises(CommandError):
                call_command(
                    "sync_external_datasets",
                    "--dataset",
                    "hospitals_england_wales",
                    stdout=StringIO(),
                    stderr=err,
                )

            error_output = err.getvalue()
            self.assertIn("Failed to sync", error_output)

    def test_command_is_idempotent(self):
        """Test that running command multiple times is safe."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            # Run twice
            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                "--force",
                stdout=StringIO(),
            )
            call_command(
                "sync_external_datasets",
                "--dataset",
                "hospitals_england_wales",
                "--force",
                stdout=StringIO(),
            )

            self.existing_dataset.refresh_from_db()

            # Should have same data (not duplicated)
            self.assertIsInstance(self.existing_dataset.options, dict)
            self.assertEqual(len(self.existing_dataset.options), 2)
            self.assertIn("RGT01", self.existing_dataset.options)
            self.assertEqual(
                self.existing_dataset.options["RGT01"], "ADDENBROOKE'S HOSPITAL"
            )

            # Version should be 3 (starts at 1, incremented twice)
            self.assertEqual(self.existing_dataset.version, 3)

    def test_transforms_nhs_trusts_correctly(self):
        """Test that NHS trusts are transformed with correct format."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            # Create NHS trusts dataset
            dataset = DataSet.objects.create(
                key="nhs_trusts",
                name="NHS Trusts",
                category="rcpch",
                source_type="api",
                is_global=True,
                is_custom=False,
                sync_frequency_hours=24,
            )

            call_command(
                "sync_external_datasets",
                "--dataset",
                "nhs_trusts",
                stdout=StringIO(),
            )

            dataset.refresh_from_db()
            self.assertIsInstance(dataset.options, dict)
            self.assertEqual(len(dataset.options), 2)
            self.assertIn("RCF", dataset.options)
            self.assertEqual(dataset.options["RCF"], "AIREDALE NHS FOUNDATION TRUST")

    def test_transforms_welsh_lhbs_with_hierarchy(self):
        """Test that Welsh LHBs include nested organisations."""
        with patch(
            "checktick_app.surveys.management.commands.sync_external_datasets.requests.get"
        ) as mock_get:
            self._patch_requests_get(mock_get)

            dataset = DataSet.objects.create(
                key="welsh_lhbs",
                name="Welsh Local Health Boards",
                category="rcpch",
                source_type="api",
                is_global=True,
                is_custom=False,
                sync_frequency_hours=24,
            )

            call_command(
                "sync_external_datasets", "--dataset", "welsh_lhbs", stdout=StringIO()
            )

            dataset.refresh_from_db()
            # Should have LHB + 1 nested org
            self.assertIsInstance(dataset.options, dict)
            self.assertEqual(len(dataset.options), 2)
            self.assertIn("7A3", dataset.options)
            self.assertEqual(
                dataset.options["7A3"], "Swansea Bay University Health Board"
            )
            self.assertIn("RW6C1", dataset.options)
            # Nested orgs have indentation in the name
            self.assertEqual(dataset.options["RW6C1"], "  Morriston Hospital")
