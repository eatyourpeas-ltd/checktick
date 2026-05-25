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
# snomed_refset_id: SCTID of the refset, or ancestor concept for descendants queries.
# snomed_member_count: populated from snomed.db at seed time.
# is_featured: True = shown in default dataset browser.
#
# DESIGN PRINCIPLE — curated refsets only
# ----------------------------------------
# A SNOMED CT reference set (refset) is a curated, expert-maintained subset of
# concepts assembled for a specific clinical purpose. This is what CheckTick
# supports: validated lists that power survey dropdowns without users having to
# define their own clinical criteria (e.g. QOF drug lists, paediatric specialty
# condition sets, ePrescribing routes).
#
# What CheckTick does NOT support here:
# - The full dm+d drug dictionary (VTM ~23k, VMP ~162k) — these are the source
#   from which clinical drug lists are carved, not curated lists themselves.
# - Full hierarchy traversals (descendants of body structure, descendants of
#   clinical finding) — these are the entire SNOMED taxonomy, not refsets.
#
# If a user needs a bespoke list not in this registry, they can:
#   1. Request a new refset via the GitHub issue template
#   2. Use "Snapshot to Custom Dataset" on an existing dataset and filter it
#   3. Create a plain custom dataset via the dataset builder
#
# All refset SCTIDs below are verified against the sct UK Monolith Edition by
# direct concept lookup (SELECT id, preferred_term FROM concepts WHERE id = ?).
#
# NOTE: QOF disease condition *register* refsets (the SNOMED codes that define
# which patients count as being on a QOF register) are distributed in the
# separate NHS England QOF Supplement TRUD product and are NOT present in the
# UK Monolith Edition. Do not attempt to seed them from the Monolith.
# ---------------------------------------------------------------------------

FEATURED_DATASETS = [
    # ── Drugs — QOF-specific lists ────────────────────────────────────────
    # Verified refset IDs from UK Monolith (queried via SELECT DISTINCT refset_id):
    {
        "key": "snomed_qof_epilepsy_drugs",
        "name": "QOF Antiepileptic Drug List (SNOMED CT)",
        "description": "Antiepileptic medication prescribable in general practice (QOF extraction refset).",
        "snomed_refset_id": "12465301000001101",
        "snomed_query_type": "refset",
        "tags": ["drugs", "epilepsy", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_diabetes_drugs",
        "name": "QOF Diabetic Drug List (SNOMED CT)",
        "description": "Diabetic drugs for enhanced services general practice extraction.",
        "snomed_refset_id": "999000851000001109",
        "snomed_query_type": "refset",
        "tags": ["drugs", "diabetes", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_asthma_copd_drugs",
        "name": "QOF Asthma / COPD Drug List (SNOMED CT)",
        "description": "Chronic asthma medication prescribable within general practice (QOF extraction refset).",
        "snomed_refset_id": "12463601000001108",
        "snomed_query_type": "refset",
        "tags": ["drugs", "asthma", "COPD", "QOF", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_qof_chd_drugs",
        "name": "QOF CHD Beta-Blocker Drug List (SNOMED CT)",
        "description": "Beta-adrenoceptor blockers for use in coronary heart disease, prescribable in general practice (QOF).",
        "snomed_refset_id": "12464101000001102",
        "snomed_query_type": "refset",
        "tags": ["drugs", "CHD", "QOF", "snomed"],
        "is_featured": True,
    },
    # ── Drugs — large reference dictionaries (is_featured=False) ─────────
    # These are the full dm+d dictionaries — not curated clinical lists.
    # They are registered as descriptors so survey responses can reference a
    # specific SNOMED release date, but they are hidden from the default
    # dataset browser (is_featured=False). Administrators can promote them
    # if a specific use case warrants it (e.g. typeahead across all medicines).
    {
        "key": "snomed_dmd_vtm",
        "name": "dm+d VTM — All Drug Substances",
        "description": "All active Virtual Therapeutic Moieties from dm+d (~23,000 concepts). "
        "Full drug substance dictionary — not a curated clinical list. "
        "Hidden by default; use a specific QOF or specialty refset instead.",
        "snomed_refset_id": "999000561000001109",
        "snomed_query_type": "refset",
        "tags": ["drugs", "dm+d", "VTM", "snomed"],
        "is_featured": False,
    },
    {
        "key": "snomed_dmd_vmp",
        "name": "dm+d VMP — All Medicinal Products",
        "description": "All active Virtual Medicinal Products from dm+d (~162,000 concepts). "
        "Full medicinal product dictionary — not a curated clinical list. "
        "Hidden by default; use a specific QOF or specialty refset instead.",
        "snomed_refset_id": "999000541000001108",
        "snomed_query_type": "refset",
        "tags": ["drugs", "dm+d", "VMP", "snomed"],
        "is_featured": False,
    },
    # ── Conditions — Paediatric clinical condition refsets ────────────────
    # These refsets ARE present in the UK Monolith Edition (verified by SCTID lookup).
    # Note: QOF disease *register* refsets (epilepsy, hypertension, CHD, AF, asthma,
    # diabetes) are only in the separate NHS England QOF Supplement TRUD product and
    # are NOT available in the Monolith — do not attempt to seed them here.
    {
        "key": "snomed_paed_neurology",
        "name": "Paediatric Neurology, Neurodevelopmental & Neurodisability Disorders",
        "description": "SNOMED CT codes for paediatric neurology, neurodevelopmental and neurodisability conditions (NHS simple reference set).",
        "snomed_refset_id": "2222191000000108",
        "snomed_query_type": "refset",
        "tags": [
            "conditions",
            "paediatric",
            "neurology",
            "neurodevelopmental",
            "snomed",
        ],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_neurodisability_outpatient",
        "name": "Paediatric Neurodisability Outpatient Diagnoses",
        "description": "SNOMED CT codes for paediatric neurodisability diagnoses used in outpatient settings (NHS simple reference set).",
        "snomed_refset_id": "999001751000000105",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "neurodisability", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_allergy_immunology",
        "name": "Paediatric Allergy & Immunology Findings",
        "description": "SNOMED CT codes for paediatric allergy and immunology clinical findings (NHS simple reference set).",
        "snomed_refset_id": "2170881000000102",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "allergy", "immunology", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_respiratory",
        "name": "Paediatric Respiratory Disorders",
        "description": "SNOMED CT codes for paediatric respiratory disorders including asthma (NHS simple reference set).",
        "snomed_refset_id": "2181221000000101",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "respiratory", "asthma", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_endocrine_metabolic",
        "name": "Paediatric Endocrine & Metabolic Disorders",
        "description": "SNOMED CT codes for paediatric endocrine and metabolic disorders including diabetes (NHS simple reference set).",
        "snomed_refset_id": "2181151000000100",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "endocrine", "diabetes", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_cardiovascular",
        "name": "Paediatric Cardiovascular Disorders",
        "description": "SNOMED CT codes for paediatric cardiovascular disorders (NHS simple reference set).",
        "snomed_refset_id": "2181141000000103",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "cardiovascular", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_genitourinary_renal",
        "name": "Paediatric Genitourinary & Renal Disorders",
        "description": "SNOMED CT codes for paediatric genitourinary and renal disorders (NHS simple reference set).",
        "snomed_refset_id": "2181181000000106",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "renal", "genitourinary", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_gi_nutrition",
        "name": "Paediatric Gastroenterology & Nutrition Findings",
        "description": "SNOMED CT codes for paediatric gastrointestinal and nutrition clinical findings (NHS simple reference set).",
        "snomed_refset_id": "2181171000000109",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "gastroenterology", "nutrition", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_infectious_disease",
        "name": "Paediatric Infectious Disease Disorders",
        "description": "SNOMED CT codes for paediatric infectious disease disorders (NHS simple reference set).",
        "snomed_refset_id": "2222181000000106",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "infectious disease", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_behaviour_mental_health",
        "name": "Paediatric Behaviour, Emotions & Mental Health",
        "description": "SNOMED CT codes for paediatric behaviour, emotions, mental health and substance use (NHS simple reference set).",
        "snomed_refset_id": "2181121000000105",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "mental health", "behaviour", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_paed_perinatal_neonatal",
        "name": "Paediatric Perinatal & Neonatal Disorders",
        "description": "SNOMED CT codes for paediatric perinatal and neonatal disorders (NHS simple reference set).",
        "snomed_refset_id": "2222221000000101",
        "snomed_query_type": "refset",
        "tags": ["conditions", "paediatric", "neonatal", "perinatal", "snomed"],
        "is_featured": True,
    },
    {
        "key": "snomed_dementia_diagnoses",
        "name": "Dementia Diagnoses (SNOMED CT)",
        "description": "Dementia diagnosis codes (NHS SNOMED CT dementia diagnosis simple reference set).",
        "snomed_refset_id": "999002771000000107",
        "snomed_query_type": "refset",
        "tags": ["conditions", "dementia", "snomed"],
        "is_featured": True,
    },
    # ── Anatomy ───────────────────────────────────────────────────────────
    # Body structure descendants (root 123037004) excluded — the hierarchy is
    # 100k+ concepts; the recursive CTE traversal hangs at seed time and at
    # request time. Use the SNOMED CT typeahead search for anatomy questions.
    {
        "key": "snomed_administration_routes",
        "name": "Drug Administration Routes (SNOMED CT)",
        "description": "Routes of drug administration from dm+d (ePrescribing route of administration refset).",
        "snomed_refset_id": "999000051000001100",
        "snomed_query_type": "refset",
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

    if query_type == "descendants" and refset_id:
        # Count via a recursive CTE COUNT(*) — avoids loading all rows into memory
        try:
            import sqlite3

            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = conn.execute(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT child_id FROM concept_isa WHERE parent_id = ?
                    UNION ALL
                    SELECT ci.child_id
                    FROM concept_isa ci
                    JOIN descendants d ON ci.parent_id = d.id
                )
                SELECT COUNT(*) FROM descendants d
                JOIN concepts c ON c.id = d.id AND c.active = 1
                """,
                (refset_id,),
            ).fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
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
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Delete DataSet records whose keys are no longer in FEATURED_DATASETS",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        prune = options["prune"]

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

        pruned = 0
        if prune:
            active_keys = {defn["key"] for defn in FEATURED_DATASETS}
            stale_qs = DataSet.objects.filter(
                category="snomed", source_type="snomed_db"
            ).exclude(key__in=active_keys)
            stale_keys = list(stale_qs.values_list("key", flat=True))
            if stale_keys:
                if dry_run:
                    for key in stale_keys:
                        self.stdout.write(
                            f"   [DELETE] {key} — no longer in FEATURED_DATASETS"
                        )
                else:
                    stale_qs.delete()
                    pruned = len(stale_keys)
                    for key in stale_keys:
                        self.stdout.write(self.style.WARNING(f"   🗑  pruned: {key}"))
            else:
                self.stdout.write("   ✔  No stale SNOMED datasets to prune.")

        if not dry_run:
            prune_str = f", {pruned} pruned" if prune else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🏥 SNOMED CT seeding complete: "
                    f"{created} created, {updated} updated, {skipped} skipped{prune_str}."
                )
            )
        else:
            self.stdout.write(
                f"\n🔍 Dry run complete: {len(FEATURED_DATASETS)} datasets would be processed."
            )
