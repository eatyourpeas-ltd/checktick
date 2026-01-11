"""
Management command to sync NHS Data Dictionary datasets into the database.

This command combines the functionality of seed_nhs_datasets and scrape_nhs_dd_datasets:
1. Reads dataset definitions from docs/nhs-data-dictionary-datasets.md
2. Creates or updates DataSet records
3. Scrapes data from NHS Data Dictionary website
4. Updates options with scraped codes/descriptions

The sync process:
1. Parse markdown file for dataset definitions
2. Create/update DataSet records with metadata
3. Scrape NHS DD website for codes and descriptions
4. Update options field with scraped data
5. Update last_scraped timestamp

Usage:
    python manage.py sync_nhs_dd_datasets
    python manage.py sync_nhs_dd_datasets --dataset smoking_status_code
    python manage.py sync_nhs_dd_datasets --force  # Re-scrape even if recent
    python manage.py sync_nhs_dd_datasets --dry-run  # Preview without saving
"""

from pathlib import Path
import re
from typing import Dict

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify
import requests

from checktick_app.surveys.models import DataSet


class Command(BaseCommand):
    help = "Sync NHS Data Dictionary datasets (seed + scrape in one command)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            type=str,
            help="Sync only a specific dataset by key",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-scrape even if recently updated",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be synced without saving",
        )

    def handle(self, *args, **options):
        dataset_key = options.get("dataset")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN MODE - No changes will be saved")
            )

        # Read datasets from markdown file
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        markdown_file = base_dir / "docs" / "nhs-data-dictionary-datasets.md"

        if not markdown_file.exists():
            raise CommandError(
                f"Markdown file not found: {markdown_file}\n"
                "Expected location: docs/nhs-data-dictionary-datasets.md"
            )

        self.stdout.write(f"📖 Reading datasets from: {markdown_file}")

        dataset_definitions = self._parse_markdown_table(markdown_file)

        if not dataset_definitions:
            self.stdout.write(self.style.WARNING("No datasets found in markdown file"))
            return

        # Filter to specific dataset if requested
        if dataset_key:
            dataset_definitions = [
                d for d in dataset_definitions if d["key"] == dataset_key
            ]
            if not dataset_definitions:
                raise CommandError(
                    f"Dataset '{dataset_key}' not found in markdown file"
                )

        total = len(dataset_definitions)
        self.stdout.write(f"📊 Found {total} dataset(s) to sync\n")

        created_count = 0
        updated_count = 0
        scraped_count = 0
        skipped_count = 0
        error_count = 0

        for dataset_data in dataset_definitions:
            try:
                # Step 1: Create or update dataset record
                dataset_obj = DataSet.objects.filter(key=dataset_data["key"]).first()

                if dataset_obj:
                    # Check if sync is needed
                    if not force and dataset_obj.last_scraped:
                        # Skip if scraped within last 7 days (weekly sync)
                        time_since_scrape = timezone.now() - dataset_obj.last_scraped
                        if time_since_scrape.days < 7:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"⏭️  Skipping '{dataset_data['name']}' - scraped {time_since_scrape.days} days ago"
                                )
                            )
                            skipped_count += 1
                            continue

                    # Update metadata
                    dataset_obj.name = dataset_data["name"]
                    dataset_obj.description = dataset_data["description"]
                    dataset_obj.reference_url = dataset_data["reference_url"]
                    dataset_obj.tags = dataset_data["tags"]
                    if not dry_run:
                        dataset_obj.save()

                    self.stdout.write(f"🔄 Syncing '{dataset_data['name']}'...")
                    action = "updated"
                else:
                    # Create new dataset
                    if not dry_run:
                        dataset_obj = DataSet.objects.create(**dataset_data)
                    else:
                        # For dry-run, create a temporary object
                        dataset_obj = DataSet(**dataset_data)

                    self.stdout.write(f"✨ Creating '{dataset_data['name']}'...")
                    action = "created"
                    created_count += 1

                # Step 2: Scrape data from NHS DD website
                if dataset_obj.reference_url:
                    try:
                        options = self._scrape_dataset(dataset_obj)

                        if dry_run:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"   Would scrape {len(options)} options for '{dataset_obj.name}'"
                                )
                            )
                            scraped_count += 1
                        else:
                            # Save scraped data
                            old_count = (
                                len(dataset_obj.options)
                                if isinstance(dataset_obj.options, dict)
                                else 0
                            )
                            dataset_obj.options = options
                            dataset_obj.last_scraped = timezone.now()
                            dataset_obj.version += 1
                            dataset_obj.save()

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"✅ {action.capitalize()} '{dataset_obj.name}': "
                                    f"{old_count} → {len(options)} options (version {dataset_obj.version})"
                                )
                            )
                            scraped_count += 1

                            if action == "updated":
                                updated_count += 1

                    except Exception as scrape_error:
                        self.stdout.write(
                            self.style.ERROR(
                                f"❌ Failed to scrape '{dataset_obj.name}': {scrape_error}"
                            )
                        )
                        error_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Error processing '{dataset_data.get('name', 'unknown')}': {e}"
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY RUN COMPLETE"))
        else:
            self.stdout.write(self.style.SUCCESS("SYNC COMPLETE"))

        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Scraped: {scraped_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"  Errors: {error_count}"))
        else:
            self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write("=" * 60)

        if not dry_run:
            total_datasets = DataSet.objects.filter(category="nhs_dd").count()
            self.stdout.write(f"\nTotal NHS DD datasets: {total_datasets}")

        if error_count > 0:
            raise CommandError(f"{error_count} dataset(s) failed to sync")

    def _parse_markdown_table(self, file_path: Path) -> list[dict]:
        """
        Parse the NHS DD datasets markdown table.

        Expected format:
        | Dataset Name | NHS DD URL | Categories | Date Added | Last Scraped | NHS DD Published |
        |--------------|------------|------------|------------|--------------|------------------|
        | Name | [Link](url) | tag1, tag2 | date | status | - |

        Returns:
            List of dataset dictionaries ready for DataSet.objects.create()
        """
        content = file_path.read_text(encoding="utf-8")
        datasets = []

        # Find the table section
        lines = content.split("\n")
        in_table = False
        header_passed = False

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Detect table start
            if line.startswith("| Dataset Name"):
                in_table = True
                continue

            # Skip separator line
            if in_table and not header_passed and line.startswith("|---"):
                header_passed = True
                continue

            # Parse data rows
            if in_table and header_passed and line.startswith("|"):
                # Stop at end of table (next section starts)
                if line.startswith("##"):
                    break

                # Split by pipes and clean
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 7:  # Need at least 7 parts (including empty first/last)
                    continue

                # Extract fields
                name = parts[1].strip()
                url_match = re.search(r"\[Link\]\((https?://[^\)]+)\)", parts[2])
                categories = parts[3].strip()

                if not name or not url_match:
                    continue

                url = url_match.group(1)

                # Parse tags
                tags = [tag.strip() for tag in categories.split(",") if tag.strip()]
                tags.append("NHS")  # Add NHS tag to all

                # Generate key from name
                key = slugify(name.lower().replace(" ", "_"))

                # Create dataset dict
                dataset = {
                    "key": key,
                    "name": name,
                    "description": f"NHS Data Dictionary - {name}",
                    "category": "nhs_dd",
                    "source_type": "scrape",
                    "reference_url": url,
                    "is_custom": False,
                    "is_global": True,
                    "tags": tags,
                    "options": {},  # Will be populated by scraping
                }

                datasets.append(dataset)

        return datasets

    def _scrape_dataset(self, dataset: DataSet) -> Dict[str, str]:
        """
        Scrape a single dataset from NHS DD website.

        Args:
            dataset: DataSet object with reference_url to scrape

        Returns:
            Dictionary of {code: description} option pairs

        Raises:
            Exception: If scraping fails
        """
        self.stdout.write(f"  📡 Fetching: {dataset.reference_url}")

        # Add a User-Agent header to mimic a real browser
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(dataset.reference_url, timeout=30, headers=headers)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Extract options from the page
        options = self._extract_options_from_html(soup, dataset)

        if not options:
            raise ValueError("No valid options found on the page")

        self.stdout.write(f"  📊 Found {len(options)} items")

        return options

    def _extract_options_from_html(
        self, soup: BeautifulSoup, dataset: DataSet
    ) -> Dict[str, str]:
        """
        Extract code/value pairs from NHS DD HTML page.

        NHS DD pages typically have tables with codes and descriptions.
        This method tries multiple strategies to find the relevant data.
        """
        options = {}

        # Strategy 1: Look for tables with "Code" and "Description" or "National Code"
        tables = soup.find_all("table")

        for table in tables:
            # Get headers
            headers = []
            header_row = table.find("tr")
            if header_row:
                headers = [
                    th.get_text(strip=True).lower()
                    for th in header_row.find_all(["th", "td"])
                ]

            # Check if this looks like a data table
            if not headers or len(headers) < 2:
                continue

            # Find code and description column indices
            code_idx = None
            desc_idx = None

            for idx, header in enumerate(headers):
                if "code" in header or "value" in header:
                    code_idx = idx
                if "description" in header or "name" in header or "meaning" in header:
                    desc_idx = idx

            if code_idx is None or desc_idx is None:
                continue

            # Extract data rows
            rows = table.find_all("tr")[1:]  # Skip header

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(code_idx, desc_idx):
                    continue

                code = cells[code_idx].get_text(strip=True)
                description = cells[desc_idx].get_text(strip=True)

                # Clean up the code and description
                code = re.sub(r"\s+", " ", code).strip()
                description = re.sub(r"\s+", " ", description).strip()

                if code and description:
                    options[code] = description

        # Strategy 2: Look for definition lists (dl/dt/dd)
        if not options:
            dls = soup.find_all("dl")
            for dl in dls:
                terms = dl.find_all("dt")
                definitions = dl.find_all("dd")

                for dt, dd in zip(terms, definitions):
                    code = dt.get_text(strip=True)
                    description = dd.get_text(strip=True)

                    # Try to extract code from the term
                    code_match = re.search(r"^([A-Z0-9]+)", code)
                    if code_match:
                        code = code_match.group(1)
                        description = re.sub(r"^[A-Z0-9]+\s*[-–—]\s*", "", description)

                    if code and description:
                        options[code] = description

        # Strategy 3: Look for lists with specific patterns
        if not options:
            lists = soup.find_all(["ul", "ol"])
            for lst in lists:
                items = lst.find_all("li")
                for item in items:
                    text = item.get_text(strip=True)
                    # Look for pattern: "CODE - Description" or "CODE: Description"
                    match = re.match(r"^([A-Z0-9]+)\s*[-–—:]\s*(.+)$", text)
                    if match:
                        code, description = match.groups()
                        options[code] = description

        return options
