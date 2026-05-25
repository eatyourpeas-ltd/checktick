---
title: SNOMED CT Integration
category: features
priority: 6
---

# SNOMED CT Integration

This document covers the design and implementation of SNOMED CT terminology integration in CheckTick. SNOMED CT is the NHS standard clinical terminology, distributed via NHS TRUD and processed locally using the [`sct`](https://github.com/pacharanero/sct) Rust binary.

---

## Implementation Status

### ✅ Phase 1 — Infrastructure (complete, on `feat/snomed-integration`)

| Component                                               | File(s)                                               | Status  |
| ------------------------------------------------------- | ----------------------------------------------------- | ------- |
| `snomed_data` Docker volume                             | `docker-compose.dev.yml`                              | ✅ Done |
| `sct` binary in all images                              | `Dockerfile`, `Dockerfile.dev`, `Dockerfile.registry` | ✅ Done |
| `SNOMED_DB_PATH`, `TRUD_API_KEY` env vars               | `settings.py`, `.env.example`                         | ✅ Done |
| DataSet model fields (6 new fields + choices)           | `models.py`, migration `0047`                         | ✅ Done |
| `SnomedResolver` service                                | `surveys/snomed_resolver.py`                          | ✅ Done |
| `fetch_dataset()` routing for `category='snomed'`       | `surveys/external_datasets.py`                        | ✅ Done |
| `/healthz` SNOMED status                                | `core/views.py`                                       | ✅ Done |
| `seed_snomed_datasets` command (22 curated datasets)    | `management/commands/seed_snomed_datasets.py`         | ✅ Done |
| `update_snomed_db` command (`sct trud check` + rebuild) | `management/commands/update_snomed_db.py`             | ✅ Done |
| Tests (18 passing, offline, mock SQLite)                | `tests/test_snomed_integration.py`                    | ✅ Done |
| `s/dev` SNOMED walkthrough + vault flow fix             | `s/dev`                                               | ✅ Done |
| Self-hosting docs updated                               | `self-hosting*.md`, `vault.md`, `scheduled-tasks.md`  | ✅ Done |

### ✅ Phase 2 — Views and Frontend (complete, on `feat/snomed-phase2-views`)

| Component                                                   | File(s)                                                                                | Status  |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------- |
| Dataset list view — SNOMED badge + live count               | `dataset_list.html`, `views.py`                                                        | ✅ Done |
| Dataset detail view — SNOMED provenance card + live options | `dataset_detail.html`, `views.py`                                                      | ✅ Done |
| Graceful degradation UI                                     | `dataset_list.html`, `dataset_detail.html`                                             | ✅ Done |
| Typeahead API endpoint                                      | `views.snomed_search`, `urls.py`                                                       | ✅ Done |
| SNOMED snapshot (live → Postgres)                           | `views.dataset_snomed_snapshot`, `urls.py`                                             | ✅ Done |
| "Request SNOMED Refset" button + issue template             | `dataset_list.html`, `.github/ISSUE_TEMPLATE/snomed_refset_request.yml`                | ✅ Done |
| Survey builder — dropdown/typeahead widget selection        | Use `snomed_member_count` thresholds (<500 dropdown, 500–2k searchable, >2k typeahead) | ✅ Done |
| Survey renderer — SCTID → preferred term resolution         | Resolve stored SCTIDs to display terms at render time; graceful degradation on absent snomed.db | ✅ Done |
| CSV export — SCTID → preferred term resolution              | Resolve SCTID answers to preferred terms in CSV export via pre-built lookup table      | ✅ Done |
| Survey respondent — SNOMED unavailable message              | Show informative alert instead of empty `<select>` when snomed.db absent               | ✅ Done |
| Builder inline SNOMED unavailable warning                   | Warning banner in dataset picker when snomed.db absent; member count hint on select    | ✅ Done |
| `datasets-and-dropdowns.md` update                          | Document SNOMED datasets for users                                                     | ✅ Done |

### 🔲 Phase 3 — User SNOMED Codelists (future)

See [Phase 2: User SNOMED Codelists](#phase-2-user-snomed-codelists) section below.

---

### Key design constraints for Phase 2

- **SCTIDs are stored in responses**, not display terms — they are semantically stable across SNOMED releases
- **`SnomedUnavailableError` must be caught at the view layer** — never propagate to a 500
- **`snomed_member_count` drives widget selection** — seeded at `seed_snomed_datasets` time, not queried live per request
- **`SnomedResolver.search()` is the typeahead backend** — it queries `snomed.db` FTS5 via thread-local connection
- **The `options` field on SNOMED DataSets is always `[]`** — never write to it; callers must use `fetch_dataset()` which routes through the resolver

---

## Design Overview

### The Core Idea

SNOMED datasets are served **live from a local SQLite database** (`snomed.db`) generated by `sct`. CheckTick holds lightweight **descriptor records** in Postgres (one per exposed refset or concept hierarchy), but the actual terms are never duplicated into Postgres. When a dropdown or typeahead is rendered, Django queries `snomed.db` directly.

This means:

- SNOMED terms are always current — update `snomed.db`, every dropdown updates immediately
- No sync lag or stale data
- Adding a new refset for users is a single descriptor row insert — no data migration
- Self-hosters who haven't set up SNOMED get graceful degradation (SNOMED datasets shown as unavailable)

### What Stays in Postgres

Each exposed SNOMED list has a `DataSet` record in Postgres containing:

- `key`, `name`, `description`, `tags` — for search and display
- `category = "snomed"`
- `snomed_refset_id` — the SNOMED reference set SCTID or root concept SCTID for hierarchy queries
- `snomed_release_date` — the release date of the `snomed.db` used to seed this descriptor
- `options = {}` — always empty for SNOMED datasets; never written to

The `DataSet` record controls **discoverability and access** (tags, permissions, is_global). It does not control the data.

### What Lives in `snomed.db`

The SQLite file is generated once by `sct trud download --edition uk_monolith --pipeline` and stored on a mounted volume (not committed to git). It contains concepts, descriptions, relationships, refsets, and FTS5 indexes — the full UK Monolith edition (~831k concepts).

Path: `/app/data/snomed.db` (configurable via `SNOMED_DB_PATH` env var).

---

## UX and Product Design

### The Tension: Exposure vs Control

SNOMED has 831k concepts. Users should not be able to query arbitrary SNOMED — that creates clinical risk (inappropriate terms surfaced for a given context) and UX problems (overwhelming lists). The maintainer controls which refsets are exposed.

**The model:**

- CheckTick ships a curated registry of exposed SNOMED datasets (seeded via management command)
- Users browse and use these in dropdowns — just like NHS DD datasets today
- Users can **request a new SNOMED refset** via a GitHub issue (same pattern as "Request NHS DD List")
- Maintainer reviews the request, adds a descriptor row, and it's immediately live
- Users can **snapshot** a SNOMED dataset into a custom Postgres-backed dataset if they need a frozen or modified version

### What the Dataset List Shows

The existing `dataset_list.html` shows an **Options** count (`dataset.options|length`). For SNOMED datasets this column needs to show a live count queried from `snomed.db`, or a label like "SNOMED — live" with a concept count badge. The list should also show a SNOMED badge (like the "NHS DD" badge on detail pages) so users understand the source.

Proposed additions to the dataset list:

- A `SNOMED` category filter option
- A "SNOMED unavailable" warning row/banner if `snomed.db` is not present on the host
- A "Request SNOMED Refset" button alongside the existing "Request NHS DD List" button

### What the Dataset Detail Page Shows

The detail page currently iterates `dataset.options.items`. For SNOMED datasets:

- Options are fetched live from `snomed.db` at page load
- Displayed as SCTID → preferred term pairs
- A "Release date" stat replaces "Last scraped"
- The "Create Custom Version" button **snapshots** the live refset into a Postgres-backed custom dataset (useful for users who need a frozen or filtered subset)
- A "SNOMED CT" provenance notice is shown with a link to the SNOMED browser

### User Workflow: Using a SNOMED Dataset in a Survey

1. User adds a dropdown question to their survey
2. They click "Use Dataset"
3. They filter by "SNOMED" category or search for a clinical area (e.g. "allergy", "procedure")
4. They select a refset (e.g. "UK Allergy Substances")
5. When the survey is rendered, the dropdown is populated live from `snomed.db`
6. Responses are stored as SCTID values (not display terms) — semantically stable across SNOMED releases
7. If the user needs a custom/filtered version, they click "Create Custom Version" to snapshot it

### Typeahead (Future)

A second question type — `snomed_typeahead` — could allow free-text search across all 831k concepts using FTS5, for open-ended clinical coding. This is a distinct use case from fixed dropdowns and should be scoped separately.

---

## Curated Refsets and the Full Registry

### How Many Refsets Are There?

The UK Monolith SNOMED edition contains **460 reference sets**. These range from clinically rich datasets (UK Ethnic Categories, QOF indicators, dm+d drug lists) to highly technical/administrative ones (module dependencies, ePrescribing rules, navigation concepts, Summary Care Record exclusions) that are not meaningful as survey dropdown options.

### Three Sources of Drug Lists

For drugs specifically, there are three complementary sources in `snomed.db`, each serving different use cases:

| Source             | How it works                                               | Examples                                              | Best for                                                               |
| ------------------ | ---------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------- |
| **Named refsets**  | Pre-defined curated lists from NHS England                 | QOF Epilepsy drugs, COVID extraction, formulary lists | Disease-specific constrained lists — exactly what survey creators need |
| **dm+d hierarchy** | Descendants of a drug-class concept                        | All GLP-1 agonists, all insulins, all antiepileptics  | Drug class lists without needing a named refset                        |
| **ECL expression** | SNOMED Expression Constraint Language query evaluated live | `<< 372938004` (all GLP-1 agonists), combinations     | Flexible, precise, user-authored — Phase 2/3                           |

**QOF refsets are particularly valuable.** The Quality and Outcomes Framework has ~30+ condition-specific refsets maintained annually by NHS England, which include disease-area drug lists directly relevant to clinical survey creators:

- QOF Epilepsy — antiepileptic medicines used in UK primary care
- QOF Diabetes — diabetes medications (covers T2DM drug classes)
- QOF Atrial Fibrillation — anticoagulants and rate control drugs
- QOF Asthma / COPD — inhaled therapies, bronchodilators
- QOF Hypertension, Heart Failure, Mental Health, Dementia, and more

These are already in the UK Monolith and will be auto-seeded as descriptor rows. They should be `is_featured = True`.

**dm+d hierarchy queries** cover drug classes where no named refset exists:

- GLP-1 agonists: descendants of `372938004`
- SGLT2 inhibitors: descendants of `703673008`
- All insulins: descendants of `67866001`

These are added as `snomed_query_type = "descendants"` descriptor rows — the `SnomedResolver` queries `snomed.db` for all active descendants at render time.

### Supporting All 460 — With a Featured Flag

Rather than maintaining a hand-picked short list in code, the `seed_snomed_datasets` command will auto-generate a `DataSet` descriptor row for **every refset** found in `snomed.db` (via `sct refset list --json`). 460 Postgres rows is trivial.

The distinction is managed with an `is_featured` boolean on the descriptor:

| `is_featured` | Meaning                                        | Default visibility                                         |
| ------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| `True`        | Curated, clinically meaningful for NHS surveys | Shown prominently in the dataset browser                   |
| `False`       | Technical, administrative, or specialist       | Hidden by default; searchable; can be promoted per request |

This means:

- Users browsing datasets by default see a curated set of clinically useful refsets (QOF disease lists, ethnic categories, allergy substances, body sites, drug classes)
- Any of the 460 can be surfaced via search or admin promotion — no code change needed
- Real usage patterns will reveal which unlisted refsets are actually wanted
- The maintainer promotes a refset to `is_featured = True` in the Django admin — immediately visible

The seeding command applies a heuristic to set `is_featured = True` for refsets whose names match known clinical patterns (e.g. "ethnic", "allerg", "QOF", "dm+d", "GLP", "diabetes", "epilep", "hypertension"), with everything else defaulting to `False`.

### Member Count and Size Warning

Some refsets are very large (dm+d VMP has ~20,000+ members). The seed command should record the member count from `snomed.db` at seed time. The UI steers users to the appropriate interaction based on size:

- **< 500 items** → standard dropdown
- **500–2,000 items** → searchable select (select2 / combobox)
- **> 2,000 items** → typeahead search required; UI enforces this and prevents use as a plain dropdown

This means dm+d VMP (all ~20,000 medicinal products) is available for typeahead questions, while QOF Epilepsy drugs (~30–50 items) work perfectly as a constrained dropdown. Survey creators get both experiences automatically, guided by the data.

### Initial Featured Refsets

To be confirmed against a live `snomed.db` — the names below are indicative. Actual SCTID/member counts require running `sct refset list` against the UK Monolith:

| Type         | Dataset Name                            | Source             | Approx Size |
| ------------ | --------------------------------------- | ------------------ | ----------- |
| Named refset | UK Ethnic Categories                    | UK Monolith        | ~30         |
| Named refset | QOF Epilepsy — drug list                | QOF module         | ~40         |
| Named refset | QOF Diabetes — drug list                | QOF module         | ~60         |
| Named refset | QOF Atrial Fibrillation — drug list     | QOF module         | ~20         |
| Named refset | QOF COPD / Asthma — drug list           | QOF module         | ~50         |
| Named refset | Allergy/intolerance substances          | UK Clinical        | ~300        |
| Named refset | dm+d VTM (all drug substances)          | dm+d               | ~1,000      |
| Named refset | dm+d VMP (all medicinal products)       | dm+d               | ~20,000+ ⚠️ |
| Hierarchy    | GLP-1 agonists                          | dm+d descendants   | ~15         |
| Hierarchy    | SGLT2 inhibitors                        | dm+d descendants   | ~10         |
| Hierarchy    | All insulins                            | dm+d descendants   | ~50         |
| Named refset | QOF Diabetes register (conditions)      | QOF module         | ~100–400    |
| Named refset | QOF Epilepsy register (conditions)      | QOF module         | ~100–400    |
| Named refset | QOF Hypertension register               | QOF module         | ~100–400    |
| Named refset | QOF CHD / Heart Failure register        | QOF module         | ~100–400    |
| Named refset | QOF AF register                         | QOF module         | ~100–400    |
| Named refset | QOF Asthma / COPD register              | QOF module         | ~100–400    |
| Named refset | QOF Cancer register                     | QOF module         | ~100–400    |
| Named refset | QOF Mental Health / Depression register | QOF module         | ~100–400    |
| Named refset | QOF Dementia register                   | QOF module         | ~100–400    |
| Named refset | QOF Stroke / TIA register               | QOF module         | ~100–400    |
| Named refset | Specialty procedure refsets             | UK Clinical        | TBD         |
| Hierarchy    | Common body sites                       | SNOMED descendants | ~500        |
| Hierarchy    | Administration methods                  | SNOMED descendants | ~50         |

> ⚠️ dm+d VMP is typeahead-only. The UI enforces this based on `snomed_member_count > 2000`.

> **Note for implementer:** Run `sct refset list --json --db snomed.db | grep -i "QOF\|diabet\|epilep\|atrial\|asthma\|copd\|ethnic\|allerg\|hypert\|cancer\|mental\|dementia\|stroke"` against the UK Monolith to get the actual SCTIDs and member counts before seeding.

### Conditions and Procedures — Same Architecture, Different Scale

The three-tier approach (named refsets → hierarchy descendants → ECL) applies equally to conditions/disease states and procedures. The key differences from drugs:

**Conditions:**

- QOF condition _registers_ define which SNOMED codes count as a diagnosis for QOF purposes — these are the most clinically validated, constrained lists available and sit at ~100–400 concepts each (searchable select territory)
- Specialty-scoped hierarchy descendants work for typeahead (all diabetic disorders, all epilepsies, all cancers), but the full clinical finding hierarchy is ~400k concepts — never used unscoped
- ICD-10 mapping is present in the UK Monolith (`snomed_query_type = "mapped"`) — useful for surveys that need to align with HES/hospital coding

**Procedures:**

- **OPCS-4** is the NHS standard for procedure coding in secondary care (theatre records, HES). The UK Monolith contains a SNOMED-OPCS-4 map. For surveys used in secondary care audit, OPCS-4 procedure codes will often be more recognisable to users than raw SNOMED procedure concepts — worth exposing via `snomed_query_type = "mapped"`
- Specialty procedure refsets exist in the UK Clinical module (to be confirmed against live `snomed.db`)
- Full procedure hierarchy is ~80k concepts — typeahead only when unscoped

**Size profile comparison:**

| Category   | QOF register | Specialty scoped | Full hierarchy |
| ---------- | ------------ | ---------------- | -------------- |
| Drugs      | ~20–60       | ~100–500         | ~20,000+ (VMP) |
| Conditions | ~100–400     | ~500–2,000       | ~400,000+      |
| Procedures | ~50–200      | ~1,000–5,000     | ~80,000+       |

The size thresholds (< 500 → dropdown, 500–2,000 → searchable select, > 2,000 → typeahead) apply uniformly across all three domains.

### Phase 2/3: User-Authored Lists (ECL and Codelists)

Survey creators who need a bespoke list — e.g. "all GLP-1 agonists licensed in the UK that are also on our local formulary", or "the 12 SNOMED codes we use for epilepsy in our service" — need either ECL or hand-picked codelists. Both apply equally to drugs, conditions, and procedures.

**ECL** uses the `snomed_query_type = "ecl"` path, evaluating an arbitrary Expression Constraint Language query against `snomed.db` at render time. ECL is powerful but requires SNOMED knowledge to author safely. The roadmap:

1. **Phase 2:** Admins can write ECL expressions via the Django admin and expose them as featured datasets — no user-facing UI yet
2. **Phase 3:** A guided ECL builder UI for technically confident users, with validation and concept preview before saving

**Codelists** (hand-picked concept-by-concept) are distinct — see the Phase 2 User SNOMED Codelists section below. ECL is class/hierarchy-based; codelists are concept-by-concept.

---

## Model Changes

### 1. Add `"snomed"` to `DataSet.CATEGORY_CHOICES`

```python
CATEGORY_CHOICES = [
    ("nhs_dd", "NHS Data Dictionary"),
    ("external_api", "External API"),
    ("user_created", "User Created"),
    ("rcpch", "RCPCH API"),
    ("snomed", "SNOMED CT"),          # NEW
]
```

### 2. Add `"snomed_db"` to `DataSet.SOURCE_TYPE_CHOICES`

```python
SOURCE_TYPE_CHOICES = [
    ("api", "External API"),
    ("manual", "Manual Entry"),
    ("imported", "Imported from File"),
    ("scrape", "Web Scraping"),
    ("snomed_db", "SNOMED CT Database"),  # NEW
]
```

### 3. Add SNOMED-specific fields to `DataSet`

```python
snomed_refset_id = models.CharField(
    max_length=30,
    blank=True,
    help_text="SNOMED CT reference set SCTID or root concept SCTID for hierarchy queries",
)
snomed_query_type = models.CharField(
    max_length=20,
    blank=True,
    choices=[
        ("refset", "Reference Set"),
        ("descendants", "All Descendants of Concept"),
        ("ecl", "ECL Expression"),
    ],
    help_text="How to query snomed.db for this dataset's terms",
)
snomed_ecl = models.TextField(
    blank=True,
    help_text="SNOMED ECL expression (if query_type = ecl)",
)
snomed_release_date = models.DateField(
    null=True,
    blank=True,
    help_text="Release date of the snomed.db used when this descriptor was created",
)
snomed_member_count = models.IntegerField(
    null=True,
    blank=True,
    help_text="Number of concepts in this refset at last seed; used to warn if too large for a dropdown",
)
is_featured = models.BooleanField(
    default=False,
    db_index=True,
    help_text="For SNOMED datasets: True = shown prominently in dataset browser; False = hidden by default but searchable",
)
```

> Migration: `0025_dataset_snomed_fields.py`
>
> `is_featured` is SNOMED-specific in intent but lives on the base model — it could also be used in future for other terminology systems.

---

## New Service: `SnomedResolver`

A service class (`checktick_app/surveys/snomed_resolver.py`) that:

- Holds a connection (or connection pool) to `snomed.db`
- Provides `get_options(dataset: DataSet) -> dict[str, str]` — returns `{sctid: preferred_term}` for any SNOMED dataset
- Provides `search(query: str, limit: int) -> list[dict]` — FTS5 search for typeahead
- Raises `SnomedUnavailableError` if `snomed.db` is not found at `SNOMED_DB_PATH`
- Is used by views and the dropdown renderer — never by management commands

The existing `DataSet.get_options()` method (or equivalent) should route through `SnomedResolver` when `dataset.category == "snomed"`.

### Connection Strategy

`snomed.db` is opened read-only (`?mode=ro`) as a separate SQLite connection. Django's ORM is not used. Connection is opened lazily per-request (SQLite read-only connections are cheap and safe for concurrent reads). A module-level cached connection with thread-local storage is appropriate.

```python
SNOMED_DB_PATH = settings.SNOMED_DB_PATH  # from env, default /app/data/snomed.db
```

---

## Setup and Self-Hosting

### Prerequisites

1. TRUD account with subscription to SNOMED CT UK Monolith Edition (item 1799)
2. `sct` binary installed on the host or in the Docker image
3. TRUD API key available as `TRUD_API_KEY` environment variable
4. A persistent volume mounted at `/app/data/` (or configured path)

### One-Time Database Generation

```bash
# Download and build snomed.db (takes ~2 minutes)
TRUD_API_KEY=your-key-here sct trud download --edition uk_monolith --pipeline

# Move to the expected path
mv snomed.db /app/data/snomed.db
```

Or from inside the Docker container:

```bash
docker compose exec web bash -c "TRUD_API_KEY=\$TRUD_API_KEY sct trud download --edition uk_monolith --pipeline --output /app/data/snomed.db"
```

### Seed SNOMED Dataset Descriptors

Once `snomed.db` exists, seed the Postgres descriptors:

```bash
docker compose exec web python manage.py seed_snomed_datasets
```

This creates `DataSet` records for all curated refsets listed above. It does **not** copy data into Postgres — it only creates the descriptor rows. Safe to re-run (idempotent).

### Environment Variables

```bash
# Path to the snomed.db file (default: /app/data/snomed.db)
SNOMED_DB_PATH=/app/data/snomed.db

# TRUD API key (for downloading new releases)
TRUD_API_KEY=your-trud-api-key
```

---

## Management Commands

### `seed_snomed_datasets`

Creates (or updates) `DataSet` descriptor records for all curated SNOMED refsets. Does not touch `snomed.db` data. Safe to re-run.

```bash
python manage.py seed_snomed_datasets
python manage.py seed_snomed_datasets --dataset snomed_allergy_substances
python manage.py seed_snomed_datasets --dry-run
```

### `update_snomed_db`

Downloads the latest SNOMED CT UK Monolith release from TRUD (if newer than current), runs `sct ndjson` + `sct sqlite` to rebuild `snomed.db`, and updates `snomed_release_date` on all SNOMED dataset descriptors.

```bash
python manage.py update_snomed_db
python manage.py update_snomed_db --force   # re-download even if current
python manage.py update_snomed_db --dry-run # check for new release only
```

This command:

1. Calls `sct trud list --edition uk_monolith` to check the latest release date
2. Compares with the stored `snomed_release_date` on existing descriptors
3. If newer: downloads and rebuilds `snomed.db` via `sct trud download --pipeline`
4. Updates `snomed_release_date` on all `DataSet` records with `category="snomed"`
5. Logs to audit log

---

## Cron Jobs / Scheduled Tasks

SNOMED CT UK is published **twice a year** (typically April and October).

**Recommended schedule:** Weekly check (Mondays, 6 AM UTC) — cheap when no new release, automatic when one is published.

```cron
0 6 * * 1 cd /app && python manage.py update_snomed_db
```

TRUD has maintenance windows (weekdays 18:00–08:00 UK time, and midnight–06:00). The weekly Monday morning schedule avoids these.

**Northflank setup:**

1. Create a Cron Job service named `checktick-snomed-update`
2. Schedule: `0 6 * * 1`
3. Command: `python manage.py update_snomed_db`
4. Add `TRUD_API_KEY` and `SNOMED_DB_PATH` to environment variables
5. Mount the same persistent volume as the web service at `/app/data/`

---

## Northflank Deployment

### The `snomed.db` Volume

`snomed.db` for the UK Monolith edition is approximately **500 MB–1 GB** on disk. It must be stored on a persistent volume shared between:

- The **web service** (reads `snomed.db` at request time to serve options)
- The **`checktick-snomed-update` cron job** (writes a new `snomed.db` on release)

The `sct trud download --pipeline` command writes the rebuilt database to the same path atomically, so there is no risk of a partially-written file being read mid-update.

### Container Storage vs Volume — Important Distinction

The web service currently runs on `nf-compute-50` (0.5 vCPU / 1024 MB RAM / 1024 MB ephemeral container storage).

**The final `snomed.db` goes to the volume — not the container storage.** The web service reads it with lightweight SQLite queries at request time, which is well within 1024 MB RAM.

**The build process is the constraint.** `sct trud download --pipeline` produces intermediate files before the final `snomed.db` exists:

| Step             | Artifact               | Approximate Size |
| ---------------- | ---------------------- | ---------------- |
| Download RF2 zip | temp download          | ~1.5 GB          |
| `sct ndjson`     | `.ndjson` intermediate | ~1 GB+           |
| `sct sqlite`     | final `snomed.db`      | ~500 MB–1 GB     |

Peak disk usage during the build is approximately **3.5 GB** (all three files simultaneously). This exceeds the container's 1024 MB ephemeral storage. **The build process must be directed to write all intermediate and output files to the mounted volume**, not to the container's working directory:

```bash
# All temp and output files go to the volume, not container ephemeral storage
sct trud download --edition uk_monolith \
  --download-dir /app/data \
  --pipeline \
  --output /app/data/snomed.db
```

The `update_snomed_db` management command must pass these flags. With the 10 GB volume, peak usage (~3.5 GB) is comfortably within limits.

**Memory (1024 MB RAM):** Sufficient. `sct` is specifically designed to avoid loading the full dataset into RAM — this is its key advantage over Snowstorm (which required 24 GB Java heap and still ran out of memory on the full UK Monolith). The build process should peak well under 1 GB RAM.

### Compute Spec: Web Service vs Cron Job

The cron job does the heavy lifting (download + build, ~2 minutes). The web service just reads. Give them **different compute specs**:

| Service                            | Recommended Spec                     | Reason                                               |
| ---------------------------------- | ------------------------------------ | ---------------------------------------------------- |
| Web service                        | `nf-compute-50` (current)            | Read-only SQLite queries; lightweight                |
| `checktick-snomed-update` cron job | `nf-compute-200` (2 vCPU / 4 GB RAM) | Download + build needs headroom; runs at most weekly |

The cron job's higher spec only costs money when it's actually running — Northflank bills by the second for job services, so a 2-minute build on `nf-compute-200` is negligible.

### Can I Reuse the Existing `vault-data` Volume?

**No.** The `vault-data` volume is used exclusively by the HashiCorp Vault service for encrypted key storage and Raft consensus data. Vault uses Raft's integrated storage backend, which writes its own binary data files directly inside the volume (`/vault/data`). Mixing `snomed.db` into the same volume would be fragile and could interfere with Vault's storage layer.

> **What `vault-data` stores:** Vault Raft data (encrypted key material, audit logs, lease metadata). It does not store application data of any kind and should remain dedicated to Vault.

### Create a New Volume

You need a new dedicated volume. Northflank's minimum volume size is **10 GB** — this is comfortably sufficient given the ~3.5 GB peak during builds and ~1 GB at rest.

**Recommended name:** `snomed-data`

**Mount path:** `/app/data` (configurable via `SNOMED_DB_PATH`)

#### Setup Steps on Northflank

1. **Create the volume:**
   - Northflank dashboard → your project → **Volumes** → **New Volume**
   - Name: `snomed-data`
   - Size: `10 GB` (minimum; sufficient for the foreseeable future)
   - Storage class: standard (no need for SSD — `snomed.db` reads are sequential and infrequent)

2. **Mount to the web service:**
   - Web service → **Volumes** → **Add Volume Mount**
   - Volume: `snomed-data`
   - Mount path: `/app/data`

3. **Mount to the cron job service:**
   - `checktick-snomed-update` cron job → **Volumes** → **Add Volume Mount**
   - Same volume: `snomed-data`
   - Same mount path: `/app/data`
   - Set compute spec to `nf-compute-200` for the build headroom

4. **Add environment variables to both services:**

   ```
   SNOMED_DB_PATH=/app/data/snomed.db
   TRUD_API_KEY=<your-trud-api-key>
   ```

   > `TRUD_API_KEY` is only strictly needed by the cron job, but having it on both is harmless and simplifies env management.

5. **Install `sct` in the Docker image** (see [Docker Image Changes](#docker-image-changes) below).

6. **Run initial setup** via the Northflank shell on the web service:
   ```bash
   python manage.py update_snomed_db
   python manage.py seed_snomed_datasets
   ```

### Docker Image Changes

The `sct` binary must be available in the Docker image for the `update_snomed_db` management command to call it. Add to the `Dockerfile`:

```dockerfile
# Install sct binary for SNOMED CT database generation
RUN curl -fsSL https://raw.githubusercontent.com/pacharanero/sct/main/install.sh | sh
ENV PATH="$HOME/.local/bin:$PATH"
```

Or pin a specific release version for reproducibility (recommended for production):

```dockerfile
ARG SCT_VERSION=v0.3.9
RUN curl -fsSL https://raw.githubusercontent.com/pacharanero/sct/main/install.sh \
    | SCT_VERSION=${SCT_VERSION} SCT_INSTALL_DIR=/usr/local/bin sh
```

The `sct` binary is only invoked by the management command (not at request time), so it does not need to be in the web process's hot path.

### Cron Job Summary for Northflank

| Service                   | Schedule    | Command                                   | Volume                      | Purpose                                        |
| ------------------------- | ----------- | ----------------------------------------- | --------------------------- | ---------------------------------------------- |
| `checktick-snomed-update` | `0 6 * * 1` | `python manage.py update_snomed_db`       | `snomed-data` → `/app/data` | Check TRUD, rebuild `snomed.db` if new release |
| `checktick-nhs-dd-sync`   | `0 5 * * 0` | `python manage.py sync_nhs_dd_datasets`   | —                           | Existing NHS DD scrape                         |
| `checktick-dataset-sync`  | `0 4 * * *` | `python manage.py sync_external_datasets` | —                           | Existing RCPCH API sync                        |

See [Self-hosting Scheduled Tasks](self-hosting-scheduled-tasks.md) for the general cron job setup guide.

---

## Views and UI Layer

### Changes to Dataset List View (`dataset_list.html`)

- Add `"snomed"` to the category filter dropdown
- The "Options" column: for SNOMED datasets, show live count from `snomed.db` (or "Live — N concepts" badge). If `snomed.db` is unavailable, show "Unavailable" with a warning icon.
- Add a `SNOMED` category badge (distinct colour — e.g. purple) to dataset rows
- Add a "Request SNOMED Refset" button (links to a GitHub issue template) alongside the existing "Request NHS DD List" button
- Show a site-wide warning banner if `SNOMED_DB_PATH` is set but `snomed.db` is missing

### Changes to Dataset Detail View (`dataset_detail.html`)

- For SNOMED datasets, options are fetched live and paginated (not iterated from `dataset.options.items`)
- Show a "SNOMED CT" provenance card: release date, refset SCTID, link to NHS SNOMED browser
- "Create Custom Version" snapshots the live options into a new Postgres-backed `user_created` dataset — users get a frozen copy they can filter
- Replace "Last scraped" stat with "SNOMED release date"
- Show SCTID as the key and preferred term as the value (same two-column layout as today)

### Changes to Survey Builder Dropdown Question Component

- When a user selects a SNOMED dataset for a dropdown question, the options are loaded via an AJAX call that queries `snomed.db`
- Responses are stored as SCTIDs (not display terms) — this is semantically stable across SNOMED releases
- The survey renderer resolves SCTIDs to preferred terms at render time from `snomed.db` (for display in results/exports)

### Graceful Degradation

If `snomed.db` is not present:

- SNOMED datasets appear in the list with a "Unavailable" badge
- Attempting to use one in a survey builder shows an inline warning
- Existing surveys using SNOMED datasets show a placeholder in place of the dropdown
- No 500 errors — `SnomedUnavailableError` is caught and handled at the view layer

---

## Phase 2: User SNOMED Codelists

> Not in scope for the initial implementation. Captured here for future planning.

### What This Is

Users building clinical surveys sometimes need a **hand-picked subset of SNOMED concepts** specific to their service — e.g. "the 15 diagnosis codes used in our paediatric diabetes MDT". This is different from:

- A CheckTick-curated refset (top-down, maintained by the platform)
- A plain custom dataset (not SNOMED-backed, no SCTIDs)

A SNOMED codelist is a user-authored list of SCTIDs with a name and description, stored as a `DataSet` with `category="snomed"` and `source_type="user_codelist"`. Options are stored as `{sctid: preferred_term}` snapshots in Postgres (not live from `snomed.db`), since the user has deliberately chosen these specific concepts and a frozen copy is appropriate.

### Why Phase 2

1. **Phase 1 already covers most practical needs**: the "Create Custom Version / snapshot" flow lets users take a curated CheckTick refset and filter it down. This handles the majority of use cases without a concept picker UI.

2. **Requires FTS5 typeahead first**: users need to search across all 831k SNOMED concepts to find and pick codes. That open search UI is a distinct feature and a prerequisite.

3. **Significant UX investment**: concept search, hierarchy browsing, individual concept selection, codelist management — this is a substantial feature in its own right.

4. **Clinical safety consideration**: should there be any guardrails on which concepts a user can include in a codelist (e.g. only active concepts, only specific hierarchies)? This needs a policy decision before implementation.

### Integration with `sct`

`sct` does not currently have a `codelist` subcommand. If it gains one (a feature worth requesting from the maintainer), it could support defining a codelist as a flat file of SCTIDs and then querying, expanding, or validating it against `snomed.db`. CheckTick could import such files directly, which would be a clean integration for technically-inclined users.

A potential workflow:

```
# User defines a codelist externally (e.g. using sct or OpenCodelists)
# and uploads the SCTID list to CheckTick
# → CheckTick resolves preferred terms from snomed.db
# → Stores as a user_codelist DataSet in Postgres
```

### Sharing and Governance

User codelists could be shared within an organisation or published globally (same permission model as today's custom datasets). Published SNOMED codelists would carry a "user-maintained" flag to distinguish them from CheckTick-curated refsets — important for clinical credibility.

---

## Other Terminology Systems (Future)

The architecture above is designed to extend. If `sct` gains support for other terminologies (LOINC, ICD-11), or separate tools produce equivalent SQLite files, CheckTick can add:

- A `loinc.db` at a configurable path (`LOINC_DB_PATH`)
- `category = "loinc"` on `DataSet`
- A `LoincResolver` following the same pattern as `SnomedResolver`
- `seed_loinc_datasets` and `update_loinc_db` management commands

The `DataSet` model and the UI layer need no further changes — they already abstract over category. The resolver is the only new piece per terminology.

**Recommendation for the `sct` maintainer:** a consistent SQLite schema across terminologies (concepts table with `id`, `preferred_term`, FTS5) would allow CheckTick to use a single generic `TerminologyResolver` rather than one per system.

**DSM-5:** Proprietary — licensing would need to be resolved before including. Out of scope unless a freely-licensable structured form is identified.

**ICD-11:** WHO publishes ICD-11 via a free REST API (`id.who.int`). Could be implemented as an `external_api` dataset source without needing a local SQLite file, at the cost of network dependency.

---

## Related Documentation

- [Datasets and Dropdowns](datasets-and-dropdowns.md) — user guide
- [Self-hosting Datasets](self-hosting-datasets.md) — existing setup guide (update with SNOMED section)
- [Scheduled Tasks](self-hosting-scheduled-tasks.md) — cron job setup
- [`sct` project](https://github.com/pacharanero/sct) — the Rust binary that generates `snomed.db`
- [NHS TRUD](https://isd.digital.nhs.uk/trud) — source of SNOMED CT releases
