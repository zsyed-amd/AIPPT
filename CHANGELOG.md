# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Theme token schema v2: typography scale (14 tokens), data visualization colors (6 tokens), shadow configuration (5 tokens), and eyebrow component tokens (4 tokens) in theme YAML
- `createDeck()` accepts `overrides` option for per-deck token adjustments by agents
- Expanded color slots: `code_bg`, `code_text`, `heading_color`, `eyebrow_color`, `stat_color`

### Changed

- ~40 hardcoded design values in pptxgenjs helpers now read from theme tokens
- `cardShadow()` accepts `theme` parameter and reads from `theme.shadow.*`
- All three bundled themes updated with explicit token values (no visual change for `default` and `amd`; `instinct` gets design-system-aligned values)

### Added

- Sphinx-based documentation covering CLI reference, web UI guide, backup/restore, and configuration
- "Docs" link in web UI nav bar opening built documentation in a new tab
- FastAPI static mount at `/docs` serving Sphinx HTML (conditional on docs being built)
- `docs-requirements.txt` with Sphinx dependencies

### Changed

- Rebranded from "Outline2PPT" to "AIPPT" — package, CLI, web UI, and all documentation
- Package directory renamed from `outline2ppt/` to `aippt/`
- CLI entry point renamed from `outline2ppt.py` to `aippt.py`
- Removed legacy `ppt2outline.py` wrapper script

### Added

- `Dockerfile` for containerized deployment
- `docker-compose.yml` with view-only (default) and full profiles
- `.dockerignore` for efficient image builds
- `AIPPT_VIEW_ONLY` environment variable for container-friendly view-only configuration
- Library / view-only mode for the web UI (`--view-only` flag or auto-detected when no LLM config)
- New `GET /api/config` endpoint exposing frontend configuration
- LLM-dependent features visibly disabled with "LLM not configured" tooltips in view-only mode
- "Library Mode" badge in nav bar when view-only is active
- Web UI: Tag browsing sidebar for filtering slides by tag across all decks
- Web UI: Sidebar toggle button in navigation bar with localStorage persistence
- Web UI: Multi-select tag filtering with AND logic and grouped-by-category display
- API: `GET /api/tags` endpoint returning all tags with slide counts and categories
- `get_all_tags()` function in catalog module for querying tags with counts
- `dirs.yaml` configuration file for standardized directory paths (outlines, templates, uploads, output, backups, images, database)
- `aippt/config.py`: `load_dirs_config()`, `resolve_path()`, and `DirsConfigError` for directory configuration management
- `dirs.yaml` auto-created with defaults on first run if it doesn't exist
- `migrate-paths` CLI command to convert absolute DB paths to relative (idempotent)
- `backup.sh --export` creates portable `tar.gz` archive in `backups/` with slides.db, images, uploads, dirs.yaml, and dbinfo.json
- `restore.sh` imports an export archive and sets up a working library directory
- Outline directives: `LAYOUT:` to specify slide layout type and `IMAGE:` to embed images directly from the outline
- Author-specified layouts override LLM suggestions when using `--enhance`
- Image paths resolved relative to the outline file's directory
- New example outline: `examples/outline-with-directives.md`
- Web UI: Next/prev navigation buttons in slide detail modal for sequential browsing
- Web UI: Keyboard navigation (Left/Right arrow keys) in slide detail modal
- Web UI: Slide position indicator ("3 of 15") in modal header
- Reverse: `--enhance` flag for LLM-powered outline generation using multimodal AI
- Reverse: `--model`, `--gateway-config`, `--images-dir` options for enhanced mode
- Enhanced reverse describes diagrams and visual elements as structured bullet points instead of listing shape labels
- Web UI: Create presentations from markdown outlines (paste text or upload .md file)
- Web UI: Enhanced mode toggle for LLM-powered layout and speaker notes generation
- Web UI: Model selector for enhanced mode generation
- Web UI: SSE progress streaming during deck generation
- Web UI: Template path configurable in Settings view
- Default template configuration via `templates.yaml`
- API: `POST /api/decks/create` SSE endpoint for outline-to-PPTX generation
- API: `GET/PUT /api/templates` endpoints for template configuration
- Reusable `create_deck()` function extracted from CLI for web endpoint reuse
- `models.yaml` configuration file for per-operation default model selection
- `aippt models` CLI command to view, set, and reset default models
- Settings page in web UI for model configuration
- `/api/models`, `/api/models/available`, and `/api/models/reset` API endpoints
- Taxonomy management: `aippt tags` CLI commands to list, add, remove, import, export, and rename taxonomy tags
- Per-slide tag management: `aippt tag` and `aippt untag` CLI commands
- Tag removal in web UI slide detail dialog (click "x" on tag badge)
- Taxonomy management section in web UI Settings page
- Tag autocomplete from taxonomy in web UI
- `/api/taxonomy` and `/api/slides/{id}/tags/{name}` API endpoints
- Deck metadata: author, creation date, and modified date extracted from PPTX file properties during catalog
- Slide metadata: author (inherited from deck) and creation date displayed in slide detail view
- Web UI: Author and date columns in deck list table
- Web UI: Metadata section in slide detail modal
- CSV export: Author and date columns included
- Web UI: Upload PowerPoint decks directly from the browser with automatic cataloging
- Web UI: Download original `.pptx` files from the deck list
- API: `POST /api/decks/upload` endpoint for deck upload and ingest
- API: `GET /api/decks/{deck_id}/download` endpoint for deck download
- CLI: `--uploads-dir` option for web server to configure upload storage location
- Real-time per-step progress display when uploading decks in the web UI (SSE streaming)
- Upload button disabled during processing to prevent duplicate uploads
- API: `POST /api/decks/upload-stream` SSE endpoint for streaming ingest progress
- Web UI: Editable speaker notes in slide detail modal with save/cancel controls
- Web UI: Dirty-state indicator and unsaved-changes guard for notes editing
- Web UI: Notes edit history panel showing previous versions with timestamps
- Web UI: Ctrl+S / Cmd+S keyboard shortcut to save notes
- API: `GET /api/slides/{id}/notes/history` endpoint
- Database: Edit history tracking for notes changes (via `edit_history` table)
- CLI: `aippt write-notes` command to write DB notes back to PPTX files
- Web UI: "Write Notes to Deck" button in deck list
- API: `POST /api/decks/{id}/write-notes` endpoint with automatic backup
- Automatic timestamped backup (`.pptx.bak`) before modifying PPTX files

### Improved

- Reverse: bullet hierarchy preserved using paragraph indentation levels
- Reverse: multi-line titles joined with proper spacing
- Reverse: "Default Section" header suppressed from output
- Reverse: smarter title detection reduces "Untitled Slide" occurrences
- Reverse: tables rendered as proper markdown tables
- Reverse: decorative shapes (connectors, callout numbers, footers) filtered from output

### Changed

- LLM API endpoints return 403 in view-only mode instead of failing with cryptic errors
- Upload endpoint silently suppresses `generate_tags` in view-only mode
- Database paths (`file_path`, `image_path`) now stored as relative paths for portability
- `catalog_deck()` accepts `base_dir` parameter for relative path computation
- CLI commands (`serve`, `catalog`, `ingest`, `export-images`) read directory defaults from `dirs.yaml`
- Web app resolves relative DB paths at serve time (backward-compatible with absolute paths)
- `backup.sh` defaults backup location to `backups/` directory (export mode)
- `POST /api/slides/{id}/notes/save` now records previous value in edit history before overwriting
- `POST /api/slides/{id}/notes/save` now updates `updated_at` timestamp
- AI-generated notes saves now recorded with `source: 'ai'` in edit history
- `GET /api/decks/{id}/download` now applies DB notes to the downloaded file (original untouched)
- `analyze --mode tags` now uses the database taxonomy table when no `--taxonomy` CSV is provided
- `catalog_deck()` now reads PPTX `core_properties` for metadata extraction
- Database schema updated with new columns (backward-compatible with defaults)

### Fixed

- Deck names in the web UI no longer show the internal UUID prefix from uploaded files
- Downloaded deck files now use the original filename instead of the UUID-prefixed name
- Reverse round-trip: speaker notes no longer leak into slide body when reversed markdown is used with `create`
- Reverse: analysis artifacts (`[Note: analysis based on slide text only...]`) stripped from speaker notes
- Reverse: notes now emitted as HTML comments (`<!-- notes ... -->`) instead of `*Notes:*` bullet lists
- New `--strip-notes` flag on `reverse` command to omit speaker notes entirely

## [2.0.0] - 2026-02-20

Complete rewrite from standalone scripts into a modular Python package with catalog, remix, analysis, and web UI capabilities.

### Added

- **Package structure**: Refactored into `outline2ppt/` package with dedicated modules for each concern
- **Unified CLI**: Single entry point (`outline2ppt.py`) with 8 subcommands: `create`, `reverse`, `catalog`, `analyze`, `search`, `remix`, `export`, `serve`
- **LLM gateway support**: YAML-configurable corporate API gateway routing with custom auth headers (`gateway.yaml`)
- **SQLite slide catalog** (`catalog.py`): Content hashing (SHA-256), file deduplication, slide versioning, tag management
- **Multimodal analysis** (`analyze.py`): Three modes -- `feedback` (design review), `notes` (speaker note generation), `tags` (auto-tagging via AI or taxonomy)
- **Tagging system**: Free-form AI tags, taxonomy-constrained tags, and manual tags with source tracking
- **CSV export** (`export.py`): Export slide metadata (title, notes, tags, hash, image path) per-deck or across all decks
- **Remix system** (`remix.py`): YAML manifest generation from search results, slide copying via XML manipulation, deck assembly with version warnings
- **Search command**: Filter cataloged slides by tags and/or title substring, export results as remix manifests
- **Web UI** (`web/`): FastAPI + htmx + Pico CSS single-page app with deck browser, slide thumbnails, search, manual tagging, and CSV export
- **Test suite**: 211 unit and integration tests across 14 test files; pytest with ~80% business logic coverage
- **Integration tests**: End-to-end tests covering catalog-search-tag-export-remix workflow
- **`pyproject.toml`**: Modern Python packaging configuration
- **Documentation**: `CLAUDE.md` (v2), `TESTING.md`, `TESTING-RESULTS.md`, `UITESTING.md`, `WORKFLOWS.md`

### Changed

- **Model registry**: Trimmed from 99+ models to a curated set of commonly available models
- **Provider detection**: Simplified `infer_provider()` with substring matching for Claude, Gemini, GPT families
- **LLMClient**: Constructor accepts optional `gateway` config; falls back to direct API keys when absent
- **File encoding**: All `open()` calls now specify `encoding='utf-8'` explicitly (fixes Windows `cp1252` errors)

### Fixed

- `UnicodeDecodeError` on Windows when reading markdown files with Unicode characters (trademark symbols, checkmarks)

## [1.0.0] - 2025-04-16

### Added

- `outline2ppt.py`: Convert markdown outlines to PowerPoint presentations
  - H1 headers become slide titles; subsequent lines become slide content
  - AI enhancement via Anthropic and OpenAI-compatible APIs
  - Four layout types: bullet, two-column, diagram, basic
  - SVG diagram generation (Claude) and raster image generation (DALL-E)
  - Progress persistence -- PPTX saved after each slide
  - 99+ model configurations across 7 providers
- `ppt2outline.py`: Reverse conversion from PowerPoint to markdown
  - Recursive shape text extraction (groups, tables)
  - Optional speaker notes inclusion

[unreleased]: https://github.com/shamsway/aippt/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/shamsway/aippt/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/shamsway/aippt/releases/tag/v1.0.0
