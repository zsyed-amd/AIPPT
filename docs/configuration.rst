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

Upload Size Limit
^^^^^^^^^^^^^^^^^

The ``upload:`` block caps the size of inbound deck uploads:

.. code-block:: yaml

    upload:
      max_size_mb: 50

- ``max_size_mb`` -- Maximum upload size in MB (default ``50``). The
  ``UploadSizeLimitMiddleware`` rejects POSTs to ``/api/decks/upload``,
  ``/api/decks/upload-stream``, and ``/api/decks/create`` whose
  ``Content-Length`` exceeds this with HTTP 413; a post-read backstop
  inside the upload handlers catches chunked uploads that omit
  ``Content-Length``. The SPA fetches the value from ``GET /api/config``
  at boot and pre-checks ``file.size`` so the user sees a useful error
  instead of an opaque HTTP/2 protocol error.

Override per-instance with ``aippt serve --max-upload-mb N``. For
container deployments, raise the matching ingress annotation (e.g.
``nginx.ingress.kubernetes.io/proxy-body-size: 50m``) to the same value.

Source Storage
^^^^^^^^^^^^^^

Decks generated through the web **Create from Outline** panel store a
copy of their originating outline at a stable per-deck location inside
the uploads directory::

    uploads/sources/<deck_id>/outline.md

This copy is made immediately after the pipeline succeeds and before the
catalog row is finalized. The catalog row's ``outline_path`` column points
to this stable path so regeneration never depends on a temporary upload
location or a local file that may have moved.

For script-based decks the layout is the same with a ``.mjs`` filename
instead of ``outline.md``; the ``source_engine`` column disambiguates.

The ``uploads/sources/`` tree should be backed up alongside ``uploads/``
and the SQLite database. If the source file for a deck is missing on disk,
regeneration returns HTTP 410; use ``aippt decks set-origin`` to supply a
replacement.

Admin Tier (v1)
^^^^^^^^^^^^^^^

A top-level ``admin_ntids`` list in ``gateway.yaml`` controls who can
hit admin-gated endpoints (``DELETE /api/decks/{id}``,
``GET /api/logs``) on top of the usual Bearer-token requirement:

.. code-block:: yaml

    admin_ntids:
      - ansgputa
      - edtian
      - egroenke
      - melliott
      - miroy
      - yrajesh
      - zsyed

Entries must match the same ``[A-Za-z0-9._-]+`` allowlist enforced on
the ``X-AIPPT-NTID`` header; malformed entries are silently dropped at
load time. An empty list (or omitted block) denies everyone -- useful
for fully view-only deployments.

Matching is **case-insensitive**: entries are lowercased when the config
loads and the incoming ``X-AIPPT-NTID`` header is lowercased before the
membership test, so ``MElliott`` in either place matches ``melliott``.
Keep config entries lowercase and sorted for readability.

**Threat model.** The gate trusts the ``X-AIPPT-NTID`` header for
membership checks, which a signed-in user could edit via
``localStorage.aippt_ntid``. Every admin action (allowed or denied)
emits an audit log line that records both the claimed NTID and a
best-effort identity claim parsed (unverified) from the Bearer JWT, so
impersonation attempts surface in ``GET /api/logs``:

.. code-block:: text

    admin_action  action=delete_deck:42  ntid=melliott  bearer_identity_unverified=upn:jdoe@amd.com

This v1 ships ahead of the original group-based admin design (which
requires the AAD ``groups`` claim in AIPPT's App Registration -- a
pending external dependency). Upgrade when that lands.

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

Storage Backend
^^^^^^^^^^^^^^^

By default AIPPT stores library assets (uploaded/generated decks, rendered
slide images, exported output) and the SQLite catalog on the local
filesystem, rooted at the data directory. For container deployments where
that directory is ephemeral, the ``s3`` backend persists everything to
S3-compatible object storage (MinIO) instead.

- ``AIPPT_STORAGE`` -- ``fs`` (default) or ``s3``. Selects the storage
  backend. Equivalent to ``serve --storage``.
- ``AIPPT_DATA_DIR`` -- Durable data root that object-storage keys are computed
  relative to (e.g. ``/app/data``). Defaults to the ``dirs.yaml`` base
  directory. Equivalent to ``serve --data-dir``. Set this to the data volume in
  container deployments so keys match the ``uploads/`` / ``images/`` /
  ``output/`` layout.

When ``AIPPT_STORAGE=s3`` the following configure the MinIO client. The
access/secret keys must arrive via a Kubernetes ``Secret`` (``secretKeyRef``)
in production — never commit them to a repo file::

    export AIPPT_STORAGE='s3'
    export MINIO_ENDPOINT='s3minio.amd.com:21000'   # S3 API host:port (not the :21001 console)
    export MINIO_BUCKET='ogmatic-zoo'
    export MINIO_PREFIX='asic/aippt/'               # key namespace (default shown)
    export MINIO_ACCESS_KEY='...'
    export MINIO_SECRET_KEY='...'
    export MINIO_CA_BUNDLE='/etc/ssl/certs/ca-bundle-with-amd.pem'  # CA bundle for TLS
    export MINIO_SECURE='1'                          # set 0/false to disable TLS

In ``s3`` mode the pod's local data directory is a read-through/write-through
cache and MinIO is the source of truth. The catalog is restored from the
``catalog/slides.db`` snapshot on startup and a debounced snapshot is pushed
back after catalog writes; blob assets (decks, slide images, sources, output)
are uploaded after they are written and fetched back on a cold pod before
serving. The ``fs`` backend keeps everything on the local volume as before.

To seed object storage from an existing local data directory (one-time
cutover), use ``aippt storage backfill`` (``--dry-run`` to preview)::

    aippt storage backfill --data-dir /app/data --dry-run
    aippt storage backfill --data-dir /app/data

The production cutover, sealed-secret, and TLS-trust steps are documented in
``deploy/slai-app-prod/aippt/OBJECT-STORAGE.md``.
