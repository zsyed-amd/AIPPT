# AIPPT User Workflows

This directory captures user-centered workflows for AIPPT in a structured form that can guide product design, documentation, and regression testing.

## Files

- `aippt-user-workflows.json` is the machine-readable workflow catalog.
- `README.md` explains why the catalog exists and how to maintain it.

## Purpose

AIPPT now has multiple surfaces: the CLI, the FastAPI web UI, Claude Code skills, configuration files, catalog storage, and generated deck assets. As the project grows, it is easy for design or testing to focus on individual commands while missing complete user journeys.

The JSON file is intended to keep those journeys visible. Each workflow describes:

- The user goal.
- The surfaces and entry points involved.
- Required preconditions.
- Typical steps.
- Expected outcomes.
- Areas that should receive test coverage.
- A priority for design and regression planning.

## How To Use This Catalog

Use the catalog as a checklist when planning new features, refactors, UI changes, CLI changes, or test suites. A change that touches one workflow should be reviewed against all related workflows so supported capabilities are not accidentally left out.

Good uses include:

- Mapping workflows to existing unit, integration, and manual tests.
- Identifying workflows that need new automated or browser coverage.
- Checking CLI and Web UI parity.
- Validating that LLM-dependent features have useful fallback and error states.
- Reviewing whether documentation still reflects supported behavior.

## Maintenance Guidance

Update `aippt-user-workflows.json` when a user-facing capability is added, removed, renamed, or significantly changed. Prefer adding or revising workflows at the level of user intent rather than duplicating every command-line flag.

When adding a workflow, include at least:

- A stable `id`.
- A concise `name`.
- The affected `surfaces`.
- A clear `goal`.
- Realistic `entry_points`.
- Testable `expected_outcomes`.
- Focused `test_focus` items.

Priorities are intentionally broad:

- `critical`: core workflows that should block releases if broken.
- `high`: important workflows that should have regular coverage.
- `medium`: valuable workflows that should be covered where practical, especially before related changes ship.
