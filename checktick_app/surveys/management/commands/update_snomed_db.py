"""
Management command to check for and apply SNOMED CT database updates.

Uses the `sct` binary's two-step approach:
  1. `sct trud check` — lightweight check against TRUD API (exit 0=current, 2=update, 1=error)
  2. `sct trud download --pipeline` — download + build snomed.db only if needed

This avoids the cost of a full download when there is nothing new, making it
safe to run frequently (e.g. as a daily cron / Northflank scheduled job).

After a successful rebuild, `seed_snomed_datasets` is re-run automatically to
refresh member counts and the release date stored in Postgres.

Usage:
    python manage.py update_snomed_db
    python manage.py update_snomed_db --force   # skip check, always download
    python manage.py update_snomed_db --edition uk_drug   # alternative edition
    python manage.py update_snomed_db --dry-run

Requirements:
    - TRUD_API_KEY environment variable set
    - SNOMED_DB_PATH environment variable set (path to snomed.db)
    - `sct` binary on PATH inside the container
"""

import os
from pathlib import Path
import subprocess
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

# sct trud check exit codes (documented at https://pacharanero.github.io/sct/commands/trud/)
SCT_EXIT_UP_TO_DATE = 0
SCT_EXIT_UPDATE_AVAILABLE = 2
SCT_EXIT_ERROR = 1


def _get_setting(name: str, default: str = "") -> str:
    return getattr(settings, name, None) or os.environ.get(name, default)


class Command(BaseCommand):
    help = (
        "Check TRUD for a new SNOMED CT release and rebuild snomed.db if one is available. "
        "Requires TRUD_API_KEY and SNOMED_DB_PATH to be set. "
        "Uses `sct trud check` to avoid unnecessary downloads."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip the update check and always download + rebuild snomed.db",
        )
        parser.add_argument(
            "--edition",
            default="uk_monolith",
            help="SNOMED CT edition to download (default: uk_monolith)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without running sct commands or saving",
        )

    def handle(self, *args, **options):
        force = options["force"]
        edition = options["edition"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN — no commands will be executed")
            )

        # ── Preflight checks ──────────────────────────────────────────────
        trud_api_key = _get_setting("TRUD_API_KEY")
        if not trud_api_key:
            self.stdout.write(
                self.style.ERROR(
                    "❌ TRUD_API_KEY is not set — cannot check for SNOMED CT updates.\n"
                    "   Register at isd.digital.nhs.uk/trud and add your API key to .env."
                )
            )
            sys.exit(1)

        snomed_db_path = _get_setting("SNOMED_DB_PATH")
        if not snomed_db_path:
            self.stdout.write(
                self.style.ERROR(
                    "❌ SNOMED_DB_PATH is not set — don't know where to write snomed.db."
                )
            )
            sys.exit(1)

        data_dir = str(Path(snomed_db_path).parent)

        # Verify sct binary is available (skipped in dry-run)
        if not dry_run:
            try:
                sct_check = subprocess.run(
                    ["sct", "--version"], capture_output=True, text=True
                )
                sct_version = sct_check.stdout.strip() or sct_check.stderr.strip()
                self.stdout.write(f"🔧 sct binary: {sct_version}")
            except FileNotFoundError:
                self.stdout.write(
                    self.style.ERROR(
                        "❌ `sct` binary not found on PATH.\n"
                        "   Install it from https://github.com/pacharanero/sct or ensure\n"
                        "   it is included in the container image."
                    )
                )
                sys.exit(1)
        else:
            self.stdout.write("🔧 sct binary: (not checked in dry-run)")

        # ── Step 1: check for update (unless --force) ─────────────────────
        needs_update = force

        if not force:
            self.stdout.write(f"🔎 Checking TRUD for new {edition} release...")

            if dry_run:
                self.stdout.write(
                    f"   [DRY RUN] would run: sct trud check --edition {edition}"
                )
                self.stdout.write("   Assuming update available for dry-run.")
                return

            check_result = subprocess.run(
                ["sct", "trud", "check", "--edition", edition],
                capture_output=True,
                text=True,
                env={**os.environ, "TRUD_API_KEY": trud_api_key},
            )

            if check_result.returncode == SCT_EXIT_UP_TO_DATE:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ SNOMED CT ({edition}) is already up to date — no download needed."
                    )
                )
                # Print what sct reported (contains version + SHA-256 info)
                if check_result.stdout:
                    for line in check_result.stdout.strip().splitlines():
                        self.stdout.write(f"   {line}")
                return

            elif check_result.returncode == SCT_EXIT_UPDATE_AVAILABLE:
                self.stdout.write(
                    self.style.WARNING(
                        f"🆕 New SNOMED CT release available ({edition}) — starting download..."
                    )
                )
                if check_result.stdout:
                    for line in check_result.stdout.strip().splitlines():
                        self.stdout.write(f"   {line}")
                needs_update = True

            else:
                # Exit code 1 = error (network, bad key, maintenance window, etc.)
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct trud check failed (exit {check_result.returncode}).\n"
                        "   TRUD may be in its maintenance window (weekdays 18:00–08:00 UK time).\n"
                        "   Check your TRUD_API_KEY and network connectivity."
                    )
                )
                if check_result.stderr:
                    self.stdout.write(check_result.stderr.strip())
                sys.exit(1)

        # ── Step 2: download + build pipeline ─────────────────────────────
        if needs_update:
            if force:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚡ --force specified — downloading {edition} regardless of current state."
                    )
                )

            self.stdout.write(
                f"⬇️  Downloading SNOMED CT {edition} and building snomed.db...\n"
                f"   This may take several minutes (UK Monolith ~1.8 GB)."
            )

            if dry_run:
                self.stdout.write(
                    f"   [DRY RUN] would run: sct trud download --edition {edition} "
                    f"--pipeline --data-dir {data_dir}"
                )
                return

            # Redirect TMPDIR to the mounted volume so that sct's intermediate
            # files (ndjson extraction, SQLite build) do not fill the container's
            # ephemeral storage and trigger an eviction/OOM kill.
            tmp_dir = str(Path(data_dir) / "tmp")
            Path(tmp_dir).mkdir(parents=True, exist_ok=True)

            download_result = subprocess.run(
                [
                    "sct",
                    "trud",
                    "download",
                    "--edition",
                    edition,
                    "--output-dir",
                    data_dir,
                    "--data-dir",
                    data_dir,
                    "--pipeline",
                ],
                text=True,
                env={
                    **os.environ,
                    "TRUD_API_KEY": trud_api_key,
                    "TMPDIR": tmp_dir,
                    "TEMP": tmp_dir,
                    "TMP": tmp_dir,
                },
            )

            if download_result.returncode != 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct trud download failed (exit {download_result.returncode}).\n"
                        "   Check the output above for details."
                    )
                )
                sys.exit(download_result.returncode)

            # sct writes a release-versioned filename (e.g. uk_sct2mo_42.1.0_….db).
            # Rename it to the canonical path that SNOMED_DB_PATH points to.
            versioned_dbs = sorted(Path(data_dir).glob("uk_sct2mo_*.db"))
            if versioned_dbs:
                versioned_db = versioned_dbs[-1]
                target = Path(snomed_db_path)
                versioned_db.rename(target)
                self.stdout.write(f"   Renamed {versioned_db.name} → {target.name}")
            elif not Path(snomed_db_path).exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ No .db file found in {data_dir} after build — rename failed."
                    )
                )
                sys.exit(1)

            self.stdout.write(self.style.SUCCESS("✅ snomed.db rebuilt successfully."))

            # ── Step 3: refresh DataSet descriptors ───────────────────────
            self.stdout.write(
                "🔄 Refreshing SNOMED CT dataset descriptors in database..."
            )
            call_command("seed_snomed_datasets", force=True, dry_run=False)

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🏥 SNOMED CT update complete ({edition}).\n"
                    "   snomed.db rebuilt and dataset descriptors refreshed."
                )
            )
