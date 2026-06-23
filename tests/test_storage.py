"""Tests for the storage abstraction (FsStorage / S3Storage) and the factory.

The S3 round-trip tests are skipped unless live MinIO credentials are present
in the environment (``MINIO_ACCESS_KEY`` / ``MINIO_SECRET_KEY``). The
filesystem backend is fully exercised with a ``tmp_path`` root and needs no
credentials -- it is the default backend and must stay byte-for-byte equivalent
to the historical local-filesystem behavior.
"""
import io
import os
from datetime import timedelta

import pytest

from aippt.storage import FsStorage, Storage, build_storage
from aippt.config import StorageConfig


# ---------------------------------------------------------------------------
# FsStorage
# ---------------------------------------------------------------------------


@pytest.fixture
def fs(tmp_path):
    return FsStorage(str(tmp_path / "data"))


def test_fs_put_bytes_get_roundtrip(fs):
    fs.put("uploads/deck.pptx", b"hello world")
    assert fs.get("uploads/deck.pptx") == b"hello world"


def test_fs_put_stream_get_roundtrip(fs):
    fs.put("uploads/sources/1/outline.md", io.BytesIO(b"# Title\n- bullet"))
    assert fs.get("uploads/sources/1/outline.md") == b"# Title\n- bullet"


def test_fs_put_creates_parent_dirs(fs, tmp_path):
    fs.put("images/my-deck/Slide1.png", b"\x89PNG")
    assert (tmp_path / "data" / "images" / "my-deck" / "Slide1.png").is_file()


def test_fs_open_streams_bytes(fs):
    fs.put("output/big.pptx", b"0123456789")
    with fs.open("output/big.pptx") as handle:
        assert handle.read(4) == b"0123"
        assert handle.read() == b"456789"


def test_fs_exists(fs):
    assert fs.exists("nope.txt") is False
    fs.put("nope.txt", b"x")
    assert fs.exists("nope.txt") is True


def test_fs_delete_is_idempotent(fs):
    fs.put("tmp.bin", b"x")
    fs.delete("tmp.bin")
    assert fs.exists("tmp.bin") is False
    # second delete on a missing key must not raise (S3 delete semantics)
    fs.delete("tmp.bin")


def test_fs_list_returns_posix_keys_under_prefix(fs):
    fs.put("images/a/Slide1.png", b"1")
    fs.put("images/a/Slide2.png", b"2")
    fs.put("images/b/Slide1.png", b"3")
    fs.put("uploads/deck.pptx", b"4")

    listed = sorted(fs.list("images/"))
    assert listed == [
        "images/a/Slide1.png",
        "images/a/Slide2.png",
        "images/b/Slide1.png",
    ]
    # keys are forward-slash regardless of platform
    assert all("\\" not in key for key in listed)


def test_fs_list_empty_prefix_returns_everything(fs):
    fs.put("a.txt", b"1")
    fs.put("sub/b.txt", b"2")
    assert sorted(fs.list("")) == ["a.txt", "sub/b.txt"]


def test_fs_list_missing_prefix_is_empty(fs):
    assert list(fs.list("does/not/exist/")) == []


def test_fs_get_missing_key_raises(fs):
    with pytest.raises(FileNotFoundError):
        fs.get("missing.bin")


def test_fs_presign_get_not_supported(fs):
    # The filesystem backend serves through the app (FileResponse), not via
    # presigned URLs. Calling presign_get is a programming error.
    fs.put("images/a/Slide1.png", b"x")
    with pytest.raises(NotImplementedError):
        fs.presign_get("images/a/Slide1.png", timedelta(minutes=10))


def test_fs_rejects_key_escaping_root(fs):
    with pytest.raises(ValueError):
        fs.put("../escape.txt", b"x")
    with pytest.raises(ValueError):
        fs.get("/etc/passwd")


def test_fsstorage_satisfies_protocol(fs):
    assert isinstance(fs, Storage)


# ---------------------------------------------------------------------------
# build_storage factory
# ---------------------------------------------------------------------------


def test_build_storage_fs_default(tmp_path):
    cfg = StorageConfig(backend="fs")
    storage = build_storage(cfg, fs_root=str(tmp_path))
    assert isinstance(storage, FsStorage)
    storage.put("k.txt", b"v")
    assert (tmp_path / "k.txt").read_bytes() == b"v"


def test_build_storage_unknown_backend_raises(tmp_path):
    cfg = StorageConfig(backend="azure")
    with pytest.raises(ValueError):
        build_storage(cfg, fs_root=str(tmp_path))


# ---------------------------------------------------------------------------
# S3Storage -- live, opt-in (skipped without credentials)
# ---------------------------------------------------------------------------

_HAVE_MINIO_CREDS = bool(
    os.environ.get("MINIO_ACCESS_KEY") and os.environ.get("MINIO_SECRET_KEY")
)

requires_minio = pytest.mark.skipif(
    not _HAVE_MINIO_CREDS,
    reason="MINIO_ACCESS_KEY / MINIO_SECRET_KEY not set; live S3 test skipped",
)


@pytest.fixture
def s3(tmp_path):
    """Live S3Storage scoped to a throwaway prefix; cleaned up after the test."""
    from aippt.config import load_storage_config

    cfg = load_storage_config(backend="s3")
    # isolate test objects under a unique sub-prefix so we never collide with
    # real data and can purge everything we wrote on teardown.
    cfg = StorageConfig(
        backend="s3",
        endpoint=cfg.endpoint,
        bucket=cfg.bucket,
        prefix=cfg.prefix.rstrip("/") + "/_pytest/",
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        ca_bundle=cfg.ca_bundle,
        secure=cfg.secure,
    )
    storage = build_storage(cfg, fs_root=str(tmp_path))
    yield storage
    for key in list(storage.list("")):
        storage.delete(key)


@requires_minio
def test_s3_put_get_roundtrip(s3):
    s3.put("hello.txt", b"aippt s3 roundtrip", content_type="text/plain")
    assert s3.get("hello.txt") == b"aippt s3 roundtrip"


@requires_minio
def test_s3_list_and_exists(s3):
    s3.put("dir/a.txt", b"1")
    s3.put("dir/b.txt", b"2")
    assert sorted(s3.list("dir/")) == ["dir/a.txt", "dir/b.txt"]
    assert s3.exists("dir/a.txt") is True
    assert s3.exists("dir/missing.txt") is False


@requires_minio
def test_s3_delete_idempotent(s3):
    s3.put("gone.txt", b"x")
    s3.delete("gone.txt")
    assert s3.exists("gone.txt") is False
    s3.delete("gone.txt")  # no raise


@requires_minio
def test_s3_presign_get_loads(s3):
    import ssl
    import urllib.request

    body = b"presigned body"
    s3.put("p.txt", body)
    url = s3.presign_get("p.txt", timedelta(minutes=5))
    ctx = ssl.create_default_context(cafile=s3._ca_bundle) if s3._ca_bundle else None
    with urllib.request.urlopen(url, timeout=20, context=ctx) as r:
        assert r.read() == body
