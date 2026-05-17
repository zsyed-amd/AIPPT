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
