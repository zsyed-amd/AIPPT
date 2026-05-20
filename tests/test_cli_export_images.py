"""Tests for the platform routing in `cmd_export_images`.

On Linux: route through `aippt.render.render_pptx_to_pngs` (Graph pipeline).
On Windows: keep the existing PowerShell COM path.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aippt import cli
from aippt.config import SharePointConfig


def _make_args(deck, out_dir, **overrides):
    base = dict(
        deck=str(deck),
        out_dir=str(out_dir),
        width=1920,
        height=1080,
        ms_token=None,
        gateway_config="gateway.yaml",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.fixture
def fake_deck(tmp_path):
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"PPTX-fake")
    return deck


class TestLinuxBranch:
    @patch("aippt.cli.sys.platform", "linux")
    @patch("aippt.cli.load_sharepoint_config")
    @patch("aippt.cli.render.render_pptx_to_pngs")
    def test_linux_routes_to_render_module(
        self, mock_render, mock_load_sp, fake_deck, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "tok-from-env")
        mock_load_sp.return_value = SharePointConfig(
            site_id="SID", drive_id="DID", root_path="AIPPT/render-staging",
        )
        mock_render.return_value = [tmp_path / "out" / "slide-1.png"]

        out_dir = tmp_path / "out"
        rc = cli.cmd_export_images(_make_args(fake_deck, out_dir))

        assert rc == 0
        mock_render.assert_called_once()
        kwargs = mock_render.call_args.kwargs
        assert kwargs["pptx_path"] == str(fake_deck)
        assert kwargs["out_dir"] == str(out_dir)
        assert kwargs["token"] == "tok-from-env"
        assert kwargs["site_id"] == "SID"
        assert kwargs["drive_id"] == "DID"
        assert kwargs["root_path"] == "AIPPT/render-staging"

    @patch("aippt.cli.sys.platform", "linux")
    @patch("aippt.cli.load_sharepoint_config")
    @patch("aippt.cli.render.render_pptx_to_pngs")
    def test_explicit_ms_token_arg_beats_env(
        self, mock_render, mock_load_sp, fake_deck, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "env-tok")
        mock_load_sp.return_value = SharePointConfig("S", "D", "r")
        mock_render.return_value = []

        cli.cmd_export_images(_make_args(
            fake_deck, tmp_path / "out", ms_token="cli-tok",
        ))
        assert mock_render.call_args.kwargs["token"] == "cli-tok"

    @patch("aippt.cli.sys.platform", "linux")
    @patch("aippt.cli.load_sharepoint_config")
    def test_linux_no_token_returns_error_with_clear_message(
        self, mock_load_sp, fake_deck, tmp_path, monkeypatch, caplog,
    ):
        monkeypatch.delenv("MS_ACCESS_TOKEN", raising=False)
        mock_load_sp.return_value = SharePointConfig("S", "D", "r")

        rc = cli.cmd_export_images(_make_args(fake_deck, tmp_path / "out"))
        assert rc != 0
        combined = caplog.text.lower()
        assert "microsoft sign-in" in combined or "ms_access_token" in combined

    @patch("aippt.cli.sys.platform", "linux")
    @patch("aippt.cli.load_sharepoint_config", return_value=None)
    def test_linux_no_sp_config_returns_error_with_clear_message(
        self, _mock_load, fake_deck, tmp_path, monkeypatch, caplog,
    ):
        monkeypatch.setenv("MS_ACCESS_TOKEN", "tok")
        rc = cli.cmd_export_images(_make_args(fake_deck, tmp_path / "out"))
        assert rc != 0
        assert "sharepoint" in caplog.text.lower()

    @patch("aippt.cli.sys.platform", "linux")
    @patch("aippt.cli.load_sharepoint_config")
    @patch("aippt.cli.render.render_pptx_to_pngs")
    def test_linux_graph_error_propagates(
        self, mock_render, mock_load_sp, fake_deck, tmp_path, monkeypatch,
    ):
        """GraphError from the render module must NOT be caught and squashed
        into rc=1 — it has to propagate so ingest_deck can re-raise it and
        the SSE worker can emit ``{status: <code>}`` for the JS sign-out hook.
        Regression guard for R9.
        """
        from aippt import graph
        monkeypatch.setenv("MS_ACCESS_TOKEN", "tok")
        mock_load_sp.return_value = SharePointConfig("S", "D", "r")
        mock_render.side_effect = graph.GraphError(
            401, "InvalidAuthenticationToken", "Token expired",
        )
        with pytest.raises(graph.GraphError) as caught:
            cli.cmd_export_images(_make_args(fake_deck, tmp_path / "out"))
        assert caught.value.status_code == 401


class TestWindowsBranch:
    @patch("aippt.cli.sys.platform", "win32")
    @patch("aippt.cli._find_powershell", return_value="/usr/bin/pwsh")
    @patch("aippt.cli._is_wsl", return_value=False)
    @patch("aippt.cli.subprocess.run")
    def test_windows_uses_powershell_path(
        self, mock_run, _wsl, _find, fake_deck, tmp_path
    ):
        # Stand in for the bundled PS script lookup so existing behavior holds
        mock_run.return_value = MagicMock(returncode=0)

        with patch("aippt.cli.os.path.exists", return_value=True):
            rc = cli.cmd_export_images(_make_args(fake_deck, tmp_path / "out"))

        assert rc == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "/usr/bin/pwsh"
        assert "-File" in cmd
