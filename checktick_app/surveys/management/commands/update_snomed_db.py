"""
Management command to check for and apply SNOMED CT database updates.

Uses the `sct` binary's two-step approach:
  1. `sct trud check` — lightweight check against TRUD API (exit 0=current, 2=update, 1=error)
  2. `sct trud download` (no --pipeline) + explicit `sct ndjson` + `sct sqlite`,
     followed by an atomic `os.replace()` into the canonical snomed.db path.

The pipeline is split deliberately rather than using `sct trud download --pipeline`:
the pipeline mode writes SQLite directly to the canonical snomed.db path, which is
held open read-only by gunicorn workers (SnomedResolver thread-local connections).
`sct sqlite` then cannot get the exclusive lock it needs to clear and rebuild,
failing with SQLITE_BUSY ("database is locked"). By building to a temp file on the
same volume and `os.replace()`-ing it into place, the swap is atomic on POSIX and
no exclusive lock is ever held against the live snomed.db. This makes the command
safe to run while the web app is serving traffic, and therefore safe to run from a
scheduled job.

This avoids the cost of a full download when there is nothing new, making it
safe to run frequently (e.g. as a daily cron / Northflank scheduled job).

After a successful rebuild, `seed_snomed_datasets` is re-run automatically to
refresh member counts and the release date stored in Postgres.

Usage:
    python manage.py update_snomed_db
    python manage.py update_snomed_db --force   # skip check, always download
    python manage.py update_snomed_db --force --prune   # clean stale artefacts first
    python manage.py update_snomed_db --edition uk_drug   # alternative edition
    python manage.py update_snomed_db --dry-run

Requirements:
    - TRUD_API_KEY environment variable set
    - SNOMED_DB_PATH environment variable set (path to snomed.db)
    - `sct` binary on PATH inside the container
"""

import os
from pathlib import Path
import shutil
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


def _prune_snomed_artifacts(data_dir: Path, snomed_db_path: Path):
    """Remove stale SNOMED build artefacts to reduce peak disk usage."""
    removed = []

    tmp_dir = data_dir / "tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
        removed.append(tmp_dir.name + "/")

    for zip_path in sorted(data_dir.glob("*.zip")):
        zip_path.unlink()
        removed.append(zip_path.name)

    for db_path in sorted(data_dir.glob("uk_sct2*.db")):
        if db_path.resolve() == snomed_db_path.resolve():
            continue
        db_path.unlink()
        removed.append(db_path.name)

    return removed


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
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "Delete stale tmp/zip/versioned db artefacts in SNOMED data dir "
                "before checking/downloading"
            ),
        )

    def handle(self, *args, **options):
        force = options["force"]
        edition = options["edition"]
        dry_run = options["dry_run"]
        prune = options["prune"]

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

        snomed_db = Path(snomed_db_path)
        data_dir = snomed_db.parent

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

        if prune:
            if dry_run:
                self.stdout.write(
                    "   [DRY RUN] would prune stale tmp/, *.zip and uk_sct2*.db artefacts"
                )
            else:
                self.stdout.write("🧹 Pruning stale SNOMED artefacts before update...")
                try:
                    removed = _prune_snomed_artifacts(data_dir, snomed_db)
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to prune SNOMED artefacts: {exc}")
                    )
                    sys.exit(1)

                if removed:
                    self.stdout.write(f"   Removed {len(removed)} artefact(s).")
                else:
                    self.stdout.write("   Nothing to prune.")

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

        # ── Step 2: download + build (explicit two-step, atomic swap) ─────
        #
        # We deliberately do NOT use `sct trud download --pipeline`. The
        # pipeline mode chains ndjson + sqlite and writes the SQLite file
        # directly to the canonical snomed.db path. That file is held open
        # read-only by gunicorn workers (SnomedResolver thread-local
        # connections), so `sct sqlite` cannot get the exclusive lock it
        # needs to clear and rebuild — failing with SQLITE_BUSY ("database
        # is locked").
        #
        # Instead we run the three steps ourselves:
        #   1. `sct trud download`           — fetch + verify the RF2 zip
        #   2. `sct ndjson --rf2 <zip>`      — build NDJSON to a temp path
        #   3. `sct sqlite --ndjson <ndjson> --output <tmp>.db`
        #                                    — build SQLite to a fresh file
        #                                    nobody else has open
        # Then atomically `os.replace(tmp_db, snomed.db)`. POSIX guarantees
        # this is atomic: readers either keep their already-open fd on the
        # old inode, or open the new inode on the next request. No exclusive
        # lock is ever held against the live snomed.db.
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

            # Redirect TMPDIR to the mounted volume so that sct's intermediate
            # files (ndjson extraction, SQLite build) do not fill the container's
            # ephemeral storage and trigger an eviction/OOM kill.
            tmp_dir = str(data_dir / "tmp")
            Path(tmp_dir).mkdir(parents=True, exist_ok=True)

            sct_env = {
                **os.environ,
                "TRUD_API_KEY": trud_api_key,
                "TMPDIR": tmp_dir,
                "TEMP": tmp_dir,
                "TMP": tmp_dir,
            }

            if dry_run:
                self.stdout.write(
                    f"   [DRY RUN] would run:\n"
                    f"     sct trud download --edition {edition} --output-dir {data_dir}\n"
                    f"     sct ndjson --rf2 <zip> --output <tmp>.ndjson\n"
                    f"     sct sqlite --ndjson <tmp>.ndjson --output <tmp>.db\n"
                    f"     os.replace(<tmp>.db, {snomed_db})"
                )
                return

            # ── Step 2a: download the RF2 zip (no pipeline) ───────────────
            download_result = subprocess.run(
                [
                    "sct",
                    "trud",
                    "download",
                    "--edition",
                    edition,
                    "--output-dir",
                    str(data_dir),
                ],
                text=True,
                env=sct_env,
            )

            if download_result.returncode != 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct trud download failed (exit {download_result.returncode}).\n"
                        "   Check the output above for details."
                    )
                )
                sys.exit(download_result.returncode)

            # Locate the downloaded zip. sct writes a release-versioned name
            # like uk_sct2mo_42.3.0_20260701000001Z.zip.
            zips = sorted(data_dir.glob("uk_sct2mo_*.zip"))
            if not zips:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ No uk_sct2mo_*.zip found in {data_dir} after download."
                    )
                )
                sys.exit(1)
            rf2_zip = zips[-1]
            self.stdout.write(f"   Downloaded: {rf2_zip.name}")

            # ── Step 2b: build NDJSON to a temp path ─────────────────────
            ndjson_tmp = data_dir / f"{rf2_zip.stem}.ndjson"
            self.stdout.write(f"   → Running: sct ndjson ({rf2_zip.name})")
            ndjson_result = subprocess.run(
                [
                    "sct",
                    "ndjson",
                    "--rf2",
                    str(rf2_zip),
                    "--output",
                    str(ndjson_tmp),
                ],
                text=True,
                env=sct_env,
            )

            if ndjson_result.returncode != 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct ndjson failed (exit {ndjson_result.returncode}).\n"
                        "   Check the output above for details."
                    )
                )
                sys.exit(ndjson_result.returncode)

            if not ndjson_tmp.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct ndjson reported success but {ndjson_tmp.name} "
                        "was not written."
                    )
                )
                sys.exit(1)

            # ── Step 2c: build SQLite to a fresh temp path (no lock conflict)
            # The temp path is on the same volume as snomed.db so that
            # os.replace() is a same-filesystem rename (atomic on POSIX).
            sqlite_tmp = data_dir / f"{rf2_zip.stem}.db.new"
            # Make sure we never reuse a stale temp file from a previous run.
            if sqlite_tmp.exists():
                sqlite_tmp.unlink()

            self.stdout.write(f"   → Running: sct sqlite → {sqlite_tmp.name}")
            sqlite_result = subprocess.run(
                [
                    "sct",
                    "sqlite",
                    "--ndjson",
                    str(ndjson_tmp),
                    "--output",
                    str(sqlite_tmp),
                ],
                text=True,
                env=sct_env,
            )

            if sqlite_result.returncode != 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct sqlite failed (exit {sqlite_result.returncode}).\n"
                        "   Check the output above for details."
                    )
                )
                # Clean up the partial temp db so the next run starts fresh.
                if sqlite_tmp.exists():
                    sqlite_tmp.unlink()
                sys.exit(sqlite_result.returncode)

            if not sqlite_tmp.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ sct sqlite reported success but {sqlite_tmp.name} "
                        "was not written."
                    )
                )
                sys.exit(1)

            # ── Step 2d: atomic swap into place ───────────────────────────
            # os.replace is atomic on POSIX when src and dst are on the same
            # filesystem (they are — both are in data_dir). Gunicorn workers
            # holding read-only connections to the old inode continue to see
            # the old snomed.db until they reconnect; new connections open the
            # new inode. No exclusive lock is required against the live file.
            os.replace(sqlite_tmp, snomed_db)
            self.stdout.write(
                f"   Atomically swapped {sqlite_tmp.name} → {snomed_db.name}"
            )

            # Clean up the NDJSON intermediate to free volume space.
            try:
                ndjson_tmp.unlink()
            except OSError:
                pass

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
