"""Write-through / read-through syncing of library assets to object storage.

In ``s3`` mode the pod's local data volume is an ephemeral cache and object
storage is the durable source of truth. After a tool writes a file locally
(deck, slide image, source, output), ``persist_*`` uploads it; before serving a
file that may be absent on a cold pod, ``materialize_file`` fetches it back.

Object-storage keys are the asset's path relative to ``app.state.data_root``,
so they match the ``uploads/…`` / ``images/<deck>/…`` / ``output/…`` layout
regardless of the working directory.

Every function is a **no-op in ``fs`` mode**: the file already lives at its
durable local location, so local dev and the existing behavior are unchanged.
All operations are best-effort -- a storage hiccup is logged, never raised, so
it cannot break a request mid-flight.
"""
from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)


def _enabled(state) -> bool:
    """True when an object-storage backend is active."""
    cfg = getattr(state, "storage_config", None)
    return bool(cfg is not None and cfg.backend == "s3")


def asset_key(data_root: str, local_path: str) -> str:
    """Return the POSIX object-storage key for *local_path* under *data_root*."""
    rel = os.path.relpath(os.path.abspath(local_path), os.path.abspath(data_root))
    return rel.replace(os.sep, "/")


def _key_or_none(state, local_path: str):
    key = asset_key(state.data_root, local_path)
    if key == ".." or key.startswith("../"):
        logger.warning(
            "Refusing to sync %s: resolves outside data_root %s",
            local_path, state.data_root,
        )
        return None
    return key


def persist_file(state, local_path: str) -> None:
    """Upload a single local file to object storage (no-op in fs mode)."""
    if not _enabled(state) or not os.path.isfile(local_path):
        return
    key = _key_or_none(state, local_path)
    if key is None:
        return
    try:
        with open(local_path, "rb") as fh:
            state.storage.put(key, fh)
        logger.debug("Persisted %s -> %s", local_path, key)
    except Exception:
        logger.exception("Failed to persist %s to object storage", key)


def persist_tree(state, local_dir: str) -> None:
    """Upload every file under *local_dir* to object storage (no-op in fs mode)."""
    if not _enabled(state) or not os.path.isdir(local_dir):
        return
    for dirpath, _dirs, files in os.walk(local_dir):
        for name in files:
            persist_file(state, os.path.join(dirpath, name))


def materialize_file(state, local_path: str) -> bool:
    """Ensure *local_path* exists locally, fetching from object storage if needed.

    Returns True if the file is present locally after the call. In fs mode this
    is just an existence check (no fetch). Streams the object to disk so large
    decks don't have to be buffered in memory.
    """
    if os.path.exists(local_path):
        return True
    if not _enabled(state):
        return False
    key = _key_or_none(state, local_path)
    if key is None:
        return False
    try:
        if not state.storage.exists(key):
            return False
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        src = state.storage.open(key)
        try:
            with open(local_path, "wb") as fh:
                shutil.copyfileobj(src, fh)
        finally:
            close = getattr(src, "close", None)
            if callable(close):
                close()
        logger.debug("Materialized %s <- %s", local_path, key)
        return True
    except Exception:
        logger.exception("Failed to materialize %s from object storage", key)
        # Leave no partial file behind
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass
        return False
