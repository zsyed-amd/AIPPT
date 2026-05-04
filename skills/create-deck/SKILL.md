---
name: create-deck
description: Create PowerPoint decks from markdown outlines using pptxgenjs (rich visuals) or python-pptx (template-based). Interactive workflow — walks through outline selection, engine choice, and theme configuration.
---

# Create Deck

Generate a PowerPoint presentation from a markdown outline. Two engines available:

- **pptxgenjs** (default) — Rich visual layouts, icons, cards, stat callouts. No template needed — builds from theme YAML. Best for creative, polished decks.
- **python-pptx** — Uses an existing corporate `.pptx` template. Best for strict brand compliance where the template defines all layouts.

## Environment Setup

### Python venv

```bash
if [ -f venv/bin/python ]; then
    VENV_PYTHON=venv/bin/python
elif [ -f venv/Scripts/python.exe ]; then
    VENV_PYTHON=venv/Scripts/python.exe
else
    echo "venv not found"
fi
```

### pptxgenjs Dependencies

Check availability:

```bash
NODE_PATH="$(npm root -g)" node -e "require('pptxgenjs'); console.log('pptxgenjs OK')"
NODE_PATH="$(npm root -g)" node -e "require('react-icons/fa'); require('react-icons/si'); require('sharp'); console.log('icons OK')"
```

Install if missing:

```bash
npm install -g pptxgenjs react-icons react react-dom sharp
```

## Interactive Flow

### Step 1: Select Outline

Scan `outlines/` recursively for `.md` files. Present choices via `AskUserQuestion`.

If `$ARGUMENTS` is provided, parse it for: outline path, engine choice, and theme/template preference. Skip any interactive steps for which the user already provided information. If all three are specified, skip the interactive flow entirely and proceed directly to generation.

### Step 2: Choose Engine

Ask the user:

| Option | When to suggest |
|--------|----------------|
| **pptxgenjs** (Recommended) | Default. Rich visual layouts with icons and cards |
| **python-pptx** | User mentions "template", provides a `.pptx` path, or needs exact brand compliance |

If the user mentions "template" or provides a `.pptx` template path, auto-select python-pptx.

### Step 3: Choose Theme or Template

**If pptxgenjs:** Scan `themes/` for `.yaml` files. If only one theme exists, use it without asking. If multiple, present choices.

**If python-pptx:** Scan `templates/` for `.pptx` files. Present choices.

### Step 4: Confirm Output Path

Auto-derive from outline filename: `output/{outline-stem}.pptx`

Mention the path to the user but don't prompt unless they want to change it.

## Generation: pptxgenjs

Read the [pptxgenjs guide](references/pptxgenjs-guide.md) for complete API reference, code examples, and pitfalls.

### Process

1. **Read the outline** — Parse markdown structure: `#` headings become slides, `##` headings become sections, bullets become content. Extract frontmatter, `LAYOUT:` directives, `IMAGE:` directives, `|||` column separators, `*Notes:*` blocks.

2. **Read the theme YAML** — Load colors, fonts, logo, slide, and footer settings. See [theme schema](references/theme-schema.md).

3. **Decide layouts** — For each slide, analyze content and choose a layout using the Layout Decision Strategy (see below). Apply the **variety rule**: never repeat the same layout on consecutive slides.

4. **Generate script** — Write a Node.js ES module (`.mjs`) that imports from the helper library:
   - `import { createDeck, addTitleSlide, addBulletSlide, addImageSlide, addImageBulletsSlide, addProcessFlow, addTwoColumn, addCardGrid, addStatCallout, addCodeSlide, addIconRowsSlide, addSectionDivider, addClosingSlide, addFooter, renderIconSvg, iconToBase64, preRenderIcons, cardShadow, SW, SH } from '../lib/pptxgenjs-helpers.mjs';`
   - Call `createDeck('themes/<theme>.yaml')` — returns a `deck` object with `pptx`, `theme`, and `layout` already configured. When `--slide-master` is specified, use `createDeck('themes/<theme>.yaml', { useSlideMaster: true })` to enable slide masters (chrome inherited from master, not baked per-slide).
   - Use slide builder functions: `addBulletSlide(deck, title, bullets, slideNum, notes)`, `addProcessFlow(deck, title, steps, slideNum)`, etc.
   - Pre-render icons with `preRenderIcons({ name: { component, color } })` or individual `iconToBase64(renderIconSvg(Icon, 256, color))`
   - **Add slide markers** — Before each slide's code block, insert a comment: `// ═══ Slide N: Title ═══`
   - **Add lineage metadata to speaker notes** — Each slide's notes should include an `[AIPPT-META]` JSON block with source lineage. Pass the metadata as part of the notes string to slide builder functions. See "Speaker Notes Metadata" section below.
   - Call `deck.save('output/<name>.pptx')` at the end
   - **Do NOT** redefine theme constants, shadow factories, footer helpers, or icon conversion functions — these are all in the library

5. **Execute** — Run with `NODE_PATH="$(npm root -g)" node <script.mjs>`

6. **Verify** — Confirm the output file exists and report file size.

### Critical Rules

- **NEVER** use `#` prefix on hex colors — causes file corruption
- **NEVER** reuse option objects (especially shadows) — use factory functions
- **NEVER** use 8-char hex colors (opacity in hex) — causes corruption
- **ALWAYS** use `bullet: true` instead of unicode bullet characters
- **ALWAYS** use `breakLine: true` between text array items
- **ALWAYS** use `cardShadow()` factory, never a shared shadow object
- **ALWAYS** use `pptx.layout = "LAYOUT_WIDE"` (13.33" × 7.5") — NEVER use `LAYOUT_16x9` (which is only 10" × 5.625")
- **ALWAYS** define safe-area constants: `SW=13.33, SH=7.5, M=margin, CONTENT_W=SW-2*M, RIGHT_EDGE=SW-M`
- **ALWAYS** validate element positions: `x + w <= RIGHT_EDGE` and `y + h <= SH - 0.6` (footer zone)

### Slide Master Flag

- `--slide-master` — Enable slide masters. Chrome (background, footer, logo, slide number) is inherited from master slides instead of baked into each slide. Generates proper PowerPoint master/layout structure for downstream editing.
- `--no-slide-master` — Disable slide masters (default). Chrome is painted directly onto each slide. Use when master inheritance is not needed.

When `--slide-master` is active, the generated script uses `createDeck('themes/<theme>.yaml', { useSlideMaster: true })`. All helper function calls remain identical — the helpers internally branch on `deck.useSlideMaster`.

### AMD Theme — Visual Modes

The AMD theme supports two visual modes. When the user selects the AMD theme, **default to Corporate Match** unless they explicitly request rich visuals.

#### Corporate Match Mode (default for AMD)

Matches the actual `corp.pptx` template output — extremely minimalist. Content slides are just bold white titles, white bullet text, and black everywhere else.

- **Backgrounds are PURE BLACK (`000000`)** — no navy, no dark blue, no `1A1A2E`, no `16213E`. Zero blue tones.
- **NO decorative shapes** — no colored bars, no card backgrounds, no icon circles, no accent shapes on content slides.
- **NO section dividers** — do NOT create section slides. If a `#` section heading has no sub-bullets (no content of its own), **skip it entirely** — do not render a blank slide. The section context is implied by the slide titles that follow.
- **Text is ALL WHITE** — titles bold ~28-32pt, body ~18-20pt. No teal stat numbers, no gray sub-text. Just white on black.
- **Content fills the slide** — do NOT cap bullet height at 70% of content area. Let content determine height; pptxgenjs clips naturally.
- **Footer** — plain slide number bottom-left, AMD wordmark bottom-right. No separator line. **Suppress the footer logo on the closing slide** — it already shows the large centered wordmark.
- **Title slide** — AMD arrow logo (left half), title text (right), logo+tagline (bottom-right). **Logo asset must be transparent PNG or exact background color match** — JPGs with dark navy/blue backgrounds create a visible rectangle against pure black slides.
- **Closing slide** — large centered AMD wordmark. Call `addFooter` with both logo and slide number suppressed: `addFooter(slide, slideNum, { suppressLogo: true, suppressNumber: true })`. No chrome on the closing card.
- **Column headers** — white, bold, centered. NOT colored (no teal/gold headers).

#### Rich Visual Mode (opt-in)

Use when the user explicitly asks for "rich", "creative", or "visual" presentations. Cards, icons, stat callouts, and accent shapes add visual interest.

- **Card/panel surfaces use gray (`636466`)** — not navy.
- **Accent is teal `00C2DE`** (not `00B4D8`). Secondary accent is gold `C1A968`.
- **Icon circles, accent bars, and card backgrounds** are allowed.
- **Stat callouts** with large colored numbers.
- **Section dividers** with accent bars.

#### Rules for Both Modes

- **Font is Arial** for both headings and body — not Trebuchet MS or Calibri.
- **Backgrounds are PURE BLACK** — the AMD palette has zero blue tones.
- **Text primary `FFFFFF`**, secondary `9D9FA2`, body `D5D5D5`.
- **ALWAYS use `LAYOUT_WIDE`** (13.33" × 7.5") — never `LAYOUT_16x9`.

## Generation: python-pptx

Read the [python-pptx guide](references/python-pptx-guide.md) for template analysis, layout indices, and code patterns.

### Process

1. **Read the outline** — Same parsing as pptxgenjs.

2. **Analyze the template** — Run the placeholder enumeration snippet from the guide to understand available layouts. Use the known layout index table for `corp.pptx`.

3. **Generate script** — Write a Python script (`.py`) that imports from the helper library:
   - `import sys; sys.path.insert(0, 'lib')`
   - `from pptx_helpers import load_template, save_deck, set_placeholder, get_placeholder, add_bullets, add_bullets_with_sub, add_numbered_bullets, add_two_column_with_header, add_column_divider, set_notes, suppress_bullet`
   - Call `prs = load_template('templates/corp.pptx')` — loads template and removes sample slides automatically
   - Use content helpers: `add_bullets(slide, idx, items)`, `add_numbered_bullets(slide, idx, items)`, `add_two_column_with_header(slide, idx, header, items)`, etc.
   - Items support strings, `(text, level)` tuples for indentation, and `{'text': ..., 'subs': [...]}` dicts for sub-bullets
   - Bold lead-in patterns (`**Bold** — rest`) are auto-detected in all bullet helpers
   - **Add slide markers** — Before each slide's code block, insert a comment: `# ═══ Slide N: Title ═══`
   - **Add lineage metadata to speaker notes** — See "Speaker Notes Metadata" section below.
   - Call `save_deck(prs, 'output/<name>.pptx')` at the end
   - **Do NOT** redefine helper functions inline — `set_placeholder`, `get_placeholder`, `suppress_bullet`, `add_bullets`, etc. are all in the library

4. **Execute** — Run with `$VENV_PYTHON <script.py>`

5. **Verify** — Confirm output exists and report size.

### Critical Rules

- **ALWAYS** remove sample slides before adding content
- **ALWAYS** find placeholders by `placeholder_format.idx`, not by position
- **ALWAYS** call `text_frame.clear()` before setting text
- **ALWAYS** import `pptx.oxml.ns` and `lxml.etree` — required for bullet suppression
- **ALWAYS** call `suppress_bullet()` on column headers in two-column layouts
- **ALWAYS** call `suppress_bullet()` on numbered list items (template adds bullet dots that conflict with number prefixes)
- **ALWAYS** use `center_image_on_slide()` for full-image slides (avoids fixed-position empty space)
- **ALWAYS** use `setup_image_and_bullets()` when a slide has both `IMAGE:` directive and bullet content
- AMD template uses OBJECT (type 7) placeholders, not BODY (type 2)
- Two-column body placeholders are idx 12 and 13

## Layout Decision Strategy

Analyze each slide's content for signals that map to layout types:

| Content Signal | pptxgenjs Layout | python-pptx Layout |
|---|---|---|
| First section heading in outline | Title slide (right-side text, left visual area) | Layout 0 (Title Slide) |
| Section heading with no slide children (corp-match) | **SKIP — do not render a slide** | N/A |
| Section heading with no slide children (rich mode) | Section divider (numbered panel) | Layout 26 (Divider) |
| 3-4 bullets with bold lead-ins (`Key: value`) | Card grid with icons (2x2) | Layout 3 (Title and Content) |
| 4–8 named technologies (tools, products, services) | Logo grid (brand SI icons + descriptions) | Layout 3 (Title and Content) |
| Prominent number or statistic | Stat callout (large number, 60-72pt) | Layout 3 (Title and Content) |
| Code blocks or CLI commands | Code panel (dark bg, mono font) | Layout 28 (Developer Code) |
| `LAYOUT: two_column` or `\|\|\|` separator | Two-column (with logos if named tools) | Layout 5 (Two Content) |
| `LAYOUT: numbered` or sequential steps | Process flow (numbered boxes) | Layout 3 (Title and Content) |
| `LAYOUT: numbered` with mixed CLI + concepts (items contain `sudo`, `docker run`, `apt install`, `pip install`, backtick code, or start with a shell verb) | **Auto-split:** concept items → process flow, CLI items → code panel | **Auto-split:** concept items → Layout 3 numbered, CLI items → Layout 28 (Developer Code) |
| 3 parallel items with headings | Three-column cards | Layout 17 (Three Content) |
| Standard bullet list | Icon + text rows or standard bullets | Layout 3 (Title and Content) |
| `IMAGE:` with no bullets | `addImageSlide()` — full-image, content to notes | Layout 7 (Title Only) + centered image |
| `IMAGE:` with bullets | `addImageBulletsSlide()` — image left, bullets right | Layout 3 + repositioned placeholder |
| `LAYOUT: diagram` without `IMAGE:` | Content fallback + actionable suggestion | Layout 3 (Title and Content) + actionable suggestion |
| Slide about specific vendor product | Any layout + brand badge (top-right) | Any layout + floating logo badge |
| Last slide / thank you | Closing slide | Layout 30 (Closing Logo) |

### Layout Variety Rule

1. **Plan phase:** For each slide, choose the best layout based on content signals (table above).
2. **Validation phase:** Scan the planned layout sequence. If two consecutive slides use the same layout type, swap the second to the next-best alternative from the substitution table below.

**Substitution table** (when layout repeats):

- Two bullet slides in a row → make the second one icon+text rows or card grid
- Two card grids in a row → make the second one icon+text rows
- Two process flows in a row → make the second one icon+text rows with numbered labels
- Two code slides in a row → make the second one standard bullets with inline code
- Two two-column slides in a row → make the second one a card grid or bullet slide
- Two icon+text rows in a row → make the second one a logo grid (if items are named technologies) or card grid

### Numbered List Item Count

If a `LAYOUT: numbered` slide has **more than 6 items**, consider splitting it into two slides. **8+ numbered items is a readability smell** — the audience cannot absorb that many sequential steps on one slide. Split by logical grouping (e.g., setup steps vs runtime steps, or concepts vs commands).

### Honoring Directives

If the outline contains explicit directives, they override the auto-detection:

- `LAYOUT: bullet` → standard bullets
- `LAYOUT: two_column` → two-column (supports `| Header1 | Header2` syntax — see below)
- `LAYOUT: numbered` → process flow or numbered list
- `LAYOUT: basic` → simple title + content
- `LAYOUT: diagram` → image slide (with `IMAGE:` directive)

**Two-column header extraction (pptxgenjs):** When `LAYOUT: two_column | Left Header | Right Header` appears, parse the pipe-separated headers and pass them to `addTwoColumn()`:

```javascript
// Parse "LAYOUT: two_column | Before | After" from outline
const layoutLine = "two_column | Before Code Review | After Code Review";
const parts = layoutLine.split("|").map(s => s.trim());
const leftHeader = parts[1] || "";
const rightHeader = parts[2] || "";

addTwoColumn(deck, title, leftHeader, rightHeader, leftItems, rightItems, sn++, notes);
```

### Diagram + Image Handling

When `LAYOUT: diagram` is specified **with** an `IMAGE:` directive, use the full-image layout — the image fills the content area, and any bullets go to speaker notes. This is not a fallback; it's the intended diagram layout.

### Image Path Resolution

Image paths in `IMAGE:` directives are relative to the outline file's directory. When generating scripts:

- **Compute `OUTLINE_DIR`** — In the generated `.mjs` script, resolve the outline's parent directory:
  ```javascript
  import { resolve, dirname } from 'path';
  import { fileURLToPath } from 'url';
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const OUTLINE_DIR = resolve(__dirname, '../outlines');
  // Then: resolve(OUTLINE_DIR, 'images/diagram.png')
  ```
- **Base64 data URIs** (`"image/png;base64,..."`) bypass file resolution entirely — pass directly to `addImageSlide` / `addImageBulletsSlide`
- **Missing files** show a gray placeholder with `[Image: <path>]` text (handled by the helper functions)
- **Absolute paths** are used as-is without resolution

### Diagram Fallback Action

When `LAYOUT: diagram` is specified but **no** `IMAGE:` directive is present, don't just print a warning — **suggest a follow-up action** in the output:

```
Slide {N} "{title}" used content fallback for LAYOUT: diagram — consider creating
an Excalidraw diagram and adding an IMAGE: directive to the outline.
```

This gives the user a concrete next step instead of a passive warning they might ignore.

### Icon Selection Strategy

When generating pptxgenjs scripts that include icons:

1. **Named technologies first** → Check `react-icons/si` (Simple Icons) for brand logos. Use brand-accurate colors.
2. **Generic concepts** → Use `react-icons/fa` (Font Awesome) in the theme's accent color (not white).
3. **No match** → Use an accent-colored left bar instead of an empty/meaningless icon circle.

**When multiple items share the same fallback icon:**
- If 3+ items would use the same FA icon, use accent-bar fallback for ALL of them instead
- Alternatively, vary FA icons by concept (FaDatabase, FaServer, FaCloud for different infra)
- Never repeat the exact same icon+color on more than 2 items — it looks like a rendering bug

**Discovery:** `Object.keys(require("react-icons/si")).filter(k => k.toLowerCase().includes("searchterm"))`

**Logo grid trigger:** When a slide lists 4–8 named technologies (title contains "Stack", "Tools", "Platform", "Services", "Components"), prefer the Logo Grid layout over Icon + Text Rows.

## Outline Format Reference

The skill supports two heading patterns. Detect which pattern the outline uses by examining the heading levels present:

### Pattern A: `#` / `##` (section-based, most common)

```markdown
# Section Name
## Slide Title
- Content bullets
```

- `#` = section heading (first `#` becomes title slide, subsequent `#` become section dividers)
- `##` = slide title
- Everything under a `##` until the next heading = slide content

### Pattern B: `#` / `##` / `###` (hierarchical)

```markdown
# Deck Title
## Section Name
### Slide Title
- Content bullets
```

- `#` = deck title (becomes title slide)
- `##` = section heading (becomes section divider)
- `###` = slide title

### How to detect

Count heading levels in the outline:
- If `###` headings are present → Pattern B
- If only `#` and `##` → Pattern A
- If only `##` → treat each `##` as a slide, no section dividers
- If only `#` → treat first `#` as title slide, subsequent `#` headings as content slides (no section dividers)

### Common elements (both patterns)

- `-` bullets = slide content
- Sub-bullets (indented `-`) = nested content
- `*Notes:*` = speaker notes (not rendered on slide)
- `LAYOUT:` = explicit layout directive
- `IMAGE:` = image to embed
- `|||` = column separator (for two-column)
- `---` (YAML frontmatter) = metadata (title, audience, etc.)
- Content with numbers/dollars/percentages = stat candidates
- Sequential items (3-4 short bullets) = process flow candidates

### CLI Command Detection in Numbered Slides

When parsing a `LAYOUT: numbered` slide, scan bullets for **shell command patterns**: lines starting with `sudo`, `docker`, `apt`, `pip`, `npm`, `kubectl`, `curl`, `wget`, `git`, `ssh`, or containing backtick-quoted inline code. If a slide mixes conceptual items and CLI commands:

1. **Split the slide** — conceptual items stay as a numbered process flow; CLI items become a separate code slide
2. **Name the split** — e.g., "Deployment Steps" (numbered) + "Deployment Commands" (code)
3. **Preserve order** — keep the code slide immediately after the conceptual slide so the narrative flow is maintained

This keeps the outline authoring simple (one slide with all items) while producing smarter output (two slides with appropriate layouts).

> **Note:** Auto-split is a content analysis step — examine the bullets, separate concept items from CLI commands, then call `addProcessFlow()` for the concepts and `addCodeSlide()` for the commands. There is no automatic detection helper; the LLM performs this split during layout planning.

## Sectioned Generation (Large Outlines)

Read the [sectioned generation reference](references/sectioned-generation.md) for the full workflow, section context format, and merge process.

When an outline has **more than 25 slides**, generate it in sections rather than as a single script. This prevents context window pressure, improves quality consistency, and enables parallel generation.

> **Note:** With helper library imports, single-script generation works well up to ~40 slides. Sectioning primarily benefits outlines with 25+ slides where context diversity (many different layout types, icon sets) would stress the LLM.

### When to Section

| Outline Size | Strategy |
|---|---|
| ≤25 slides | Single script (no sectioning) |
| 26–40 slides | 2–3 sections |
| 41+ slides | 3–5 sections (cap at ~15 slides/section) |

### Process

1. **Parse the outline** — Use `lib/section_parser.py` to split the outline at `##` heading boundaries:
   ```python
   import sys; sys.path.insert(0, 'lib')
   from section_parser import parse_sections
   result = parse_sections(open('outlines/deck.md').read())
   # result.sections → list of section dicts with title, slides, global_offset
   ```

2. **Generate each section** — Create a separate script per section. Each section script uses the same theme and helper library but only generates its subset of slides. Pass the `global_offset` so slide numbers are correct.

3. **Merge sections** — Combine section PPTX files into the final deck:

   **pptxgenjs (preferred):** Use function-composition — each section exports an `addSlides(deck)` function, and a single merge script calls them all on one deck object. No PPTX-level merging needed.

   **python-pptx:** Generate standalone section PPTX files, then merge:
   ```bash
   $VENV_PYTHON aippt.py merge output/sections/section-*.pptx -o output/final.pptx
   ```
   Or programmatically:
   ```python
   from lib.merge import merge_decks
   merge_decks(['output/sections/s1.pptx', 'output/sections/s2.pptx'], 'output/final.pptx')
   ```

4. **Parallel dispatch (optional)** — For 3+ sections, dispatch section generation as parallel subagents using `superpowers:dispatching-parallel-agents`. Each section is fully independent.

## Speaker Notes Metadata

Every slide's speaker notes should include an `[AIPPT-META]` JSON block that tracks source lineage. This metadata enables the `/edit-deck` skill to understand each slide's history.

### Format

The metadata is a JSON array embedded between `[AIPPT-META]` and `[/AIPPT-META]` delimiters. If the slide has human-readable speaker notes, they come first, separated by `\n\n---\n`.

### pptxgenjs Example

```javascript
// ═══ Slide 3: Architecture Overview ═══
const notes3 = `Key talking points for this slide

---
[AIPPT-META]
[{"operation":"create","source":"outline -> pptxgenjs","created":"2026-03-13","layout":"bullet","theme":"amd","history":["2026-03-13: Created from outline (bullet layout)"]}]
[/AIPPT-META]`;

addBulletSlide(deck, 'Architecture Overview', bullets, sn++, notes3);
```

### python-pptx Example

```python
# ═══ Slide 3: Architecture Overview ═══
notes3 = """Key talking points for this slide

---
[AIPPT-META]
[{"operation":"create","source":"outline -> python-pptx","created":"2026-03-13","layout":"bullet","theme":"corp","history":["2026-03-13: Created from outline (bullet layout)"]}]
[/AIPPT-META]"""

set_notes(slide, notes3)
```

### Required Fields

| Field | Value | Description |
|-------|-------|-------------|
| `operation` | `"create"` | Always "create" for initial generation |
| `source` | `"outline -> pptxgenjs"` or `"outline -> python-pptx"` | Lineage string |
| `created` | `"2026-03-13"` | ISO date of generation |
| `layout` | `"bullet"`, `"two_column"`, etc. | Layout type chosen for this slide |
| `theme` | `"amd"`, `"default"`, etc. | Theme name |
| `history` | `["2026-03-13: Created from outline (bullet layout)"]` | Array with initial entry |

### Slide Marker Comments

Add a visual marker comment before each slide's code block for easy navigation by the `/edit-deck` skill:

**JavaScript:** `// ═══ Slide N: Title ═══`
**Python:** `# ═══ Slide N: Title ═══`

These are not parsed programmatically — they just need to be clear enough for an LLM to reliably find "slide 4."

## Output & Handoff

### File Naming

- Output deck: `output/{outline-stem}.pptx`
- Generated script: `output/{outline-stem}.mjs` (pptxgenjs) or `output/{outline-stem}.py` (python-pptx)
- Section scripts (if sectioned): `output/sections/{outline-stem}-section-N.mjs` or `.py`

The generated script is saved alongside the deck for reference and reproducibility.

### Next Steps Message

After generating, show the user:

```
Deck created: output/{name}.pptx ({size})
Script saved: output/{name}.mjs

Next steps:
- /edit-deck output/{name}.mjs — Edit slides conversationally
- /deck-review — Visual QA and feedback
- aippt ingest output/{name}.pptx --source output/{name}.mjs — Catalog with source tracking
- aippt improve output/{name}.pptx — LLM-powered refinement
```

### Auto-Ingest with Source Tracking

When the user requests ingest after deck creation (or when auto-handoff to ingest triggers), **always pass the `--source` flag** so the catalog entry tracks its generating script:

```bash
aippt ingest output/{name}.pptx --source output/{name}.mjs
```

This enables the `/edit-deck` skill to find the source script by deck name later.

### Auto-Handoff to Deck Review

After generation completes, check the user's original prompt (`$ARGUMENTS` and conversation context) for review-related language:

- Keywords: "deck-review", "review", "visual QA", "analyze", "check slides", "inspect"

If any match is found, **invoke the deck-review skill directly** after showing the "Next steps" message:

```
Skill("deck-review", "output/{name}.pptx")
```

Do **not** just print `/deck-review` as a suggestion — call the Skill tool so the handoff actually fires. If no review language is detected, leave the "Next steps" message as-is and let the user decide.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `Cannot find module 'pptxgenjs'` | Not installed or NODE_PATH not set | `npm install -g pptxgenjs` and prepend `NODE_PATH="$(npm root -g)"` |
| PowerPoint repair dialog | Shadow object reuse, `#` in colors, or 8-char hex | Use shadow factory, remove `#`, use `opacity` property |
| Missing logo on slides | Theme `logo.path` points to non-existent file | Verify file exists at the path relative to project root |
| Fonts don't render | Font not installed on system | Use safe fonts: Calibri, Arial, Trebuchet MS |
| Template placeholders show "Click to edit" | Didn't clear text frame | Call `tf.clear()` before setting text |
| Extra slides from template | Didn't remove sample slides | Add removal loop at script start |
| Wrong placeholder filled | Matched by position instead of idx | Use `placeholder_format.idx` |
| Icons not rendering | react-icons/sharp not installed | `npm install -g react-icons react react-dom sharp` |
| `js-yaml` not found | Not installed globally | Embed theme values as JS constants instead |
