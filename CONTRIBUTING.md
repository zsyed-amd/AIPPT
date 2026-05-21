# Contributing to AIPPT

Thanks for contributing. This document is the canonical guide to how work is
done on AIPPT. Read it once end-to-end before opening your first PR — it is
self-contained so you do not need to read `CLAUDE.md` or the Obsidian vault
to ship your first change.

## 1. Quick start

```bash
git clone <repo-url> aippt && cd aippt
python -m venv venv
source venv/bin/activate          # WSL/Linux/macOS
# venv/Scripts/activate           # Windows Git Bash / PowerShell
pip install -r requirements.txt
pytest tests/ -v                   # fast suite (~5s, 406 tests)
```

If that passes, you are ready to work.

The five hard rules:

1. Every non-trivial change starts with a **PRD** in `.local-docs/plans/`
   built from `.local-docs/plans/PRD-TEMPLATE.md`.
2. Feature work happens on a **branch** (and ideally a **git worktree**),
   never directly on `main`.
3. Tests come **first** — TDD discipline. The fast `pytest` suite must pass
   before every commit.
4. Every PR updates **`CHANGELOG.md`** under the `[Unreleased]` heading.
5. Every PR that changes user-visible behavior updates the relevant
   **Sphinx documentation** in `docs/`.

## 2. Repository structure

```
aippt/                  Python package (CLI, web app, builders)
  cli.py                Unified CLI with subcommands
  web/app.py            FastAPI app factory + lifespan
  web/routes.py         HTTP endpoints
  web/static/           SPA assets (htmx + Pico CSS + Instinct tokens)
themes/                 pptxgenjs themes (default, amd, instinct)
templates/              python-pptx template files
docs/                   Sphinx source (.rst + .md)
  _build/html/          Build output, served at /docs by the web UI
tests/                  pytest suite (mostly mocked; e2e/live opt-in)
deploy/slai-app-prod/   K8s manifests for the SLAI app platform
.local-docs/plans/      Gitignored PRDs and implementation plans
  PRD-TEMPLATE.md       Required starting point for new PRDs
  implemented/          Completed PRDs (archive)
skills/                 Source of truth for Claude/Cursor skills
.claude/skills/         Symlinks → skills/
.cursor/skills/         Symlinks → skills/
CHANGELOG.md            Keep-a-Changelog format, [Unreleased] section
CLAUDE.md               AI-assistant-specific guidance (optional reading)
CONTRIBUTING.md         This file
```

## 3. Development environment

### Python virtualenv

The Python virtualenv lives at `venv/` in the project root. The path to the
Python binary differs by platform:

```bash
# Detect platform once at the top of your shell session
if [ -f venv/bin/python ]; then
    VENV_PYTHON=venv/bin/python
elif [ -f venv/Scripts/python.exe ]; then
    VENV_PYTHON=venv/Scripts/python.exe
fi
```

| Platform           | venv Python                  | Activate                         |
| ------------------ | ---------------------------- | -------------------------------- |
| Linux / WSL2 / Mac | `venv/bin/python`            | `source venv/bin/activate`       |
| Windows Git Bash   | `venv/Scripts/python.exe`    | `source venv/Scripts/activate`   |

On Windows, the system `python` command often points to the Microsoft Store
stub. Always use the virtualenv Python.

### Gateway configuration (optional)

If you need LLM features, copy `gateway.yaml.example` to `gateway.yaml` and
fill in your credentials. The AMD internal gateway requires a `user: <NTID>`
header on every request (enforced 2026-05-02). Without `gateway.yaml`, the
app starts in view-only mode automatically.

### System dependencies

| Tool                   | Required for                                   |
| ---------------------- | ---------------------------------------------- |
| `poppler-utils`        | Linux image rendering via Microsoft Graph      |
| LibreOffice            | Local PPTX → PDF for visual QA (optional)      |
| PowerPoint (Windows)   | CLI `export-images` on Windows (optional)      |
| Node.js + `pptxgenjs`  | Skill-based deck generation (optional)         |

## 4. Project tracking

PRDs are the unit of planning. **Where you personally track tasks, daily
notes, or follow-ups is up to you** — Kanban board, sticky notes, Obsidian,
plain text, whatever works. The repo only requires that work is captured in
a PRD before implementation begins.

### PRD lifecycle

```
draft  →  in-review  →  in-progress  →  implemented
```

| State         | Where it lives                                       |
| ------------- | ---------------------------------------------------- |
| `draft`       | `.local-docs/plans/YYYY-MM-DD-feature-name.md`       |
| `in-review`   | Same file; frontmatter `status: in-review`           |
| `in-progress` | Same file; frontmatter `status: in-progress`         |
| `implemented` | Moved to `.local-docs/plans/implemented/`            |

The PRD file's frontmatter `status` field is the source of truth for state.

### When you can skip the PRD

- Typo fixes, comment-only changes, dependency bumps with no behavior change.
- Hot-fix one-liners under operational pressure (still requires a changelog
  entry and a follow-up retrospective PRD if it touched anything non-trivial).
- Test additions for already-implemented code.

When in doubt, write the PRD. PRDs are cheap, surprises are expensive.

## 5. Authoring a PRD

1. **Copy the template:**
   ```bash
   cp .local-docs/plans/PRD-TEMPLATE.md \
      .local-docs/plans/$(date +%Y-%m-%d)-my-feature.md
   ```
2. **Fill in every section.** Sections that do not apply get the literal
   text "No CLI changes" / "No UI changes" / "No data model changes" —
   never delete the heading. This makes it obvious nothing was overlooked.
3. **Required sections that often get skipped:**
   - **Documentation Updates** — name the `docs/*.rst` files that get
     touched, or justify why none are needed. PRs that change user-facing
     behavior without doc updates will be sent back.
   - **Testing** — list the test files and test classes you will add or
     extend. TDD means these get written first.
   - **Implementation Tasks** — ordered, independently committable tasks.
     Each row becomes a commit (or close to it).
4. **Request review** before starting implementation. A 15-minute review
   conversation up front saves hours of rework.

### Documentation discipline

The Sphinx docs in `docs/` are served at `/docs` in the running web UI
(`docs/_build/html`). They are the user-facing reference. Every PRD that
changes behavior must update the appropriate page:

| Change type                         | Page to update                       |
| ----------------------------------- | ------------------------------------ |
| New or modified CLI subcommand      | `docs/cli.rst`                       |
| Web UI feature, button, modal       | `docs/web-ui.rst`                    |
| New environment variable or config  | `docs/configuration.rst`             |
| Backup, restore, portability        | `docs/backup-restore.rst`            |
| Image export pipeline               | `docs/export-images.rst`             |
| New high-level concept              | `docs/overview.rst`                  |
| New external integration            | `docs/<integration>-setup.md`        |

Build the docs locally to verify they render:

```bash
cd docs && make html && python -m http.server -d _build/html 8001
```

## 6. Planning with superpowers

The Claude Code superpowers framework is the default workflow for non-trivial
features. The skills are surfaced as the `superpowers:*` skill family.

| When you have…                      | Use the skill…                           |
| ----------------------------------- | ---------------------------------------- |
| A vague idea ("we should add X")    | `superpowers:brainstorming`              |
| A clear concept, no plan yet        | `superpowers:writing-plans`              |
| A PRD ready to execute              | `superpowers:executing-plans`            |
| A plan with parallel sub-tasks      | `superpowers:dispatching-parallel-agents`|
| Anything claimed to be "done"       | `superpowers:verification-before-completion` |
| A failing test you cannot explain   | `superpowers:systematic-debugging`       |
| Working on a feature branch         | `superpowers:using-git-worktrees`        |

Workflow for a typical feature:

```
brainstorm  →  writing-plans  →  (PRD lands in .local-docs/plans/)
            →  using-git-worktrees  (create worktree, branch)
            →  test-driven-development  (write failing tests first)
            →  executing-plans  (implement one task at a time)
            →  verification-before-completion  (before claiming done)
            →  finishing-a-development-branch  (PR, merge, cleanup)
```

You are not required to use AI assistants to follow this workflow — the
skills codify the *process*, not the tool. The same checklist works if you
are typing code by hand.

## 7. Branch and worktree workflow

### Naming

- `feature/<descriptive-name>` — new features
- `fix/<descriptive-name>` — bug fixes
- `refactor/<scope>` — restructuring without behavior change
- `chore/<scope>` — tooling, deps, CI

### Worktree-based development (preferred)

```bash
# Create worktree + branch
git worktree add .worktrees/admin-tier -b feature/admin-tier main

# Work in it
cd .worktrees/admin-tier
# ...edit, test, commit...

# Merge back
cd /path/to/aippt           # main worktree
git merge feature/admin-tier

# Cleanup
git worktree remove .worktrees/admin-tier
git branch -d feature/admin-tier
```

Worktrees go in `.worktrees/<short-name>/` (gitignored). They keep the main
working directory clean and let you switch context without stashing.

### Plain branches (acceptable)

If worktrees feel like overhead for a small change, a regular feature branch
is fine:

```bash
git checkout -b fix/ingress-413 main
# ...work, commit...
git checkout main && git merge fix/ingress-413
git branch -d fix/ingress-413
```

### Rules that apply either way

- Never commit directly to `main`.
- Never force-push to `main`.
- Never `--no-verify` past a failing pre-commit hook. Fix the underlying
  issue and create a new commit.
- Investigate unfamiliar files/branches before deleting them — they may be
  another contributor's in-progress work.

## 8. Test discipline (TDD)

### Run the fast suite before every commit

```bash
$VENV_PYTHON -m pytest tests/ -v
```

The default `pytest` invocation excludes `e2e` and `live` markers via
`pyproject.toml`'s `addopts`. Fast suite is ~406 tests in ~5 seconds, fully
mocked, no API calls.

### Marker reference

| Marker  | Count | What it does                                        |
| ------- | ----: | --------------------------------------------------- |
| default | 406   | Fully mocked, no network, runs in ~5s               |
| `e2e`   | 24    | Real LLM calls. Requires `AMD_LLM_KEY`. Slow.       |
| `live`  | 3     | Gateway connectivity checks. Requires creds.       |

```bash
pytest -m e2e               # run e2e suite
pytest -m live              # run live suite
pytest -m ""                # run everything (override default exclusion)
```

### Test-driven development

1. Write the failing test that captures the behavior you want.
2. Run the test, confirm it fails for the *right reason*.
3. Implement the minimum code that makes it pass.
4. Refactor while keeping the test green.

Tests live in `tests/test_<module>.py`. New test files belong next to a
new module under test. Use the existing fixture patterns
(`tmp_path`, `deck_path`, `client`) rather than inventing new ones.

### Coverage expectations

- Business logic in `aippt/` modules: ~80% line coverage minimum.
- Pure UI / static asset code: not required.
- Migration code in `catalog.get_db()`: idempotency test required (run
  twice, assert no errors).

### What not to mock

- The SQLite database — use a `tmp_path` DB instead. Mocked DBs miss
  schema migration bugs and lock-contention issues.
- The filesystem when the test is about filesystem behavior.

## 9. Changelog and versioning

`CHANGELOG.md` follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
format. Every PR adds an entry under `[Unreleased]`.

### Section conventions

```markdown
## [Unreleased]

### Added
- User-visible new capability. Include the API surface or CLI flag.

### Changed
- Behavior change to an existing capability. State the old and new behavior.

### Fixed
- Bug fix. Include the symptom and the root cause when non-obvious.

### Removed
- Removed feature or deprecation. Include the migration path.
```

### Writing good entries

- **Lead with the user-visible change**, not the file you edited.
- **Include the "why"** when it is non-obvious — "Re-installed in the
  FastAPI lifespan because `uvicorn.run` calls `logging.config.dictConfig`
  after `create_app` and replaces handlers on `uvicorn.access` /
  `uvicorn.error`."
- **Name the endpoint, flag, or config key** so future-you can grep for it.
- **One entry per logical change**, even if the change spans multiple files.

### Release cadence

There is no fixed release schedule. When the `[Unreleased]` section has
accumulated enough material to ship, a maintainer:

1. Renames `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD — Short Theme`.
2. Adds a new empty `[Unreleased]` section above it.
3. Updates the comparison link at the bottom of the file.
4. Tags the commit: `git tag -a vX.Y.Z -m "Release X.Y.Z"`.
5. Bumps `aippt/__init__.py` `__version__` to the next dev version.

Semver guidance:

- `MAJOR` — backwards-incompatible API/CLI change.
- `MINOR` — new feature, backwards compatible.
- `PATCH` — bug fix only.

## 10. Web UI and deployment validation

### Local validation

```bash
$VENV_PYTHON aippt.py serve --port 8000
# Open http://localhost:8000
```

For changes that affect the SPA, use Playwright to drive the browser:

```bash
# Manual smoke check
$VENV_PYTHON aippt.py serve --port 8000 &
# Open browser, exercise the changed flow, screenshot if appropriate
```

The `superpowers:verification-before-completion` skill formalizes this —
**type-check and test passes verify code correctness, not feature
correctness**. If you cannot test the UI, say so explicitly in the PR
description rather than claiming success.

### SLAI app platform deployment

The production deployment lives at `https://slai-app.amd.com/aippt/`. The
flow:

1. **Bake an image** to Harbor:
   `mkmhub.amd.com/hw-slaiapp-dev/aippt:<short-sha>` — CI handles this on
   merge to `main`.
2. **Stamp the deployment** manifest at
   `deploy/slai-app-prod/aippt/deployment.yaml` — bump the `image:` tag
   to the new sha.
3. **Submit** via the platform's helper script (the hosted GitHub App
   opens the PR against `AMD-SLAI/slai-app-platform` — never `git push`
   directly to that repo from your laptop).
4. **Validate in production** with Playwright after the rollout.

The `app-platform` and `slai-app-creator` project skills automate steps
2–4. See `skills/app-platform/` for details.

## 11. Submitting work

### Commits

- **Conventional-style messages** are encouraged but not required.
- **Co-Author attribution** is required when AI assistants generated
  meaningful code. Use the trailer:
  ```
  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```
- **Never amend a published commit.** Create a new commit instead.
- **Never bypass hooks** (`--no-verify`, `--no-gpg-sign`) without a
  written reason.
- **Stage files explicitly.** `git add -A` and `git add .` can pull in
  `.env`, credentials, or large binaries by accident.

### Pull requests

PR title: short (under 70 chars), describes the user-visible change.

PR body template:

```markdown
## Summary
<1–3 bullets — what changed, from the user's perspective>

## Why
<the motivation — link to the PRD>

## Test plan
- [ ] Fast pytest suite passes locally
- [ ] Manually exercised: <flow>
- [ ] Docs updated: <pages>
- [ ] Changelog entry added under [Unreleased]

## Risks
<anything reviewers should look at closely>
```

PRs that change user-visible behavior without a changelog entry, doc
update, or test will be sent back.

### What requires reviewer sign-off (not just merge)

- Anything that affects production deployment manifests (`deploy/`).
- Anything that touches authentication, authorization, or secrets handling.
- Schema migrations (`schema.sql` or `catalog.get_db()` migration loop).
- Changes to the changelog format or release process.

## 12. Code style

- **Use the venv Python.** `python` on Windows may be the MS Store stub.
- **Always pass `encoding='utf-8'`** to `open()`. Windows defaults to
  `cp1252` and breaks on Unicode in markdown files (™, ✓, em-dashes).
- **Defensive attribute access** on `python-pptx` core properties — many
  attributes are absent on real-world files. Use
  `getattr(cp, "attr", None)`.
- **No comments that explain WHAT the code does** — well-named identifiers
  do that. Only comment WHY when it is non-obvious (hidden constraints,
  invariants, workarounds, surprising behavior).
- **No trailing-summary docstrings** describing the current PR — that
  belongs in the PR description, not the source tree.
- **Trust internal code.** Validate at system boundaries (user input,
  external APIs). Do not add defensive error handling for scenarios that
  cannot happen.
- **Match scope to the task.** A bug fix does not need surrounding
  cleanup. A one-shot operation does not need a helper class.

### Gateway compliance

The AMD LLM gateway enforces a mandatory `user: <NTID>` header. The web UI
captures the NTID in `localStorage` and sends it via `X-AIPPT-NTID` on
every authenticated request. The server validates against
`^[A-Za-z0-9._-]+$` before letting the value reach the SharePoint staging
path. If you add a new endpoint that uses the gateway, route through
`LLMClient` rather than calling the gateway directly — the user-header
plumbing lives there.

## 13. Skills (Claude Code / Cursor)

The `skills/` directory is the **source of truth** for all skill files.
Both AI client directories symlink into it:

```
skills/                  # Source of truth — edit here
  create-outline/
  create-deck/
  deck-review/
  app-platform/
  llm-gateway/
  slai-app-creator/

.claude/skills/          # Symlinks → ../../skills/
.cursor/skills/          # Symlinks → ../../skills/
```

When updating a skill, edit `skills/<name>/SKILL.md`. The symlinks pick
up the change automatically. Adding a brand-new skill requires creating
a new symlink in both `.claude/skills/` and `.cursor/skills/`.

`.claude/` is gitignored at the user level; force-add new skill files:

```bash
git add -f .claude/skills/<name>
```

See `SKILLS.md` for the catalogue of available skills.

---

## Reporting bugs

File issues against the repository with:

- AIPPT version (`aippt/__init__.py` `__version__`)
- Python version (`python --version`)
- OS and shell
- Minimal reproduction (outline file or input deck if applicable)
- Expected vs. actual behavior
- Any relevant lines from the server log (or the `/api/logs` endpoint
  when running the web UI)

If the bug is in the production SLAI deployment, check `/api/logs?level=ERROR`
first — the in-memory ring buffer captures the last 2,000 records.

## Asking for help

Tag a maintainer in your PR or open a draft PR with `[WIP]` in the title
when you want early feedback. The cheapest review is the one that happens
before you have written a thousand lines of code.

Welcome aboard.
