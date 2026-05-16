"""Static-analysis regression guard for the device-code modal in ms-auth.js.

The modal renders network-supplied ``verification_uri`` and ``user_code``
from Microsoft's device-code endpoint. Earlier the modal assembled itself
with ``innerHTML = [...].join('')`` and interpolated those values directly.
Because access/refresh tokens live in localStorage, an XSS in this modal is
a direct token-theft path.

The fix is to:
  1. Build the modal with ``document.createElement`` + ``textContent`` so
     the user_code is rendered as text, never as HTML.
  2. Validate that ``verification_uri`` starts with ``https://`` before
     assigning it to an anchor's ``href`` (a ``javascript:`` URL would
     otherwise execute on click).

The project has no JS test runner, so this Python test reads the JS file
and asserts the dangerous patterns are absent and the safe patterns are
present. It is brittle by design — the point is to scream loudly the next
time someone reintroduces ``innerHTML = ...`` for this rendering path.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


JS_PATH = Path(__file__).parent.parent / "aippt" / "web" / "static" / "js" / "ms-auth.js"


@pytest.fixture(scope="module")
def js_source() -> str:
    return JS_PATH.read_text(encoding="utf-8")


def _extract_function_body(source: str, name: str) -> str:
    """Return the body of `function name(...) { ... }` (best-effort brace match)."""
    pattern = re.compile(
        r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{",
    )
    match = pattern.search(source)
    assert match, f"function {name!r} not found in ms-auth.js"
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
    assert depth == 0, f"function {name!r} body unterminated"
    return source[start:i - 1]


class TestDeviceCodeModalXss:
    def test_render_device_code_does_not_use_innerhtml(self, js_source):
        """The modal renderer must not assemble HTML from network-supplied
        verification_uri / user_code via innerHTML."""
        body = _extract_function_body(js_source, "_renderDeviceCode")
        assert ".innerHTML" not in body, (
            "_renderDeviceCode uses .innerHTML — this re-introduces the XSS "
            "vector for network-supplied verification_uri / user_code. Build "
            "the modal with document.createElement + textContent instead."
        )

    def test_render_device_code_uses_text_content(self, js_source):
        """The renderer must place network values via textContent (not HTML)."""
        body = _extract_function_body(js_source, "_renderDeviceCode")
        assert "textContent" in body, (
            "_renderDeviceCode must use .textContent so user_code is rendered "
            "as text, never parsed as HTML."
        )

    def test_render_device_code_uses_create_element(self, js_source):
        body = _extract_function_body(js_source, "_renderDeviceCode")
        assert "createElement" in body, (
            "_renderDeviceCode must build the modal with document.createElement "
            "rather than string concatenation + innerHTML."
        )

    def test_verification_uri_is_validated_as_https(self, js_source):
        """A javascript: URL in verification_uri would execute on click.
        The modal must reject anything that isn't an https:// URL."""
        body = _extract_function_body(js_source, "_renderDeviceCode")
        assert "https://" in body, (
            "_renderDeviceCode must validate verification_uri begins with "
            "'https://' before assigning it to an anchor href, to prevent "
            "javascript: URL execution."
        )

    def test_modal_skeleton_does_not_use_innerhtml(self, js_source):
        """The dialog skeleton in _ensureModal should also be assembled
        safely. Even though it has no network input today, switching to
        createElement avoids future innerHTML reuse mistakes."""
        body = _extract_function_body(js_source, "_ensureModal")
        # Allow innerHTML='' to clear, but not innerHTML = '<...'
        bad = re.search(r"\.innerHTML\s*=\s*[`'\"]\s*<", body)
        assert bad is None, (
            "_ensureModal builds the dialog skeleton with innerHTML and HTML "
            "strings — use createElement so the modal cannot become an XSS "
            "sink even if a future change adds network-supplied content."
        )


class TestNtidHeaderInFetchWithAuth:
    """fetchWithAuth must attach X-AIPPT-NTID so the Linux render path can
    write to the per-user SharePoint subfolder. Without it, every render
    lands under a generic 'anonymous' folder."""

    def test_fetch_with_auth_attaches_ntid_header(self, js_source):
        body = _extract_function_body(js_source, "fetchWithAuth")
        assert "X-AIPPT-NTID" in body, (
            "fetchWithAuth must attach the X-AIPPT-NTID header from "
            "localStorage so per-user SP folders work on Linux."
        )

    def test_fetch_with_auth_reads_ntid_from_local_storage(self, js_source):
        body = _extract_function_body(js_source, "fetchWithAuth")
        assert "aippt_ntid" in body, (
            "fetchWithAuth must read 'aippt_ntid' from localStorage — the "
            "key already used by the rest of the UI."
        )
