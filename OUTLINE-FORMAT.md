# AIPPT Outline Format

The input outline is a markdown file. This document covers everything needed to write high-quality outlines — structure, formatting, directives, and best practices. It is designed to be self-contained so that an LLM can generate outlines from source material (a GitHub repo, a document, meeting notes, etc.) without additional context.

## Frontmatter

Optional YAML frontmatter at the top of the file provides metadata used by `--enhance`:

```markdown
---
audience: engineers
goal: Explain the migration strategy and get buy-in
tone: professional
---
```

| Field | Purpose | Examples |
|-------|---------|---------|
| `audience` | Who the slides are for — affects language level and detail depth | `engineers`, `executives`, `mixed`, `sales` |
| `goal` | What the presentation should accomplish | `Introduce the product`, `Get budget approval` |
| `tone` | Communication style | `professional`, `conversational`, `technical` |

All fields are optional. When present, the enhancement LLM uses them to tailor layout choices, speaker notes, and narrative structure.

## Structure modes

The parser supports two modes, selected automatically based on whether `## ` (H2) headers are present.

**Simple mode (H1 = slides)** — Each `# ` header becomes a slide title; everything below it becomes the slide body.

```markdown
# Introduction
- Welcome to the presentation
- Today's agenda

# Key Findings
- Revenue grew 15% year-over-year
- Customer satisfaction at an all-time high
  - NPS score of 72
  - Support ticket volume down 30%
```

**Hierarchical mode (H1 = sections, H2 = slides)** — When any `## ` header is present, H1 headers become PowerPoint sections and H2 headers become slide titles. Use this for longer decks with logical groupings.

```markdown
# Introduction
## Welcome
- About the team
- Meeting objectives

## Agenda
- Review Q1 results
- Discuss roadmap
- Q&A

# Q1 Results
## Revenue
- Total revenue: $4.2M
- 15% growth over Q4
```

## Content formatting

| Syntax | Result on slide |
|--------|----------------|
| `- item` or `* item` | Bullet point (level 1) |
| `  - sub-item` (2+ leading spaces) | Sub-bullet (level 2, smaller font) |
| `1. step` | Numbered item |
| `**bold text**` | Converted to UPPERCASE in plain text |
| `*italic text*` | Stripped to plain text |
| `[link text](url)` | Link text only (URL removed) |
| `` `code` `` | Inline code markers removed |
| Plain text lines | Rendered as-is |

## Bold lead-ins

Text matching the pattern `Term: rest of text` or `Term — rest of text` (1-4 words before a colon-space or em-dash) is automatically rendered with the lead-in in **bold** and the remainder in regular weight. This creates strong visual hierarchy on slides without manual formatting.

```markdown
## Why Containers?
- **Reproducibility** — consistent environments across dev, staging, and production
- **Driver decoupling** — container carries ROCm toolkit, host only needs the kernel module
- **Version flexibility** — run multiple ROCm versions side-by-side
- **Orchestration-ready** — standard deployment unit for Kubernetes
```

**Guidelines:**
- Use bold lead-ins on every bullet when presenting a list of features, benefits, concepts, or categories
- Keep lead-ins to 1-4 words — they should be scannable at a glance
- Use either `: ` or ` — ` (space-emdash-space) as the separator, not both in the same slide
- Apply consistently within a slide — either all bullets have lead-ins or none do
- Omit lead-ins when bullets are short, self-explanatory, or part of a sequential process

## Outline directives

Add `LAYOUT:` and `IMAGE:` directives to any slide's content to control its appearance. Directives are stripped from the slide body before rendering — they only affect how the slide is built.

### `LAYOUT: <type>`

Sets the slide layout type. Must be one of:

| Type | When to use | PowerPoint Layout |
|------|-------------|-------------------|
| `basic` | Default. Short bullet lists, simple content | Title and Content |
| `bullet` | Explicit choice for bullet-heavy slides (same rendering as basic) | Title and Content |
| `numbered` | Sequential steps, procedures, workflows, installation instructions | Title and Content |
| `two_column` | Comparisons, category/example pairs, before/after, pros/cons | Two Content |
| `diagram` | Full content area for images or diagrams | Title Only |

When used with `--enhance`, the author's `LAYOUT:` directive overrides the LLM's layout suggestion.

**Choosing the right layout:**
- If content describes steps in order (Step 1, Step 2...) or a process flow → `numbered`
- If content compares two things or groups items into two categories → `two_column`
- If a slide has an image that should fill the content area → `diagram`
- For everything else → `bullet` or omit the directive and let `--enhance` decide

### `LAYOUT: numbered` — numbered lists

Use for any sequential or procedural content. The layout auto-numbers top-level bullets (1., 2., 3...) and preserves sub-bullets without numbering.

```markdown
## Installing the Server
LAYOUT: numbered
- Install ROCm (provides the kernel driver and Python bindings)
- Clone the repository: git clone https://github.com/org/project.git
- Install dependencies: pip install -r requirements.txt
- Run the server: python server.py
```

**Do not** include inline numbers (`1.`, `2.`) in the bullet text when using `LAYOUT: numbered` — the layout adds them automatically.

### `LAYOUT: two_column` — side-by-side content

Use `|||` on its own line to explicitly separate left and right column content. Without `|||`, content is split at the midpoint automatically, which may not produce the desired grouping.

Add pipe-separated column headers after the layout type:

```markdown
## Feature Comparison
LAYOUT: two_column | Open Source | Enterprise
- Community support only
- Self-hosted infrastructure
- Manual scaling and updates
|||
- 24/7 vendor support with SLA
- Managed cloud deployment
- Auto-scaling and rolling updates
```

**Guidelines:**
- Always use `|||` for explicit column breaks — don't rely on auto-splitting
- Aim for roughly equal content in each column (3-4 bullets per side)
- Keep individual bullets short (one line) to avoid overflow in narrow columns
- Column headers are optional but strongly recommended for comparison slides

### `IMAGE: <path>`

Embeds a local image file onto the slide. The path is resolved relative to the outline file's directory.

```markdown
# Architecture Overview
LAYOUT: diagram
IMAGE: images/architecture.png
- Microservices communicate via event bus
- Each service owns its data store
```

When an image is present with `diagram` or `two_column` layout, it occupies the full content area (8" x 4") and the bullet text is moved to speaker notes. With other layouts, the image and text are displayed side-by-side.

**Rules:**
- Directives are case-sensitive (`LAYOUT:` and `IMAGE:`, uppercase)
- Place directives in the slide's content block (after the header line), before or among bullet content
- One of each per slide (first occurrence wins if duplicated)
- Missing images log a warning and the slide is created without the image
- Invalid layout types log a warning and fall back to `basic`
- Supported image formats: PNG, JPG, JPEG, GIF, BMP, TIFF, SVG

## Writing effective outlines

These guidelines produce outlines that render well as slides — whether generated by hand or by an LLM from source material.

**Content density:**
- Aim for 4-6 bullets per slide. More than 6 top-level bullets risks text overflow on most templates.
- Keep each bullet to one line of text (roughly 80-100 characters). Multi-sentence bullets become unreadable at presentation font sizes.
- If a slide has more than 6 bullets, split it into two slides or use a two-column layout.

**Slide structure:**
- Use hierarchical mode (`# sections`, `## slides`) for decks longer than 5-6 slides — sections create visual groupings in PowerPoint's slide sorter.
- The first slide under each `# section` acts as a section opener — keep it high-level.
- End with a summary or resources slide.

**Layout selection:**
- Prefer `LAYOUT: numbered` for any sequential, procedural, or step-by-step content. This includes installation guides, workflows, troubleshooting steps, and how-it-works explanations.
- Prefer `LAYOUT: two_column` for comparisons, before/after, category/example pairs, and pros/cons.
- Use `LAYOUT: diagram` only when you have an `IMAGE:` directive or when `--enhance` will generate a diagram.
- Omit `LAYOUT:` when content is a straightforward bullet list — let `--enhance` choose, or accept the default `basic` layout.

**Bold lead-ins:**
- Use `**Term** —` or `**Term:** ` patterns on every bullet when presenting features, benefits, tools, or categories.
- Don't use bold lead-ins on numbered/sequential content — the step numbers provide the visual anchor.
- Be consistent within each slide: either all bullets have lead-ins or none do.

**Two-column best practices:**
- Always include `|||` to mark the column break explicitly.
- Add column headers: `LAYOUT: two_column | Left Header | Right Header`
- Balance content across columns (3-4 bullets each).
- Shorten descriptions — columns are half-width, so long text wraps poorly.

## Example: complete outline

This example demonstrates all the formatting features in a realistic outline:

```markdown
---
audience: engineers
goal: Introduce the monitoring stack and get teams to adopt it
tone: technical
---

# Introduction

## GPU Monitoring Overview
- **Visibility** — real-time insight into GPU health, utilization, and errors
- **Proactive ops** — detect thermal, ECC, and power anomalies before they cause downtime
- **Standard tooling** — Prometheus and Grafana, no vendor lock-in

## Agenda
- Management tools and CLI
- Metrics exporter and dashboards
- Alerting patterns
- Enterprise integration

# Core Tools

## amd-smi CLI
- **Live monitoring** — real-time GPU metrics from the command line
- **Fleet queries** — query all GPUs on a node in one command
- **JSON output** — machine-readable for scripting and automation
- **Configuration** — set power limits, clock profiles, partition modes

## Deploying the Exporter
LAYOUT: numbered
- Install the Device Metrics Exporter container on each GPU node
- Configure Prometheus to scrape the exporter endpoint on port 5000
- Import the pre-built Grafana dashboards from the exporter repo
- Add Alertmanager rules for thermal and ECC thresholds

## Key Metrics
LAYOUT: two_column | Metric | Description
- GPU_GFX_ACTIVITY — compute utilization (%)
- GPU_JUNCTION_TEMPERATURE — hotspot temp (C)
- GPU_AVERAGE_SOCKET_POWER — power draw (W)
|||
- GPU_ECC_CORRECT_TOTAL — correctable ECC errors
- GPU_ECC_UNCORRECT_TOTAL — uncorrectable ECC errors
- GPU_USED_VRAM / GPU_TOTAL_VRAM — memory usage

# Operations

## Alerts to Configure
- **Thermal** — junction temperature exceeding safe thresholds
- **ECC errors** — any uncorrectable error triggers immediate investigation
- **Utilization** — sustained 0% may indicate workload failure
- **Power** — unexpected draw changes signal hardware issues

## Summary and Resources
- Standard Prometheus/Grafana stack — no custom tooling required
- **Resources:**
  - Metrics Exporter: github.com/ROCm/device-metrics-exporter
  - AMD SMI Docs: instinct.docs.amd.com
```
