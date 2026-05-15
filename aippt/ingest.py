"""Reusable ingest pipeline: export images → catalog → optional AI tags.

Used by both the CLI ``ingest`` command and the web upload endpoint.
"""

import argparse
import logging
import os
from typing import Optional

from aippt.catalog import catalog_deck, get_deck_by_id, detect_source_engine, detect_source_theme
from aippt.cli import cmd_export_images, cmd_analyze

logger = logging.getLogger(__name__)


def ingest_deck(
    deck_path: str,
    db_path: str = "slides.db",
    images_dir: Optional[str] = None,
    generate_tags: bool = False,
    taxonomy: Optional[str] = None,
    model: Optional[str] = None,
    gateway_config: Optional[str] = None,
    api_key: Optional[str] = None,
    width: int = 1920,
    height: int = 1080,
    require_images: bool = True,
    progress_callback: Optional[callable] = None,
    source_script_path: Optional[str] = None,
    source_theme: Optional[str] = None,
    ms_token: Optional[str] = None,
) -> dict:
    """Run full ingest pipeline: export images → catalog → optional tags.

    Args:
        deck_path: Path to the .pptx file.
        db_path: SQLite database path.
        images_dir: Output directory for slide images. Defaults to ``images/<deck-stem>/``.
        generate_tags: When True, run AI tag generation after cataloging.
        taxonomy: Path to taxonomy CSV for constrained tagging.
        model: LLM model name for tag generation.
        gateway_config: Path to gateway YAML config.
        api_key: API key for LLM provider.
        width: Image export width in pixels.
        height: Image export height in pixels.
        require_images: When True (default), abort with RuntimeError if image
            export fails. When False, log a warning and continue without images.
        progress_callback: Optional ``fn(step: str, detail: str)`` called at each stage.
        source_script_path: Path to the generating script (JS/Python) for source tracking.
        source_theme: Theme name override (auto-detected from script if not provided).

    Returns:
        dict with keys: deck_id, deck_name, slide_count, images_dir,
        images_exported (bool), tags_generated (bool), source_tracked (bool).
    """
    if not os.path.exists(deck_path):
        raise FileNotFoundError(f"Deck not found: {deck_path}")

    deck_name = os.path.splitext(os.path.basename(deck_path))[0]

    # Resolve images directory
    if not images_dir:
        images_dir = os.path.join("images", deck_name)

    def _progress(step: str, detail: str = ""):
        if progress_callback:
            progress_callback(step, detail)

    # --- Step 1: Export images ---
    images_exported = False
    _progress("export_images", "Exporting slide images...")
    try:
        export_args = argparse.Namespace(
            deck=deck_path,
            out_dir=images_dir,
            width=width,
            height=height,
            ms_token=ms_token,
            gateway_config=gateway_config or "gateway.yaml",
        )
        rc = cmd_export_images(export_args)
        if rc == 0:
            images_exported = True
            _progress("export_images_done", f"Images exported to {images_dir}")
        elif require_images:
            raise RuntimeError(f"Image export failed with exit code {rc}")
        else:
            logger.warning("Image export failed (PowerShell/PowerPoint unavailable). Cataloging without images.")
            _progress("export_images_skipped", "Image export unavailable, continuing without images")
            images_dir = None
    except RuntimeError:
        raise
    except Exception as exc:
        if require_images:
            raise RuntimeError(f"Image export error: {exc}") from exc
        logger.warning(f"Image export error: {exc}. Cataloging without images.")
        _progress("export_images_skipped", "Image export unavailable, continuing without images")
        images_dir = None

    # --- Step 2: Catalog ---
    _progress("catalog", "Cataloging deck...")
    # Auto-detect source engine/theme from script when provided
    source_engine = None
    detected_theme = None
    if source_script_path:
        source_engine = detect_source_engine(source_script_path)
        detected_theme = source_theme or detect_source_theme(source_script_path)
    deck_id = catalog_deck(
        deck_path, db_path=db_path, images_dir=images_dir,
        source_script_path=source_script_path,
        source_engine=source_engine,
        source_theme=detected_theme,
    )
    _progress("catalog_done", f"Cataloged as deck_id={deck_id}")

    # Get slide count from DB
    deck_info = get_deck_by_id(deck_id, db_path)
    slide_count = deck_info["slide_count"] if deck_info else 0

    # --- Step 3: Tags (optional) ---
    tags_generated = False
    if generate_tags:
        _progress("tags", "Generating AI tags...")
        try:
            analyze_args = argparse.Namespace(
                deck=deck_path,
                mode="tags",
                images_dir=images_dir,
                db=db_path,
                model=model,
                taxonomy=taxonomy,
                gateway_config=gateway_config,
                api_key=api_key,
            )
            rc = cmd_analyze(analyze_args)
            if rc == 0:
                tags_generated = True
                _progress("tags_done", "Tags generated")
            else:
                logger.warning("Tag generation completed with errors (some slides may have failed)")
                _progress("tags_partial", "Tag generation completed with some errors")
        except Exception as exc:
            logger.warning(f"Tag generation error: {exc}")
            _progress("tags_error", f"Tag generation failed: {exc}")

    _progress("complete", "Ingest complete")

    return {
        "deck_id": deck_id,
        "deck_name": deck_name,
        "slide_count": slide_count,
        "images_dir": images_dir,
        "images_exported": images_exported,
        "tags_generated": tags_generated,
        "source_tracked": source_script_path is not None,
    }
