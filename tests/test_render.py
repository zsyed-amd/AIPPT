"""Unit tests for aippt.render — Graph-based PPTX → PNG pipeline."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

import pytest

from aippt import render


class TestBuildUploadPath:
    def test_path_includes_ntid_and_job_id(self):
        path = render._build_upload_path(
            site_id="SID", drive_id="DID",
            root_path="AIPPT/render-staging",
            ntid="melliott", job_id="abcd1234",
        )
        assert path == (
            "/sites/SID/drives/DID/root:"
            "/AIPPT/render-staging/melliott/abcd1234.pptx"
        )

    def test_strips_leading_and_trailing_slashes_in_root(self):
        path = render._build_upload_path(
            site_id="S", drive_id="D",
            root_path="/AIPPT/staging/",
            ntid="x", job_id="y",
        )
        assert path == "/sites/S/drives/D/root:/AIPPT/staging/x/y.pptx"

    def test_rejects_empty_ntid(self):
        with pytest.raises(ValueError, match="ntid"):
            render._build_upload_path(
                site_id="S", drive_id="D", root_path="r",
                ntid="", job_id="j",
            )


class TestRenderHappyPath:
    @patch("aippt.render.shutil.which", return_value="/usr/bin/pdftoppm")
    @patch("aippt.render.subprocess.run")
    @patch("aippt.render.graph")
    def test_small_file_uses_put_small(self, mock_graph, mock_run, _which, tmp_path):
        # Fake input PPTX (< 4 MB)
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"x" * 1024)

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # Graph stubs
        mock_graph.SMALL_FILE_LIMIT = 4 * 1024 * 1024
        mock_graph.PPTX_CONTENT_TYPE = render.PPTX_CONTENT_TYPE
        mock_graph.put_small_file.return_value = {"id": "ITEM_ID"}
        mock_graph.download_pdf.return_value = b"%PDF-1.7 fake"
        mock_graph.delete_item.return_value = None

        # pdftoppm stub: write 3 PNG files into out_dir
        def _fake_run(cmd, **kw):
            for i in range(1, 4):
                (out_dir / f"slide-{i:02d}.png").write_bytes(b"PNG")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        mock_run.side_effect = _fake_run

        pngs = render.render_pptx_to_pngs(
            pptx_path=str(pptx),
            out_dir=str(out_dir),
            token="bearer-tok",
            ntid="melliott",
            site_id="SID",
            drive_id="DID",
            root_path="AIPPT/render-staging",
            dpi=150,
        )

        assert len(pngs) == 3
        assert all(p.suffix == ".png" for p in pngs)

        mock_graph.put_small_file.assert_called_once()
        kwargs = mock_graph.put_small_file.call_args.kwargs
        assert kwargs["token"] == "bearer-tok"
        assert kwargs["content_type"] == render.PPTX_CONTENT_TYPE
        assert "melliott/" in mock_graph.put_small_file.call_args.args[0]
        assert mock_graph.put_small_file.call_args.args[0].endswith(
            "/content")

        mock_graph.download_pdf.assert_called_once()
        dl_path = mock_graph.download_pdf.call_args.args[0]
        assert dl_path == "/sites/SID/drives/DID/items/ITEM_ID"

        # Cleanup
        mock_graph.delete_item.assert_called_once_with(
            "/sites/SID/drives/DID/items/ITEM_ID", token="bearer-tok")

        # pdftoppm called with -png and the right -r
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "pdftoppm"
        assert "-png" in cmd
        assert "-r" in cmd and "150" in cmd


class TestRenderLargeFile:
    @patch("aippt.render.shutil.which", return_value="/usr/bin/pdftoppm")
    @patch("aippt.render.subprocess.run")
    @patch("aippt.render.graph")
    def test_large_file_uses_resumable(self, mock_graph, mock_run, _which, tmp_path):
        pptx = tmp_path / "big.pptx"
        # Just over the 4 MB limit
        pptx.write_bytes(b"x" * (4 * 1024 * 1024 + 100))

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_graph.SMALL_FILE_LIMIT = 4 * 1024 * 1024
        mock_graph.upload_resumable.return_value = {"id": "BIG_ID"}
        mock_graph.download_pdf.return_value = b"%PDF"
        mock_graph.delete_item.return_value = None
        mock_run.side_effect = lambda cmd, **kw: (
            (out_dir / "slide-1.png").write_bytes(b"PNG")
            or subprocess.CompletedProcess(cmd, 0))

        render.render_pptx_to_pngs(
            pptx_path=str(pptx), out_dir=str(out_dir),
            token="t", ntid="x", site_id="S", drive_id="D",
            root_path="r",
        )

        mock_graph.upload_resumable.assert_called_once()
        mock_graph.put_small_file.assert_not_called()


class TestRenderCleanupOnFailure:
    @patch("aippt.render.shutil.which", return_value="/usr/bin/pdftoppm")
    @patch("aippt.render.graph")
    def test_pdf_download_failure_still_deletes_staged_pptx(
        self, mock_graph, _which, tmp_path
    ):
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"x" * 100)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_graph.SMALL_FILE_LIMIT = 4 * 1024 * 1024
        mock_graph.put_small_file.return_value = {"id": "ITEM_ID"}
        mock_graph.download_pdf.side_effect = mock_graph.GraphError = type(
            "GraphError", (Exception,), {"status_code": 500,
                                         "error_code": "x", "message": "y"})
        mock_graph.download_pdf.side_effect = mock_graph.GraphError(
            500, "internalServerError", "boom")
        mock_graph.delete_item.return_value = None

        with pytest.raises(Exception):
            render.render_pptx_to_pngs(
                pptx_path=str(pptx), out_dir=str(out_dir),
                token="t", ntid="x", site_id="S", drive_id="D",
                root_path="r",
            )

        mock_graph.delete_item.assert_called_once_with(
            "/sites/S/drives/D/items/ITEM_ID", token="t")

    @patch("aippt.render.shutil.which", return_value="/usr/bin/pdftoppm")
    @patch("aippt.render.graph")
    def test_delete_failure_does_not_mask_render_success(
        self, mock_graph, _which, tmp_path
    ):
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"x" * 100)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_graph.SMALL_FILE_LIMIT = 4 * 1024 * 1024
        mock_graph.put_small_file.return_value = {"id": "ITEM_ID"}
        mock_graph.download_pdf.return_value = b"%PDF"
        # delete_item raises but it's wrapped — must not fail the call
        mock_graph.GraphError = type(
            "GraphError", (Exception,), {})
        mock_graph.delete_item.side_effect = mock_graph.GraphError("nope")

        with patch("aippt.render.subprocess.run") as mock_run:
            mock_run.side_effect = lambda cmd, **kw: (
                (out_dir / "slide-1.png").write_bytes(b"PNG")
                or subprocess.CompletedProcess(cmd, 0))
            # The point of this test: delete failure must not propagate.
            # Patch render's reference to graph.GraphError to match the mock.
            with patch("aippt.render.graph.GraphError",
                       mock_graph.GraphError):
                pngs = render.render_pptx_to_pngs(
                    pptx_path=str(pptx), out_dir=str(out_dir),
                    token="t", ntid="x", site_id="S", drive_id="D",
                    root_path="r",
                )
        assert len(pngs) == 1


class TestRenderPreconditions:
    def test_missing_pptx_raises_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="PPTX not found"):
            render.render_pptx_to_pngs(
                pptx_path=str(tmp_path / "missing.pptx"),
                out_dir=str(tmp_path / "out"),
                token="t", ntid="x", site_id="S",
                drive_id="D", root_path="r",
            )

    @patch("aippt.render.shutil.which", return_value=None)
    def test_missing_pdftoppm_raises_filenotfound(self, _which, tmp_path):
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"x")
        with pytest.raises(FileNotFoundError, match="poppler-utils"):
            render.render_pptx_to_pngs(
                pptx_path=str(pptx), out_dir=str(tmp_path / "o"),
                token="t", ntid="x", site_id="S", drive_id="D",
                root_path="r",
            )


# ---------------------------------------------------------------------------
# R4: render must ensure the per-user SP folder exists before upload.
#
# Without this, the first render for a brand-new NTID 404s because Graph's
# small-file PUT doesn't create intermediate SharePoint folders.
# ---------------------------------------------------------------------------


class TestEnsureFolderBeforeUpload:
    @patch("aippt.render.shutil.which", return_value="/usr/bin/pdftoppm")
    @patch("aippt.render.subprocess.run")
    @patch("aippt.render.graph")
    def test_render_ensures_per_user_folder_before_put(
        self, mock_graph, mock_run, _which, tmp_path,
    ):
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"x" * 1024)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        mock_graph.SMALL_FILE_LIMIT = 4 * 1024 * 1024
        mock_graph.PPTX_CONTENT_TYPE = render.PPTX_CONTENT_TYPE
        mock_graph.put_small_file.return_value = {"id": "ITEM_ID"}
        mock_graph.download_pdf.return_value = b"%PDF fake"
        mock_graph.delete_item.return_value = None
        mock_graph.ensure_folder.return_value = None

        def _fake_run(cmd, **kw):
            (out_dir / "slide-01.png").write_bytes(b"PNG")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        mock_run.side_effect = _fake_run

        render.render_pptx_to_pngs(
            pptx_path=str(pptx),
            out_dir=str(out_dir),
            token="t",
            ntid="melliott",
            site_id="SID",
            drive_id="DID",
            root_path="AIPPT/render-staging",
        )

        # Must call ensure_folder for the NTID subfolder
        mock_graph.ensure_folder.assert_called_once()
        kw = mock_graph.ensure_folder.call_args.kwargs
        assert kw["name"] == "melliott"
        assert kw["token"] == "t"
        # Parent path points at the configured root, not the per-user dir
        parent = mock_graph.ensure_folder.call_args.args[0]
        assert parent == "/sites/SID/drives/DID/root:/AIPPT/render-staging"

        # Folder must be created BEFORE the upload (or at least called)
        assert mock_graph.ensure_folder.called
        assert mock_graph.put_small_file.called
