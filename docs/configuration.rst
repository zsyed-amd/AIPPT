Configuration
=============

AIPPT uses YAML configuration files for directory paths, model defaults, and
LLM gateway routing. All config files live in the project root directory.

dirs.yaml
---------

Controls where AIPPT stores and looks for files. Created automatically with
defaults on first run if it doesn't exist.

.. code-block:: yaml

   # All paths are relative to the directory containing this file.
   # Absolute paths are also supported.
   directories:
     outlines: outlines/
     templates: templates/
     uploads: uploads/
     output: output/
     backups: backups/
     images: images/
     db: slides.db

Each key sets the default directory for that type of content. CLI commands
(``serve``, ``catalog``, ``ingest``, ``export-images``) read these defaults
automatically.

models.yaml
------------

Controls which AI model is used for each operation. Initialize from the
included example::

    python aippt.py models init

The file has two sections:

**registry** -- Every model the system can use, with provider, context window,
and capability flags:

.. code-block:: yaml

   registry:
     gpt-4o:
       provider: openai
       max_tokens: 128000
       max_input_tokens: 128000
       supports_vision: true
       supports_images: true
     claude-3.5-sonnet:
       provider: anthropic
       max_tokens: 200000
       max_input_tokens: 200000
       supports_vision: true
       supports_images: false

**defaults** -- Which model to use for each operation:

.. code-block:: yaml

   defaults:
     enhance: "claude-3.5-sonnet"     # aippt create --enhance
     improve: "claude-3.5-sonnet"     # aippt improve
     feedback: "gpt-4o"               # aippt analyze --mode feedback
     notes: "gpt-4o"                  # aippt analyze --mode notes
     tags: "gpt-4o"                   # aippt analyze --mode tags
     image: "dall-e-3"                # aippt create --image-gen dalle

CLI ``--model`` flags override defaults for a single invocation. Models from
OpenAI, Anthropic, and Google are supported. Custom models can be added to the
registry.

Manage defaults via the CLI::

    python aippt.py models                       # View current defaults
    python aippt.py models list-available         # Show all registry models
    python aippt.py models set enhance gpt-4o     # Change a default

gateway.yaml
-------------

Routes LLM API calls through a corporate API gateway instead of calling
provider APIs directly.

.. code-block:: yaml

   gateway:
     base_url: "https://llm-api.example.com"
     auth_header: "Ocp-Apim-Subscription-Key"
     auth_value_env: "GATEWAY_API_KEY"
     # Mandatory per-user header (required by some corporate gateways,
     # e.g. AMD's gateway as of May 2, 2026)
     user_header: "user"
     user_value_env: "AIPPT_USER_NTID"
   providers:
     openai:
       path: "/OpenAI"
     anthropic:
       path: "/Anthropic"
     google:
       path: "/VertexAI"

Fields:

- ``base_url`` -- The gateway's base URL
- ``auth_header`` -- HTTP header name for authentication
- ``auth_value_env`` -- Name of the environment variable containing the auth
  token (e.g. ``GATEWAY_API_KEY``)
- ``user_header`` -- HTTP header name for the per-user identifier (optional;
  required by gateways that enforce per-user accounting)
- ``user_value_env`` -- Name of the environment variable containing the user
  identifier (e.g. ``AIPPT_USER_NTID``). The web UI also accepts this value
  via the ``X-AIPPT-NTID`` header on each request, which overrides the env
  var on a per-request basis.
- ``providers`` -- Maps each provider to a path appended to ``base_url``

Usage::

    # Pass to any LLM-using command
    python aippt.py create outline.md template.pptx output.pptx --enhance --gateway-config gateway.yaml

    # Or place gateway.yaml in the project root (the default path)
    python aippt.py create outline.md template.pptx output.pptx --enhance

sharepoint (Microsoft Graph render staging)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Linux and containerized deployments cannot use PowerPoint COM for image
export. The Graph render pipeline (``PPTX → SharePoint → ?format=pdf →
pdftoppm → PNGs``) stages files in a SharePoint document library. Required
only on Linux/containerized deployments; Windows installations with
PowerPoint can leave this unset.

.. code-block:: yaml

   sharepoint:
     # Graph site ID — "contoso.sharepoint.com,<site-guid>,<web-guid>"
     render_site_id: "REPLACE_WITH_SITE_ID"
     # render_site_id_env: "AIPPT_SP_SITE_ID"

     # Graph drive ID for the document library — "b!xxxxxxxx..."
     render_drive_id: "REPLACE_WITH_DRIVE_ID"
     # render_drive_id_env: "AIPPT_SP_DRIVE_ID"

     # Optional: folder path inside the drive (default
     # "AIPPT/render-staging"). Per-user subfolders (NTID) and per-job
     # filenames (UUID) are appended automatically.
     render_root_path: "AIPPT/render-staging"

Fields:

- ``render_site_id`` -- Microsoft Graph site identifier for the staging site
- ``render_drive_id`` -- Microsoft Graph drive identifier for the document
  library
- ``render_root_path`` -- Optional folder path inside the drive (default
  ``AIPPT/render-staging``)

Each key has an optional ``*_env`` variant that reads the value from the
named environment variable instead — useful for CI / secret management.

See the ``sharepoint-setup`` page (``docs/sharepoint-setup.md``) for
provisioning the staging library and finding the site / drive IDs.

Environment Variables
---------------------

API Keys
^^^^^^^^

Set these for direct API access (not needed when using a gateway):

- ``ANTHROPIC_API_KEY`` -- API key for Claude models (Anthropic)
- ``OPENAI_API_KEY`` -- API key for OpenAI and DALL-E models

Gateway Authentication
^^^^^^^^^^^^^^^^^^^^^^

Set the environment variable named in your ``gateway.yaml``'s
``auth_value_env`` field::

    export GATEWAY_API_KEY='your-gateway-token'

If your gateway also requires a per-user identifier (``user_header`` /
``user_value_env`` in ``gateway.yaml``), set that too::

    export AIPPT_USER_NTID='your-ntid'

The web UI captures this value via the NTID input in the nav bar (persisted
to ``localStorage``) and sends it as ``X-AIPPT-NTID`` on each request,
overriding any env-var default on a per-request basis.

Microsoft Graph (Linux Image Export)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The CLI ``export-images`` command on Linux uses the Microsoft Graph render
pipeline (see ``docs/sharepoint-setup.md``). Set the Graph bearer token in the
environment so the CLI can authenticate as the current user::

    export MS_ACCESS_TOKEN='eyJ0eXAiOiJKV1Qi...'

The web UI does not use this variable — it passes the bearer obtained from
the in-browser Microsoft sign-in flow on each request.

Web Deployment
^^^^^^^^^^^^^^

- ``BASE_PATH`` -- When the web UI is served at a sub-path on a shared
  domain (e.g. ``https://example.com/aippt/``), set this to the path prefix
  (with leading and trailing slashes, ``/aippt/``). The server injects
  ``<base href>`` into ``index.html`` so the SPA's relative ``static/``,
  ``api/``, ``docs/``, and ``slide-image/`` URLs resolve correctly behind
  the prefix. Defaults to ``/`` (apex deployment).

View-Only Mode
^^^^^^^^^^^^^^

- ``AIPPT_VIEW_ONLY`` -- When set to any value, forces the web UI into
  view-only (Library Mode), disabling all LLM-dependent features. Equivalent
  to ``--view-only`` on the CLI.

When neither a gateway config nor direct API keys are detected, the web UI
automatically enters view-only mode.
