Web UI Guide
============

AIPPT includes a web-based interface for browsing, searching, and managing
your slide library. It is built with FastAPI, htmx, and Pico CSS, and uses
the AMD Instinct design system (Klavika headings, DM Sans body, teal accent
``#00C2DE`` on dark surfaces).

Launching the Server
--------------------

Start the web UI::

    python aippt.py serve --port 8000

Open ``http://localhost:8000`` in your browser. See :doc:`cli` for the full
flag list; the most commonly relevant options are:

- ``--host HOST`` -- Bind address (default: ``127.0.0.1``; use ``0.0.0.0``
  for container deployments)
- ``--port N`` -- Port number (default: ``8000``)
- ``--gateway-config PATH`` -- Gateway config for LLM access (default:
  ``gateway.yaml``)
- ``--uploads-dir DIR`` -- Directory for uploaded files (default:
  ``uploads``)
- ``--images-dir DIR`` -- Parent directory for rendered slide images. Set
  this to a persistent volume in container deployments; otherwise PNGs land
  in cwd and are lost on pod restart.
- ``--view-only`` -- Disable LLM features (also settable via
  ``AIPPT_VIEW_ONLY``; auto-detected when no gateway/API keys are present)

Themes
------

The nav bar contains a theme switcher (top-right) with three modes:

- **Dark** (default) — dark surface with teal accent.
- **Light** — AMD corporate light palette.
- **Aurora** — dark surface with an animated background of four colour blobs
  (teal, purple, sky-blue, warm magenta) that drift and morph organically.
  Purely cosmetic; has no effect on functionality.

The selected theme is persisted to ``localStorage`` under the key
``aippt_theme`` and restored on the next page load.

Signing In
----------

LLM features and SharePoint-backed image rendering both require a
Microsoft account. Sign-in is device-code based -- the server never sees
your password and stores no session state; the browser holds a Bearer
token in ``localStorage``.

Click **Sign in to Microsoft** in the nav bar to begin. The modal opens
to an NTID entry screen first (see `Identity and NTID`_ below). After you
enter a valid NTID and click **Continue**, the modal shows:

1. A short user code (e.g. ``ABCD-EFGH``) and a **Copy code** button.
2. A link to ``https://microsoft.com/devicelogin``.

Open the link in a new tab (the same browser is fine), paste the code, and
authenticate as yourself. The modal polls every few seconds and closes
automatically when the sign-in completes. The nav bar swaps the
**Sign in to Microsoft** button for **Sign out** and shows a small NTID
badge.

Tokens live only in your browser, under the ``localStorage`` keys
``aippt_ms_access_token``, ``aippt_ms_refresh_token``,
``aippt_ms_expires_at``, and ``aippt_ms_user_name``. **Sign out** clears
all four. To revoke the refresh token globally (e.g. after pasting a
transcript), visit https://mysignins.microsoft.com/security-info and use
**Sign out everywhere** -- the client-side clear alone does not invalidate
the refresh token on Microsoft's side.

Error states
^^^^^^^^^^^^

- **"Sign-in code expired. Please try again."** -- the device code timed
  out before you finished entering it (default 15 min). Click **Sign in to
  Microsoft** again to get a fresh code.
- **"Sign-in was rejected or expired."** -- you declined consent, or the
  code was invalid. Re-trigger the flow.
- A long-running upload or SSE stream that returns ``status: 401`` mid-flight
  signs you out automatically and surfaces an error -- restart the action
  after signing in again.

Identity and NTID
-----------------

Your NTID is collected as the first step of the Microsoft sign-in flow,
before the device code is issued. When you click **Sign in to Microsoft**
the modal opens to an NTID entry screen. Type your NTID (``A-Z``, ``a-z``,
``0-9``, ``.``, ``_``, ``-``) and click **Continue**; the button stays
disabled until the value is valid, and an inline error explains the
restriction. **Cancel** aborts the flow without starting the device-code
exchange.

After you click **Continue** the value is saved to ``localStorage``
(key ``aippt_ntid``) and the modal proceeds to the device-code screen.
That screen shows a small "NTID: *value* (edit)" line above the code; if
you spot a typo, click **(edit)** to go back to the NTID screen — you
will need to complete a fresh device-code exchange because the previous
code is abandoned.

On successful sign-in, a small ``👤 ntid`` badge appears in the nav bar
next to **Sign out**. Clicking **Sign out** clears both the Microsoft
tokens and the saved NTID from ``localStorage``.

The NTID is forwarded on every authenticated API call:

- As the ``X-AIPPT-NTID`` request header (upload, create, AI actions).
- As a ``user_ntid`` POST field on AI actions; the server forwards it to
  the LLM gateway's ``user:`` header, which AMD's gateway requires for
  attribution.

The server rejects NTIDs that do not match ``^[A-Za-z0-9._-]+$`` with a
400 (path-traversal guard). The NTID input and badge are hidden in
view-only mode.

Deck List
---------

The default view (**LIBRARY** eyebrow → **Cataloged Decks**) shows all
cataloged decks in a table with columns for name, slide count, author,
created date, and updated date.

From the deck list you can:

- **Click a deck name** to browse its slides.
- **Upload Deck** -- upload a ``.pptx`` file (button replaced by **Sign in
  to upload** when not signed in). Linux deployments render slide images
  via Microsoft Graph; see :doc:`sharepoint-setup` for required SharePoint
  configuration. The **Generate AI tags** checkbox triggers tag suggestion
  during ingest (disabled in view-only).
- **Download** -- download the original ``.pptx``.
- **Write Notes to Deck** -- push database notes back into the PPTX file
  (creates a ``.pptx.bak`` backup first).

Regenerate from Source
^^^^^^^^^^^^^^^^^^^^^^

Decks generated through the **Create from Outline** panel carry their
origin (the outline file, engine, and theme) in the catalog. When origin
information is present the deck card shows:

- An **Origin** badge (e.g. ``outline → python-pptx · amd``) with the
  engine and theme used.
- A **↻ Regenerate** button that reruns the same pipeline against the
  stored outline and replaces the deck in place.

Clicking **↻ Regenerate** opens a confirmation modal that shows:

- The stable source path (``uploads/sources/<deck_id>/outline.md``).
- The date the deck was last generated.
- A reminder that the existing PPTX and slide catalog rows will be
  replaced (tags are preserved).

Confirm to start the pipeline. Progress streams in real time via the same
SSE events as **Create from Outline** (parse → enhance → build → ingest).
When regeneration completes, the deck row updates in place -- the
``deck_id`` is unchanged.

**View-only mode:** The **↻ Regenerate** button is hidden and the endpoint
returns 403.

**Missing source file:** If the stored source file has been removed from
disk, the endpoint returns 410 with a message indicating the path.
Backfill the origin using ``aippt decks set-origin`` (see :doc:`cli`).

**Upload-only decks** (no recorded source) do not show the Origin badge
or Regenerate button. ``GET /api/decks/{id}`` returns
``origin: {kind: "upload", ...}`` for these decks.

Creating Presentations from Outlines
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Expand the **Create from Outline** panel below the deck list to generate a
new deck from a markdown outline. The panel supports:

- A textarea for pasting markdown, or an **Upload outline file** button for
  ``.md`` uploads.
- An **Attach images** button for embedding local images referenced by the
  outline (``image/*``, multiple).
- **Enhanced mode** (checked by default) -- LLM picks layouts and writes
  speaker notes. Toggling off creates a deck from the outline as-is.
- **Model** -- pick a model for enhanced mode (populated from
  ``/api/models/available``).
- **Audience** -- adapts enhanced output to one of ``Mixed / General``
  (default), ``Engineers``, ``Executives``, or ``Product``. The selection
  is sent as the ``audience`` form field when non-default.
- **Create Presentation** -- starts the pipeline. Progress streams in real
  time via SSE (parse → enhance → build → ingest).

All Create controls are disabled in view-only mode.

Upload Limits
^^^^^^^^^^^^^

Decks larger than the configured cap (default 50 MB) are rejected before
the multipart POST starts. The SPA reads the cap from ``GET /api/config``
at boot and pre-checks ``file.size`` on selection; if the file is over
the limit, a toast shows ``File too large: X MB. Maximum upload size:
Y MB.`` and the upload never fires.

If the SPA pre-check is bypassed (curl, custom client), the server
enforces the same cap with a JSON 413: middleware short-circuits on
``Content-Length``, and a post-read backstop in the upload handler
catches chunked uploads that omit the header. Container deployments also
need the matching ingress annotation (e.g.
``nginx.ingress.kubernetes.io/proxy-body-size: 50m``); see
:doc:`configuration` for the ``upload:`` block and ``aippt serve
--max-upload-mb N`` for the runtime override.

Duplicate Detection
^^^^^^^^^^^^^^^^^^^

On file selection the SPA computes the SHA-256 of the chosen ``.pptx``
in the browser (``crypto.subtle.digest``) and calls ``GET
/api/decks/by-hash/{sha256}``. If the catalog already has a deck with
that hash, an **Already in catalog** dialog appears with the existing
deck's name, slide count, and cataloging date, plus a **View existing**
button that opens the duplicate's slide browser. The upload never
starts.

To re-process an identical deck, delete the existing entry from the
deck list first (or via ``aippt decks delete``) and re-upload.

If hashing or the lookup fails (non-secure context, network blip, 5xx),
the upload proceeds and the existing server-side dedup in
``catalog_deck`` is the backstop -- the user sees a successful upload
that quietly maps onto the existing catalog row.

Slide Browser
-------------

Clicking a deck shows its slides as a grid of thumbnail cards. Each card
displays the slide image (if available), title, and tags.

**Detail modal**: Click any slide card to open a full-size detail view
showing:

- Slide image.
- Title and section.
- Metadata (author, created, last updated).
- AI action buttons -- **Analyze**, **Suggest Notes**, **Suggest
  Improvements** (all disabled in view-only).
- AI result panel -- title, model name, rendered markdown body, and a
  **Save to Slide Notes** button when the action was **Suggest Notes**.
- Tags with removable ``×`` chips and an autocomplete input (loads
  taxonomy from ``/api/taxonomy`` on first focus).
- Speaker notes (editable) with a history panel.

**Navigation**: Use the next/prev buttons or left/right arrow keys to move
between slides. The modal header shows your position (e.g. "3 of 15").

Search
------

Click **Search** in the nav bar (**DISCOVER** eyebrow → **Search Slides**)
to open the search view.

- **Title** -- filter slides by title substring (placeholder ``e.g. ROCm``).
- **Tags** -- filter by one or more tags (comma-separated; placeholder
  ``e.g. security, architecture``).

Results appear as slide cards. Click any result to open the detail modal.

Tag Sidebar
-----------

Click **Tags** in the nav bar to toggle the tag sidebar. The sidebar
displays all tags grouped by category, with slide counts.

- Click a tag to filter slides across all decks.
- Select multiple tags for AND filtering (only slides with *all* selected
  tags are shown).
- Click **Clear all** to reset the tag filter.

The sidebar state (open/closed) is saved in ``localStorage`` and persists
across page loads.

Notes Editing
-------------

Speaker notes can be edited directly in the slide detail modal:

1. Click into the notes text area.
2. Edit the notes content.
3. Click **Save** or press ``Ctrl+S`` / ``Cmd+S``.
4. Click **Cancel** to discard changes.

A dirty-state indicator warns you of unsaved changes; **Save** and
**Cancel** are disabled until you start editing. The notes history panel
shows previous versions with timestamps and is collapsible below the
editor.

Notes can be written back to the original PPTX file using the **Write
Notes to Deck** button in the deck list.

Settings
--------

Click **Settings** in the nav bar to access configuration:

- **Models** -- view and change default models per operation (``enhance``,
  ``improve``, ``feedback``, ``notes``, ``tags``, ``image``). Each row has
  a dropdown + **Save** button; a footer line shows where the current
  config came from (e.g. ``Source: gateway.yaml``). **Reset all** restores
  the built-in defaults.
- **Default Template** -- the ``.pptx`` template used by ``serve``-driven
  ``create`` calls when no template is provided. Set the path and click
  **Save**.
- **Taxonomy** -- manage the predefined tag taxonomy. Add tags with an
  optional category, remove existing tags via the list, and use
  **Import CSV** / **Export CSV** for bulk edits.
- **Available Models** -- read-only table of all models the gateway
  exposes, including provider, model ID, vision support, image support,
  and context window. Useful for picking what to put in the Models
  dropdown.

In view-only mode the model dropdowns, **Save**, and **Reset all** buttons
are disabled; the Taxonomy and Template sections remain interactive
because they do not require an LLM.

Theme
-----

The nav bar has a ``🌓`` toggle that switches between the AMD Instinct
dark theme (default) and a light variant. The choice persists to
``localStorage`` (key ``aippt_theme``, values ``dark`` or ``light``) and is
applied by a synchronous head script before first paint, so the theme
never flashes on load.

Both themes use Klavika for headings, DM Sans for body text, and the
Instinct teal accent (``#00C2DE`` on dark, ``#007DB8`` on light). The dark
theme adds a 40 px dot-grid background.

View-Only Mode
--------------

When no LLM gateway or API keys are configured, the web UI automatically
enters **Library Mode** (view-only). This can also be forced with
``--view-only`` or the ``AIPPT_VIEW_ONLY`` env var.

In view-only mode:

- Browsing, searching, tagging, and downloading all work normally.
- LLM-dependent features (Enhanced mode, **Analyze**, **Suggest Notes**,
  **Suggest Improvements**, AI tagging during ingest) are disabled and
  show "LLM not configured" tooltips.
- The **Library Mode** badge appears in the nav bar.
- The NTID input and Microsoft sign-in controls are hidden -- there is
  nothing for them to gate.
- Upload still works (cataloging itself does not require an LLM); on
  Linux, image rendering still requires SharePoint configuration.

This mode is ideal for deploying a shared, read-only slide library (e.g.
via the :doc:`backup/restore workflow <backup-restore>`).

Export CSV
----------

Click **Export CSV** in the nav bar to download a CSV file containing
metadata for all cataloged slides (title, notes, tags, deck name, image
path, etc.). The export honors any active tag-sidebar filter.

Diagnostic Endpoints
--------------------

A few endpoints exist for ops triage and have no UI surface yet:

- ``GET /api/config`` -- public, unauthenticated. Returns
  ``{view_only, max_upload_bytes}`` so the SPA can pre-check uploads
  without hardcoding deployment-specific limits.
- ``GET /api/decks/by-hash/{sha256}`` -- public. Returns existing deck
  metadata for a given SHA-256 file hash, or 404. Used by the
  duplicate-upload pre-check; safe to call directly when scripting.
- ``GET /api/auth/whoami`` -- returns
  ``{signed_in, ntid, is_admin}``. The SPA will use this to gate
  admin-only UI controls (delete button, log panel) when those land.
  The actual admin gate runs server-side on each admin endpoint --
  ``is_admin: true`` in the response is a hint, not a permission.
- ``GET /api/logs`` -- in-memory ring buffer (capacity 2000) of recent log
  records. **Admin-gated** (in addition to the Bearer requirement);
  allowed in view-only mode because it has no mutating side effects.
  Supports ``limit``, ``level``, ``since`` (cursor polling), and
  ``logger_prefix`` query parameters. Useful on the SLAI platform where
  ``kubectl logs`` is not exposed to deck authors. See
  :doc:`configuration` for the ``admin_ntids`` list.
- ``DELETE /api/decks/{id}?purge_images=true|false`` -- **admin-gated**
  deck removal. Rejected in view-only mode. Not yet surfaced as a UI
  control -- use ``aippt decks delete`` from the CLI for now.

Admin actions emit an audit log line that records both the claimed
``X-AIPPT-NTID`` and a best-effort identity parsed from the Bearer JWT
(unverified -- audit only). See :doc:`configuration` for the threat
model.
