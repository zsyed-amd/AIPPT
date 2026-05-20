"""Static guard for ``index.html`` -- ensures privileged endpoints go through
``msAuth.fetchWithAuth`` so the Bearer token + ``X-AIPPT-NTID`` headers are
attached and the one-shot refresh-on-401 path runs.

Background: the web UI hits the server with several SSE-streaming endpoints
(``/api/decks/create``, ``/api/decks/upload-stream``) that are now Bearer-
gated. Without ``fetchWithAuth`` the server returns 401 for every signed-in
user, and an expired token silently leaves the user "signed in" until they
try a different operation. There is no JS test runner in this repo, so we
parse the static HTML and assert each privileged ``fetch(... '/api/...')``
call goes through the auth wrapper.

This is brittle by design — the point is to scream loudly the next time
someone reintroduces a plain ``fetch()`` against a Bearer-gated endpoint.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


HTML_PATH = (
    Path(__file__).parent.parent / "aippt" / "web" / "static" / "index.html"
)


@pytest.fixture(scope="module")
def html_source() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


# Endpoints that REQUIRE Authorization: Bearer per the server contract.
# Keep this list in sync with the @auth-required routes in routes.py.
BEARER_GATED_ENDPOINTS = [
    "/api/decks/create",
    "/api/decks/upload-stream",
]


@pytest.mark.parametrize("endpoint", BEARER_GATED_ENDPOINTS)
def test_endpoint_is_called_via_fetch_with_auth(html_source: str, endpoint: str):
    """Every reference to a Bearer-gated endpoint must use msAuth.fetchWithAuth.

    Plain ``fetch('/api/decks/create', ...)`` silently drops the token and
    NTID headers, so the server 401s and the user can't tell why.
    """
    # Find every fetch-style call that mentions the endpoint, in either
    # plain or auth-wrapped form. The regex is intentionally generous
    # (handles single and double quotes, optional whitespace).
    pattern = re.compile(
        r"(?P<wrapper>\w+(?:\.\w+)?)?\s*"
        r"(?P<fn>fetch|fetchWithAuth)\s*"
        r"\(\s*['\"]" + re.escape(endpoint) + r"['\"]"
    )
    matches = list(pattern.finditer(html_source))
    assert matches, (
        f"{endpoint!r} not referenced in index.html — did the endpoint move? "
        "Update BEARER_GATED_ENDPOINTS if so."
    )
    for m in matches:
        wrapper = (m.group("wrapper") or "").rstrip(".")
        fn = m.group("fn")
        # Acceptable shapes:
        #   msAuth.fetchWithAuth('/api/decks/create', ...)
        #   fetchWithAuth('/api/decks/create', ...)
        # Reject:
        #   fetch('/api/decks/create', ...)
        if fn == "fetchWithAuth":
            continue
        # fn == "fetch" — only OK if it's actually msAuth.fetchWithAuth that
        # got matched as `wrapper="msAuth.fetch"`. Be strict and fail.
        raise AssertionError(
            f"Plain fetch() on {endpoint!r} at offset {m.start()}: "
            "use msAuth.fetchWithAuth so the Bearer token and X-AIPPT-NTID "
            "header are attached."
        )


def _extract_function_body(source: str, name: str) -> str:
    """Return the body of ``function name(...) { ... }`` (best-effort braces)."""
    pattern = re.compile(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
    )
    match = pattern.search(source)
    assert match, f"function {name!r} not found in index.html"
    start = match.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return source[start:i - 1]


# SSE error events tunnel server-side errors over a 200 response. When the
# server emits ``event: error\ndata: {"status": 401, ...}`` it means the
# bearer token has been rejected mid-stream. fetchWithAuth's HTTP-level
# refresh-on-401 doesn't fire (the response was already 200), so the
# handlers must explicitly notice the in-band 401 and sign the user out —
# otherwise the UI keeps the stale token in localStorage and just toasts
# every subsequent retry.
SSE_HANDLERS_REQUIRING_401_HOOK = [
    "handleUploadEvent",
    "handleCreateEvent",
]


@pytest.mark.parametrize("handler", SSE_HANDLERS_REQUIRING_401_HOOK)
def test_sse_handler_signs_out_on_401(html_source: str, handler: str):
    """SSE error events with status 401 must trigger msAuth.signOut()."""
    body = _extract_function_body(html_source, handler)
    # Must read the status field from the error event.
    assert re.search(r"data\.status\s*===?\s*401", body), (
        f"{handler} does not check data.status === 401 on SSE error events. "
        "Without it, expired-token errors during streaming are silently "
        "toasted while the stale token stays in localStorage."
    )
    # Must actually sign the user out so the UI reverts to the signed-out
    # nav state and the next privileged action triggers re-auth.
    assert "msAuth.signOut" in body, (
        f"{handler} sees the 401 but doesn't call msAuth.signOut() — the "
        "UI will keep claiming the user is signed in with a dead token."
    )
