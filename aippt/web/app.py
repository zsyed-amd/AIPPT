"""FastAPI web application."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from aippt.config import load_sharepoint_config, load_upload_config, load_admin_ntids, load_storage_config, DEFAULT_MAX_UPLOAD_MB
from aippt.storage import build_storage
from aippt.web.log_buffer import install_ring_buffer
from aippt.web.logging_filter import install_authorization_scrub
from aippt.web.middleware import UploadSizeLimitMiddleware
from aippt.web.routes import router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def detect_view_only(gateway_config: str) -> bool:
    """Return True if no LLM access is available.

    Priority: AIPPT_VIEW_ONLY env var > gateway/API-key auto-detection.
    The --view-only CLI flag is handled by create_app() before this is called.
    """
    env_val = os.environ.get("AIPPT_VIEW_ONLY", "").lower()
    if env_val in ("1", "true", "yes"):
        return True
    if env_val in ("0", "false", "no"):
        return False
    if gateway_config and os.path.exists(gateway_config):
        return False
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return False
    return True


def create_app(db_path: str = "slides.db", gateway_config: str = None, uploads_dir: str = "uploads", images_dir: str = "images", project_root: str = None, view_only: bool = None, max_upload_mb: int = None, storage_backend: str = None, data_dir: str = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the SQLite database
        gateway_config: Optional path to gateway YAML config for LLM access
        uploads_dir: Directory for uploaded files (created if it doesn't exist)
        images_dir: Parent directory for rendered slide images. Each deck's
            PNGs land in ``{images_dir}/{deck_name}/``. Default ``"images"``
            (cwd-relative) matches historical behavior; override via the
            ``serve --images-dir`` flag for container deployments where the
            cwd is not the data volume.
        project_root: Base directory for resolving relative DB paths (default: cwd)
        view_only: Force view-only mode (True), or auto-detect (None)
        max_upload_mb: Hard cap on inbound upload size in MB. Overrides the
            ``upload.max_size_mb`` key in ``gateway.yaml``; defaults to
            ``DEFAULT_MAX_UPLOAD_MB`` when neither is set.
        storage_backend: ``"fs"`` (default) or ``"s3"``. Overrides the
            ``AIPPT_STORAGE`` env var. The filesystem backend is rooted at
            ``data_dir`` and preserves historical local behavior; the s3
            backend reads MinIO coordinates from the environment and, on
            startup, restores the catalog snapshot and installs the debounced
            snapshot scheduler.
        data_dir: Root that storage keys are relative to (the durable data
            volume, e.g. ``/app/data``). Object-storage keys are computed as
            the path of each asset relative to this root, so they match the
            ``uploads/…``/``images/…``/``output/…`` layout regardless of where
            the working directory sits. Defaults to ``project_root``.

    Returns:
        Configured FastAPI app
    """
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    # Strip Bearer tokens from any log line before it leaves the process.
    # Order matters: scrub installs filters on the root logger that mutate
    # records in place; the ring buffer then attaches as a root handler so
    # it captures already-scrubbed text.
    install_authorization_scrub()
    log_buffer = install_ring_buffer()

    resolved_root = project_root or os.getcwd()
    data_root = os.path.abspath(data_dir or os.environ.get("AIPPT_DATA_DIR") or resolved_root)
    storage_config = load_storage_config(storage_backend)
    storage = build_storage(storage_config, fs_root=data_root)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        # uvicorn.run calls logging.config.dictConfig AFTER create_app,
        # which wipes our handler off uvicorn.access / uvicorn.error.
        # Re-install on startup so the HTTP access log lands in the ring
        # buffer. install_ring_buffer is idempotent.
        install_ring_buffer()

        # Object-storage mode: restore the catalog from the last snapshot
        # before any request opens the DB, then install the debounced
        # snapshot scheduler so catalog writes are pushed back. Filesystem
        # mode (the default) does neither -- behavior is unchanged.
        scheduler = None
        if storage_config.backend == "s3":
            from aippt.catalog import (
                restore_db,
                SnapshotScheduler,
                set_snapshot_scheduler,
            )
            try:
                restore_db(db_path, storage)
            except Exception:
                logger.exception("Catalog restore from object storage failed")
            scheduler = SnapshotScheduler(db_path, storage)
            set_snapshot_scheduler(scheduler)
        try:
            yield
        finally:
            if scheduler is not None:
                from aippt.catalog import set_snapshot_scheduler
                scheduler.flush()
                scheduler.shutdown()
                set_snapshot_scheduler(None)

    app = FastAPI(title="AIPPT", version="2.0.0", lifespan=_lifespan)
    app.state.log_buffer = log_buffer
    app.state.db_path = db_path
    app.state.gateway_config = gateway_config
    app.state.uploads_dir = uploads_dir
    app.state.images_dir = images_dir
    app.state.project_root = resolved_root
    app.state.data_root = data_root
    app.state.storage = storage
    app.state.storage_config = storage_config
    if view_only is None:
        app.state.view_only = detect_view_only(gateway_config)
    else:
        app.state.view_only = view_only

    # Load SharePoint render-staging coordinates if available. Linux deploys
    # need this for the Graph PPTX -> PDF -> PNG path; Windows / no-render
    # deploys can leave it unset.
    sp_config = None
    try:
        if gateway_config:
            sp_config = load_sharepoint_config(gateway_config)
    except (ValueError, RuntimeError) as exc:
        logger.warning("SharePoint config invalid in %s: %s", gateway_config, exc)
    app.state.sharepoint_config = sp_config

    # Upload size limit. CLI flag wins; otherwise gateway.yaml; otherwise default.
    if max_upload_mb is not None and max_upload_mb > 0:
        app.state.max_upload_bytes = max_upload_mb * 1024 * 1024
    else:
        app.state.max_upload_bytes = load_upload_config(gateway_config)

    # Admin tier v1: NTID allowlist from gateway.yaml. Empty set means no
    # admins are configured; admin-gated endpoints reject everyone. See
    # aippt.config.load_admin_ntids for the threat model.
    app.state.admin_ntids = load_admin_ntids(gateway_config)

    app.add_middleware(UploadSizeLimitMiddleware)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Mount Sphinx docs at /docs when the build output exists
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "_build" / "html"
    if docs_dir.is_dir():
        app.mount("/docs", StaticFiles(directory=str(docs_dir), html=True), name="docs")

    app.include_router(router)

    return app
