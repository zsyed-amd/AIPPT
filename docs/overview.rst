Overview
========

What is AIPPT?
--------------

AIPPT is a modular Python toolkit for creating, analyzing, and managing
PowerPoint presentations. It connects markdown-based workflows with AI-powered
slide generation, a searchable catalog, and a web UI for browsing your slide
library.

Key features:

- **Create** -- Convert markdown outlines into polished PowerPoint decks, with
  optional AI enhancement (layout selection, speaker notes, diagram generation)
- **Catalog** -- Index slides into a SQLite database with content hashing for
  deduplication and version tracking
- **Render** -- Export per-slide PNG images via PowerPoint COM on Windows or
  Microsoft Graph (PPTX → SharePoint → PDF → pdftoppm) on Linux. Used by
  Analyze for multimodal AI input and by the web UI for thumbnails.
- **Analyze** -- Use multimodal AI (slide images + text) for feedback, speaker
  notes, auto-tagging, and improvement suggestions
- **Search & Remix** -- Query cataloged slides by tags or title, then assemble
  new decks from slides across your library
- **Web UI** -- Browse, search, tag, and edit speaker notes from a FastAPI-based
  single-page application
- **Authentication** -- Microsoft device-code sign-in in the web UI; per-user
  NTID is auto-forwarded to the LLM gateway via the ``X-AIPPT-NTID`` header
  on every authenticated request
- **Improve** -- LLM-powered rewrite of slide content with revision history
  tracked in speaker notes
- **Corporate Template Merge** -- Inject corporate master/layouts into
  generated decks so PowerPoint users see the full branded layout palette
- **Skills** -- Three Claude Code skills (``/create-outline``, ``/create-deck``,
  ``/deck-review``) form an end-to-end presentation pipeline. See ``SKILLS.md``
  in the repository root for the full catalog.

Quick Start
-----------

Install
^^^^^^^

1. Create a virtualenv and install dependencies::

    python -m venv venv
    source venv/bin/activate    # Linux/macOS
    pip install -r requirements.txt

2. Set up API keys for AI features (or configure a :doc:`gateway <configuration>`)::

    export ANTHROPIC_API_KEY='your-key'   # For Claude models
    export OPENAI_API_KEY='your-key'      # For OpenAI/DALL-E models

3. Initialize model configuration::

    python aippt.py models init

Ingest a Deck
^^^^^^^^^^^^^

Ingest a PowerPoint file to catalog it and export slide images::

    python aippt.py ingest presentation.pptx

Add AI-generated tags::

    python aippt.py ingest presentation.pptx --tags --model gpt-4o

Launch the Web UI
^^^^^^^^^^^^^^^^^

Start the web server::

    python aippt.py serve --port 8000

Open ``http://localhost:8000`` in your browser to browse decks, search slides,
manage tags, and edit speaker notes.

Create a Presentation
^^^^^^^^^^^^^^^^^^^^^

Write a markdown outline and generate a deck::

    python aippt.py create outline.md template.pptx output.pptx

Enable AI enhancement for layout selection and speaker notes::

    python aippt.py create outline.md template.pptx output.pptx --enhance

See :doc:`cli` for the full command reference.
