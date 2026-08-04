"""
Tests for the Phase 4 checkpointed runner: the SQLite state store and the
init / status / verify commands. All tests use an in-memory SQLite database
so nothing touches the real runs/state.db file.

Tests:
    test_init_is_idempotent          — seeding twice keeps 126 rows, not 252
    test_status_on_empty_db          — status works before any tables exist
    test_verify_detects_missing_file — verify reports a complete run whose
                                       result file is absent
"""

import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from fos.experiment import commands, store  # noqa: E402


@pytest.fixture
def db():
    """An in-memory SQLite database with the tables created and seeded."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store.init_db(conn)
    store.seed_from_csv(conn)
    yield conn
    conn.close()


def test_init_is_idempotent(db):
    """Initialising and seeding twice must keep 126 rows, not 252."""
    store.init_db(db)
    store.seed_from_csv(db)
    count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 126


def test_status_on_empty_db():
    """The status command must work before any tables exist."""
    conn = sqlite3.connect(":memory:")
    try:
        summary = commands.status(conn)
        assert summary["total"] == 126
        assert summary["complete"] == 0
        assert summary["pending"] == 0
    finally:
        conn.close()


def test_verify_detects_missing_file(db):
    """A run marked complete with no result file on disk must be reported."""
    store.mark_complete("run_079", "runs/results/run_079.json", db)
    report = commands.verify_runs(db)
    assert "run_079" in report["missing"]
