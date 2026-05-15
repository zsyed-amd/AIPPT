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
