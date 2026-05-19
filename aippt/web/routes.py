"""API routes for the web UI."""
import json
import logging
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse

from aippt.catalog import (
    get_db,
    display_name,
    search_slides,
    add_tags,
    get_slide_tags,
    get_all_tags,
    remove_slide_tag,
    list_taxonomy,
    add_taxonomy_tags,
    remove_taxonomy_tag,
    import_taxonomy_csv,
    export_taxonomy_csv,
    rename_tag,
    catalog_deck,
    get_deck_by_id,
    record_edit,
)
from aippt.export import export_csv
from aippt import graph
from aippt.ingest import ingest_deck

router = APIRouter()
STATIC_DIR = Path(__file__).parent / "static"


@router.get("/healthz")
async def healthz():
    """Health check for Kubernetes liveness/readiness probes."""
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard -- serves the single-page app."""
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@router.get("/api/config")
async def get_config(request: Request):
    """API: Return frontend configuration flags."""
    return {"view_only": getattr(request.app.state, "view_only", False)}


@router.get("/api/decks")
async def list_decks(request: Request):
    """API: List all cataloged decks."""
    db_path = request.app.state.db_path
    conn = get_db(db_path)
    decks = conn.execute(
        "SELECT id, name, slide_count, cataloged_at, updated_at, author, created_date, modified_date, subject, description FROM decks ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for d in decks:
        deck = dict(d)
        deck["display_name"] = display_name(deck["name"])
        result.append(deck)
    return result


@router.get("/api/decks/{deck_id}/slides")
async def deck_slides(deck_id: int, request: Request):
    """API: List slides for a deck."""
    db_path = request.app.state.db_path
    conn = get_db(db_path)
    slides = conn.execute(
        "SELECT id, position, title, notes, image_path, content_hash, author, slide_created_date, updated_at, layout_type FROM slides WHERE deck_id = ? ORDER BY position",
        (deck_id,),
    ).fetchall()
    result = []
    for s in slides:
        tags = get_slide_tags(s["id"], db_path)
        d = dict(s)
        d["tags"] = tags
        result.append(d)
    conn.close()
    return result


@router.get("/api/search")
async def search(request: Request, tags: str = "", title: str = ""):
    """API: Search slides by tags and/or title."""
    db_path = request.app.state.db_path
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] or None
    title_contains = title if title else None
    results = search_slides(db_path=db_path, tags=tag_list, title_contains=title_contains)
    for r in results:
        if "deck_name" in r:
            r["display_deck_name"] = display_name(r["deck_name"])
    return results


@router.get("/api/tags")
async def list_all_tags(request: Request):
    """API: List all tags in use across all slides."""
    result = get_all_tags(db_path=request.app.state.db_path)
    return {"tags": result}


@router.get("/api/slides/{slide_id}")
async def get_slide(slide_id: int, request: Request):
    """API: Get a single slide by ID with tags."""
    db_path = request.app.state.db_path
    conn = get_db(db_path)
    row = conn.execute(
        """SELECT s.id, s.position, s.title, s.notes, s.content_hash, s.image_path,
                  s.author, s.slide_created_date, s.updated_at, s.layout_type,
                  d.name as deck_name
           FROM slides s JOIN decks d ON s.deck_id = d.id
           WHERE s.id = ?""",
        (slide_id,),
    ).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Slide not found"}, status_code=404)
    slide = dict(row)
    slide["tags"] = get_slide_tags(slide_id, db_path)
    return slide


@router.get("/api/slides/{slide_id}/tags")
async def get_slide_tags_endpoint(slide_id: int, request: Request):
    """API: Get tags for a slide."""
    db_path = request.app.state.db_path
    tags = get_slide_tags(slide_id, db_path)
    return {"tags": tags}


@router.post("/api/slides/{slide_id}/tags")
async def tag_slide(slide_id: int, request: Request):
    """API: Add tags to a slide."""
    db_path = request.app.state.db_path
    body = await request.json()
    tag_names = body.get("tags", [])
    source = body.get("source", "manual")
    add_tags(slide_id, tag_names, source=source, db_path=db_path)
    return {"status": "ok", "tags": get_slide_tags(slide_id, db_path)}


@router.get("/api/export")
async def export(request: Request):
    """API: Export all cataloged slides to CSV and return file."""
    db_path = request.app.state.db_path
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    export_csv(tmp.name, db_path=db_path, export_all=True)
    return FileResponse(tmp.name, filename="slides.csv", media_type="text/csv")


@router.get("/api/models")
async def get_models():
    """API: Get current model configuration."""
    from aippt.config import load_model_config, ConfigError
    try:
        config = load_model_config()
        # Return only the serializable parts (registry values are ModelConfig dataclasses)
        return {
            "defaults": config["defaults"],
            "source": config["source"],
        }
    except ConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.put("/api/models")
async def update_models(request: Request):
    """API: Update one or more model defaults."""
    from aippt.config import load_model_config, save_model_config, VALID_OPERATIONS, ConfigError

    body = await request.json()
    defaults = body.get("defaults", {})

    try:
        config = load_model_config()
        registry = config["registry"]
        for op, model in defaults.items():
            if op not in VALID_OPERATIONS:
                return JSONResponse({"error": f"Unknown operation '{op}'"}, status_code=400)
            if not isinstance(model, str) or not model:
                return JSONResponse({"error": f"Model for '{op}' must be a non-empty string"}, status_code=400)
            if model not in registry:
                return JSONResponse(
                    {"error": f"Model '{model}' is not in the registry. Add it to models.yaml first."},
                    status_code=400,
                )
            config["defaults"][op] = model

        save_model_config(config["defaults"])
        return {"defaults": config["defaults"], "source": config["source"]}
    except ConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.post("/api/models/reset")
async def reset_models():
    """API: Reset model configuration to built-in defaults (deprecated)."""
    return JSONResponse(
        {"error": "Reset is no longer supported. Edit models.yaml directly."},
        status_code=410,
    )


@router.get("/api/models/available")
async def available_models():
    """API: List all models from the registry with capabilities."""
    from aippt.config import get_model_registry, ConfigError
    try:
        registry = get_model_registry()
    except ConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    result = []
    for name, cfg in registry.items():
        result.append({
            "name": name,
            "provider": cfg.provider,
            "supports_vision": cfg.supports_vision,
            "supports_images": cfg.supports_images,
            "max_input_tokens": cfg.max_input_tokens,
        })
    return result


# ---------------------------------------------------------------------------
# Template configuration endpoints
# ---------------------------------------------------------------------------


@router.get("/api/templates")
async def get_templates():
    """API: Get current template configuration."""
    from aippt.config import load_template_config, TemplateConfigError
    try:
        config = load_template_config()
        return {
            "default_template": config["default_template"],
            "source": config["source"],
        }
    except TemplateConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.put("/api/templates")
async def update_templates(request: Request):
    """API: Update the default template path."""
    from aippt.config import set_template_default, load_template_config, TemplateConfigError

    body = await request.json()
    template_path = body.get("default_template", "").strip()

    if not template_path:
        return JSONResponse({"error": "default_template must be a non-empty string"}, status_code=400)

    try:
        set_template_default(template_path)
        config = load_template_config()
        return {
            "default_template": config["default_template"],
            "source": config["source"],
        }
    except (TemplateConfigError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


# ---------------------------------------------------------------------------
# Taxonomy endpoints
# ---------------------------------------------------------------------------


@router.get("/api/taxonomy")
async def get_taxonomy(request: Request):
    """API: List all taxonomy tags grouped by category."""
    db_path = request.app.state.db_path
    tags = list_taxonomy(db_path)
    # Group by category for the UI
    categories = {}
    for t in tags:
        cat = t["category"] or "(uncategorized)"
        categories.setdefault(cat, []).append(t["name"])
    return {"tags": tags, "by_category": categories}


@router.post("/api/taxonomy")
async def add_taxonomy(request: Request):
    """API: Add a tag to the taxonomy."""
    db_path = request.app.state.db_path
    body = await request.json()
    name = body.get("name", "").strip()
    category = body.get("category", "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    new, updated = add_taxonomy_tags([{"name": name, "category": category}], db_path)
    return {"status": "ok", "new": new, "updated": updated}


@router.delete("/api/taxonomy/{tag_name}")
async def delete_taxonomy(tag_name: str, request: Request):
    """API: Remove a tag from the taxonomy."""
    db_path = request.app.state.db_path
    removed = remove_taxonomy_tag(tag_name, db_path)
    if not removed:
        return JSONResponse({"error": "tag not found"}, status_code=404)
    return {"status": "ok"}


@router.put("/api/taxonomy/{tag_name}")
async def rename_taxonomy(tag_name: str, request: Request):
    """API: Rename a taxonomy tag (also updates slide associations)."""
    db_path = request.app.state.db_path
    body = await request.json()
    new_name = body.get("new_name", "").strip()
    if not new_name:
        return JSONResponse({"error": "new_name is required"}, status_code=400)
    assoc_count = rename_tag(tag_name, new_name, db_path)
    return {"status": "ok", "updated_associations": assoc_count}


@router.post("/api/taxonomy/import")
async def import_taxonomy(request: Request, file: UploadFile = File(...)):
    """API: Import taxonomy from uploaded CSV."""
    db_path = request.app.state.db_path
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb")
    content = await file.read()
    tmp.write(content)
    tmp.close()
    try:
        new, updated = import_taxonomy_csv(tmp.name, db_path)
        return {"status": "ok", "new": new, "updated": updated, "total": new + updated}
    finally:
        os.unlink(tmp.name)


@router.get("/api/taxonomy/export")
async def export_taxonomy(request: Request):
    """API: Export taxonomy as CSV download."""
    db_path = request.app.state.db_path
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    count = export_taxonomy_csv(tmp.name, db_path)
    return FileResponse(tmp.name, filename="taxonomy.csv", media_type="text/csv")


# ---------------------------------------------------------------------------
# AI analysis endpoints
# ---------------------------------------------------------------------------


def _resolve_user_ntid(request: Request, body: dict) -> str:
    """Resolve user NTID from request body, then env var fallback."""
    ntid = body.get("user_ntid", "").strip()
    if not ntid:
        ntid = os.environ.get("AIPPT_USER_NTID", "").strip()
    return ntid


def _make_llm_client(request: Request, operation: str, model_override: str = None, user_ntid: str = None):
    """Create an LLM client using gateway config and model registry.

    Args:
        request: FastAPI request (for app.state access)
        operation: Config operation name ('feedback', 'notes', 'improvements')
        model_override: Optional model name to use instead of configured default
        user_ntid: Optional NTID for the gateway user header

    Returns:
        Configured LLMClient

    Raises:
        ValueError: If model config is missing or gateway cannot be loaded
    """
    from aippt.llm import LLMClient, load_gateway_config
    from aippt.config import get_model_default, ConfigError

    try:
        model = model_override or get_model_default(operation)
    except ConfigError as exc:
        raise ValueError(str(exc))

    gateway = None
    gateway_config_path = getattr(request.app.state, "gateway_config", None)
    if gateway_config_path:
        if os.path.exists(gateway_config_path):
            gateway = load_gateway_config(gateway_config_path)

    if gateway and gateway.user_header and not user_ntid and not gateway.user_value:
        raise ValueError(
            "User NTID is required for LLM gateway requests. "
            "Set your NTID in the web UI or the AIPPT_USER_NTID environment variable."
        )

    try:
        return LLMClient(model=model, gateway=gateway, user_ntid=user_ntid)
    except (ConfigError, ValueError) as exc:
        raise ValueError(str(exc))


def _resolve_db_path(path: str, project_root: str) -> str:
    """Resolve a path from the database (may be relative or absolute)."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(project_root, path))


def _get_slide_image_path(slide_id: int, db_path: str, project_root: str = None):
    """Return the image path for a slide, or None if not found."""
    conn = get_db(db_path)
    row = conn.execute(
        "SELECT image_path FROM slides WHERE id = ?", (slide_id,)
    ).fetchone()
    conn.close()
    if not row or not row["image_path"]:
        return None
    path = _resolve_db_path(row["image_path"], project_root or os.getcwd())
    return path if os.path.exists(path) else None


VIEW_ONLY_MSG = "LLM features are disabled in view-only mode"


@router.post("/api/slides/{slide_id}/analyze")
async def analyze_slide_endpoint(slide_id: int, request: Request):
    """API: Run feedback analysis on a single slide."""
    if getattr(request.app.state, "view_only", False):
        return JSONResponse({"error": VIEW_ONLY_MSG}, status_code=403)
    from aippt.analyze import analyze_slide

    db_path = request.app.state.db_path
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    image_path = _get_slide_image_path(slide_id, db_path, request.app.state.project_root)
    if not image_path:
        return JSONResponse({"error": "No image available for this slide"}, status_code=404)

    conn = get_db(db_path)
    row = conn.execute("SELECT title FROM slides WHERE id = ?", (slide_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Slide not found"}, status_code=404)

    user_ntid = _resolve_user_ntid(request, body)
    try:
        client = _make_llm_client(request, "feedback", body.get("model"), user_ntid=user_ntid)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    try:
        result = analyze_slide(client=client, image_path=image_path, mode="feedback", title=row["title"] or "")
    except Exception as exc:
        return JSONResponse({"error": f"Analysis failed: {exc}"}, status_code=500)

    return {"result": result, "model": client.model}


@router.post("/api/slides/{slide_id}/notes")
async def suggest_notes_endpoint(slide_id: int, request: Request):
    """API: Generate speaker notes for a single slide."""
    if getattr(request.app.state, "view_only", False):
        return JSONResponse({"error": VIEW_ONLY_MSG}, status_code=403)
    from aippt.analyze import analyze_slide

    db_path = request.app.state.db_path
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    image_path = _get_slide_image_path(slide_id, db_path, request.app.state.project_root)
    if not image_path:
        return JSONResponse({"error": "No image available for this slide"}, status_code=404)

    conn = get_db(db_path)
    row = conn.execute("SELECT title FROM slides WHERE id = ?", (slide_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Slide not found"}, status_code=404)

    user_ntid = _resolve_user_ntid(request, body)
    try:
        client = _make_llm_client(request, "notes", body.get("model"), user_ntid=user_ntid)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    try:
        result = analyze_slide(client=client, image_path=image_path, mode="notes", title=row["title"] or "")
    except Exception as exc:
        return JSONResponse({"error": f"Notes generation failed: {exc}"}, status_code=500)

    return {"result": result, "model": client.model}


@router.post("/api/slides/{slide_id}/notes/save")
async def save_notes_endpoint(slide_id: int, request: Request):
    """API: Save notes to the slide record with edit-history tracking."""
    db_path = request.app.state.db_path
    body = await request.json()
    notes = body.get("notes", "").strip()
    source = body.get("source", "web")
    if not notes:
        return JSONResponse({"error": "notes is required"}, status_code=400)

    try:
        changed = record_edit(slide_id, "notes", notes, source=source, db_path=db_path)
    except ValueError:
        return JSONResponse({"error": "Slide not found"}, status_code=404)

    return {"status": "ok", "changed": changed}


@router.get("/api/slides/{slide_id}/notes/history")
async def notes_history_endpoint(slide_id: int, request: Request):
    """API: Return edit history for a slide's notes field, newest first."""
    db_path = request.app.state.db_path
    conn = get_db(db_path)
    row = conn.execute("SELECT id FROM slides WHERE id = ?", (slide_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Slide not found"}, status_code=404)

    rows = conn.execute(
        "SELECT old_value, new_value, source, created_at FROM edit_history "
        "WHERE slide_id = ? AND field = 'notes' ORDER BY id DESC",
        (slide_id,),
    ).fetchall()
    conn.close()

    history = [
        {
            "old_value": r["old_value"],
            "new_value": r["new_value"],
            "source": r["source"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {"history": history}


@router.post("/api/decks/{deck_id}/write-notes")
async def write_notes_to_deck_endpoint(deck_id: int, request: Request):
    """API: Write DB notes back to the original PPTX file (with backup)."""
    from aippt.writeback import write_notes_to_pptx, create_backup

    db_path = request.app.state.db_path
    project_root = request.app.state.project_root
    deck = get_deck_by_id(deck_id, db_path)
    if deck is None:
        return JSONResponse({"error": "Deck not found"}, status_code=404)

    file_path = deck.get("file_path", "")
    if file_path:
        file_path = _resolve_db_path(file_path, project_root)
    if not file_path or not os.path.exists(file_path):
        return JSONResponse({"error": "Source file not found"}, status_code=404)

    try:
        backup_path = create_backup(file_path)
    except FileNotFoundError:
        return JSONResponse({"error": "Source file not found"}, status_code=404)

    try:
        result = write_notes_to_pptx(
            file_path, db_path=db_path, deck_id=deck_id
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return {
        "status": "ok",
        "slides_written": result.slides_written,
        "slides_skipped": result.slides_skipped,
        "slides_total": result.slides_total,
        "backup_path": backup_path,
        "warnings": result.warnings,
    }


@router.post("/api/slides/{slide_id}/improvements")
async def improvements_endpoint(slide_id: int, request: Request):
    """API: Run improvement analysis on a single slide."""
    if getattr(request.app.state, "view_only", False):
        return JSONResponse({"error": VIEW_ONLY_MSG}, status_code=403)
    from aippt.analyze import analyze_slide

    db_path = request.app.state.db_path
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    image_path = _get_slide_image_path(slide_id, db_path, request.app.state.project_root)
    if not image_path:
        return JSONResponse({"error": "No image available for this slide"}, status_code=404)

    conn = get_db(db_path)
    row = conn.execute("SELECT title FROM slides WHERE id = ?", (slide_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Slide not found"}, status_code=404)

    user_ntid = _resolve_user_ntid(request, body)
    try:
        client = _make_llm_client(request, "feedback", body.get("model"), user_ntid=user_ntid)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    try:
        result = analyze_slide(client=client, image_path=image_path, mode="improvements", title=row["title"] or "")
    except Exception as exc:
        return JSONResponse({"error": f"Improvements analysis failed: {exc}"}, status_code=500)

    return {"result": result, "model": client.model}


# ---------------------------------------------------------------------------
# Per-slide tag removal
# ---------------------------------------------------------------------------


@router.delete("/api/slides/{slide_id}/tags/{tag_name}")
async def remove_tag_from_slide(slide_id: int, tag_name: str, request: Request):
    """API: Remove a specific tag from a slide."""
    db_path = request.app.state.db_path
    removed = remove_slide_tag(slide_id, tag_name, db_path)
    if not removed:
        return JSONResponse({"error": "tag not found on slide"}, status_code=404)
    return {"status": "ok", "tags": get_slide_tags(slide_id, db_path)}


@router.get("/slide-image/{slide_id}")
async def serve_slide_image(slide_id: int, request: Request):
    """Serve a slide image by slide ID."""
    db_path = request.app.state.db_path
    project_root = request.app.state.project_root
    conn = get_db(db_path)
    row = conn.execute(
        "SELECT image_path FROM slides WHERE id = ?", (slide_id,)
    ).fetchone()
    conn.close()

    if not row or not row["image_path"]:
        return HTMLResponse("No image", status_code=404)

    image_path = _resolve_db_path(row["image_path"], project_root)
    if os.path.exists(image_path):
        return FileResponse(
            image_path,
            headers={"Cache-Control": "no-cache"},
        )
    return HTMLResponse("Image not found", status_code=404)


# ---------------------------------------------------------------------------
# Microsoft Graph device-code auth endpoints
#
# These are unauthenticated and ignore view-only mode -- they ARE the auth
# path. Tokens are returned to the browser, which holds them in localStorage
# and forwards them as Authorization: Bearer on subsequent calls.
# ---------------------------------------------------------------------------


def _per_deck_images_dir(request: Request, deck_path: str) -> str:
    """Resolve the per-deck images directory under app.state.images_dir.

    Container deployments override the parent images dir via
    ``serve --images-dir /app/data/images`` so PNGs land on the data
    volume; without this helper, ingest_deck falls back to a cwd-relative
    ``images/`` path that lives in ephemeral container storage and is
    lost on pod restart.
    """
    base = getattr(request.app.state, "images_dir", None) or "images"
    deck_name = os.path.splitext(os.path.basename(deck_path))[0]
    return os.path.join(base, deck_name)


def _require_images_for_render() -> bool:
    """Whether the render pipeline must succeed for the upload to succeed.

    On Linux the only image path is Microsoft Graph; a render failure means
    no images at all, which makes the catalog useless. Surface it as an
    HTTP error instead of silently completing.
    """
    return sys.platform.startswith("linux")


def _graph_error_status(exc) -> int:
    """Map a graph.GraphError status_code → an HTTP response status.

    4xx Graph errors pass through (the caller's token or permissions are at
    fault). 5xx and anything weird become 502 Bad Gateway — we couldn't
    complete the request because the upstream service couldn't.
    """
    code = getattr(exc, "status_code", 0) or 0
    if 400 <= code < 500:
        return code
    return 502


def _extract_bearer_token(request: Request) -> str:
    """Return the bearer token from the Authorization header, or '' if absent
    or not a Bearer-scheme header.

    Strict: only ``Authorization: Bearer <token>`` is accepted (case-insensitive
    on 'Bearer'). Anything else — Basic, Digest, a raw token without a scheme,
    or 'Bearer ' with no token — returns '' so the caller treats it as
    unauthenticated.

    Tolerating raw tokens here would let any non-empty Authorization value
    (e.g. ``Authorization: Basic dXNlcjpwYXNz``) slip past the gate.
    """
    raw = request.headers.get("Authorization", "").strip()
    if not raw:
        return ""
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    token = parts[1].strip()
    return token  # empty after strip → '' → treated as unauthenticated


class InvalidNtid(ValueError):
    """Raised when X-AIPPT-NTID is present but fails the allowlist check."""


# NTIDs are interpolated into the SharePoint path
# /sites/.../root:/<root>/<NTID>/<job>.pptx — any character outside this set
# either splits the path ('/', '\\', ':'), escapes the folder ('..'), or
# causes Graph to 4xx deep inside the pipeline (whitespace, '?', '*', '#').
_NTID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _extract_ntid_header(request: Request) -> str:
    """Return the trimmed X-AIPPT-NTID header, or '' if absent.

    Used by the upload endpoints to scope per-user SharePoint render-staging
    folders. We deliberately do NOT fall back to the server-side USER env
    var here — that would route every signed-in user's renders through one
    shared folder. The CLI layer applies env fallbacks for non-web callers.

    Raises InvalidNtid if the header is present but doesn't match
    ``[A-Za-z0-9._-]+``. Validating at the edge keeps malformed input out of
    the Graph request URL.
    """
    raw = request.headers.get("X-AIPPT-NTID", "").strip()
    if not raw:
        return ""
    if not _NTID_RE.match(raw):
        raise InvalidNtid(
            "Invalid X-AIPPT-NTID: must match [A-Za-z0-9._-]+ "
            "(no path separators, whitespace, or URL metacharacters)."
        )
    return raw


def _ntid_or_400(request: Request):
    """Wrap ``_extract_ntid_header`` for the edge endpoints.

    Returns ``(ntid, None)`` on success or ``("", JSONResponse(400))`` if the
    header is malformed. The JSONResponse is shaped like the other 4xx errors
    (``{"error": "..."}``) so the existing client error handling works.
    """
    try:
        return _extract_ntid_header(request), None
    except InvalidNtid as exc:
        return "", JSONResponse({"error": str(exc)}, status_code=400)


async def _read_json_body_or_400(request: Request):
    """Parse the request body as JSON; return ({}, None) when empty,
    (body, None) on success, or ({}, JSONResponse(400)) for malformed input.

    Without this guard, FastAPI hands ``json.loads`` an arbitrary byte
    stream — a client sending ``Content-Type: application/x-www-form-urlencoded``
    triggers ``JSONDecodeError`` and bubbles a 500 to the user. Auth
    endpoints in particular should never 500 on malformed input; the JS
    client treats 5xx very differently from 4xx.
    """
    raw = await request.body()
    if not raw:
        return {}, None
    try:
        return json.loads(raw), None
    except (json.JSONDecodeError, ValueError):
        return {}, JSONResponse(
            {"error": "Request body must be valid JSON"}, status_code=400,
        )


def _user_auth_error_status(exc) -> int:
    """Status mapping for /poll and /refresh.

    These endpoints' GraphErrors come in two flavors:
      - 4xx from AAD (expired_token, access_denied, invalid_grant) → the user
        needs to re-auth. The browser keys off HTTP 401 to abort the flow,
        so we collapse all 4xx into 401.
      - 5xx from AAD (service outage) → re-auth won't help. Surface as 502
        so the UI shows a transient error instead of bouncing the user back
        to sign-in repeatedly.
    """
    code = getattr(exc, "status_code", 0) or 0
    if 500 <= code:
        return 502
    return 401


@router.post('/api/auth/microsoft/start')
async def auth_microsoft_start(request: Request):
    """Start a Microsoft device-code flow. Unauthenticated."""
    try:
        return graph.start_device_code()
    except graph.GraphError as exc:
        # Pass 4xx through (server-config bugs like invalid_client are easier
        # to debug when the real status reaches the client); collapse 5xx to
        # 502 so transient AAD outages don't masquerade as our bugs.
        return JSONResponse(
            {"error": f"Microsoft auth start failed: {exc.message}",
             "code": exc.error_code},
            status_code=_graph_error_status(exc),
        )


@router.post('/api/auth/microsoft/poll')
async def auth_microsoft_poll(request: Request):
    """Poll the device-code endpoint once. Unauthenticated.

    Body: ``{"device_code": "..."}``.
    Returns either ``{"status": "pending"}`` or the token-bearing dict.
    """
    body, err = await _read_json_body_or_400(request)
    if err is not None:
        return err
    device_code = (body or {}).get("device_code", "").strip()
    if not device_code:
        return JSONResponse(
            {"error": "device_code is required"}, status_code=400,
        )
    try:
        return graph.poll_device_code(device_code)
    except graph.GraphError as exc:
        return JSONResponse(
            {"error": exc.message, "code": exc.error_code},
            status_code=_user_auth_error_status(exc),
        )


@router.post('/api/auth/microsoft/refresh')
async def auth_microsoft_refresh(request: Request):
    """Exchange a refresh token for a fresh access token. Unauthenticated."""
    body, err = await _read_json_body_or_400(request)
    if err is not None:
        return err
    refresh_token = (body or {}).get("refresh_token", "").strip()
    if not refresh_token:
        return JSONResponse(
            {"error": "refresh_token is required"}, status_code=400,
        )
    try:
        return graph.refresh_access_token(refresh_token)
    except graph.GraphError as exc:
        return JSONResponse(
            {"error": exc.message, "code": exc.error_code},
            status_code=_user_auth_error_status(exc),
        )


# ---------------------------------------------------------------------------
# Deck upload and download endpoints
# ---------------------------------------------------------------------------


@router.post('/api/decks/upload')
async def upload_deck(
    request: Request,
    file: UploadFile = File(...),
    generate_tags: bool = Form(False),
):
    """API: Upload a .pptx file, export images, catalog, and optionally generate tags.

    Requires an ``Authorization: Bearer <ms-token>`` header so the Linux
    Graph render path has a token. Returns 403 in view-only mode and 401
    when no token was provided.
    """
    db_path = request.app.state.db_path
    uploads_dir = request.app.state.uploads_dir
    gateway_config = request.app.state.gateway_config

    # Validate file extension
    if not file.filename or not file.filename.lower().endswith('.pptx'):
        return JSONResponse({'error': 'Only .pptx files are supported'}, status_code=400)

    # View-only deployments cannot ingest at all (LLM access required for
    # downstream tagging, and the render path needs a per-user MS token).
    if getattr(request.app.state, "view_only", False):
        return JSONResponse(
            {"error": "Deck ingest is disabled in view-only mode"},
            status_code=403,
        )

    ms_token = _extract_bearer_token(request)
    if not ms_token:
        return JSONResponse(
            {"error": "Microsoft sign-in required for ingest. "
                      "Sign in with the Microsoft button and retry."},
            status_code=401,
        )
    ntid, _ntid_err = _ntid_or_400(request)
    if _ntid_err is not None:
        return _ntid_err

    # Build a collision-safe filename and save to uploads_dir
    unique_prefix = uuid.uuid4().hex
    safe_name = f'{unique_prefix}_{file.filename}'
    dest_path = os.path.join(uploads_dir, safe_name)

    content = await file.read()
    with open(dest_path, 'wb') as fh:
        fh.write(content)

    # Run ingest pipeline: export images → catalog → optional tags
    try:
        result = ingest_deck(
            deck_path=dest_path,
            db_path=db_path,
            images_dir=_per_deck_images_dir(request, dest_path),
            generate_tags=generate_tags,
            gateway_config=gateway_config,
            require_images=_require_images_for_render(),
            ms_token=ms_token,
            ntid=ntid,
        )
    except graph.GraphError as exc:
        return JSONResponse(
            {'error': f'Microsoft Graph error: {exc.message}',
             'code': exc.error_code},
            status_code=_graph_error_status(exc),
        )
    except RuntimeError as exc:
        # ingest_deck raises RuntimeError when require_images=True and the
        # render path failed for a non-Graph reason (pdftoppm missing, etc.)
        return JSONResponse(
            {'error': str(exc)}, status_code=502,
        )
    except Exception as exc:
        return JSONResponse({'error': f'Failed to ingest deck: {exc}'}, status_code=500)

    # Build descriptive message
    parts = [f"Deck '{result['deck_name']}' uploaded"]
    parts.append(f"{result['slide_count']} slide{'s' if result['slide_count'] != 1 else ''}")
    if result['images_exported']:
        parts.append("images exported")
    if result['tags_generated']:
        parts.append("tags generated")

    return {
        'id': result['deck_id'],
        'name': result['deck_name'],
        'display_name': display_name(result['deck_name']),
        'slide_count': result['slide_count'],
        'images_exported': result['images_exported'],
        'tags_generated': result['tags_generated'],
        'message': " — ".join(parts),
    }


def _save_image_uploads(md_text, outline_save_path, image_data):
    """Save uploaded images to paths matching IMAGE: directives.

    Parses IMAGE: directives from the outline to determine subdirectory
    structure (e.g., ``IMAGE: memes/photo.jpg`` -> save as ``memes/photo.jpg``
    relative to the outline). Falls back to saving with the original filename
    if no matching directive is found.

    Args:
        md_text: Raw markdown outline text.
        outline_save_path: Path where the outline was saved on disk.
        image_data: List of (filename, bytes) tuples from uploaded images.
    """
    outline_dir = os.path.dirname(outline_save_path)

    # Build map: basename -> relative path from IMAGE: directives
    image_map = {}
    for match in re.finditer(r'^IMAGE:\s*(.+)$', md_text, re.MULTILINE):
        path = match.group(1).strip()
        basename = os.path.basename(path)
        image_map[basename] = path

    for filename, data in image_data:
        # Look up full relative path from IMAGE: directives
        rel_path = image_map.get(filename, filename)
        save_path = os.path.join(outline_dir, rel_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(data)


@router.post('/api/decks/create')
async def create_deck_stream(
    request: Request,
    outline_text: str = Form(None),
    outline_file: UploadFile = File(None),
    enhance: bool = Form(True),
    model: str = Form(None),
    audience: str = Form(None),
    title: str = Form(None),
    image_files: List[UploadFile] = File(default=[]),
):
    """API: Create a deck from markdown outline, streaming progress as SSE."""
    if getattr(request.app.state, "view_only", False):
        return JSONResponse({"error": VIEW_ONLY_MSG}, status_code=403)

    ms_token = _extract_bearer_token(request)
    if not ms_token:
        return JSONResponse(
            {"error": "Microsoft sign-in required for ingest. "
                      "Sign in with the Microsoft button and retry."},
            status_code=401,
        )
    ntid, _ntid_err = _ntid_or_400(request)
    if _ntid_err is not None:
        return _ntid_err

    import asyncio
    import json
    import queue as _queue

    from aippt.pipeline import run_pipeline, PipelineConfig
    from aippt.config import get_template_default, TemplateConfigError

    # --- Validate inputs before entering SSE mode ---
    md_text = None
    if outline_text and outline_text.strip():
        md_text = outline_text
    elif outline_file and outline_file.filename:
        content = await outline_file.read()
        md_text = content.decode("utf-8")

    if not md_text or not md_text.strip():
        return JSONResponse(
            {"error": "Provide outline text or upload a .md file"},
            status_code=400,
        )

    try:
        template_path = get_template_default()
    except TemplateConfigError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    if not os.path.exists(template_path):
        return JSONResponse(
            {"error": f"Template not found: {template_path}. Update the path in Settings."},
            status_code=404,
        )

    db_path = request.app.state.db_path
    uploads_dir = request.app.state.uploads_dir
    gateway_config = request.app.state.gateway_config

    # Derive filename from outline title (first H1 or H2)
    _title_match = re.search(r'^#{1,2}\s+(.+)', md_text, re.MULTILINE)
    _base_name = _title_match.group(1).strip() if _title_match else "generated"
    # Sanitize for filesystem: keep alphanumeric, spaces, hyphens, underscores
    _base_name = re.sub(r'[^\w\s-]', '', _base_name).strip()
    _base_name = re.sub(r'\s+', ' ', _base_name)[:80]  # cap length
    _short_id = uuid.uuid4().hex[:8]
    output_path = os.path.join(uploads_dir, f"{_short_id}_{_base_name}.pptx")

    # Save outline to disk for IMAGE: directive resolution
    outline_filename = outline_file.filename if (outline_file and outline_file.filename) else "outline.md"
    outline_save_path = os.path.join(uploads_dir, f"{_short_id}_{outline_filename}")
    with open(outline_save_path, 'w', encoding='utf-8') as f:
        f.write(md_text)

    # Save uploaded images relative to the outline
    image_data = []
    for img in (image_files or []):
        if img.filename:
            data = await img.read()
            if data:
                image_data.append((img.filename, data))
    if image_data:
        _save_image_uploads(md_text, outline_save_path, image_data)

    event_q: _queue.Queue = _queue.Queue()

    def create_progress(step, detail=""):
        # Map completion markers to done status
        status = "running"
        if any(detail.startswith(w) for w in ("Parsed", "All", "Built")):
            status = "done"
        event_q.put(("progress", {"step": step, "status": status, "detail": detail}))

    def ingest_progress(step, detail=""):
        ingest_map = {
            "export_images": "running", "export_images_done": "running",
            "export_images_skipped": "running", "catalog": "running",
            "catalog_done": "running", "complete": "done",
        }
        if step in ingest_map:
            event_q.put(("progress", {"step": "ingest", "status": ingest_map[step], "detail": detail}))

    async def _event_generator():
        loop = asyncio.get_running_loop()

        def _worker():
            pipeline_config = PipelineConfig(
                outline_text=md_text,
                template_path=template_path,
                output_path=output_path,
                enhance=enhance,
                model=model,
                audience=audience,
                gateway_config=gateway_config,
                progress_callback=create_progress,
                outline_path=outline_save_path,
            )
            pipeline_result = run_pipeline(pipeline_config)
            result = {
                "output_path": pipeline_result.output_path,
                "slide_count": pipeline_result.slide_count,
                "title": pipeline_result.title,
            }
            event_q.put(("progress", {"step": "ingest", "status": "running", "detail": "Cataloging generated deck..."}))
            ingest_result = ingest_deck(
                deck_path=output_path,
                db_path=db_path,
                images_dir=_per_deck_images_dir(request, output_path),
                gateway_config=gateway_config,
                require_images=_require_images_for_render(),
                progress_callback=ingest_progress,
                ms_token=ms_token,
                ntid=ntid,
            )
            return {**result, **ingest_result}

        future = loop.run_in_executor(None, _worker)

        def _format_sse(event_name, payload):
            return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

        while not future.done():
            await asyncio.sleep(0)
            while True:
                try:
                    event_name, payload = event_q.get_nowait()
                    yield _format_sse(event_name, payload)
                except _queue.Empty:
                    break

        while True:
            try:
                event_name, payload = event_q.get_nowait()
                yield _format_sse(event_name, payload)
            except _queue.Empty:
                break

        try:
            result = await future
        except graph.GraphError as exc:
            yield _format_sse("error", {
                "detail": f"Microsoft Graph error: {exc.message}",
                "code": exc.error_code,
                "status": _graph_error_status(exc),
            })
            return
        except Exception as exc:
            yield _format_sse("error", {"detail": str(exc)})
            return

        yield _format_sse("complete", {
            "deck_id": result["deck_id"],
            "deck_name": result["deck_name"],
            "display_name": display_name(result["deck_name"]),
            "slide_count": result["slide_count"],
            "output_path": result["output_path"],
        })

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.post('/api/decks/upload-stream')
async def upload_deck_stream(
    request: Request,
    file: UploadFile = File(...),
    generate_tags: bool = Form(False),
):
    """API: Upload a .pptx file and stream progress as Server-Sent Events.

    The response is a ``text/event-stream`` that emits ``progress`` events for
    each ingest step (export_images, catalog, tags) and a final ``complete`` or
    ``error`` event.  Clients that do not support SSE should use the regular
    ``/api/decks/upload`` endpoint instead.
    """
    import asyncio
    import json
    import queue as _queue

    # NOTE: ingest_deck is imported at module top; do NOT re-import locally,
    # or test patches on `aippt.web.routes.ingest_deck` won't take effect for
    # the SSE handler.

    # Validate file extension before entering SSE mode so we can return a
    # plain JSON 400 response (SSE has already started once we yield the first
    # byte, so validation must happen first).
    if not file.filename or not file.filename.lower().endswith('.pptx'):
        return JSONResponse({'error': 'Only .pptx files are supported'}, status_code=400)

    # Same gates as /api/decks/upload — view-only blocks ingest entirely, and
    # the Linux Graph render path requires a per-user MS token from the browser.
    if getattr(request.app.state, "view_only", False):
        return JSONResponse(
            {"error": "Deck ingest is disabled in view-only mode"},
            status_code=403,
        )

    ms_token = _extract_bearer_token(request)
    if not ms_token:
        return JSONResponse(
            {"error": "Microsoft sign-in required for ingest. "
                      "Sign in with the Microsoft button and retry."},
            status_code=401,
        )
    ntid, _ntid_err = _ntid_or_400(request)
    if _ntid_err is not None:
        return _ntid_err

    db_path = request.app.state.db_path
    uploads_dir = request.app.state.uploads_dir
    gateway_config = request.app.state.gateway_config

    # Save uploaded file to uploads_dir
    unique_prefix = uuid.uuid4().hex
    safe_name = f'{unique_prefix}_{file.filename}'
    dest_path = os.path.join(uploads_dir, safe_name)

    content = await file.read()
    with open(dest_path, 'wb') as fh:
        fh.write(content)

    # Step-name → (step field, status field) mapping
    _STEP_MAP = {
        'export_images':         ('export_images', 'running'),
        'export_images_done':    ('export_images', 'done'),
        'export_images_skipped': ('export_images', 'skipped'),
        'catalog':               ('catalog',        'running'),
        'catalog_done':          ('catalog',        'done'),
        'tags':                  ('tags',           'running'),
        'tags_done':             ('tags',           'done'),
        'tags_partial':          ('tags',           'done'),
        'tags_error':            ('tags',           'error'),
    }

    # Queue is used to pass events from the worker thread to the generator.
    event_q: _queue.Queue = _queue.Queue()

    def progress_callback(step: str, detail: str = ''):
        """Called by ingest_deck at each pipeline stage."""
        if step in _STEP_MAP:
            mapped_step, status = _STEP_MAP[step]
            event_q.put(('progress', {'step': mapped_step, 'status': status, 'detail': detail}))
        # 'complete' is handled after the future resolves

    async def _event_generator():
        """Async generator that drives the ingest in a thread and yields SSE lines."""
        loop = asyncio.get_running_loop()

        # Run the blocking ingest in a thread pool executor so we don't block
        # the event loop.  Events land on event_q via progress_callback.
        future = loop.run_in_executor(
            None,
            lambda: ingest_deck(
                deck_path=dest_path,
                db_path=db_path,
                images_dir=_per_deck_images_dir(request, dest_path),
                generate_tags=generate_tags,
                gateway_config=gateway_config,
                require_images=_require_images_for_render(),
                progress_callback=progress_callback,
                ms_token=ms_token,
                ntid=ntid,
            ),
        )

        def _format_sse(event_name: str, payload: dict) -> str:
            return f'event: {event_name}\ndata: {json.dumps(payload)}\n\n'

        # Drain queued progress events while the future runs.
        while not future.done():
            # Give the event loop a chance to advance the future.
            await asyncio.sleep(0)
            while True:
                try:
                    event_name, payload = event_q.get_nowait()
                    yield _format_sse(event_name, payload)
                except _queue.Empty:
                    break

        # Drain any remaining events that arrived before the loop exited.
        while True:
            try:
                event_name, payload = event_q.get_nowait()
                yield _format_sse(event_name, payload)
            except _queue.Empty:
                break

        # Retrieve the result (or propagate the exception).
        try:
            result = await future
        except graph.GraphError as exc:
            yield _format_sse('error', {
                'detail': f'Microsoft Graph error: {exc.message}',
                'code': exc.error_code,
                'status': _graph_error_status(exc),
            })
            return
        except Exception as exc:  # noqa: BLE001
            yield _format_sse('error', {'detail': str(exc)})
            return

        yield _format_sse('complete', {
            'deck_id':        result['deck_id'],
            'deck_name':      result['deck_name'],
            'display_name':   display_name(result['deck_name']),
            'slide_count':    result['slide_count'],
            'images_exported': result['images_exported'],
            'tags_generated':  result['tags_generated'],
        })

    return StreamingResponse(_event_generator(), media_type='text/event-stream')


@router.get('/api/decks/{deck_id}/download')
async def download_deck(deck_id: int, request: Request):
    """API: Download a .pptx file with DB notes applied (temp copy, original untouched)."""
    from aippt.writeback import write_notes_to_pptx

    db_path = request.app.state.db_path
    project_root = request.app.state.project_root

    deck = get_deck_by_id(deck_id, db_path)
    if deck is None:
        return JSONResponse({'error': 'Deck not found'}, status_code=404)

    file_path = deck.get('file_path', '')
    if file_path:
        file_path = _resolve_db_path(file_path, project_root)
    if not file_path or not os.path.exists(file_path):
        return JSONResponse({'error': 'Source file not found'}, status_code=404)

    # Create temp copy with DB notes applied
    tmp = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    tmp.close()
    try:
        write_notes_to_pptx(
            file_path, db_path=db_path, deck_id=deck_id, output_path=tmp.name
        )
    except (FileNotFoundError, ValueError):
        # If write-back fails (e.g. mismatch), fall back to serving original
        os.unlink(tmp.name)
        tmp_name = file_path
    else:
        tmp_name = tmp.name

    download_name = display_name(deck['name'])
    return FileResponse(
        tmp_name,
        media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        headers={'Content-Disposition': f'attachment; filename="{download_name}.pptx"'},
    )
