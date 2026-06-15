CLI Reference
=============

All commands use the unified entry point::

    python aippt.py <command> [options]

Use ``--debug`` on any command for detailed logging.

create
------

Build a PowerPoint deck from a markdown outline.

.. code-block:: text

   aippt.py create <outline> <template> <output> [options]

Arguments:

- ``outline`` -- Markdown outline file
- ``template`` -- PowerPoint template file
- ``output`` -- Output ``.pptx`` file

Options:

- ``--enhance`` -- Use LLM to select layouts and generate speaker notes
- ``--model MODEL`` -- Model name (overrides ``models.yaml`` default)
- ``--gateway-config PATH`` -- Gateway YAML config (default: ``gateway.yaml``)
- ``--api-key KEY`` -- API key for the LLM provider
- ``--api-base URL`` -- Base URL for API endpoint
- ``--api-provider {anthropic,openai,compatible}`` -- Force a specific provider
- ``--test N`` -- Process only the first *N* slides (for quick testing)
- ``--analyze-template`` -- Analyze template layouts before generating
- ``--image-gen {claude,dalle,openai,mcp,none}`` -- Diagram generation mode (default: ``none``)
- ``--corp-template PATH`` -- Merge generated slides into a corporate template as a
  post-processing step. The output file will contain the corporate master and all
  31 layouts, with each slide re-assigned to a matching corporate layout based on
  ``[AIPPT-META]`` metadata.
- ``--audience {engineers,executives,product,mixed}`` -- Target audience (default: ``mixed``)
- ``--show-plan`` -- Print the deck narrative plan before enhancing (requires ``--enhance``)
- ``--no-plan`` -- Skip deck-level narrative planning (per-slide enhancement only)

Examples::

    # Basic creation
    python aippt.py create outline.md template.pptx output.pptx

    # With AI enhancement
    python aippt.py create outline.md template.pptx output.pptx --enhance

    # Specific model and diagram generation
    python aippt.py create outline.md template.pptx output.pptx --enhance --model gpt-4o --image-gen dalle

    # Test run: first 3 slides only
    python aippt.py create outline.md template.pptx output.pptx --enhance --test 3

    # With corporate template merge
    python aippt.py create outline.md template.pptx output.pptx --corp-template templates/corp.pptx

When ``--enhance`` is enabled, the LLM analyzes each slide and selects from
five layout types (``bullet``, ``numbered``, ``two_column``, ``diagram``,
``basic``), generates speaker notes, and suggests visuals. Original outline
content is preserved on the slide body.

reverse
-------

Convert an existing PowerPoint file back to a markdown outline.

.. code-block:: text

   aippt.py reverse <input> [output] [options]

Arguments:

- ``input`` -- Input ``.pptx`` file
- ``output`` -- Output ``.md`` file (optional; prints to stdout if omitted)

Options:

- ``--no-notes`` -- Exclude speaker notes from output
- ``--strip-notes`` -- Omit speaker notes entirely
- ``--enhance`` -- Use LLM for high-quality multimodal outline generation
- ``--model MODEL`` -- Model for enhancement (overrides ``models.yaml``)
- ``--gateway-config PATH`` -- Gateway YAML config (default: ``gateway.yaml``)
- ``--images-dir DIR`` -- Directory with pre-exported slide images (``Slide1.PNG``, ...)

Examples::

    python aippt.py reverse presentation.pptx output.md
    python aippt.py reverse presentation.pptx output.md --strip-notes
    python aippt.py reverse presentation.pptx output.md --enhance --images-dir images/deck/

catalog
-------

Catalog a deck into the SQLite database (without image export).

.. code-block:: text

   aippt.py catalog <deck> [options]

Arguments:

- ``deck`` -- PowerPoint file to catalog

Options:

- ``--images-dir DIR`` -- Directory with exported slide images
- ``--db PATH`` -- Database file path (default: ``slides.db``)

Example::

    python aippt.py catalog deck.pptx --images-dir images/deck/

analyze
-------

Run AI analysis on a presentation. Four modes are available.

.. code-block:: text

   aippt.py analyze <deck> --mode <mode> [options]

Arguments:

- ``deck`` -- PowerPoint file

Options:

- ``--mode {feedback,notes,tags,improvements}`` -- Analysis mode (required)
- ``--taxonomy CSV`` -- CSV file with predefined tags (for ``tags`` mode)
- ``--model MODEL`` -- Model to use (overrides ``models.yaml``)
- ``--api-key KEY`` -- API key
- ``--gateway-config PATH`` -- Gateway config (default: ``gateway.yaml``)
- ``--images-dir DIR`` -- Directory with slide images (enables multimodal analysis)
- ``--db PATH`` -- Database path (default: ``slides.db``)

Modes:

- **feedback** -- Get design and content feedback (printed to stdout)
- **notes** -- Generate speaker notes (written back to the PPTX)
- **tags** -- Auto-tag slides using AI or a taxonomy (stored in the database)
- **improvements** -- Get improvement suggestions

Examples::

    # Design feedback
    python aippt.py analyze deck.pptx --mode feedback --images-dir images/deck/

    # Generate speaker notes
    python aippt.py analyze deck.pptx --mode notes --images-dir images/deck/

    # Auto-tag with taxonomy
    python aippt.py analyze deck.pptx --mode tags --taxonomy tags.csv

    # Improvement suggestions
    python aippt.py analyze deck.pptx --mode improvements --images-dir images/deck/

improve
-------

Rewrite slide content using LLM analysis. The LLM sees each slide's image
(when available) and text, then rewrites the body content. Revision history is
tracked in speaker notes.

.. code-block:: text

   aippt.py improve <deck> [options]

Arguments:

- ``deck`` -- PowerPoint file to improve

Options:

- ``--output PATH`` -- Save to a different file (default: overwrite in place)
- ``--dry-run`` -- Preview changes without modifying the file
- ``--slides LIST`` -- Comma-separated slide numbers to improve (e.g. ``3,5,8``)
- ``--passes N`` -- Number of improvement passes (default: ``1``)
- ``--focus {general,accuracy,detail,brevity,structure}`` -- Focus area (default: ``general``)
- ``--images-dir DIR`` -- Slide images directory
- ``--model MODEL`` -- Model for rewrite
- ``--gateway-config PATH`` -- Gateway config (default: ``gateway.yaml``)
- ``--api-key KEY`` -- API key
- ``--db PATH`` -- Database path (default: ``slides.db``)

Examples::

    # Preview changes
    python aippt.py improve deck.pptx --dry-run

    # Improve specific slides with a focus
    python aippt.py improve deck.pptx --slides 3,5,8 --focus brevity

    # Multiple passes, save to new file
    python aippt.py improve deck.pptx --output improved.pptx --passes 2

search
------

Query cataloged slides by tags, title, or section.

.. code-block:: text

   aippt.py search [options]

Options:

- ``--tags LIST`` -- Comma-separated tags to filter by
- ``--title-contains TEXT`` -- Filter by title substring
- ``--section TEXT`` -- Filter by section name (substring match)
- ``--export-manifest PATH`` -- Export results as a remix manifest YAML
- ``--db PATH`` -- Database path (default: ``slides.db``)

Examples::

    python aippt.py search --tags "security,architecture"
    python aippt.py search --title-contains "zero trust"
    python aippt.py search --tags "security" --export-manifest security-remix.yaml

remix
-----

Assemble a new deck from a manifest of slides pulled from different source decks.

.. code-block:: text

   aippt.py remix <manifest> <output> [options]

Arguments:

- ``manifest`` -- YAML manifest file (e.g. generated by ``search --export-manifest``)
- ``output`` -- Output ``.pptx`` file

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)

Example::

    python aippt.py remix manifest.yaml output.pptx

ingest
------

One-step pipeline: export slide images, catalog the deck, and optionally
generate AI tags.

.. code-block:: text

   aippt.py ingest <deck> [options]

Arguments:

- ``deck`` -- PowerPoint file to ingest

Options:

- ``--images-dir DIR`` -- Output directory for slide images (default: ``images/<deck-name>/``)
- ``--db PATH`` -- Database file path (default: ``slides.db``)
- ``--tags`` -- Generate AI tags after cataloging
- ``--taxonomy CSV`` -- CSV file for taxonomy-constrained tagging
- ``--model MODEL`` -- Model for tag generation
- ``--gateway-config PATH`` -- Gateway config (default: ``gateway.yaml``)
- ``--api-key KEY`` -- API key
- ``--width N`` -- Image export width in pixels (default: ``1920``)
- ``--height N`` -- Image export height in pixels (default: ``1080``)

Examples::

    # Basic ingest (images + catalog)
    python aippt.py ingest deck.pptx

    # With AI tagging
    python aippt.py ingest deck.pptx --tags --model gpt-4o

    # With taxonomy-constrained tags and custom image directory
    python aippt.py ingest deck.pptx --tags --taxonomy tags.csv --images-dir images/deck/

Image export requires PowerPoint (Windows or WSL with PowerPoint installed).

export
------

Export slide metadata from the database to CSV.

.. code-block:: text

   aippt.py export [deck] [options]

Arguments:

- ``deck`` -- Specific deck file to export (optional)

Options:

- ``--all`` -- Export all cataloged decks
- ``--output PATH`` -- Output CSV file (default: ``slides.csv``)
- ``--db PATH`` -- Database path (default: ``slides.db``)

Examples::

    python aippt.py export deck.pptx --output slides.csv
    python aippt.py export --all --output catalog.csv

export-images
-------------

Export slides as PNG images using PowerPoint COM automation (Windows/WSL).

.. code-block:: text

   aippt.py export-images <deck> [out_dir] [options]

Arguments:

- ``deck`` -- PowerPoint file to export
- ``out_dir`` -- Output directory (default: ``images/<deck-name>/``)

Options:

- ``--width N`` -- Image width in pixels (default: ``1920``)
- ``--height N`` -- Image height in pixels (default: ``1080``)

Examples::

    python aippt.py export-images deck.pptx images/deck/
    python aippt.py export-images deck.pptx images/deck/ --width 2560 --height 1440

serve
-----

Launch the web UI (FastAPI + htmx).

.. code-block:: text

   aippt.py serve [options]

Options:

- ``--host HOST`` -- Bind address (default: ``127.0.0.1``)
- ``--port N`` -- Port number (default: ``8000``)
- ``--db PATH`` -- Database path (default: ``slides.db``)
- ``--gateway-config PATH`` -- Gateway config for LLM access (default: ``gateway.yaml``)
- ``--uploads-dir DIR`` -- Directory for uploaded files (default: ``uploads``)
- ``--images-dir DIR`` -- Parent directory for rendered slide images (default:
  value from ``dirs.yaml`` or ``images``). Set this to a persistent volume in
  container deployments -- otherwise PNGs land in cwd and are lost on pod
  restart.
- ``--view-only`` -- Disable LLM features (also settable via the
  ``AIPPT_VIEW_ONLY`` env var; auto-detected when no gateway/API keys)
- ``--max-upload-mb N`` -- Override the upload size cap (default ``50``;
  reads ``upload.max_size_mb`` from ``gateway.yaml`` otherwise). The
  middleware rejects oversized POSTs to ``/api/decks/upload*`` with HTTP
  413 before the route handler runs.
- ``--storage {fs,s3}`` -- Storage backend for library assets and the catalog
  snapshot (default ``fs``; also settable via ``AIPPT_STORAGE``). See
  :doc:`configuration` for the ``MINIO_*`` env vars used by ``s3``.
- ``--data-dir DIR`` -- Durable data root that object-storage keys are computed
  relative to (default: ``dirs.yaml`` base; also ``AIPPT_DATA_DIR``).

Examples::

    python aippt.py serve --port 8000
    python aippt.py serve --port 8000 --gateway-config gateway.yaml
    python aippt.py serve --view-only
    python aippt.py serve --host 0.0.0.0 --port 8000 --images-dir /app/data/images
    python aippt.py serve --max-upload-mb 100

storage
-------

Object-storage maintenance commands.

.. code-block:: text

   aippt.py storage backfill [options]

The ``backfill`` action performs a one-time upload of the local
``uploads/``, ``images/``, and ``output/`` trees plus a catalog snapshot
(``catalog/slides.db``) to object storage. Used to seed MinIO from an existing
local data directory during cutover. Requires an object-storage backend
(``--storage s3`` or ``AIPPT_STORAGE=s3`` with the ``MINIO_*`` env set).

Options:

- ``--data-dir DIR`` -- Local data root to back up (default: ``dirs.yaml`` base)
- ``--db PATH`` -- Catalog DB to snapshot (default: ``dirs.yaml`` db path)
- ``--storage {fs,s3}`` -- Target backend; must resolve to ``s3``
- ``--dry-run`` -- List what would be uploaded without uploading

Examples::

    python aippt.py storage backfill --data-dir /app/data --dry-run
    python aippt.py storage backfill --data-dir /app/data

models
------

View and manage model configuration stored in ``models.yaml``.

.. code-block:: text

   aippt.py models [subcommand] [options]

With no subcommand, displays the current defaults.

Subcommands:

- ``init`` -- Create ``models.yaml`` from ``models.yaml.example``
- ``set <operation> <model>`` -- Set the default model for an operation
- ``list-available`` -- Show all models in the registry
- ``reset`` -- (Deprecated) Reset all defaults to built-in values

Operations: ``enhance``, ``improve``, ``feedback``, ``notes``, ``tags``, ``image``

Examples::

    python aippt.py models                        # Show current defaults
    python aippt.py models list-available          # List all registry models
    python aippt.py models set enhance gpt-4o      # Change default for enhance
    python aippt.py models init                    # Create models.yaml from example

tags
----

Manage the taxonomy of predefined tags.

.. code-block:: text

   aippt.py tags [subcommand] [options]

With no subcommand, lists all taxonomy tags.

Subcommands:

- ``add <tag> [--category CAT]`` -- Add a tag to the taxonomy
- ``remove <tag>`` -- Remove a tag from the taxonomy
- ``import <csv_file>`` -- Import taxonomy from a CSV file
- ``export <csv_file>`` -- Export taxonomy to a CSV file
- ``rename <old_name> <new_name>`` -- Rename a taxonomy tag

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)

Examples::

    python aippt.py tags                          # List all tags
    python aippt.py tags add "cloud" --category "Technology"
    python aippt.py tags import taxonomy.csv
    python aippt.py tags rename "old-name" "new-name"

tag
---

Add tags to a specific slide.

.. code-block:: text

   aippt.py tag <slide_id> <tags> [options]

Arguments:

- ``slide_id`` -- Slide ID (integer)
- ``tags`` -- Comma-separated tag names

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)

Example::

    python aippt.py tag 42 "security,compliance"

untag
-----

Remove tags from a specific slide.

.. code-block:: text

   aippt.py untag <slide_id> [tags] [options]

Arguments:

- ``slide_id`` -- Slide ID (integer)
- ``tags`` -- Comma-separated tag names (optional if ``--all`` is used)

Options:

- ``--all`` -- Remove all tags from the slide
- ``--db PATH`` -- Database path (default: ``slides.db``)

Examples::

    python aippt.py untag 42 "compliance"
    python aippt.py untag 42 --all

write-notes
-----------

Write speaker notes from the database back into a PPTX file. Creates a
timestamped backup (``.pptx.bak``) before modifying the file.

.. code-block:: text

   aippt.py write-notes <deck> [options]

Arguments:

- ``deck`` -- Path to the PPTX file

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)

Example::

    python aippt.py write-notes deck.pptx

migrate-paths
-------------

Convert absolute database paths to relative paths for portability. This
command is idempotent -- running it multiple times has no additional effect.

.. code-block:: text

   aippt.py migrate-paths [options]

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)
- ``--base-dir DIR`` -- Base directory for relative paths (default: current directory)

Example::

    python aippt.py migrate-paths

merge
-----

Merge multiple PPTX section files into a single deck. Used internally by the
sectioned generation pipeline but available as a standalone command.

.. code-block:: text

   aippt.py merge <chunks...> -o <output> [options]

Arguments:

- ``chunks`` -- One or more PPTX files to merge, in order

Options:

- ``-o, --output PATH`` -- Output file path (required)
- ``--no-renumber`` -- Skip slide number renumbering

Example::

    python aippt.py merge section-1.pptx section-2.pptx section-3.pptx -o final.pptx

merge-template
--------------

Merge a generated deck into a corporate template. The corporate template's
master and all layouts are preserved in the output, and each slide is
re-assigned to a matching corporate layout based on ``[AIPPT-META]``
``layout_selected`` metadata in speaker notes.

.. code-block:: text

   aippt.py merge-template <generated_pptx> --corp-template <template> -o <output> [options]

Arguments:

- ``generated_pptx`` -- Path to the AI-generated PPTX deck

Options:

- ``--corp-template PATH`` -- Path to the corporate template PPTX (required)
- ``-o, --output PATH`` -- Output file path (required)
- ``--layout-map PATH`` -- JSON file overriding the default layout map
- ``--dry-run`` -- Print layout assignments without writing the output file

The default layout map assigns generated slides to corporate layouts:

.. code-block:: text

   title          -> Title Slide - No Image
   bullet         -> Title and Content
   two_column     -> Two Content
   code           -> Developer Code Layout
   section_divider -> Divider slide
   closing        -> Closing logo slide
   (unmapped)     -> Blank

Examples::

    # Merge a generated deck into the corporate template
    python aippt.py merge-template generated.pptx --corp-template templates/corp.pptx -o merged.pptx

    # Preview layout assignments without writing
    python aippt.py merge-template generated.pptx --corp-template templates/corp.pptx -o merged.pptx --dry-run

    # Use a custom layout map
    python aippt.py merge-template generated.pptx --corp-template templates/corp.pptx -o merged.pptx --layout-map custom-map.json

metadata
--------

Extract embedded ``[AIPPT-META]`` blocks from a PPTX file's speaker notes.
Outputs JSON with operation history, layout selections, and lineage tracking.

.. code-block:: text

   aippt.py metadata <deck> [options]

Arguments:

- ``deck`` -- Path to the PPTX file

Options:

- ``--slide N`` -- Show metadata for a specific slide number only

Examples::

    python aippt.py metadata deck.pptx
    python aippt.py metadata deck.pptx --slide 3

db-info
-------

Dump database schema, statistics, and content.

.. code-block:: text

   aippt.py db-info [options]

Options:

- ``--db PATH`` -- Database path (default: ``slides.db``)
- ``--json`` -- Output as JSON instead of plain text
- ``--output PATH`` -- Write output to a file instead of stdout

Examples::

    python aippt.py db-info
    python aippt.py db-info --json --output dbinfo.json

decks
-----

Manage cataloged decks: list, inspect, rename, delete, and view the source
script that produced a generated deck.

.. code-block:: text

   aippt.py decks [subcommand] [options]

Subcommands:

- ``list`` -- List all cataloged decks
- ``info <deck>`` -- Show detailed information for a deck
- ``rename <deck> <new_name>`` -- Set a deck's display name
- ``delete <deck>`` -- Delete a deck and all associated catalog data
- ``source <deck>`` -- Show the source script path for a generated deck
- ``set-origin <deck>`` -- Set or backfill the origin for an existing deck

``<deck>`` accepts a deck ID (integer) or a substring of the deck name.

Common options:

- ``--db PATH`` -- Database path (default: ``slides.db``)
- ``--json`` -- (``list``, ``info``) Output as JSON

``delete`` options:

- ``--force`` -- Skip the confirmation prompt
- ``--purge-images`` -- Also delete the rendered image directory

``source`` options:

- ``--cat`` -- Print the script contents to stdout

``set-origin`` options:

- ``--outline PATH`` -- Markdown outline file that produced this deck
- ``--script PATH`` -- Generator script (``.mjs`` or ``.py``) that produced this deck
- ``--engine {pptxgenjs,python-pptx}`` -- Engine used to generate the deck
- ``--theme NAME`` -- Theme name used (e.g. ``amd``, ``default``)

Exactly one of ``--outline`` or ``--script`` must be provided.  Paths are
stored as absolute paths; the column written depends on which flag is
given (``outline_path`` or ``source_script_path``).  After running
``set-origin``, the **↻ Regenerate** button appears on the deck card in
the web UI.

Examples::

    python aippt.py decks list
    python aippt.py decks list --json
    python aippt.py decks info "Zero Trust"
    python aippt.py decks rename 42 "Zero Trust Architecture v3"
    python aippt.py decks delete 42 --force --purge-images
    python aippt.py decks source 42 --cat

    # Backfill origin on an existing cataloged deck
    python aippt.py decks set-origin "Matt Elliott Intro" --outline source-material/intro.md
    python aippt.py decks set-origin 7 --script output/q1-roadmap.mjs --engine pptxgenjs --theme amd

mcp
---

Manage MCP (Model Context Protocol) server configuration.

.. code-block:: text

   aippt.py mcp [subcommand] [options]

Subcommands:

- ``list`` -- List configured MCP servers and their tools

Common options:

- ``--config PATH`` -- MCP servers config file (default: ``mcp_servers.json``)

``list`` options:

- ``--json`` -- Output as JSON

Examples::

    python aippt.py mcp list
    python aippt.py mcp list --json
    python aippt.py mcp list --config path/to/mcp_servers.json
