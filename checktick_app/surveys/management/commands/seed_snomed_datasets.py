"""
Management command to seed SNOMED CT dataset descriptors into the database.

This command creates or updates DataSet records for curated SNOMED CT terminology
lists. It does NOT copy SNOMED data into Postgres — the DataSet rows are lightweight
descriptors only. Options are served live from snomed.db via SnomedResolver at
request time.

Requires snomed.db to be present at SNOMED_DB_PATH (built by the sct binary).
If snomed.db is absent, the command exits cleanly with a warning so it can be
run safely in environments where SNOMED is not configured.

Usage:
    python manage.py seed_snomed_datasets
    python manage.py seed_snomed_datasets --dry-run
    python manage.py seed_snomed_datasets --force   # re-seed even if already seeded
"""

import datetime
import logging
import os
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand

from checktick_app.surveys.models import DataSet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curated dataset definitions
# ---------------------------------------------------------------------------
# Each entry becomes one DataSet descriptor row.
# snomed_refset_id: SCTID — use '' for ecl/mapped types (Phase 2).
# snomed_member_count: left None here; populated from snomed.db at seed time.
# is_featured: True = shown in default dataset browser.
#
# SCTIDs below are indicative. Run `sct refset list --json` against a live
# UK Monolith snomed.db to confirm exact IDs before production seeding.
# ---------------------------------------------------------------------------

FEATURED_DATASETS = [
    # ── Demographics ──────────────────────────────────────────────────────
    {
        "key": "snomed_ethnic_category",
        "name": "Ethnic Category (SNOMED CT)",
        "description": "UK ethnic categories as SNOMED CT concepts.",
        "snomed_refset_id": "999004081000000106",
        "snomed_query_type": "refset",
        "tags": ["demographics", "ethnicity", "snomed"],
        "is_featured": True,
    },
    # ── Drugs — QOF-specific lists ────────────────────────────────────────
    {
        "key": "snomed_qof_epilepsy_drugs",
        "name": "QOF Epilepsy Drug List (SNOMED CT)",
        "description": "Drugs used to treat epilepsy as defined by QOF business rules.",
        "snomed_refset_id": "999002391000000104",
        "snomed_query_type": "refset",
        "tags": ["drugs", "epilepsy", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_diabetes_drugs",
        "name": "QOF Diabetes Drug List (SNOMED CT)",
        "description": "Drugs used to treat diabetes as defined by QOF business rules.",
        "snomed_refset_id": "999002401000000101",
        "snomed_query_type": "refset",
        "tags": ["drugs", "diabetes", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_af_drugs",
        "name": "QOF Atrial Fibrillation Drug List (SNOMED CT)",
        "description": "Anticoagulant and rate-control drugs for AF as defined by QOF.",
        "snomed_refset_id": "999002421000000105",
        "snomed_query_type": "refset",
        "tags": ["drugs", "atrial fibrillation", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_asthma_copd_drugs",
        "name": "QOF Asthma / COPD Drug List (SNOMED CT)",
        "description": "Inhaled and systemic drugs for asthma and COPD as defined by QOF.",
        "snomed_refset_id": "999002411000000103",
        "snomed_query_type": "refset",
        "tags": ["drugs", "asthma", "COPD", "QOF", "snomed"],
        "is_featured": True,
    },
    # ── Drugs — dm+d hierarchy ────────────────────────────────────────────
    {
        "key": "snomed_glp1_agonists",
        "name": "GLP-1 Receptor Agonists (dm+d)",
        "description": "All GLP-1 receptor agonist drugs (descendants of 372938004).",
        "snomed_refset_id": "372938004",
        "snomed_query_type": "descendants",
        "tags": ["drugs", "GLP-1", "diabetes", "dm+d", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_sglt2_inhibitors",
        "name": "SGLT2 Inhibitors (dm+d)",
        "description": "All SGLT2 inhibitor drugs (descendants of 703673008).",
        "snomed_refset_id": "703673008",
        "snomed_query_type": "descendants",
        "tags": ["drugs", "SGLT2", "diabetes", "dm+d", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_insulins",
        "name": "Insulin Products (dm+d)",
        "description": "All insulin products (descendants of 67866001).",
        "snomed_refset_id": "67866001",
        "snomed_query_type": "descendants",
        "tags": ["drugs", "insulin", "diabetes", "dm+d", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_dmd_vtm",
        "name": "dm+d VTM — All Drug Substances",
        "description": "All active Virtual Therapeutic Moieties from dm+d (~1,000 concepts). "
        "Use for drug substance-level questions.",
        "snomed_refset_id": "999000561000001109",
        "snomed_query_type": "refset",
        "tags": ["drugs", "dm+d", "VTM", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_dmd_vmp",
        "name": "dm+d VMP — All Medicinal Products",
        "description": "All active Virtual Medicinal Products from dm+d (~20,000+ concepts). "
        "Typeahead only — too large for a dropdown.",
        "snomed_refset_id": "999000541000001108",
        "snomed_query_type": "refset",
        "tags": ["drugs", "dm+d", "VMP", "snomed"],
        "is_featured": True,
    },
    # ── Conditions — QOF registers ────────────────────────────────────────
    {
        "key": "snomed_qof_diabetes_register",
        "name": "QOF Diabetes Register (SNOMED CT)",
        "description": "SNOMED CT codes that define the QOF Diabetes disease register.",
        "snomed_refset_id": "999002441000000106",
        "snomed_query_type": "refset",
        "tags": ["conditions", "diabetes", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_epilepsy_register",
        "name": "QOF Epilepsy Register (SNOMED CT)",
        "description": "SNOMED CT codes that define the QOF Epilepsy disease register.",
        "snomed_refset_id": "999002451000000109",
        "snomed_query_type": "refset",
        "tags": ["conditions", "epilepsy", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_hypertension_register",
        "name": "QOF Hypertension Register (SNOMED CT)",
        "description": "SNOMED CT codes that define the QOF Hypertension disease register.",
        "snomed_refset_id": "999002461000000107",
        "snomed_query_type": "refset",
        "tags": ["conditions", "hypertension", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_chd_register",
        "name": "QOF CHD / Heart Failure Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Coronary Heart Disease and Heart Failure register.",
        "snomed_refset_id": "999002471000000100",
        "snomed_query_type": "refset",
        "tags": ["conditions", "CHD", "heart failure", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_af_register",
        "name": "QOF Atrial Fibrillation Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Atrial Fibrillation disease register.",
        "snomed_refset_id": "999002481000000103",
        "snomed_query_type": "refset",
        "tags": ["conditions", "atrial fibrillation", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_asthma_register",
        "name": "QOF Asthma / COPD Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Asthma and COPD disease registers.",
        "snomed_refset_id": "999002491000000101",
        "snomed_query_type": "refset",
        "tags": ["conditions", "asthma", "COPD", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_cancer_register",
        "name": "QOF Cancer Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Cancer disease register.",
        "snomed_refset_id": "999002501000000102",
        "snomed_query_type": "refset",
        "tags": ["conditions", "cancer", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_mental_health_register",
        "name": "QOF Mental Health / Depression Register (SNOMED CT)",
        "description": "SNOMED CT codes for QOF Mental Health and Depression registers.",
        "snomed_refset_id": "999002511000000100",
        "snomed_query_type": "refset",
        "tags": ["conditions", "mental health", "depression", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_dementia_register",
        "name": "QOF Dementia Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Dementia disease register.",
        "snomed_refset_id": "999002521000000106",
        "snomed_query_type": "refset",
        "tags": ["conditions", "dementia", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_stroke_register",
        "name": "QOF Stroke / TIA Register (SNOMED CT)",
        "description": "SNOMED CT codes for the QOF Stroke and TIA disease register.",
        "snomed_refset_id": "999002531000000108",
        "snomed_query_type": "refset",
        "tags": ["conditions", "stroke", "TIA", "QOF", "snomed"],
        "is_featured": True,
    },
    # ── Anatomy ───────────────────────────────────────────────────────────
    {
        "key": "snomed_body_sites",
        "name": "Common Body Sites (SNOMED CT)",
        "description": "Frequently used anatomical sites (descendants of 123037004 — Body structure).",
        "snomed_refset_id": "123037004",
        "snomed_query_type": "descendants",
        "tags": ["anatomy", "body site", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_administration_routes",
        "name": "Drug Administration Routes (SNOMED CT)",
        "description": "Routes of drug administration (descendants of 284009009 — Route of administration).",
        "snomed_refset_id": "284009009",
        "snomed_query_type": "descendants",
        "tags": ["drugs", "administration", "route", "snomed"],
        "is_featured": True,
    },
]


def _get_snomed_db_path() -> str | None:
    """Return snomed.db path if configured and present, else None."""
    path = getattr(settings, "SNOMED_DB_PATH", None) or os.environ.get(
        "SNOMED_DB_PATH", ""
    )
    if path and os.path.isfile(path):
        return path
    return None


def _get_release_date(db_path: str) -> datetime.date | None:
    """Try to read the SNOMED release date from snomed.db metadata table."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'release_date' LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return datetime.date.fromisoformat(row[0])
    except Exception:
        pass
    return None


def _get_member_count(db_path: str, definition: dict) -> int | None:
    """Count members for refset or descendants query types."""
    from checktick_app.surveys.snomed_resolver import (
        SnomedUnavailableError,
        get_refset_member_count,
    )

    query_type = definition["snomed_query_type"]
    refset_id = definition.get("snomed_refset_id", "")

    if query_type == "refset" and refset_id:
        try:
            return get_refset_member_count(refset_id)
        except SnomedUnavailableError:
            return None
    return None


class Command(BaseCommand):
    help = (
        "Seed SNOMED CT dataset descriptors into the database. "
        "Requires snomed.db to be present at SNOMED_DB_PATH. "
        "Exits cleanly if SNOMED CT is not configured."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created/updated without saving",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-seed all datasets even if they already exist",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN — no changes will be saved")
            )

        # Check snomed.db is available
        configured_path = getattr(settings, "SNOMED_DB_PATH", None) or os.environ.get(
            "SNOMED_DB_PATH", ""
        )
        db_path = _get_snomed_db_path()
        if not db_path:
            if not configured_path:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️  SNOMED_DB_PATH is not set — skipping SNOMED CT dataset seeding.\n"
                        "   Add SNOMED_DB_PATH to your .env and run 'sct trud download ...' to build snomed.db."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  snomed.db not found at {configured_path} — skipping SNOMED CT dataset seeding.\n"
                        "   Run 'sct trud download --edition uk_monolith --pipeline' to build it."
                    )
                )
            return

        self.stdout.write(f"🏥 Seeding SNOMED CT datasets from: {db_path}")

        release_date = _get_release_date(db_path)
        if release_date:
            self.stdout.write(f"📅 SNOMED CT release date: {release_date}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "   Could not read release date from snomed.db metadata."
                )
            )

        created = updated = skipped = 0

        for defn in FEATURED_DATASETS:
            key = defn["key"]

            existing = DataSet.objects.filter(key=key).first()

            if existing and not force:
                skipped += 1
                self.stdout.write(
                    f"   ⏭  {key} — already exists (use --force to re-seed)"
                )
                continue

            member_count = _get_member_count(db_path, defn)

            fields = {
                "name": defn["name"],
                "description": defn["description"],
                "category": "snomed",
                "source_type": "snomed_db",
                "snomed_refset_id": defn.get("snomed_refset_id", ""),
                "snomed_query_type": defn["snomed_query_type"],
                "snomed_ecl": defn.get("snomed_ecl", ""),
                "snomed_release_date": release_date,
                "snomed_member_count": member_count,
                "is_featured": defn.get("is_featured", False),
                "is_global": True,
                "is_custom": False,
                "is_active": True,
                "tags": defn.get("tags", []),
                "options": [],  # always empty — served live from snomed.db
            }

            count_str = (
                f" ({member_count:,} members)" if member_count is not None else ""
            )

            if dry_run:
                action = "UPDATE" if existing else "CREATE"
                self.stdout.write(f"   [{action}] {key} — {defn['name']}{count_str}")
                continue

            if existing:
                for attr, value in fields.items():
                    setattr(existing, attr, value)
                existing.save()
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ updated: {key}{count_str}")
                )
            else:
                DataSet.objects.create(key=key, **fields)
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   ✨ created: {key}{count_str}")
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🏥 SNOMED CT seeding complete: "
                    f"{created} created, {updated} updated, {skipped} skipped."
                )
            )
        else:
            self.stdout.write(
                f"\n🔍 Dry run complete: {len(FEATURED_DATASETS)} datasets would be processed."
            )
