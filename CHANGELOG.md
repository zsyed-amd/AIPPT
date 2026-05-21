# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `GET /api/logs` — in-memory ring buffer (capacity 2000) of recent log records for in-browser triage on the SLAI platform, where `kubectl logs` is not exposed to deck authors. Bearer-gated, allowed in view-only mode, supports `limit` / `level` / `since` (cursor polling) / `logger_prefix` filters. The `AuthorizationScrubFilter` is attached directly to the handler so `Bearer <token>` strings are redacted before they land in the buffer (Python logger filters do not run for propagated records; only handler filters do). Re-installed in the FastAPI lifespan because `uvicorn.run` calls `logging.config.dictConfig` after `create_app` and replaces handlers on `uvicorn.access` / `uvicorn.error`.
- `DELETE /api/decks/{id}` — bearer-gated deck removal for ops cleanup during testing. Rejected in view-only mode. Optional `?purge_images=false` keeps the rendered PNG directory; default purges it. Not yet surfaced in the UI.
- `templates.yaml` is now baked into the container image so `GET /api/templates` no longer returns 503 on the platform.
- NTID is now required as a gating first step inside the Microsoft sign-in modal. Clicking **Sign in to Microsoft** opens an NTID entry screen before the device-code exchange begins; the **Continue** button stays disabled until the value matches `^[A-Za-z0-9._-]+$` and an inline error explains the restriction. A small **(edit)** link on the device-code screen lets users correct a typo (abandons the current device code; the next **Continue** starts a fresh exchange).
- Small read-only `👤 ntid` badge appears in the nav bar next to **Sign out** when the user is signed in and an NTID is saved.

### Changed

- `signOut()` now also clears `localStorage.aippt_ntid` so the next sign-in re-prompts for an NTID.

### Removed

- Floating NTID `<input>` from the nav bar (`#ntid-nav-item`, `#ntid-input`). NTID entry is now handled exclusively inside the sign-in modal.

### Fixed

- Linux Graph render path: `aippt/render.py` now renames `pdftoppm`'s `slide-NN.png` output to the `Slide{i}.png` pattern that `catalog_deck` globs for, so `/api/decks/{id}/slides` returns populated `image_path` values and the UI thumbnail grid renders. Previously every slide had `image_path: null` even when the upload reported `images_exported: true`.
- `app.py` startup hook migrated from the deprecated `@app.on_event("startup")` to an `asynccontextmanager` lifespan.

### Documentation

- Get-well pass on the Sphinx reference (`docs/`) to reconcile with features shipped since v3.0. Per-page audit + one PR per touched page per `.local-docs/plans/2026-05-20-docs-get-well.md` (audit results in `2026-05-20-docs-audit-results.md`). Updated `overview.rst` (Graph render, Microsoft auth, skills bullet), `cli.rst` (new `decks` and `mcp` subcommand sections, `serve --host` / `--images-dir` flags), `configuration.rst` (`sharepoint:` block, `gateway.user_header`, `AIPPT_USER_NTID`, `MS_ACCESS_TOKEN`, `BASE_PATH`), `export-images.rst` (Linux/Microsoft Graph path alongside Windows COM), `web-ui.rst` (Microsoft sign-in, NTID input, theme toggle, Instinct reskin, sectioned decks, audience selector), `backup-restore.rst` (audited, no changes), and adopted `sharepoint-setup.md` into the toctree via `myst-parser` so cross-references resolve. `requirements.txt` gained `sphinx`, `sphinx-rtd-theme`, and `myst-parser` so the Sphinx build runs on a clean checkout.

## [3.5.0] - 2026-05-20 — Linux Image Rendering via Microsoft Graph

### Added

- Stat callout cards with shadow and rounded corners
- URL auto-linking in slide content (bare URLs converted to hyperlinks)
- Microsoft Graph render pipeline for Linux/containerized deployments: PPTX → SharePoint → `?format=pdf` → `pdftoppm` → per-slide PNGs (`aippt/graph.py`, `aippt/render.py`). Removes the PowerPoint COM dependency for image export on non-Windows hosts.
- Device-code Microsoft sign-in in the web UI (`static/js/ms-auth.js`) — tokens live only in browser `localStorage`; the server is stateless and accepts `Authorization: Bearer` per request.
- `X-AIPPT-NTID` header allowlist validation (`^[A-Za-z0-9._-]+$`) on upload/create endpoints — rejects path-traversal and shell-metacharacter values with a 400 before reaching the SharePoint staging path.
- `MS_ACCESS_TOKEN` env var path for the CLI `export-images` command on Linux.
- `--images-dir` flag on `aippt serve`, threaded through all `ingest_deck` call sites so the Dockerfile/K8s `/app/data/images` path is honored instead of falling back to a cwd-relative `images/` (which was invisible to a PVC mounted at `/app/data` and lost on pod restart).
- `gateway.yaml` `sharepoint:` block (`render_site_id`, `render_drive_id`, optional `render_root_path`) loaded by `aippt/config.py`.
- `docs/sharepoint-setup.md` — provisioning, IDs, permissions, and verification for the staging library.
- `poppler-utils` installed in the Dockerfile (provides `pdftoppm`).
- Live integration tests at `tests/test_graph_live.py`, opt-in via `-m live` and `MS_ACCESS_TOKEN` (+ `AIPPT_SP_SITE_ID` / `AIPPT_SP_DRIVE_ID` for the end-to-end render check).
- `AuthorizationScrubFilter` on uvicorn loggers — preventatively rewrites `Bearer <token>` → `Bearer <redacted>` in case a future debug log call ever touches an auth header.
- Per-stage observability logging in `aippt/render.py` (Uploading / Downloading PDF / Running pdftoppm / Deleted staged) so slow renders can be triaged from the server log.

### Changed

- Two-column layout alignment improved for density-aware content distribution
- Web `/api/decks/create` and `/api/decks/upload[-stream]` now require `Authorization: Bearer <token>`; Linux deployments without SharePoint configuration refuse image-render requests with a clear error instead of failing later in the pipeline.
- Microsoft auth endpoints (`/api/auth/microsoft/start|poll|refresh`) surface upstream Graph errors with their status code preserved (4xx pass-through on `/start`; 5xx → 502 on `/poll`/`/refresh` while keeping 4xx → 401 for the existing UI contract).
- `/api/auth/microsoft/poll` and `/refresh` return **400** on malformed/non-JSON request bodies (previously 500 via uncaught `JSONDecodeError`).
- Web UI `createDeck()` flow goes through `msAuth.fetchWithAuth` (Bearer token + `X-AIPPT-NTID` attached, one-shot refresh-on-401). Both SSE handlers (`handleUploadEvent`, `handleCreateEvent`) now sign the user out on in-band `event: error data: {"status": 401, ...}` payloads, so an expired-token failure mid-stream surfaces correctly instead of leaving stale tokens in `localStorage`.
- `aippt.cli._export_images_linux` re-raises `graph.GraphError` instead of catching-and-returning-int, so typed auth failures propagate through `ingest_deck` to the SSE worker's `except graph.GraphError` branch and reach the browser as `{"status": 401, ...}`.
- Device-code modal renders user codes as text (XSS-safe).
- Device-code poll distinguishes `slow_down` from `authorization_pending` and backs off rather than tight-looping.

## [3.4.0] - 2026-05-15 — AMD Instinct Design System Web UI

### Added

- AMD Instinct design tokens (`tokens.css`) wired into web UI — four surface levels (L0–L3), teal accent `#00C2DE`, semantic text and border aliases
- Klavika font family (Light/Regular/Medium/Bold) vendored as woff2 — headings in web UI now use the AMD Instinct typeface
- DM Sans (Regular/Medium) vendored as woff2 — body text matches Daedalus portal convention
- Pico CSS → Instinct token bridge (`pico-overrides.css`) — Pico components (buttons, forms, dialogs) automatically pick up Instinct palette without rewriting Pico's component CSS
- FOUC-prevention head script — reads `localStorage.aippt_theme` and applies `.dark` or `.theme-amd-light` class before first paint
- Theme toggle button (🌓) in nav bar with `localStorage` persistence and `prefers-reduced-motion`-aware transition suppression
- Signature utility CSS classes: `.glow-line` (teal accent rule), `.tool-card` (hover card with glow shadow), `.eyebrow` (labelled section heading with teal bar), `.stat-number` (Klavika tabular teal numerals)
- Dot-grid background pattern (40 px radial dots at 5 % teal opacity, fixed attachment, light-mode variant)
- Eyebrow labels on "Cataloged Decks" (Library) and "Search Slides" (Discover) section headers
- Teal `.stat-number` styling on deck slide-count column
- Teal spinner accent (`border-top-color: var(--accent)`) with motion-token duration
- Visual baseline screenshots — pre- and post-Instinct (9 views × 2 themes = 18 PNGs each) in `tests/visual-baselines/`

### Fixed

- `role="button"` on `.slide-card` elements caused Pico to apply primary (teal) button background; fixed by adding explicit `background: var(--bg-card); color: var(--text-primary)` to `.slide-card`
- Pico v2 specificity collision: `--pico-background-color` was not overridden by plain `:root` (0,1,0) because Pico's `[data-theme]` rules win at (0,2,0); resolved by using `:root.dark, :root.theme-amd-light` selectors in `pico-overrides.css`

### Changed

- `<html>` element no longer carries a hard-coded `data-theme` attribute — theme is now applied exclusively by the FOUC head script from `localStorage`

## [3.3.0] - 2026-05-06 — Theme Token Schema v2

### Added

- Theme token schema v2: typography scale (14 tokens), data visualization colors (6 tokens), shadow configuration (5 tokens), and eyebrow component tokens (4 tokens) in theme YAML
- `createDeck()` accepts `overrides` option for per-deck token adjustments by agents
- Expanded color slots: `code_bg`, `code_text`, `heading_color`, `eyebrow_color`, `stat_color`
- `TOKEN_DEFAULTS` constant and expanded `loadTheme()` with new token sections
- Tests for all new token categories (typography, shadow, eyebrow, data_colors, overrides)

### Changed

- ~40 hardcoded design values in pptxgenjs helpers now read from theme tokens
- `cardShadow()` reads from `theme.shadow.*` tokens
- `addEyebrowText()` reads from `theme.eyebrow` and `theme.typography` tokens
- `addCodeSlide()` reads `code_bg`, `code_text`, `code_size` from theme
- `addStatCallout()` reads from `theme.typography` and semantic color tokens
- Master slide number reads `fontSize` from `theme.typography.footer_size`
- All three bundled themes updated with explicit token values (no visual change for `default` and `amd`; `instinct` gets design-system-aligned values)
- Eyebrow drawn per-slide instead of globally; two-column layout is density-aware

## [3.2.0] - 2026-05-06 — AMD Instinct Design System Theme

### Added

- `instinct.yaml` pptxgenjs theme with AMD Instinct Design System tokens
- Four slide masters: TITLE, CONTENT, SECTION_DIVIDER, CLOSING
- `addEyebrowText()` helper for branded eyebrow text
- Glow-line accent and dark background with teal highlights
- 10-slide demo deck showcasing all Instinct theme features

### Fixed

- Inner ellipse added for radial-gradient glow on title slide

## [3.1.0] - 2026-05-05 — Corporate Template Merge

### Added

- `merge-template` CLI subcommand for corporate template merge
- `--corp-template` flag on `create` subcommand for pipeline integration
- Core merge module with layout mapping and slide copy from corporate `.pptx` masters

### Changed

- TestChromeNotDuplicated tests and AMD 27-slide side-by-side example added

## [3.0.0] - 2026-05-04 — Slide Masters + LLM Gateway Compliance

### Added

- Slide masters: `defineSlideMaster()` for TITLE, CONTENT, and SECTION_DIVIDER
- `useSlideMaster` opt-in flag on `createDeck()` — chrome inherited from masters instead of baked per-slide
- Chrome gating in all content slide helpers, title slide, closing slide, and section divider
- Master section parsing in `loadTheme()` with commented examples in theme YAMLs
- Master-on variant of slides-as-code-design example
- Python-pptx validation tests for slide masters
- Mandatory `user: NTID` header support for AMD LLM Gateway compliance (deadline: May 2)
- Web UI input for NTID user header
- App-platform deployment scaffold (Dockerfile, K8s manifests, SOPS secrets, Harbor publishing, GitHub Actions CI/CD)

### Fixed

- "Thank You" fallback text in `addClosingSlide()` for logo-less themes

## [2.5.0] - 2026-03-11 — Slides-as-Code Skills

Shipped as three Claude Code skills on the SLAI Marketplace (PR #636).

### Added

- `/create-outline` skill: analyze source material (docs, repos, URLs, web apps) → structured markdown outline with Playwright screenshots
- `/create-deck` skill: markdown outline → PowerPoint via pptxgenjs or python-pptx engine, with theme-based styling
- `/deck-review` (formerly `/edit-deck`) skill: visual QA loop with slide screenshots, source code editing, and `[AIPPT-META]` change tracking in speaker notes
- Slides-as-code foundation: source tracking in catalog, `---aippt-meta---` speaker notes format
- Slide helper libraries for reusable layout components
- Sectioned deck generation with section dividers

### Changed

- Pipeline refactored: shared `pipeline.py` + `builder.py` extracted from CLI
- Audience-aware enhancement with audience selector in web UI
- Deck-level narrative planning for coherent slide flow
- Insight-driven title rewriting in enhancement pipeline
- Iterative improvement loop with self-evaluation

## [2.4.0] - 2026-03-08 — MCP + Slide Notes Metadata

### Added

- MCP client infrastructure layer using FastMCP, with config loading, server/tool discovery, and `mcp list` CLI command
- MCP text-to-image generation for slide visuals
- Slide notes metadata and LLM action logging in `[AIPPT-META]` format

## [2.3.0] - 2026-03-05 — Web/CLI Parity + Content Enhancement

### Added

- Web UI / CLI feature parity for deck creation
- CLI deck management commands (`list`, `delete`, `info`)
- Content enhancement in `--enhance` mode with richer bullet rewriting
- Image + text co-display on slides

## [2.2.0] - 2026-03-04 — Docker, Library Mode, Portability

### Added

- `Dockerfile` and `docker-compose.yml` with view-only (default) and full profiles
- `.dockerignore` for efficient image builds
- `AIPPT_VIEW_ONLY` environment variable for container-friendly view-only mode
- Library / view-only mode (`--view-only` flag or auto-detected when no LLM config)
- "Library Mode" badge in nav bar; LLM features disabled with tooltips
- Tag browsing sidebar with multi-select AND filtering and grouped-by-category display
- `dirs.yaml` configuration for standardized directory paths
- `migrate-paths` CLI command to convert absolute DB paths to relative
- Portable library export (`backup.sh --export`) and restore (`restore.sh`)
- Sphinx-based documentation (CLI reference, web UI guide, backup/restore, configuration)
- "Docs" link in web UI nav bar; FastAPI static mount at `/docs`

### Changed

- Rebranded from "Outline2PPT" to "AIPPT" — package, CLI, web UI, and all documentation
- Package directory renamed from `outline2ppt/` to `aippt/`
- CLI entry point renamed from `outline2ppt.py` to `aippt.py`
- Database paths stored as relative paths for portability
- LLM API endpoints return 403 in view-only mode

## [2.1.0] - 2026-03-02 — Improve Pipeline, Notes Editing, Upload

### Added

- `aippt improve` command: AI-suggested improvements to slide source code
- Web UI: editable speaker notes with save/cancel, dirty-state indicator, Ctrl+S shortcut, and edit history
- `aippt write-notes` command to write DB notes back to PPTX files with automatic backup
- Web UI: "Write Notes to Deck" button in deck list
- Web UI: create presentations from markdown outlines (paste or upload .md)
- Web UI: SSE progress streaming during deck generation
- Web UI: upload PowerPoint decks with automatic cataloging and streaming progress
- Web UI: download original `.pptx` files from deck list
- Web UI: next/prev navigation and keyboard shortcuts in slide detail modal
- Outline directives: `LAYOUT:` to specify slide layout, `IMAGE:` to embed images
- `models.yaml` for per-operation default model selection; `aippt models` CLI command
- Taxonomy management: `aippt tags` CLI commands (list, add, remove, import, export, rename)
- Deck metadata extraction (author, dates) from PPTX core properties
- Reverse: `--enhance` flag for LLM-powered multimodal outline generation

### Improved

- Reverse: bullet hierarchy, multi-line titles, table rendering, decorative shape filtering

### Fixed

- Reverse round-trip: speaker notes no longer leak into slide body
- Reverse: analysis artifacts stripped from notes; notes emitted as HTML comments
- Deck names no longer show UUID prefix; downloads use original filename

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

[unreleased]: https://github.com/shamsway/aippt/compare/v3.3.0...HEAD
[3.3.0]: https://github.com/shamsway/aippt/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/shamsway/aippt/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/shamsway/aippt/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/shamsway/aippt/compare/v2.5.0...v3.0.0
[2.5.0]: https://github.com/shamsway/aippt/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/shamsway/aippt/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/shamsway/aippt/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/shamsway/aippt/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/shamsway/aippt/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/shamsway/aippt/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/shamsway/aippt/releases/tag/v1.0.0
