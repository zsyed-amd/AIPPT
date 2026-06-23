# AGENTS.md

Guidance for AI coding assistants working on AIPPT. This is the vendor-neutral
entry point — any agent (Claude Code, Cursor, OpenAI Codex, Aider, Goose,
Gemini CLI, etc.) should read this first.

**Process is process.** AIPPT's contribution rules apply equally to humans and
to AI assistants. Read `CONTRIBUTING.md` end-to-end before making your first
change. This file does not duplicate it.

## The required loop

Every non-trivial change goes through this loop. No exceptions for AI agents.

1. **PRD** — copy `~/git/swproductmgmt/projects/aippt/PRD-TEMPLATE.md` (shared repo)
   and fill every section. File at
   `~/git/swproductmgmt/projects/aippt/prds/YYYY-MM-DD-feature-name.md`, then publish for
   review (`/github publish … --no-merge`, reviewer requested — never self-merge
   in swproductmgmt). See `CONTRIBUTING.md` §4.
2. **Branch / worktree** — `feature/<name>` off `main`. Worktrees in
   `.worktrees/<short-name>/` (gitignored) are preferred.
3. **TDD** — write the failing test first, then the minimum code to pass.
   Fast suite (`pytest tests/`) must stay green before every commit.
4. **CHANGELOG.md** — add an entry under `[Unreleased]`. Keep-a-Changelog
   format.
5. **Sphinx docs** — update the relevant `docs/*.rst` page. `make html -W`
   must stay clean.

If you skip any of those steps without an explicit reason from the user, you
are out of bounds.

## Tool-specific guidance

| Tool                       | File                                            |
| -------------------------- | ----------------------------------------------- |
| Claude Code                | `CLAUDE.md` (project root)                      |
| Cursor                     | `.cursor/rules/` and `.cursor/skills/` symlinks |
| All other agents           | This file + `CONTRIBUTING.md`                   |

Skills (Claude Code / Cursor) live in `skills/` as the source of truth; the
`.claude/skills/` and `.cursor/skills/` directories are symlinks into it.

## Hard nos

These apply to every agent, every time:

- **Never commit to `main` directly.** Always work on a branch.
- **Never commit without an explicit user request.** "Let's implement X"
  is not a commit instruction.
- **Never bypass hooks** (`--no-verify`, `--no-gpg-sign`). If a pre-commit
  hook fails, fix the underlying issue and create a new commit — do not
  `--amend` past a hook failure.
- **Never force-push to `main`.**
- **Never `git add -A` / `git add .`** — stage files by name to avoid
  accidentally committing `.env`, credentials, large binaries, or another
  agent's in-progress work.
- **Never delete unfamiliar files, branches, or worktrees** without
  investigating — they may be another contributor's in-flight work.
- **Never claim a feature works without running it.** Type-check and tests
  verify code correctness, not feature correctness. If you cannot exercise
  the UI or CLI flow yourself, say so explicitly in your handoff.

## Co-author attribution

When you generate meaningful code, add a trailer to the commit message:

```
Co-Authored-By: <Model Name> <noreply@anthropic.com>
```

Use the actual model identifier (`Claude Opus 4.7`, `GPT-5`, etc.) rather
than a generic "AI assistant" label.

## Where to look when stuck

- Process questions → `CONTRIBUTING.md`
- Project conventions, CLI commands, environment setup → `CLAUDE.md`
- Skill catalogue → `SKILLS.md`
- Active PRDs → `~/git/swproductmgmt/projects/aippt/prds/` (shared; branch→PR→reviewed
  and merged by someone else)
- Implemented PRDs (the historical record of how decisions were made) →
  `~/git/swproductmgmt/projects/aippt/prds/implemented/`
- PRD status dashboard → `AIPPT PRD Tracker` note in the Obsidian vault
- Production deployment state → `deploy/slai-app-prod/`
