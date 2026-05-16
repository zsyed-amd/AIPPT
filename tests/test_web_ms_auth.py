"""Tests for /api/auth/microsoft/* endpoints and Bearer-token passthrough.

The auth endpoints are unauthenticated (they ARE the auth path) and must
also work in view-only mode. The upload endpoint uses the Bearer token to
drive the Linux Graph render path.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aippt import graph
from aippt.web.app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    uploads_dir = str(tmp_path / "uploads")
    app = create_app(db_path=db_path, uploads_dir=uploads_dir, view_only=False)
    return TestClient(app)


@pytest.fixture
def view_only_client(tmp_path):
    db_path = str(tmp_path / "test.db")
    uploads_dir = str(tmp_path / "uploads")
    app = create_app(db_path=db_path, uploads_dir=uploads_dir, view_only=True)
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/auth/microsoft/start
# ---------------------------------------------------------------------------

class TestAuthStart:
    @patch("aippt.web.routes.graph.start_device_code")
    def test_returns_device_code_dict(self, mock_start, client):
        mock_start.return_value = {
            "user_code": "ABC123",
            "device_code": "longopaquedevicecode",
            "verification_uri": "https://microsoft.com/devicelogin",
            "expires_in": 900,
            "interval": 5,
            "message": "To sign in...",
        }
        resp = client.post("/api/auth/microsoft/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_code"] == "ABC123"
        assert body["device_code"] == "longopaquedevicecode"
        assert body["verification_uri"] == "https://microsoft.com/devicelogin"

    @patch("aippt.web.routes.graph.start_device_code")
    def test_works_in_view_only_mode(self, mock_start, view_only_client):
        mock_start.return_value = {
            "user_code": "X", "device_code": "Y",
            "verification_uri": "Z", "expires_in": 60, "interval": 5,
            "message": "m",
        }
        resp = view_only_client.post("/api/auth/microsoft/start")
        assert resp.status_code == 200

    @patch("aippt.web.routes.graph.start_device_code")
    def test_graph_error_returns_502(self, mock_start, client):
        mock_start.side_effect = graph.GraphError(
            500, "internalServerError", "AAD is down",
        )
        resp = client.post("/api/auth/microsoft/start")
        assert resp.status_code == 502
        assert "AAD is down" in resp.json()["error"]


# ---------------------------------------------------------------------------
# /api/auth/microsoft/poll
# ---------------------------------------------------------------------------

class TestAuthPoll:
    @patch("aippt.web.routes.graph.poll_device_code")
    def test_pending_returns_pending(self, mock_poll, client):
        mock_poll.return_value = {"status": "pending"}
        resp = client.post(
            "/api/auth/microsoft/poll", json={"device_code": "abc"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "pending"}

    @patch("aippt.web.routes.graph.poll_device_code")
    def test_success_returns_tokens(self, mock_poll, client):
        mock_poll.return_value = {
            "status": "ok",
            "access_token": "at-xyz",
            "refresh_token": "rt-xyz",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        resp = client.post(
            "/api/auth/microsoft/poll", json={"device_code": "abc"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["access_token"] == "at-xyz"
        assert body["refresh_token"] == "rt-xyz"

    def test_missing_device_code_returns_400(self, client):
        resp = client.post("/api/auth/microsoft/poll", json={})
        assert resp.status_code == 400

    @patch("aippt.web.routes.graph.poll_device_code")
    def test_expired_token_returns_401(self, mock_poll, client):
        mock_poll.side_effect = graph.GraphError(
            400, "expired_token", "Code expired",
        )
        resp = client.post(
            "/api/auth/microsoft/poll", json={"device_code": "abc"},
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# /api/auth/microsoft/refresh
# ---------------------------------------------------------------------------

class TestAuthRefresh:
    @patch("aippt.web.routes.graph.refresh_access_token")
    def test_returns_new_token_pair(self, mock_refresh, client):
        mock_refresh.return_value = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "expires_in": 3600,
        }
        resp = client.post(
            "/api/auth/microsoft/refresh",
            json={"refresh_token": "old-rt"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "new-at"

    def test_missing_refresh_token_returns_400(self, client):
        resp = client.post("/api/auth/microsoft/refresh", json={})
        assert resp.status_code == 400

    @patch("aippt.web.routes.graph.refresh_access_token")
    def test_invalid_grant_returns_401(self, mock_refresh, client):
        mock_refresh.side_effect = graph.GraphError(
            400, "invalid_grant", "Refresh expired",
        )
        resp = client.post(
            "/api/auth/microsoft/refresh", json={"refresh_token": "expired"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/decks/upload — Bearer token passthrough + 401/403 gating
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_pptx_bytes():
    # python-pptx-free minimal payload; ingest_deck is mocked, so any bytes work
    return b"PK\x03\x04fake-pptx"


class TestUploadBearer:
    @patch("aippt.web.routes.ingest_deck")
    def test_bearer_token_threads_to_ingest(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "deck", "slide_count": 3,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer browser-tok-123"},
        )
        assert resp.status_code == 200, resp.text
        assert mock_ingest.call_args.kwargs["ms_token"] == "browser-tok-123"

    @patch("aippt.web.routes.ingest_deck")
    def test_missing_token_returns_401_with_clear_error(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        assert resp.status_code == 401
        assert "sign-in" in resp.json()["error"].lower() or \
               "microsoft" in resp.json()["error"].lower()
        mock_ingest.assert_not_called()

    @patch("aippt.web.routes.ingest_deck")
    def test_view_only_returns_403(
        self, mock_ingest, view_only_client, fake_pptx_bytes
    ):
        resp = view_only_client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 403
        mock_ingest.assert_not_called()

    @patch("aippt.web.routes.ingest_deck")
    def test_strips_bearer_prefix_case_insensitive(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "bearer  spaced-tok  "},
        )
        assert resp.status_code == 200
        assert mock_ingest.call_args.kwargs["ms_token"] == "spaced-tok"


# ---------------------------------------------------------------------------
# R1: upload endpoints must fail loud on render failure (no silent 200)
# ---------------------------------------------------------------------------


class TestUploadStrictBearer:
    """Authorization must be strictly 'Bearer <token>' — any other scheme
    (Basic, Digest, raw token) must be rejected as if no token were sent.

    Without this, `Authorization: Basic anything` slipped past the gate as
    a 'raw token' and tokens were never validated for shape."""

    @patch("aippt.web.routes.ingest_deck")
    def test_basic_auth_is_rejected(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401, resp.text
        mock_ingest.assert_not_called()

    @patch("aippt.web.routes.ingest_deck")
    def test_raw_token_without_scheme_is_rejected(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "rawtokenwithoutscheme"},
        )
        assert resp.status_code == 401, resp.text
        mock_ingest.assert_not_called()

    @patch("aippt.web.routes.ingest_deck")
    def test_digest_auth_is_rejected(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Digest username=foo"},
        )
        assert resp.status_code == 401, resp.text
        mock_ingest.assert_not_called()

    @patch("aippt.web.routes.ingest_deck")
    def test_bearer_with_empty_token_is_rejected(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401, resp.text
        mock_ingest.assert_not_called()


class TestUploadFailLoudOnRenderFailure:
    """When Graph render fails, the upload endpoint must NOT silently return
    200 with a no-images deck. It must propagate a non-2xx status."""

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_requires_images_on_linux(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        """The upload endpoint must call ingest_deck with require_images=True
        on Linux so render failures surface."""
        import sys
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200, resp.text
        if sys.platform.startswith("linux"):
            assert mock_ingest.call_args.kwargs["require_images"] is True

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_graph_401_maps_to_http_401(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        from aippt import graph
        mock_ingest.side_effect = graph.GraphError(
            401, "InvalidAuthenticationToken", "Token expired",
        )
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 401, resp.text
        assert "token" in resp.json()["error"].lower()

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_graph_403_maps_to_http_403(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        from aippt import graph
        mock_ingest.side_effect = graph.GraphError(
            403, "accessDenied", "No SP access",
        )
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 403, resp.text

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_graph_5xx_maps_to_http_502(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        from aippt import graph
        mock_ingest.side_effect = graph.GraphError(
            503, "serviceUnavailable", "SP down",
        )
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 502, resp.text

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_runtime_error_maps_to_http_502(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        """Ingest raises RuntimeError when require_images=True and the export
        path failed for a non-Graph reason (subprocess, FileNotFoundError)."""
        mock_ingest.side_effect = RuntimeError("Image export failed: pdftoppm not found")
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 502, resp.text
        assert "pdftoppm" in resp.json()["error"]


class TestUploadStreamFailLoudOnRenderFailure:
    """Same gates apply to the SSE upload endpoint. Errors land as an SSE
    'error' event, not as a silent 'complete' with no images."""

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_stream_requires_images_on_linux(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        import sys
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload-stream",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200
        # Drain the body so the executor finishes
        _ = resp.text
        if sys.platform.startswith("linux"):
            assert mock_ingest.call_args.kwargs["require_images"] is True

    @patch("aippt.web.routes.ingest_deck")
    def test_upload_stream_graph_error_emits_error_event(
        self, mock_ingest, client, fake_pptx_bytes
    ):
        from aippt import graph
        mock_ingest.side_effect = graph.GraphError(
            401, "InvalidAuthenticationToken", "Token expired",
        )
        resp = client.post(
            "/api/decks/upload-stream",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200  # SSE always 200
        body = resp.text
        assert "event: error" in body
        assert "Token expired" in body
        assert "event: complete" not in body


# ---------------------------------------------------------------------------
# R4: NTID propagation — the X-AIPPT-NTID header must thread through the
# upload endpoint into ingest_deck so the per-user SP subfolder is correct.
# Without this, every user's renders collide under the same "anonymous"
# folder (or whatever USER env var happens to be set on the server).
# ---------------------------------------------------------------------------


class TestUploadNtidPropagation:
    @patch("aippt.web.routes.ingest_deck")
    def test_ntid_header_is_threaded_to_ingest(
        self, mock_ingest, client, fake_pptx_bytes,
    ):
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={
                "Authorization": "Bearer tok",
                "X-AIPPT-NTID": "melliott",
            },
        )
        assert resp.status_code == 200, resp.text
        assert mock_ingest.call_args.kwargs["ntid"] == "melliott"

    @patch("aippt.web.routes.ingest_deck")
    def test_missing_ntid_header_falls_back_to_empty(
        self, mock_ingest, client, fake_pptx_bytes,
    ):
        """No NTID header → ingest_deck receives ntid='' (or None). The CLI
        layer is responsible for choosing the env-var fallback so the web
        layer doesn't leak server-side state into per-user paths."""
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200, resp.text
        # Must be a falsy/empty value, not the server's $USER
        assert not mock_ingest.call_args.kwargs.get("ntid")

    @patch("aippt.web.routes.ingest_deck")
    def test_ntid_is_trimmed(
        self, mock_ingest, client, fake_pptx_bytes,
    ):
        mock_ingest.return_value = {
            "deck_id": 1, "deck_name": "d", "slide_count": 1,
            "images_exported": True, "tags_generated": False,
            "source_tracked": False,
        }
        resp = client.post(
            "/api/decks/upload",
            files={"file": ("deck.pptx", fake_pptx_bytes,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            headers={
                "Authorization": "Bearer tok",
                "X-AIPPT-NTID": "  melliott  ",
            },
        )
        assert resp.status_code == 200, resp.text
        assert mock_ingest.call_args.kwargs["ntid"] == "melliott"


# ---------------------------------------------------------------------------
# R5: slow_down must surface distinctly so the JS poll loop can back off.
# ---------------------------------------------------------------------------


class TestAuthPollSlowDown:
    @patch("aippt.web.routes.graph.poll_device_code")
    def test_slow_down_passes_through(self, mock_poll, client):
        """When poll_device_code returns slow_down, the endpoint must NOT
        rewrite it to 'pending'. The browser uses the distinct status to
        widen its polling interval per the device-code spec."""
        mock_poll.return_value = {"status": "slow_down"}
        resp = client.post(
            "/api/auth/microsoft/poll", json={"device_code": "abc"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "slow_down"}
