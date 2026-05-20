"""FastAPI web application."""
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from aippt.config import load_sharepoint_config
from aippt.web.logging_filter import install_authorization_scrub
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


def create_app(db_path: str = "slides.db", gateway_config: str = None, uploads_dir: str = "uploads", images_dir: str = "images", project_root: str = None, view_only: bool = None) -> FastAPI:
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

    Returns:
        Configured FastAPI app
    """
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    # Strip Bearer tokens from any log line before it leaves the process.
    install_authorization_scrub()
    app = FastAPI(title="AIPPT", version="2.0.0")
    app.state.db_path = db_path
    app.state.gateway_config = gateway_config
    app.state.uploads_dir = uploads_dir
    app.state.images_dir = images_dir
    app.state.project_root = project_root or os.getcwd()
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

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Mount Sphinx docs at /docs when the build output exists
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "_build" / "html"
    if docs_dir.is_dir():
        app.mount("/docs", StaticFiles(directory=str(docs_dir), html=True), name="docs")

    app.include_router(router)
    return app
