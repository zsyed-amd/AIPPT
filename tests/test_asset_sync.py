"""Tests for write-through / read-through asset syncing.

The ``s3`` backend is simulated with a second ``FsStorage`` pointed at a
separate "remote" directory, so the cold-pod round-trip (write local -> persist
-> wipe local -> materialize) is proven without any object-storage credentials.
``fs`` mode must be a pure no-op.
"""
import os
from types import SimpleNamespace

import pytest

from aippt.config import StorageConfig
from aippt.storage import FsStorage
from aippt.web.asset_sync import (
    asset_key,
    persist_file,
    persist_tree,
    materialize_file,
)


def _state(backend, data_root, remote_root):
    return SimpleNamespace(
        storage=FsStorage(remote_root),
        storage_config=StorageConfig(backend=backend),
        data_root=str(data_root),
    )


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def test_asset_key_is_relative_posix(tmp_path):
    local = tmp_path / "uploads" / "deck.pptx"
    assert asset_key(str(tmp_path), str(local)) == "uploads/deck.pptx"


def test_asset_key_nested(tmp_path):
    local = tmp_path / "images" / "my-deck" / "Slide1.png"
    assert asset_key(str(tmp_path), str(local)) == "images/my-deck/Slide1.png"


# ---------------------------------------------------------------------------
# fs mode: pure no-op
# ---------------------------------------------------------------------------


def test_fs_mode_persist_is_noop(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    (data / "uploads").mkdir(parents=True)
    f = data / "uploads" / "deck.pptx"
    f.write_bytes(b"x")
    state = _state("fs", data, str(remote))

    persist_file(state, str(f))
    # nothing should have been written to the "remote"
    assert not remote.exists() or list(remote.rglob("*")) == []


def test_fs_mode_materialize_is_existence_check_only(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    data.mkdir()
    state = _state("fs", data, str(remote))
    # seed the remote, but fs mode must NOT fetch it
    state.storage.put("uploads/deck.pptx", b"remote-bytes")

    missing = data / "uploads" / "deck.pptx"
    assert materialize_file(state, str(missing)) is False
    assert not missing.exists()

    present = data / "present.txt"
    present.write_bytes(b"y")
    assert materialize_file(state, str(present)) is True


# ---------------------------------------------------------------------------
# s3 mode: write-through + read-through round-trip
# ---------------------------------------------------------------------------


def test_s3_mode_persist_uploads(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    (data / "uploads").mkdir(parents=True)
    f = data / "uploads" / "deck.pptx"
    f.write_bytes(b"deck-bytes")
    state = _state("s3", data, str(remote))

    persist_file(state, str(f))
    assert state.storage.exists("uploads/deck.pptx")
    assert state.storage.get("uploads/deck.pptx") == b"deck-bytes"


def test_s3_mode_cold_pod_materialize(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    (data / "uploads").mkdir(parents=True)
    f = data / "uploads" / "deck.pptx"
    f.write_bytes(b"deck-bytes")
    state = _state("s3", data, str(remote))

    persist_file(state, str(f))
    # simulate a cold pod: local cache wiped
    os.remove(f)
    assert not f.exists()

    assert materialize_file(state, str(f)) is True
    assert f.read_bytes() == b"deck-bytes"


def test_s3_mode_materialize_already_local_skips_fetch(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    data.mkdir()
    f = data / "present.bin"
    f.write_bytes(b"local")
    state = _state("s3", data, str(remote))
    # remote has different content; materialize must NOT overwrite a present file
    state.storage.put("present.bin", b"remote")
    assert materialize_file(state, str(f)) is True
    assert f.read_bytes() == b"local"


def test_s3_mode_materialize_missing_remote_returns_false(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    data.mkdir()
    state = _state("s3", data, str(remote))
    missing = data / "nope.bin"
    assert materialize_file(state, str(missing)) is False
    assert not missing.exists()


def test_s3_mode_persist_tree(tmp_path):
    data = tmp_path / "data"
    remote = tmp_path / "remote"
    imgs = data / "images" / "deck"
    imgs.mkdir(parents=True)
    (imgs / "Slide1.png").write_bytes(b"1")
    (imgs / "Slide2.png").write_bytes(b"2")
    state = _state("s3", data, str(remote))

    persist_tree(state, str(imgs))
    assert sorted(state.storage.list("images/deck/")) == [
        "images/deck/Slide1.png",
        "images/deck/Slide2.png",
    ]


def test_s3_mode_key_escaping_data_root_is_skipped(tmp_path):
    data = tmp_path / "data" / "inner"
    remote = tmp_path / "remote"
    data.mkdir(parents=True)
    outside = tmp_path / "data" / "outside.txt"
    outside.write_bytes(b"x")
    state = _state("s3", data, str(remote))
    # must not raise, and must not upload anything outside the root
    persist_file(state, str(outside))
    assert not remote.exists() or list(remote.rglob("*")) == []
