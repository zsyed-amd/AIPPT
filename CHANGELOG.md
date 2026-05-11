# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Stat callout cards with shadow and rounded corners
- URL auto-linking in slide content (bare URLs converted to hyperlinks)

### Changed

- Two-column layout alignment improved for density-aware content distribution

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
