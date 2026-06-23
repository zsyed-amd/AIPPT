"""Storage abstraction for AIPPT library assets.

One interface, two backends, selected by the ``AIPPT_STORAGE`` config switch:

- ``FsStorage`` -- maps each key to a path under a local root. This is the
  historical behavior and the default; it must stay byte-for-byte equivalent
  to the pre-existing local-filesystem layout so local dev and the existing
  test suite are unaffected.
- ``S3Storage`` -- an S3-compatible object store (MinIO in production) reached
  via ``minio-py``. Keys are prefixed with ``asic/aippt/`` so all AIPPT
  artifacts live under one namespace in the shared ``ogmatic-zoo`` bucket.

Keys are always forward-slash POSIX-style and relative (e.g.
``uploads/deck.pptx``, ``images/my-deck/Slide1.png``, ``catalog/slides.db``).
``FsStorage`` translates them to the host path separator internally and always
lists them back with forward slashes, so a key produced against one backend is
valid against the other.
"""
from __future__ import annotations

import io
import os
import shutil
from datetime import timedelta
from typing import BinaryIO, Iterable, Optional, Protocol, Union, runtime_checkable

from aippt.config import StorageConfig

DataLike = Union[bytes, BinaryIO]

# minio is only needed for the S3 backend. The default (fs) backend must import
# and run with no object-storage dependency installed, so the import is lazy.
try:  # pragma: no cover - import guard
    from minio import Minio
    from minio.error import S3Error
    HAS_MINIO = True
except ImportError:  # pragma: no cover - exercised only without minio installed
    HAS_MINIO = False


@runtime_checkable
class Storage(Protocol):
    """Blob storage contract shared by the filesystem and object-store backends."""

    def put(self, key: str, data: DataLike, content_type: Optional[str] = None) -> None:
        """Write ``data`` (bytes or a readable binary stream) at ``key``."""
        ...

    def get(self, key: str) -> bytes:
        """Return the full contents at ``key``. Raises if the key is absent."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Return a readable binary stream for ``key`` (for large objects)."""
        ...

    def list(self, prefix: str) -> Iterable[str]:
        """Yield every key under ``prefix`` (recursive), as POSIX-style keys."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key``. Idempotent -- deleting an absent key is not an error."""
        ...

    def exists(self, key: str) -> bool:
        """Return whether ``key`` is present."""
        ...

    def presign_get(self, key: str, expires: timedelta) -> str:
        """Return a time-limited URL that serves ``key`` directly."""
        ...


# ---------------------------------------------------------------------------
# Filesystem backend
# ---------------------------------------------------------------------------


class FsStorage:
    """Local-filesystem storage. ``key`` maps to ``root/<key>``."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def _path(self, key: str) -> str:
        # Reject absolute keys and any ".." segment that would escape the root.
        # Keys are internally generated, but several derive from deck names, so
        # a cheap traversal guard is worth keeping at this boundary.
        if key.startswith("/") or key.startswith("\\"):
            raise ValueError(f"storage key must be relative, got {key!r}")
        parts = key.replace("\\", "/").split("/")
        if any(part == ".." for part in parts):
            raise ValueError(f"storage key must not escape the root: {key!r}")
        path = os.path.normpath(os.path.join(self.root, *parts))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ValueError(f"storage key resolves outside the root: {key!r}")
        return path

    def put(self, key: str, data: DataLike, content_type: Optional[str] = None) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            if isinstance(data, (bytes, bytearray)):
                fh.write(data)
            else:
                shutil.copyfileobj(data, fh)

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as fh:
            return fh.read()

    def open(self, key: str) -> BinaryIO:
        return open(self._path(key), "rb")

    def list(self, prefix: str) -> Iterable[str]:
        base = self._path(prefix) if prefix else self.root
        # A prefix may name a file directly or a directory subtree.
        if os.path.isfile(base):
            yield prefix.replace("\\", "/")
            return
        if not os.path.isdir(base):
            return
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.root)
                yield rel.replace(os.sep, "/")

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def presign_get(self, key: str, expires: timedelta) -> str:
        raise NotImplementedError(
            "FsStorage has no presigned URLs; the app serves local files "
            "directly via FileResponse."
        )


# ---------------------------------------------------------------------------
# S3 / MinIO backend
# ---------------------------------------------------------------------------

# minio requires a known length up front; for unbounded streams we fall back to
# multipart with this part size and length=-1.
_MULTIPART_PART_SIZE = 16 * 1024 * 1024


class S3Storage:
    """S3-compatible object storage via minio-py.

    All keys are stored under ``prefix`` (default ``asic/aippt/``) inside
    ``bucket``. The prefix is an implementation detail; callers pass and get
    back app-relative keys (``uploads/...``), never the bucket-absolute path.
    """

    def __init__(
        self,
        client: "Minio",
        bucket: str,
        prefix: str = "asic/aippt/",
        ca_bundle: Optional[str] = None,
    ):
        self.client = client
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") or prefix == "" else prefix + "/"
        # retained for presigned-URL TLS verification by callers/tests
        self._ca_bundle = ca_bundle

    def _full(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def put(self, key: str, data: DataLike, content_type: Optional[str] = None) -> None:
        ctype = content_type or "application/octet-stream"
        if isinstance(data, (bytes, bytearray)):
            buf = io.BytesIO(bytes(data))
            self.client.put_object(
                self.bucket, self._full(key), buf, length=len(data),
                content_type=ctype,
            )
            return
        length = _stream_length(data)
        if length is not None:
            self.client.put_object(
                self.bucket, self._full(key), data, length=length,
                content_type=ctype,
            )
        else:
            self.client.put_object(
                self.bucket, self._full(key), data, length=-1,
                part_size=_MULTIPART_PART_SIZE, content_type=ctype,
            )

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, self._full(key))
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def open(self, key: str) -> BinaryIO:
        # minio's response object is a urllib3 HTTPResponse: a readable,
        # closeable binary stream suitable for streaming large objects.
        return self.client.get_object(self.bucket, self._full(key))

    def list(self, prefix: str) -> Iterable[str]:
        full_prefix = self._full(prefix)
        for obj in self.client.list_objects(
            self.bucket, prefix=full_prefix, recursive=True
        ):
            name = obj.object_name
            if name.startswith(self.prefix):
                yield name[len(self.prefix):]
            else:  # pragma: no cover - defensive; minio honors the prefix
                yield name

    def delete(self, key: str) -> None:
        # remove_object is already idempotent (no error on a missing key).
        self.client.remove_object(self.bucket, self._full(key))

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, self._full(key))
            return True
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject", "NotFound"):
                return False
            raise

    def presign_get(self, key: str, expires: timedelta) -> str:
        return self.client.presigned_get_object(
            self.bucket, self._full(key), expires=expires
        )


def _stream_length(stream: BinaryIO) -> Optional[int]:
    """Best-effort byte length of a seekable stream, else ``None``."""
    try:
        pos = stream.tell()
        stream.seek(0, os.SEEK_END)
        end = stream.tell()
        stream.seek(pos, os.SEEK_SET)
        return end - pos
    except (OSError, AttributeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_storage(config: StorageConfig, fs_root: str) -> Storage:
    """Construct the configured storage backend.

    Args:
        config: Resolved storage configuration (see ``config.load_storage_config``).
        fs_root: Root directory for the filesystem backend. Ignored for s3.

    Raises:
        ValueError: unknown backend, or s3 selected with missing config.
        RuntimeError: s3 selected but minio-py is not installed.
    """
    if config.backend == "fs":
        return FsStorage(fs_root)
    if config.backend == "s3":
        if not HAS_MINIO:
            raise RuntimeError(
                "AIPPT_STORAGE=s3 requires the 'minio' package. "
                "Install it with: pip install minio"
            )
        missing = [
            name for name, val in (
                ("MINIO_ENDPOINT", config.endpoint),
                ("MINIO_BUCKET", config.bucket),
                ("MINIO_ACCESS_KEY", config.access_key),
                ("MINIO_SECRET_KEY", config.secret_key),
            )
            if not val
        ]
        if missing:
            raise ValueError(
                "AIPPT_STORAGE=s3 is missing required config: "
                + ", ".join(missing)
            )
        http_client = None
        if config.ca_bundle:
            import urllib3
            http_client = urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED", ca_certs=config.ca_bundle
            )
        client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
            http_client=http_client,
        )
        return S3Storage(
            client, config.bucket, prefix=config.prefix, ca_bundle=config.ca_bundle
        )
    raise ValueError(f"unknown AIPPT_STORAGE backend: {config.backend!r}")
