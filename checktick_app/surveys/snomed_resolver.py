"""
SNOMED CT Resolver

Serves terminology options live from a local snomed.db SQLite file built by
the `sct` binary (https://github.com/pacharanero/sct).

Architecture
------------
- snomed.db lives on the snomed-data volume at SNOMED_DB_PATH
- All queries are read-only; the file is never written by this module
- One SQLite connection is held per thread (thread-local) to avoid locking
- If snomed.db is absent or SNOMED_DB_PATH is unset, SnomedUnavailableError
  is raised so callers can degrade gracefully

DataSet.snomed_query_type controls how options are fetched:
    refset      — all members of a SNOMED refset (snomed_refset_id = SCTID)
    descendants — all active descendants of a root concept (snomed_refset_id = root SCTID)
    ecl         — ECL expression (snomed_ecl field) — Phase 2, raises NotImplementedError
    mapped      — mapped codes (e.g. OPCS-4 via SNOMED map) — Phase 2

Return format
-------------
All methods return a list of strings in the form "SCTID | Preferred term", matching
the DataSet.options list format used by all other dataset categories.
"""

import logging
import os
import sqlite3
import threading
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from .models import DataSet

logger = logging.getLogger(__name__)

_local = threading.local()


class SnomedUnavailableError(Exception):
    """Raised when snomed.db is not present or SNOMED_DB_PATH is not configured."""


def _get_db_path() -> str:
    """Return the configured path to snomed.db, or raise SnomedUnavailableError."""
    path = getattr(settings, "SNOMED_DB_PATH", None) or os.environ.get(
        "SNOMED_DB_PATH", ""
    )
    if not path:
        raise SnomedUnavailableError(
            "SNOMED_DB_PATH is not configured. "
            "Set it in your environment to enable SNOMED CT features."
        )
    if not os.path.isfile(path):
        raise SnomedUnavailableError(
            f"snomed.db not found at {path}. "
            "Run 'python manage.py seed_snomed_datasets' after building snomed.db."
        )
    return path


def _get_connection() -> sqlite3.Connection:
    """Return a thread-local read-only SQLite connection to snomed.db."""
    if not getattr(_local, "conn", None):
        path = _get_db_path()
        uri = f"file:{path}?mode=ro"
        _local.conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _format_option(sctid: str, term: str) -> str:
    return f"{sctid} | {term}"


def get_options(dataset: "DataSet") -> list[str]:
    """
    Return a list of option strings for a SNOMED dataset.

    Dispatches to the appropriate query based on dataset.snomed_query_type.

    Args:
        dataset: A DataSet instance with category='snomed'

    Returns:
        List of strings in "SCTID | Preferred term" format

    Raises:
        SnomedUnavailableError: snomed.db missing or not configured
        ValueError: dataset is missing required SNOMED fields
        NotImplementedError: snomed_query_type is 'ecl' or 'mapped' (Phase 2)
    """
    query_type = dataset.snomed_query_type
    refset_id = dataset.snomed_refset_id

    if query_type == "refset":
        if not refset_id:
            raise ValueError(
                f"Dataset '{dataset.key}' has snomed_query_type='refset' "
                "but snomed_refset_id is not set."
            )
        return _fetch_refset_members(refset_id)

    elif query_type == "descendants":
        if not refset_id:
            raise ValueError(
                f"Dataset '{dataset.key}' has snomed_query_type='descendants' "
                "but snomed_refset_id (root concept SCTID) is not set."
            )
        return _fetch_descendants(refset_id)

    elif query_type in ("ecl", "mapped"):
        raise NotImplementedError(
            f"snomed_query_type='{query_type}' is a Phase 2 feature and is not yet implemented."
        )

    else:
        raise ValueError(
            f"Unknown snomed_query_type '{query_type}' on dataset '{dataset.key}'."
        )


def search(query: str, limit: int = 50) -> list[str]:
    """
    Full-text search across all active SNOMED concepts using FTS5.

    Used for typeahead inputs when the option list is too large for a dropdown
    (snomed_member_count > 2000).

    Args:
        query: Search string (minimum 2 characters recommended)
        limit: Maximum number of results to return

    Returns:
        List of strings in "SCTID | Preferred term" format

    Raises:
        SnomedUnavailableError: snomed.db missing or not configured
    """
    conn = _get_connection()
    try:
        # FTS5 prefix match: append * for typeahead-style prefix searching
        fts_query = f'"{query}"*' if query else ""
        rows = conn.execute(
            """
            SELECT id, preferred_term
            FROM concepts_fts
            WHERE concepts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
        return [_format_option(str(row["id"]), row["preferred_term"]) for row in rows]
    except sqlite3.OperationalError as exc:
        logger.error("SNOMED search failed: %s", exc)
        raise SnomedUnavailableError(
            f"SNOMED search failed — snomed.db may be corrupt or incompatible: {exc}"
        )


def get_refset_member_count(refset_id: str) -> int:
    """
    Return the number of active members in a SNOMED refset.

    Used by seed_snomed_datasets to populate snomed_member_count.
    Members are counted via JOIN with concepts to filter inactive concepts
    (refset_members itself has no active column — sct only loads active concepts
    by default, but the JOIN is a belt-and-braces guard).

    Args:
        refset_id: SCTID of the refset

    Returns:
        Integer count of active members

    Raises:
        SnomedUnavailableError: snomed.db missing or not configured
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM refset_members r
            JOIN concepts c ON c.id = r.referenced_component_id AND c.active = 1
            WHERE r.refset_id = ?
            """,
            (refset_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    except sqlite3.OperationalError as exc:
        logger.warning("Could not count refset members for %s: %s", refset_id, exc)
        return 0


def _fetch_refset_members(refset_id: str) -> list[str]:
    """
    Fetch all members of a SNOMED refset with their preferred terms.

    sct schema: refset_members(refset_id, referenced_component_id)
    Preferred term is on concepts.preferred_term (no separate descriptions table).
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT r.referenced_component_id, c.preferred_term
            FROM refset_members r
            JOIN concepts c ON c.id = r.referenced_component_id AND c.active = 1
            WHERE r.refset_id = ?
            ORDER BY c.preferred_term
            """,
            (refset_id,),
        ).fetchall()
        return [_format_option(str(row[0]), row[1]) for row in rows]
    except sqlite3.OperationalError as exc:
        logger.error("Failed to fetch refset %s: %s", refset_id, exc)
        raise SnomedUnavailableError(
            f"Failed to fetch refset {refset_id} — snomed.db may be corrupt: {exc}"
        )


def _fetch_descendants(root_id: str) -> list[str]:
    """
    Fetch all active descendants of a root concept.

    sct schema: concept_isa(child_id, parent_id) — direct IS-A relationships only.
    Uses a recursive CTE (WITH RECURSIVE) to traverse the full hierarchy.
    SQLite supports recursive CTEs since v3.8.3 (2014).
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT child_id FROM concept_isa WHERE parent_id = ?
                UNION ALL
                SELECT ci.child_id
                FROM concept_isa ci
                JOIN descendants d ON ci.parent_id = d.id
            )
            SELECT c.id, c.preferred_term
            FROM descendants d
            JOIN concepts c ON c.id = d.id AND c.active = 1
            ORDER BY c.preferred_term
            """,
            (root_id,),
        ).fetchall()
        return [_format_option(str(row[0]), row[1]) for row in rows]
    except sqlite3.OperationalError as exc:
        raise SnomedUnavailableError(f"Failed to fetch descendants of {root_id}: {exc}")
