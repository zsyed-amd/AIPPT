"""Tests for the SQLite catalog snapshot/restore round-trip and the debounced
snapshot scheduler.

These use ``FsStorage`` against a ``tmp_path`` so the snapshot/restore contract
is proven end-to-end without any object-storage credentials. The contract is
identical for ``S3Storage`` -- only the ``put``/``get``/``exists`` backend
differs.
"""
import os
import sqlite3

import pytest

from aippt.catalog import (
    get_db,
    snapshot_db,
    restore_db,
    SnapshotScheduler,
    set_snapshot_scheduler,
    request_snapshot,
)
from aippt.storage import FsStorage

SNAP_KEY = "catalog/slides.db"


def _seed_db(path):
    """Create a real catalog DB with one deck + two slides."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = get_db(path)
    conn.execute(
        "INSERT INTO decks (name, file_path, file_hash, slide_count) "
        "VALUES (?, ?, ?, ?)",
        ("demo", "uploads/demo.pptx", "deadbeef", 2),
    )
    deck_id = conn.execute("SELECT id FROM decks WHERE name = 'demo'").fetchone()["id"]
    for pos, title in ((1, "Intro"), (2, "Details")):
        conn.execute(
            "INSERT INTO slides (deck_id, position, title, content_hash) "
            "VALUES (?, ?, ?, ?)",
            (deck_id, pos, title, f"hash{pos}"),
        )
    conn.commit()
    conn.close()


def test_snapshot_then_restore_roundtrip(tmp_path):
    src_db = str(tmp_path / "src" / "slides.db")
    _seed_db(src_db)

    storage = FsStorage(str(tmp_path / "store"))
    snapshot_db(src_db, storage, key=SNAP_KEY)
    assert storage.exists(SNAP_KEY)

    # restore into a *fresh* dir as a cold pod would
    cold_db = str(tmp_path / "coldpod" / "slides.db")
    assert restore_db(cold_db, storage, key=SNAP_KEY) is True

    conn = sqlite3.connect(cold_db)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM slides").fetchone()[0] == 2
    conn.close()


def test_snapshot_uses_online_backup_with_wal_writes_in_flight(tmp_path):
    """An open WAL connection with uncommitted-to-main writes must still yield a
    consistent snapshot (the reason we use the online backup API, not ``cp``)."""
    src_db = str(tmp_path / "slides.db")
    _seed_db(src_db)

    live = get_db(src_db)  # holds a WAL connection open
    live.execute(
        "INSERT INTO decks (name, file_path, file_hash, slide_count) "
        "VALUES (?, ?, ?, ?)",
        ("inflight", "uploads/inflight.pptx", "cafe", 0),
    )
    live.commit()

    storage = FsStorage(str(tmp_path / "store"))
    snapshot_db(src_db, storage, key=SNAP_KEY)
    live.close()

    cold_db = str(tmp_path / "coldpod" / "slides.db")
    restore_db(cold_db, storage, key=SNAP_KEY)
    conn = sqlite3.connect(cold_db)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # the committed in-flight write is captured
    assert conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0] == 2
    conn.close()


def test_restore_missing_key_returns_false(tmp_path):
    storage = FsStorage(str(tmp_path / "store"))
    cold_db = str(tmp_path / "slides.db")
    assert restore_db(cold_db, storage, key=SNAP_KEY) is False
    assert not (tmp_path / "slides.db").exists()


def test_restore_clears_stale_wal_sidecars(tmp_path):
    src_db = str(tmp_path / "slides.db")
    _seed_db(src_db)
    storage = FsStorage(str(tmp_path / "store"))
    snapshot_db(src_db, storage, key=SNAP_KEY)

    cold_db = str(tmp_path / "coldpod" / "slides.db")
    (tmp_path / "coldpod").mkdir()
    # leftover sidecars from a previous incarnation must not bleed into the
    # restored database
    (tmp_path / "coldpod" / "slides.db-wal").write_bytes(b"stale")
    (tmp_path / "coldpod" / "slides.db-shm").write_bytes(b"stale")

    restore_db(cold_db, storage, key=SNAP_KEY)
    assert not (tmp_path / "coldpod" / "slides.db-wal").exists()
    assert not (tmp_path / "coldpod" / "slides.db-shm").exists()


# ---------------------------------------------------------------------------
# Debounced snapshot scheduler
# ---------------------------------------------------------------------------


def test_scheduler_flush_writes_snapshot(tmp_path):
    src_db = str(tmp_path / "slides.db")
    _seed_db(src_db)
    storage = FsStorage(str(tmp_path / "store"))

    sched = SnapshotScheduler(src_db, storage, key=SNAP_KEY, debounce_seconds=30)
    sched.request()
    assert not storage.exists(SNAP_KEY)  # debounced, not yet fired
    sched.flush()  # force immediate snapshot
    assert storage.exists(SNAP_KEY)
    sched.shutdown()


def test_scheduler_coalesces_multiple_requests(tmp_path):
    src_db = str(tmp_path / "slides.db")
    _seed_db(src_db)

    calls = {"n": 0}

    class CountingStorage(FsStorage):
        def put(self, key, data, content_type=None):
            calls["n"] += 1
            super().put(key, data, content_type)

    storage = CountingStorage(str(tmp_path / "store"))
    sched = SnapshotScheduler(src_db, storage, key=SNAP_KEY, debounce_seconds=30)
    for _ in range(5):
        sched.request()
    sched.flush()
    assert calls["n"] == 1  # five requests coalesced into a single snapshot
    sched.shutdown()


def test_module_request_snapshot_is_noop_without_scheduler(tmp_path):
    # default state: no scheduler installed (filesystem mode) -> inert
    set_snapshot_scheduler(None)
    request_snapshot()  # must not raise


def test_module_request_snapshot_routes_to_installed_scheduler(tmp_path):
    src_db = str(tmp_path / "slides.db")
    _seed_db(src_db)
    storage = FsStorage(str(tmp_path / "store"))
    sched = SnapshotScheduler(src_db, storage, key=SNAP_KEY, debounce_seconds=30)
    set_snapshot_scheduler(sched)
    try:
        request_snapshot()
        sched.flush()
        assert storage.exists(SNAP_KEY)
    finally:
        set_snapshot_scheduler(None)
        sched.shutdown()
