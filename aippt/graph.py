"""Microsoft Graph HTTP client for AIPPT.

Stateless, stdlib-only. Designed for server-side use where tokens arrive
per-request from the browser (Authorization: Bearer) or from the
MS_ACCESS_TOKEN environment variable (CLI/CI).

Architectural notes:
  - No file-based token storage. Tokens are caller-supplied per call.
  - All HTTP errors raise GraphError; no sys.exit.
  - Reuses the Microsoft Teams Desktop public client ID
    (1fec8e78-bce4-4aaf-ab1b-5451cc387264) — same as the m365-* SLAI
    marketplace skills. Pre-authorized for Files.ReadWrite.All and
    Sites.ReadWrite.All.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
LOGIN_BASE = "https://login.microsoftonline.com"
DEFAULT_CLIENT_ID = "1fec8e78-bce4-4aaf-ab1b-5451cc387264"
DEFAULT_SCOPES = "Files.ReadWrite.All Sites.ReadWrite.All offline_access"
DEFAULT_TENANT = "organizations"
DEFAULT_TIMEOUT = 30.0


class GraphError(Exception):
    """Raised for any non-success Graph or Azure AD response."""

    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"Graph {status_code} {error_code}: {message}")


def _post_form(url: str, data: dict, *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """POST application/x-www-form-urlencoded; return parsed JSON.

    Raises GraphError on any HTTP error (4xx/5xx) or invalid JSON.
    """
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=encoded, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read() if hasattr(exc, "read") else b""
        try:
            body = json.loads(body_bytes)
        except (ValueError, TypeError):
            body = {}
        raise GraphError(
            status_code=exc.code,
            error_code=body.get("error", "http_error"),
            message=body.get("error_description", str(exc)),
        ) from exc


def start_device_code(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    tenant_id: str = DEFAULT_TENANT,
    scopes: str = DEFAULT_SCOPES,
) -> dict:
    """Begin a device-code authentication flow.

    Returns a dict with: user_code, device_code, verification_uri,
    expires_in (seconds), interval (poll seconds), message.
    """
    url = f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/devicecode"
    return _post_form(url, {"client_id": client_id, "scope": scopes})


def poll_device_code(
    device_code: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    tenant_id: str = DEFAULT_TENANT,
) -> dict:
    """Poll the token endpoint once for a pending device-code flow.

    Returns:
        {"status": "pending"} — user hasn't completed sign-in yet; keep
            polling at the current cadence.
        {"status": "slow_down"} — AAD asked us to back off; the caller
            MUST widen the polling interval (per OAuth 2.0 device-code
            spec) or risk a longer rate-limit lockout.
        {"status": "ok", "access_token": ..., "refresh_token": ...,
         "expires_in": ..., "token_type": ..., "scope": ...} on success.

    Raises GraphError for terminal errors (expired_token, access_denied, etc.).
    Caller is responsible for sleeping `interval` seconds between polls.
    """
    url = f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token"
    try:
        result = _post_form(url, {
            "client_id": client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        })
    except GraphError as exc:
        if exc.error_code == "authorization_pending":
            return {"status": "pending"}
        if exc.error_code == "slow_down":
            return {"status": "slow_down"}
        raise
    return {"status": "ok", **result}


def refresh_access_token(
    refresh_token: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    tenant_id: str = DEFAULT_TENANT,
    scopes: str = DEFAULT_SCOPES,
) -> dict:
    """Exchange a refresh_token for a new access_token (and possibly a new refresh_token).

    Returns the raw token response: access_token, refresh_token, expires_in, ...
    Raises GraphError if the refresh has been revoked or expired.
    """
    url = f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token"
    return _post_form(url, {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": scopes,
    })


def _auth_headers(token: str, *, content_type: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _parse_graph_error(exc: urllib.error.HTTPError) -> GraphError:
    """Extract Graph's nested {"error": {"code": ..., "message": ...}} shape
    OR Azure AD's flat {"error": ..., "error_description": ...} shape."""
    try:
        body = json.loads(exc.read())
    except Exception:
        body = {}
    err = body.get("error")
    if isinstance(err, dict):
        code = err.get("code", "unknown")
        message = err.get("message", str(exc))
    elif isinstance(err, str):
        code = err
        message = body.get("error_description", str(exc))
    else:
        code = "unknown"
        message = str(exc)
    return GraphError(status_code=exc.code, error_code=code, message=message)


def get_json(
    path: str,
    *,
    token: str,
    params: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """GET a Graph endpoint and return the parsed JSON response.

    `path` must start with '/' (e.g. '/me' or '/sites/{id}/drive').
    Raises GraphError on any 4xx/5xx response.
    """
    url = f"{GRAPH_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_auth_headers(token), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise _parse_graph_error(exc) from exc


# Graph soft-cap above which the resumable upload session is required (4 MB).
SMALL_FILE_LIMIT = 4 * 1024 * 1024


def delete_item(
    path: str,
    *,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """DELETE a Graph resource. Returns None on 2xx; raises GraphError otherwise."""
    url = f"{GRAPH_BASE}{path}"
    req = urllib.request.Request(url, headers=_auth_headers(token), method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return None
    except urllib.error.HTTPError as exc:
        raise _parse_graph_error(exc) from exc


def ensure_folder(
    parent_path: str,
    *,
    name: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """Idempotently create a folder named ``name`` under ``parent_path``.

    Graph's small-file PUT does not create intermediate SharePoint folders,
    so per-user subfolders must exist before the first upload. We POST with
    conflictBehavior=fail and swallow 409 so concurrent renders for the same
    NTID don't race each other.

    ``parent_path`` is the path-style Graph URL fragment of the parent (no
    trailing colon), e.g. ``/sites/{sid}/drives/{did}/root:/AIPPT/staging``.
    """
    url = f"{GRAPH_BASE}{parent_path}:/children"
    body = json.dumps({
        "name": name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "fail",
    }).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers=_auth_headers(token, content_type="application/json"),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return None
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            # Folder already exists — treat as success.
            return None
        raise _parse_graph_error(exc) from exc


def put_small_file(
    path: str,
    *,
    data: bytes,
    token: str,
    content_type: str,
    timeout: float = 60.0,
) -> dict:
    """PUT raw bytes to a Graph endpoint (small-file path, < 4 MB).

    `path` is the full Graph item path, typically ending in ':/content'
    for the upload-by-path style.
    """
    url = f"{GRAPH_BASE}{path}"
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers=_auth_headers(token, content_type=content_type),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise _parse_graph_error(exc) from exc


def _create_upload_session(path: str, *, token: str, timeout: float) -> str:
    """POST createUploadSession on a path-style Graph URL; return uploadUrl."""
    url = f"{GRAPH_BASE}{path}:/createUploadSession"
    body = json.dumps({"item": {
        "@microsoft.graph.conflictBehavior": "replace",
    }}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers=_auth_headers(token, content_type="application/json"),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())["uploadUrl"]
    except urllib.error.HTTPError as exc:
        raise _parse_graph_error(exc) from exc


def upload_resumable(
    path: str,
    *,
    data: bytes,
    token: str,
    chunk_size: int = 5 * 1024 * 1024,
    timeout: float = 120.0,
) -> dict:
    """Upload `data` to the path-style Graph URL using a resumable session.

    Use this for files >= 4 MB. Each chunk MUST be a multiple of 320 KB
    except for the final chunk (Graph requirement).
    """
    if chunk_size % (320 * 1024) != 0:
        raise ValueError("chunk_size must be a multiple of 320 KiB")
    upload_url = _create_upload_session(path, token=token, timeout=timeout)
    total = len(data)
    pos = 0
    last_response: dict = {}
    while pos < total:
        end = min(pos + chunk_size, total)
        chunk = data[pos:end]
        req = urllib.request.Request(
            upload_url, data=chunk, method="PUT",
            headers={
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {pos}-{end - 1}/{total}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body_bytes = resp.read()
                if body_bytes:
                    try:
                        last_response = json.loads(body_bytes)
                    except ValueError:
                        last_response = {}
        except urllib.error.HTTPError as exc:
            raise _parse_graph_error(exc) from exc
        pos = end
    return last_response


def download_pdf(
    item_path: str,
    *,
    token: str,
    timeout: float = 90.0,
) -> bytes:
    """Download a SharePoint/OneDrive item as PDF.

    `item_path` is something like '/sites/{sid}/drives/{did}/items/{iid}'.
    Returns raw PDF bytes. urllib's default opener follows 302 redirects
    (Graph returns 302 to the SharePoint CDN), so we just read the body.

    Raises GraphError on 4xx/5xx.
    """
    url = f"{GRAPH_BASE}{item_path}/content?format=pdf"
    req = urllib.request.Request(url, headers=_auth_headers(token), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise _parse_graph_error(exc) from exc


def get_token_from_env() -> Optional[str]:
    """Return the MS_ACCESS_TOKEN env var, stripped of any 'Bearer ' prefix.

    Returns None if the variable is unset or empty.
    """
    raw = os.environ.get("MS_ACCESS_TOKEN", "").strip()
    if not raw:
        return None
    return raw.removeprefix("Bearer ").strip()
