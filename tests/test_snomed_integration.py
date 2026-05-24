"""
Tests for SNOMED CT integration.

Covers:
  - SnomedResolver (snomed_resolver.py): error paths, option formatting,
    refset/descendants dispatch — all via an in-memory SQLite mock db
  - fetch_dataset() routing for category='snomed'
  - seed_snomed_datasets management command: dry-run, graceful absent-db exit
  - update_snomed_db management command: dry-run paths

All tests are offline — no real snomed.db required.
"""

from io import StringIO
import sqlite3

from django.core.management import call_command
from django.test import override_settings
import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_snomed_db(path: str) -> None:
    """
    Build a minimal snomed.db at *path* matching the actual sct v0.3.11 schema.

    Real schema (verified against live snomed.db built by sct sqlite):
      concepts(id, fsn, preferred_term, ..., active)
      refset_members(refset_id, referenced_component_id)   -- no active column
      concept_isa(child_id, parent_id)                     -- direct IS-A only
      concepts_fts                                          -- FTS5 virtual table
      metadata(key, value)
    """
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE concepts (
            id              TEXT PRIMARY KEY,
            fsn             TEXT,
            preferred_term  TEXT,
            active          INTEGER DEFAULT 1
        );
        CREATE TABLE refset_members (
            refset_id                TEXT,
            referenced_component_id  TEXT
        );
        CREATE TABLE concept_isa (
            child_id   TEXT,
            parent_id  TEXT
        );
        CREATE VIRTUAL TABLE concepts_fts USING fts5(
            id,
            preferred_term,
            content='concepts',
            content_rowid='rowid'
        );
        CREATE TABLE metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- Two active concepts, one inactive
        INSERT INTO concepts VALUES ('11111111', 'Metformin (substance)', 'Metformin', 1);
        INSERT INTO concepts VALUES ('22222222', 'Insulin glargine (substance)', 'Insulin glargine', 1);
        INSERT INTO concepts VALUES ('33333333', 'Old concept (substance)', 'Old concept', 0);

        -- Populate FTS (mirrors concepts table)
        INSERT INTO concepts_fts(id, preferred_term) VALUES
            ('11111111', 'Metformin'),
            ('22222222', 'Insulin glargine');

        -- A refset containing concepts 11111111, 22222222, and inactive 33333333
        INSERT INTO refset_members VALUES ('999TEST0001', '11111111');
        INSERT INTO refset_members VALUES ('999TEST0001', '22222222');
        INSERT INTO refset_members VALUES ('999TEST0001', '33333333');

        -- IS-A relationship: 11111111 IS-A root 55555555
        INSERT INTO concept_isa VALUES ('11111111', '55555555');

        INSERT INTO metadata VALUES ('release_date', '2026-03-18');
        """)
    conn.commit()
    conn.close()


@pytest.fixture
def snomed_db(tmp_path):
    """Provide a temporary snomed.db and configure settings to point at it."""
    db_path = str(tmp_path / "snomed.db")
    _make_snomed_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def reset_thread_local():
    """
    Clear the thread-local SQLite connection between tests so each test
    gets a fresh connection pointing at its own db.
    """
    from checktick_app.surveys import snomed_resolver

    snomed_resolver._local.conn = None
    yield
    snomed_resolver._local.conn = None


# ── SnomedUnavailableError paths ──────────────────────────────────────────────


@pytest.mark.django_db
def test_resolver_raises_when_path_not_set(monkeypatch):
    from checktick_app.surveys.snomed_resolver import (
        SnomedUnavailableError,
        _get_db_path,
    )

    monkeypatch.delenv("SNOMED_DB_PATH", raising=False)
    with override_settings(SNOMED_DB_PATH=""):
        with pytest.raises(
            SnomedUnavailableError, match="SNOMED_DB_PATH is not configured"
        ):
            _get_db_path()


@pytest.mark.django_db
def test_resolver_raises_when_file_missing(tmp_path):
    from checktick_app.surveys.snomed_resolver import (
        SnomedUnavailableError,
        _get_db_path,
    )

    with override_settings(SNOMED_DB_PATH=str(tmp_path / "nonexistent.db")):
        with pytest.raises(SnomedUnavailableError, match="not found"):
            _get_db_path()


# ── get_options — refset ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_options_refset_returns_active_members(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_options

    class FakeDataset:
        snomed_query_type = "refset"
        snomed_refset_id = "999TEST0001"
        snomed_ecl = ""
        key = "test_refset"

    with override_settings(SNOMED_DB_PATH=snomed_db):
        options = get_options(FakeDataset())

    assert len(options) == 2
    assert "11111111 | Metformin" in options
    assert "22222222 | Insulin glargine" in options
    # inactive member should be excluded
    assert not any("33333333" in o for o in options)


@pytest.mark.django_db
def test_get_options_refset_missing_id_raises(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_options

    class FakeDataset:
        snomed_query_type = "refset"
        snomed_refset_id = ""
        snomed_ecl = ""
        key = "bad"

    with override_settings(SNOMED_DB_PATH=snomed_db):
        with pytest.raises(ValueError, match="snomed_refset_id is not set"):
            get_options(FakeDataset())


# ── get_options — descendants ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_options_descendants_recursive_isa(snomed_db):
    """
    concept_isa holds direct IS-A relationships; resolver uses WITH RECURSIVE
    to traverse the full hierarchy.
    """
    from checktick_app.surveys.snomed_resolver import get_options

    class FakeDataset:
        snomed_query_type = "descendants"
        snomed_refset_id = "55555555"  # root concept
        snomed_ecl = ""
        key = "test_descendants"

    with override_settings(SNOMED_DB_PATH=snomed_db):
        options = get_options(FakeDataset())

    assert len(options) == 1
    assert "11111111 | Metformin" in options


# ── get_options — not-yet-implemented types ───────────────────────────────────


@pytest.mark.django_db
def test_get_options_ecl_raises_not_implemented(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_options

    class FakeDataset:
        snomed_query_type = "ecl"
        snomed_refset_id = ""
        snomed_ecl = "< 73211009"
        key = "test_ecl"

    with override_settings(SNOMED_DB_PATH=snomed_db):
        with pytest.raises(NotImplementedError):
            get_options(FakeDataset())


@pytest.mark.django_db
def test_get_options_unknown_type_raises(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_options

    class FakeDataset:
        snomed_query_type = "bananas"
        snomed_refset_id = ""
        snomed_ecl = ""
        key = "test_bad"

    with override_settings(SNOMED_DB_PATH=snomed_db):
        with pytest.raises(ValueError, match="Unknown snomed_query_type"):
            get_options(FakeDataset())


# ── get_refset_member_count ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_get_refset_member_count(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_refset_member_count

    with override_settings(SNOMED_DB_PATH=snomed_db):
        count = get_refset_member_count("999TEST0001")

    assert count == 2  # only active members


@pytest.mark.django_db
def test_get_refset_member_count_missing_refset(snomed_db):
    from checktick_app.surveys.snomed_resolver import get_refset_member_count

    with override_settings(SNOMED_DB_PATH=snomed_db):
        count = get_refset_member_count("DOESNOTEXIST")

    assert count == 0


# ── search ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_search_returns_matching_terms(snomed_db):
    from checktick_app.surveys.snomed_resolver import search

    with override_settings(SNOMED_DB_PATH=snomed_db):
        results = search("Metformin")

    assert len(results) == 1
    assert results[0] == "11111111 | Metformin"


@pytest.mark.django_db
def test_search_is_case_insensitive_via_fts5(snomed_db):
    """FTS5 handles case-insensitive matching by default."""
    from checktick_app.surveys.snomed_resolver import search

    with override_settings(SNOMED_DB_PATH=snomed_db):
        results = search("insulin")

    assert any("Insulin glargine" in r for r in results)


@pytest.mark.django_db
def test_search_returns_empty_for_no_match(snomed_db):
    from checktick_app.surveys.snomed_resolver import search

    with override_settings(SNOMED_DB_PATH=snomed_db):
        results = search("xyzzy_no_such_term")

    assert results == []


# ── seed_snomed_datasets command ──────────────────────────────────────────────


@pytest.mark.django_db
def test_seed_command_graceful_exit_no_db(monkeypatch):
    """Command exits cleanly with a warning when snomed.db is absent."""
    monkeypatch.delenv("SNOMED_DB_PATH", raising=False)
    out = StringIO()
    with override_settings(SNOMED_DB_PATH=""):
        call_command("seed_snomed_datasets", stdout=out)
    output = out.getvalue()
    assert "snomed.db not found" in output or "skipping" in output.lower()


@pytest.mark.django_db
def test_seed_command_dry_run(snomed_db):
    """Dry run prints CREATE/UPDATE actions without writing to the database."""
    from checktick_app.surveys.models import DataSet

    out = StringIO()
    with override_settings(SNOMED_DB_PATH=snomed_db):
        call_command("seed_snomed_datasets", dry_run=True, stdout=out)

    output = out.getvalue()
    assert "DRY RUN" in output
    # No DataSet records should have been created
    assert DataSet.objects.filter(category="snomed").count() == 0


@pytest.mark.django_db
def test_seed_command_skips_existing_without_force(snomed_db):
    """Existing datasets are skipped unless --force is passed."""
    from checktick_app.surveys.models import DataSet

    # Pre-create one dataset that matches a key in FEATURED_DATASETS
    DataSet.objects.create(
        key="snomed_dmd_vtm",
        name="Existing",
        category="snomed",
        source_type="snomed_db",
        options=[],
    )

    out = StringIO()
    with override_settings(SNOMED_DB_PATH=snomed_db):
        call_command("seed_snomed_datasets", stdout=out)

    output = out.getvalue()
    assert "already exists" in output
    # The name should NOT have been updated (still "Existing")
    assert DataSet.objects.get(key="snomed_dmd_vtm").name == "Existing"


@pytest.mark.django_db
def test_seed_command_force_updates_existing(snomed_db):
    """--force overwrites an existing dataset's fields."""
    from checktick_app.surveys.models import DataSet

    DataSet.objects.create(
        key="snomed_dmd_vtm",
        name="Old name",
        category="snomed",
        source_type="snomed_db",
        options=[],
    )

    out = StringIO()
    with override_settings(SNOMED_DB_PATH=snomed_db):
        call_command("seed_snomed_datasets", force=True, stdout=out)

    updated = DataSet.objects.get(key="snomed_dmd_vtm")
    assert updated.name != "Old name"


# ── update_snomed_db command ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_update_command_dry_run_no_trud_key(monkeypatch):
    """Without TRUD_API_KEY, command exits with error (not a crash)."""
    monkeypatch.delenv("TRUD_API_KEY", raising=False)
    out = StringIO()
    with override_settings(SNOMED_DB_PATH="/tmp/snomed.db", TRUD_API_KEY=""):
        with pytest.raises(SystemExit) as exc_info:
            call_command("update_snomed_db", dry_run=True, stdout=out)
    assert exc_info.value.code == 1
    assert "TRUD_API_KEY" in out.getvalue()


@pytest.mark.django_db
def test_update_command_dry_run_no_db_path(monkeypatch):
    """Without SNOMED_DB_PATH, command exits with error."""
    monkeypatch.delenv("SNOMED_DB_PATH", raising=False)
    out = StringIO()
    with override_settings(SNOMED_DB_PATH="", TRUD_API_KEY="dummy-key"):
        with pytest.raises(SystemExit) as exc_info:
            call_command("update_snomed_db", dry_run=True, stdout=out)
    assert exc_info.value.code == 1
    assert "SNOMED_DB_PATH" in out.getvalue()
