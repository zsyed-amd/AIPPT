# SharePoint Setup for the Graph Render Pipeline

The AIPPT web UI exports slides to PNG by uploading the generated PPTX to a
SharePoint document library, asking Microsoft Graph for its PDF rendition,
then converting that PDF locally with `pdftoppm`. This document describes the
one-time SharePoint configuration required for that pipeline.

> **When you need this:** Linux / containerized deployments only. On Windows
> hosts AIPPT can still drive PowerPoint COM, which bypasses Graph entirely.

## Why a SharePoint library?

Microsoft Graph's `?format=pdf` rendition only works for items already stored
in SharePoint or OneDrive — it does not accept arbitrary bytes. The library
acts as transient render staging:

- Each render uploads `{NTID}/{UUID}.pptx`, downloads the PDF, then `DELETE`s
  the item. The library should be empty most of the time.
- Per-user NTID subfolders give each engineer their own scratch area, which
  makes audit logs and accidental retention obvious.
- No file-based tokens ever land on the server — each request supplies its own
  Bearer token from the browser session.

## 1. Provision the library

Create (or designate) a document library inside an existing SharePoint site.
A dedicated site is cleanest, but any library users can write to will work.

Recommended settings:

| Setting | Value | Why |
|---------|-------|-----|
| Versioning | Off (or low limit) | Renders churn through unique UUID names; version history just wastes quota. |
| Retention | Short (≤ 7 days) or none | The pipeline deletes on success; retention catches leaks. |
| Sync to OneDrive | Disabled | The library is server-side scratch. |

Create the root folder the app will write into. The default is
`AIPPT/render-staging` (configurable via `render_root_path`). The folder must
exist before the first render — the app creates the per-user subfolder on
demand but does **not** create the root.

## 2. Capture `site_id` and `drive_id`

Both IDs are Graph identifiers, not SharePoint URLs. Get them with the Graph
Explorer (https://developer.microsoft.com/graph/graph-explorer) or any
authenticated `GET` against Graph:

```
GET /v1.0/sites/{hostname}:/{server-relative-path}
```

Example:

```
GET /v1.0/sites/contoso.sharepoint.com:/sites/aippt-render
```

The response includes:

```json
{
  "id": "contoso.sharepoint.com,11111111-2222-3333-4444-555555555555,66666666-7777-8888-9999-aaaaaaaaaaaa",
  "displayName": "AIPPT Render"
}
```

That triple is your `render_site_id`. Then fetch the drive:

```
GET /v1.0/sites/{site_id}/drives
```

Find the entry whose `name` matches your library (e.g. `Documents`). Its `id`
field (`b!...`) is your `render_drive_id`.

## 3. Grant access

The web UI uses delegated permissions — every user signs in via device-code
flow and acts as themselves. There are no app credentials. The pre-registered
public client (`1fec8e78-bce4-4aaf-ab1b-5451cc387264`, Microsoft Teams
Desktop) already has `Files.ReadWrite.All` and `Sites.ReadWrite.All` consented
at the Microsoft Graph resource.

What you still need to do in SharePoint:

1. Give every AIPPT user **Contribute** (or higher) on the staging library.
   A simple AAD security group works; add it once and manage membership
   through the group.
2. If your tenant requires admin consent for the two delegated scopes above,
   request it once for the public client ID. Most tenants where the Teams
   Desktop app is already in use have nothing to do here.

The app never authenticates as a service principal, so no client secret,
certificate, or app-registration password is involved.

## 4. Populate `gateway.yaml`

Add a `sharepoint:` block alongside the existing `gateway:` block. See
`gateway.yaml.example` for the canonical template. Inline form:

```yaml
sharepoint:
  render_site_id: "contoso.sharepoint.com,1111...,6666..."
  render_drive_id: "b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  render_root_path: "AIPPT/render-staging"
```

Or, for CI / secret-managed deployments, point the values at env vars:

```yaml
sharepoint:
  render_site_id_env: "AIPPT_SP_SITE_ID"
  render_drive_id_env: "AIPPT_SP_DRIVE_ID"
  render_root_path: "AIPPT/render-staging"
```

`render_root_path` is optional; it defaults to `AIPPT/render-staging`.

If the `sharepoint:` block is missing, the loader logs a warning and the web
UI falls back to refusing image-render requests on Linux. Outline-only and
PPTX-only flows still work without it.

## 5. Verify

After deployment, sign in to the web UI with your Microsoft account, then:

1. Confirm the top-right shows your account and the **Sign in with
   Microsoft** button is gone.
2. Upload a small outline + template and request image export.
3. Watch the staging library: a `{your-ntid}/` folder should appear, contain
   a single `*.pptx` for a few seconds, then empty out.
4. Tail the server logs — you should see the Graph `PUT`, `GET ?format=pdf`,
   and `DELETE` calls, each returning 2xx.

If step 3 leaves `.pptx` files behind, the render failed after upload but
before cleanup. Inspect the SSE error event in the browser's DevTools network
panel; the `code` and `status` fields surface the underlying Graph error
(typical culprits: `accessDenied`, `itemNotFound`, expired token).
