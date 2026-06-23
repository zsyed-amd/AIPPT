"""Tests for the `aippt storage backfill` CLI command."""
import argparse
import os

import pytest

import aippt.cli as cli
import aippt.storage as storage_mod
from aippt.storage import FsStorage


def _args(tmp_path, db_path, dry_run):
    return argparse.Namespace(
        storage_action="backfill",
        data_dir=str(tmp_path / "data"),
        db=str(db_path),
        storage="s3",
        dry_run=dry_run,
    )


def _seed_data(tmp_path):
    data = tmp_path / "data"
    (data / "uploads").mkdir(parents=True)
    (data / "uploads" / "deck.pptx").write_bytes(b"deck")
    (data / "uploads" / "sources" / "1").mkdir(parents=True)
    (data / "uploads" / "sources" / "1" / "outline.md").write_text("# o", encoding="utf-8")
    (data / "images" / "deck").mkdir(parents=True)
    (data / "images" / "deck" / "Slide1.png").write_bytes(b"img")
    (data / "backups").mkdir()
    (data / "backups" / "old.pptx").write_bytes(b"nope")  # must NOT be uploaded
    return data


def test_backfill_requires_s3(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AIPPT_STORAGE", raising=False)
    args = _args(tmp_path, tmp_path / "slides.db", dry_run=True)
    args.storage = "fs"
    assert cli.cmd_storage(args) == 2
    assert "requires an object-storage backend" in capsys.readouterr().out


def test_backfill_dry_run_lists_without_uploading(tmp_path, capsys):
    _seed_data(tmp_path)
    args = _args(tmp_path, tmp_path / "slides.db", dry_run=True)
    assert cli.cmd_storage(args) == 0
    out = capsys.readouterr().out
    assert "uploads/deck.pptx" in out
    assert "uploads/sources/1/outline.md" in out
    assert "images/deck/Slide1.png" in out
    assert "backups/old.pptx" not in out  # backups are node-local


def test_backfill_uploads_blobs_and_snapshot(tmp_path, monkeypatch):
    data = _seed_data(tmp_path)
    remote = tmp_path / "remote"

    # a real catalog DB to snapshot
    from aippt.catalog import get_db
    db_path = tmp_path / "slides.db"
    conn = get_db(str(db_path))
    conn.execute(
        "INSERT INTO decks (name, file_path, file_hash, slide_count) VALUES (?,?,?,?)",
        ("demo", "uploads/deck.pptx", "h", 0),
    )
    conn.commit()
    conn.close()

    # back the s3 client with a local FsStorage "remote"
    monkeypatch.setattr(
        storage_mod, "build_storage", lambda cfg, fs_root: FsStorage(str(remote))
    )
    args = _args(tmp_path, db_path, dry_run=False)
    assert cli.cmd_storage(args) == 0

    fs = FsStorage(str(remote))
    keys = set(fs.list(""))
    assert "uploads/deck.pptx" in keys
    assert "uploads/sources/1/outline.md" in keys
    assert "images/deck/Slide1.png" in keys
    assert "catalog/slides.db" in keys           # catalog snapshot
    assert "backups/old.pptx" not in keys        # excluded
