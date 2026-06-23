# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AIPPT** -- A modular Python package that converts markdown outlines into PowerPoint presentations. Includes slide cataloging, AI-powered analysis, search/remix, CSV export, and a web UI. Supports corporate LLM gateways via YAML configuration.

## Development Environment

This is a cross-platform project developed on both Windows and Linux/WSL2. The Python virtualenv is at `venv/` in the project root, but the path to the Python binary differs by platform.

**Before running any commands, validate the platform and locate the venv Python:**

```bash
# Check which platform you're on and find the correct Python
if [ -f venv/bin/python ]; then
    VENV_PYTHON=venv/bin/python
elif [ -f venv/Scripts/python.exe ]; then
    VENV_PYTHON=venv/Scripts/python.exe
else
    echo "venv not found -- create one or check the path"
fi
```

### Linux / WSL2

```bash
source venv/bin/activate
venv/bin/python -m pytest tests/ -v
venv/bin/pip install -r requirements.txt
```

### Windows (Git Bash / PowerShell)

```bash
source venv/Scripts/activate      # Git Bash
venv/Scripts/python.exe -m pytest tests/ -v
venv/Scripts/pip.exe install -r requirements.txt
```

**Note:** On Windows the system `python` command may point to the Microsoft Store stub. Always use the virtualenv Python.

## Setup & Usage

```bash
# Install dependencies (use the virtualenv)
$VENV_PYTHON -m pip install -r requirements.txt

# Run tests
$VENV_PYTHON -m pytest tests/ -v
```

## CLI Commands

All commands use the unified entry point: `$VENV_PYTHON aippt.py <command>`

```bash
# Create presentation from markdown outline
$VENV_PYTHON aippt.py create outline.md template.pptx output.pptx
$VENV_PYTHON aippt.py create outline.md template.pptx output.pptx --enhance --model gpt-4o
$VENV_PYTHON aippt.py create outline.md template.pptx output.pptx --test 5

# Reverse: PowerPoint back to markdown
$VENV_PYTHON aippt.py reverse input.pptx output.md

# Catalog a deck into SQLite database
$VENV_PYTHON aippt.py catalog deck.pptx --images-dir images/deck-name/ --db slides.db

# AI analysis of slides (requires images directory + LLM gateway or API key)
$VENV_PYTHON aippt.py analyze deck.pptx --mode feedback --images-dir images/deck/ --model gpt-4o
$VENV_PYTHON aippt.py analyze deck.pptx --mode notes --images-dir images/deck/
$VENV_PYTHON aippt.py analyze deck.pptx --mode tags --taxonomy tags.csv
$VENV_PYTHON aippt.py analyze deck.pptx --mode improvements --images-dir images/deck/

# Search cataloged slides
$VENV_PYTHON aippt.py search --tags "security,architecture" --title-contains "zero trust"
$VENV_PYTHON aippt.py search --tags "security" --export-manifest security-remix.yaml

# Remix: assemble new deck from manifest
$VENV_PYTHON aippt.py remix manifest.yaml output.pptx

# Ingest: export images + catalog + optional tags in one step
$VENV_PYTHON aippt.py ingest deck.pptx
$VENV_PYTHON aippt.py ingest deck.pptx --tags --model gpt-4o
$VENV_PYTHON aippt.py ingest deck.pptx --tags --taxonomy tags.csv --images-dir images/deck/

# Export slides as PNG images (requires PowerPoint on Windows)
$VENV_PYTHON aippt.py export-images deck.pptx images/deck-name/
$VENV_PYTHON aippt.py export-images deck.pptx images/deck-name/ --width 2560 --height 1440

# Export slide metadata to CSV
$VENV_PYTHON aippt.py export deck.pptx --output slides.csv
$VENV_PYTHON aippt.py export --all --output catalog.csv

# Deck management
$VENV_PYTHON aippt.py decks list
$VENV_PYTHON aippt.py decks info <deck-id-or-name>
$VENV_PYTHON aippt.py decks rename <deck-id-or-name> "New Display Name"
$VENV_PYTHON aippt.py decks delete <deck-id-or-name>
$VENV_PYTHON aippt.py decks delete <deck-id-or-name> --force --purge-images

# MCP server management
$VENV_PYTHON aippt.py mcp list
$VENV_PYTHON aippt.py mcp list --json
$VENV_PYTHON aippt.py mcp list --config path/to/mcp_servers.json

# Launch web UI
$VENV_PYTHON aippt.py serve --port 8000
$VENV_PYTHON aippt.py serve --port 8000 --gateway-config gateway.yaml
```

Legacy positional syntax (`aippt.py outline.md template.pptx output.pptx`) still works.

## Skills / Slash Commands

Three skills form the presentation pipeline:

```
Source Material → /create-outline → outline.md → /create-deck → deck.pptx → /deck-review → feedback
```

- `/create-outline` — Generate a presentation outline from source material (docs, code, repos, URLs)
- `/create-deck` — Generate a PowerPoint deck from a markdown outline (pptxgenjs or python-pptx)
- `/deck-review` — Visual QA, slide analysis, source editing, Excalidraw diagrams, and web UI

### Skill Directory Layout

**`skills/` is the source of truth** for all skill files. Both AI client directories symlink into it:

```
skills/
  create-outline/       # SKILL.md + references/
  create-deck/          # SKILL.md + references/
  deck-review/          # SKILL.md + references/
  llm-gateway/          # SKILL.md + references/ + scripts/

.claude/skills/         # symlinks → skills/  (Claude Code)
.cursor/skills/         # symlinks → skills/  (Cursor)
```

To add or update a skill, edit files under `skills/<name>/`. The `.claude/skills/` and `.cursor/skills/` symlinks pick up changes automatically. See `SKILLS.md` for full skill documentation.

## Environment Variables

- `ANTHROPIC_API_KEY` -- Required for Claude models (direct API)
- `OPENAI_API_KEY` -- Required for OpenAI/DALL-E models (direct API)
- `AIPPT_VIEW_ONLY` -- Set to `1`/`true`/`yes` to force view-only mode, `0`/`false`/`no` to disable (overrides auto-detection; CLI `--view-only` flag takes priority)
- Gateway auth env var (e.g. `AMD_LLM_KEY`) -- Set in `gateway.yaml`

## Gateway Configuration

Create `gateway.yaml` to route LLM calls through a corporate API gateway. The AMD internal gateway (`https://llm-api.amd.com`) requires a mandatory `user: <NTID>` header on every request (enforced May 2, 2026). Copy `gateway.yaml.example` as a starting point.

```yaml
gateway:
  base_url: "https://llm-api.amd.com"
  auth_header: "Ocp-Apim-Subscription-Key"
  auth_value_env: "AMD_LLM_KEY"       # your individual API key
  user_header: "user"
  user_value_env: "AIPPT_USER_NTID"   # your NTID (e.g. melliott)
providers:
  openai:
    path: "/OpenAI"
  anthropic:
    path: "/Anthropic"
  google:
    path: "/VertexAI"
```

The web UI shows an NTID input field (top-right) that persists to `localStorage` and is sent with all LLM requests, allowing per-user NTID without editing `gateway.yaml`.

## Docker Deployment

```bash
# Build the image
docker compose build

# Run in view-only mode (default)
docker compose up -d

# Run in full mode with LLM access
docker compose --profile full up -d

# Override port
AIPPT_PORT=9000 docker compose up -d

# Run directly with docker
docker run -p 8000:8000 \
  -v ./slides.db:/app/slides.db \
  -v ./images:/app/images \
  -v ./uploads:/app/uploads \
  -e AIPPT_VIEW_ONLY=1 \
  aippt
```

The default service runs in view-only mode (`AIPPT_VIEW_ONLY=1`). The `full` profile mounts `gateway.yaml` and passes API key env vars for LLM features. Both profiles mount `uploads/`, `images/`, `slides.db`, and `models.yaml` as volumes.

## Architecture

Modular Python package with unified CLI:

```
aippt/
  __init__.py       # Package init, version
  cli.py            # Unified CLI with subcommands (argparse)
  parser.py         # Markdown parsing, text processing
  llm.py            # LLMClient, gateway config, model registry
  enhancer.py       # AI slide enhancement pipeline
  layouts.py        # Slide layout selection and application
  images.py         # SVG/DALL-E image generation
  reverse.py        # PPTX-to-markdown reverse conversion
  ingest.py         # Reusable ingest pipeline (export images → catalog → tags)
  catalog.py        # SQLite catalog, hashing, versioning, tagging
  analyze.py        # Multimodal slide analysis (feedback, notes, tags, improvements)
  export.py         # CSV metadata export
  remix.py          # Manifest generation, slide copy, deck assembly
  mcp.py            # MCP client infrastructure (FastMCP wrapper)
  schema.sql        # SQLite schema definition
  web/
    app.py          # FastAPI app factory
    routes.py       # API endpoints
    static/
      index.html    # Single-page app (htmx + Pico CSS)

themes/
  amd.yaml            # AMD corporate theme (colors, fonts, logo)
  default.yaml        # Clean dark theme, no branding
  assets/
    amd-logo.jpg      # AMD logo graphic
    amd-wordmark.png  # AMD text wordmark
```

### Database

SQLite database (`slides.db` by default). Schema: `decks`, `slides`, `tags`, `slide_tags`, `taxonomy`.

- Slides identified by `content_hash = sha256(title + content)`
- Re-cataloging detects changes via file hash
- Version warnings when remix finds newer slides across decks

### Resetting Ingested Decks

Use the `decks` CLI commands to manage cataloged decks:

```bash
# List all decks
$VENV_PYTHON aippt.py decks list

# View deck details
$VENV_PYTHON aippt.py decks info <deck-name-or-id>

# Delete a deck and all data
$VENV_PYTHON aippt.py decks delete <deck-name-or-id>

# Delete without confirmation, also remove images
$VENV_PYTHON aippt.py decks delete <deck-name-or-id> --force --purge-images
```

Full reset (delete DB and re-ingest):

```bash
rm slides.db
rm -rf images/<deck-name>/
```

### Outline Directives

Authors can add `LAYOUT:` and `IMAGE:` directives in slide content for explicit control:

```markdown
# My Slide
LAYOUT: two_column
IMAGE: images/diagram.png
- Bullet content here
```

- **`LAYOUT: <type>`**: Sets the layout (`bullet`, `two_column`, `numbered`, `basic`, `diagram`). Overrides LLM suggestion in `--enhance` mode.
- **`IMAGE: <path>`**: Embeds an image file. Path resolved relative to the outline file. Image takes full content area; text moves to speaker notes.
- Directives are stripped from content before rendering (not visible on slides).
- Case-sensitive (uppercase). First occurrence wins if duplicated.
- Parsed by `_extract_directives()` in `parser.py`, honored by `_add_slide()` in `cli.py`.

### Key Patterns

- **Graceful degradation**: Individual slide/operation failures don't abort the batch
- **Provider agnosticism**: LLMClient normalizes Anthropic and OpenAI-compatible APIs
- **Gateway support**: YAML-configured base URL, auth headers, provider path routing
- **Progress persistence**: PPTX saved after each slide creation
- **Content hashing**: SHA-256 for deduplication and version detection

## External Tooling (MCP Servers & Plugins)

### Playwright (Browser Automation)

The Playwright MCP plugin provides headless browser control for visual QA and interaction with web tools. Chrome is installed at `/opt/google/chrome/chrome`.

**Visual QA workflow for generated presentations:**

```bash
# Convert PPTX to slide images (requires libreoffice-impress + poppler-utils)
python3 scripts/office/soffice.py --headless --convert-to pdf output/deck.pptx
mkdir -p output/slides && pdftoppm -jpeg -r 150 deck.pdf output/slides/slide
```

Then use Playwright to screenshot, or read the images directly for visual inspection via subagents.

**Caveats:**
- Chrome must be at `/opt/google/chrome/chrome` (symlink from Playwright's Chromium if needed)
- `npx playwright install` requires interactive sudo on WSL2 -- run in a separate terminal
- LibreOffice + poppler are system deps, not in the venv

### Excalidraw (Diagram Creation)

The Excalidraw MCP server generates diagrams inline. A self-hosted instance is available at `https://excalidraw.lab.shamsway.net/`.

**Creating diagrams:**
- Use the `mcp__excalidraw__create_view` tool to render diagrams inline in Claude Code
- The `label` shorthand works for inline preview but does NOT export properly to `.excalidraw` files
- For exportable diagrams, use proper bound text elements: add `containerId` on the text and `boundElements` on the shape

**Pasting diagrams into Excalidraw via Playwright:**

```
1. Navigate to the Excalidraw instance
2. Dismiss welcome screen (press Escape)
3. Use browser_evaluate to set clipboard with excalidraw/clipboard format:
   { type: "excalidraw/clipboard", elements: [...], files: {} }
4. Press Ctrl+V to paste
5. Screenshot to verify
```

**Updating an existing canvas:** `Ctrl+A` → `Delete` → paste new clipboard data → `Ctrl+V`

**Caveats:**
- `export_to_excalidraw` tool only targets excalidraw.com, not self-hosted instances
- For self-hosted, save as `.excalidraw` JSON file (drag-and-drop import) or paste via Playwright
- Bound text elements need `containerId`/`boundElements` cross-references to render labels inside shapes

### PPTX Skill (Document Skills Plugin)

The `pptx` skill (from `anthropic-agent-skills/document-skills`) provides optimized workflows for reading, editing, and creating PowerPoint files. See `docs/analysis/2026-03-10-pptx-skill-recap.md` for full comparison with aippt.

**Key tools:**
- `python -m markitdown file.pptx` -- text extraction to markdown
- `scripts/thumbnail.py file.pptx` -- visual grid of slide thumbnails
- `scripts/office/unpack.py` / `pack.py` -- XML-level PPTX editing
- `pptxgenjs` (npm, installed globally) -- from-scratch slide creation via Node.js

**When to use which:**
- **aippt CLI**: Primary tool for outline → PPTX generation and enhancement
- **PPTX skill**: Visual QA, post-generation inspection, and XML-level debugging
- **Playwright + soffice**: Automated visual regression / feedback loops
- **Excalidraw**: Creating diagrams for `IMAGE:` directives in outlines

## Project Tracking

PRDs live in the shared **`swproductmgmt`** repo at `~/git/swproductmgmt/projects/aippt/prds/` — the single source of truth, where collaboration + review happen (house rule: branch → PR → reviewed and merged by someone else). This project additionally uses an **Obsidian vault** for the PRD status **dashboard** and daily logs — not GitHub Issues or Planner.

**Vault root:** `/mnt/c/Users/melliott/git/obsidian-vault/`

| Resource | Path |
|----------|------|
| Daily work log | `10 - Daily/YYYY-MM-DD.md` — add a `## 🛠️ Work Log` section with AIPPT subsection |
| PRD content (canonical) | `~/git/swproductmgmt/projects/aippt/prds/` — shared repo, single source of truth |
| PRD status dashboard | `30 - Projects/AIPPT/AIPPT PRD Tracker.md` (Obsidian) |
| Dev notes | `30 - Projects/AIPPT/AIPPT Dev Notes.md` |
| Feedback | `30 - Projects/AIPPT/AIPPT Feedback.md` |

**After completing meaningful work** (feature implemented, PRD finished, branch merged):
1. Add an entry to today's daily log under `## 🛠️ Work Log`
2. Update `AIPPT PRD Tracker.md` — move the PRD to In Progress / Completed as appropriate
3. Update the PRD's frontmatter `status` in `~/git/swproductmgmt/projects/aippt/prds/` via a PR (`draft` → `in-review` → `implemented`); on `implemented`, move it to `~/git/swproductmgmt/projects/aippt/prds/implemented/`

## Planning Docs

PRDs are authored and stored in the shared **`swproductmgmt`** repo at `~/git/swproductmgmt/projects/aippt/prds/` — see `CONTRIBUTING.md` §4 for the publish/review flow.

| Path | Purpose |
|------|---------|
| `~/git/swproductmgmt/projects/aippt/prds/` | Active PRDs (shared source of truth) |
| `~/git/swproductmgmt/projects/aippt/prds/implemented/` | Completed PRDs (archive) |

> **Retired (2026-06):** the gitignored `.local-docs/plans/` tree has been removed — PRDs now live in `~/git/swproductmgmt/projects/aippt/prds/` (migration complete). When completing a PRD: move it to `~/git/swproductmgmt/projects/aippt/prds/implemented/` via PR **and** update the vault tracker.

## Worktree-Based Development

**Prefer worktree-based development on this project.** Each feature or PRD gets its own worktree with an isolated branch. This keeps the main working directory clean and allows parallel development.

### Worktree Workflow

```bash
# Create a new worktree for a feature
git worktree add .worktrees/<name> -b feature/<branch-name> main

# When feature is complete, merge into main
cd /home/matt/git/shamsway/aippt
git merge feature/<branch-name>

# Remove a worktree after merging
git worktree remove .worktrees/<name>
git branch -d feature/<branch-name>
```

### Worktree Guidelines

- **Feature work**: Branch from `main`, use `feature/<descriptive-name>`
- **Worktrees**: Go in `.worktrees/<short-name>/` (gitignored)
- **PRDs**: Authored in `~/git/swproductmgmt/projects/aippt/prds/` (canonical content). Status is tracked in the `AIPPT PRD Tracker` note in the Obsidian vault — the tracker is your dashboard; swproductmgmt is the source of truth for PRD content.
- **Cleanup**: Remove worktrees and delete branches after merging

### Current Active Branches

| Branch | Status | Notes |
|--------|--------|-------|
| `main` | Integration | Primary branch |
