"""Linux PPTX -> PNG render pipeline using Microsoft Graph.

End-to-end:
    1. Upload PPTX to a SharePoint staging library subfolder.
    2. Ask Graph to convert the item to PDF (?format=pdf).
    3. Stream the PDF to a temp file.
    4. Run pdftoppm to produce per-slide PNGs.
    5. Best-effort delete the staged PPTX in finally.

Token + SP coordinates are caller-supplied (per-request from the web layer
or per-CLI-invocation from the env). This module never reads MS_ACCESS_TOKEN
itself.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from aippt import graph

logger = logging.getLogger(__name__)

PPTX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation"
)


def _build_upload_path(
    *,
    site_id: str,
    drive_id: str,
    root_path: str,
    ntid: str,
    job_id: str,
) -> str:
    """Construct the path-style Graph URL fragment for the upload target.

    Returns something like:
        /sites/{site_id}/drives/{drive_id}/root:/{root_path}/{ntid}/{job_id}.pptx
    """
    if not ntid:
        raise ValueError("ntid is required to build per-user upload path")
    if not job_id:
        raise ValueError("job_id is required")
    clean_root = root_path.strip("/")
    return (
        f"/sites/{site_id}/drives/{drive_id}/root:"
        f"/{clean_root}/{ntid}/{job_id}.pptx"
    )


def render_pptx_to_pngs(
    *,
    pptx_path: str,
    out_dir: str,
    token: str,
    ntid: str,
    site_id: str,
    drive_id: str,
    root_path: str = "AIPPT/render-staging",
    dpi: int = 150,
    job_id: Optional[str] = None,
) -> list[Path]:
    """Render `pptx_path` to per-slide PNGs in `out_dir` via Microsoft Graph.

    Returns the sorted list of generated PNG paths.

    Raises:
        FileNotFoundError: pptx_path missing or pdftoppm not on PATH.
        graph.GraphError: any non-success Graph response.
        subprocess.CalledProcessError: pdftoppm failed.
    """
    pptx = Path(pptx_path)
    if not pptx.exists():
        raise FileNotFoundError(f"PPTX not found: {pptx_path}")
    if shutil.which("pdftoppm") is None:
        raise FileNotFoundError(
            "pdftoppm not found on PATH. Install poppler-utils.")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    job_id = job_id or uuid.uuid4().hex
    upload_path = _build_upload_path(
        site_id=site_id, drive_id=drive_id, root_path=root_path,
        ntid=ntid, job_id=job_id,
    )
    upload_target = f"{upload_path}:/content"

    # Graph's small-file PUT does not create intermediate SharePoint folders,
    # so the per-user subfolder must exist before the first render for a new
    # NTID. ensure_folder swallows 409 to keep concurrent renders idempotent.
    clean_root = root_path.strip("/")
    parent_path = (
        f"/sites/{site_id}/drives/{drive_id}/root:/{clean_root}"
    )
    graph.ensure_folder(parent_path, name=ntid, token=token)

    data = pptx.read_bytes()
    item_id: Optional[str] = None
    item_path: Optional[str] = None
    try:
        if len(data) < graph.SMALL_FILE_LIMIT:
            logger.info("Uploading %d bytes via small-file PUT", len(data))
            response = graph.put_small_file(
                upload_target, data=data, token=token,
                content_type=PPTX_CONTENT_TYPE,
            )
        else:
            logger.info("Uploading %d bytes via resumable session", len(data))
            response = graph.upload_resumable(
                upload_path, data=data, token=token,
            )
        item_id = response.get("id")
        if not item_id:
            raise RuntimeError(
                f"Graph upload response missing 'id': {response!r}")
        item_path = f"/sites/{site_id}/drives/{drive_id}/items/{item_id}"

        logger.info("Downloading PDF from SharePoint (item %s)", item_id)
        pdf_bytes = graph.download_pdf(item_path, token=token)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            pdf_tmp = tmp.name
        try:
            prefix = str(Path(out_dir) / "slide")
            logger.info(
                "Running pdftoppm on %d-byte PDF at %d dpi -> %s",
                len(pdf_bytes), dpi, prefix,
            )
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), pdf_tmp, prefix],
                check=True,
            )
        finally:
            try:
                os.unlink(pdf_tmp)
            except OSError:
                pass

        # pdftoppm writes `slide-NN.png` (1-based, zero-padded to the page
        # count). catalog_deck looks for `Slide{i}.png` (no dash, no padding)
        # to match the Windows PowerShell export output. Rename in sorted
        # order so the Linux render path produces files the catalog can find.
        raw_pngs = sorted(Path(out_dir).glob("slide-*.png"))
        pngs: list[Path] = []
        for i, src in enumerate(raw_pngs, start=1):
            dst = Path(out_dir) / f"Slide{i}.png"
            if src != dst:
                src.replace(dst)
            pngs.append(dst)
        return pngs
    finally:
        if item_path:
            try:
                graph.delete_item(item_path, token=token)
                logger.info("Deleted staged PPTX %s", item_path)
            except graph.GraphError as exc:
                logger.warning(
                    "Failed to delete staged PPTX %s: %s", item_path, exc)
