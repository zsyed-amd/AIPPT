"""Unit tests for aippt.graph — Microsoft Graph HTTP client."""
from __future__ import annotations

import io
import json
import time
import urllib.error
from unittest.mock import patch, MagicMock

import pytest

from aippt import graph


class TestGraphError:
    def test_graph_error_carries_status_and_code(self):
        err = graph.GraphError(
            status_code=401,
            error_code="invalid_token",
            message="The access token is invalid",
        )
        assert err.status_code == 401
        assert err.error_code == "invalid_token"
        assert err.message == "The access token is invalid"
        assert "invalid_token" in str(err)
        assert "401" in str(err)


class TestStartDeviceCode:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_returns_user_code_and_verification_uri(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "user_code": "ABC123",
            "device_code": "longopaquedevicecode",
            "verification_uri": "https://microsoft.com/devicelogin",
            "expires_in": 900,
            "interval": 5,
            "message": "To sign in...",
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = graph.start_device_code()

        assert result["user_code"] == "ABC123"
        assert result["device_code"] == "longopaquedevicecode"
        assert result["verification_uri"] == "https://microsoft.com/devicelogin"
        assert result["expires_in"] == 900
        assert result["interval"] == 5

        called_url = mock_urlopen.call_args[0][0].full_url
        assert "/organizations/oauth2/v2.0/devicecode" in called_url
        body = mock_urlopen.call_args[0][0].data.decode()
        assert "client_id=1fec8e78-bce4-4aaf-ab1b-5451cc387264" in body
        assert "Files.ReadWrite.All" in body

    @patch("aippt.graph.urllib.request.urlopen")
    def test_custom_tenant_in_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "user_code": "X", "device_code": "Y",
            "verification_uri": "Z", "expires_in": 60, "interval": 5,
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        graph.start_device_code(tenant_id="contoso.onmicrosoft.com")

        called_url = mock_urlopen.call_args[0][0].full_url
        assert "/contoso.onmicrosoft.com/oauth2/v2.0/devicecode" in called_url

    @patch("aippt.graph.urllib.request.urlopen")
    def test_http_error_raises_graph_error(self, mock_urlopen):
        body = json.dumps({"error": "invalid_client",
                           "error_description": "Bad client id"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=400, msg="Bad Request", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.start_device_code()
        assert exc.value.status_code == 400
        assert exc.value.error_code == "invalid_client"


class TestPollDeviceCode:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_returns_pending_when_authorization_pending(self, mock_urlopen):
        body = json.dumps({"error": "authorization_pending",
                           "error_description": "User has not signed in"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=400, msg="", hdrs=None, fp=io.BytesIO(body))

        result = graph.poll_device_code(device_code="abc",
                                        tenant_id="organizations")
        assert result == {"status": "pending"}

    @patch("aippt.graph.urllib.request.urlopen")
    def test_returns_tokens_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "at-xyz",
            "refresh_token": "rt-xyz",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "Files.ReadWrite.All",
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = graph.poll_device_code(device_code="abc")
        assert result["status"] == "ok"
        assert result["access_token"] == "at-xyz"
        assert result["refresh_token"] == "rt-xyz"
        assert result["expires_in"] == 3600

    @patch("aippt.graph.urllib.request.urlopen")
    def test_expired_token_raises_graph_error(self, mock_urlopen):
        body = json.dumps({"error": "expired_token",
                           "error_description": "Code expired"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=400, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.poll_device_code(device_code="abc")
        assert exc.value.error_code == "expired_token"

    @patch("aippt.graph.urllib.request.urlopen")
    def test_slow_down_returns_pending(self, mock_urlopen):
        body = json.dumps({"error": "slow_down"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=400, msg="", hdrs=None, fp=io.BytesIO(body))

        result = graph.poll_device_code(device_code="abc")
        assert result == {"status": "pending"}


class TestRefreshAccessToken:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_returns_new_token_pair(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "expires_in": 3600,
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = graph.refresh_access_token("old-rt")
        assert result["access_token"] == "new-at"
        assert result["refresh_token"] == "new-rt"

        body = mock_urlopen.call_args[0][0].data.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=old-rt" in body

    @patch("aippt.graph.urllib.request.urlopen")
    def test_invalid_grant_raises(self, mock_urlopen):
        body = json.dumps({"error": "invalid_grant",
                           "error_description": "Refresh expired"}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=400, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.refresh_access_token("expired-rt")
        assert exc.value.error_code == "invalid_grant"


class TestGetJson:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_get_returns_parsed_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"id": "abc", "name": "Test"}).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = graph.get_json("/me", token="bearer-tok")
        assert result == {"id": "abc", "name": "Test"}

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://graph.microsoft.com/v1.0/me"
        assert req.headers["Authorization"] == "Bearer bearer-tok"

    @patch("aippt.graph.urllib.request.urlopen")
    def test_get_appends_query_params(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        graph.get_json("/users", token="t",
                       params={"$filter": "displayName eq 'X'", "$top": "5"})

        url = mock_urlopen.call_args[0][0].full_url
        assert "%24filter=displayName+eq+%27X%27" in url
        assert "%24top=5" in url

    @patch("aippt.graph.urllib.request.urlopen")
    def test_get_401_raises_graph_error(self, mock_urlopen):
        body = json.dumps({"error": {"code": "InvalidAuthenticationToken",
                                     "message": "Token expired"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=401, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.get_json("/me", token="bad")
        assert exc.value.status_code == 401
        assert exc.value.error_code == "InvalidAuthenticationToken"


class TestDeleteItem:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_delete_uses_delete_method(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.status = 204
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        graph.delete_item("/sites/x/drive/items/y", token="t")

        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "DELETE"
        assert req.headers["Authorization"] == "Bearer t"

    @patch("aippt.graph.urllib.request.urlopen")
    def test_delete_404_raises(self, mock_urlopen):
        body = json.dumps({"error": {"code": "itemNotFound",
                                     "message": "Not found"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=404, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.delete_item("/sites/x/drive/items/y", token="t")
        assert exc.value.status_code == 404


class TestPutSmallFile:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_put_small_uploads_bytes(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "id": "ITEM_ID",
            "name": "test.pptx",
            "size": 1234,
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = graph.put_small_file(
            "/sites/SID/drives/DID/root:/AIPPT/render-staging/ntid/job.pptx:/content",
            data=b"fake-pptx-bytes",
            token="t",
            content_type=("application/vnd.openxmlformats-officedocument."
                          "presentationml.presentation"),
        )

        assert result["id"] == "ITEM_ID"
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "PUT"
        assert req.data == b"fake-pptx-bytes"
        assert req.headers["Content-type"].startswith(
            "application/vnd.openxmlformats")

    @patch("aippt.graph.urllib.request.urlopen")
    def test_put_small_409_raises(self, mock_urlopen):
        body = json.dumps({"error": {"code": "nameAlreadyExists",
                                     "message": "Conflict"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=409, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.put_small_file("/x", data=b"d", token="t",
                                 content_type="application/octet-stream")
        assert exc.value.status_code == 409


class TestUploadResumable:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_creates_session_then_uploads_in_chunks(self, mock_urlopen):
        # 1st call: POST createUploadSession -> {uploadUrl}
        # 2nd call: PUT chunk 1
        # 3rd call: PUT chunk 2 (final, returns driveItem)
        session_resp = MagicMock()
        session_resp.read.return_value = json.dumps({
            "uploadUrl": "https://upload.example/session/abc",
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }).encode()
        session_resp.__enter__.return_value = session_resp

        chunk1_resp = MagicMock()
        chunk1_resp.read.return_value = b""
        chunk1_resp.__enter__.return_value = chunk1_resp

        final_resp = MagicMock()
        final_resp.read.return_value = json.dumps({
            "id": "FINAL_ID", "name": "big.pptx", "size": 6_000_000,
        }).encode()
        final_resp.__enter__.return_value = final_resp

        mock_urlopen.side_effect = [session_resp, chunk1_resp, final_resp]

        # 6 MB payload, chunk size 5 MB (16 * 320 KiB, Graph-valid) -> 2 chunks
        payload = b"x" * 6_000_000
        result = graph.upload_resumable(
            "/sites/SID/drives/DID/root:/path/big.pptx",
            data=payload, token="t",
            chunk_size=5 * 1024 * 1024,
        )

        assert result["id"] == "FINAL_ID"
        assert mock_urlopen.call_count == 3

        # Session creation request
        sess_req = mock_urlopen.call_args_list[0][0][0]
        assert sess_req.get_method() == "POST"
        assert "createUploadSession" in sess_req.full_url

        # Chunk 1: bytes 0-5242879/6000000
        c1 = mock_urlopen.call_args_list[1][0][0]
        assert c1.get_method() == "PUT"
        assert c1.headers["Content-range"] == "bytes 0-5242879/6000000"
        assert c1.headers["Content-length"] == "5242880"

        # Chunk 2 (final, may be any size): bytes 5242880-5999999/6000000
        c2 = mock_urlopen.call_args_list[2][0][0]
        assert c2.headers["Content-range"] == "bytes 5242880-5999999/6000000"
        assert c2.headers["Content-length"] == str(6_000_000 - 5_242_880)


class TestDownloadPdf:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_follows_302_to_download_url(self, mock_urlopen):
        # Graph returns a 302 with a Location header pointing at the SP CDN.
        # urllib by default follows redirects — we need to verify the bytes
        # come back, not the redirect mechanics. So mock urlopen to return
        # a streamed response containing PDF bytes.
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"%PDF-1.7\n...payload..."
        mock_resp.headers.get_content_type.return_value = "application/pdf"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        pdf_bytes = graph.download_pdf(
            "/sites/SID/drives/DID/items/ITEM",
            token="t",
        )

        assert pdf_bytes.startswith(b"%PDF")
        req = mock_urlopen.call_args[0][0]
        assert req.full_url.endswith("/content?format=pdf")
        assert req.headers["Authorization"] == "Bearer t"

    @patch("aippt.graph.urllib.request.urlopen")
    def test_404_raises(self, mock_urlopen):
        body = json.dumps({"error": {"code": "itemNotFound",
                                     "message": "Not found"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=404, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.download_pdf("/sites/x/drives/y/items/z", token="t")
        assert exc.value.status_code == 404


class TestGetTokenFromEnv:
    def test_returns_token_when_env_set(self, monkeypatch):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "abc-123")
        assert graph.get_token_from_env() == "abc-123"

    def test_strips_bearer_prefix(self, monkeypatch):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "Bearer abc-123")
        assert graph.get_token_from_env() == "abc-123"

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("MS_ACCESS_TOKEN", raising=False)
        assert graph.get_token_from_env() is None

    def test_returns_none_when_empty(self, monkeypatch):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "")
        assert graph.get_token_from_env() is None

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "  abc-123  ")
        assert graph.get_token_from_env() == "abc-123"


# ---------------------------------------------------------------------------
# R4: idempotent folder creation for the per-user SP staging subfolder.
#
# Graph's small-file PUT does NOT consistently create intermediate folders
# on SharePoint (it does for OneDrive personal). Without an explicit folder
# step, the first upload for a new NTID 404s. ensure_folder() POSTs a
# children-create with conflictBehavior=fail and treats 409 as success
# so concurrent renders for the same NTID don't race.
# ---------------------------------------------------------------------------


class TestEnsureFolder:
    @patch("aippt.graph.urllib.request.urlopen")
    def test_creates_folder_with_conflict_behavior_fail(self, mock_urlopen):
        """Happy path: POST /children with folder facet + conflictBehavior=fail."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"id": "folder-id", "name": "melliott"}).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        graph.ensure_folder(
            "/sites/SID/drives/DID/root:/AIPPT/render-staging",
            name="melliott",
            token="t",
        )

        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url.endswith("/children")
        body = json.loads(req.data)
        assert body["name"] == "melliott"
        assert "folder" in body
        # Idempotency knob — fail on conflict so we can swallow 409 cleanly.
        assert body["@microsoft.graph.conflictBehavior"] == "fail"

    @patch("aippt.graph.urllib.request.urlopen")
    def test_409_conflict_is_idempotent_success(self, mock_urlopen):
        """409 'nameAlreadyExists' must NOT raise — concurrent renders race."""
        body = json.dumps({"error": {"code": "nameAlreadyExists",
                                     "message": "Already there"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=409, msg="", hdrs=None, fp=io.BytesIO(body))

        # Must not raise. Return value irrelevant; the side effect is "folder exists now."
        graph.ensure_folder(
            "/sites/SID/drives/DID/root:/AIPPT/render-staging",
            name="melliott",
            token="t",
        )

    @patch("aippt.graph.urllib.request.urlopen")
    def test_other_errors_raise(self, mock_urlopen):
        body = json.dumps({"error": {"code": "accessDenied",
                                     "message": "No access"}}).encode()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="x", code=403, msg="", hdrs=None, fp=io.BytesIO(body))

        with pytest.raises(graph.GraphError) as exc:
            graph.ensure_folder(
                "/sites/SID/drives/DID/root:/AIPPT/render-staging",
                name="melliott",
                token="t",
            )
        assert exc.value.status_code == 403
        assert exc.value.error_code == "accessDenied"
